"""DNA double-helix waveform renderer.

Renders the left and right audio channels as two intertwined helical
strands with energy-bridge rungs, using the dna_helix vertex/fragment
shaders.  Waveform amplitudes modulate vertical displacement along each
strand.  Rungs pulse with beat intensity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import moderngl
import numpy as np

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState

NUM_SAMPLES = 512
NUM_RUNGS = 64  # connecting bridges between strands


class DNAHelixRenderer:
    """Renders stereo waveform data as a double-helix of GL_POINTS."""

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx
        self._program = rctx.create_program("dna_helix.vert", "dna_helix.frag")

        # Vertex data: (sample_index_norm, amplitude, strand_id) = 3 floats.
        # Two strands x NUM_SAMPLES + rungs (each rung = multiple interpolated points).
        rung_points_per_rung = 8
        self._rung_points_per_rung = rung_points_per_rung
        total_strand_verts = 2 * NUM_SAMPLES
        total_rung_verts = NUM_RUNGS * rung_points_per_rung
        total_verts = total_strand_verts + total_rung_verts

        ctx = rctx.ctx
        self._vbo = ctx.buffer(reserve=total_verts * 3 * 4)  # 3 floats * 4 bytes
        self._vao = ctx.vertex_array(
            self._program,
            [(self._vbo, "3f", "in_position")],
        )
        self._total_strand_verts = total_strand_verts
        self._total_rung_verts = total_rung_verts
        self._total_verts = total_verts

    # ------------------------------------------------------------------
    # Data upload
    # ------------------------------------------------------------------

    def update(self, audio_state: SmoothedAudioState) -> None:
        """Downsample waveforms and upload vertex data.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state.
        """
        left = audio_state.left_waveform
        right = audio_state.right_waveform

        # Downsample 512 -> NUM_SAMPLES (already 512, so just copy).
        left_ds = left[:NUM_SAMPLES].copy()
        right_ds = right[:NUM_SAMPLES].copy()

        # Ensure exactly NUM_SAMPLES.
        if len(left_ds) < NUM_SAMPLES:
            left_ds = np.pad(left_ds, (0, NUM_SAMPLES - len(left_ds)))
        if len(right_ds) < NUM_SAMPLES:
            right_ds = np.pad(right_ds, (0, NUM_SAMPLES - len(right_ds)))

        # Normalised sample index [0, 1].
        t = np.linspace(0.0, 1.0, NUM_SAMPLES, dtype=np.float32)

        # Build vertex data: (t, amplitude, strand_id).
        verts = np.empty((self._total_verts, 3), dtype=np.float32)

        # Strand 0 (left channel) -- strand_id = 0.0
        verts[:NUM_SAMPLES, 0] = t
        verts[:NUM_SAMPLES, 1] = left_ds
        verts[:NUM_SAMPLES, 2] = 0.0

        # Strand 1 (right channel) -- strand_id = 1.0
        verts[NUM_SAMPLES:2 * NUM_SAMPLES, 0] = t
        verts[NUM_SAMPLES:2 * NUM_SAMPLES, 1] = right_ds
        verts[NUM_SAMPLES:2 * NUM_SAMPLES, 2] = 1.0

        # Rungs -- strand_id = 2.0 + fractional lerp factor [0..1]
        # Each rung sits at evenly spaced positions along the helix,
        # interpolated between strand 0 and strand 1.
        rung_t = np.linspace(0.0, 1.0, NUM_RUNGS, endpoint=False, dtype=np.float32)
        ppg = self._rung_points_per_rung
        lerp_factors = np.linspace(0.0, 1.0, ppg, dtype=np.float32)

        offset = 2 * NUM_SAMPLES
        for i in range(NUM_RUNGS):
            # Find the nearest sample index for amplitude lookup.
            idx = int(rung_t[i] * (NUM_SAMPLES - 1))
            avg_amp = (left_ds[idx] + right_ds[idx]) * 0.5

            for j in range(ppg):
                vidx = offset + i * ppg + j
                verts[vidx, 0] = rung_t[i]
                verts[vidx, 1] = avg_amp
                # Encode: strand_id >= 2.0 means rung; fractional part = lerp.
                verts[vidx, 2] = 2.0 + lerp_factors[j]

        self._vbo.write(verts.tobytes())

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Update waveform data and draw the helix.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Current smoothed audio analysis state.
        time : float
            Elapsed time in seconds.
        """
        self.update(audio_state)

        rctx = self._rctx
        prog = self._program

        rctx.set_additive_blending()

        energy = float(audio_state.overall_energy)
        bass = float(audio_state.bass_energy)
        beat = float(audio_state.beat_intensity)
        stereo = float(audio_state.stereo_width)
        reaction = float(audio_state.reaction_scale)

        su = rctx.set_uniform
        su(prog, "u_resolution", (float(rctx.width), float(rctx.height)))
        su(prog, "u_time", time)
        su(prog, "u_energy", energy)
        su(prog, "u_bass_energy", bass)
        su(prog, "u_beat_intensity", beat)
        su(prog, "u_reaction_scale", reaction)
        # Twist rate scales with energy: 4 (calm) to 24 (intense).
        su(prog, "u_twist_rate", 4.0 + energy * 20.0)
        # Helix radius scales with stereo width: 0.08 (mono) to 0.30 (full).
        su(prog, "u_helix_radius", 0.08 + stereo * 0.22)
        su(prog, "u_perspective_z", 0.5)

        rctx.ctx.enable_only(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
        self._vao.render(moderngl.POINTS, vertices=self._total_verts)
