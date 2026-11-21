import logging
import math
import struct
from pathlib import Path
import json

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import (
    QAudioBuffer,
    QAudioBufferOutput,
    QAudioFormat,
    QAudioOutput,
    QMediaPlayer,
)

from midi_handler import MIDI_CC_TO_OSC
from osc_handler import OscHandler

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

        # Configure audio output, media player and activate audio buffer output
        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        self.buffer_output = QAudioBufferOutput()
        self.player.setAudioBufferOutput(self.buffer_output)
        self.buffer_output.audioBufferReceived.connect(self._process_audio_buffer)
        self.player.mediaStatusChanged.connect(self._handle_media_status)
        self.player.errorOccurred.connect(self._handle_player_error)

    def play(self, file_path: Path | str | None = None) -> None:
        # Start playing audio file
        audio_path = Path(file_path) if file_path is not None else self.file_path
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        self._envelope = 0.0
        self._last_sent_level = None
        self._set_level(0.0)
        self.player.setSource(QUrl.fromLocalFile(str(audio_path.resolve())))
        self.player.play()

    def stop(self) -> None:
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