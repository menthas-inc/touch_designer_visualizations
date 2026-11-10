"""What plays next, for how long, and which effects: the decisions, then thin TouchDesigner glue.

The pure layer has no TouchDesigner names at module level, so tests import it as a module. In
TouchDesigner the file is synced into the Text DAT /project1/fx/sequencer and the timers'
callbacks reach it through op('sequencer').module. Mutable state lives in the fx container's
storage, not in this module, so a re-sync of the file mid-show loses nothing.
"""
import colorsys
import json
import math
import os
import random

# ---------------------------------------------------------------- the corpus
# One place for every effect, read by build_fx.py (to create the custom pars) and by choose().
# family: frame (always on), dark (darkeners), treat (treatments). stateful effects keep cooking
# behind a Cross at 0 instead of a Switch, and are only re-rolled at a transition.
CORPUS = {
    "framing":    {"family": "frame", "params": {"Zoom": (1.0, 1.35), "Tx": (-0.15, 0.15), "Ty": (-0.15, 0.15), "Flipx": [0, 1], "Flipy": [0, 1],
                                                 "Rotate": [0, 0, 0, 0, 180, 180, -12, -7, 7, 12, 173, 187]}},
    "highlights": {"family": "dark", "params": {"Cut": (0.85, 0.6), "Soft": (12.0, 4.0), "Amount": (0.5, 1.0)}},
    "crush":      {"family": "dark", "params": {"Gamma": (0.7, 0.4), "Black": (0.0, 0.2)}},  # Level TOP gamma over 1 brightens
    "edges":      {"family": "dark", "params": {"Strength": (0.8, 2.0), "Mix": (0.6, 1.0)}},
    "tint":       {"family": "dark", "params": {"Hue": (0.0, 1.0), "Sat": (0.8, 1.0)}},
    "selfmask":   {"family": "dark", "params": {"Amount": (0.6, 1.0), "Contrast": (1.3, 2.0), "Sat": (1.2, 1.8)}},
    "feedback":   {"family": "treat", "stateful": True, "params": {"Zoom": (0.95, 1.06), "Rotate": (-3.0, 3.0), "Decay": (0.9, 0.98), "Mix": (0.5, 0.8)}},
    "displace":   {"family": "treat", "params": {"Amount": (0.03, 0.1), "Speed": (0.01, 0.06), "Scale": (5.0, 14.0)}},
    "echo":       {"family": "treat", "stateful": True, "params": {"Frames": [12, 20, 30, 45, 60], "Mix": (0.4, 0.7)}},
    "mirror":     {"family": "treat", "params": {"Mode": [0, 1, 2]}},
    "chroma":     {"family": "treat", "params": {"Shift": (0.01, 0.06)}},
}
# Dropped after the owner stepped through them on 2026-11-03: pixelate, slope (both read as grey),
# keepchannel.
ORDER = list(CORPUS)  # the chain order, fixed: part of the look and makes a selection reproducible
OFF = {"tint", "mirror"}  # built and on the Try page, never drawn (owner, 2026-11-10; mirror folds the strip about its centre)
DARK = [n for n, e in CORPUS.items() if e["family"] == "dark" and n not in OFF]
TREAT = [n for n, e in CORPUS.items() if e["family"] == "treat" and n not in OFF]
XFADE_TYPES = 4  # burn, distort, colour, smear
PLAIN = 0.8  # per group on a dark clip: the clip as it is, both groups may be

DEFAULTS = {"cap": 120.0, "bright_mean": 0.33, "bright_high": 0.65}  # thresholds: about the 60th percentile of the measured buckets
# the Darkness macro: Ceiling for the limiter, the bright thresholds that bring darkeners in,
# how far the darkeners' draws are pushed to the dark end of their ranges, and the Cut range
# of a highlights cut forced on every clip (None: not forced). The upper levels remove bright
# patches rather than dim the whole picture, so the ceiling stays
DARKNESS = {"none": (1.0, 2.0, 2.0, 0.0, None), "default": (0.18, 0.33, 0.65, 0.0, None),
            "darker": (0.18, 0.33, 0.65, 0.5, (0.75, 0.55)), "darkest": (0.18, 0.33, 0.65, 0.85, (0.5, 0.3))}
