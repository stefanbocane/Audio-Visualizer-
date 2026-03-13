#version 410

#define PI 3.14159265358979323846

in float v_intensity;
in float v_along_bar;
in float v_across_bar;
in float v_bar_id_norm;
in float v_is_reflection;
in float v_neighbor_avg;
in float v_tip_trail;
flat in int v_bar_id;

uniform float u_time;

out vec4 frag_color;

// --- Aurora color palette ---
vec3 aurora_teal()    { return vec3(0.05, 0.55, 0.60); }
vec3 aurora_emerald() { return vec3(0.08, 0.72, 0.45); }
vec3 aurora_violet()  { return vec3(0.50, 0.18, 0.75); }
vec3 aurora_magenta() { return vec3(0.65, 0.12, 0.55); }
vec3 aurora_ice()     { return vec3(0.25, 0.65, 0.80); }

// Simple hash for per-bar variation
float hash(float n) {
    return fract(sin(n * 127.1) * 43758.5453);
}

void main() {
    float t = v_along_bar;       // 0 = base, 1 = tip
    float across = v_across_bar; // 0 = left edge, 1 = right edge
    float intensity = v_intensity;
    float is_refl = v_is_reflection;

    // --- Aurora color gradient along bar height ---
    // Base: deep teal -> mid: emerald -> upper: violet -> peak: magenta tint
    vec3 col;
    if (t < 0.35) {
        // Base zone: teal to emerald
        float f = t / 0.35;
        col = mix(aurora_teal(), aurora_emerald(), f);
    } else if (t < 0.7) {
        // Mid zone: emerald to violet
        float f = (t - 0.35) / 0.35;
        col = mix(aurora_emerald(), aurora_violet(), f);
    } else {
        // Peak zone: violet with magenta bloom at very top
        float f = (t - 0.7) / 0.3;
        col = mix(aurora_violet(), aurora_magenta(), f * 0.6);
    }

    // Per-bar hue variation (subtle, keeps within aurora palette)
    float bar_var = hash(float(v_bar_id)) * 0.15;
    col = mix(col, aurora_ice(), bar_var * (1.0 - t));

    // Slow time-based color drift
    float drift = sin(u_time * 0.3 + v_bar_id_norm * PI * 2.0) * 0.08;
    col = mix(col, aurora_ice(), max(0.0, drift));

    // --- Soft glowing edges (horizontal) ---
    // Distance from bar center (0 at center, 1 at edges)
    float edge_dist = abs(across - 0.5) * 2.0;

    // Core: solid, then soft falloff at edges
    float core_width = 0.55;  // fraction of bar that is "solid"
    float edge_alpha;
    if (edge_dist < core_width) {
        edge_alpha = 1.0;
    } else {
        // Smooth Gaussian-like falloff beyond core
        float edge_t = (edge_dist - core_width) / (1.0 - core_width);
        edge_alpha = exp(-3.0 * edge_t * edge_t);
    }

    // Wider glow halo for high-intensity bars
    float glow_extend = intensity * 0.3;
    float halo_alpha = exp(-2.5 * edge_dist * edge_dist) * glow_extend;
    edge_alpha = max(edge_alpha, halo_alpha);

    // --- Soft vertical edges at base and tip ---
    float base_fade = smoothstep(0.0, 0.04, t);
    float tip_fade = smoothstep(1.0, 0.92, t);
    float vert_soft = base_fade * tip_fade;

    // --- Bright glowing tip cap ---
    // The tip cap is a concentrated bright region near the top of the bar
    float tip_zone = smoothstep(0.82, 0.96, t);
    float tip_brightness = tip_zone * intensity * 1.8;
    vec3 tip_color = mix(aurora_violet(), aurora_ice(), 0.4);
    col += tip_color * tip_brightness * 0.5;

    // --- Tip trail effect ---
    // If the bar was higher last frame, the region between current and previous
    // tip gets a fading ghost. We approximate this: if v_along_bar is near the
    // tip AND previous was higher, add a trail glow.
    float prev_height = v_tip_trail;
    if (prev_height > intensity) {
        // Normalized position within the "trail zone"
        // Current bar goes to intensity, trail extends to prev_height
        float trail_start = max(intensity - 0.05, 0.0);
        float trail_end = min(prev_height + 0.02, 1.0);
        // Map current t (which is 0..1 within actual bar geometry) to trail space
        // The actual position in "amplitude space" is t * intensity
        float amp_pos = t * intensity;
        if (amp_pos > trail_start && amp_pos < trail_end) {
            float trail_t = (amp_pos - trail_start) / max(trail_end - trail_start, 0.001);
            float trail_alpha = (1.0 - trail_t) * 0.4;
            col += tip_color * trail_alpha;
        }
    }

    // --- Inter-bar glow ---
    // When neighboring bars are high, light bleeds outward from bar edges
    float inter_glow = v_neighbor_avg * edge_dist * 0.35;
    vec3 glow_col = mix(aurora_emerald(), aurora_teal(), 0.5);
    col += glow_col * inter_glow * intensity;

    // --- Intensity-driven brightness ---
    // Moderate overall brightness (accent, not main show)
    float brightness = mix(0.20, 0.75, intensity);
    col *= brightness;

    // --- Assemble alpha ---
    float alpha = edge_alpha * vert_soft * mix(0.35, 0.90, intensity);

    // --- Reflection handling ---
    if (is_refl > 0.5) {
        // Fade reflection with distance from baseline (t = how far into reflection)
        float refl_fade = (1.0 - t) * 0.25;
        alpha *= refl_fade;
        // Dim and shift reflection slightly toward teal
        col = mix(col, aurora_teal(), 0.3);
        col *= 0.5;
    }

    // Clamp to avoid negative from any math
    col = max(col, vec3(0.0));

    // --- HDR output for bloom pass ---
    // Let very bright tips exceed 1.0 so bloom picks them up
    vec3 final_color = col * (1.0 + tip_brightness * 0.4);

    frag_color = vec4(final_color, alpha);
}
