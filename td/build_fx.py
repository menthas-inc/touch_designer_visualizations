"""Build /project1/fx: two players, two group chains, the transitions, the limiter, the timers.

Run inside TouchDesigner, from the Textport:
    exec(open(project.folder + '/../td/build_fx.py').read())

Running it again deletes and rebuilds fx. It ends by pointing the four strips at the two group
outputs, clearing Rectangle6's dangling texture, deleting the old playlist chain, and starting
the sequencer. Spec: docs/specs/001-dynamic-effects/impl-spec.md.

A parameter name this script gets wrong is reported, not fatal: the build goes on and the
Textport lists every miss at the end, so one typo costs one rerun, not a blind debugging session.
"""
import os

# file pars are relative to the .toe's folder (TD_Mapping/), so the save carries no machine path
SEQ = "../td/sequencer.py"
GLSL = "../td/glsl/xfade.glsl"
ROOM_GLSL = "../td/glsl/room.glsl"
W, H = 340, 1080  # the strip cut
PAN_LFO = {"outer": (0.011, 128), "inner": (0.017, 64)}  # Hz free, or beats per cycle when synced: the two groups drift at different rates
PAN_DRIFT = 0.1  # of the frame width, the drift's reach either way
WIDE_FRAME = 1100  # the wide scheme covers this width at 1080 tall: 1920 was three times closer on a portrait clip, this about 1.8
HELP = {
    "Ceiling": "The limiter: each group's mean brightness is held at or below this. 1 turns it off.",
    "Brightmean": "A clip window with a mean luma at or above this counts as bright and gets a darkening effect.",
    "Brighthigh": "A clip window whose high-percentile luma reaches this counts as bright, whatever its mean.",
    "Cap": "Seconds a clip plays on the wall at most; long clips get a random window of this length.",
    "Rerollevery": "Seconds between reroll ticks; each tick one group, in turn, may swap to a new look mid clip.",
    "Seed": "Random seed for the whole show. 0 means a fresh one at every start.",
    "Darkness": "Macro: none turns darkening off, default, darker and darkest cut bright patches harder.",
    "Roomdark": "Pulls whites down by this much, near-black stays; set for the room. 0 is off.",
    "Roomcontrast": "Steepens the picture after Roomdark so the midtones follow the whites down. 1 is off.",
    "Beatsync": "Follow the beat from beat/beat_osc.py: LFO rates, the reroll tick, the spice swells and the bounce.",
    "Beatoffset": "Seconds the tracker hears the beat late; positive pulls the chain earlier. Tune against the bounce.",
    "Beatbounce": "How much both groups zoom on each beat, settling before the next. 0 is off.",
    "Bpm": "What the tracker hears, 0 when nothing for 3 s. A readout, not a setting.",
    "Beatsource": "What the tracker listens to: the mic, or system, everything the Mac plays (a Chrome tab). Sent to it over OSC.",
    "Hold": "Stop the random choosing and show one effect, chosen below, on both groups.",
    "Effect": "The effect shown while Hold is on.",
    "Preveffect": "Step Hold to the previous effect.",
    "Nexteffect": "Step Hold to the next effect.",
    "Reroll": "New random values for the held effect.",
    "Xfadetype": "Force one transition type for every clip change, or random.",
}
STRIPS = {"outer": ("item5", "item1"), "inner": ("item4", "item2")}  # left to right: 5 4 2 1

ns = {}
exec(open(os.path.join(project.folder, SEQ)).read(), ns)  # the corpus, without touching TouchDesigner names
CORPUS, ORDER = ns["CORPUS"], ns["ORDER"]

misses = []


def setp(o, **pars):
    """Set parameters by name; a wrong name is logged, not fatal."""
    for k, v in pars.items():
        p = getattr(o.par, k, None)
        if p is None:
            misses.append(f"{o.path}: no par {k}")
            continue
        try:
            if isinstance(v, str) and v.startswith("="):
                p.expr = v[1:]
            else:
                p.val = v
        except Exception as e:  # a bad menu token, a bad expression
            misses.append(f"{o.path}.{k} = {v!r}: {e}")


def wire(dst, *srcs):
    for i, s in enumerate(srcs):
        # a COMP source has several outputs, so connect() wants its connector, not the OP
        dst.inputConnectors[i].connect(s.outputConnectors[0])
    return dst


