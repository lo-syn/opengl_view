import logging
import math
import struct
from pathlib import Path
import json
from typing import Optional, Callable

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import (
    QAudioBuffer,
    QAudioBufferOutput,
    QAudioFormat,
    QAudioOutput,
    QMediaPlayer,
)

from osc_handler import OscHandler
from bluetooth_audio import BluetoothAudioManager, BluetoothDevice

# Import MIDI related settings from JSON file
with open("settings.json", "r") as f:
    settings = json.load(f)

AUDIO_FILE_PATH = Path(__file__).resolve().parent / settings["audio"]["file_path"]
AUDIO_OSC_ADDRESSES = settings["audio"]["osc_addresses"]
ATTACK_SECONDS = 0.01
RELEASE_SECONDS = 0.15

logger = logging.getLogger(__name__)


class AudioHandler:
    def __init__(
        self,
        osc_handler: OscHandler,
        file_path: Path | str = AUDIO_FILE_PATH,
        osc_address: str | None = None,
        enable_bluetooth: bool = False,
    ):
        self.osc_handler = osc_handler
        self.file_path = Path(file_path)
        self.osc_addresses = (
            (osc_address,) if osc_address is not None else AUDIO_OSC_ADDRESSES
        )

        # Initialize audio level and envelope tracking variables
        self.level = 0.0
        self._envelope = 0.0
        self._last_sent_level: float | None = None

        # Lazy initialization - create audio objects only when needed
        self.audio_output: Optional[QAudioOutput] = None
        self.player: Optional[QMediaPlayer] = None
        self.buffer_output: Optional[QAudioBufferOutput] = None

        # Initialize Bluetooth support if enabled
        self.bluetooth_manager: Optional[BluetoothAudioManager] = None
        self.use_bluetooth = False
        if enable_bluetooth:
            try:
                self.bluetooth_manager = BluetoothAudioManager()
                self.use_bluetooth = True
                logger.info("Bluetooth audio support initialized")
            except OSError as e:
                logger.warning(f"Bluetooth audio not available: {e}")

    def _init_audio_output(self) -> bool:
        """Initialize audio output objects (called on first use)."""
        if self.player is not None:
            return True  # Already initialized

        try:
            # Configure audio output, media player and activate audio buffer output
            self.audio_output = QAudioOutput()
            self.player = QMediaPlayer()
            self.player.setAudioOutput(self.audio_output)

            self.buffer_output = QAudioBufferOutput()
            self.player.setAudioBufferOutput(self.buffer_output)
            self.buffer_output.audioBufferReceived.connect(self._process_audio_buffer)
            self.player.mediaStatusChanged.connect(self._handle_media_status)
            self.player.errorOccurred.connect(self._handle_player_error)
            
            return True
        except Exception as e:
            logger.error(f"Failed to initialize audio output: {e}")
            return False

    def play(self, file_path: Path | str | None = None) -> None:
        """Start playing audio.
        
        If Bluetooth is enabled and connected, plays audio stream through Bluetooth.
        Otherwise, plays audio file through default speaker/headphones.
        """
        self._envelope = 0.0
        self._last_sent_level = None
        self._set_level(0.0)
        
        if self.use_bluetooth and self.bluetooth_manager:
            # Play through Bluetooth connection
            logger.info("Starting Bluetooth audio stream")
            self.bluetooth_manager.start_audio_stream()
        else:
            # Initialize audio output if needed
            if not self._init_audio_output():
                logger.error("Failed to initialize audio output")
                return
            
            # Play audio file through default output
            audio_path = Path(file_path) if file_path is not None else self.file_path
            if not audio_path.is_file():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            logger.info(f"Playing audio file: {audio_path}")
            self.player.setSource(QUrl.fromLocalFile(str(audio_path.resolve())))
            self.player.play()

    def stop(self) -> None:
        """Stop all audio playback."""
        if self.use_bluetooth and self.bluetooth_manager:
            # Stop Bluetooth stream
            self.bluetooth_manager.stop_audio_stream()
        elif self.player is not None:
            # Stop file playback (only if player was initialized)
            self.player.stop()
        
        self._envelope = 0.0
        self._set_level(0.0)

    def _process_audio_buffer(self, buffer: QAudioBuffer) -> None:
        if not buffer.isValid() or buffer.sampleCount() == 0:
            return

        raw_samples = buffer.data().asstring(buffer.byteCount())
        peak = self._peak_amplitude(raw_samples, buffer.format().sampleFormat())
        duration = buffer.duration() / 1_000_000
        if duration <= 0:
            sample_rate = buffer.format().sampleRate()
            if sample_rate <= 0:
                return
            duration = buffer.frameCount() / sample_rate

        time_constant = (
            ATTACK_SECONDS if peak > self._envelope else RELEASE_SECONDS
        )
        coefficient = math.exp(-duration / time_constant)
        self._envelope = peak + (self._envelope - peak) * coefficient
        self._set_level(self._envelope)

    @staticmethod
    def _peak_amplitude(raw_samples: bytes, sample_format: QAudioFormat.SampleFormat) -> float:
        # Caculates peak amplitude of the audio samples based on the sample format
        peak = 0.0
        if sample_format == QAudioFormat.SampleFormat.UInt8:
            return max(
                (abs((sample - 128) / 128) for sample in raw_samples),
                default=0.0,
            )

        # Determine sample code, size, and scale based on the sample format
        if sample_format == QAudioFormat.SampleFormat.Int16:
            sample_code, sample_size, scale = "h", 2, 32768.0
        elif sample_format == QAudioFormat.SampleFormat.Int32:
            sample_code, sample_size, scale = "i", 4, 2147483648.0
        elif sample_format == QAudioFormat.SampleFormat.Float:
            sample_code, sample_size, scale = "f", 4, 1.0
        else:
            raise ValueError(f"Unsupported audio sample format: {sample_format}")

        # Iterate through the raw samples and calculate the peak amplitude
        for offset in range(0, len(raw_samples) - sample_size + 1, sample_size):
            sample = struct.unpack_from("=" + sample_code, raw_samples, offset)[0]
            peak = max(peak, abs(sample / scale))
        return min(peak, 1.0)

    def _set_level(self, level: float) -> None:
        # Clamp the level to the range [0.0, 1.0]
        self.level = max(0.0, min(1.0, level))
        if self.level == self._last_sent_level:
            return

        # Send the updated level to all OSC addresses if it has changed
        for address in self.osc_addresses:
            self.osc_handler.set_level(address, "audio", self.level)
        self._last_sent_level = self.level

    def _handle_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        # Handle different media statuses, such as end of media
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._envelope = 0.0
            self._set_level(0.0)

    @staticmethod
    def _handle_player_error(
        error: QMediaPlayer.Error, error_string: str
    ) -> None:
        # Log the audio playback error with the error code and message
        logger.error("Audio playback error (%s): %s", error, error_string)

    # Bluetooth audio methods
    def scan_bluetooth_devices(self) -> list[BluetoothDevice]:
        """Scan for available Bluetooth audio devices."""
        if not self.bluetooth_manager:
            logger.warning("Bluetooth not initialized")
            return []
        return self.bluetooth_manager.scan_for_devices()

    def get_connected_bluetooth_devices(self) -> list[BluetoothDevice]:
        """Get list of currently connected Bluetooth devices."""
        if not self.bluetooth_manager:
            return []
        return self.bluetooth_manager.get_connected_devices()

    def connect_bluetooth_device(
        self, device: BluetoothDevice, set_as_default: bool = True
    ) -> bool:
        """Connect to a Bluetooth audio device."""
        if not self.bluetooth_manager:
            logger.error("Bluetooth manager not initialized")
            return False

        success = self.bluetooth_manager.connect(device, set_as_default)
        if success:
            self.use_bluetooth = True
            logger.info(f"Connected to Bluetooth device: {device.name}")
        return success

    def connect_bluetooth_device_async(
        self, device: BluetoothDevice, 
        callback: Optional[Callable[[bool, str], None]] = None,
        set_as_default: bool = True
    ) -> None:
        """Connect to a Bluetooth device asynchronously (non-blocking).
        
        Args:
            device: Device to connect to
            callback: Function called with (success, message) when complete
            set_as_default: Whether to set as default audio output
        """
        if not self.bluetooth_manager:
            if callback:
                callback(False, "Bluetooth not initialized")
            return
        
        def on_connect(success):
            if success:
                self.use_bluetooth = True
                message = f"Connected to {device.name}"
                logger.info(message)
            else:
                message = f"Failed to connect to {device.name}"
                logger.warning(message)
            
            if callback:
                callback(success, message)
        
        self.bluetooth_manager.connect_async(device, on_connect, set_as_default)

    def disconnect_bluetooth_device(self) -> bool:
        """Disconnect from the current Bluetooth device."""
        if not self.bluetooth_manager:
            return False

        success = self.bluetooth_manager.disconnect()
        if success:
            self.use_bluetooth = False
            logger.info("Disconnected from Bluetooth device")
        return success

    def enable_bluetooth_output(self, device: BluetoothDevice) -> bool:
        """Enable audio output to a Bluetooth device."""
        if not self.bluetooth_manager:
            logger.error("Bluetooth not available")
            return False

        # First connect to the device
        if not self.connect_bluetooth_device(device, set_as_default=True):
            return False

        self.use_bluetooth = True
        return True

    def disable_bluetooth_output(self) -> bool:
        """Disable Bluetooth audio output and return to default."""
        self.use_bluetooth = False
        return self.disconnect_bluetooth_device()

    def save_bluetooth_config(self) -> bool:
        """Save the current Bluetooth device configuration."""
        if self.bluetooth_manager:
            return self.bluetooth_manager.save_device_config()
        return False

    def load_bluetooth_config(self) -> bool:
        """Load and reconnect to the last used Bluetooth device."""
        if not self.bluetooth_manager:
            return False

        device = self.bluetooth_manager.load_device_config()
        if device:
            return self.connect_bluetooth_device(device)
        return False