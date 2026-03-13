#version 410

uniform vec2  u_resolution;
uniform float u_shockwave_progress;   // 0 = just triggered, 1 = fully expanded
uniform float u_shockwave_intensity;  // Decays on CPU

in vec2 v_uv;

out vec4 frag_color;

void main() {
    vec2 uv = v_uv;
    float aspect = u_resolution.x / u_resolution.y;
    vec2 center = vec2(0.5, 0.5);

    // Aspect-corrected distance from center
    vec2 delta = uv - center;
    delta.x *= aspect;
    float dist = length(delta);

    // Ring parameters
    float ring_radius = u_shockwave_progress * 0.8;
    // Ring thickness decreases as it expands
    float ring_thickness = mix(0.06, 0.01, u_shockwave_progress);

    // SDF ring
    float ring_dist = abs(dist - ring_radius);
    float ring = 1.0 - smoothstep(0.0, ring_thickness, ring_dist);

    // Color: ice_blue tinted, no white blowout
    vec3 ice_blue = vec3(0.5, 0.9, 1.0);
    vec3 teal     = vec3(0.0, 0.7, 0.7);
    vec3 ring_color = mix(ice_blue, teal, u_shockwave_progress * 0.5);

    // Fade out with progress
    float fade = 1.0 - smoothstep(0.3, 1.0, u_shockwave_progress);

    // Apply intensity — scaled down to avoid flash
    float alpha = ring * fade * u_shockwave_intensity * 0.4;

    // Additive output (will be composited additively)
    frag_color = vec4(ring_color * alpha, alpha);
}
