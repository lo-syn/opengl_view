import os
import struct
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtMultimedia import QAudio
from PyQt6.QtWidgets import QApplication

from audio_handler import AudioHandler, AudioOutputRouter
from shader_menu import DefaultMenu


app = QApplication.instance() or QApplication([])


class AudioOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.device = Mock()
        self.device.description.return_value = "Speakers"
        self.device.id.return_value = b"speakers"
        self.device.isFormatSupported.return_value = True
        self.sink = Mock()
        self.sink.error.return_value = QAudio.Error.NoError
        self.sink.bytesFree.return_value = 4096
        self.sink.start.return_value.write.side_effect = len
        self.sink_patch = patch("audio_handler.QAudioSink", return_value=self.sink)
        self.sink_patch.start()
        self.addCleanup(self.sink_patch.stop)

    def test_sink_reports_open_and_later_errors(self):
        failed = Mock()
        router = AudioOutputRouter(failed)
        self.sink.start.return_value = None
        self.assertFalse(router.connect(self.device))
        self.assertIsNone(router.device)

        self.sink.start.return_value = Mock()
        self.assertTrue(router.connect(self.device))
        self.sink.error.return_value = QAudio.Error.IOError
        router._state_changed(QAudio.State.StoppedState)
        failed.assert_called_once_with("Speakers")
        router.disconnect()

    def test_file_output_is_muted_by_default_and_selects_device(self):
        router = AudioOutputRouter(Mock())
        handler = AudioHandler(Mock())
        handler.audio_output = Mock()
        handler.set_output_router(router)
        handler.audio_output.setMuted.assert_called_with(True)

        self.assertTrue(router.connect(self.device))
        handler.set_output_router(router)
        handler.audio_output.setDevice.assert_called_with(self.device)
        handler.audio_output.setMuted.assert_called_with(False)
        router.disconnect()
        handler.set_output_router(router)
        handler.audio_output.setMuted.assert_called_with(True)

    def test_bluetooth_capture_is_forwarded_only_while_enabled(self):
        router = AudioOutputRouter(Mock())
        handler = AudioHandler(Mock())
        handler.set_output_router(router)
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, write_fd)
        process = Mock()
        process.stdout = os.fdopen(read_fd, "rb", buffering=0)
        process.poll.return_value = None
        handler.ffmpeg_process = process
        handler._setup_bluetooth_audio_processing()
        self.addCleanup(handler.stop)
        frame = struct.pack("<hh", 123, 123)
        os.write(write_fd, frame)
        self.app.processEvents()
        self.sink.start.assert_not_called()

        self.assertTrue(router.connect(self.device))
        os.write(write_fd, frame)
        self.app.processEvents()
        self.sink.start.return_value.write.assert_called_once_with(frame)
        router.disconnect()

    def test_menu_cycles_devices_and_reports_failure(self):
        other = Mock()
        other.description.return_value = "Headphones"
        other.id.return_value = b"headphones"
        other.isFormatSupported.return_value = True
        with patch("shader_menu.OscHandler"), patch("shader_menu.BrowserHandler"), \
                patch("shader_menu.QMediaDevices.audioOutputs", return_value=[self.device, other]):
            menu = DefaultMenu()
            menu.show_settings()
            self.assertFalse(menu.settings["enable_audio_output"].state)
            menu._run_settings_option("enable_audio_output")
            self.assertEqual(menu.status_labels["enable_audio_output"].text(), "Speakers")
            menu._run_settings_option("enable_audio_output")
            self.assertEqual(menu.status_labels["enable_audio_output"].text(), "Headphones")
            menu._run_settings_option("enable_audio_output")
            self.assertEqual(menu.status_labels["enable_audio_output"].text(), "disabled")

            self.sink.start.return_value = None
            menu._run_settings_option("enable_audio_output")
            self.assertEqual(menu.status_bar.text(), "unable to connect to Speakers")
            self.assertFalse(menu.settings["enable_audio_output"].state)
            self.sink.start.return_value = Mock()
            menu._run_settings_option("enable_audio_output")
            self.assertEqual(menu.status_labels["enable_audio_output"].text(), "Headphones")
            menu._audio_output_failed("Headphones")
            self.assertEqual(menu.status_bar.text(), "unable to connect to Headphones")
            self.assertEqual(menu.status_labels["enable_audio_output"].text(), "disabled")
            menu.close()

    def test_removed_device_is_disabled_and_reported(self):
        with patch("shader_menu.OscHandler"), patch("shader_menu.BrowserHandler"), \
                patch("shader_menu.QMediaDevices.audioOutputs", return_value=[self.device]) as outputs:
            menu = DefaultMenu()
            menu.show_settings()
            menu._run_settings_option("enable_audio_output")
            outputs.return_value = []
            menu._audio_outputs_changed()
            self.assertEqual(menu.status_bar.text(), "unable to connect to Speakers")
            self.assertEqual(menu.status_labels["enable_audio_output"].text(), "disabled")
            menu.close()

    def test_no_devices_reports_failure(self):
        with patch("shader_menu.OscHandler"), patch("shader_menu.BrowserHandler"), \
                patch("shader_menu.QMediaDevices.audioOutputs", return_value=[]):
            menu = DefaultMenu()
            menu.show_settings()
            menu._run_settings_option("enable_audio_output")
            self.assertEqual(menu.status_bar.text(), "unable to connect to output device")
            self.assertFalse(menu.settings["enable_audio_output"].state)
            menu.close()


if __name__ == "__main__":
    unittest.main()
