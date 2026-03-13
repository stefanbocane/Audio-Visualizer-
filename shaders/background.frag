#version 410

// ========================================================================
// Aurora Borealis background shader — a living, breathing northern lights
// experience that reacts to music. Layered noise curtains, flowing color
// palettes, starfield, and bass-driven motion.
// ========================================================================

uniform float u_time;
uniform vec2  u_resolution;
uniform float u_bass_energy;
uniform float u_overall_energy;
uniform float u_mid_energy;
uniform float u_high_energy;
uniform float u_beat_intensity;

in vec2 v_uv;
out vec4 frag_color;

// -----------------------------------------------------------------------
// Hash & noise primitives
// -----------------------------------------------------------------------

// Fast 2D hash for starfield
float hash21(vec2 p) {
    p = fract(p * vec2(233.34, 851.73));
    p += dot(p, p + 23.45);
    return fract(p.x * p.y);
}

// 2D value noise
float hash2D(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float valueNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f); // smoothstep

    float a = hash2D(i);
    float b = hash2D(i + vec2(1.0, 0.0));
    float c = hash2D(i + vec2(0.0, 1.0));
    float d = hash2D(i + vec2(1.0, 1.0));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// -----------------------------------------------------------------------
// Simplex noise (Ashima Arts / Ian McEwan)
// -----------------------------------------------------------------------

vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec3 permute(vec3 x) { return mod289(((x * 34.0) + 1.0) * x); }

float snoise(vec2 v) {
    const vec4 C = vec4(
        0.211324865405187,
        0.366025403784439,
       -0.577350269189626,
        0.024390243902439
    );
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v - i + dot(i, C.xx);
    vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 x1 = x0 - i1 + C.xx;
    vec2 x2 = x0 + C.zz;
    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
                             + i.x + vec3(0.0, i1.x, 1.0));
    vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x1, x1), dot(x2, x2)), 0.0);
    m = m * m;
    m = m * m;
    vec3 x  = 2.0 * fract(p * C.www) - 1.0;
    vec3 h  = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
    vec3 g;
    g.x = a0.x * x0.x + h.x * x0.y;
    g.y = a0.y * x1.x + h.y * x1.y;
    g.z = a0.z * x2.x + h.z * x2.y;
    return 130.0 * dot(m, g);
}

// -----------------------------------------------------------------------
// Fractional Brownian Motion (3 to 5 octaves depending on use)
// -----------------------------------------------------------------------

float fbm3(vec2 p) {
    float v = 0.0;
    float amp = 0.5;
    mat2 rot = mat2(0.8, -0.6, 0.6, 0.8); // rotation between octaves
    for (int i = 0; i < 3; i++) {
        v += amp * snoise(p);
        p = rot * p * 2.1;
        amp *= 0.5;
    }
    return v;
}

// -----------------------------------------------------------------------
// Domain-warped noise: the core "flowing curtain" generator.
// Feed the output of one noise into the coordinates of another.
// -----------------------------------------------------------------------

float warpedNoise(vec2 p, float t, float bassWarp) {
    // First warp layer — slow, large-scale distortion
    vec2 q = vec2(
        fbm3(p + vec2(0.0, t * 0.12)),
        fbm3(p + vec2(5.2, t * 0.08 + 1.3))
    );

    // Second warp layer — bass energy drives additional displacement
    vec2 r = vec2(
        fbm3(p + 4.0 * q + vec2(1.7, t * 0.15 + 9.2)),
        fbm3(p + 4.0 * q + vec2(8.3, t * 0.10 + 2.8))
    );

    // Bass makes the warp displacement larger, more chaotic
    float warpStrength = 3.5 + bassWarp * 4.0;
    return fbm3(p + warpStrength * r);
}

// -----------------------------------------------------------------------
// Aurora curtain layers
// -----------------------------------------------------------------------

float auroraCurtain(vec2 uv, float t, float layer, float bassEnergy) {
    // Vertical stretching — aurora curtains are tall and thin
    vec2 p = vec2(uv.x * 1.8, uv.y * 0.4);

    // Layer offset for parallax
    p += vec2(layer * 3.7, layer * 1.3);

    // Bass-driven horizontal sway
    float sway = sin(uv.y * 3.0 + t * 0.5 + layer * 2.0) * (0.15 + bassEnergy * 0.4);
    sway += sin(uv.y * 7.0 - t * 0.3 + layer) * (0.05 + bassEnergy * 0.15);
    p.x += sway;

    // Domain-warped noise for organic curtain shapes
    float n = warpedNoise(p, t + layer * 10.0, bassEnergy);

    // Remap to [0, 1] and shape the curtain profile
    n = n * 0.5 + 0.5;
    n = smoothstep(0.25, 0.85, n);

    // Vertical envelope: curtains live in the upper 2/3 of the screen,
    // with a soft fade at top and bottom
    float vEnvelope = smoothstep(0.0, 0.35, uv.y) * smoothstep(1.0, 0.55, uv.y);
    // Push the curtain center upward
    vEnvelope *= smoothstep(-0.1, 0.4, uv.y);

    n *= vEnvelope;

    return n;
}

