"""What plays next, for how long, and which effects: the decisions, then thin TouchDesigner glue.

The pure layer has no TouchDesigner names at module level, so tests import it as a module. In
TouchDesigner the file is synced into the Text DAT /project1/fx/sequencer and the timers'
callbacks reach it through op('sequencer').module. Mutable state lives in the fx container's
storage, not in this module, so a re-sync of the file mid-show loses nothing.
"""
import colorsys
import json
import os
import random

# ---------------------------------------------------------------- the corpus
# One place for every effect, read by build_fx.py (to create the custom pars) and by choose().
# family: frame (always on), dark (darkeners), treat (treatments). stateful effects keep cooking
# behind a Cross at 0 instead of a Switch, and are only re-rolled at a transition.
CORPUS = {
    "framing":    {"family": "frame", "params": {"Zoom": (1.0, 1.35), "Tx": (-0.15, 0.15), "Ty": (-0.15, 0.15), "Flipx": [0, 1], "Flipy": [0, 1]}},
    "keepchannel": {"family": "dark", "params": {"Mode": [0, 1, 2]}},
    "highlights": {"family": "dark", "params": {"Cut": (0.55, 0.8), "Soft": (2.0, 10.0)}},
    "crush":      {"family": "dark", "params": {"Gamma": (1.5, 2.6), "Black": (0.0, 0.2)}},
    "edges":      {"family": "dark", "params": {"Strength": (0.8, 2.0), "Mix": (0.6, 1.0)}},
    "tint":       {"family": "dark", "params": {"Hue": (0.0, 1.0), "Sat": (0.6, 1.0)}},
    "selfmask":   {"family": "dark", "params": {"Amount": (0.6, 1.0)}},
    "feedback":   {"family": "treat", "stateful": True, "params": {"Zoom": (0.99, 1.03), "Rotate": (-1.0, 1.0), "Decay": (0.85, 0.97), "Mix": (0.3, 0.6)}},
    "displace":   {"family": "treat", "params": {"Amount": (0.01, 0.06), "Speed": (0.05, 0.4), "Scale": (0.5, 3.0)}},
    "echo":       {"family": "treat", "stateful": True, "params": {"Frames": [4, 8, 12, 18, 24], "Mix": (0.3, 0.6)}},
    "mirror":     {"family": "treat", "params": {"Mode": [0, 1, 2]}},
    "pixelate":   {"family": "treat", "params": {"Cells": (24.0, 120.0)}},
    "slope":      {"family": "treat", "params": {"Mix": (0.4, 0.9)}},
    "chroma":     {"family": "treat", "params": {"Shift": (0.005, 0.03)}},
}
ORDER = list(CORPUS)  # the chain order, fixed: part of the look and makes a selection reproducible
DARK = [n for n, e in CORPUS.items() if e["family"] == "dark"]
TREAT = [n for n, e in CORPUS.items() if e["family"] == "treat"]
XFADE_TYPES = 3  # melt, displace, smear

DEFAULTS = {"cap": 60.0, "bright_mean": 0.33, "bright_high": 0.65}  # thresholds: about the 60th percentile of the measured buckets
BUCKET = 10.0
LONG_DIR = "VJ_Visuals/Long/"
FLOOR = 6.0  # seconds of plain play before the inner transition: the time the next clip has to cue


def _draw(rng, spec):
    if isinstance(spec, list):
        return rng.choice(spec)
    lo, hi = spec
    return round(rng.uniform(lo, hi), 4)


def params_for(name, rng):
    return {k: _draw(rng, spec) for k, spec in CORPUS[name]["params"].items()}


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
    total = clip["length"] if clip else cap
    window = min(total, cap)
    start = 0.0 if total <= cap else round(rng.uniform(0.0, total - cap), 2)
    length = round(max(window - lead, 0.0), 2)
    tease = round(rng.uniform(1.0, 6.0), 2) if rng.random() < 0.5 else 0.0
    xfade = round(rng.uniform(2.0, 3.0), 2)
    if length - tease - xfade < FLOOR:
        tease = max(0.0, round(length - xfade - FLOOR, 2))
        if tease < 1.0:
            tease = 0.0  # a tease under a second is a glitch, not a tease
    if length - xfade < FLOOR:
        xfade = max(0.3, round(length - FLOOR, 2))
    fps = clip["fps"] if clip else 30.0
    motion = clip["motion"] if clip else 0.0
    if fps < 25:
        speed = 0.75  # slowing a low frame rate clip stutters
    elif motion >= 0.12:
        speed = 0.65
    elif motion >= 0.08:
        speed = 0.70
    else:
        speed = 0.75
    return {"start": start, "window": round(window, 2), "length": length, "tease": tease, "xfade": xfade, "speed": speed}


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


