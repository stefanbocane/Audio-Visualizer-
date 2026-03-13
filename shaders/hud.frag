#version 410

uniform sampler2D u_texture;

in vec2 v_uv;

out vec4 frag_color;

void main() {
    vec4 texel = texture(u_texture, v_uv);
    frag_color = texel;
}
