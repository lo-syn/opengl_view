# Bluetooth Audio Passthrough Prevention

## Problem Solved
Previously, once a Bluetooth device was connected to the system, audio would automatically pass through it even if the application hadn't explicitly enabled Bluetooth mode. This made it impossible to prevent unwanted audio routing.

## Solution Implemented
The application now prevents automatic Bluetooth passthrough during initialization by explicitly setting the default audio output to a non-Bluetooth device (speakers/headphones).

## Technical Details

### How It Works

#### Debian/Linux (PulseAudio)
On initialization (`BluetoothAudioBackend.__init__`):

1. **Scan audio sinks**: Uses `pactl list sinks` to get all available audio outputs
2. **Filter Bluetooth**: Removes any sinks with 'bluez' or 'bluetooth' in the name
3. **Set default**: Calls `pactl set-default-sink <speaker_sink>` to set a non-Bluetooth device as default
4. **Result**: Audio routed to built-in speakers, not Bluetooth

**Key Methods**:
- `_get_non_bluetooth_sinks()` - Scans and filters audio devices
- `_set_default_to_non_bluetooth()` - Sets system default to non-Bluetooth output

#### Windows
On initialization:
1. Checks if current default audio device is Bluetooth
2. Logs warning if Bluetooth is default (manual intervention may be needed)
3. Windows device management is more complex, but logging helps identify issues

### Application Flow

```
Application Startup
│
└─→ BluetoothAudioManager()
    └─→ BluetoothAudioBackend (Windows/Debian)
        └─→ __init__()
            └─→ _set_default_to_non_bluetooth()
                ├─→ [Linux] Gets all sinks
                ├─→ [Linux] Filters Bluetooth devices
                ├─→ [Linux] Sets default to speakers
                └─→ ✓ Bluetooth passthrough PREVENTED

User Connects Bluetooth Device (System Level)
│
├─→ Device is connected ✓
├─→ Device appears in app's device list ✓
└─→ But system audio routes to speakers, NOT Bluetooth ✓

User Enables Bluetooth Mode in App
│
└─→ Calls connect_bluetooth_device(device)
    └─→ Calls pactl set-default-sink <bluetooth_device>
        └─→ ✓ Audio now flows to Bluetooth device

User Disables Audio or Switches Modes
│
└─→ Calls _stop_all_audio()
    └─→ System defaults back to built-in speakers
        └─→ ✓ Bluetooth passthrough stopped
```

## Code Changes

### File: bluetooth_audio.py

#### 1. WindowsBluetoothBackend.__init__() (Lines 59-68)
Added call to `_set_default_to_non_bluetooth()` during initialization to check and log Bluetooth status.

```python
def __init__(self):
    # ...
    self._set_default_to_non_bluetooth()  # Added this line
    logger.info("Windows Bluetooth backend initialized")
```

#### 2. DebianBluetoothBackend.__init__() (Lines 250-258)
Added call to `_set_default_to_non_bluetooth()` during initialization to prevent passthrough.

```python
def __init__(self):
    # ...
    self._set_default_to_non_bluetooth()  # Added this line
    logger.info("Debian/Linux Bluetooth backend initialized")
```

#### 3. New Method: _get_non_bluetooth_sinks() (Lines 462-493)
Retrieves all audio sinks and filters out Bluetooth devices.

```python
@staticmethod
def _get_non_bluetooth_sinks() -> list[str]:
    """Get list of non-Bluetooth audio sinks (speakers, headphones, etc)."""
    # Uses pactl list sinks to find all audio outputs
    # Filters out anything with 'bluez' or 'bluetooth' in the name
    # Returns list of non-Bluetooth sink names
```

#### 4. New Method: _set_default_to_non_bluetooth() (Lines 495-531)
Sets the default audio output to a non-Bluetooth device.

```python
@staticmethod
def _set_default_to_non_bluetooth() -> bool:
    """Set default audio output to a non-Bluetooth device.
    
    This prevents automatic audio passthrough to Bluetooth devices.
    Called during initialization to ensure audio doesn't flow to Bluetooth
    unless explicitly enabled by the application.
    """
    # Gets non-Bluetooth sinks using _get_non_bluetooth_sinks()
    # Sets first non-Bluetooth sink as default via pactl
    # Logs success or failure
```

## User Experience

### Before Changes
1. User connects Bluetooth device via system settings
2. Audio automatically flows to Bluetooth device
3. User must manually set audio back to speakers in system settings

### After Changes
1. User connects Bluetooth device via system settings
2. Audio remains on built-in speakers (application prevents passthrough)
3. User enables Bluetooth mode in application
4. User selects device in application
5. Audio flows to Bluetooth device (application routes it explicitly)
6. User switches audio mode or disables audio
7. Audio returns to speakers automatically

## System Requirements

**Debian/Linux**:
- PulseAudio with `pactl` utility
- Bluetooth tools (bluez, bluetoothctl)
- Command: `sudo apt-get install bluez pulseaudio-module-bluetooth`

**Windows**:
- Windows 10 or later
- PowerShell with AudioDevice module (optional, for enhanced support)

## Logging

The application logs passthrough prevention events:

```
INFO: Debian/Linux Bluetooth backend initialized
INFO: Set default audio output to: alsa_output.pci-0000_00_1b.0.analog-stereo
WARNING: No non-Bluetooth audio sinks found  (if only Bluetooth devices present)
ERROR: Error getting non-Bluetooth sinks: <error details>
```

## Edge Cases

### No Non-Bluetooth Audio Devices
If the system has no speakers or built-in audio:
- Method returns False and logs warning
- Application continues normally
- User may need to manually manage audio devices

### Multiple Audio Devices
If multiple non-Bluetooth devices present:
- Uses the first device found (usually primary speaker)
- User can manually switch via system settings if needed

### Device Disconnection
If Bluetooth device is disconnected:
- System audio remains on built-in speakers
- Application continues normally

## Security/Safety Benefits

✓ **Prevents Accidental Bluetooth Streaming**: Even if Bluetooth is connected, audio doesn't pass through without explicit user action
✓ **Clear User Intent**: User must actively select Bluetooth mode in app to enable streaming
✓ **Privacy Protection**: Audio doesn't leak to unexpected devices
✓ **Predictable Behavior**: Users know exactly when audio routes to Bluetooth
✓ **Fallback Safety**: If application crashes, audio remains on safe device

## Future Enhancements

- [ ] Add UI option to view current default audio device
- [ ] Allow user to select which device to use as "default"
- [ ] Add option to allow automatic Bluetooth passthrough (if desired)
- [ ] Support for ALSA on systems without PulseAudio
- [ ] Enhanced Windows support using native APIs
