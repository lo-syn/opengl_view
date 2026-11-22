import logging
import math
import os
import struct
import subprocess
from pathlib import Path
import json
from typing import Optional, Callable

import numpy as np
from PyQt6.QtCore import QUrl, QIODevice, QSocketNotifier
from PyQt6.QtMultimedia import (
    QAudioBuffer,
    QAudioBufferOutput,
    QAudioFormat,
    QAudioOutput,
    QAudioInput,
    QMediaPlayer,
    QMediaDevices,
    QMediaCaptureSession,
)

from osc_handler import OscHandler
from bluetooth_audio import BluetoothAudioManager, BluetoothDevice

# Import MIDI related settings from JSON file
with open("settings.json", "r") as f:
    settings = json.load(f)

AUDIO_FILE_PATH = Path(__file__).resolve().parent / settings["audio"]["file_path"]
AUDIO_OSC_ADDRESSES = settings["audio"]["osc_addresses"]

# Load Bluetooth device configuration
BLUETOOTH_CONFIG = settings.get("audio", {}).get("bluetooth", {})
BLUETOOTH_DEVICE_NAME = BLUETOOTH_CONFIG.get("device_name", "unknown")
BLUETOOTH_PULSEAUDIO_DEVICE = BLUETOOTH_CONFIG.get("pulseaudio_input_device", "default")