// -----------------------------------------------------------------------
// Color palette — shifts based on audio energy
// -----------------------------------------------------------------------

vec3 auroraPalette(float t, float energy, float midEnergy, float highEnergy) {
    // Base palette anchors (deep teal -> emerald -> green -> violet -> magenta)
    vec3 deep_teal  = vec3(0.01, 0.18, 0.22);
    vec3 teal       = vec3(0.0,  0.55, 0.55);
    vec3 emerald    = vec3(0.0,  0.75, 0.35);
    vec3 green_glow = vec3(0.15, 1.0,  0.35);
    vec3 violet     = vec3(0.55, 0.15, 0.85);
    vec3 magenta    = vec3(0.95, 0.1,  0.65);
    vec3 hot_pink   = vec3(1.0,  0.2,  0.5);

    // Audio-driven palette cycling:
    // High energy shifts from green toward violet/magenta ("rave mode")
    // Mid energy warms the greens
    // Low energy keeps it cool and teal

    // Phase shifts the palette over time + audio reactivity
    float phase = t * 0.08 + energy * 0.5 + highEnergy * 1.5;
    float s = fract(phase);

    // Construct a cycling palette
    vec3 col;
    if (s < 0.2) {
        col = mix(deep_teal, teal, s / 0.2);
    } else if (s < 0.4) {
        col = mix(teal, emerald, (s - 0.2) / 0.2);
    } else if (s < 0.6) {
        col = mix(emerald, green_glow, (s - 0.4) / 0.2);
    } else if (s < 0.8) {
        col = mix(green_glow, violet, (s - 0.6) / 0.2);
    } else {
        col = mix(violet, magenta, (s - 0.8) / 0.2);
    }

    // High energy pushes toward violet/magenta warmth
    vec3 hotShift = mix(violet, hot_pink, highEnergy);
    col = mix(col, hotShift, highEnergy * 0.35);

    // Mid energy brightens and saturates greens
    col += vec3(0.0, midEnergy * 0.15, midEnergy * 0.05);

    return col;
}

// -----------------------------------------------------------------------
// Starfield — subtle twinkling stars in the dark areas
// -----------------------------------------------------------------------

float starfield(vec2 uv, float t) {
    float stars = 0.0;

    // Layer 1: small, dense stars
    vec2 gridUV = uv * 80.0;
    vec2 cellId = floor(gridUV);
    vec2 cellUV = fract(gridUV) - 0.5;
    float h = hash21(cellId);
    // Random star position within cell
    vec2 starPos = vec2(hash21(cellId + 0.31), hash21(cellId + 0.67)) - 0.5;
    float d = length(cellUV - starPos * 0.8);
    // Twinkling: each star blinks at its own frequency
    float twinkle = sin(t * (2.0 + h * 4.0) + h * 6.28) * 0.5 + 0.5;
    twinkle = twinkle * 0.6 + 0.4;
    float brightness = smoothstep(0.04, 0.0, d) * twinkle;
    // Only ~30% of cells have a visible star
    brightness *= step(0.7, h);
    stars += brightness;

    // Layer 2: fewer, brighter stars
    gridUV = uv * 35.0;
    cellId = floor(gridUV);
    cellUV = fract(gridUV) - 0.5;
    h = hash21(cellId + 42.0);
    starPos = vec2(hash21(cellId + 10.31), hash21(cellId + 10.67)) - 0.5;
    d = length(cellUV - starPos * 0.7);
    twinkle = sin(t * (1.5 + h * 3.0) + h * 6.28) * 0.5 + 0.5;
    brightness = smoothstep(0.035, 0.0, d) * twinkle * 1.5;
    brightness *= step(0.85, h);
    stars += brightness;

    // Layer 3: rare bright stars with a soft glow
    gridUV = uv * 15.0;
    cellId = floor(gridUV);
    cellUV = fract(gridUV) - 0.5;
    h = hash21(cellId + 99.0);
    starPos = vec2(hash21(cellId + 20.31), hash21(cellId + 20.67)) - 0.5;
    d = length(cellUV - starPos * 0.6);
    twinkle = sin(t * (1.0 + h * 2.0) + h * 6.28) * 0.5 + 0.5;
    float core = smoothstep(0.03, 0.0, d) * 2.0;
    float glow = smoothstep(0.15, 0.0, d) * 0.3;
    brightness = (core + glow) * twinkle;
    brightness *= step(0.92, h);
    stars += brightness;

    return stars;
}

// -----------------------------------------------------------------------
// Cosmic dust / nebula haze in dark regions
// -----------------------------------------------------------------------

