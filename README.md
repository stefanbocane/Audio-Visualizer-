# Aurora Visualizer

A GPU-accelerated real-time music visualizer that captures your system audio and renders a reactive Aurora Borealis-themed visual experience. Built with Python, ModernGL (OpenGL 4.1), and pygame.

Think planetarium laser show crossed with a rave — everything reacts to your music in real time.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue) ![macOS](https://img.shields.io/badge/platform-macOS-lightgrey) ![OpenGL 4.1](https://img.shields.io/badge/OpenGL-4.1-green)

---

## What It Looks Like

The visualizer renders multiple layered visual elements simultaneously, all reacting to different aspects of the audio:

- **Aurora Background** — 3-layer flowing aurora curtains using domain-warped fractal noise, with a twinkling starfield and cosmic dust. Colors shift from cool teals during quiet passages to intense violets during loud sections.
- **Central Orb** — A morphing energy sphere with noise-distorted edges and internal plasma swirl. Pulses outward on beats with colored ripple rings (never white flash).
- **Particle System** — 3,500 particles in four spiral arms with murmuration-like flocking behavior. Particles scatter on beats and explode outward on drops, colored through the aurora palette based on speed and distance.
- **DNA Double Helix** — Stereo waveform data rendered as two intertwined glowing ribbon strands (left/right channels) with 64 energy bridge rungs that pulse on beats. Twist rate accelerates with energy.
- **Frequency Bars** — 128 spectrum analyzer bars in a gentle arc with aurora color gradient (teal base to violet peaks), glowing edges, bright tip caps with trails, inter-bar glow bleed, and mirror reflections.
- **Warp Tunnel** — Corkscrew spiral rays in 3 parallax depth layers with nebula noise texture. Activates at moderate energy and dramatically accelerates on drops.
- **Shockwave Rings** — Expanding colored rings triggered by bass drops.
- **Lissajous Scope** — Small oscilloscope in the corner showing stereo phase correlation.

### Post-Processing

- Bloom with soft colored extraction (no white washout)
- Chromatic aberration that pulses with beats
- Teal/violet color grading (shadows to highlights)
- Film grain texture
- Motion blur feedback between frames
- Dramatic vignette that breathes with energy

---

## Requirements

- **macOS** (tested on macOS 13+) — requires OpenGL 4.1 (Metal-backed)
- **Python 3.10+**
- **BlackHole 2ch** — virtual audio loopback for digital audio capture (optional but recommended)

---

## Setup Guide

### Step 1: Install Python Dependencies

```bash
# Clone the repo
git clone https://github.com/stefanbocane/Audio-Visualizer-.git
cd Audio-Visualizer-

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

The dependencies are:
| Package | Purpose |
|---------|---------|
| `moderngl` | OpenGL 4.1 context, shaders, framebuffers |
| `pygame` | Window management, event loop, HUD text |
| `sounddevice` | Real-time audio capture from system devices |
| `numpy` | FFT analysis, particle physics, array math |

### Step 2: Install BlackHole (Recommended)

BlackHole is a free virtual audio driver that lets the visualizer capture your system audio digitally — no microphone needed, zero background noise, works with headphones.

```bash
brew install blackhole-2ch
```

After installing:

1. **Approve the system extension**: Go to **System Settings > Privacy & Security**, scroll down, and click **Allow** next to the BlackHole kernel extension message.
2. **Restart your Mac.** This is required for the audio driver to load.

### Step 3: Set Up Audio Routing

After restarting:

1. Open **Audio MIDI Setup** (press `Cmd+Space`, type "Audio MIDI Setup", hit Enter)
2. Click the **+** button in the bottom-left corner
3. Select **Create Multi-Output Device**
4. Check both:
   - **Your speakers/headphones** (e.g., "MacBook Air Speakers")
   - **BlackHole 2ch**
5. Make sure your speakers are listed **first** (this is the "Primary Device")
6. Right-click the new **Multi-Output Device** in the left sidebar
7. Select **"Use This Device For Sound Output"**

> **Note:** Multi-Output Devices disable the macOS volume keys. Control volume from within your music app (Spotify, Apple Music, etc.) instead.

### Without BlackHole

If you skip BlackHole, the visualizer falls back to your **default microphone** input. This works but:
- Audio quality is lower (picks up room noise)
- Doesn't work with headphones
- Quieter music may not register well

If no audio device is available at all, the app runs in **demo mode** with synthetic animated data.

---

## Running

```bash
python3 main.py
```

A launch menu appears where you can select resolution:
- **1280x720** (720p) — good for lower-end hardware
- **1920x1080** (1080p) — recommended
- **Fullscreen** — uses your native display resolution

Use arrow keys to select, Enter to launch.

### Controls

| Key | Action |
|-----|--------|
| `Q` / `Esc` | Quit |
| `F` | Toggle fullscreen |

### HUD

The top-left corner displays:
- **BPM** — detected beats per minute
- **FPS** — current frame rate

---

## Architecture

```
main.py                    Launch menu, game loop, audio→render bridge
audio/
  capture.py               Sounddevice stream, ring buffer, low-latency config
  analyzer.py              FFT analysis, 6-band decomposition, stereo width
  beat_detector.py         Beat/drop detection with adaptive thresholds
renderer/
  context.py               ModernGL context, FBOs, shader loading, blending
  pipeline.py              Orchestrates all renderers, bloom, composite
  bloom.py                 Bloom post-processing (extract + 2-pass Gaussian blur)
  background.py            Aurora curtain background renderer
  orb.py                   Central energy orb with beat ripple state machine
  particles.py             3500-particle spiral system with CPU physics
  dna_helix.py             Stereo waveform double helix with rungs
  frequency_bars.py        128-bar spectrum analyzer with reflections
  warp_tunnel.py           Radial warp tunnel overlay
  shockwave.py             Expanding ring effect on drops
  lissajous.py             Stereo phase scope
  hud.py                   BPM/FPS text overlay
shaders/
  *.vert / *.frag          GLSL 4.1 vertex and fragment shaders for each element
utils/
  math_utils.py            Exponential smoothing, easing, SmoothedAudioState
  color_palette.py         Aurora color definitions
```

### Render Pipeline (per frame)

1. **Audio capture** — 256-sample blocks at 44.1kHz with low-latency config (~6ms)
2. **FFT analysis** — 1024-sample window, 6 frequency bands, stereo waveforms
3. **Beat detection** — Adaptive threshold (1.3σ for beats, 2.2σ for drops)
4. **Smoothing** — Exponential smoothing on all audio metrics (responsive but fluid)
5. **Scene render** — All visual elements drawn into an offscreen FBO with additive blending
6. **Bloom** — Bright pixel extraction → 2-pass 13-tap Gaussian blur at half resolution
7. **Composite** — Scene + bloom + motion blur feedback + chromatic aberration + color grading + vignette + film grain
8. **HUD** — BPM/FPS overlay with alpha blending

### Audio Latency

The pipeline is tuned for ~25ms total latency from sound to visual response:
- Audio device buffer: ~6ms (256 frames)
- FFT window: 23ms (overlapping, not additive)
- Smoothing: 2 frames to reach 70% of target

---

## Performance Notes

- Targets **60fps** with vsync, caps at 120fps
- Particle physics runs on **CPU with NumPy vectorization** (macOS OpenGL 4.1 has no compute shaders)
- 3,500 particles with 6-position trails = 21,000 GL_POINTS per frame
- All shaders use **additive blending** for luminous layering
- Bloom runs at **half resolution** for performance
- Tested on M1/M2 MacBook Air at 1080p, steady 60fps

### If Performance is Low

- Use 720p instead of 1080p
- Close other GPU-intensive apps
- The particle count can be reduced in `renderer/particles.py` (`NUM_PARTICLES`)

---

## Troubleshooting

### "No audio device found" / Demo mode

- Make sure BlackHole is installed and the system extension was approved
- You must **restart** after approving the BlackHole extension
- Check that the Multi-Output Device is set as system output

### Volume keys don't work

This is a macOS limitation with Multi-Output Devices. Control volume from your music app instead (Spotify, Apple Music, browser, etc.).

### Shader compile error

- Requires OpenGL 4.1 (all modern Macs support this)
- If you see GLSL errors, check that no shader files are corrupted

### Choppy/laggy visuals

- Ensure you're running on the discrete GPU if available (Energy Saver settings)
- Lower the resolution via the launch menu
- Close Chrome/other GPU-heavy apps

---

## License

MIT

---

## Credits

Built with Claude Code by [stefanbocane](https://github.com/stefanbocane).
