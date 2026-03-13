"""Background renderer: animated aurora borealis backdrop.

Uses a fullscreen quad with a multi-layered domain-warped noise shader
that reacts to bass, mids, highs, overall energy, and beat intensity.
Rendered opaque (no blending) as the first layer each frame.
"""

from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState


class BackgroundRenderer:
    """Renders the animated aurora borealis background."""

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx
        self._program = rctx.create_program("fullscreen_quad.vert", "background.frag")

    # ------------------------------------------------------------------
    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Draw the full-screen aurora background.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state.
        time : float
            Elapsed time in seconds since the visualiser started.
        """
        rctx = self._rctx
        prog = self._program

        # No blending -- opaque background layer.
        rctx.set_no_blending()

        # Derive mid and high energy from the 6-band frequency array.
        # bands layout (6 bands): [sub-bass, bass, low-mid, mid, high-mid, high]
        bands = audio_state.bands
        mid_energy = float(np.mean(bands[2:4])) if len(bands) >= 4 else 0.0
        high_energy = float(np.mean(bands[4:6])) if len(bands) >= 6 else 0.0

        su = rctx.set_uniform
        su(prog, "u_time", time)
        su(prog, "u_resolution", (float(rctx.width), float(rctx.height)))
        su(prog, "u_bass_energy", float(audio_state.bass_energy))
        su(prog, "u_overall_energy", float(audio_state.overall_energy))
        su(prog, "u_mid_energy", mid_energy)
        su(prog, "u_high_energy", high_energy)
        su(prog, "u_beat_intensity", float(audio_state.beat_intensity))

        rctx.render_fullscreen_quad(prog)
