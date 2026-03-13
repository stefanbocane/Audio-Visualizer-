#version 410

uniform sampler2D u_texture;
uniform vec2      u_direction;  // (1/width, 0) for horizontal, (0, 1/height) for vertical

in vec2 v_uv;

out vec4 frag_color;

void main() {
    // 13-tap Gaussian blur for a wider, softer bloom halo.
    // Sigma ~ 4.0 gives a dreamy spread without losing too much colour.
    // Weights are symmetric and normalised to sum to 1.0.
    const int RADIUS = 6;
    float weights[13] = float[13](
        0.036108,   // -6
        0.050920,   // -5
        0.067458,   // -4
        0.083953,   // -3
        0.098151,   // -2
        0.107798,   // -1
        0.111220,   //  0 (center)
        0.107798,   // +1
        0.098151,   // +2
        0.083953,   // +3
        0.067458,   // +4
        0.050920,   // +5
        0.036108    // +6
    );

    vec3 result = vec3(0.0);

    for (int i = 0; i < 13; i++) {
        float offset = float(i - RADIUS);
        vec2 sample_uv = v_uv + u_direction * offset;
        result += texture(u_texture, sample_uv).rgb * weights[i];
    }

    frag_color = vec4(result, 1.0);
}