BUCKET = 10.0
LONG_DIR = "VJ_Visuals/Long/"
FLOOR = 6.0  # seconds of plain play before the inner transition: the time the next clip has to cue
PREROLL = 1.0
XFADE = (7.5, 22.5)  # seconds a clip change transition takes
SWAP = (6.0, 12.0)  # seconds a mid-clip look swap takes
KNEE = 1.0 / 3.0  # the first half of a meld happens in this share of its time, the rest is slower


def progress(fraction):
    """Transition progress 0 to 1 from the timer's fraction: quick to half way, then half speed."""
    f = min(max(fraction, 0.0), 1.0)
    return 0.5 * f / KNEE if f < KNEE else 0.5 + 0.5 * (f - KNEE) / (1.0 - KNEE)
SWAP_CHANCE = 0.3  # per reroll tick, for the one group whose turn it is
UPSIDE_CHANCE = 0.5  # per clip change and group, that one strip of the pair, drawn at random, hangs upside down
MIRROR_CHANCE = 0.5  # per clip change and group, that one strip of the pair, drawn at random, has left for right
PAN_REACH = 0.3  # of the frame width, how far from the centre a group's window may sit
PAN_APART = 0.2  # of the frame width, the least distance between the two groups' windows


def pick_pan(rng, other):
    """Where a group's window sits on the frame, away from the other group's. Pure."""
    for _ in range(50):
        pan = round(rng.uniform(-PAN_REACH, PAN_REACH), 3)
        if other is None or abs(pan - other) >= PAN_APART:
            return pan
    return -PAN_REACH if other > 0 else PAN_REACH
# the spice: a third clip that drops in over one pair or both, pulses, and leaves
SPICE_GAP = (28.0, 84.0)  # seconds between spices
SPICE_IN = (8.0, 16.0)  # seconds of swells coming in
SPICE_HOLD = (10.0, 20.0)  # seconds fully on
SPICE_OUT = (6.0, 12.0)  # seconds of swells going out
SPICE_PULSES = (2, 4)  # swells coming in, the last being the takeover itself: 1 to 3 before it (owner, 2026-11-10); going out, half
SPICE_MIN_CLIP = 30.0  # seconds; a spice clip must outlast the spice at its speed
SPICE_WHERE = ["outer", "inner", "outer", "inner", "both"]


BEAT_HOLD = 3.0  # seconds without a beat before the chain goes back to its free rates
BEAT_BOUNCE_DECAY = 0.12  # seconds, the bounce's settle
REROLL_BEATS = 32  # the reroll tick when synced, in beats


def beat_phase_of(now, t, bpm, offset):
    """0 to 1 through the current beat, given the last beat's time and the tracker's lag. Pure.
    A positive offset says the tracker was late by that much, so the beat was earlier."""
    return ((now - t + offset) * bpm / 60.0) % 1.0


def lfo_rate_of(free, beats, bpm):
    """One cycle per `beats` beats when bpm is known, else the free rate. Pure."""
    return bpm / 60.0 / beats if bpm else free


SPICE_ACCEL = 1.0  # the swells come e^this times faster at the end of a phase than at its start; negative spreads them out


def _swell(f, pulses, beats):
    """0.1 to 1, `pulses` swells over f 0 to 1, spacing changing exponentially, 1 at both ends;
    or, given beats elapsed, one swell every two bars."""
    phase = beats / 8.0 if beats is not None else (pulses - 1) * (math.exp(SPICE_ACCEL * f) - 1.0) / (math.exp(SPICE_ACCEL) - 1.0)
    return 0.55 + 0.45 * math.cos(2 * math.pi * phase)


