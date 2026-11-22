import unittest
from unittest.mock import Mock, patch

from bluetooth_audio import BluetoothAudioManager, BluetoothDevice, DebianBluetoothBackend


class BluetoothConnectionTests(unittest.TestCase):
    def setUp(self):
        self.device = BluetoothDevice(
            name="Phone",
            mac_address="AA:BB:CC:DD:EE:FF",
            is_audio_device=True,
        )

    def test_linux_connect_does_not_change_default_output(self):
        backend = DebianBluetoothBackend.__new__(DebianBluetoothBackend)
        with patch(
            "bluetooth_audio.subprocess.run",
            side_effect=[
                Mock(returncode=0),
                Mock(returncode=0, stdout="Connection successful", stderr=""),
            ],
        ), patch.object(backend, "_set_pulseaudio_default") as set_default:
            self.assertTrue(backend.connect_device(self.device))

        set_default.assert_not_called()

    def test_manager_sets_default_only_when_requested(self):
        manager = BluetoothAudioManager.__new__(BluetoothAudioManager)
        manager.backend = Mock()
        manager.backend.connect_device.return_value = True
        manager.current_device = None

        self.assertTrue(manager.connect(self.device, set_as_default=False))
        manager.backend.set_as_default_output.assert_not_called()

        manager.current_device = None
        self.assertTrue(manager.connect(self.device, set_as_default=True))
        manager.backend.set_as_default_output.assert_called_once_with(self.device)


if __name__ == "__main__":
    unittest.main()