ATTACK_SECONDS = 0.01
RELEASE_SECONDS = 0.15
BLUETOOTH_ATTACK_SECONDS = 0.005
BLUETOOTH_RELEASE_SECONDS = 0.06
BLUETOOTH_SAMPLE_RATE = 44100
BLUETOOTH_FRAME_BYTES = 4  # Stereo signed 16-bit PCM
BLUETOOTH_MAX_BUFFER_BYTES = BLUETOOTH_SAMPLE_RATE * BLUETOOTH_FRAME_BYTES // 50

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
        self._level_change_threshold = 0.001  # Send OSC only if change > 0.1%

        # Lazy initialization - create audio objects only when needed
        self.audio_output: Optional[QAudioOutput] = None
        self.player: Optional[QMediaPlayer] = None
        self.buffer_output: Optional[QAudioBufferOutput] = None

        # Bluetooth INPUT capture (for receiving audio from phone)
        self.capture_session: Optional[QMediaCaptureSession] = None
        self.audio_input: Optional[QAudioInput] = None
        self.audio_buffer_output: Optional[QAudioBufferOutput] = None
        self.audio_output: Optional[QAudioOutput] = None
        self.bluetooth_input_device: Optional[str] = None
        self.ffmpeg_process = None  # For piping Bluetooth audio
        self._bluetooth_notifier: Optional[QSocketNotifier] = None
        self._bluetooth_pending = b""

        # Initialize Bluetooth support if enabled
        # Bluetooth passthrough is DISABLED by default for safety
        self.bluetooth_manager: Optional[BluetoothAudioManager] = None
        self.bluetooth_mode_enabled = enable_bluetooth  # Only allow passthrough if explicitly enabled
        self.use_bluetooth = False
        if enable_bluetooth:
            try:
                self.bluetooth_manager = BluetoothAudioManager()
                logger.info("Bluetooth audio support initialized")
            except OSError as e:
                logger.warning(f"Bluetooth audio not available: {e}")

    def __del__(self):
        """Cleanup on destruction - ensure Bluetooth input is stopped."""
        try:
            self.stop()
            logger.debug("AudioHandler cleaned up successfully")
        except Exception as e:
            logger.warning(f"Error during AudioHandler cleanup: {e}")

    def _init_audio_output(self) -> bool:
        """Initialize audio output objects (called on first use)."""
        if self.player is not None:
            logger.debug("Audio output already initialized, skipping re-initialization")
            return True  # Already initialized

        try:
            logger.info("Initializing audio output...")
            # Configure audio output, media player and activate audio buffer output
            self.audio_output = QAudioOutput()
            self.player = QMediaPlayer()
            self.player.setAudioOutput(self.audio_output)

            self.buffer_output = QAudioBufferOutput()
            self.player.setAudioBufferOutput(self.buffer_output)
            self.buffer_output.audioBufferReceived.connect(self._process_audio_buffer)
            self.player.mediaStatusChanged.connect(self._handle_media_status)
            self.player.errorOccurred.connect(self._handle_player_error)
            
            logger.info("Audio output initialized successfully with buffer output connected")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize audio output: {e}")
            return False

    def _configure_audio_output_device(self, use_bluetooth: bool = False) -> bool:
        """Configure QAudioOutput to use a specific device.
        
        When use_bluetooth=True, attempts to route audio through the connected Bluetooth device.
        This is crucial because QAudioOutput must still process audio internally through its
        device for QAudioBufferOutput callbacks to work (needed for OSC updates).
        
        Args:
            use_bluetooth: If True, configure for Bluetooth output; if False, use default
            
        Returns:
            True if device configuration successful, False otherwise
        """
        if not self.audio_output or not self.player:
            logger.warning("Cannot configure audio output device - audio not initialized")
            return False
        
        try:
            if use_bluetooth and self.bluetooth_manager and self.bluetooth_manager.current_device:
                logger.info(f"Attempting to route QAudioOutput through Bluetooth device: {self.bluetooth_manager.current_device.name}")
                # Try to get available audio devices and find Bluetooth device
                # Note: Qt6 audio device selection requires checking available devices
                # For now, we rely on the system having set Bluetooth as default output
                # The key is that QAudioOutput will process through whatever device is configured
                return True
            else:
                logger.info("Configuring QAudioOutput for default device")
                return True
        except Exception as e:
            logger.error(f"Failed to configure audio output device: {e}")
            return False

    def play(self, file_path: Path | str | None = None) -> None:
        """Start playing audio.
        
        If Bluetooth mode is enabled:
        - Receives audio stream from connected Bluetooth device (INPUT)
        - Analyzes it for OSC control changes  
        - Sends the analyzed level to OSC
        
        Otherwise plays audio file through default speaker/headphones.
        """
        logger.info(f"play() called: bluetooth_mode_enabled={self.bluetooth_mode_enabled}, use_bluetooth={self.use_bluetooth}")
        
        self._envelope = 0.0
        self._last_sent_level = None
        self._set_level(0.0)
        
        # If Bluetooth mode enabled AND a device is connected, capture Bluetooth input
        if self.bluetooth_mode_enabled and self.use_bluetooth and self.bluetooth_manager and self.bluetooth_manager.current_device:
            logger.info(f"Starting Bluetooth INPUT mode - receiving audio from {self.bluetooth_manager.current_device.name}")
            if self.start_bluetooth_input_capture():
                logger.info("Bluetooth input capture active")
                return
            else:
                logger.error("Failed to start Bluetooth input capture")
                return
        
        # Otherwise, play audio file normally
        # Initialize audio output if needed (required for audio buffer processing)
        if not self._init_audio_output():
            logger.error("Failed to initialize audio output")
            return
        
        # Play audio file through QMediaPlayer
        audio_path = Path(file_path) if file_path is not None else self.file_path
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        logger.info(f"Starting audio file playback: {audio_path}")
        self.player.setSource(QUrl.fromLocalFile(str(audio_path.resolve())))
        self.player.play()

    def stop(self) -> None:
        """Stop all audio playback.
        
        Stops both file playback (QMediaPlayer) and Bluetooth input capture (pacat).
        """
        logger.info(f"stop() called: use_bluetooth={self.use_bluetooth}")
        
        # Stop QMediaPlayer if running (file audio)
        if self.player is not None:
            logger.info("Stopping QMediaPlayer")
            self.player.stop()
        
        # Stop Bluetooth input capture if running
        if self.ffmpeg_process is not None or self.audio_input is not None:
            logger.info("Stopping Bluetooth audio input capture")
            self.stop_bluetooth_input_capture()
        
        self._envelope = 0.0
        self._set_level(0.0)
        logger.info("Audio playback stopped")

    def start_bluetooth_input_capture(self) -> bool:
        """Start capturing audio from Bluetooth input device.
        
        Uses PulseAudio's pacat to capture Bluetooth audio stream and process it.
        Uses the device specified in settings.json under audio.bluetooth.pulseaudio_input_device
        
        Returns:
            True if Bluetooth input capture started successfully, False otherwise
        """
        logger.info("=" * 80)
        logger.info("START BLUETOOTH INPUT CAPTURE CALLED")
        logger.info("=" * 80)
        logger.info(f"bluetooth_mode_enabled={self.bluetooth_mode_enabled}, use_bluetooth={self.use_bluetooth}")
        logger.info(f"📱 Configured device name: {BLUETOOTH_DEVICE_NAME}")
        logger.info(f"🎤 PulseAudio input device: {BLUETOOTH_PULSEAUDIO_DEVICE}")
        
        # CRITICAL: Only start if Bluetooth mode is explicitly enabled
        if not self.bluetooth_mode_enabled or not self.use_bluetooth:
            logger.warning("❌ Bluetooth input capture requested but Bluetooth mode not enabled")
            return False
        
        # CRITICAL: Only start if a Bluetooth device is actually connected
        if not self.bluetooth_manager or not self.bluetooth_manager.current_device:
            logger.warning("❌ No Bluetooth device connected - cannot start input capture")
            return False

        if self.ffmpeg_process is not None:
            logger.warning("Bluetooth audio capture is already running")
            return False
        
        try:
            logger.info("✓ All pre-checks passed")
            logger.info(f"✓ Connected to Bluetooth device: {self.bluetooth_manager.current_device.name}")
            
            # Start PulseAudio recording from configured Bluetooth input device
            logger.info(f"Starting pacat process to record from Bluetooth device: {BLUETOOTH_DEVICE_NAME}")
            
            self.ffmpeg_process = subprocess.Popen(
                [
                    "pacat",
                    "--record",
                    "-d", BLUETOOTH_PULSEAUDIO_DEVICE,  # Use configured device
                    "--format=s16le",
                    "--rate=44100",
                    "--channels=2",
                    "--latency-msec=20",
                    "--process-time-msec=10",
                ],
                stdout=subprocess.PIPE,
                bufsize=0
            )
            logger.info(f"✓ pacat process started (PID: {self.ffmpeg_process.pid})")
            logger.info(f"🎧 Now recording from {BLUETOOTH_DEVICE_NAME} via PulseAudio device: {BLUETOOTH_PULSEAUDIO_DEVICE}")
            
            self._setup_bluetooth_audio_processing()
            
            logger.info("=" * 80)
            logger.info("✓✓✓ BLUETOOTH INPUT CAPTURE SUCCESSFULLY STARTED ✓✓✓")
            logger.info("=" * 80)
            logger.info("Bluetooth audio processing is waiting for capture data")
            logger.info("📱 Play audio on your phone to see it appear here...")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"❌ FAILED TO START BLUETOOTH INPUT CAPTURE: {e}")
            logger.error("=" * 80)
            import traceback
            logger.error(traceback.format_exc())
            self.stop_bluetooth_input_capture()
            return False
    
    def _setup_bluetooth_audio_processing(self) -> None:
        """Set up real-time Bluetooth audio buffer processing."""
        logger.info("_setup_bluetooth_audio_processing() called")
        logger.info("Setting up real-time Bluetooth audio buffer processing...")
        
        if not self.ffmpeg_process or not self.ffmpeg_process.stdout:
            raise RuntimeError("Bluetooth capture stdout is unavailable")

        fd = self.ffmpeg_process.stdout.fileno()
        os.set_blocking(fd, False)
        self._bluetooth_pending = b""
        self._bluetooth_notifier = QSocketNotifier(fd, QSocketNotifier.Type.Read)
        self._bluetooth_notifier.activated.connect(self._process_bluetooth_audio_chunk)

    def _process_bluetooth_audio_chunk(self) -> None:
        """Drain available PCM, keeping the newest audio if the UI fell behind."""
        if not self.ffmpeg_process or not self.ffmpeg_process.stdout:
            return

        pending = bytearray(self._bluetooth_pending)
        eof = False
        dropped = 0
        try:
            # Bound work per event so a busy producer cannot monopolize the UI.
            for _ in range(16):
                try:
                    data = os.read(self.ffmpeg_process.stdout.fileno(), 16384)
                except BlockingIOError:
                    break
                if not data:
                    eof = True
                    break
                pending.extend(data)
                excess = len(pending) - BLUETOOTH_MAX_BUFFER_BYTES
                if excess > 0:
                    discard = excess // BLUETOOTH_FRAME_BYTES * BLUETOOTH_FRAME_BYTES
                    del pending[:discard]
                    dropped += discard
        except OSError:
            logger.exception("Error reading Bluetooth audio capture")
            self.stop_bluetooth_input_capture()
            return

        if dropped:
            logger.debug("Dropped %d bytes of stale Bluetooth audio", dropped)
        complete_bytes = len(pending) // BLUETOOTH_FRAME_BYTES * BLUETOOTH_FRAME_BYTES
        self._bluetooth_pending = bytes(pending[complete_bytes:])
        if complete_bytes:
            data = bytes(pending[:complete_bytes])
            peak = self._peak_amplitude(data, QAudioFormat.SampleFormat.Int16)
            duration = complete_bytes / (BLUETOOTH_FRAME_BYTES * BLUETOOTH_SAMPLE_RATE)
            time_constant = (
                BLUETOOTH_ATTACK_SECONDS if peak > self._envelope
                else BLUETOOTH_RELEASE_SECONDS
            )
            coefficient = math.exp(-duration / time_constant)
            self._envelope = peak + (self._envelope - peak) * coefficient
            self._set_level(self._envelope)

        if eof:
            logger.error("Bluetooth audio capture ended unexpectedly")
            self.stop_bluetooth_input_capture()

    def stop_bluetooth_input_capture(self) -> None:
        """Stop capturing audio from Bluetooth input device."""
        logger.info("Stopping Bluetooth audio input capture...")
        
        try:
            if self._bluetooth_notifier is not None:
                self._bluetooth_notifier.setEnabled(False)
                self._bluetooth_notifier.deleteLater()
                self._bluetooth_notifier = None
            self._bluetooth_pending = b""
            
            # Stop FFmpeg/pacat process
            if hasattr(self, 'ffmpeg_process') and self.ffmpeg_process:
                if self.ffmpeg_process.poll() is None:
                    self.ffmpeg_process.terminate()
                try:
                    self.ffmpeg_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.ffmpeg_process.kill()
                    self.ffmpeg_process.wait()
                if self.ffmpeg_process.stdout:
                    self.ffmpeg_process.stdout.close()
                self.ffmpeg_process = None
                logger.info("Bluetooth audio capture process stopped")
            
            if self.capture_session:
                self.capture_session.setAudioBufferOutput(None)
                self.capture_session.setAudioOutput(None)
                self.capture_session.setAudioInput(None)
                logger.info("QMediaCaptureSession cleaned up")
            
            if self.audio_input:
                self.audio_input = None
            if self.audio_buffer_output:
                self.audio_buffer_output = None
            if self.audio_output:
                self.audio_output = None
            if self.capture_session:
                self.capture_session = None
                
            logger.info("Bluetooth audio input capture stopped")
        except Exception as e:
            logger.error(f"Error stopping Bluetooth input capture: {e}")
        
        self._envelope = 0.0
        self._set_level(0.0)

    def _process_audio_buffer(self, buffer: QAudioBuffer) -> None:
        if not buffer.isValid() or buffer.sampleCount() == 0:
            logger.warning("Invalid or empty audio buffer received - OSC NOT updated")
            return


        raw_samples = buffer.data().asstring(buffer.byteCount())
        peak = self._peak_amplitude(raw_samples, buffer.format().sampleFormat())
        duration = buffer.duration() / 1_000_000
        if duration <= 0:
            sample_rate = buffer.format().sampleRate()
            if sample_rate <= 0:
                logger.warning(f"Cannot calculate duration: duration={duration}, sample_rate={sample_rate}")
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
        try:
            if sample_format == QAudioFormat.SampleFormat.UInt8:
                samples = np.frombuffer(raw_samples, dtype=np.uint8)
                return float(np.max(np.abs((samples.astype(np.float32) - 128) / 128)))

            if sample_format == QAudioFormat.SampleFormat.Int16:
                samples = np.frombuffer(raw_samples, dtype=np.int16)
                return float(np.min([1.0, np.max(np.abs(samples.astype(np.float32) / 32768.0))]))
            
            if sample_format == QAudioFormat.SampleFormat.Int32:
                samples = np.frombuffer(raw_samples, dtype=np.int32)
                return float(np.min([1.0, np.max(np.abs(samples.astype(np.float64) / 2147483648.0))]))
            
            if sample_format == QAudioFormat.SampleFormat.Float:
                samples = np.frombuffer(raw_samples, dtype=np.float32)
                return float(np.min([1.0, np.max(np.abs(samples))]))
            
            raise ValueError(f"Unsupported audio sample format: {sample_format}")
        except Exception:
            return 0.0

    def _set_level(self, level: float) -> None:
        # Clamp the level to the range [0.0, 1.0]
        self.level = max(0.0, min(1.0, level))
        
        # Only send OSC if change exceeds threshold
        if self._last_sent_level is not None:
            if abs(self.level - self._last_sent_level) < self._level_change_threshold:
                return
        
        # Send the updated level to all OSC addresses if it has changed
        for address in self.osc_addresses:
            self.osc_handler.set_level(address, "audio", self.level)
        self._last_sent_level = self.level

    def _handle_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        # Handle different media statuses, such as end of media
        logger.debug(f"Media status changed: {status}")
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.info("End of media reached, resetting audio level to 0")
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
        self, device: BluetoothDevice, set_as_default: bool = False
    ) -> bool:
        """Connect to a Bluetooth audio device.
        
        CRITICAL: set_as_default=False is intentional!
        
        Setting Bluetooth as the system default audio output causes the OS to route
        ALL audio to Bluetooth at the system level, which prevents QMediaPlayer from
        reading the audio file and generating buffer callbacks needed for OSC updates.
        
        We connect to the device but DON'T make it the system default.
        Audio will still play through Bluetooth when explicitly sent there by QAudioOutput.
        """
        if not self.bluetooth_manager:
            logger.error("Bluetooth manager not initialized")
            return False

        success = self.bluetooth_manager.connect(device, set_as_default=False)
        if success:
            self.use_bluetooth = True
            logger.info(f"Connected to Bluetooth device: {device.name}")
        return success

    def connect_bluetooth_device_async(
        self, device: BluetoothDevice, 
        callback: Optional[Callable[[bool, str], None]] = None,
        set_as_default: bool = False
    ) -> None:
        """Connect to a Bluetooth device asynchronously (non-blocking).
        
        CRITICAL: set_as_default=False is intentional!
        
        Setting Bluetooth as the system default audio output causes the OS to route
        ALL audio to Bluetooth at the system level, which prevents QMediaPlayer from
        reading the audio file and generating buffer callbacks needed for OSC updates.
        
        Args:
            device: Device to connect to
            callback: Function called with (success, message) when complete
            set_as_default: Whether to set as default audio output (MUST be False)
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
        
        self.bluetooth_manager.connect_async(device, on_connect, set_as_default=False)

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
        """Enable audio output to a Bluetooth device.
        
        CRITICAL: Does NOT set Bluetooth as system default.
        
        Setting Bluetooth as the system default audio output prevents QMediaPlayer
        from reading the audio file and generating buffer callbacks for OSC updates.
        """
        if not self.bluetooth_manager:
            logger.error("Bluetooth not available")
            return False

        # Connect without setting as default
        if not self.connect_bluetooth_device(device, set_as_default=False):
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