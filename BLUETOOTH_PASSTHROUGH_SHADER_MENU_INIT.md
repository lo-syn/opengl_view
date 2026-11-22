# Bluetooth Passthrough Prevention via Shader Menu Initialization

> Historical implementation notes. Current Linux routing uses a temporary
> private capture sink and app-controlled output; see the audio section in
> `README.md`. This document describes the earlier default-sink approach.

## Overview
Bluetooth audio passthrough prevention now occurs when the shader menu (application UI) is initialized, rather than when the Bluetooth backend is created. This provides better control and clearer application lifecycle management.

## Changes Made

### 1. shader_menu.py

#### Import Addition (Line 8)
```python
from bluetooth_audio import BluetoothAudioManager
```
Added import to access Bluetooth functionality from the main UI class.

#### Initialization Call (Lines 87-88)
```python
# Prevent automatic Bluetooth audio passthrough on startup
self._prevent_bluetooth_passthrough()
```
Called in `DefaultMenu.__init__()` during menu setup.

#### New Method (Lines 227-243)
```python
def _prevent_bluetooth_passthrough(self) -> None:
    """Prevent automatic Bluetooth audio passthrough on application startup."""
    try:
        manager = BluetoothAudioManager()
        manager.prevent_automatic_passthrough()
        logger.info("Bluetooth passthrough prevention initialized")
    except OSError:
        logger.debug("Bluetooth audio not available, passthrough prevention skipped")
    except Exception as e:
        logger.warning(f"Could not initialize Bluetooth passthrough prevention: {e}")
```

**Key Features:**
- Creates BluetoothAudioManager instance
- Calls public `prevent_automatic_passthrough()` method
- Gracefully handles systems without Bluetooth
- Non-blocking - application continues even if prevention fails
- Detailed logging at appropriate levels

### 2. bluetooth_audio.py

#### New Public Method (Lines 549-559)
```python
def prevent_automatic_passthrough(self) -> bool:
    """Prevent automatic Bluetooth audio passthrough by setting default to non-Bluetooth device.
    
    This should be called during application initialization to ensure audio doesn't
    automatically route to Bluetooth devices when they connect.
    
    Returns:
        True if successful or operation not needed, False if explicitly failed
    """
    if hasattr(self.backend, '_set_default_to_non_bluetooth'):
        return self.backend._set_default_to_non_bluetooth()
    return True  # Backend doesn't support this operation
```

**Key Features:**
- Public interface for triggering passthrough prevention
- Backend-agnostic (works with any backend implementation)
- Safe delegation to backend if method exists
- Returns status for caller to handle

#### Backend Changes
- **Removed** passthrough prevention calls from both backend `__init__` methods
- Backend methods `_set_default_to_non_bluetooth()` still exist and function normally
- Backends are now simpler with focused responsibility

## Application Startup Flow

```
Application Starts
│
├─→ Parse command line arguments
├─→ Setup logging
│
├─→ Create DefaultMenu (shader_menu.py)
│   │
│   ├─→ DefaultMenu.__init__() called
│   │   │
│   │   ├─→ Setup menu items and handlers
│   │   ├─→ Initialize OSC, MIDI, etc.
│   │   ├─→ Setup audio mode state (audio_mode = 0)
│   │   │
│   │   ├─→ _prevent_bluetooth_passthrough() called ← HERE
│   │   │   │
│   │   │   ├─→ BluetoothAudioManager created
│   │   │   │   └─→ Backend selected (Windows or Debian)
│   │   │   │
│   │   │   ├─→ prevent_automatic_passthrough() called
│   │   │   │   │
│   │   │   │   ├─→ [Debian] Calls Backend._set_default_to_non_bluetooth()
│   │   │   │   │   ├─→ Scans all PulseAudio sinks
│   │   │   │   │   ├─→ Filters out Bluetooth devices
│   │   │   │   │   ├─→ Sets default to speakers/headphones
│   │   │   │   │   └─→ ✓ Passthrough PREVENTED
│   │   │   │   │
│   │   │   │   └─→ [Windows] Calls Backend._set_default_to_non_bluetooth()
│   │   │   │       └─→ Checks if default is Bluetooth
│   │   │   │
│   │   │   ├─→ Exception handled gracefully
│   │   │   └─→ Application continues
│   │   │
│   │   ├─→ Setup UI (window, widgets, etc.)
│   │   └─→ Ready for user input
│   │
│   └─→ Menu displayed to user
│
└─→ Application runs and awaits user interaction
```

