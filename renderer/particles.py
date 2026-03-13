"""Spiral-arm particle renderer with trails.

3 500 particles arranged in four spiral arms, simulated with vectorised
NumPy physics on the CPU.  Each particle keeps a trail of its last 6
positions, yielding 21 000 GL_POINTS rendered per frame.

Particles exhibit murmuration-like flocking behaviour, dramatic beat
scatter with outward spiral bursts, and full radial explosions on drops.
Colour is driven by speed and distance through an aurora palette (no white).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import moderngl
import numpy as np

if TYPE_CHECKING:
    from renderer.context import RenderContext
    from utils.math_utils import SmoothedAudioState

NUM_PARTICLES = 3500
TRAIL_LENGTH = 6
TOTAL_POINTS = NUM_PARTICLES * TRAIL_LENGTH
NUM_ARMS = 4

# Pre-computed base trail alpha values (newest -> oldest).
_TRAIL_ALPHAS = np.array([1.0, 0.72, 0.48, 0.28, 0.14, 0.06], dtype=np.float32)


class ParticleRenderer:
    """Spiral-arm particles with CPU physics and GPU point rendering."""

    def __init__(self, rctx: RenderContext) -> None:
        self._rctx = rctx
        self._program = rctx.create_program("particles.vert", "particles.frag")

        # Physics state (all float32 for GPU upload).
        self._positions = np.zeros((NUM_PARTICLES, 2), dtype=np.float32)
        self._velocities = np.zeros((NUM_PARTICLES, 2), dtype=np.float32)
        self._trails = np.zeros((NUM_PARTICLES, TRAIL_LENGTH, 2), dtype=np.float32)

        # Per-particle persistent properties.
        self._home_radii = np.zeros(NUM_PARTICLES, dtype=np.float32)
        self._arm_ids = np.zeros(NUM_PARTICLES, dtype=np.float32)
        # Phase offset per particle for organic variation in orbit.
        self._phase_offsets = np.random.uniform(0, 2 * math.pi, NUM_PARTICLES).astype(
            np.float32
        )
        # Higher damping = more fluid, less jerky motion.
        self._damping = np.random.uniform(0.975, 0.992, NUM_PARTICLES).astype(
            np.float32
        )

        # Accumulated spiral rotation (for visible spinning).
        self._spiral_rotation = 0.0

        self._init_spiral_arms()

        # GPU buffer: each point = (x, y, speed, alpha, radius, trail_factor) = 6 floats.
        ctx = rctx.ctx
        self._vbo = ctx.buffer(reserve=TOTAL_POINTS * 6 * 4)  # 6 floats * 4 bytes
        self._vao = ctx.vertex_array(
            self._program,
            [(self._vbo, "2f 1f 1f 1f 1f",
              "in_position", "in_speed", "in_alpha", "in_radius", "in_trail_factor")],
        )

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_spiral_arms(self) -> None:
        """Distribute particles across four spiral arms with organic scatter."""
        n = NUM_PARTICLES
        arm_ids = (np.arange(n, dtype=np.float32) % NUM_ARMS)
        self._arm_ids = arm_ids

        # Radii: more particles toward the center for density, tapering outward.
        radii = np.random.power(2.0, size=n).astype(np.float32) * 0.65 + 0.05
        self._home_radii = radii

        # Spiral angle: arm base + logarithmic twist + per-particle scatter.
        scatter = np.random.normal(0.0, 0.2, size=n).astype(np.float32)
        angles = arm_ids * (2.0 * math.pi / NUM_ARMS) + radii * 2.5 + scatter

        self._positions[:, 0] = np.cos(angles) * radii
        self._positions[:, 1] = np.sin(angles) * radii

        # Small initial tangential velocity.
        speed_mag = 0.04 + radii * 0.02
        self._velocities[:, 0] = -np.sin(angles) * speed_mag
        self._velocities[:, 1] = np.cos(angles) * speed_mag

        # Fill trail history with current position.
        for t in range(TRAIL_LENGTH):
            self._trails[:, t, :] = self._positions

    # ------------------------------------------------------------------
    # Physics update (fully vectorised)
    # ------------------------------------------------------------------

    def update(self, audio_state: SmoothedAudioState, dt: float) -> None:
        """Advance particle simulation by *dt* seconds."""
        if dt <= 0.0:
            return

        pos = self._positions
        vel = self._velocities

        energy = float(audio_state.overall_energy)
        bass = float(audio_state.bass_energy)
        beat = float(audio_state.beat_intensity)
        drop = float(audio_state.drop_intensity)
        reaction = float(audio_state.reaction_scale)

        # --- Compute polar coordinates ---
        angles = np.arctan2(pos[:, 1], pos[:, 0])
        radii = np.sqrt(pos[:, 0] ** 2 + pos[:, 1] ** 2)
        safe_radii = np.maximum(radii, 0.01)

        # --- Accumulate spiral rotation for visible spin ---
        spin_rate = 0.3 + energy * 1.8 + bass * 0.8
        self._spiral_rotation += spin_rate * dt

        # --- Target: spiral arm positions (rotating over time) ---
        arm_base_angle = self._arm_ids * (2.0 * math.pi / NUM_ARMS)
        target_angle = (
            arm_base_angle
            + self._home_radii * 2.5
            + self._spiral_rotation
            + self._phase_offsets * 0.15
        )
        target_r = self._home_radii

        target_x = np.cos(target_angle) * target_r
        target_y = np.sin(target_angle) * target_r

        # --- Spring force toward spiral target (murmuration cohesion) ---
        # Stronger spring when energy is low (particles hold formation);
        # weaker spring with high energy (particles break free).
        spring_strength = 0.6 - energy * 0.25
        spring_strength = max(spring_strength, 0.1)
        force_x = (target_x - pos[:, 0]) * spring_strength
        force_y = (target_y - pos[:, 1]) * spring_strength

        # --- Tangential orbital velocity (the visible spin) ---
        orbit_speed = 1.2 + energy * 3.5 + bass * 1.5
        tangent_x = -pos[:, 1] / safe_radii * orbit_speed
        tangent_y = pos[:, 0] / safe_radii * orbit_speed
        force_x += tangent_x * 0.25
        force_y += tangent_y * 0.25

        # --- Murmuration-like flow field (Perlin-ish via sine harmonics) ---
        # Creates organic swirling patterns across the field.
        t = self._spiral_rotation * 0.4
        flow_scale = 0.15 + energy * 0.2
        flow_x = (
            np.sin(pos[:, 1] * 3.0 + t * 1.3) * 0.5
            + np.sin(pos[:, 0] * 2.1 - t * 0.7) * 0.3
            + np.cos((pos[:, 0] + pos[:, 1]) * 1.7 + t) * 0.2
        ) * flow_scale
        flow_y = (
            np.cos(pos[:, 0] * 3.0 - t * 1.1) * 0.5
            + np.cos(pos[:, 1] * 2.3 + t * 0.9) * 0.3
            + np.sin((pos[:, 0] - pos[:, 1]) * 1.9 - t) * 0.2
        ) * flow_scale
        force_x += flow_x
        force_y += flow_y

        # --- Separation force (avoid clumping) ---
        # Approximate: push away from sector-averaged positions.
        # Divide the field into a coarse grid and compute repulsion.
        # This is O(N) rather than O(N^2) while giving a flock-like feel.
        grid_res = 8
        grid_counts = np.zeros((grid_res, grid_res), dtype=np.float32)
        grid_cx = np.zeros((grid_res, grid_res), dtype=np.float32)
        grid_cy = np.zeros((grid_res, grid_res), dtype=np.float32)

        # Map positions to grid cells.
        gx = np.clip(((pos[:, 0] + 1.0) * 0.5 * grid_res).astype(np.int32), 0, grid_res - 1)
        gy = np.clip(((pos[:, 1] + 1.0) * 0.5 * grid_res).astype(np.int32), 0, grid_res - 1)

        np.add.at(grid_counts, (gx, gy), 1.0)
        np.add.at(grid_cx, (gx, gy), pos[:, 0])
        np.add.at(grid_cy, (gx, gy), pos[:, 1])

        # Average position per cell.
        mask = grid_counts > 0
        grid_cx[mask] /= grid_counts[mask]
        grid_cy[mask] /= grid_counts[mask]

        # Per-particle repulsion from own cell center.
        cell_avg_x = grid_cx[gx, gy]
        cell_avg_y = grid_cy[gx, gy]
        cell_count = grid_counts[gx, gy]

        sep_dx = pos[:, 0] - cell_avg_x
        sep_dy = pos[:, 1] - cell_avg_y
        sep_dist = np.sqrt(sep_dx ** 2 + sep_dy ** 2) + 0.001
        sep_strength = 0.08 * np.minimum(cell_count / 30.0, 1.0)
        force_x += (sep_dx / sep_dist) * sep_strength
        force_y += (sep_dy / sep_dist) * sep_strength

        # --- Beat reaction: outward spiral burst (moderate) ---
        if beat > 0.05:
            scatter_mag = beat * 0.9 * reaction
            # Outward radial + tangential twist = spiral burst.
            radial_x = pos[:, 0] / safe_radii
            radial_y = pos[:, 1] / safe_radii
            twist_x = -pos[:, 1] / safe_radii
            twist_y = pos[:, 0] / safe_radii
            # Mix radial outward (0.6) with tangential twist (0.4).
            burst_x = radial_x * 0.6 + twist_x * 0.4
            burst_y = radial_y * 0.6 + twist_y * 0.4
            # Add randomness for scatter feel.
            scatter_angles = np.random.uniform(
                0, 2 * math.pi, NUM_PARTICLES
            ).astype(np.float32)
            rand_scatter = beat * 0.25 * reaction
            burst_x += np.cos(scatter_angles) * rand_scatter
            burst_y += np.sin(scatter_angles) * rand_scatter

            force_x += burst_x * scatter_mag
            force_y += burst_y * scatter_mag

        # --- Drop reaction: radial explosion (controlled) ---
        if drop > 0.05:
            explode_mag = drop * 1.5 * reaction
            # Strong outward push proportional to drop intensity.
            radial_x = pos[:, 0] / safe_radii
            radial_y = pos[:, 1] / safe_radii
            # Particles closer to center get pushed harder (inverse radius).
            push_scale = np.clip(1.0 / (radii + 0.1), 0.5, 4.0)
            force_x += radial_x * explode_mag * push_scale
            force_y += radial_y * explode_mag * push_scale

            # Moderate direct velocity injection.
            vel[:, 0] += radial_x * drop * 0.6 * reaction * dt * 60.0
            vel[:, 1] += radial_y * drop * 0.6 * reaction * dt * 60.0

        # --- Gentle radial containment (soft boundary, not hard clamp) ---
        too_far_factor = np.clip((radii - 0.8) * 2.0, 0.0, 1.0)
        force_x -= pos[:, 0] / safe_radii * too_far_factor * 0.5
        force_y -= pos[:, 1] / safe_radii * too_far_factor * 0.5

        # --- Apply forces ---
        vel[:, 0] += force_x * dt
        vel[:, 1] += force_y * dt

        # --- Per-particle damping (varied for organic feel) ---
        # Damping depends on energy: less damping when music is intense.
        damp_mod = 1.0 - energy * 0.01  # Slightly less damping with energy.
        effective_damp = self._damping * damp_mod
        vel[:, 0] *= effective_damp
        vel[:, 1] *= effective_damp

        # --- Update positions ---
        pos[:, 0] += vel[:, 0] * dt
        pos[:, 1] += vel[:, 1] * dt

        # --- Soft respawn for particles that escape too far ---
        dist_sq = pos[:, 0] ** 2 + pos[:, 1] ** 2
        too_far = dist_sq > 1.8 * 1.8
        if np.any(too_far):
            n_respawn = int(np.sum(too_far))
            new_r = np.random.uniform(0.05, 0.35, size=n_respawn).astype(np.float32)
            new_a = np.random.uniform(0, 2 * math.pi, size=n_respawn).astype(
                np.float32
            )
            pos[too_far, 0] = np.cos(new_a) * new_r
            pos[too_far, 1] = np.sin(new_a) * new_r
            vel[too_far] *= 0.1  # Don't fully zero -- keep slight momentum.
            # Reset home radii so they settle into a new spiral position.
            self._home_radii[too_far] = new_r

        # --- Shift trail history (newest at index 0) ---
        self._trails[:, 1:, :] = self._trails[:, :-1, :]
        self._trails[:, 0, :] = pos

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, audio_state: SmoothedAudioState, time: float) -> None:
        """Upload trail data and draw all points."""
        rctx = self._rctx
        prog = self._program

        rctx.set_additive_blending()

        # Compute per-particle speed.
        speeds = np.sqrt(
            self._velocities[:, 0] ** 2 + self._velocities[:, 1] ** 2
        )
        # Normalise speed to roughly [0, 1].
        max_speed = max(float(speeds.max()), 0.01)
        speeds_norm = np.clip(speeds / max_speed, 0.0, 1.0)

        # Compute per-particle radius (distance from center), normalised.
        radii = np.sqrt(
            self._positions[:, 0] ** 2 + self._positions[:, 1] ** 2
        )
        max_radius = max(float(radii.max()), 0.01)
        radii_norm = np.clip(radii / max_radius, 0.0, 1.0)

        # Trail factor: fast-moving particles get longer (more visible) trails.
        # Base trail_factor is 1.0; fast particles up to 2.5x trail visibility.
        trail_factor = 1.0 + speeds_norm * 1.5

        # Pre-allocate output array: (x, y, speed, alpha, radius, trail_factor).
        vbo_data = np.empty((TOTAL_POINTS, 6), dtype=np.float32)

        for t in range(TRAIL_LENGTH):
            start = t * NUM_PARTICLES
            end = start + NUM_PARTICLES
            vbo_data[start:end, 0] = self._trails[:, t, 0]  # x
            vbo_data[start:end, 1] = self._trails[:, t, 1]  # y
            vbo_data[start:end, 2] = speeds_norm             # speed
            # Alpha: base trail alpha scaled by trail_factor for fast particles.
            base_alpha = _TRAIL_ALPHAS[t]
            # For the head (t=0), alpha is always full.  For tails, scale by
            # trail_factor so fast particles have longer visible trails.
            if t == 0:
                vbo_data[start:end, 3] = base_alpha
            else:
                # Lerp between base_alpha and a boosted alpha based on speed.
                boosted = np.clip(base_alpha * trail_factor, 0.0, 1.0)
                vbo_data[start:end, 3] = boosted
            vbo_data[start:end, 4] = radii_norm              # radius
            vbo_data[start:end, 5] = trail_factor             # trail_factor

        self._vbo.write(vbo_data.tobytes())

        rctx.set_uniform(prog, "u_resolution", (float(rctx.width), float(rctx.height)))
        rctx.set_uniform(prog, "u_time", time)
        rctx.set_uniform(prog, "u_energy", float(audio_state.overall_energy))

        rctx.ctx.enable_only(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
        self._vao.render(moderngl.POINTS)
