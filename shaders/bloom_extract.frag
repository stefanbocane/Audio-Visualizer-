#version 410

uniform sampler2D u_scene;
uniform float     u_threshold;  // Default ~0.55 (lowered for more glow)

in vec2 v_uv;

out vec4 frag_color;

void main() {
    vec3 color = texture(u_scene, v_uv).rgb;

    // Perceived luminance (Rec. 709)
    float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));

    // Soft knee extraction -- wider transition band for a gentler bloom onset.
    // Everything above threshold starts glowing; full bloom at threshold + knee.
    float knee = 0.6;
    float extraction = smoothstep(u_threshold, u_threshold + knee, brightness);

    // Preserve the original colour hue instead of washing toward white.
    // Scale by extraction but also attenuate very bright pixels to prevent blowout.
    vec3 extracted = color * extraction;

    // Soft saturation boost: push bloom colours slightly so the glow
    // enhances hue rather than bleaching it.
    float ext_lum = dot(extracted, vec3(0.2126, 0.7152, 0.0722));
    vec3 chroma = extracted - ext_lum;
    extracted = ext_lum + chroma * 1.3;  // 30% saturation boost on bloom

    frag_color = vec4(max(extracted, 0.0), 1.0);
}
