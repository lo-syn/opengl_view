import math
import os
import struct
import unittest
from unittest.mock import Mock, patch

import mido
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtMultimedia import QAudioFormat

from audio_handler import (
    ATTACK_SECONDS,
    BLUETOOTH_ATTACK_SECONDS,
    BLUETOOTH_MAX_BUFFER_BYTES,
    BLUETOOTH_RELEASE_SECONDS,
    BLUETOOTH_SAMPLE_RATE,
    AudioHandler,
)
from midi_handler import MidiHandler
from osc_handler import OscHandler


class AudioLevelTests(unittest.TestCase):
    def setUp(self):
        with patch("osc_handler.socket.socket"):
            self.osc_handler = OscHandler()
        self.handler = AudioHandler.__new__(AudioHandler)
        self.handler.osc_handler = self.osc_handler
        self.handler.osc_addresses = ("/u_x0",)
        self.handler._last_sent_level = None
        self.handler._envelope = 0.0

    def test_level_is_clamped_and_sent_as_osc_float(self):
        for value, expected in ((-1.0, 0.0), (0.5, 0.5), (2.0, 1.0)):
            with self.subTest(value=value):
                self.handler._set_level(value)
                packet = self.handler.osc_handler.udp_socket.sendto.call_args.args[0]
                self.assertEqual(packet[:12], b"/u_x0\0\0\0,f\0\0")
                self.assertEqual(struct.unpack(">f", packet[12:])[0], expected)
                self.assertEqual(self.handler.level, expected)

    def test_audio_buffer_sends_normalized_smoothed_envelope(self):
        buffer = Mock()
        buffer.isValid.return_value = True
        buffer.sampleCount.return_value = 1
        buffer.byteCount.return_value = 4
        buffer.data.return_value.asstring.return_value = struct.pack("=f", 1.0)
        buffer.format.return_value.sampleFormat.return_value = QAudioFormat.SampleFormat.Float
        buffer.duration.return_value = 10_000

        self.handler._process_audio_buffer(buffer)

        packet = self.handler.osc_handler.udp_socket.sendto.call_args.args[0]
        self.assertAlmostEqual(
            struct.unpack(">f", packet[12:])[0],
            1.0 - math.exp(-0.01 / ATTACK_SECONDS),
        )

    @patch("audio.QAudioBufferOutput")
    @patch("audio.QMediaPlayer")
    @patch("audio.QAudioOutput")
    def test_default_and_custom_addresses(self, _output, _player, _buffer):
        osc_handler = self.osc_handler
        handler = AudioHandler(osc_handler)
        handler._set_level(0.5)
        handler._set_level(0.0)
        packets = [
            call.args[0] for call in osc_handler.udp_socket.sendto.call_args_list
        ]
        self.assertEqual(
            packets,
            [
                b"/u_x0\0\0\0,f\0\0" + struct.pack(">f", 0.5),
                b"/u_x1\0\0\0,f\0\0" + struct.pack(">f", 0.5),
                b"/u_x2\0\0\0,f\0\0" + struct.pack(">f", 0.5),
                b"/u_x3\0\0\0,f\0\0" + struct.pack(">f", 0.5),
                b"/u_x0\0\0\0,f\0\0" + struct.pack(">f", 0.0),
                b"/u_x1\0\0\0,f\0\0" + struct.pack(">f", 0.0),
                b"/u_x2\0\0\0,f\0\0" + struct.pack(">f", 0.0),
                b"/u_x3\0\0\0,f\0\0" + struct.pack(">f", 0.0),
            ],
        )

        osc_handler.udp_socket.sendto.reset_mock()
        custom_handler = AudioHandler(osc_handler, osc_address="/custom")
        custom_handler._set_level(0.5)
        packets = osc_handler.udp_socket.sendto.call_args_list
        self.assertEqual(len(packets), 1)
        self.assertEqual(
            packets[0].args[0], b"/custom\0,f\0\0" + struct.pack(">f", 0.5)
        )

    @patch("audio.QAudioBufferOutput")
    @patch("audio.QMediaPlayer")
    @patch("audio.QAudioOutput")
    def test_audio_and_midi_are_summed_clipped_and_restored(
        self, _output, _player, _buffer
    ):
        audio = AudioHandler(self.osc_handler)
        midi = MidiHandler(self.osc_handler)
        midi.midi_input = Mock()
        midi.midi_input.iter_pending.return_value = [
            mido.Message("control_change", control=120, value=64),
            mido.Message("control_change", control=121, value=32),
        ]
        midi.read_midi()
        audio._set_level(0.5)

        calls = self.osc_handler.udp_socket.sendto.call_args_list
        packets = [call.args[0] for call in calls[-4:]]
        values = [struct.unpack(">f", packet[12:])[0] for packet in packets]
        self.assertEqual([packet[:8] for packet in packets], [
            b"/u_x0\0\0\0", b"/u_x1\0\0\0", b"/u_x2\0\0\0", b"/u_x3\0\0\0"
        ])
        self.assertEqual(values[0], 1.0)
        self.assertAlmostEqual(values[1], 0.5 + 32 / 127.0)
        self.assertEqual(values[2:], [0.5, 0.5])

        midi.midi_input.iter_pending.return_value = [
            mido.Message("control_change", control=120, value=10)
        ]
        midi.read_midi()
        packet = self.osc_handler.udp_socket.sendto.call_args.args[0]
        self.assertAlmostEqual(struct.unpack(">f", packet[12:])[0], 0.5 + 10 / 127.0)

        audio.stop()
        packets = [
            call.args[0]
            for call in self.osc_handler.udp_socket.sendto.call_args_list[-4:]
        ]
        values = [struct.unpack(">f", packet[12:])[0] for packet in packets]
        self.assertAlmostEqual(values[0], 10 / 127.0)
        self.assertAlmostEqual(values[1], 32 / 127.0)
        self.assertEqual(values[2:], [0.0, 0.0])

    @patch("audio.QAudioBufferOutput")
    @patch("audio.QMediaPlayer")
    @patch("audio.QAudioOutput")
    def test_midi_controls_independent_audio_gains(self, _output, _player, _buffer):
        audio = AudioHandler(self.osc_handler)
        midi = MidiHandler(self.osc_handler)
        midi.midi_input = Mock()
        midi.midi_input.iter_pending.return_value = [
            mido.Message("control_change", control=16, value=0),
            mido.Message("control_change", control=17, value=64),
            mido.Message("control_change", control=18, value=127),
            mido.Message("control_change", control=19, value=0),
            mido.Message("control_change", control=120, value=32),
        ]
        midi.read_midi()
        audio._set_level(0.5)

        calls = self.osc_handler.udp_socket.sendto.call_args_list[-4:]
        values = [struct.unpack(">f", call.args[0][12:])[0] for call in calls]
        self.assertAlmostEqual(values[0], 32 / 127.0)
        self.assertAlmostEqual(values[1], 0.5 * 64 / 127.0)
        self.assertEqual(values[2:], [0.5, 0.0])

        midi.midi_input.iter_pending.return_value = [
            mido.Message("control_change", control=16, value=127),
            mido.Message("control_change", control=18, value=0),
        ]
        midi.read_midi()
        calls = self.osc_handler.udp_socket.sendto.call_args_list[-2:]
        self.assertEqual([call.args[0][:8] for call in calls], [
            b"/u_x0\0\0\0", b"/u_x2\0\0\0"
        ])
        self.assertAlmostEqual(
            struct.unpack(">f", calls[0].args[0][12:])[0], 32 / 127.0 + 0.5
        )
        self.assertEqual(struct.unpack(">f", calls[1].args[0][12:])[0], 0.0)


class BluetoothCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.osc = Mock()
        self.handler = AudioHandler(self.osc, osc_address="/audio")
        self.read_fd, self.write_fd = os.pipe()
        self.process = Mock()
        self.process.stdout = os.fdopen(self.read_fd, "rb", buffering=0)
        self.process.poll.return_value = None
        self.handler.ffmpeg_process = self.process
        self.handler._setup_bluetooth_audio_processing()

    def tearDown(self):
        self.handler.stop()
        if self.write_fd is not None:
            os.close(self.write_fd)

    def test_notifier_processes_split_frames_without_polling(self):
        frame = struct.pack("<hh", 32767, 32767)
        os.write(self.write_fd, frame[:3])
        self.app.processEvents()
        self.osc.set_level.assert_not_called()

        os.write(self.write_fd, frame[3:])
        self.app.processEvents()
        expected = (32767 / 32768) * (
            1 - math.exp(-1 / BLUETOOTH_SAMPLE_RATE / BLUETOOTH_ATTACK_SECONDS)
        )
        self.osc.set_level.assert_called_once()
        self.assertAlmostEqual(self.osc.set_level.call_args.args[2], expected)

    def test_backlog_keeps_only_recent_audio(self):
        old_audio = struct.pack("<hh", 32767, 32767)
        recent_silence = bytes(BLUETOOTH_MAX_BUFFER_BYTES)
        os.write(self.write_fd, old_audio + recent_silence)
        read = os.read
        with patch(
            "audio_handler.os.read",
            side_effect=lambda fd, size: read(fd, min(size, 1000)),
        ) as read_mock:
            self.app.processEvents()
        self.assertGreater(read_mock.call_count, 1)
        self.osc.set_level.assert_called_once_with("/audio", "audio", 0.0)

    def test_release_and_unexpected_end(self):
        os.write(self.write_fd, struct.pack("<hh", 32767, 32767) * 441)
        self.app.processEvents()
        attack_level = self.handler.level
        os.write(self.write_fd, bytes(441 * 4))
        self.app.processEvents()
        self.assertAlmostEqual(
            self.handler.level,
            attack_level * math.exp(-0.01 / BLUETOOTH_RELEASE_SECONDS),
        )
        os.close(self.write_fd)
        self.write_fd = None
        with self.assertLogs("audio_handler", level="ERROR") as logs:
            self.app.processEvents()
        self.assertIn("ended unexpectedly", logs.output[0])
        self.assertIsNone(self.handler.ffmpeg_process)
        self.assertEqual(self.handler.level, 0)

    def test_stop_and_restart_capture_with_low_latency_options(self):
        self.handler.stop()
        self.assertIsNone(self.handler._bluetooth_notifier)
        self.assertIsNone(self.handler.ffmpeg_process)
        self.process.terminate.assert_called_once()

        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, write_fd)
        process = Mock()
        process.stdout = os.fdopen(read_fd, "rb", buffering=0)
        process.poll.return_value = None
        self.handler.bluetooth_mode_enabled = True
        self.handler.use_bluetooth = True
        self.handler.bluetooth_manager = Mock()
        with patch("audio_handler.subprocess.Popen", return_value=process) as popen:
            self.assertTrue(self.handler.start_bluetooth_input_capture())
        command = popen.call_args.args[0]
        self.assertIn("--latency-msec=20", command)
        self.assertIn("--process-time-msec=10", command)

        self.osc.reset_mock()
        os.write(write_fd, struct.pack("<hh", 32767, 32767) * 441)
        self.app.processEvents()
        self.osc.set_level.assert_called_once()
        self.assertGreater(self.osc.set_level.call_args.args[2], 0.8)


if __name__ == "__main__":
    unittest.main()
