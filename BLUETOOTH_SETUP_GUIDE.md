# Bluetooth Audio Setup Guide

## Problem Solved
The app now correctly captures Bluetooth audio from your S23 phone and sends OSC messages to control shader parameters.

## What Was Wrong
1. The app had no saved Bluetooth device configuration
2. When you selected Bluetooth mode, it would scan devices but fail to auto-connect
3. The pacat process would never start, so no audio was being captured

## What's Fixed Now
1. ✅ Created `bluetooth_config.json` with your S23 device info
2. ✅ Updated `settings.json` with correct PulseAudio device name
3. ✅ App now loads saved config and auto-connects on startup

## How It Works

### App Startup
1. User selects "Bluetooth" mode in the UI
2. App creates AudioHandler with `enable_bluetooth=True`
3. App calls `load_bluetooth_config()` → loads S23 from `bluetooth_config.json`
4. App routes the S23 playback stream to a temporary private audio sink
5. App calls `play()` → starts pacat on that sink's monitor

### Audio Processing
1. `pacat` records from `opengl_viewer_bluetooth_capture.monitor`
2. A Qt socket notifier reacts when PCM data is available
3. `_process_bluetooth_audio_chunk()` drains the pipe, keeping up to the newest 20 ms of PCM
4. Analyzes peak amplitude and updates the Bluetooth envelope
5. Sends OSC message via `_set_level()` to `/u_x0`, `/u_x1`, `/u_x2`, `/u_x3`
6. Audio is sent to an output device only when `enable_audio_output` is enabled

### App Shutdown
1. Timer stops
2. pacat process terminates
3. The phone stream's original route and mute state are restored

## Configuration Files

### settings.json
```json
{
  "audio": {
    "bluetooth": {
      "input": {
        "device_name": "Laurence's S23",
        "pulseaudio_input_device": "bluez_source.f8_5b_6e_c1_75_d8.a2dp_source"
      }
    }
  }
}
```

### bluetooth_config.json
```json
{
  "last_device": {
    "name": "Laurence's S23",
    "mac_address": "F8:5B:6E:C1:75:D8"
  }
}
```

## Testing

1. Connect S23 to computer via Bluetooth (using system settings)
2. Launch the app
3. Select "Bluetooth" mode
4. Play audio on your S23 phone
5. Enable `enable_audio_output` and select an output device to hear the audio
6. Disable `enable_audio_output` to confirm capture and OSC analysis continue
   without sending audio to speakers
7. Verify the shader responds to audio on OSC channels /u_x0, /u_x1, /u_x2, /u_x3

## If Still Not Working

### Check logs for specific error messages
- Look for lines starting with ❌
- These indicate exactly where the connection failed

### Verify PulseAudio device name
```bash
pactl -f json list sink-inputs
```

While phone audio is playing, the Bluetooth stream should show the configured
device address and `api.bluez5.profile` set to `a2dp-source`.

If different, update both:
- `settings.json` - `audio.bluetooth.input.pulseaudio_input_device`
- Re-run the device connection script

### Verify S23 is connected
```bash
bluetoothctl devices | grep -i s23
```

Should show: `Device F8:5B:6E:C1:75:D8 Laurence's S23`

## Technical Details

**Audio Format**
- 16-bit signed PCM (s16le)
- 44.1 kHz sample rate
- 2-channel stereo
- Read in 4096-byte chunks every 50ms

**Envelope Follower**
- Attack time: 0.01s (fast response to peaks)
- Release time: 0.15s (smooth fade-out)
- Scales to [0.0, 1.0] for OSC messages

**OSC Messages**
- Address: `/u_x0`, `/u_x1`, `/u_x2`, `/u_x3`
- Format: Float32 value [0.0, 1.0]
- Frequency: 20 times per second (50ms timer)
