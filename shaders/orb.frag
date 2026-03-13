#version 410

uniform vec2  u_resolution;
uniform float u_bass_energy;
uniform float u_beat_intensity;
uniform float u_overall_energy;
uniform float u_time;
uniform vec3  u_color;
uniform float u_beat_ripple;      // 0..1, decays after each beat hit

in vec2 v_uv;
out vec4 frag_color;

// ---------------------------------------------------------------
// Hash / noise utilities (no textures needed)
// ---------------------------------------------------------------
float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(41.1, 289.7))) * 43758.5453);
}

// Simplex-ish 2D gradient noise
float gnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);

    float a = hash21(i + vec2(0.0, 0.0));
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));

    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Fractal Brownian Motion — 4 octaves
float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    mat2 rot = mat2(0.8, 0.6, -0.6, 0.8);   // fixed rotation per octave
    for (int i = 0; i < 4; i++) {
        v += a * gnoise(p);
        p = rot * p * 2.0;
        a *= 0.5;
    }
    return v;
}

// Rotation helper
mat2 rot2(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

// ---------------------------------------------------------------
// Aurora palette — energy-driven colour ramp
// ---------------------------------------------------------------
vec3 aurora_palette(float t) {
    // 0 → deep teal, 0.33 → emerald, 0.66 → violet, 1.0 → ice blue
    vec3 teal     = vec3(0.0,  0.55, 0.55);
    vec3 emerald  = vec3(0.05, 0.75, 0.40);
    vec3 violet   = vec3(0.50, 0.18, 0.82);
    vec3 ice_blue = vec3(0.40, 0.80, 0.95);

    t = clamp(t, 0.0, 1.0);
    if (t < 0.333) return mix(teal, emerald,  t / 0.333);
    if (t < 0.666) return mix(emerald, violet, (t - 0.333) / 0.333);
    return mix(violet, ice_blue, (t - 0.666) / 0.334);
}

// ---------------------------------------------------------------
// Main
// ---------------------------------------------------------------
void main() {
    float aspect = u_resolution.x / u_resolution.y;
    vec2 center = vec2(0.5 * aspect, 0.5);
    vec2 p = vec2(v_uv.x * aspect, v_uv.y);
    vec2 d = p - center;
    float dist = length(d);
    float angle = atan(d.y, d.x);

    // ---- Orb radius (moderate: 0.05 → 0.11) -----------------
    float base_radius = mix(0.05, 0.09, u_bass_energy);
    // Beat adds a small kick, capped at 0.12
    float radius = min(base_radius + u_beat_intensity * 0.025, 0.12);

    // ---- Noise-based edge distortion (breathing / morphing) --
    float slow_t = u_time * 0.4;
    float edge_noise = fbm(vec2(angle * 2.0 + slow_t, dist * 8.0 + slow_t * 0.7));
    // Amplitude of distortion scales with energy so quiet = smooth sphere
    float distortion_amp = mix(0.006, 0.018, u_bass_energy);
    // Additional morph on beats
    distortion_amp += u_beat_intensity * 0.008;
    float morphed_radius = radius + (edge_noise - 0.5) * distortion_amp;

    // Signed distance
    float sdf = dist - morphed_radius;

    // ---- Internal plasma / nebula swirl ----------------------
    // Rotate UVs over time for swirl
    vec2 swirl_uv = rot2(u_time * 0.3 + u_bass_energy * 1.5) * d;
    swirl_uv += vec2(u_time * 0.15, u_time * -0.1);

    float plasma1 = fbm(swirl_uv * 12.0 + vec2(u_time * 0.2));
    float plasma2 = fbm(swirl_uv * 18.0 - vec2(u_time * 0.35, u_time * 0.15));
    float plasma = plasma1 * 0.6 + plasma2 * 0.4;

    // Map plasma to colour from aurora palette, shifted by energy
    float palette_t = plasma + u_bass_energy * 0.4 + u_overall_energy * 0.2;
    vec3 plasma_col = aurora_palette(palette_t);

    // ---- Core mask (inside the orb) --------------------------
    float core = smoothstep(0.003, -0.003, sdf);

    // ---- Inner glow (tight, falls off fast outside edge) -----
    float inner_glow = exp(-max(sdf, 0.0) * 28.0);

    // ---- Outer glow (wide, soft) -----------------------------
    float outer_glow = exp(-max(sdf, 0.0) * 6.0);

    // ---- Beat ripple ring ------------------------------------
    // u_beat_ripple goes 1→0 after beat; map to expanding ring
    float ripple_radius = morphed_radius + (1.0 - u_beat_ripple) * 0.08;
    float ripple_width = 0.008 + (1.0 - u_beat_ripple) * 0.006;
    float ripple_dist = abs(dist - ripple_radius);
    float ripple = smoothstep(ripple_width, 0.0, ripple_dist) * u_beat_ripple;

    // ---- Colour composition ----------------------------------
    // Base colour from Python (already aurora-mapped)
    vec3 base_col = u_color;

    // Internal swirl (only visible inside the core)
    vec3 internal = mix(base_col, plasma_col, 0.55);

    // Compose layers
    vec3 col = vec3(0.0);

    // Core: internal plasma-infused colour
    col += internal * core * 0.65;

    // Inner glow: coloured, not white
    vec3 inner_col = mix(base_col, plasma_col, 0.3);
    col += inner_col * inner_glow * 0.35;

    // Outer glow: shifted toward ice-teal
    vec3 glow_col = mix(base_col, vec3(0.3, 0.7, 0.75), 0.5);
    col += glow_col * outer_glow * 0.2;

    // Beat ripple: coloured ring, NOT white
    vec3 ripple_col = mix(base_col, aurora_palette(u_bass_energy + 0.3), 0.6);
    col += ripple_col * ripple * 0.55;

    // Breathing luminance variation (slow sine)
    float breathe = sin(u_time * 2.5) * 0.08 + 1.0;
    col *= breathe;

    // ---- Hard clamp — NEVER allow white blowout --------------
    col = min(col, vec3(0.85));

    // Alpha for additive blending
    float alpha = max(core, inner_glow * 0.8);
    alpha = max(alpha, outer_glow * 0.3);
    alpha = max(alpha, ripple * 0.6);

    frag_color = vec4(col, alpha);
}