def mk(parent, optype, name, *inputs, **pars):
    o = parent.create(optype, name)
    if inputs:
        wire(o, *inputs)
    if pars:
        setp(o, **pars)
    return o


def custom(comp, page, **pars):
    """Custom pars: name -> default (float, int or 0/1 toggle)."""
    pg = comp.appendCustomPage(page)
    out = {}
    for name, default in pars.items():
        if isinstance(default, bool):
            p = pg.appendToggle(name, label=name)[0]
        elif isinstance(default, int):
            p = pg.appendInt(name, label=name)[0]
        else:
            p = pg.appendFloat(name, label=name)[0]
        p.default = default
        p.val = default
        out[name] = p
    return out


def default_for(spec):
    if isinstance(spec, list):
        return spec[0]
    lo, hi = spec
    return round((lo + hi) / 2, 4)


# ---------------------------------------------------------------- effects
# Each returns the last TOP of the wet path, given the effect base and its in1.
def fx_framing(b, src):
    t = mk(b, transformTOP, "xform", src, extend="mirror",  # mirrored edges, so a tilt shows no black corner
           sx="=parent().par.Zoom", sy="=parent().par.Zoom", tx="=parent().par.Tx", ty="=parent().par.Ty",
           rotate="=parent().par.Rotate")
    return mk(b, flipTOP, "flip", t, flipx="=parent().par.Flipx", flipy="=parent().par.Flipy")


def fx_keepchannel(b, src):
    # Channel Mix: red1..red4 are output red's weights from input r, g, b, a, and so on.
    # Mode 0 keeps red, 1 green, 2 blue; the other two outputs go to zero.
    pars = {}
    for i, c in enumerate(("red", "green", "blue")):
        for j in range(1, 4):
            pars[f"{c}{j}"] = f"=1 if (int(parent().par.Mode) == {i} and {j} == {i + 1}) else 0"
    return mk(b, channelmixTOP, "mix", src, **pars)


def lfo(b, name, freq, beats):
    """A slow LFO at `freq` Hz, or one cycle per `beats` beats when the beat is being heard."""
    return mk(b, lfoCHOP, name, frequency=f"=op('/project1/fx/sequencer').module.lfo_rate({freq}, {beats})")


def fx_highlights(b, src):
    m = mk(b, monochromeTOP, "mono", src)
    th = mk(b, thresholdTOP, "thresh", m, threshold="=parent().par.Cut")
    bl = mk(b, blurTOP, "soft", th, size="=parent().par.Soft")
    inv = mk(b, levelTOP, "inv", bl, invert=1.0)
    mul = mk(b, compositeTOP, "mul", src, inv, operand="multiply")
    return mk(b, crossTOP, "cross", src, mul, cross="=parent().par.Amount")  # dim the highlights, do not cut them


def fx_crush(b, src):
    return mk(b, levelTOP, "level", src, gamma1="=parent().par.Gamma", blacklevel="=parent().par.Black")


def fx_edges(b, src):
    e = mk(b, edgeTOP, "edge", src, strength="=parent().par.Strength")
    return mk(b, crossTOP, "cross", src, e, cross="=parent().par.Mix")


def fx_tint(b, src):
    m = mk(b, monochromeTOP, "mono", src)
    deep = mk(b, levelTOP, "deep", m, gamma1=1.4, blacklevel=0.05)  # blacks stay black under the colour
    c = mk(b, constantTOP, "colour",
           colorr="=op('/project1/fx/sequencer').module.hsv_rgb(parent().par.Hue, parent().par.Sat)[0]",
           colorg="=op('/project1/fx/sequencer').module.hsv_rgb(parent().par.Hue, parent().par.Sat)[1]",
           colorb="=op('/project1/fx/sequencer').module.hsv_rgb(parent().par.Hue, parent().par.Sat)[2]")
    return mk(b, compositeTOP, "mul", deep, c, operand="multiply")


