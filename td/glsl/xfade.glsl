// Two transitions in one shader. uType 0: luma melt, the brighter picture eats the darker one
// through a soft threshold that sweeps. uType 1: displacement meld, each picture displaces the
// other, growing then settling. Inputs: 0 = current, 1 = next, same size (both are the 340 x 1080 cut).
uniform float uProgress;
uniform float uType;
out vec4 fragColor;

float luma(vec4 c) { return dot(c.rgb, vec3(0.299, 0.587, 0.114)); }

void main() {
    vec2 uv = vUV.st;
    float p = clamp(uProgress, 0.0, 1.0);
    vec4 cur = texture(sTD2DInputs[0], uv);
    vec4 nxt = texture(sTD2DInputs[1], uv);
    vec4 o;
    if (uType < 0.5) {
        float k = luma(nxt) - luma(cur) + (2.0 * p - 1.0) * 1.2;
        o = mix(cur, nxt, smoothstep(-0.15, 0.15, k));
    } else {
        float a = 0.08;
        vec4 c2 = texture(sTD2DInputs[0], uv + vec2(luma(nxt) - 0.5) * p * a);
        vec4 n2 = texture(sTD2DInputs[1], uv + vec2(luma(cur) - 0.5) * (1.0 - p) * a);
        o = mix(c2, n2, smoothstep(0.2, 0.8, p));
    }
    fragColor = TDOutputSwizzle(o);
}