def choose(stats, rng, avoid=(), **thresholds):
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
        else:
            picks = rng.sample(TREAT, rng.choice([1, 2]))
        for n in picks:
            sel[n] = {"Enable": 1, **params_for(n, rng)}
        if enabled(sel) not in taken:
            return sel
    spare = next(n for n in TREAT if n not in enabled(sel))  # twenty collisions: force a difference
    sel[spare] = {"Enable": 1, **params_for(spare, rng)}
    return sel


def reroll(selection, rng):
    """New parameters for the enabled, non-stateful treatments. Nothing else moves."""
    out = {n: dict(v) for n, v in selection.items()}
    for n in TREAT:
        if out[n].get("Enable") and not CORPUS[n].get("stateful"):
            out[n] = {"Enable": 1, **params_for(n, rng)}
    return out


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


def _apply(group, sel):
    chain = _fx().op("chain_" + group)
    for name, vals in sel.items():
        b = chain.op(name)
        for k, v in vals.items():
            getattr(b.par, k).val = v


def _cue(player, key, plan):
    p = _fx().op("player" + player)
    p.par.file = os.path.join(project.folder, key)
    p.par.cuepoint = plan["start"]
    p.par.speed = plan["speed"]
    p.par.cue = True
    p.par.play = True


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
    rng = _rng(st)
    clip = _table().get(st["clip"].get(player))
    plan = st["plan"][player]
    stats = window_stats(clip, plan["start"], plan["window"])
    fx = _fx()
    other = GROUPS[1 - GROUPS.index(group)]
    return choose(stats, rng, avoid=[st["sel"].get(group), st["sel"].get(other)],
                  bright_mean=float(fx.par.Brightmean), bright_high=float(fx.par.Brighthigh))


def _start_xfade(st, group):
    """The group starts its transition to the other player: new look, random transition."""
    fx = _fx()
    nxt = OTHER[st["player"]]
    sel = _selection_for(st, nxt, group)
    st["sel"][group] = sel
    _apply(group, sel)
    x = fx.op("xfade_" + group)
    x.par.Type = _rng(st).randrange(XFADE_TYPES)
    x.op("smear_fb").par.resetpulse.pulse()
    fx.op("nxt_" + group).par.index = 0 if nxt == "A" else 1
    fx.op("player" + nxt).par.cue = False  # it was cued at the segment start; now it plays
    x.par.Active = 1
    fx.op("tx_" + group).par.start.pulse()


def _timer(name, seconds):
    t = _fx().op(name)
    t.par.length = max(seconds, 0.05)
    t.par.start.pulse()


def start():
    """Called once from the Execute DAT's onStart and at the end of the build."""
    fx = _fx()
    fx.unstore("state")
    st = _state()
    st["player"] = "B"  # so that _pick_next cues the first clip into A
    first = _pick_next(st)
    st["player"] = first
    st["lead"] = 0.0
    fx.op("player" + first).par.cue = False
    for g in GROUPS:
        fx.op("cur_" + g).par.index = 0 if first == "A" else 1
        st["sel"][g] = None
    for g in GROUPS:
        st["sel"][g] = _selection_for(st, first, g)
        _apply(g, st["sel"][g])
    _begin_segment(st)


def _begin_segment(st):
    """Both groups show st['player']; cue the next clip and arm the timers."""
    fx = _fx()
    plan = st["plan"][st["player"]]
    _pick_next(st)
    L, T, t = plan["length"], plan["tease"], plan["xfade"]
    for g in GROUPS:
        fx.op("tx_" + g).par.length = t
    _timer("t_inner", L - T - t)
    _timer("t_outer", L - t)
    r = fx.op("t_reroll")
    r.par.length = float(fx.par.Rerollevery)
    r.par.start.pulse()


def on_done(timer_name):
    st = _state()
    fx = _fx()
    if timer_name == "t_inner":
        _start_xfade(st, "inner")
    elif timer_name == "t_outer":
        _start_xfade(st, "outer")
    elif timer_name in ("tx_inner", "tx_outer"):
        g = timer_name[3:]
        nxt = OTHER[st["player"]]
        fx.op("cur_" + g).par.index = 0 if nxt == "A" else 1
        fx.op("xfade_" + g).par.Active = 0
        fx.op(timer_name).par.initialize.pulse()  # fraction back to 0, so the xfade shows cur
        if g == "outer":
            plan = st["plan"][st["player"]]
            st["lead"] = plan["tease"] + plan["xfade"]
            st["player"] = nxt
            _begin_segment(st)


def on_reroll():
    st = _state()
    for g in GROUPS:
        if st["sel"].get(g):
            st["sel"][g] = reroll(st["sel"][g], _rng(st))
            _apply(g, st["sel"][g])
