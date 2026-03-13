#version 410

in float v_intensity;

out vec4 frag_color;

void main() {
    // Circular point sprite
    vec2 coord = gl_PointCoord - vec2(0.5);
    float dist = length(coord);

    // Discard outside circle
    if (dist > 0.5) {
        discard;
    }

    // Soft edge
    float edge = 1.0 - smoothstep(0.25, 0.5, dist);

    // Color: teal with alpha fadeout
    vec3 teal = vec3(0.0, 0.6, 0.6);

    // Slight color shift with intensity
    vec3 emerald = vec3(0.0, 0.8, 0.4);
    float t = clamp(v_intensity, 0.0, 1.0);
    vec3 col = mix(teal, emerald, t * 0.3);

    // Alpha fadeout
    float alpha = edge * 0.7;

    frag_color = vec4(col * alpha, alpha);
}
