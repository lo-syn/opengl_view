# opengl_viewer

An openFrameworks app that renders the `bin/data` shaders and receives shader
parameter updates over OSC.

## Dependencies

- openFrameworks 0.12.1 for Linux 64-bit, including its Linux build
  prerequisites.
- The `ofxOsc` addon installed at
  `$OF_ROOT/addons/ofxOsc` (the addon listed in `addons.make`).

Do not copy the openFrameworks SDK into this repository. Install it separately
and point `OF_ROOT` at its root directory.

On Windows, the VS Code build tasks use MSYS2 UCRT64. Install the
openFrameworks MSYS2 dependencies in that environment, including GLFW, and
build the openFrameworks core with the same toolchain.

## Build and run

From this project directory, set `OF_ROOT` to your openFrameworks installation:

```sh
export OF_ROOT="$HOME/of_v0.12.1_linux64_gcc6_release"
test -f "$OF_ROOT/libs/openFrameworks/ofMain.h"
test -f "$OF_ROOT/addons/ofxOsc/src/ofxOsc.h"
make Debug
make RunDebug
```

For a release build, use `make Release` and `make RunRelease`. The default
`OF_ROOT` is `../../../`, which works when this project is located under
`OF_ROOT/apps/myApps/opengl_viewer`. If you clone it elsewhere, set `OF_ROOT`
as above. `config.make` can also hold local build settings, but avoid committing
machine-specific absolute paths.

Keep the shader files in `bin/data`; they are runtime assets, not build output.

## Shader banks over OSC

The renderer listens on OSC port `8001`. Send `/shader_bank` with one string
containing a bank folder name, for example `MyBank`. The renderer reads
`bin/data/MyBank/manifest.json`; shader paths in that manifest are relative
to the bank folder:

```json
{
  "programs": {
    "waves": {
      "vertex": "default.vert",
      "fragment": "waves.frag",
      "defines": ["EXAMPLE 1"]
    }
  }
}
```

`defines` is optional. Send `/fb0`, `/fb1`, or `/fb2` to select a framebuffer
(the default is `/fb0`), then send `/shader` with the string `waves` to compile
and select that program for that framebuffer. Program names are case-sensitive.
Send `/shader` with `reset` to clear the selected framebuffer. Layers are
composited in order from fb0 to fb2, so opaque later layers cover earlier ones.
The `/u_x0`–`/u_x3` values are shared by all layers. The selected shader remains
visible when changing banks, or if a bank or shader fails to load; errors are
logged by the renderer.
Re-select a program to load changed shader files, or re-send `/shader_bank`
to reload a changed manifest.

The default bank is `ShaderPack1`. For compatibility with the existing assets,
`bin/data/manifest.json` can also define a bank if its `pack_name` matches the
requested bank name; its shader paths are relative to `bin/data`. The legacy
`blob` alias selects `Blob` when there is no `blob` entry, and `shader` loads
the built-in shader if the bank has no `shader` entry.

## Shader menu overlay

The openFrameworks app listens for shader selections over OSC on port `8001`.
It starts with a black screen. Send `/shader` with the string `Blob` to select
the `Blob` program from the shader-pack manifest; `blob` is also accepted for
compatibility with the Python menu. Run the menu to select between that program
and `shader.frag`:

```sh
make Debug
```

In one terminal, launch the renderer:

```sh
make RunDebug
```

In a second terminal, launch the menu:

```sh
sudo apt install libxcb-cursor0
pip install PyQt6 mido python-rtmidi
python3 shader_menu.py
```

The menu opens as a small always-on-top panel near the bottom-center of the
primary display. The renderer uses a
borderless window so this menu can stay visible above it. Press `Esc` to close it.
Activate a shader pack to show its shaders directly beneath it; activate it
again to collapse the list. Multiple shader packs can stay open at once.
Use the up/down arrow keys to navigate the shader names, then press `Enter` or
`Space` to activate one; clicking a name also works. The active choice is
marked `on` at the right. Activating the active shader again resets the
renderer, and `Reset` always resets it. The renderer keeps its currently loaded
shader if a new shader fails to load.

The menu also reads MIDI from input-list index `1` (the second input,
since indices start at zero). MIDI control changes `120`–`123` are sent
as normalized float values to `/u_x0`–`/u_x3`. To confirm the
input index on your machine, run:

```sh
python3 -c "import mido; print(*enumerate(mido.get_input_names()), sep='\n')"
```

Select the audio file in `settings.json` under `audio.file_path`, then cycle
`enable_audio_input` on the Settings page to `audio_file`. Audio output is
disabled by default; activate `enable_audio_output` to select an available
output device. Further activations cycle through the devices and then disable
output. The selected output plays the active audio file or Bluetooth input;
audio analysis continues when output is disabled. A device must already be
available to Qt, and must support 44.1 kHz stereo 16-bit PCM for Bluetooth
capture. Connection failures are shown in the status bar. The menu disconnects
its Bluetooth input when leaving that mode, but does not disconnect unrelated
Bluetooth devices at startup or shutdown.
On Linux, Bluetooth input mode moves the configured phone's stream to a
temporary private capture sink. The app forwards it only to the selected output
when `enable_audio_output` is enabled; with output disabled, it is still
analyzed for OSC but is not played. Bluetooth input mode unmutes the configured
phone stream while capturing it. While Bluetooth input mode is off, the
phone's direct playback stream is muted. The app restores its original route
and mute state when it exits.

The audio file path is relative to the project directory. The audio envelope
is added to the latest MIDI value on each of `/u_x0`–`/u_x3` and sent as a
normalized OSC float, capped at 1.0 (equivalent to MIDI 127). Stopping audio
removes its contribution; MIDI values remain at their last received levels.
MIDI CC `16`–`19` control the audio contribution for `/u_x0`–`/u_x3`
respectively: 0 mutes it and 127 applies it at full strength. Each channel
defaults to full strength until its gain control is received.

## Bluetooth audio latency

Bluetooth input uses `pacat` to capture the monitor of the temporary private
PipeWire/PulseAudio sink. The source configured in `settings.json` under
`audio.bluetooth.input.pulseaudio_input_device` identifies the phone whose
system playback stream is routed there. Capture requests 20 ms latency and a
10 ms processing interval; the audio server may choose different values. Audio
is processed as it arrives, and when the UI falls behind, only the newest
20 ms of queued PCM is analyzed. This favors responsiveness over preserving
every transient. Bluetooth uses a 5 ms attack and 60 ms release; file playback
keeps its existing envelope.

Bluetooth transport and the audio server can add latency before capture, and
renderer updates add further delay. Measure the complete path on the target
system; wired input or producing OSC at the audio source can avoid Bluetooth
transport delay.
