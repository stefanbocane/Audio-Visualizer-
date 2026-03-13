#!/usr/bin/env python3
"""
Real-Time Music Visualizer
GPU-accelerated audio visualizer with Aurora Borealis aesthetic.
Captures system audio via BlackHole, renders with ModernGL + pygame.
"""

import sys
import time
import pygame
import numpy as np

# Display size options for the launch menu
DISPLAY_MODES = [
    ("1280x720 (720p)", 1280, 720),
    ("1920x1080 (1080p)", 1920, 1080),
    ("Fullscreen", 0, 0),
]


def launch_menu():
    """Simple pygame launch menu for selecting resolution."""
    pygame.init()
    menu_w, menu_h = 500, 400
    screen = pygame.display.set_mode((menu_w, menu_h))
    pygame.display.set_caption("Music Visualizer — Launch")
    font_title = pygame.font.SysFont("Helvetica", 32, bold=True)
    font_option = pygame.font.SysFont("Helvetica", 22)
    font_hint = pygame.font.SysFont("Helvetica", 16)

    # Aurora-ish colors for the menu
    bg_color = (5, 15, 25)
    teal = (0, 180, 180)
    emerald = (0, 210, 120)
    highlight = (100, 220, 200)
    dim = (80, 120, 120)

    selected = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % len(DISPLAY_MODES)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(DISPLAY_MODES)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(0)

        screen.fill(bg_color)

        # Title
        title_surf = font_title.render("Aurora Visualizer", True, teal)
        screen.blit(title_surf, (menu_w // 2 - title_surf.get_width() // 2, 40))

        subtitle_surf = font_hint.render("Real-Time Music Visualizer", True, dim)
        screen.blit(subtitle_surf, (menu_w // 2 - subtitle_surf.get_width() // 2, 80))

        # Resolution options
        y_start = 140
        for i, (label, w, h) in enumerate(DISPLAY_MODES):
            color = highlight if i == selected else emerald
            prefix = "▸ " if i == selected else "  "
            text_surf = font_option.render(f"{prefix}{label}", True, color)
            screen.blit(text_surf, (100, y_start + i * 50))

        # Instructions
        hint1 = font_hint.render("↑↓  Select resolution    Enter  Launch", True, dim)
        hint2 = font_hint.render("Esc  Quit    Q  Quit during visualization", True, dim)
        screen.blit(hint1, (menu_w // 2 - hint1.get_width() // 2, 330))
        screen.blit(hint2, (menu_w // 2 - hint2.get_width() // 2, 355))

        pygame.display.flip()
        pygame.time.wait(30)

    pygame.quit()
    return DISPLAY_MODES[selected]


def init_pygame_gl(width, height, fullscreen):
    """Initialize pygame with OpenGL context for ModernGL."""
    pygame.init()
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 4)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 1)
    pygame.display.gl_set_attribute(
        pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE
    )
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, 1)

    flags = pygame.OPENGL | pygame.DOUBLEBUF
    if fullscreen:
        flags |= pygame.FULLSCREEN
        info = pygame.display.Info()
        width, height = info.current_w, info.current_h

    screen = pygame.display.set_mode((width, height), flags)
    pygame.display.set_caption("Aurora Visualizer")
    return screen, width, height


def main():
    # Launch menu
    label, width, height = launch_menu()
    fullscreen = width == 0 and height == 0

    # Init pygame + OpenGL
    screen, width, height = init_pygame_gl(width, height, fullscreen)

    # Import after pygame GL init so ModernGL can pick up the context
    from audio.capture import AudioCapture
    from audio.analyzer import AudioAnalyzer
    from audio.beat_detector import BeatDetector
    from renderer.context import RenderContext
    from renderer.pipeline import RenderPipeline
    from utils.math_utils import SmoothedAudioState

    # Setup render context and pipeline
    ctx = RenderContext(width, height)
    pipeline = RenderPipeline(ctx)

    # Setup audio
    try:
        audio_capture = AudioCapture()
        audio_capture.start()
        audio_active = True
        print(f"Audio capture started (device: {audio_capture.device_name})")
    except Exception as e:
        print(f"Warning: Could not start audio capture: {e}")
        print("Running in demo mode (no audio input)")
        audio_active = False

    analyzer = AudioAnalyzer()
    beat_detector = BeatDetector()
    audio_state = SmoothedAudioState()

    # Main loop
    clock = pygame.time.Clock()
    running = True
    prev_time = time.perf_counter()

    while running:
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()

        # Delta time
        now = time.perf_counter()
        dt = min(now - prev_time, 0.05)  # Cap at 50ms to avoid spiral
        prev_time = now

        # Audio processing
        if audio_active:
            try:
                audio_data = audio_capture.get_audio_data()
                if audio_data is not None:
                    analysis = analyzer.analyze(audio_data)
                    beat_event = beat_detector.update(analysis.bass_energy)

                    # Build raw data dict for SmoothedAudioState
                    beat_val = 0.0
                    drop_val = 0.0
                    if beat_event is not None:
                        if beat_event.is_beat:
                            beat_val = beat_event.intensity
                        if beat_event.is_drop:
                            drop_val = beat_event.intensity

                    raw = {
                        "bands": np.array([
                            analysis.bands["sub_bass"],
                            analysis.bands["bass"],
                            analysis.bands["low_mid"],
                            analysis.bands["mid"],
                            analysis.bands["high_mid"],
                            analysis.bands["treble"],
                        ]),
                        "bins": analysis.bins,
                        "overall_energy": analysis.overall_energy,
                        "bass_energy": analysis.bass_energy,
                        "left_waveform": analysis.left_waveform,
                        "right_waveform": analysis.right_waveform,
                        "stereo_width": analysis.stereo_width,
                        "beat_intensity": beat_val,
                        "drop_intensity": drop_val,
                        "bpm": beat_event.bpm if beat_event else audio_state.bpm,
                    }
                    audio_state.update(raw, dt)
            except Exception:
                pass  # Audio glitch, skip frame
        else:
            # Demo mode: generate synthetic audio data
            t = now
            raw = {
                "bands": np.array([
                    0.3 + 0.2 * np.sin(t * 2.0),
                    0.2 + 0.15 * np.sin(t * 3.0),
                    0.15 + 0.1 * np.sin(t * 4.0),
                    0.1 + 0.08 * np.sin(t * 5.0),
                    0.05 + 0.03 * np.sin(t * 7.0),
                    0.03 + 0.02 * np.sin(t * 11.0),
                ]),
                "bins": np.abs(np.sin(np.linspace(0, t * 3, 128) + t)) * 0.3,
                "overall_energy": 0.5 + 0.3 * np.sin(t * 1.5),
                "bass_energy": 0.3 + 0.2 * np.sin(t * 2.0),
                "left_waveform": np.sin(
                    np.linspace(0, 4 * np.pi, 512) + t * 5
                ) * 0.5,
                "right_waveform": np.sin(
                    np.linspace(0, 4 * np.pi, 512) + t * 5 + 0.5
                ) * 0.5,
                "stereo_width": 0.3 + 0.2 * np.sin(t * 0.5),
                "beat_intensity": max(0, np.sin(t * 8.0) - 0.9) * 10,
                "drop_intensity": max(0, np.sin(t * 2.0) - 0.95) * 20,
                "bpm": 120.0,
            }
            audio_state.update(raw, dt)

        # Render
        pipeline.render(audio_state, dt)

        # Swap buffers
        pygame.display.flip()
        clock.tick(120)  # Cap at 120fps, actual target ~60fps via vsync

    # Cleanup
    if audio_active:
        audio_capture.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
