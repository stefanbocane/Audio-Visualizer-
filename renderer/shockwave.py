"""Shockwave ring effect renderer.

Produces an expanding ring of light triggered by beat drops.
The ring expands over approximately 0.67 seconds, fading with
exponential decay.  Only rendered when active.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState


class ShockwaveRenderer:
    """Renders a triggered expanding shockwave ring."""

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx
        self._program = rctx.create_program("fullscreen_quad.vert", "shockwave.frag")

        # State.
        self._active: bool = False
        self._progress: float = 0.0
        self._intensity: float = 0.0

    # ------------------------------------------------------------------
    # Trigger / update
    # ------------------------------------------------------------------

    def trigger(self) -> None:
        """Start a new shockwave expansion."""
        self._active = True
        self._progress = 0.0
        self._intensity = 1.0

    def update(self, dt: float) -> None:
        """Advance the shockwave animation.

        Parameters
        ----------
        dt : float
            Delta time in seconds since last update.
        """
        if not self._active:
            return

        self._progress += dt * 1.5  # Full expansion in ~0.67 s.
        self._intensity *= math.exp(-3.0 * dt)

        if self._progress >= 1.0:
            self._active = False
            self._progress = 0.0
            self._intensity = 0.0

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    @property
    def active(self) -> bool:
        """Whether a shockwave is currently animating."""
        return self._active

    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Draw the shockwave if active.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state (unused directly, but
            kept for interface consistency).
        time : float
            Elapsed time in seconds.
        """
        if not self._active:
            return

        rctx = self._rctx
        prog = self._program

        rctx.set_additive_blending()

        su = rctx.set_uniform
        su(prog, "u_resolution", (float(rctx.width), float(rctx.height)))
        su(prog, "u_shockwave_progress", self._progress)
        su(prog, "u_shockwave_intensity", self._intensity)

        rctx.render_fullscreen_quad(prog)
