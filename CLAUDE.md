# AudioVisual — Real-Time Music Visualizer

## What This Is
A GPU-accelerated real-time music visualizer built with Python, ModernGL, and pygame. Captures system audio and renders an Aurora Borealis-themed visual experience that reacts to music. Think planetarium laser show crossed with a rave.

## How to Run
```
python3 main.py
```
A launch menu lets you pick resolution (720p, 1080p, fullscreen). Press Q or Esc to quit during visualization. Press F to toggle fullscreen.

## Audio Setup (macOS)
- Uses **BlackHole 2ch** as a virtual audio loopback device to capture system audio digitally.
- If BlackHole is not found, falls back to the **default microphone** (picks up audio from speakers, lower quality).
- BlackHole is installed via `brew install blackhole-2ch` but **requires macOS to approve the system extension** in System Settings > Privacy & Security. A **restart is required** after approval.
- After restart, open **Audio MIDI Setup**, create a **Multi-Output Device** combining your speakers + BlackHole 2ch, and set it as system output. This sends audio to both your speakers and the visualizer.

## Known Gotchas

### ModernGL Uniform Arrays
ModernGL does NOT support bracket notation for array uniforms (e.g. `prog["u_bar_data[0]"]` will KeyError). You must set the entire array at once: `prog["u_bar_data"].value = tuple(...)`.

### GLSL Compiler Optimizes Away Unused Uniforms
If a uniform is declared in a shader but never used in the shader body, the GLSL compiler strips it out. Accessing it from Python via `prog["u_name"]` will KeyError. Always use `RenderContext.set_uniform()` which silently skips missing uniforms.

### Shader Attribute Binding Failures
Same as above but for vertex attributes — if an `in` attribute is declared in a .vert shader but never referenced in `main()`, the compiler removes it. Creating a VAO that tries to bind it will crash. Only declare attributes that are actually used.

### Renderer Signatures
All visual element renderers follow the signature `render(self, audio_state, time)` — two args after self. The pipeline calls them this way. The particles renderer has a separate `update(audio_state, dt)` called before render. The shockwave renderer has its own `trigger()` / `update(dt)` / `active` API managed by the pipeline.

### Demo Mode
When no audio device is available at all, the app runs in demo mode with synthetic sine-wave-based data so visuals still animate. This is handled in main.py's game loop.

### OpenGL Version
Targets OpenGL 4.1 (macOS maximum). No compute shaders available — particle physics runs on CPU with numpy vectorization instead.

## Tech Stack
- **moderngl** — OpenGL context, shaders, FBOs, VAOs
- **pygame** — window management, event loop, HUD text rendering
- **sounddevice** — audio capture from system devices
- **numpy** — FFT analysis, particle physics, array smoothing
