"""HUD (heads-up display) renderer (stretch goal).

Uses pygame.font to render BPM and FPS text as a texture, then draws
it as a textured quad in the top-left corner.  The texture is only
regenerated every ~0.5 seconds to avoid per-frame font rendering costs.
"""

from __future__ import annotations

import struct
import time as _time
from typing import TYPE_CHECKING

import moderngl
import numpy as np

try:
    import pygame
    import pygame.font

    _PYGAME_AVAILABLE = True
except ImportError:
    _PYGAME_AVAILABLE = False

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState

_UPDATE_INTERVAL = 0.5  # seconds between texture rebuilds
_FONT_SIZE = 20
_PADDING = 8
_TEXT_COLOR = (200, 230, 240)  # ice-blue tint (pygame RGBA)
_BG_COLOR = (5, 13, 20, 160)  # semi-transparent deep space


class HUDRenderer:
    """Renders BPM and FPS text as a textured quad overlay."""

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx

        if not _PYGAME_AVAILABLE:
            self._enabled = False
            return

        # Ensure pygame.font is initialised.
        if not pygame.font.get_init():
            pygame.font.init()

        self._enabled = True
        self._font = pygame.font.SysFont("monospace", _FONT_SIZE)

        # Shader program for textured quad.
        self._program = rctx.create_program("hud.vert", "hud.frag")

        # Texture (created on first update).
        self._texture: moderngl.Texture | None = None
        self._vbo: moderngl.Buffer | None = None
        self._vao: moderngl.VertexArray | None = None
        self._ibo: moderngl.Buffer | None = None

        # Timing for throttled updates.
        self._last_update: float = 0.0
        self._frame_count: int = 0
        self._fps: float = 0.0
        self._last_fps_time: float = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_texture(self, bpm: float, fps: float) -> None:
        """Render text to a pygame surface and upload as an OpenGL texture."""
        line1 = f"BPM: {int(round(bpm)):>3d}"
        line2 = f"FPS: {int(round(fps)):>3d}"

        surf1 = self._font.render(line1, True, _TEXT_COLOR)
        surf2 = self._font.render(line2, True, _TEXT_COLOR)

        w = max(surf1.get_width(), surf2.get_width()) + _PADDING * 2
        h = surf1.get_height() + surf2.get_height() + _PADDING * 3

        # Create RGBA surface.
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        surface.fill(_BG_COLOR)
        surface.blit(surf1, (_PADDING, _PADDING))
        surface.blit(surf2, (_PADDING, _PADDING * 2 + surf1.get_height()))

        # Convert to RGBA bytes (pygame stores as BGRA on some platforms,
        # so we use tobytes with explicit format via tostring / get_buffer).
        raw = pygame.image.tobytes(surface, "RGBA", True)

        ctx = self._rctx.ctx

        # Release old texture if size changed.
        if self._texture is not None:
            if self._texture.size != (w, h):
                self._texture.release()
                self._texture = None

        if self._texture is None:
            self._texture = ctx.texture((w, h), 4, data=raw)
            self._texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._rebuild_quad(w, h)
        else:
            self._texture.write(raw)

    def _rebuild_quad(self, tex_w: int, tex_h: int) -> None:
        """Build a small quad positioned in the top-left corner."""
        rctx = self._rctx
        ctx = rctx.ctx

        # Quad in NDC: top-left corner with pixel-accurate sizing.
        # NDC x: [-1, -1 + 2*tex_w/screen_w]
        # NDC y: [1 - 2*tex_h/screen_h, 1]
        x0 = -1.0
        x1 = -1.0 + 2.0 * tex_w / rctx.width
        y0 = 1.0 - 2.0 * tex_h / rctx.height
        y1 = 1.0

        #           px   py   u    v
        vertices = [
            x0, y0, 0.0, 0.0,  # bottom-left
            x1, y0, 1.0, 0.0,  # bottom-right
            x0, y1, 0.0, 1.0,  # top-left
            x1, y1, 1.0, 1.0,  # top-right
        ]
        indices = [0, 1, 2, 2, 1, 3]

        # Release old buffers.
        if self._vbo is not None:
            self._vbo.release()
        if self._ibo is not None:
            self._ibo.release()
        if self._vao is not None:
            self._vao.release()

        self._vbo = ctx.buffer(struct.pack(f"{len(vertices)}f", *vertices))
        self._ibo = ctx.buffer(struct.pack(f"{len(indices)}I", *indices))

        self._vao = ctx.vertex_array(
            self._program,
            [(self._vbo, "2f 2f", "in_position", "in_texcoord")],
            index_buffer=self._ibo,
            index_element_size=4,
        )

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Draw the HUD overlay.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state.
        time : float
            Elapsed time in seconds.
        """
        if not self._enabled:
            return

        # Track FPS.
        self._frame_count += 1
        now = _time.monotonic()
        fps_dt = now - self._last_fps_time
        if fps_dt >= _UPDATE_INTERVAL:
            self._fps = self._frame_count / fps_dt
            self._frame_count = 0
            self._last_fps_time = now

        # Throttle texture rebuilds.
        if now - self._last_update >= _UPDATE_INTERVAL:
            self._last_update = now
            self._rebuild_texture(float(audio_state.bpm), self._fps)

        if self._texture is None or self._vao is None:
            return

        rctx = self._rctx

        rctx.set_alpha_blending()

        self._texture.use(location=0)
        if "u_texture" in self._program:
            self._program["u_texture"].value = 0

        self._vao.render(moderngl.TRIANGLES)
