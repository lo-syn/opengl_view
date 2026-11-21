import math
import struct
import unittest
from unittest.mock import Mock, patch

import mido
from PyQt6.QtMultimedia import QAudioFormat

from audio_handler import ATTACK_SECONDS, AudioHandler
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


if __name__ == "__main__":
    unittest.main()
