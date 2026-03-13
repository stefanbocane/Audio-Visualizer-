#version 410

in vec2 in_position;  // L/R sample as (x, y)

out float v_intensity;

void main() {
    // Scale to fit in a small viewport (glViewport will confine the rendering area)
    vec2 scaled = in_position * 0.8;

    gl_Position = vec4(scaled, 0.0, 1.0);
    gl_PointSize = 3.0;

    // Intensity based on distance from center (more active = brighter)
    v_intensity = length(in_position);
}