def fx_selfmask(b, src):
    m = mk(b, monochromeTOP, "mono", src)
    inv = mk(b, levelTOP, "inv", m, invert=1.0)
    mul = mk(b, compositeTOP, "mul", src, inv, operand="multiply")
    con = mk(b, levelTOP, "contrast", mul, contrast="=parent().par.Contrast")
    sat = mk(b, hsvadjustTOP, "sat", con, saturationmult="=parent().par.Sat")
    return mk(b, crossTOP, "cross", src, sat, cross="=parent().par.Amount")


def fx_feedback(b, src):
    out = mk(b, nullTOP, "fb_out")
    lfo(b, "lfo_zoom", 0.05, 32)
    lfo(b, "lfo_rot", 0.03, 64)
    fb = mk(b, feedbackTOP, "fb", src, top="fb_out")  # input is the first frame, top the loop
    t = mk(b, transformTOP, "xform", fb,
           sx="=1 + (parent().par.Zoom - 1) * op('lfo_zoom')[0]", sy="=1 + (parent().par.Zoom - 1) * op('lfo_zoom')[0]",
           rotate="=parent().par.Rotate * op('lfo_rot')[0]")
    lv = mk(b, levelTOP, "decay", t, brightness1="=parent().par.Decay")
    cr = mk(b, crossTOP, "cross", src, lv, cross="=parent().par.Mix * parent().par.Enable")
    wire(out, cr)
    return out


def fx_displace(b, src):
    lfo(b, "lfo", 0.03, 64)
    n = mk(b, noiseTOP, "noise", mono=True, period="=parent().par.Scale", tz="=absTime.seconds * parent().par.Speed",
           resolutionw=128, resolutionh=128)
    amt = "=parent().par.Amount * (0.7 + 0.3 * op('lfo')[0])"
    return mk(b, displaceTOP, "disp", src, n, displaceweightx=amt, displaceweighty=amt)


def fx_echo(b, src):
    lfo(b, "lfo", 0.05, 32)
    c = mk(b, cacheTOP, "cache", src, cachesize=61)
    s = mk(b, cacheselectTOP, "sel", cachetop="cache", index="=-int(parent().par.Frames * (0.67 + 0.33 * op('lfo')[0]))")
    return mk(b, crossTOP, "cross", src, s, cross="=parent().par.Mix * parent().par.Enable")


def fx_mirror(b, src):
    # Mode 0 mirrors across x, 1 across y, 2 both; the seam drifts on two slow LFOs
    lfo(b, "lfo_x", 0.04, 32)
    lfo(b, "lfo_y", 0.025, 64)
    return mk(b, mirrorTOP, "mirror", src, flipx="=int(parent().par.Mode) in (0, 2)", flipy="=int(parent().par.Mode) in (1, 2)",
              pivotunit="fraction", pivotx="=0.5 + 0.2 * op('lfo_x')[0]", pivoty="=0.5 + 0.2 * op('lfo_y')[0]")


def fx_chroma(b, src):
    lfo(b, "lfo", 0.08, 16)
    sh = "parent().par.Shift * (0.5 + 0.5 * op('lfo')[0])"
    left = mk(b, transformTOP, "left", src, tx=f"=-{sh}", extend="mirror")
    right = mk(b, transformTOP, "right", src, tx=f"={sh}", extend="mirror")

    def only(name, s, keep):  # output channel `keep` from its own input channel, the other two zero
        pars = {f"{c}{j}": (1 if (c == keep and j == i + 1) else 0)
                for i, c in enumerate(("red", "green", "blue")) for j in range(1, 4)}
        return mk(b, channelmixTOP, name, s, **pars)
    r = only("onlyr", left, "red")
    g = only("onlyg", src, "green")
    bl = only("onlyb", right, "blue")
    return mk(b, compositeTOP, "add", r, g, bl, operand="add")


BUILDERS = {n: globals()["fx_" + n] for n in CORPUS}
WET_IS_OUTPUT = {"feedback", "echo"}  # stateful: their own cross at 0 instead of a switch


def build_effect(chain, name):
    b = chain.create(baseCOMP, name)
    pars = {k: default_for(spec) for k, spec in CORPUS[name]["params"].items()}
    custom(b, "Fx", Enable=False, **pars)
    src = mk(b, inTOP, "in1")
    wet = BUILDERS[name](b, src)
    if name in WET_IS_OUTPUT:
        last = wet
    else:
        last = mk(b, switchTOP, "sw", src, wet, index="=int(parent().par.Enable)")
    mk(b, outTOP, "out1", last)
    return b


