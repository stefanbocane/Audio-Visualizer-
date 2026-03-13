"""Lissajous (XY oscilloscope) renderer (stretch goal).

Plots the left waveform against the right waveform as an XY scatter in
a small viewport region (bottom-right corner), giving a classic
oscilloscope Lissajous figure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import moderngl
import numpy as np

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState

_NUM_POINTS = 512
_VIEWPORT_SIZE = 200  # pixels (square)


class LissajousRenderer:
    """Renders a Lissajous XY display in a corner viewport."""

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx
        self._program = rctx.create_program("lissajous.vert", "lissajous.frag")

        ctx = rctx.ctx
        # VBO for 512 points: each is (left_sample, right_sample) = 2 floats.
        self._vbo = ctx.buffer(reserve=_NUM_POINTS * 2 * 4)
        self._vao = ctx.vertex_array(
            self._program,
            [(self._vbo, "2f", "in_position")],
        )

    # ------------------------------------------------------------------
    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Upload waveform XY data and draw in corner viewport.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state.
        time : float
            Elapsed time in seconds.
        """
        rctx = self._rctx
        ctx = rctx.ctx

        rctx.set_additive_blending()

        # Build XY pairs from left/right waveforms.
        left = audio_state.left_waveform[:_NUM_POINTS]
        right = audio_state.right_waveform[:_NUM_POINTS]

        xy_data = np.empty((_NUM_POINTS, 2), dtype=np.float32)
        xy_data[:, 0] = left
        xy_data[:, 1] = right

        self._vbo.write(xy_data.tobytes())

        # Save current viewport and set a small one in the bottom-right.
        vp_x = rctx.width - _VIEWPORT_SIZE - 10
        vp_y = 10  # bottom-right corner
        old_viewport = ctx.viewport
        ctx.viewport = (vp_x, vp_y, _VIEWPORT_SIZE, _VIEWPORT_SIZE)

        ctx.enable_only(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
        self._vao.render(moderngl.POINTS, vertices=_NUM_POINTS)

        # Restore viewport.
        ctx.viewport = old_viewport
