import logging
import math
import struct
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import (
    QAudioBuffer,
    QAudioBufferOutput,
    QAudioFormat,
    QAudioOutput,
    QMediaPlayer,
)

from osc_handler import OSC_HOST, OSC_PORT, OscHandler, osc_string


AUDIO_FILE_PATH = Path(r"C:\Users\Laurence\Documents\Music\Plata - Kru (MssingNo Remix).mp3")
AUDIO_OSC_ADDRESS = "/u_x0"
LEVEL_MAX = 127
ATTACK_SECONDS = 0.01
RELEASE_SECONDS = 0.15

logger = logging.getLogger(__name__)


class AudioHandler:
    def __init__(
        self,
        osc_handler: OscHandler,
        file_path: Path | str = AUDIO_FILE_PATH,
        osc_address: str = AUDIO_OSC_ADDRESS,
    ):
        self.osc_handler = osc_handler
        self.file_path = Path(file_path)
        self.osc_address = osc_address
        self.level = 0
        self._envelope = 0.0
        self._last_sent_level: int | None = None

        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        self.buffer_output = QAudioBufferOutput()
        self.player.setAudioBufferOutput(self.buffer_output)
        self.buffer_output.audioBufferReceived.connect(self._process_audio_buffer)
        self.player.mediaStatusChanged.connect(self._handle_media_status)
        self.player.errorOccurred.connect(self._handle_player_error)

    def play(self, file_path: Path | str | None = None) -> None:
        audio_path = Path(file_path) if file_path is not None else self.file_path
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        self._envelope = 0.0
        self._last_sent_level = None
        self._set_level(0)
        self.player.setSource(QUrl.fromLocalFile(str(audio_path.resolve())))
        self.player.play()

    def stop(self) -> None:
        self.player.stop()
        self._envelope = 0.0
        self._set_level(0)

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
        self._set_level(round(self._envelope * LEVEL_MAX))

    @staticmethod
    def _peak_amplitude(raw_samples: bytes, sample_format: QAudioFormat.SampleFormat) -> float:
        peak = 0.0
        if sample_format == QAudioFormat.SampleFormat.UInt8:
            return max(
                (abs((sample - 128) / 128) for sample in raw_samples),
                default=0.0,
            )

        if sample_format == QAudioFormat.SampleFormat.Int16:
            sample_code, sample_size, scale = "h", 2, 32768.0
        elif sample_format == QAudioFormat.SampleFormat.Int32:
            sample_code, sample_size, scale = "i", 4, 2147483648.0
        elif sample_format == QAudioFormat.SampleFormat.Float:
            sample_code, sample_size, scale = "f", 4, 1.0
        else:
            raise ValueError(f"Unsupported audio sample format: {sample_format}")

        for offset in range(0, len(raw_samples) - sample_size + 1, sample_size):
            sample = struct.unpack_from("=" + sample_code, raw_samples, offset)[0]
            peak = max(peak, abs(sample / scale))
        return min(peak, 1.0)

    def _set_level(self, level: int) -> None:
        self.level = max(0, min(LEVEL_MAX, level))
        if self.level == self._last_sent_level:
            return

        packet = (
            osc_string(self.osc_address)
            + osc_string(",i")
            + struct.pack(">i", self.level)
        )
        self.osc_handler.udp_socket.sendto(packet, (OSC_HOST, OSC_PORT))
        self._last_sent_level = self.level

    def _handle_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._envelope = 0.0
            self._set_level(0)

    @staticmethod
    def _handle_player_error(
        error: QMediaPlayer.Error, error_string: str
    ) -> None:
        logger.error("Audio playback error (%s): %s", error, error_string)