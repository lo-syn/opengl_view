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
