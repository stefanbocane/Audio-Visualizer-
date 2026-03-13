#version 410

uniform float u_energy;

in vec2  in_position;      // NDC (-1 to 1)
in float in_speed;         // Normalised speed [0, 1]
in float in_alpha;         // Trail alpha (speed-scaled for tails)
in float in_radius;        // Normalised distance from center [0, 1]
in float in_trail_factor;  // Speed-based trail stretch factor

out float v_speed;
out float v_alpha;
out float v_radius;

void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);

    // --- Point size ---
    // Bigger particles near center, smaller at edges.
    // Base size range: center = 7, edge = 2.
    float size_by_radius = mix(7.0, 2.5, clamp(in_radius, 0.0, 1.0));

    // Fast particles get a slight boost (energy streaks).
    float speed_boost = smoothstep(0.5, 1.0, in_speed) * 1.5;

    // Energy pulse: all particles breathe with the music.
    float energy_pulse = 1.0 + u_energy * 0.4;

    // Trail points (alpha < 1) are smaller than head points.
    float trail_shrink = mix(0.5, 1.0, clamp(in_alpha, 0.0, 1.0));

    // Fast-moving particles have larger trail dots (trail_factor > 1.0).
    // This creates a visible "stretching" effect during bursts and drops.
    float trail_scale = mix(1.0, clamp(in_trail_factor * 0.5, 0.8, 1.5), 1.0 - trail_shrink);

    gl_PointSize = (size_by_radius + speed_boost) * energy_pulse * trail_shrink * trail_scale;

    // Clamp to reasonable GPU range.
    gl_PointSize = clamp(gl_PointSize, 1.5, 12.0);

    v_speed  = in_speed;
    v_alpha  = in_alpha;
    v_radius = in_radius;
}
