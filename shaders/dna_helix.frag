#version 410

#define PI 3.14159265358979323846

in float v_depth;
in float v_amplitude;
in float v_strand_id;
in float v_glow_size;
in float v_energy;
in float v_beat;
in float v_helix_phase;

out vec4 frag_color;

// --- Aurora palette ---
// Strand 0: teal / emerald family
vec3 aurora_teal(float phase, float energy) {
    vec3 deep_teal  = vec3(0.0,  0.55, 0.65);
    vec3 emerald    = vec3(0.05, 0.85, 0.45);
    vec3 cyan_glow  = vec3(0.1,  0.95, 0.80);
    // Phase shifts color along the strand; energy pushes toward brighter cyan.
    float t = clamp(phase + energy * 0.3, 0.0, 1.0);
    vec3 base = mix(deep_teal, emerald, t);
    // High energy adds cyan highlight.
    base = mix(base, cyan_glow, energy * 0.25);
    return base;
}

// Strand 1: violet / magenta family
vec3 aurora_violet(float phase, float energy) {
    vec3 deep_violet = vec3(0.45, 0.10, 0.75);
    vec3 magenta     = vec3(0.85, 0.15, 0.65);
    vec3 pink_glow   = vec3(0.95, 0.30, 0.80);
    float t = clamp(phase + energy * 0.3, 0.0, 1.0);
    vec3 base = mix(deep_violet, magenta, t);
    base = mix(base, pink_glow, energy * 0.25);
    return base;
}

// Rung color: blend between the two strand palettes.
vec3 aurora_rung(float lerp_factor, float phase, float energy) {
    vec3 c0 = aurora_teal(phase, energy);
    vec3 c1 = aurora_violet(phase, energy);
    return mix(c0, c1, lerp_factor);
}

void main() {
    // --- Soft circular glow falloff (no hard discard) ---
    vec2 coord = gl_PointCoord - vec2(0.5);
    float dist = length(coord);

    // Two-tier glow: bright core + soft outer halo.
    float core_radius = 0.18;
    float glow_radius = v_glow_size;
    // Gaussian-ish falloff for ribbon feel.
    float core  = exp(-dist * dist / (core_radius * core_radius * 2.0));
    float halo  = exp(-dist * dist / (glow_radius * glow_radius * 0.8));
    float shape = max(core * 0.8, halo * 0.45);

    // Discard only truly invisible fragments.
    if (shape < 0.005) {
        discard;
    }

    // --- Determine vertex type and color ---
    bool is_rung = (v_strand_id >= 1.5);
    float amp = clamp(abs(v_amplitude), 0.0, 1.0);

    vec3 col;

    if (is_rung) {
        // Rung: interpolated color between strands.
        float lerp_factor = fract(v_strand_id);
        col = aurora_rung(lerp_factor, v_helix_phase, v_energy);
        // Rungs pulse with beat: brighter on beat, dimmer otherwise.
        float rung_pulse = 0.3 + v_beat * 1.5;
        col *= rung_pulse;
        // Fade at rung endpoints for soft bridges.
        float edge_soft = sin(lerp_factor * PI);
        shape *= max(edge_soft, 0.15);
    } else if (v_strand_id < 0.5) {
        // Strand 0 (left channel): teal / emerald
        col = aurora_teal(v_helix_phase, v_energy);
        // Amplitude shifts toward brighter emerald.
        vec3 amp_boost = vec3(0.05, 0.9, 0.55);
        col = mix(col, amp_boost, amp * 0.4);
    } else {
        // Strand 1 (right channel): violet / magenta
        col = aurora_violet(v_helix_phase, v_energy);
        // Amplitude shifts toward brighter magenta.
        vec3 amp_boost = vec3(0.9, 0.2, 0.75);
        col = mix(col, amp_boost, amp * 0.4);
    }

    // --- Depth-based brightness and saturation ---
    // Front (depth=1) is bright and saturated; back (depth=0) is dimmer and slightly desaturated.
    float depth_brightness = mix(0.25, 1.3, v_depth);
    col *= depth_brightness;

    // Slight desaturation on far side for atmospheric perspective.
    float desat_amount = mix(0.15, 0.0, v_depth);
    float luma = dot(col, vec3(0.299, 0.587, 0.114));
    col = mix(col, vec3(luma), desat_amount);

    // --- Energy-driven color crossfade between strands ---
    // At very high energy, strand 0 picks up hints of violet and vice versa.
    if (!is_rung) {
        float crossfade = v_energy * 0.15;
        if (v_strand_id < 0.5) {
            vec3 hint = aurora_violet(v_helix_phase, v_energy) * depth_brightness;
            col = mix(col, hint, crossfade);
        } else {
            vec3 hint = aurora_teal(v_helix_phase, v_energy) * depth_brightness;
            col = mix(col, hint, crossfade);
        }
    }

    // --- Gentle HDR bloom for high amplitude (no white!) ---
    // Instead of adding white, push the existing color brighter (maintain hue).
    float bloom_factor = smoothstep(0.4, 1.0, amp) * 0.6 * v_energy;
    col *= (1.0 + bloom_factor);

    // --- Final alpha ---
    // Combine shape, depth, and a minimum floor so back-strands still visible.
    float alpha = shape * mix(0.35, 1.0, v_depth);

    // Premultiplied alpha output for additive blending.
    frag_color = vec4(col * alpha, alpha);
}
