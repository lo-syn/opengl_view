import json
import os
import struct
import threading
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtMultimedia import QAudio
from PyQt6.QtWidgets import QApplication

from audio_handler import (
    AudioHandler,
    AudioOutputRouter,
    BluetoothInputRouter,
    BLUETOOTH_CAPTURE_SINK,
)
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

    def test_bluetooth_input_router_owns_stream_and_restores_original_route(self):
        source_name = "bluez_source.aa_bb_cc_dd_ee_ff.a2dp_source"
        stream = {
            "index": 12,
            "sink": 5,
            "mute": False,
            "properties": {
                "api.bluez5.address": "AA:BB:CC:DD:EE:FF",
                "api.bluez5.profile": "a2dp-source",
                "object.serial": "34",
            },
        }
        unrelated = {**stream, "index": 13, "properties": {
            **stream["properties"], "api.bluez5.address": "11:22:33:44:55:66"
        }}
        state = {"stream": stream, "unrelated": unrelated}
        calls = []

        def run_pactl(command, **_kwargs):
            calls.append(command)
            if command[1:] == ["-f", "json", "list", "sink-inputs"]:
                return Mock(
                    returncode=0,
                    stdout=json.dumps([state["stream"], state["unrelated"]]),
                    stderr="",
                )
            if command[1] == "set-sink-input-mute":
                state["stream"]["mute"] = command[3] == "true"
            elif command[1] == "load-module":
                return Mock(returncode=0, stdout="42\n", stderr="")
            elif command[1:] == ["-f", "json", "list", "sinks"]:
                return Mock(
                    returncode=0,
                    stdout=json.dumps([{
                        "index": 11,
                        "name": "opengl_viewer_bluetooth_capture",
                    }]),
                    stderr="",
                )
            elif command[1] == "move-sink-input":
                state["stream"]["sink"] = int(command[3])
            return Mock(returncode=0, stdout="", stderr="")

        with patch(
            "audio_handler.BLUETOOTH_PULSEAUDIO_INPUT_DEVICE", source_name
        ), patch(
            "audio_handler.subprocess.run",
            side_effect=run_pactl,
        ):
            router = BluetoothInputRouter()
            self.assertTrue(router.set_enabled(False))
            self.assertTrue(state["stream"]["mute"])

            self.assertTrue(router.set_enabled(True))
            self.assertEqual(state["stream"]["sink"], 11)
            self.assertFalse(state["stream"]["mute"])
            mute_call_count = sum(
                command[1] == "set-sink-input-mute" for command in calls
            )
            self.assertTrue(router.sync())
            self.assertEqual(
                sum(command[1] == "set-sink-input-mute" for command in calls),
                mute_call_count,
            )

            self.assertTrue(router.set_enabled(False))
            self.assertEqual(state["stream"]["sink"], 5)
            self.assertTrue(state["stream"]["mute"])
            self.assertTrue(router.restore())

        self.assertEqual(state["stream"]["sink"], 5)
        self.assertFalse(state["stream"]["mute"])
        self.assertEqual(state["unrelated"]["sink"], 5)
        self.assertFalse(state["unrelated"]["mute"])
        self.assertEqual(
            [command[3] for command in calls if command[1] == "move-sink-input"],
            ["11", "5"],
        )

    def test_muted_bluetooth_stream_is_audible_only_during_capture(self):
        stream = {
            "index": 12,
            "sink": 5,
            "mute": True,
            "properties": {
                "api.bluez5.address": "AA:BB:CC:DD:EE:FF",
                "api.bluez5.profile": "a2dp-source",
                "object.serial": "34",
            },
        }

        def set_muted(_index, muted):
            stream["mute"] = muted
            return True

        def move_to_sink(_index, sink):
            stream["sink"] = sink
            return True

        with patch(
            "audio_handler.BLUETOOTH_PULSEAUDIO_INPUT_DEVICE",
            "bluez_source.aa_bb_cc_dd_ee_ff.a2dp_source",
        ):
            router = BluetoothInputRouter()
        router.capture_sink_id = 11
        with patch.object(router, "_list_sink_inputs", side_effect=lambda: [stream]), \
                patch.object(router, "_ensure_capture_sink", return_value=True), \
                patch.object(router, "_unload_capture_sink", return_value=True), \
                patch.object(router, "_set_muted", side_effect=set_muted), \
                patch.object(router, "_move_to_sink", side_effect=move_to_sink):
            self.assertTrue(router.set_enabled(True))
            self.assertFalse(stream["mute"])
            self.assertEqual(stream["sink"], 11)
            self.assertTrue(router.set_enabled(False))
            self.assertTrue(stream["mute"])
            self.assertTrue(router.restore())
            self.assertTrue(stream["mute"])
            self.assertEqual(stream["sink"], 5)

    def test_menu_cycles_devices_and_reports_failure(self):
        other = Mock()
        other.description.return_value = "Headphones"
        other.id.return_value = b"headphones"
        other.isFormatSupported.return_value = True
        private_sink = Mock()
        private_sink.description.return_value = BLUETOOTH_CAPTURE_SINK
        private_sink.id.return_value = b"private-capture"
        with patch("shader_menu.OscHandler"), patch("shader_menu.BrowserHandler"), \
                patch("shader_menu.BluetoothInputRouter"), \
                patch(
                    "shader_menu.QMediaDevices.audioOutputs",
                    return_value=[self.device, private_sink, other],
                ):
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
                patch("shader_menu.BluetoothInputRouter"), \
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
                patch("shader_menu.BluetoothInputRouter"), \
                patch("shader_menu.QMediaDevices.audioOutputs", return_value=[]):
            menu = DefaultMenu()
            menu.show_settings()
            menu._run_settings_option("enable_audio_output")
            self.assertEqual(menu.status_bar.text(), "unable to connect to output device")
            self.assertFalse(menu.settings["enable_audio_output"].state)
            menu.close()

    def test_menu_routes_bluetooth_only_when_selected(self):
        with patch("shader_menu.OscHandler"), patch("shader_menu.BrowserHandler"), \
                patch("shader_menu.BluetoothInputRouter") as router_factory:
            menu = DefaultMenu()
            router = router_factory.return_value
            menu.audio_mode = 1
            menu._sync_bluetooth_input_route()
            router.set_enabled.assert_called_with(True)

            menu.audio_mode = 0
            menu._sync_bluetooth_input_route()
            router.set_enabled.assert_called_with(False)
            menu.close()

    def test_slow_route_poll_does_not_block_audio_processing(self):
        started = threading.Event()
        release = threading.Event()

        def slow_sync():
            started.set()
            return release.wait(5)

        with patch("shader_menu.OscHandler"), patch("shader_menu.BrowserHandler"), \
                patch("shader_menu.BluetoothInputRouter") as router_factory:
            router_factory.return_value.sync.side_effect = slow_sync
            menu = DefaultMenu()
            menu.bluetooth_input_router_timer.stop()
            handler = AudioHandler(Mock())
            read_fd, write_fd = os.pipe()
            process = Mock()
            process.stdout = os.fdopen(read_fd, "rb", buffering=0)
            process.poll.return_value = None
            handler.ffmpeg_process = process
            handler._setup_bluetooth_audio_processing()
            try:
                menu._poll_bluetooth_input_route()
                self.assertTrue(started.wait(1))
                menu._poll_bluetooth_input_route()
                router_factory.return_value.sync.assert_called_once()

                os.write(write_fd, struct.pack("<hh", 32767, 32767) * 441)
                self.app.processEvents()
                self.assertGreater(handler.level, 0)
            finally:
                release.set()
                handler.stop()
                os.close(write_fd)
                menu.close()

    def test_outdated_poll_result_does_not_override_new_route_state(self):
        with patch("shader_menu.OscHandler"), patch("shader_menu.BrowserHandler"), \
                patch("shader_menu.BluetoothInputRouter"):
            menu = DefaultMenu()
            generation = menu._bluetooth_route_generation
            menu._sync_bluetooth_input_route()
            menu._bluetooth_route_check_finished(generation, False)
            self.assertNotEqual(
                menu.message_bar.text(), "Could not route Bluetooth audio through the app"
            )
            menu.close()


if __name__ == "__main__":
    unittest.main()
