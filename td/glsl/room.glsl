// Room darkening, the last step of each group's chain, set on site for the room's light.
// uDark pulls the whites down by 1 + uDark and leaves near-black alone, v / (1 + uDark v);
// uContrast then steepens the result so the midtones follow the whites down instead of
// settling into grey. Both at 0 and 1 is a pass-through.
uniform float uDark;
uniform float uContrast;
out vec4 fragColor;

void main() {
    vec4 c = texture(sTD2DInputs[0], vUV.st);
    vec3 v = max(c.rgb, 0.0);
    float top = 1.0 + uDark;
    v = v / (1.0 + uDark * v);        // white lands at 1 / top
    v = pow(v * top, vec3(uContrast)) / top;  // contrast on the normalised range, then back down
    fragColor = TDOutputSwizzle(vec4(v, c.a));
}
