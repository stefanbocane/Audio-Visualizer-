#version 410

// ---------------------------------------------------------------
// Warp Tunnel — Nebula/Aurora Warp Drive
// Radial corkscrew rays through a color-rich aurora nebula.
// Multiple octaves layered at different speeds for parallax depth.
// ---------------------------------------------------------------

#define PI  3.14159265358979323846
#define TAU 6.28318530717958647692

uniform float u_time;
uniform vec2  u_resolution;
uniform float u_energy;
uniform float u_speed;
uniform float u_bass_energy;
uniform float u_beat_intensity;
uniform float u_drop_intensity;

in  vec2 v_uv;
out vec4 frag_color;

// ------- helpers ------------------------------------------------

// 2D hash
float hash2(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

// 2D smooth value noise
float vnoise2d(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash2(i);
    float b = hash2(i + vec2(1.0, 0.0));
    float c = hash2(i + vec2(0.0, 1.0));
    float d = hash2(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// FBM (3 octaves, cheap)
float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 3; i++) {
        v += a * vnoise2d(p);
        p *= 2.17;
        a *= 0.5;
    }
    return v;
}

// ------- aurora palette -----------------------------------------

// Map a 0-1 parameter to the aurora palette.
// Inner = teal / emerald, outer = violet / magenta.
// No white allowed — everything stays saturated and rich.
vec3 auroraPalette(float t) {
    // Key stops: deep teal -> emerald -> cyan -> purple -> magenta
    vec3 c0 = vec3(0.02, 0.30, 0.35);   // deep teal
    vec3 c1 = vec3(0.04, 0.65, 0.45);   // emerald green
    vec3 c2 = vec3(0.05, 0.80, 0.70);   // bright teal-cyan
    vec3 c3 = vec3(0.30, 0.30, 0.80);   // blue-violet
    vec3 c4 = vec3(0.60, 0.10, 0.65);   // magenta-purple
    vec3 c5 = vec3(0.45, 0.05, 0.50);   // deep magenta

    // Piecewise mix across the range
    if (t < 0.2) return mix(c0, c1, t / 0.2);
    if (t < 0.4) return mix(c1, c2, (t - 0.2) / 0.2);
    if (t < 0.6) return mix(c2, c3, (t - 0.4) / 0.2);
    if (t < 0.8) return mix(c3, c4, (t - 0.6) / 0.2);
    return mix(c4, c5, (t - 0.8) / 0.2);
}

// ------- single octave of warp rays ----------------------------

float warpOctave(vec2 uv, float time, float speedMul, float twistAmt,
                 float numRays, float thickness, float dropBoost) {

    float dist  = length(uv);
    float angle = atan(uv.y, uv.x);

    // Spiral twist: angle offset increases with distance and time.
    // The twist corkscrews outward.  dropBoost amplifies rotation.
    float twist = twistAmt * dist * (1.0 + dropBoost * 2.0);
    float twistedAngle = angle + twist + time * 0.3 * speedMul;

    // Streaming time offset — rays zoom outward from center.
    float stream = time * speedMul * (1.0 + dropBoost * 3.0);

    // Radial ray pattern (angular slicing)
    float rayAngle = fract(twistedAngle * numRays / TAU);
    // Triangular pulse for each ray: thin bright core, soft falloff
    float ray = 1.0 - abs(rayAngle - 0.5) * 2.0;
    ray = pow(max(ray, 0.0), 1.0 / thickness);     // sharpen

    // Radial streaking — lines that rush along the distance axis
    float streak = fract(dist * 6.0 - stream);
    streak = smoothstep(0.0, 0.08, streak) * (1.0 - smoothstep(0.08, 0.25, streak));

    // Combine: rays * streak gives crossing radial+angular pattern
    float combined = ray * 0.7 + streak * 0.4;

    // Nebula texture modulation — fbm breaks up uniformity
    float neb = fbm(vec2(twistedAngle * 2.0, dist * 4.0 - stream * 0.5));
    combined *= 0.6 + neb * 0.6;

    // Radial fade: invisible at center, peaks mid-range, fades at edge
    float fade = smoothstep(0.0, 0.06, dist) * smoothstep(0.95, 0.20, dist);
    combined *= fade;

    return combined;
}

// ------- main ---------------------------------------------------

void main() {
    float aspect = u_resolution.x / u_resolution.y;

    // Centered, aspect-corrected UV
    vec2 uv = v_uv - 0.5;
    uv.x *= aspect;

    float dist  = length(uv);
    float angle = atan(uv.y, uv.x);

    // Effective speed incorporates base speed + energy surge
    float eff_speed = u_speed * (1.0 + u_bass_energy * 0.6);

    // Drop intensity drives the dramatic acceleration burst
    float drop = u_drop_intensity;
    float beat = u_beat_intensity;

    // ---------- layer multiple octaves for depth ----------------

    // Octave 1: dense fast foreground rays
    float o1 = warpOctave(uv, u_time, eff_speed * 1.3, 3.5 + beat * 2.0,
                           50.0 + u_energy * 40.0, 0.35, drop);

    // Octave 2: medium rays, slightly slower, offset twist
    vec2 uv2 = uv * 0.85;  // scale for parallax
    float o2 = warpOctave(uv2, u_time + 17.3, eff_speed * 0.85, -2.8 - beat * 1.5,
                           30.0 + u_energy * 20.0, 0.45, drop * 0.7);

    // Octave 3: sparse slow background — wide soft rays
    vec2 uv3 = uv * 0.65;
    float o3 = warpOctave(uv3, u_time + 41.7, eff_speed * 0.5, 1.8,
                           18.0 + u_energy * 10.0, 0.6, drop * 0.4);

    // Combine octaves with decreasing weight for depth ordering
    float tunnel = o1 * 0.55 + o2 * 0.30 + o3 * 0.15;

    // Boost overall with energy + extra pop on beats
    tunnel *= u_energy * (1.0 + beat * 0.6);

    // ---------- coloring ----------------------------------------

    // Map color based on angle + distance -> aurora palette
    // Angle maps the base hue, distance shifts toward outer palette.
    float hueParam = fract(angle / TAU + 0.5);              // 0-1 from angle
    float distShift = smoothstep(0.0, 0.6, dist) * 0.45;   // push outer toward violet
    float colorT = fract(hueParam * 0.5 + distShift + u_time * 0.02);

    vec3 col = auroraPalette(colorT);

    // Modulate brightness per-octave: foreground brighter teal, background more violet
    vec3 innerGlow = auroraPalette(fract(colorT - 0.15));   // shift tealward
    vec3 outerGlow = auroraPalette(fract(colorT + 0.25));   // shift violetward

    // Blend inner/outer by distance
    float innerMix = smoothstep(0.5, 0.0, dist);
    col = mix(outerGlow, innerGlow, innerMix);

    // Apply intensity
    col *= tunnel * 2.2;

    // Drop flash: momentary bloom in saturated magenta-violet
    vec3 dropColor = vec3(0.50, 0.08, 0.60);
    col += dropColor * drop * tunnel * 1.8;

    // Beat pulse: subtle brightness surge in emerald
    vec3 beatColor = vec3(0.05, 0.55, 0.40);
    col += beatColor * beat * tunnel * 0.6;

    // Soft vignette at extreme edges to frame the tunnel
    float vignette = 1.0 - smoothstep(0.3, 0.85, dist);
    col *= 0.5 + vignette * 0.5;

    // Clamp to prevent negative from the noise math
    col = max(col, vec3(0.0));

    // Alpha: tunnel visibility
    float alpha = clamp(tunnel * 1.5, 0.0, 1.0);

    frag_color = vec4(col, alpha);
}
