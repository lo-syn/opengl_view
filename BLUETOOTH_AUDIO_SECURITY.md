# Bluetooth Audio Passthrough Security Implementation

## Overview
Bluetooth audio passthrough is **disabled by default** and only enabled when the audio mode is explicitly set to "bluetooth".

## Implementation Details

### Key Changes
1. **AudioHandler** (`audio_handler.py`):
   - Added `bluetooth_mode_enabled` flag to track if Bluetooth mode is active
   - Modified `play()` method to check `bluetooth_mode_enabled` before attempting Bluetooth passthrough
   - Requires both `bluetooth_mode_enabled = True` AND `use_bluetooth = True` for Bluetooth to be used

2. **ShaderMenu** (`shader_menu.py`):
   - Audio mode cycling: Disabled (0) → Bluetooth (1) → Audio File (2) → Disabled (0)
   - Mode 0 (Disabled): No audio handlers active
   - Mode 1 (Bluetooth): Creates AudioHandler with `enable_bluetooth=True`
   - Mode 2 (File): Creates AudioHandler with `enable_bluetooth=False`

### Security Architecture

```
Application Startup
│
├─→ audio_mode = 0 (disabled)
│   └─→ bluetooth_mode_enabled = False
│
User Toggles Audio Mode Button
│
├─→ If Mode 1 (Bluetooth):
│   ├─→ bluetooth_mode_enabled = True ✓
│   ├─→ Scans for devices
│   └─→ Waits for device selection
│
├─→ If Mode 2 (File):
│   ├─→ bluetooth_mode_enabled = False ✓
│   └─→ Uses file playback
│
└─→ If Mode 0 (Disabled):
    └─→ All audio disabled ✓

User Plays Audio
│
├─→ play() checks:
│   ├─→ if bluetooth_mode_enabled:  ← Mode must be Bluetooth
│   ├─→ if use_bluetooth:           ← Device must be connected
│   └─→ if bluetooth_manager:       ← Manager must exist
│
├─→ All conditions true:
│   └─→ Stream to Bluetooth device ✓
│
└─→ Any condition false:
    └─→ Fall back to default audio ✓
```

## Usage Scenarios

### Scenario 1: Default (Safe)
- Application starts
- Audio mode = 0 (Disabled)
- Bluetooth passthrough: **DISABLED ❌**
- Audio output: None

### Scenario 2: User Enables Bluetooth Mode
- User presses audio button
- Audio mode = 1 (Bluetooth)
- Bluetooth passthrough: **ENABLED ✓** (once device is connected)
- Audio output: Bluetooth device (or fallback to default)

### Scenario 3: User Switches to File Mode
- User presses audio button
- Audio mode = 2 (File)
- Bluetooth passthrough: **DISABLED ❌**
- Audio output: Default speaker/headphones

### Scenario 4: User Disables Audio
- User presses audio button
- Audio mode = 0 (Disabled)
- Bluetooth passthrough: **DISABLED ❌**
- Audio output: None

## Security Guarantees

✓ **Dual-Lock Protection**: Bluetooth requires both mode flag AND device connection  
✓ **Fallback Safety**: If Bluetooth fails, audio automatically uses default speaker  
✓ **Mode Isolation**: Each mode uses separate handler instance  
✓ **Explicit Control**: Bluetooth can only be used by explicitly selecting Bluetooth mode  
✓ **No Accidental Passthrough**: Even if device is connected, Bluetooth won't be used unless mode is Bluetooth  

## Code References

**AudioHandler.play()** - Lines 93-128  
- Checks `bluetooth_mode_enabled` before attempting Bluetooth
- Falls back to file playback if Bluetooth unavailable

**AudioHandler.__init__()** - Lines 30-62  
- Sets `bluetooth_mode_enabled` based on `enable_bluetooth` parameter
- Never enables Bluetooth passthrough by default

**ShaderMenu.set_audio_enabled()** - Lines 249-315  
- Mode 1: Creates AudioHandler with `enable_bluetooth=True`
- Mode 2: Creates AudioHandler with `enable_bluetooth=False` (implicit)
- Mode 0: Disables all audio

