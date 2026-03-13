#version 410

#define PI 3.14159265358979323846
#define NUM_BARS 128

uniform vec2  u_resolution;
uniform float u_bar_data[NUM_BARS];
uniform float u_bar_prev[NUM_BARS];   // previous-frame heights for tip trails
uniform float u_beat_ripple;
uniform float u_time;
uniform float u_bass_energy;

in vec2 in_position;   // Unit quad vertices: x in [0,1], y in [0,1]

out float v_intensity;       // bar amplitude 0..1
out float v_along_bar;       // 0 at base, 1 at tip
out float v_across_bar;      // 0 at left edge, 1 at right edge (for soft edges)
out float v_bar_id_norm;     // normalized bar index 0..1
out float v_is_reflection;   // 0 = main bar, 1 = reflection
out float v_neighbor_avg;    // average intensity of neighboring bars (inter-bar glow)
out float v_tip_trail;       // previous frame height for tip trail effect
flat out int v_bar_id;       // integer bar ID

void main() {
    int id = gl_InstanceID % NUM_BARS;
    // Instances 0..127 = main bars, 128..255 = reflections
    bool is_reflection = gl_InstanceID >= NUM_BARS;

    float bar_val = u_bar_data[id];
    float bar_prev = u_bar_prev[id];
    float id_norm = float(id) / float(NUM_BARS - 1);  // 0..1

    // --- Compute neighbor average for inter-bar glow ---
    float neighbor_sum = 0.0;
    int count = 0;
    for (int offset = -2; offset <= 2; offset++) {
        int nid = id + offset;
        if (nid >= 0 && nid < NUM_BARS && offset != 0) {
            neighbor_sum += u_bar_data[nid];
            count++;
        }
    }
    float neighbor_avg = (count > 0) ? neighbor_sum / float(count) : 0.0;

    // --- Arc layout: bars spread across the bottom in a gentle curve ---
    // Horizontal spread: bars go from about -0.85 to +0.85 in NDC x
    float spread = 1.7;
    float bar_center_x = (id_norm - 0.5) * spread;

    // Gentle arc: bars in the center are slightly lower, edges slightly higher
    // This creates a subtle smile/bowl shape
    float arc_strength = 0.06;
    float arc_offset = arc_strength * (4.0 * (id_norm - 0.5) * (id_norm - 0.5));

    // Baseline y position (bottom of screen area)
    float baseline_y = -0.55 + arc_offset;

    // Bar dimensions
    float max_bar_height = 0.75;
    float bar_height = bar_val * max_bar_height;

    // Beat ripple: subtle per-bar oscillation
    float ripple = sin(float(id) * 0.25 + u_time * 4.0) * u_beat_ripple * 0.015;
    bar_height += ripple;
    bar_height = max(bar_height, 0.005); // minimum visible height

    // Bar width with slight taper toward tips
    float along_bar = in_position.y;
    float bar_gap = spread / float(NUM_BARS);
    float base_width = bar_gap * 0.72;
    float taper = mix(1.0, 0.55, along_bar);  // narrower at top
    float half_w = base_width * 0.5 * taper;

    // Tangential position within the bar
    float across = in_position.x;  // 0..1
    float local_x = (across - 0.5) * 2.0 * half_w;

    float x = bar_center_x + local_x;
    float y;

    if (!is_reflection) {
        // Main bar: rises upward from baseline
        y = baseline_y + along_bar * bar_height;
    } else {
        // Reflection: extends downward from baseline, compressed
        float reflection_height = bar_height * 0.35;
        y = baseline_y - along_bar * reflection_height;
    }

    // Subtle bass-driven sway
    float sway = sin(u_time * 1.5 + id_norm * PI) * u_bass_energy * 0.008;
    x += sway;

    // Aspect ratio correction
    float aspect = u_resolution.x / u_resolution.y;
    x /= aspect;

    gl_Position = vec4(x, y, 0.0, 1.0);

    // Pass varyings
    v_intensity = bar_val;
    v_along_bar = along_bar;
    v_across_bar = across;
    v_bar_id_norm = id_norm;
    v_is_reflection = is_reflection ? 1.0 : 0.0;
    v_neighbor_avg = neighbor_avg;
    v_tip_trail = bar_prev;
    v_bar_id = id;
}
