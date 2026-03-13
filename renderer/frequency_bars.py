"""Aurora-pillar frequency-bar renderer.

Draws 128 bars arranged in a gentle arc along the bottom of the screen,
with soft glowing edges, aurora color gradients, bright tip caps with
trails, inter-bar glow, and a faded reflection below.  Uses instanced
rendering -- instances 0..127 are the main bars, 128..255 are reflections.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import moderngl
import numpy as np

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState

_NUM_BARS = 128


class FrequencyBarsRenderer:
    """Renders aurora-pillar frequency bars via instanced draw calls."""

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx
        self._program = rctx.create_program(
            "frequency_bars.vert", "frequency_bars.frag"
        )
        self._vao = self._create_geometry()

        # Previous-frame bar data for tip-trail effect.
        # Starts at zero so the first frame has no trails.
        self._prev_bars = np.zeros(_NUM_BARS, dtype=np.float32)

    # ------------------------------------------------------------------
    # Geometry setup
    # ------------------------------------------------------------------

    def _create_geometry(self) -> moderngl.VertexArray:
        """Build a unit quad (4 vertices) for instanced bar rendering.

        Vertex layout: ``in_position`` (vec2).

        The vertex shader uses ``gl_InstanceID`` to position each instance
        along the arc. Instances 0..127 = main bars, 128..255 = reflections.
        """
        ctx = self._rctx.ctx

        # Unit quad: x in [0, 1], y in [0, 1].
        # x controls width across the bar, y controls height along the bar.
        vertices = [
            0.0, 0.0,  # bottom-left
            1.0, 0.0,  # bottom-right
            0.0, 1.0,  # top-left
            1.0, 1.0,  # top-right
        ]
        indices = [0, 1, 2, 2, 1, 3]

        vbo = ctx.buffer(struct.pack(f"{len(vertices)}f", *vertices))
        ibo = ctx.buffer(struct.pack(f"{len(indices)}I", *indices))

        vao = ctx.vertex_array(
            self._program,
            [(vbo, "2f", "in_position")],
            index_buffer=ibo,
            index_element_size=4,
        )
        return vao

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Draw the frequency bars (main + reflection).

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state.
        time : float
            Elapsed time in seconds.
        """
        rctx = self._rctx
        prog = self._program
        su = rctx.set_uniform

        rctx.set_additive_blending()

        # Current bar data from the audio pipeline.
        bins = audio_state.bins
        bar_data = tuple(float(bins[i]) for i in range(_NUM_BARS))

        # Previous-frame bar data for tip trails.
        prev_data = tuple(float(self._prev_bars[i]) for i in range(_NUM_BARS))

        # Upload uniforms (set_uniform silently skips if GLSL optimized it away).
        su(prog, "u_bar_data", bar_data)
        su(prog, "u_bar_prev", prev_data)
        su(prog, "u_beat_ripple", float(audio_state.beat_intensity))
        su(prog, "u_bass_energy", float(audio_state.bass_energy))
        su(prog, "u_time", time)
        su(prog, "u_resolution", (float(rctx.width), float(rctx.height)))

        # Draw main bars (instances 0..127) + reflections (128..255).
        self._vao.render(moderngl.TRIANGLES, instances=_NUM_BARS * 2)

        # Store current frame's data as "previous" for next frame's tip trails.
        # Use a fast decay so trails are brief (not a hard copy).
        decay = 0.88  # per-frame multiplicative decay for trail persistence
        self._prev_bars = np.maximum(
            np.array(bar_data, dtype=np.float32),
            self._prev_bars * decay,
        )
