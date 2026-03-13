"""Central energy orb renderer.

Draws a glowing orb at the centre of the screen whose colour shifts
through the aurora palette in response to bass energy and beat intensity.
Rendered with additive blending on top of the background.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState


# Aurora palette key colours (RGB, 0-1).
_TEAL = (0.0, 0.55, 0.55)
_EMERALD = (0.05, 0.75, 0.40)
_VIOLET = (0.50, 0.18, 0.82)
_ICE_BLUE = (0.40, 0.80, 0.95)

# Beat ripple decay speed (higher = faster ring expansion & fade)
_RIPPLE_DECAY_SPEED = 4.0
# Minimum beat_intensity to trigger a new ripple
_RIPPLE_TRIGGER_THRESHOLD = 0.35


def _lerp3(a: tuple, b: tuple, t: float) -> tuple:
    """Linearly interpolate two RGB tuples."""
    t = max(0.0, min(1.0, t))
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


class OrbRenderer:
    """Renders the central pulsing energy orb."""

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx
        self._program = rctx.create_program("fullscreen_quad.vert", "orb.frag")

        # Beat ripple state: 1.0 at trigger, decays toward 0.
        self._beat_ripple = 0.0
        self._prev_beat_intensity = 0.0
        self._last_time = 0.0

    # ------------------------------------------------------------------
    def _compute_orb_color(self, audio_state: SmoothedAudioState) -> tuple:
        """Map bass energy and beat intensity to an aurora colour.

        Transition logic:
        - Low bass:              teal
        - Medium bass:           emerald
        - High bass + beat:      violet
        - Peak:                  ice_blue
        """
        bass = float(audio_state.bass_energy)
        beat = float(audio_state.beat_intensity)

        # Energy-based base colour.
        if bass < 0.3:
            base = _lerp3(_TEAL, _EMERALD, bass / 0.3)
        elif bass < 0.7:
            base = _lerp3(_EMERALD, _VIOLET, (bass - 0.3) / 0.4)
        else:
            base = _lerp3(_VIOLET, _ICE_BLUE, (bass - 0.7) / 0.3)

        # Beat pushes toward violet / ice_blue.
        if beat > 0.5:
            beat_t = (beat - 0.5) / 0.5
            if bass < 0.5:
                base = _lerp3(base, _VIOLET, beat_t * 0.7)
            else:
                base = _lerp3(base, _ICE_BLUE, beat_t * 0.7)

        # Clamp individual channels to avoid feeding >0.9 into the shader
        return (
            min(base[0], 0.85),
            min(base[1], 0.85),
            min(base[2], 0.85),
        )

    # ------------------------------------------------------------------
    def _update_beat_ripple(self, audio_state: SmoothedAudioState, dt: float) -> None:
        """Manage the beat ripple ring lifecycle.

        On a beat onset (rising edge above threshold), reset ripple to 1.0.
        Then let it decay exponentially toward 0.
        """
        beat = float(audio_state.beat_intensity)

        # Detect rising edge: current beat is above threshold and
        # exceeds previous by a meaningful amount (onset, not sustain).
        if beat > _RIPPLE_TRIGGER_THRESHOLD and beat > self._prev_beat_intensity + 0.1:
            self._beat_ripple = 1.0

        self._prev_beat_intensity = beat

        # Exponential decay
        if self._beat_ripple > 0.0:
            self._beat_ripple *= math.exp(-_RIPPLE_DECAY_SPEED * dt)
            if self._beat_ripple < 0.005:
                self._beat_ripple = 0.0

    # ------------------------------------------------------------------
    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Draw the orb with additive blending.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state.
        time : float
            Elapsed time in seconds.
        """
        rctx = self._rctx
        prog = self._program

        # Compute dt from elapsed time
        dt = time - self._last_time if self._last_time > 0.0 else 1.0 / 60.0
        dt = max(dt, 1e-4)  # safety clamp
        self._last_time = time

        # Update ripple state
        self._update_beat_ripple(audio_state, dt)

        rctx.set_additive_blending()

        color = self._compute_orb_color(audio_state)

        su = rctx.set_uniform
        su(prog, "u_resolution", (float(rctx.width), float(rctx.height)))
        su(prog, "u_bass_energy", float(audio_state.bass_energy))
        su(prog, "u_beat_intensity", float(audio_state.beat_intensity))
        su(prog, "u_overall_energy", float(audio_state.overall_energy))
        su(prog, "u_time", time)
        su(prog, "u_color", color)
        su(prog, "u_beat_ripple", float(self._beat_ripple))

        rctx.render_fullscreen_quad(prog)
