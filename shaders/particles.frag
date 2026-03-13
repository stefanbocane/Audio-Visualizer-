#version 410

uniform float u_time;
uniform float u_energy;

in float v_speed;
in float v_alpha;
in float v_radius;

out vec4 frag_color;

void main() {
    // Circular falloff from gl_PointCoord center.
    vec2 coord = gl_PointCoord - vec2(0.5);
    float dist = length(coord);

    // Discard fragments outside the circle.
    if (dist > 0.5) {
        discard;
    }

    // Soft circular edge with extra glow halo for fast particles.
    float edge = 1.0 - smoothstep(0.2, 0.5, dist);
    // Inner glow core (brighter center).
    float core = 1.0 - smoothstep(0.0, 0.25, dist);
    float glow = edge + core * 0.3 * v_speed;

    // --- Aurora palette (no white!) ---
    // Deep teal (slow/far) -> Emerald (medium) -> Violet/Magenta (fast/close)
    vec3 deep_teal  = vec3(0.05, 0.45, 0.50);
    vec3 teal       = vec3(0.0,  0.65, 0.55);
    vec3 emerald    = vec3(0.05, 0.80, 0.40);
    vec3 aurora_green = vec3(0.20, 0.85, 0.35);
    vec3 violet     = vec3(0.55, 0.15, 0.85);
    vec3 magenta    = vec3(0.75, 0.10, 0.65);
    vec3 rose       = vec3(0.65, 0.20, 0.55);

    // Speed-based colour ramp: 5 stops for richness.
    float s = clamp(v_speed, 0.0, 1.0);
    vec3 col;
    if (s < 0.2) {
        col = mix(deep_teal, teal, s / 0.2);
    } else if (s < 0.4) {
        col = mix(teal, emerald, (s - 0.2) / 0.2);
    } else if (s < 0.6) {
        col = mix(emerald, aurora_green, (s - 0.4) / 0.2);
    } else if (s < 0.8) {
        col = mix(aurora_green, violet, (s - 0.6) / 0.2);
    } else {
        col = mix(violet, magenta, (s - 0.8) / 0.2);
    }

    // Distance tint: particles far from center shift toward teal/blue,
    // particles near center get a warmer violet push.
    float r = clamp(v_radius, 0.0, 1.0);
    vec3 center_tint = rose * 0.15;
    vec3 edge_tint   = deep_teal * 0.15;
    col += mix(center_tint, edge_tint, r);

    // Subtle time-based hue shimmer (organic aurora ripple).
    float shimmer = sin(v_speed * 12.0 + u_time * 2.5 + v_radius * 8.0) * 0.5 + 0.5;
    col = mix(col, col * vec3(0.9, 1.1, 1.05), shimmer * 0.12);

    // HDR boost for fast particles -- saturated glow, NOT white.
    // The boost multiplies color channels non-uniformly to keep hue.
    float hdr = 1.0 + smoothstep(0.4, 1.0, s) * 1.2;
    col *= hdr;

    // Energy-reactive luminance lift (subtle).
    col *= 1.0 + u_energy * 0.25;

    // Clamp to prevent any channel from going bright-white.
    // Allow mild HDR overbrights but keep the strongest channel < 2.0.
    col = min(col, vec3(1.8));

    // Final alpha: circular edge * trail alpha * glow shape.
    float alpha = glow * v_alpha;

    // Pre-multiplied alpha output (additive blending).
    frag_color = vec4(col * alpha, alpha);
}
