// Three transitions in one shader, picked by uType. Inputs: 0 = current, 1 = next, same size
// (both are the 340 x 1080 cut). uProgress runs 0 to 1 over the transition.
//   0 burn:     the next clip appears in the bright parts of the current one first and eats
//               outward through a crisp, slightly ragged edge
//   1 distort:  each picture warps the other by its brightness, peaking mid way at 40% of the
//               strip, so the two smear into one before the next settles
//   2 colour:   the next clip's red lands first, then green, then blue, each sliding in from
//               its own small offset, so the picture passes through a split, saturated phase
uniform float uProgress;
uniform float uType;
out vec4 fragColor;

float luma(vec4 c) { return dot(c.rgb, vec3(0.299, 0.587, 0.114)); }

// samples outside the strip mirror back in, no streaked edges
vec2 mir(vec2 u) { vec2 m = mod(u, 2.0); return mix(m, 2.0 - m, step(1.0, m)); }
vec4 cur(vec2 u) { return texture(sTD2DInputs[0], mir(u)); }
vec4 nxt(vec2 u) { return texture(sTD2DInputs[1], mir(u)); }

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float noise(vec2 p) { return 0.65 * vnoise(p) + 0.35 * vnoise(p * 2.7 + 5.0); }

void main() {
    vec2 uv = vUV.st;
    float p = clamp(uProgress, 0.0, 1.0);
    vec4 c = cur(uv), n = nxt(uv);
    vec4 o;
    if (uType < 0.5) {
        float edge = luma(c) + 0.12 * noise(uv * vec2(6.0, 18.0));
        float t = 1.15 - p * 1.45;
        o = mix(c, n, smoothstep(t - 0.03, t + 0.03, edge));
    } else if (uType < 1.5) {
        float a = 0.4 * sin(3.14159 * p);
        vec4 c2 = cur(uv + vec2(luma(n) - 0.5, (luma(n) - 0.5) * 0.3) * a);
        vec4 n2 = nxt(uv - vec2(luma(c) - 0.5, (luma(c) - 0.5) * 0.3) * a);
        o = mix(c2, n2, smoothstep(0.3, 0.7, p));
    } else {
        float pr = smoothstep(0.0, 0.6, p), pg = smoothstep(0.2, 0.8, p), pb = smoothstep(0.4, 1.0, p);
        float r = nxt(uv + vec2(0.03 * (1.0 - pr), 0.0)).r;
        float g = nxt(uv + vec2(0.0, 0.02 * (1.0 - pg))).g;
        float b = nxt(uv - vec2(0.03 * (1.0 - pb), 0.0)).b;
        o = vec4(mix(c.r, r, pr), mix(c.g, g, pg), mix(c.b, b, pb), 1.0);
    }
    fragColor = TDOutputSwizzle(o);
}
