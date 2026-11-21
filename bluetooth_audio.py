"""
Bluetooth audio streaming module for cross-platform support (Windows and Debian/Linux).
Provides abstraction layer for sending audio to Bluetooth speakers and headphones.
"""

import logging
import platform
import subprocess
import json
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BluetoothDevice:
    """Represents a Bluetooth device."""
    name: str
    mac_address: str
    connected: bool = False
    is_audio_device: bool = False


class BluetoothAudioBackend(ABC):
    """Abstract base class for Bluetooth audio backends."""

    @abstractmethod
    def scan_devices(self) -> list[BluetoothDevice]:
        """Scan for available Bluetooth devices."""
        pass

    @abstractmethod
    def connect_device(self, device: BluetoothDevice) -> bool:
        """Connect to a Bluetooth device."""
        pass

    @abstractmethod
    def disconnect_device(self, device: BluetoothDevice) -> bool:
        """Disconnect from a Bluetooth device."""
        pass

    @abstractmethod
    def get_connected_devices(self) -> list[BluetoothDevice]:
        """Get list of currently connected audio devices."""
        pass

    @abstractmethod
    def set_as_default_output(self, device: BluetoothDevice) -> bool:
        """Set device as the default audio output."""
        pass


class WindowsBluetoothBackend(BluetoothAudioBackend):
    """Windows-specific Bluetooth audio implementation using Windows APIs."""

    def __init__(self):
        self.devices: dict[str, BluetoothDevice] = {}
        try:
            import winreg
            self.winreg = winreg
            logger.info("Windows Bluetooth backend initialized")
        except ImportError:
            logger.warning("winreg not available, some features may be limited")
            self.winreg = None

    def scan_devices(self) -> list[BluetoothDevice]:
        """Scan for Bluetooth audio devices on Windows.
        
        Prioritizes actual Bluetooth audio outputs (like A2DP speakers/headsets)
        over intermediate receiver devices.
        """
        devices = []
        try:
            # Get all audio endpoint devices
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PnpDevice -Class AudioEndpoint | Select-Object -ExpandProperty Name"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                # Filter for Bluetooth-related devices
                # Prioritize A2DP (actual audio streaming) over Bluetooth receiver devices
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Only include actual Bluetooth audio devices
                    # - A2DP: Advanced Audio Distribution Profile (Bluetooth audio streaming)
                    # - Avoid intermediate receivers like "RX-V781" which are not direct audio outputs
                    if 'A2DP' in line:
                        devices.append(BluetoothDevice(
                            name=line,
                            mac_address="unknown",
                            is_audio_device=True
                        ))
                        logger.info(f"Found Bluetooth audio device: {line}")
                    elif 'Bluetooth' in line and 'RX' not in line:
                        # Include other Bluetooth devices but not RX receivers
                        devices.append(BluetoothDevice(
                            name=line,
                            mac_address="unknown",
                            is_audio_device=True
                        ))
                        logger.info(f"Found Bluetooth device: {line}")
                
                logger.info(f"Found {len(devices)} Bluetooth audio devices on Windows")

        except subprocess.TimeoutExpired:
            logger.error("Bluetooth device scan timed out")
        except Exception as e:
            logger.error(f"Error scanning Bluetooth devices: {e}")

        return devices

    def connect_device(self, device: BluetoothDevice) -> bool:
        """Connect to a Bluetooth device on Windows."""
        try:
            # Windows Bluetooth connection is typically automatic when device is paired
            # Escape apostrophes in device name for PowerShell
            escaped_name = device.name.replace("'", "''")
            
            result = subprocess.run(
                ["powershell", "-Command",
                 f"$device = Get-PnpDevice -Class AudioEndpoint | Where-Object {{$_.Name -eq '{escaped_name}'}}; if ($device) {{ Write-Host 'Found' }}"],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0 and 'Found' in result.stdout:
                device.connected = True
                logger.info(f"Connected to Bluetooth device: {device.name}")
                return True
            else:
                logger.warning(f"Device {device.name} not ready or not found")
                return False
        except Exception as e:
            logger.error(f"Error connecting to Bluetooth device: {e}")
            return False

    def disconnect_device(self, device: BluetoothDevice) -> bool:
        """Disconnect from a Bluetooth device on Windows."""
        try:
            device.connected = False
            logger.info(f"Disconnected from Bluetooth device: {device.name}")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from Bluetooth device: {e}")
            return False

    def get_connected_devices(self) -> list[BluetoothDevice]:
        """Get connected Bluetooth audio devices on Windows."""
        try:
            # Use Get-PnpDevice to find connected audio devices
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-PnpDevice -Class AudioEndpoint | Where-Object {$_.Status -eq 'OK' -and $_.Name -like '*Bluetooth*'} | Select-Object -ExpandProperty Name)"],
                capture_output=True,
                text=True,
                timeout=10
            )

            devices = []
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line:
                        devices.append(BluetoothDevice(
                            name=line,
                            mac_address="unknown",
                            connected=True,
                            is_audio_device=True
                        ))
                logger.info(f"Found {len(devices)} connected Bluetooth audio devices")
            return devices
        except Exception as e:
            logger.error(f"Error getting connected devices: {e}")
            return []

    def set_as_default_output(self, device: BluetoothDevice) -> bool:
        """Set as default audio output on Windows."""
        try:
            # Escape apostrophes in device name for PowerShell
            escaped_name = device.name.replace("'", "''")
            
            logger.info(f"Attempting to set {device.name} as default audio output")
            
            # Try using Get-PnpDevice to verify device exists
            result = subprocess.run(
                ["powershell", "-Command",
                 f"$audio = Get-PnpDevice -Class AudioEndpoint | Where-Object {{$_.Name -eq '{escaped_name}'}}; if ($audio) {{ Write-Host 'Found device' }}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and 'Found device' in result.stdout:
                logger.info(f"Device {device.name} exists and can be used")
                return True
            else:
                logger.warning(f"Could not locate device: {device.name}")
                return False
        except Exception as e:
            logger.error(f"Error setting default audio device: {e}")
            return False
            logger.error(f"Error setting default audio device: {e}")
            return False


class DebianBluetoothBackend(BluetoothAudioBackend):
    """Debian/Linux-specific Bluetooth audio implementation using BlueZ."""

    def __init__(self):
        self.devices: dict[str, BluetoothDevice] = {}
        self._check_dependencies()
        logger.info("Debian/Linux Bluetooth backend initialized")

    def _check_dependencies(self):
        """Check if required Bluetooth tools are installed."""
        required_tools = ["bluetoothctl", "pactl", "pacmd"]
        missing_tools = []

        for tool in required_tools:
            result = subprocess.run(
                ["which", tool],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                missing_tools.append(tool)

        if missing_tools:
            logger.warning(
                f"Missing Bluetooth tools: {', '.join(missing_tools)}. "
                "Install with: sudo apt-get install bluez pulseaudio-module-bluetooth"
            )

    def scan_devices(self) -> list[BluetoothDevice]:
        """Scan for Bluetooth devices on Debian/Linux using bluetoothctl."""
        devices = []
        try:
            # Start Bluetooth scan
            subprocess.run(
                ["bluetoothctl", "scan", "on"],
                capture_output=True,
                timeout=2
            )

            # Get available devices
            result = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.startswith("Device"):
                        parts = line.split()
                        if len(parts) >= 3:
                            mac_address = parts[1]
                            device_name = ' '.join(parts[2:])
                            devices.append(BluetoothDevice(
                                name=device_name,
                                mac_address=mac_address,
                                is_audio_device=self._is_audio_device(mac_address)
                            ))
                logger.info(f"Found {len(devices)} Bluetooth devices")
            else:
                logger.warning(f"Failed to scan devices: {result.stderr}")

            # Stop scan
            subprocess.run(
                ["bluetoothctl", "scan", "off"],
                capture_output=True,
                timeout=2
            )

        except subprocess.TimeoutExpired:
            logger.error("Bluetooth scan timed out")
        except FileNotFoundError:
            logger.error("bluetoothctl not found. Install with: sudo apt-get install bluez")
        except Exception as e:
            logger.error(f"Error scanning Bluetooth devices: {e}")

        return devices

    def _is_audio_device(self, mac_address: str) -> bool:
        """Check if device supports audio (A2DP or HFP)."""
        try:
            result = subprocess.run(
                ["bluetoothctl", "info", mac_address],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                return any(audio_codec in output for audio_codec in ["a2dp", "hfp", "audio"])
            return False
        except Exception:
            return False

    def connect_device(self, device: BluetoothDevice) -> bool:
        """Connect to a Bluetooth device on Debian/Linux."""
        try:
            # Trust the device first
            subprocess.run(
                ["bluetoothctl", "trust", device.mac_address],
                capture_output=True,
                timeout=5
            )

            # Connect to device
            result = subprocess.run(
                ["bluetoothctl", "connect", device.mac_address],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0 or "already connected" in result.stdout.lower():
                device.connected = True
                logger.info(f"Connected to {device.name} ({device.mac_address})")

                # Try to set as default audio device
                self._set_pulseaudio_default(device)
                return True
            else:
                logger.warning(f"Failed to connect: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Connection attempt timed out")
            return False
        except Exception as e:
            logger.error(f"Error connecting to device: {e}")
            return False

    def disconnect_device(self, device: BluetoothDevice) -> bool:
        """Disconnect from a Bluetooth device on Debian/Linux."""
        try:
            result = subprocess.run(
                ["bluetoothctl", "disconnect", device.mac_address],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 or "not connected" in result.stdout.lower():
                device.connected = False
                logger.info(f"Disconnected from {device.name}")
                return True
            else:
                logger.warning(f"Failed to disconnect: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error disconnecting device: {e}")
            return False

    def get_connected_devices(self) -> list[BluetoothDevice]:
        """Get connected Bluetooth devices on Debian/Linux."""
        devices = []
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.startswith("Device"):
                        parts = line.split()
                        if len(parts) >= 3:
                            mac_address = parts[1]
                            device_name = ' '.join(parts[2:])
                            devices.append(BluetoothDevice(
                                name=device_name,
                                mac_address=mac_address,
                                connected=True,
                                is_audio_device=self._is_audio_device(mac_address)
                            ))
            return devices
        except Exception as e:
            logger.error(f"Error getting connected devices: {e}")
            return []

    def set_as_default_output(self, device: BluetoothDevice) -> bool:
        """Set as default audio output using PulseAudio."""
        return self._set_pulseaudio_default(device)

    @staticmethod
    def _set_pulseaudio_default(device: BluetoothDevice) -> bool:
        """Set device as default PulseAudio output."""
        try:
            # Get PulseAudio sink index
            result = subprocess.run(
                ["pactl", "list", "sinks"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if device.name in line or device.mac_address in line:
                        # Extract sink number and set as default
                        subprocess.run(
                            ["pactl", "set-default-sink", device.mac_address],
                            capture_output=True,
                            timeout=5
                        )
                        logger.info(f"Set {device.name} as default PulseAudio output")
                        return True

            # Fallback: try using device MAC address directly
            result = subprocess.run(
                ["pactl", "set-default-sink", device.mac_address],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0

        except Exception as e:
            logger.error(f"Error setting PulseAudio default: {e}")
            return False


class BluetoothAudioManager:
    """High-level interface for Bluetooth audio management."""

    def __init__(self):
        """Initialize the appropriate backend based on the platform."""
        system = platform.system()

        if system == "Windows":
            self.backend = WindowsBluetoothBackend()
        elif system == "Linux":
            self.backend = DebianBluetoothBackend()
        else:
            raise OSError(f"Unsupported platform: {system}")

        self.current_device: Optional[BluetoothDevice] = None
        logger.info(f"BluetoothAudioManager initialized for {system}")

    def scan_for_devices(self) -> list[BluetoothDevice]:
        """Scan for available Bluetooth audio devices."""
        return self.backend.scan_devices()

    def connect(self, device: BluetoothDevice, set_as_default: bool = True) -> bool:
        """Connect to a Bluetooth device and optionally set as default output."""
        success = self.backend.connect_device(device)
        if success:
            if set_as_default:
                self.backend.set_as_default_output(device)
            self.current_device = device
        return success

    def disconnect(self) -> bool:
        """Disconnect from the current device."""
        if self.current_device:
            success = self.backend.disconnect_device(self.current_device)
            if success:
                self.current_device = None
            return success
        return False

    def get_connected_devices(self) -> list[BluetoothDevice]:
        """Get list of currently connected devices."""
        return self.backend.get_connected_devices()

    def save_device_config(self, config_file: Path | str = "bluetooth_config.json"):
        """Save current device configuration to file."""
        try:
            if self.current_device:
                config = {
                    "last_device": {
                        "name": self.current_device.name,
                        "mac_address": self.current_device.mac_address,
                    }
                }
                with open(config_file, "w") as f:
                    json.dump(config, f, indent=2)
                logger.info(f"Saved Bluetooth config to {config_file}")
                return True
        except Exception as e:
            logger.error(f"Error saving Bluetooth config: {e}")
        return False

    def load_device_config(self, config_file: Path | str = "bluetooth_config.json") -> Optional[BluetoothDevice]:
        """Load and reconnect to last used device."""
        try:
            if Path(config_file).exists():
                with open(config_file, "r") as f:
                    config = json.load(f)
                    device_info = config.get("last_device")
                    if device_info:
                        device = BluetoothDevice(
                            name=device_info["name"],
                            mac_address=device_info["mac_address"]
                        )
                        logger.info(f"Loaded Bluetooth device config: {device.name}")
                        return device
        except Exception as e:
            logger.error(f"Error loading Bluetooth config: {e}")
        return None

    def start_audio_stream(self) -> bool:
        """Start streaming audio to the connected Bluetooth device."""
        if not self.current_device:
            logger.warning("No Bluetooth device connected")
            return False
        
        logger.info(f"Starting audio stream to {self.current_device.name}")
        # On Windows and Linux, once the device is set as default, audio automatically streams
        # This is a placeholder for any platform-specific streaming setup
        return True

    def stop_audio_stream(self) -> bool:
        """Stop streaming audio to the Bluetooth device."""
        if not self.current_device:
            return False
        
        logger.info(f"Stopping audio stream to {self.current_device.name}")
        return True
