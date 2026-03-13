"""Warp-tunnel effect renderer.

Draws a multi-layered radial warp-tunnel overlay with corkscrew spiral rays
through an aurora/nebula palette.  Speed, twist, and color react to energy,
bass, beats, and drops.  Only rendered when energy exceeds a modest threshold
(0.18) to avoid visual clutter during quiet passages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState


class WarpTunnelRenderer:
    """Renders a radial warp-tunnel effect as an additive overlay."""

    # Lower threshold so the tunnel activates more often.
    _THRESHOLD = 0.18

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx
        self._program = rctx.create_program("fullscreen_quad.vert", "warp_tunnel.frag")

    # ------------------------------------------------------------------
    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Draw the warp tunnel if energy is above threshold.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state.
        time : float
            Elapsed time in seconds.
        """
        energy = float(audio_state.overall_energy)

        # Only render when there is enough energy to be visible.
        if energy <= self._THRESHOLD:
            return

        rctx = self._rctx
        prog = self._program

        rctx.set_additive_blending()

        # Speed scales with energy: ramps from gentle to aggressive.
        speed = 0.4 + (energy - self._THRESHOLD) / (1.0 - self._THRESHOLD) * 3.0

        bass = float(audio_state.bass_energy)
        beat = float(audio_state.beat_intensity)
        drop = float(audio_state.drop_intensity)

        su = rctx.set_uniform
        su(prog, "u_time", time)
        su(prog, "u_resolution", (float(rctx.width), float(rctx.height)))
        su(prog, "u_energy", energy)
        su(prog, "u_speed", speed)
        su(prog, "u_bass_energy", bass)
        su(prog, "u_beat_intensity", beat)
        su(prog, "u_drop_intensity", drop)

        rctx.render_fullscreen_quad(prog)
