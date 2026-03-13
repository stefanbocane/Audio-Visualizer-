#version 410

uniform sampler2D u_scene;
uniform sampler2D u_bloom;
uniform sampler2D u_previous_frame;
uniform float     u_flash_intensity;
uniform float     u_motion_blur_strength;  // ~0.85
uniform float     u_time;
uniform float     u_beat_intensity;        // 0..1+ from beat detector
uniform float     u_bass_energy;           // 0..1+ low-frequency energy
uniform vec2      u_resolution;            // screen width, height in pixels

in vec2 v_uv;

out vec4 frag_color;

// -------------------------------------------------------------------
// Utility: pseudo-random hash for film grain
// -------------------------------------------------------------------
float hash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void main() {
    // ---------------------------------------------------------------
    // Chromatic aberration -- splits RGB at edges, driven by beat
    // ---------------------------------------------------------------
    vec2 uv_centered = v_uv - 0.5;
    float edge_dist = length(uv_centered);

    // Aberration strength scales with distance from center and beat
    float aberration_base = 0.001;
    float aberration_beat = 0.004 * u_beat_intensity;
    float aberration = (aberration_base + aberration_beat) * edge_dist;

    // Offset direction points radially outward from center
    vec2 aberration_dir = normalize(uv_centered + 0.0001) * aberration;

    float r = texture(u_scene, v_uv + aberration_dir).r;
    float g = texture(u_scene, v_uv).g;
    float b = texture(u_scene, v_uv - aberration_dir).b;
    vec3 scene = vec3(r, g, b);

    // Sample bloom and previous frame normally
    vec3 bloom  = texture(u_bloom, v_uv).rgb;
    vec3 prev   = texture(u_previous_frame, v_uv).rgb;

    // ---------------------------------------------------------------
    // Combine scene with bloom (additive)
    // ---------------------------------------------------------------
    float bloom_strength = 0.65;
    vec3 color = scene + bloom * bloom_strength;

    // ---------------------------------------------------------------
    // Motion blur: mix with previous frame using decay factor
    // ---------------------------------------------------------------
    color = mix(color, prev, u_motion_blur_strength);

    // ---------------------------------------------------------------
    // Beat flash: always 0, kept for compatibility
    // ---------------------------------------------------------------
    color += vec3(u_flash_intensity);

    // ---------------------------------------------------------------
    // Reinhard tone mapping (HDR -> LDR)
    // ---------------------------------------------------------------
    color = color / (1.0 + color);

    // ---------------------------------------------------------------
    // Color grading: shadows toward deep teal, highlights toward violet
    // ---------------------------------------------------------------
    float luminance = dot(color, vec3(0.2126, 0.7152, 0.0722));

    // Shadow tint: deep teal (dark cyan-blue)
    vec3 shadow_tint = vec3(0.04, 0.12, 0.14);
    // Highlight tint: soft violet
    vec3 highlight_tint = vec3(0.14, 0.06, 0.16);

    // Blend factor: shadows get teal push, highlights get violet push
    float shadow_weight = 1.0 - smoothstep(0.0, 0.35, luminance);
    float highlight_weight = smoothstep(0.55, 1.0, luminance);

    // Apply subtle color grading via additive tinting
    color += shadow_tint * shadow_weight * 0.35;
    color += highlight_tint * highlight_weight * 0.25;

    // ---------------------------------------------------------------
    // Vignette: dramatic pull to center
    // ---------------------------------------------------------------
    float vignette_dist = length(uv_centered * vec2(1.0, 0.85)); // slightly oval
    // Two-stage vignette: gentle inner falloff + hard outer edge
    float vignette_inner = 1.0 - smoothstep(0.25, 0.75, vignette_dist);
    float vignette_outer = 1.0 - smoothstep(0.6, 1.1, vignette_dist);
    float vignette = vignette_inner * 0.6 + vignette_outer * 0.4;
    // Floor so edges never go fully black -- keep some atmosphere
    vignette = mix(0.15, 1.0, vignette);
    // Beat slightly opens the vignette (breathing effect)
    vignette = mix(vignette, 1.0, u_beat_intensity * 0.08);
    color *= vignette;

    // ---------------------------------------------------------------
    // Film grain: subtle noise overlay for texture
    // ---------------------------------------------------------------
    float grain = hash(v_uv * u_resolution + fract(u_time * 7.13) * 1000.0);
    // Remap from [0,1] to [-1,1], keep very subtle
    grain = (grain - 0.5) * 0.04;
    // Grain is more visible in darker areas, less in bright
    float grain_mask = 1.0 - luminance * 0.6;
    color += grain * grain_mask;

    // ---------------------------------------------------------------
    // Final clamp (safety)
    // ---------------------------------------------------------------
    color = clamp(color, 0.0, 1.0);

    frag_color = vec4(color, 1.0);
}
