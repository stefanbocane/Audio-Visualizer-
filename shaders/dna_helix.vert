#version 410

#define PI  3.14159265358979323846
#define TAU 6.28318530717958647692

uniform vec2  u_resolution;
uniform float u_time;
uniform float u_twist_rate;
uniform float u_helix_radius;
uniform float u_perspective_z;
uniform float u_energy;
uniform float u_bass_energy;
uniform float u_beat_intensity;
uniform float u_reaction_scale;

in vec3 in_position;  // x = sample index [0,1], y = amplitude, z = strand_id (0, 1, or 2+lerp for rungs)

out float v_depth;        // 0 = far back, 1 = front
out float v_amplitude;
out float v_strand_id;    // 0.0 or 1.0 for strands, 2.0+ for rungs
out float v_glow_size;    // hint to fragment shader for glow radius
out float v_energy;       // energy passthrough for color modulation
out float v_beat;         // beat passthrough for rung pulsing
out float v_helix_phase;  // phase along helix for color shimmer

void main() {
    float sample_t  = in_position.x;
    float amplitude = in_position.y;
    float raw_id    = in_position.z;

    // Determine if this is a rung vertex (strand_id >= 2.0).
    bool is_rung = (raw_id >= 1.5);

    // For rungs, extract the lerp factor (fractional part above 2.0).
    float rung_lerp = is_rung ? fract(raw_id) : 0.0;

    // Pass raw_id through as strand_id for fragment shader classification.
    float strand_id = raw_id;

    // --- Helix geometry ---

    // Scroll speed increases with energy; base gentle drift + energy boost.
    float scroll_speed = 1.5 + u_energy * 4.0 + u_bass_energy * 2.0;
    float time_offset = u_time * scroll_speed;

    // Base helix angle from sample position and twist rate.
    float base_angle = sample_t * u_twist_rate * TAU + time_offset;

    // Compute positions for strand 0 and strand 1.
    float angle_s0 = base_angle;
    float angle_s1 = base_angle + PI;

    float radius = u_helix_radius;

    // Amplitude creates visible bulges along the strand -- scale radius.
    float amp_abs = abs(amplitude);
    float bulge = 1.0 + amp_abs * 1.8 * u_reaction_scale;

    // Strand 0 position in helix space.
    float y_s0 = sin(angle_s0) * radius * bulge;
    float z_s0 = cos(angle_s0) * radius * bulge;

    // Strand 1 position in helix space.
    float y_s1 = sin(angle_s1) * radius * bulge;
    float z_s1 = cos(angle_s1) * radius * bulge;

    // Screen X: sample index mapped to [-0.85, 0.85].
    float x_pos = mix(-0.85, 0.85, sample_t);

    float y_pos, z_pos;

    if (is_rung) {
        // Rungs interpolate between strand 0 and strand 1 positions.
        y_pos = mix(y_s0, y_s1, rung_lerp);
        z_pos = mix(z_s0, z_s1, rung_lerp);
        // Add a slight wave to rungs so they're not flat lines.
        y_pos += sin(rung_lerp * PI) * 0.015 * (1.0 + u_beat_intensity * 2.0);
    } else {
        // Pick the correct strand.
        y_pos = (raw_id < 0.5) ? y_s0 : y_s1;
        z_pos = (raw_id < 0.5) ? z_s0 : z_s1;
        // Amplitude pushes strand vertically (waveform modulation).
        y_pos += amplitude * 0.25 * u_reaction_scale;
    }

    // --- Perspective projection ---
    // Stronger perspective for real 3D feel.
    float perspective = 1.0 / (1.0 + z_pos * u_perspective_z);
    x_pos *= perspective;
    y_pos *= perspective;

    // Correct for aspect ratio.
    float aspect = u_resolution.x / u_resolution.y;
    x_pos /= aspect;

    gl_Position = vec4(x_pos, y_pos, 0.0, 1.0);

    // --- Point size ---
    // Base size varies with depth for 3D ribbon feel.
    float depth_norm = z_pos * 0.5 / (radius + 0.001) + 0.5; // [0,1], 1 = front
    depth_norm = clamp(depth_norm, 0.0, 1.0);

    float base_size;
    if (is_rung) {
        // Rungs: smaller points that pulse with beat.
        base_size = mix(2.0, 5.0, depth_norm);
        base_size *= (0.6 + u_beat_intensity * 1.5);
        // Fade rungs at the endpoints to avoid hard edges.
        float rung_edge = sin(rung_lerp * PI);
        base_size *= max(rung_edge, 0.2);
    } else {
        // Strand points: large soft points that overlap for a ribbon.
        // Scale range: 6 (back) to 18 (front), boosted by energy.
        base_size = mix(6.0, 18.0, depth_norm);
        base_size *= (0.8 + u_energy * 0.6 + amp_abs * 0.8);
    }

    // Resolution scaling -- larger screens get proportionally bigger points.
    float res_scale = u_resolution.y / 1080.0;
    gl_PointSize = base_size * res_scale;

    // --- Varyings ---
    v_depth       = depth_norm;
    v_amplitude   = amplitude;
    v_strand_id   = strand_id;
    v_glow_size   = is_rung ? 0.4 : 0.7;
    v_energy      = u_energy;
    v_beat        = u_beat_intensity;
    v_helix_phase = fract(base_angle / TAU);
}