# ---------------------------------------------------------------- transitions
def build_xfade(fx, g):
    x = fx.create(baseCOMP, "xfade_" + g)
    custom(x, "Xfade", Progress=0.0, Type=0, Active=False)
    cur = mk(x, inTOP, "cur")
    nxt = mk(x, inTOP, "nxt")
    mk(x, textDAT, "glsl_src", file=GLSL, syncfile=True)  # synced like the sequencer, so shader edits land live
    glsl = mk(x, glslTOP, "glsl", cur, nxt, pixeldat="glsl_src",
              uniname0="uProgress", value0x="=parent().par.Progress", uniname1="uType", value1x="=parent().par.Type")
    # smear: the outgoing picture feeds back and dissolves under the incoming one
    smear_out = mk(x, nullTOP, "smear_out")
    fb = mk(x, feedbackTOP, "smear_fb", cur, top="smear_out")
    z = mk(x, transformTOP, "smear_zoom", fb, sx=1.015, sy=1.015)
    d = mk(x, levelTOP, "smear_decay", z, brightness1=0.94)
    base = mk(x, crossTOP, "smear_base", cur, d, cross="=parent().par.Progress")
    smear = mk(x, crossTOP, "smear_mix", base, nxt, cross="=min(1, max(0, parent().par.Progress * parent().par.Progress * (3 - 2 * parent().par.Progress)))")
    wire(smear_out, smear)
    # Types 0 to 2 are the shader, 3 the smear; outside a transition the raw current picture
    sel = mk(x, switchTOP, "type", glsl, glsl, glsl, smear_out, index="=int(parent().par.Type)")
    live = mk(x, switchTOP, "live", cur, sel, index="=int(parent().par.Active)")
    mk(x, outTOP, "out1", live)
    return x