float cosmicDust(vec2 uv, float t) {
    vec2 p = uv * 3.0;
    float n = 0.0;
    n += valueNoise(p + t * 0.02) * 0.5;
    n += valueNoise(p * 2.3 - t * 0.03 + 3.0) * 0.25;
    n += valueNoise(p * 5.1 + t * 0.01 + 7.0) * 0.125;
    return n;
}

// -----------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------

void main() {
    vec2 uv = v_uv;
    float aspect = u_resolution.x / u_resolution.y;
    vec2 aspectUV = vec2(uv.x * aspect, uv.y);

    float t = u_time;

    // Clamp audio inputs to sane ranges
    float bass     = clamp(u_bass_energy, 0.0, 1.0);
    float energy   = clamp(u_overall_energy, 0.0, 1.0);
    float mid      = clamp(u_mid_energy, 0.0, 1.0);
    float high     = clamp(u_high_energy, 0.0, 1.0);
    float beat     = clamp(u_beat_intensity, 0.0, 1.0);

    // === Deep space background ===
    vec3 spaceTop    = vec3(0.005, 0.01, 0.03);
    vec3 spaceBottom = vec3(0.01, 0.005, 0.02);
    vec3 col = mix(spaceBottom, spaceTop, uv.y);

    // Subtle nebula dust in the dark
    float dust = cosmicDust(aspectUV, t);
    vec3 dustColor = mix(
        vec3(0.02, 0.01, 0.04),  // faint purple
        vec3(0.01, 0.03, 0.04),  // faint teal
        dust
    );
    col += dustColor * dust * 0.15 * (1.0 + energy * 0.5);

    // === Starfield ===
    float stars = starfield(aspectUV, t);
    // Stars are dimmer when aurora is bright (energy-based)
    float starDim = 1.0 - energy * 0.7;
    col += vec3(0.85, 0.9, 1.0) * stars * 0.5 * starDim;

    // === Aurora curtain layers ===
    // Three overlapping curtain layers at different scales and speeds
    // for depth and richness.

    // Time modulation: bass energy speeds up the animation
    float tAurora = t * (0.25 + bass * 0.5 + energy * 0.3);

    // Beat pulse: momentary brightening and scale shift on beats
    float beatPulse = beat * beat; // square for sharper pulse

    // --- Layer 1: far, slow, diffuse ---
    float c1 = auroraCurtain(aspectUV * 0.7, tAurora * 0.5, 0.0, bass);
    vec3 p1 = auroraPalette(c1 * 3.0 + t * 0.03, energy, mid, high);
    col += p1 * c1 * (0.35 + energy * 0.3);

    // --- Layer 2: mid, primary curtain ---
    float c2 = auroraCurtain(aspectUV * 1.0, tAurora * 0.8, 1.0, bass);
    vec3 p2 = auroraPalette(c2 * 3.0 + t * 0.05 + 0.33, energy, mid, high);
    col += p2 * c2 * (0.5 + energy * 0.4);

    // --- Layer 3: near, fast, bright, more reactive ---
    float c3 = auroraCurtain(aspectUV * 1.4, tAurora * 1.2, 2.0, bass);
    vec3 p3 = auroraPalette(c3 * 3.0 + t * 0.07 + 0.66, energy, mid, high);
    col += p3 * c3 * (0.4 + energy * 0.5);

    // === Bright edge glow along curtain tops ===
    // Simulate the intensely bright lower edge of real aurora curtains
    float edgeGlow1 = smoothstep(0.3, 0.6, c2) * smoothstep(0.8, 0.55, c2);
    vec3 edgeColor = mix(
        vec3(0.3, 1.0, 0.5),    // bright green edge
        vec3(0.8, 0.4, 1.0),    // violet edge when high energy
        high * 0.6 + energy * 0.3
    );
    col += edgeColor * edgeGlow1 * (0.3 + beat * 0.5);

    // === Bass pulse: global brightness surge on bass hits ===
    col *= 1.0 + bass * 0.25 + beatPulse * 0.35;

    // === High-energy shimmer: fine sparkle overlaid on bright areas ===
    float shimmer = snoise(aspectUV * 30.0 + t * 2.0) * 0.5 + 0.5;
    shimmer *= snoise(aspectUV * 45.0 - t * 1.5 + 5.0) * 0.5 + 0.5;
    float totalAurora = c1 + c2 + c3;
    col += vec3(0.5, 0.8, 1.0) * shimmer * high * 0.15 * smoothstep(0.2, 0.8, totalAurora);

    // === Vignette: darken the edges for depth ===
    vec2 vc = uv - 0.5;
    float vignette = 1.0 - dot(vc, vc) * 1.2;
    vignette = clamp(vignette, 0.0, 1.0);
    vignette = mix(vignette, 1.0, energy * 0.3); // less vignette when loud
    col *= vignette;

    // === Final tone mapping: soft clamp to prevent harsh clipping ===
    col = col / (1.0 + col * 0.3); // simple Reinhard-ish

    frag_color = vec4(col, 1.0);
}