## User Experience Timeline

### Startup (What Happens)
1. Application starts
2. UI initializes (shader menu created)
3. Bluetooth passthrough prevented internally (user doesn't see this)
4. UI is displayed and ready
5. User can now interact with audio controls

### User Workflow
```
Step 1: User Connects Bluetooth Device (System Level)
  └─→ Device appears in system settings ✓
  └─→ Device shows in app's device list ✓
  └─→ Audio stays on built-in speakers ✓ (thanks to prevention)

Step 2: User Presses Audio Mode Button
  └─→ Audio mode cycles: disabled → bluetooth ✓

Step 3: User Selects Bluetooth Device
  └─→ App calls connect_bluetooth_device(device)
  └─→ App sets device as default via pactl
  └─→ Audio now flows to Bluetooth device ✓

Step 4: User Presses Audio Mode Button Again
  └─→ Audio mode cycles: bluetooth → audio_file ✓
  └─→ App resets default to speakers
  └─→ Audio flows to built-in speakers ✓

Step 5: User Presses Audio Mode Button Again
  └─→ Audio mode cycles: audio_file → disabled ✓
  └─→ All audio disabled
```

## Architecture Benefits

### Separation of Concerns
- **Backend Classes**: Handle Bluetooth connectivity and device-specific operations
- **BluetoothAudioManager**: Provides high-level Bluetooth management
- **DefaultMenu**: Application-level initialization and control

### Flexibility
- Can call `prevent_automatic_passthrough()` anytime if needed
- Not bound to backend initialization
- Easy to extend or modify behavior

### Error Handling
- Application doesn't depend on passthrough prevention succeeding
- Graceful degradation on systems without Bluetooth
- Detailed logging for debugging

### Cleaner Backends
- Backends focus on what they do well (device management)
- No side effects on creation
- Can be tested in isolation

## Logging Output

When application starts, you'll see:
```
INFO:  Debian/Linux Bluetooth backend initialized
INFO:  Set default audio output to: alsa_output.pci-0000_00_1b.0.analog-stereo
INFO:  Bluetooth passthrough prevention initialized
```

Or if Bluetooth isn't available:
```
DEBUG: Bluetooth audio not available, passthrough prevention skipped
```

Or if there's an issue:
```
WARNING: Could not initialize Bluetooth passthrough prevention: <error>
```

## Testing the Implementation

### Test 1: Verify Passthrough Prevention at Startup
```bash
# Start application and check logs
python app.py 2>&1 | grep -i "passthrough\|bluetooth"
```

### Test 2: Connect Bluetooth Device and Verify Audio Stays on Speakers
```bash
# 1. Start application
# 2. Connect Bluetooth device via system settings
# 3. Play audio from another application
# 4. Confirm audio comes from speakers, not Bluetooth
```

### Test 3: Enable Bluetooth Mode in App
```bash
# 1. Start application
# 2. Press audio mode button to enable Bluetooth mode
# 3. Select device from list
# 4. Confirm audio now flows to Bluetooth device
```

## Future Enhancements

- [ ] Add UI feedback showing which device is currently default
- [ ] Allow user to manually trigger passthrough prevention
- [ ] Add configuration option to disable prevention (if desired)
- [ ] Support for ALSA on systems without PulseAudio
- [ ] Enhanced Windows device management

## Summary

The Bluetooth audio passthrough prevention now:
- ✓ Runs at shader menu initialization
- ✓ Uses a clean public API
- ✓ Separates concerns properly
- ✓ Handles errors gracefully
- ✓ Provides detailed logging
- ✓ Doesn't block application startup
- ✓ Can be called multiple times if needed