def spice_env(t, parts, pulses, beats=None):
    """The spice's level t seconds in. parts is (in, hold, out) in seconds: swells rising to
    full over the first, fully on through the second, swells falling away over the third.
    beats, when known, is beats elapsed in the current part. Pure."""
    a, h, o = parts
    if t < a:
        f = t / a
        return f ** 0.7 * _swell(f, pulses, beats)
    if t < a + h:
        return 1.0
    f = min(max((t - a - h) / o, 0.0), 1.0)
    return (1.0 - f) ** 0.7 * _swell(f, max(2, pulses // 2), beats)


def spice_part(t, parts):
    """Which part t falls in, 0 1 2, and when that part began. Pure."""
    a, h, _ = parts
    return (0, 0.0) if t < a else (1, a) if t < a + h else (2, a + h)
SHORT = 45.0  # clips under this play twice, to last longer


def _draw(rng, spec, bias=0.0):
    """A value from the range; dark ranges run light to dark, bias narrows the draw to the dark end."""
    if isinstance(spec, list):
        return rng.choice(spec)
    lo, hi = spec
    return round(rng.uniform(lo + bias * (hi - lo), hi), 4)


def params_for(name, rng, bias=0.0):
    return {k: _draw(rng, spec, 0.0 if k == "Hue" else bias) for k, spec in CORPUS[name]["params"].items()}


def hsv_rgb(h, s, v=0.9):
    return colorsys.hsv_to_rgb(h % 1.0, s, v)


# ---------------------------------------------------------------- the playlist
class Playlist:
    """Shuffled, short clips twice (anything outside Long/), never the same clip twice running.

    State is the plain dict passed in ({"queue": [...], "last": ...}), mutated in place, so the
    caller can keep it in TouchDesigner storage.
    """

    def __init__(self, paths, rng, state=None):
        self.rng = rng
        self.paths = list(paths)
        self.state = state if state is not None else {}
        self.state.setdefault("queue", [])
        self.state.setdefault("last", None)

    def _refill(self):
        # Draw from the remaining counts, never the clip just played, the fullest pile first so
        # the doubled short clips cannot be left to collide at the end.
        left = {p: (1 if p.startswith(LONG_DIR) else 2) for p in self.paths}
        q, last = [], self.state["last"]
        while any(left.values()):
            top = max(n for p, n in left.items() if p != last) if len(left) > 1 else max(left.values())
            pick = self.rng.choice([p for p, n in left.items() if n == top and (p != last or len(left) == 1)])
            q.append(pick)
            left[pick] -= 1
            if left[pick] == 0:
                del left[pick]
            last = pick
        self.state["queue"] = q

    def next(self):
        # a clip dropped from the table since the queue was drawn is skipped, its file may be gone
        self.state["queue"] = [p for p in self.state["queue"] if p in self.paths]
        if not self.state["queue"]:
            self._refill()
        self.state["last"] = self.state["queue"].pop(0)
        return self.state["last"]


# ---------------------------------------------------------------- one segment
def plan_segment(clip, rng, cap=DEFAULTS["cap"], lead=0.0):
    """Where in the clip, how long, the tease, the transition, the speed.

    clip is the clips.json entry or None. lead is how long this clip has already played when
    it becomes both groups' picture (the previous change's tease plus transition), so the
    window is measured from the cue point and the plain play before the next change is
    length - tease - xfade. Clamped so that plain play >= FLOOR, by shrinking the tease, then
    the transition.
    """
    fps = clip["fps"] if clip else 30.0
    motion = clip["motion"] if clip else 0.0
    if fps < 25:
        speed = 0.6  # slowing a low frame rate clip stutters
    elif motion >= 0.12:
        speed = 0.4
    elif motion >= 0.08:
        speed = 0.5
    else:
        speed = 0.6
    # window, length, tease, xfade and turn are real seconds; start is a clip time
    total = clip["length"] if clip else cap
    if total < SHORT:
        start, turn = 0.0, round(total / speed, 2)  # the end of the first pass
        window = min(2 * turn, cap)
    else:
        content = min(total, cap * speed)
        start = round(rng.uniform(0.0, total - content), 2)
        window, turn = content / speed, None
    length = round(max(window - lead, 0.0), 2)
    tease = 0.0 if rng.random() < 0.3 else round(rng.uniform(8.0, 20.0), 2)  # instant three times in ten
    xfade = round(rng.uniform(*XFADE), 2)
    if length - tease - xfade < FLOOR:
        tease = max(0.0, round(length - xfade - FLOOR, 2))
        if tease < 1.0:
            tease = 0.0  # a tease under a second is a glitch, not a tease
    if length - xfade < FLOOR:
        xfade = max(0.3, round(length - FLOOR, 2))
    return {"start": start, "window": round(window, 2), "length": length, "tease": tease, "xfade": xfade,
            "speed": speed, "turn": turn}


def window_stats(clip, start, length):
    """Mean and high luma over the buckets under the window. A missing clip is bright."""
    if not clip or not clip.get("buckets"):
        return {"mean": 1.0, "high": 1.0}
    b = clip["buckets"]
    first = min(int(start // BUCKET), len(b) - 1)
    last = min(int(max(start + length - 0.01, start) // BUCKET), len(b) - 1)
    used = b[first:last + 1]
    return {"mean": sum(x["mean"] for x in used) / len(used), "high": max(x["high"] for x in used)}


def is_bright(stats, bright_mean=DEFAULTS["bright_mean"], bright_high=DEFAULTS["bright_high"]):
    return stats["high"] >= bright_high or stats["mean"] >= bright_mean


def enabled(selection):
    return frozenset(n for n, v in selection.items() if v.get("Enable"))


def choose(stats, rng, avoid=(), bias=0.0, cut=None, **thresholds):
    """A selection: {effect: {"Enable": 0|1, params...}} for every effect in the corpus.

    avoid is a list of selections whose enabled set this one must differ from: the group's
    previous one and the other group's current one.
    """
    taken = {enabled(a) for a in avoid if a}
    for _ in range(20):
        sel = {n: {"Enable": 0} for n in CORPUS}
        sel["framing"] = {"Enable": 1, **params_for("framing", rng)}
        if is_bright(stats, **thresholds):
            picks = rng.sample(DARK, rng.choice([1, 2]))
            if rng.random() < 0.5:
                picks += rng.sample(TREAT, 1)
        elif rng.random() < PLAIN:
            picks = []  # plain is always allowed, so avoid does not force an effect on
        else:
            picks = rng.sample(TREAT, rng.choice([1, 2]))
        for n in picks:
            sel[n] = {"Enable": 1, **params_for(n, rng, bias if n in DARK else 0.0)}
        if cut:  # bright patches above Cut go black, on every clip
            sel["highlights"] = {"Enable": 1, **params_for("highlights", rng, bias), "Cut": _draw(rng, cut, bias), "Amount": 1.0}
        if not picks or enabled(sel) not in taken:
            return sel
    spare = next(n for n in TREAT if n not in enabled(sel))  # twenty collisions: force a difference
    sel[spare] = {"Enable": 1, **params_for(spare, rng)}
    return sel


def load_table(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- TouchDesigner glue
# Everything below touches op() and pars. State is a plain dict in the fx container's storage.
GROUPS = ("outer", "inner")
OTHER = {"A": "B", "B": "A"}


def _fx():
    return op("/project1/fx")


def _state():
    fx = _fx()
    st = fx.fetch("state", None)
    if st is None:
        seed = int(fx.par.Seed) or None
        st = {"seed": seed, "rng": None, "playlist": {}, "player": "A", "clip": {}, "plan": {}, "sel": {}, "lead": 0.0}
        fx.store("state", st)
    return st


def _rng(st):
    if st.get("rng") is None:
        st["rng"] = random.Random(st.get("seed"))
    return st["rng"]


def _table():
    return load_table(os.path.join(project.folder, "..", "td", "clips.json"))


def _apply(group, slot, sel):
    """Two chain slots per group, so a transition melds the old look into the new."""
    _apply_chain(_fx().op(f"chain{slot}_{group}"), sel)


def _apply_chain(chain, sel):
    for name, vals in sel.items():
        b = chain.op(name)
        for k, v in vals.items():
            getattr(b.par, k).val = v
    chain.op("feedback/fb").par.resetpulse.pulse()  # the idle chain's loop holds a stale frame


# ---------------------------------------------------------------- hold mode: step through by hand
NEUTRAL_FRAMING = {"Enable": 1, "Zoom": 1.0, "Tx": 0.0, "Ty": 0.0, "Flipx": 0, "Flipy": 0, "Rotate": 0}


def held_selection(name, params):
    """Only `name` on, with `params`, over a neutral framing. Pure."""
    sel = {n: {"Enable": 0} for n in CORPUS}
    sel["framing"] = dict(NEUTRAL_FRAMING)
    sel[name] = {"Enable": 1, **params}
    if name == "framing":
        sel["framing"] = {"Enable": 1, **params}
    return sel


def _hold_apply(st, name=None, fresh=False):
    fx = _fx()
    held = st.setdefault("held", {})
    name = name or held.get("name") or ORDER[1]
    if fresh or held.get("name") != name:
        held["name"] = name
        held["params"] = params_for(name, _rng(st))
    sel = held_selection(name, held["params"])
    for g in GROUPS:
        st["sel"][g] = sel
        for slot in (1, 2):
            _apply(g, slot, sel)
    fx.par.Effect = name
    print("try:", name, "  ".join(f"{k} {v}" for k, v in held["params"].items()))


def on_try(par_name):
    """A control on the Try page changed."""
    st = _state()
    fx = _fx()
    if par_name == "Darkness":
        fx.par.Ceiling, fx.par.Brightmean, fx.par.Brighthigh = DARKNESS[str(fx.par.Darkness)][:3]
        return
    if par_name == "Hold":
        if fx.par.Hold:
            _hold_apply(st, str(fx.par.Effect))
        return
    if not fx.par.Hold:
        return
    if par_name == "Effect":
        _hold_apply(st, str(fx.par.Effect))
    elif par_name in ("Nexteffect", "Preveffect"):
        i = ORDER.index(st.get("held", {}).get("name", ORDER[1]))
        step = 1 if par_name == "Nexteffect" else -1
        _hold_apply(st, ORDER[(i + step) % len(ORDER)])
    elif par_name == "Reroll":
        _hold_apply(st, fresh=True)


def _cue(player, key, plan):
    p = _fx().op("player" + player)
    p.par.file = os.path.join(project.folder, key)
    p.par.cuepoint = plan["start"]
    p.par.speed = plan["speed"]
    p.par.play = False
    p.par.cue = True
    p.par.cuepulse.pulse()


def _pick_next(st):
    rng = _rng(st)
    table = _table()
    pl = Playlist(sorted(table) if table else [], rng, st["playlist"])
    key = pl.next() if pl.paths else None
    nxt = OTHER[st["player"]]
    plan = plan_segment(table.get(key), rng, cap=float(_fx().par.Cap), lead=st["lead"])
    st["clip"][nxt] = key
    st["plan"][nxt] = plan
    if key:
        _cue(nxt, key, plan)
    return nxt


def _selection_for(st, player, group):
    """A look for `player`'s clip, unlike the group's own and the other group's."""
    rng = _rng(st)
    clip = _table().get(st["clip"].get(player))
    plan = st["plan"][player]
    stats = window_stats(clip, plan["start"], plan["window"])
    fx = _fx()
    level = DARKNESS[str(fx.par.Darkness)]
    avoid = [st["sel"].get(g) for g in GROUPS if g != group] + [st["sel"].get(group)]
    return choose(stats, rng, avoid=avoid, bias=level[3], cut=level[4],
                  bright_mean=float(fx.par.Brightmean), bright_high=float(fx.par.Brighthigh))


# ---------------------------------------------------------------- the spice
def _schedule_spice(st):
    """Cue a random clip into player C and start the wait for the next spice."""
    rng = _rng(st)
    table = _table()
    if not table:
        return
    keys = sorted(k for k in table if table[k]["length"] >= SPICE_MIN_CLIP) or sorted(table)
    key = rng.choice(keys)
    plan = plan_segment(table[key], rng, cap=SPICE_IN[1] + SPICE_HOLD[1] + SPICE_OUT[1])
    st["clip"]["C"], st["plan"]["C"] = key, plan
    _cue("C", key, plan)
    _timer("t_spicewait", rng.uniform(*SPICE_GAP))


def _start_spice(st):
    fx = _fx()
    rng = _rng(st)
    where = rng.choice(SPICE_WHERE)
    parts = tuple(round(rng.uniform(*r), 2) for r in (SPICE_IN, SPICE_HOLD, SPICE_OUT))
    st["spice"] = {"groups": GROUPS if where == "both" else [where], "pulses": rng.randint(*SPICE_PULSES),
                   "type": rng.randrange(XFADE_TYPES - 1), "t0": absTime.seconds, "parts": parts}  # a shader transition, not the smear
    st["sel"]["spice"] = _selection_for(st, "C", "spice")
    _apply_chain(fx.op("chainC"), st["sel"]["spice"])
    _release("C")
    print(f"spice on {where} -> {st['clip']['C']}  ({' + '.join(f'{x:.0f}' for x in parts)} s)")
    _timer("t_spice", sum(parts))


def _end_spice(st):
    _fx().op("playerC").par.play = False
    _schedule_spice(st)


def spice_level(group):
    """The spice's progress for a group, read every frame by spice_g's shader."""
    st = _state()
    sp = st.get("spice")
    if not sp or group not in sp["groups"]:
        return 0.0
    t = _fx().op("t_spice")["timer_fraction"] * sum(sp["parts"])
    beats = None
    if beat_phase() is not None:
        _, began = spice_part(t, sp["parts"])
        beats = (t - began) * st["beat"]["bpm"] / 60.0
    return spice_env(t, sp["parts"], sp["pulses"], beats)


# ---------------------------------------------------------------- the beat
def on_beat(bpm, kind):
    """A beat from the tracker, through beat_in's callbacks."""
    st = _state()
    b = st.setdefault("beat", {"t": 0.0, "bpm": 0.0, "n": 0})
    b["t"], b["bpm"], b["n"] = absTime.seconds, float(bpm), b["n"] + 1
    _fx().par.Bpm = round(float(bpm), 1)


def _beat(st):
    """The beat state when sync is on and a beat is fresh, else None."""
    fx = _fx()
    b = st.get("beat")
    if not fx.par.Beatsync or not b or not b["bpm"] or absTime.seconds - b["t"] > BEAT_HOLD:
        if b and fx.par.Bpm != 0 and absTime.seconds - b["t"] > BEAT_HOLD:
            fx.par.Bpm = 0
        return None
    return b


def beat_phase():
    """0 to 1 through the current beat, None when not synced. Read every frame."""
    b = _beat(_state())
    return None if b is None else beat_phase_of(absTime.seconds, b["t"], b["bpm"], float(_fx().par.Beatoffset))


def lfo_rate(free, beats):
    """An LFO's frequency: one cycle per `beats` beats when synced, else its free rate."""
    b = _beat(_state())
    return lfo_rate_of(free, beats, b["bpm"] if b else 0.0)


def beat_pulse():
    """1 on the beat, settling to 0 before the next; 0 when not synced. For the bounce."""
    b = _beat(_state())
    if b is None:
        return 0.0
    since = (absTime.seconds - b["t"] + float(_fx().par.Beatoffset)) % (60.0 / b["bpm"])
    return math.exp(-since / BEAT_BOUNCE_DECAY)


def reroll_seconds():
    b = _beat(_state())
    return REROLL_BEATS * 60.0 / b["bpm"] if b else float(_fx().par.Rerollevery)


def spice_type():
    sp = _state().get("spice")
    return sp["type"] if sp else 0


def spice_on():
    """1 while a spice shows on any group, so spicesw_g pulls the shader and chainC only then."""
    return int(any(spice_level(g) > 0.0 for g in GROUPS))


def spice_drift(axis):
    """A small wander of the spice picture over its life, read every frame by spice_drift."""
    f = _fx().op("t_spice")["timer_fraction"]
    return 0.06 * math.sin(2 * math.pi * f) if axis == "x" else 0.04 * math.sin(4 * math.pi * f + 1.0)


def _start_xfade(st, group, player, seconds):
    """The group melds from its shown chain slot into the other, carrying `player` with a new
    look: the next clip at a clip change, the same clip for a mid-clip swap."""
    fx = _fx()
    x = fx.op("xfade_" + group)
    if x.par.Active:
        _finish_xfade(st, group)  # a swap still running when the clip change comes
    if player != st["player"] and not fx.par.Hold:
        _roll_mirror(st, group, seconds)
        _roll_pan(st, group, seconds)
        print(f"{group} -> {st['clip'][player]}  (over {seconds:.0f} s)")
    slot = 3 - st["chain"][group]
    fx.op(f"src{slot}_{group}").par.index = 0 if player == "A" else 1
    if not fx.par.Hold:
        sel = _selection_for(st, player, group)
        st["sel"][group] = sel
        _apply(group, slot, sel)
    st["target"][group] = (slot, player)  # read back at the end, when roles may have swapped already
    forced = fx.par.Xfadetype.menuIndex  # 0 random, else the type plus one
    x.par.Type = (forced - 1) if forced else _rng(st).randrange(XFADE_TYPES)
    x.op("smear_fb").par.resetpulse.pulse()
    fx.op("nxt_" + group).par.index = slot - 1
    _release(player)  # normally already rolling from the pre-roll; harmless twice
    x.par.Active = 1
    t = fx.op("tx_" + group)
    t.par.length = seconds
    t.par.start.pulse()


def _roll_pan(st, group, seconds=4.0):
    """A new part of the frame for the group at a clip change, and the window scheme: the inner
    group draws close or wide, the outer takes the other. The lags ease both moves over the
    transition, so the move is part of the meld and not a shift before it."""
    fx = _fx()
    for lag in ("panlag_", "zoomlag_"):
        fx.op(lag + group).par.lag1 = fx.op(lag + group).par.lag2 = seconds
    other = GROUPS[1 - GROUPS.index(group)]
    fx.op("pan_" + group).par.value0 = pick_pan(_rng(st), float(fx.op("pan_" + other).par.value0))
    fx.op("zoom_" + group).par.value0 = float(_rng(st).randrange(2)) if group == "inner" else 1.0 - float(fx.op("zoom_inner").par.value0)


def _roll_mirror(st, group, seconds=3.0):
    """Per axis a coin: on heads one strip of the pair, drawn at random, turns (upside down, or
    left for right) and the other stays, so the pair mirrors across the wall; the lags blend
    both over the transition (owner, 2026-11-10)."""
    fx = _fx()
    rng = _rng(st)
    for name, chance in (("flip", UPSIDE_CHANCE), ("mirror", MIRROR_CHANCE)):
        turned = rng.choice((1, 2)) if rng.random() < chance else 0
        for n in (1, 2):
            lag = fx.op(f"{name}_lag_{group}{n}")
            lag.par.lag1 = lag.par.lag2 = seconds
            fx.op(f"{name}_tgt_{group}{n}").par.value0 = 1.0 if n == turned else 0.0


def _finish_xfade(st, group):
    """The transition is over: the group shows the slot it melded into."""
    fx = _fx()
    if group in st["target"]:
        slot, _ = st["target"][group]
        st["chain"][group] = slot
        fx.op("cur_" + group).par.index = slot - 1
    fx.op("xfade_" + group).par.Active = 0
    fx.op("tx_" + group).par.initialize.pulse()  # fraction back to 0, so the xfade shows cur


def _release(player):
    p = _fx().op("player" + player)
    p.par.cue = False
    p.par.play = True


def _timer(name, seconds):
    t = _fx().op(name)
    t.par.length = max(seconds, 0.05)
    t.par.start.pulse()


def start():
    """Called once from the Execute DAT's onStart and at the end of the build."""
    fx = _fx()
    fx.unstore("state")
    for name in ("t_preroll", "t_turn", "t_inner", "t_outer", "tx_inner", "tx_outer", "t_reroll", "t_spice", "t_spicewait"):
        fx.op(name).par.initialize.pulse()  # a timer saved mid run would fire into fresh state
    for g in GROUPS:
        fx.op("xfade_" + g).par.Active = 0
    st = _state()
    st["player"] = "B"  # so that _pick_next cues the first clip into A
    first = _pick_next(st)
    st["player"] = first
    st["lead"] = 0.0
    _release(first)
    st["chain"], st["target"] = {}, {}
    for g in GROUPS:
        st["chain"][g] = 1
        fx.op("cur_" + g).par.index = 0
        fx.op("src1_" + g).par.index = 0 if first == "A" else 1
        st["sel"][g] = None
    for g in GROUPS:
        st["sel"][g] = _selection_for(st, first, g)
        _apply(g, 1, st["sel"][g])
        _roll_mirror(st, g)
        _roll_pan(st, g)
    if fx.par.Hold:
        _hold_apply(st, str(fx.par.Effect))
    _begin_segment(st)
    _schedule_spice(st)


def _begin_segment(st):
    """Both groups show st['player']; cue the next clip and arm the timers."""
    fx = _fx()
    plan = st["plan"][st["player"]]
    _pick_next(st)
    L, T, t = plan["length"], plan["tease"], plan["xfade"]
    if plan["turn"] is None:
        fx.op("t_turn").par.initialize.pulse()  # cancel a turn armed by the segment before
    else:
        _timer("t_turn", plan["turn"] - st["lead"])
    _timer("t_preroll", L - T - t - PREROLL)
    _timer("t_inner", L - T - t)
    _timer("t_outer", L - t)
    r = fx.op("t_reroll")
    r.par.length = reroll_seconds()
    r.par.start.pulse()


def on_done(timer_name):
    st = _state()
    fx = _fx()
    if timer_name == "t_preroll":
        _release(OTHER[st["player"]])
    elif timer_name == "t_spicewait":
        if not fx.par.Hold:
            _start_spice(st)
        else:
            _schedule_spice(st)
    elif timer_name == "t_spice":
        _end_spice(st)
    elif timer_name == "t_turn":
        fx.op("player" + st["player"]).par.cuepulse.pulse()  # a short clip reaches its end: again from the top
    elif timer_name in ("t_inner", "t_outer"):
        _start_xfade(st, timer_name[2:], OTHER[st["player"]], st["plan"][st["player"]]["xfade"])
    elif timer_name in ("tx_inner", "tx_outer"):
        g = timer_name[3:]
        # with no tease both transitions end in the same frame, and the outer one may have
        # swapped st["player"] already, so the target comes from the start of the transition
        _, nxt = st["target"].get(g, (None, st["player"]))
        _finish_xfade(st, g)
        if g == "outer" and st["player"] != nxt:
            plan = st["plan"][st["player"]]
            st["lead"] = plan["tease"] + plan["xfade"] + PREROLL
            st["player"] = nxt
            _begin_segment(st)


def on_reroll():
    """Every Rerollevery seconds one group, in turn, may swap to a new look mid clip, melded
    over SWAP seconds, unless its clip change is about to do that anyway."""
    st = _state()
    fx = _fx()
    if fx.par.Hold:
        return
    st["reroll_n"] = st.get("reroll_n", 0) + 1
    g = GROUPS[st["reroll_n"] % 2]
    rng = _rng(st)
    secs = round(rng.uniform(*SWAP), 2)
    if rng.random() >= SWAP_CHANCE or fx.op("xfade_" + g).par.Active:
        return
    t = fx.op("t_" + g)
    if float(t.par.length) * (1 - t["timer_fraction"]) < secs + 2:
        return
    _start_xfade(st, g, st["player"], secs)
