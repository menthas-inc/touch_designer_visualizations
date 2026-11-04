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
DARK = [n for n, e in CORPUS.items() if e["family"] == "dark"]
TREAT = [n for n, e in CORPUS.items() if e["family"] == "treat"]
XFADE_TYPES = 3  # melt, displace, smear
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
SWAP = (4.0, 8.0)  # seconds a mid-clip look swap takes
SWAP_CHANCE = 0.3  # per reroll tick, for the one group whose turn it is
SHORT = 45.0  # clips under this play twice, to last longer  # the cued player is released this long before it is shown, so it is rolling by then


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
    tease = round(rng.uniform(1.0, 6.0), 2) if rng.random() < 0.5 else 0.0
    xfade = round(rng.uniform(5.0, 15.0), 2)
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
    chain = _fx().op(f"chain{slot}_{group}")
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
    rng = _rng(st)
    clip = _table().get(st["clip"].get(player))
    plan = st["plan"][player]
    stats = window_stats(clip, plan["start"], plan["window"])
    fx = _fx()
    other = GROUPS[1 - GROUPS.index(group)]
    level = DARKNESS[str(fx.par.Darkness)]
    return choose(stats, rng, avoid=[st["sel"].get(group), st["sel"].get(other)], bias=level[3], cut=level[4],
                  bright_mean=float(fx.par.Brightmean), bright_high=float(fx.par.Brighthigh))


def _start_xfade(st, group, player, seconds):
    """The group melds from its shown chain slot into the other, carrying `player` with a new
    look: the next clip at a clip change, the same clip for a mid-clip swap."""
    fx = _fx()
    x = fx.op("xfade_" + group)
    if x.par.Active:
        _finish_xfade(st, group)  # a swap still running when the clip change comes
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


def _finish_xfade(st, group):
    """The transition is over: the group shows the slot it melded into."""
    fx = _fx()
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
    if fx.par.Hold:
        _hold_apply(st, str(fx.par.Effect))
    _begin_segment(st)


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
    r.par.length = float(fx.par.Rerollevery)
    r.par.start.pulse()


def on_done(timer_name):
    st = _state()
    fx = _fx()
    if timer_name == "t_preroll":
        _release(OTHER[st["player"]])
    elif timer_name == "t_turn":
        fx.op("player" + st["player"]).par.cuepulse.pulse()  # a short clip reaches its end: again from the top
    elif timer_name in ("t_inner", "t_outer"):
        _start_xfade(st, timer_name[2:], OTHER[st["player"]], st["plan"][st["player"]]["xfade"])
    elif timer_name in ("tx_inner", "tx_outer"):
        g = timer_name[3:]
        # with no tease both transitions end in the same frame, and the outer one may have
        # swapped st["player"] already, so the target comes from the start of the transition
        _, nxt = st["target"][g]
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
