#version 410

uniform float u_time;
uniform vec2  u_resolution;
uniform float u_energy;
uniform float u_bass_energy;

in vec2 v_uv;

out vec4 frag_color;

// --- 2D Simplex Noise (Ashima Arts / Ian McEwan) ---
// https://github.com/ashima/webgl-noise

vec3 mod289(vec3 x) {
    return x - floor(x * (1.0 / 289.0)) * 289.0;
}

vec2 mod289(vec2 x) {
    return x - floor(x * (1.0 / 289.0)) * 289.0;
}

vec3 permute(vec3 x) {
    return mod289(((x * 34.0) + 1.0) * x);
}

float snoise(vec2 v) {
    const vec4 C = vec4(
        0.211324865405187,   // (3.0 - sqrt(3.0)) / 6.0
        0.366025403784439,   // 0.5 * (sqrt(3.0) - 1.0)
       -0.577350269189626,   // -1.0 + 2.0 * C.x
        0.024390243902439    // 1.0 / 41.0
    );

    // First corner
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v - i + dot(i, C.xx);

    // Other corners
    vec2 i1;
    i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 x1 = x0 - i1 + C.xx;
    vec2 x2 = x0 + C.zz;

    // Permutations
    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
                             + i.x + vec3(0.0, i1.x, 1.0));

    vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x1, x1), dot(x2, x2)), 0.0);
    m = m * m;
    m = m * m;

    // Gradients: 41 points uniformly over a line, mapped onto a diamond
    vec3 x  = 2.0 * fract(p * C.www) - 1.0;
    vec3 h  = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;

    // Normalise gradients implicitly by scaling m
    m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);

    // Compute final noise value at P
    vec3 g;
    g.x = a0.x * x0.x + h.x * x0.y;
    g.y = a0.y * x1.x + h.y * x1.y;
    g.z = a0.z * x2.x + h.z * x2.y;

    return 130.0 * dot(m, g);
}

void main() {
    vec2 uv = v_uv;
    float aspect = u_resolution.x / u_resolution.y;
    vec2 p = vec2(uv.x * aspect, uv.y);

    // Animation speed scales with energy
    float speed = mix(0.15, 0.6, u_energy);
    float t = u_time * speed;

    // 3 octaves of noise with time-based animation
    float n = 0.0;
    n += 0.5   * snoise(p * 1.5 + vec2(t * 0.3, t * 0.2));
    n += 0.25  * snoise(p * 3.0 + vec2(-t * 0.5, t * 0.4));
    n += 0.125 * snoise(p * 6.0 + vec2(t * 0.7, -t * 0.3));
    n = n * 0.5 + 0.5; // remap to [0, 1]

    // Vertical curtain effect: noise stronger at top, fading at bottom
    float curtain = smoothstep(0.0, 0.7, uv.y);
    curtain = pow(curtain, mix(2.0, 0.8, u_energy));
    n *= curtain;

    // Boost noise intensity with energy
    n *= mix(0.3, 1.0, u_energy);

    // Aurora palette
    vec3 deep_space = vec3(0.02, 0.05, 0.08);
    vec3 teal       = vec3(0.0,  0.6,  0.6);
    vec3 emerald    = vec3(0.0,  0.8,  0.4);
    vec3 green      = vec3(0.2,  1.0,  0.3);
    vec3 violet     = vec3(0.6,  0.2,  0.9);

    // Energy-driven palette interpolation
    // Low energy: deep_space with subtle teal wisps
    // High energy: brilliant aurora curtains
    float energy_ramp = u_energy;
    vec3 col;

    if (n < 0.25) {
        col = mix(deep_space, teal, n / 0.25);
    } else if (n < 0.5) {
        col = mix(teal, emerald, (n - 0.25) / 0.25);
    } else if (n < 0.75) {
        col = mix(emerald, green, (n - 0.5) / 0.25);
    } else {
        col = mix(green, violet, (n - 0.75) / 0.25);
    }

    // Blend toward deep_space at low energy
    col = mix(deep_space + (col - deep_space) * 0.15, col, energy_ramp);

    // Add subtle bass-driven brightness pulse
    col += col * u_bass_energy * 0.2;

    frag_color = vec4(col, 1.0);
}