# ---------------------------------------------------------------- the build
def build():
    proj = op("/project1")
    old = proj.op("fx")
    if old:
        old.destroy()
    fx = proj.create(baseCOMP, "fx")
    fx.nodeX, fx.nodeY = 0, -600
    custom(fx, "Fx", Ceiling=0.18, Brightmean=ns["DEFAULTS"]["bright_mean"], Brighthigh=ns["DEFAULTS"]["bright_high"],
           Cap=120.0, Rerollevery=20.0, Seed=0, Roomdark=0.0, Roomcontrast=1.0,  # the room ones: set on site, see room.glsl
           Beatsync=False, Beatoffset=0.0, Beatbounce=0.03, Bpm=0.0)  # spec 002; Bpm is a readout
    fx.par.Cap.normMax, fx.par.Rerollevery.normMax = 300.0, 120.0  # the sliders' reach; a custom float runs 0 to 1 otherwise
    fx.par.Roomdark.normMax = 2.0
    fx.par.Roomcontrast.normMin, fx.par.Roomcontrast.normMax = 1.0, 3.0
    fx.par.Beatoffset.normMin, fx.par.Beatoffset.normMax = -0.5, 0.5
    fx.par.Beatbounce.normMax = 0.1
    fx.par.Bpm.normMax = 200.0
    dk = next(pg for pg in fx.customPages if pg.name == "Fx").appendMenu("Darkness", label="Darkness (sets Ceiling and the bright thresholds)")[0]
    dk.menuNames = list(ns["DARKNESS"])
    dk.menuLabels = dk.menuNames
    dk.default = dk.val = "default"
    bs = next(pg for pg in fx.customPages if pg.name == "Fx").appendMenu("Beatsource", label="Beatsource (what the tracker hears)")[0]
    bs.menuNames = ["mic", "system"]
    bs.menuLabels = ["mic", "system audio"]
    bs.default = bs.val = "mic"
    # the Try page: hold the random choosing and step through effects by hand
    tp = fx.appendCustomPage("Try")
    tp.appendToggle("Hold", label="Hold (no random choosing)")
    eff = tp.appendMenu("Effect", label="Effect")[0]
    eff.menuNames = ORDER
    eff.menuLabels = ORDER
    tp.appendPulse("Preveffect", label="Prev effect")
    tp.appendPulse("Nexteffect", label="Next effect")
    tp.appendPulse("Reroll", label="Reroll values")
    xt = tp.appendMenu("Xfadetype", label="Transition")[0]
    xt.menuNames = ["random", "burn", "distort", "colour", "smear"]
    xt.menuLabels = xt.menuNames
    for name, text in HELP.items():  # shown on hover over the parameter's name
        getattr(fx.par, name).help = text

    seq = mk(fx, textDAT, "sequencer", file=SEQ, syncfile=True)

    players = {}
    for name in ("A", "B", "C"):  # C is the spice, a third clip that drops in now and then
        # sequential: play and cue mean something; the default follows the 20 s timeline loop
        players[name] = mk(fx, moviefileinTOP, "player" + name, playmode="sequential", play=False, interp=True,
                           prereadframes=60, cuepointunit="seconds", hwdecode=False)

    # the spice: its own chain over player C, a small wander, crossed over each group before the limiter
    fitC = mk(fx, fitTOP, "fitC", players["C"], fit="fitoutside", outputresolution="custom", resolutionw=W, resolutionh=H)
    chainC = fx.create(baseCOMP, "chainC")
    prev = mk(chainC, inTOP, "in1")
    for name in ORDER:
        b = build_effect(chainC, name)
        wire(b, prev)
        prev = b
    mk(chainC, outTOP, "out1", prev)
    wire(chainC, fitC)
    drift = mk(fx, transformTOP, "spice_drift", chainC, extend="mirror",
               tx="=op('/project1/fx/sequencer').module.spice_drift('x')", ty="=op('/project1/fx/sequencer').module.spice_drift('y')")
    mk(fx, textDAT, "spice_glsl", file=GLSL, syncfile=True)  # the transition shader again: a spice pulses in through it
    mk(fx, textDAT, "room_glsl", file=ROOM_GLSL, syncfile=True)

    for g in STRIPS:
        # two chain slots per group, each fed by either player through src: a transition melds
        # the shown slot into the other, for a new clip or a new look on the same clip. Only
        # the slot the Switches pull cooks, so outside a transition one chain per group runs
        # the strip's window on the clip, two schemes crossed on zoomlag_g: close (the clip covers
        # the strip, as the file always did) and wide (the clip first covers a WIDE_FRAME x 1080
        # frame, which brings a portrait clip about 1.8 times closer; a landscape clip looks the
        # same both ways). The sequencer gives the two groups different schemes at each clip change. Either
        # way the clip is shifted sideways by the group's pan (picked per clip change, lagged) plus
        # a slow drift, so the two groups show different parts of the same clip and wander at
        # different rates; past the clip's edge the shift mirrors, so there is never black
        pan = mk(fx, constantCHOP, "pan_" + g, value0=0.0)
        mk(fx, lagCHOP, "panlag_" + g, pan, lag1=4.0, lag2=4.0)
        lfo(fx, "lfo_pan_" + g, *PAN_LFO[g])
        zoom = mk(fx, constantCHOP, "zoom_" + g, value0=0.0)
        mk(fx, lagCHOP, "zoomlag_" + g, zoom, lag1=4.0, lag2=4.0)
        shift = f"=op('/project1/fx/panlag_{g}')[0] + {PAN_DRIFT} * op('/project1/fx/lfo_pan_{g}')[0]"
        fits = []
        for p in "AB":
            close = mk(fx, transformTOP, f"pan{p}_{g}", players[p], extend="mirror", tx=shift)
            close = mk(fx, fitTOP, f"fit{p}_{g}", close, fit="fitoutside", outputresolution="custom", resolutionw=W, resolutionh=H)
            wide = mk(fx, fitTOP, f"frame{p}_{g}", players[p], fit="fitoutside", outputresolution="custom", resolutionw=WIDE_FRAME, resolutionh=H)
            wide = mk(fx, transformTOP, f"wpan{p}_{g}", wide, extend="mirror", tx=shift)
            wide = mk(fx, fitTOP, f"wfit{p}_{g}", wide, fit="fitoutside", outputresolution="custom", resolutionw=W, resolutionh=H)
            fits.append(mk(fx, crossTOP, f"win{p}_{g}", close, wide, cross=f"=op('/project1/fx/zoomlag_{g}')[0]"))
        chains = {}
        for slot in (1, 2):
            src = mk(fx, switchTOP, f"src{slot}_{g}", *fits, index=0)
            chain = fx.create(baseCOMP, f"chain{slot}_{g}")
            prev = mk(chain, inTOP, "in1")
            for name in ORDER:
                b = build_effect(chain, name)
                wire(b, prev)
                prev = b
            mk(chain, outTOP, "out1", prev)
            wire(chain, src)
            chains[slot] = chain
        cur = mk(fx, switchTOP, "cur_" + g, chains[1], chains[2], index=0)
        nxt = mk(fx, switchTOP, "nxt_" + g, chains[1], chains[2], index=1)
        x = build_xfade(fx, g)
        wire(x, cur, nxt)
        # the limiter: feedforward from a small mono copy, one-sided, fast down and slow up
        chain = fx.create(baseCOMP, "limiter_" + g)
        prev = mk(chain, inTOP, "in1")
        mono = mk(chain, monochromeTOP, "lim_mono", prev)
        small = mk(chain, fitTOP, "lim_small", mono, fit="fitoutside", outputresolution="custom", resolutionw=40, resolutionh=40)
        an = mk(chain, analyzeTOP, "lim_avg", small)
        tc = mk(chain, toptoCHOP, "lim_val", top="lim_avg", crop="pixel", uvunits="pixel")
        ex = mk(chain, expressionCHOP, "lim_gain", tc, expr0="=min(1.0, op('/project1/fx').par.Ceiling / max(me.inputVal, 0.001))")
        lag = mk(chain, lagCHOP, "lim_lag", ex, lag1=0.5, lag2=0.05)
        lv = mk(chain, levelTOP, "lim_level", prev, brightness1="=op('lim_lag')[0]")
        mk(chain, outTOP, "out1", lv)
        spice = mk(fx, glslTOP, "spice_" + g, x, drift, pixeldat="spice_glsl",
                   uniname0="uProgress", value0x=f"=op('/project1/fx/sequencer').module.spice_level('{g}')",
                   uniname1="uType", value1x="=op('/project1/fx/sequencer').module.spice_type()")
        spicesw = mk(fx, switchTOP, "spicesw_" + g, x, spice, index="=op('/project1/fx/sequencer').module.spice_on()")
        wire(chain, spicesw)
        room = mk(fx, glslTOP, "room_" + g, chain, pixeldat="room_glsl",
                  uniname0="uDark", value0x="=op('/project1/fx').par.Roomdark", uniname1="uContrast", value1x="=op('/project1/fx').par.Roomcontrast")
        bounce = mk(fx, transformTOP, "bounce_" + g, room, extend="mirror",
                    sx="=1 + op('/project1/fx').par.Beatbounce * op('/project1/fx/sequencer').module.beat_pulse()",
                    sy="=1 + op('/project1/fx').par.Beatbounce * op('/project1/fx/sequencer').module.beat_pulse()")
        out = mk(fx, nullTOP, "out_" + g, bounce)
        # how each strip hangs: at each clip change the sequencer draws, per pair and per axis, a
        # coin, and on heads one strip of the pair (drawn at random) turns, upside down
        # (flip_tgt_gN) or left for right (mirror_tgt_gN), while the other stays, so the pair
        # mirrors across the wall; both blended in over the transition so there is never a cut
        # (owner, 2026-11-10). Kantan's own flip and orientation flags stay off.
        for n in (1, 2):
            tgt = mk(fx, constantCHOP, f"flip_tgt_{g}{n}", value0=0.0)
            mk(fx, lagCHOP, f"flip_lag_{g}{n}", tgt, lag1=3.0, lag2=3.0)
            upside = mk(fx, flipTOP, f"flip_y_{g}{n}", out, flipy=True)
            hung = mk(fx, crossTOP, f"upside_{g}{n}", out, upside, cross=f"=op('/project1/fx/flip_lag_{g}{n}')[0]")
            mtgt = mk(fx, constantCHOP, f"mirror_tgt_{g}{n}", value0=0.0)
            mk(fx, lagCHOP, f"mirror_lag_{g}{n}", mtgt, lag1=3.0, lag2=3.0)
            mirrored = mk(fx, flipTOP, f"flip_x_{g}{n}", hung, flipx=True)
            mk(fx, crossTOP, f"orient_{g}{n}", hung, mirrored, cross=f"=op('/project1/fx/mirror_lag_{g}{n}')[0]")

    # timers: one per event, in seconds, all sharing one callbacks DAT
    cb = mk(fx, textDAT, "timers_callbacks")
    cb.text = (
        "def onDone(timerOp, segment, interrupt):\n"
        "    op('sequencer').module.on_done(timerOp.name)\n"
        "    return\n\n"
        "def onCycle(timerOp, segment, cycle):\n"
        "    op('sequencer').module.on_reroll()\n"
        "    return\n"
    )
    for name in ("t_turn", "t_preroll", "t_inner", "t_outer", "tx_inner", "tx_outer", "t_spice", "t_spicewait"):
        mk(fx, timerCHOP, name, lengthunits="seconds", length=10, callbacks="timers_callbacks")
    mk(fx, timerCHOP, "t_reroll", lengthunits="seconds", length=20, cycle=True, cyclelimit=False, callbacks="timers_callbacks")
    for g in STRIPS:
        # a relative path on a COMP's own parameter resolves from its parent, so absolute
        setp(fx.op("xfade_" + g), Progress=f"=op('/project1/fx/sequencer').module.progress(op('/project1/fx/tx_{g}')['timer_fraction'])")

    # the beat tracker (beat/beat_osc.py) sends /beat bpm kind here, and /hello when it starts;
    # osc_out answers with /source, the Beatsource menu, also sent whenever that changes
    bi = mk(fx, oscinDAT, "beat_in", port=7400, callbacks="beat_in_callbacks")
    bc = mk(fx, textDAT, "beat_in_callbacks")
    bc.text = ("def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):\n"
               "    if address == '/beat' and len(args) >= 2:\n"
               "        op('sequencer').module.on_beat(args[0], args[1])\n"
               "    elif address == '/hello':\n"
               "        op('sequencer').module.send_source()\n"
               "    return\n")
    mk(fx, oscoutDAT, "osc_out", address="127.0.0.1", port=7401)

    ex = mk(fx, executeDAT, "run", start=True)
    ex.text = "def onStart():\n    op('sequencer').module.start()\n    return\n"

    # the Try page's controls reach the sequencer through a Parameter Execute DAT
    px = mk(fx, parameterexecuteDAT, "try_pars", op="..", pars="Darkness Beatsource Hold Effect Preveffect Nexteffect Reroll Xfadetype",
            valuechange=True, onpulse=True)
    px.text = (
        "def onValueChange(par, prev):\n"
        "    op('sequencer').module.on_try(par.name)\n"
        "    return\n\n"
        "def onPulse(par):\n"
        "    op('sequencer').module.on_try(par.name)\n"
        "    return\n"
    )

    # the mapper: four textures, one dangling reference cleared
    shapes = "/project1/kantanMapper1/project/allShapes/"
    for g, items in STRIPS.items():
        for n, it in enumerate(items, 1):
            p = op(shapes + it + "/parameters").par
            p.Fliptexture, p.Textureorientation = False, 0  # the flips live in fx now: orient_gN
            p.Texture = f"/project1/fx/orient_{g}{n}"
    op(shapes + "item6/parameters").par.Texture = ""

    # the old chain, gone in one step now that the new one is wired
    for name in ("folderRaw", "folderRaw1", "folder", "folder1", "folder1_callbacks", "folder2_callbacks", "shuffled",
                 "shuffled1", "script1", "script1_callbacks", "select1", "playlist", "reorder1", "playlist_index",
                 "remaining", "info", "select2", "math2", "speed", "chopto1", "touchout1", "touchin1", "datto1", "reset",
                 "reset_index", "movie", "switch2", "moviefilein2", "fit2", "button1", "mood_logo", "moviefilein1",
                 "fit", "fit1", "diff", "diff1", "analyze1", "analyze2", "topto1", "topto2", "math1", "math3", "invert",
                 "invert1", "switch", "switch1", "white", "movie_null"):
        o = proj.op(name)
        if o:
            o.destroy()

    seq.module.start()
    print("fx built;", len(misses), "parameter misses")
    for m in misses:
        print("  ", m)


build()
