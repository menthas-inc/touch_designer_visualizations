# 001 Dynamic effects, implementation

> How the feature spec is built. Every piece is a script in `td/`; the only mapper write is
> four `Texture` parameters.

## Constitution check

- DEV-1: one new container, `/project1/fx`, built from one script; the old playlist chain is
  deleted rather than bypassed. Compliant.
- DEV-2: this document is the spec the build script follows; divergences are edited here in
  the same commit. Compliant.
- DEV-3: native TOPs, two short GLSL shaders for transitions, ffmpeg for the offline table.
  Compliant.
- QUAL-1: the sequencer's decisions are pure Python with tests in `tests/`, run by the
  pre-commit gate. The TouchDesigner side is checked on the preview, with AC-4's frame check
  as a Script CHOP log. Compliant, with the preview as the test for the look.
- SV-1: `td/build_fx.py` builds everything; `td/sequencer.py` is the runtime; both committed.
  Compliant.
- SV-2: corner data untouched; the four `Texture` parameters change. Compliant, stated.
- SV-3: per frame, two 1080p decodes, two 340 x 1080 chains with at most four effects cooking
  each, two 40 x 40 measurements, one transition shader per group during a change. Said here;
  measured on the preview (AC-6).

## Pieces

### 1. `td/clip_stats.py`, offline, plain Python

Walks `TD_Mapping/VJ_Visuals` for movie files. Per clip, `ffprobe` for duration and frame
rate, then two `ffmpeg` passes at one frame per second on a 160 px wide copy: `signalstats`
for luma average and high percentile per sampled frame, and `tblend=difference,signalstats`
for motion. Writes `td/clips.json`:

```
{"VJ_Visuals/x.mp4": {"length": 31.2, "fps": 30.0, "motion": 0.08,
                      "buckets": [{"mean": 0.21, "high": 0.62}, ...]}}   one bucket per 10 s
```

Paths are relative to `TD_Mapping/` so the table works on any machine. Re-run after adding
clips. Missing clips count as bright (spec C).

### 2. `td/sequencer.py`, pure logic plus thin glue

Loaded into a Text DAT `/project1/fx/sequencer` synced to the file, so it is editable in the
repo and importable in tests. Two layers:

**Pure, tested.** No TouchDesigner names at module level.
- `plan_segment(clip, rng, cap=120, lead=0)`: window start and length in wall seconds (a clip
  under `SHORT` 45 s gets `turn`, when it reaches its end and starts over); tease (coin flip, then
  1 to 6 s); transition length 5 to 15 s; speed from fps and motion. `lead` is how long the clip
  has already played when it becomes both groups' picture (the previous change's tease plus
  transition), so the play before the next change is `length - tease - xfade`, clamped to at
  least `FLOOR` (6 s, the time the next clip has to cue) by shrinking the tease, then the
  transition. A tease under a second becomes none.
- `window_stats(clip, start, length)`: the buckets under the window, as mean and high.
- `is_bright(stats)`: `high >= 0.55 or mean >= 0.30` (parameters on the fx container).
- `choose(stats, rng, avoid=[...])`: a selection dict `{effect: {enable, params}}` following
  the spec: bright gives one or two darkeners plus maybe one treatment, dark gives one or two
  treatments, framing always, its enabled set different from every selection in `avoid` (the
  group's previous one and the other group's current one).
- `reroll(selection, rng)`: new params for the enabled non-stateful treatments only.
- `Playlist`: the shuffled list with short clips twice, no clip twice in a row.

**Glue, thin.** Module functions `start()`, `on_done(timer_name)`, `on_reroll()`, stateless:
the mutable state (which player, clips, plans, selections, playlist queue, lead) is a plain
dict in the fx container's storage, so a re-sync of the file mid-show loses nothing. They only
set parameters and pulse.

### 3. `td/build_fx.py`, builds `/project1/fx`

Run once; running again deletes and rebuilds `fx`. Inside:

- `playerA`, `playerB`: Movie File In, `interp` on, `prereadframes` 30. The idle one is cued
  (file, cue point, `cue` on, `play` on) at the start of every segment, at least `FLOOR`
  seconds before it is shown. Resolution as decoded; the licence cap applies.
- Per group `g` in `outer`, `inner`:
  - `cur_g`, `nxt_g`: Switch TOPs over A and B, indices held by the sequencer.
  - `fitA_g`, `fitB_g`: Fit TOPs, 340 x 1080, fit outside, one per player, then two chain
    slots `chain1_g` and `chain2_g`, each behind a `srcN_g` Switch over the two fits, then
    `cur_g` and `nxt_g` Switches over the slots into the transition. A new look always goes on
    the idle slot, so the shader melds the old look into the new one, at a clip change and at
    a mid-clip swap alike; outside a transition only the shown slot cooks.
  - `xfade_g`: a Base with inputs `cur`, `nxt`, custom pars `Progress`, `Type` and `Active`.
    Types 0 and 1 are one GLSL TOP (`td/glsl/xfade.glsl`, uniforms `uProgress`, `uType`),
    type 2 is a Feedback TOP loop (`smear_fb`, target `smear_out`, `resetpulse` at each
    start). A Switch on `Type`, then a Switch on `Active` that passes `cur` straight through
    outside a transition, so the shader and the second chain only cook during a change.
  - a chain: Bases in this fixed order, each `in1`, a wet path, a Switch (index =
    `parent().par.Enable`), `out1`:
    `framing, highlights, crush, edges, tint, selfmask, feedback, displace, echo, mirror,
    chroma` (keepchannel, pixelate and slope were cut on the wall: grey or dull).
    `feedback` and `echo` are the exception: no Switch, their own Cross at `Mix * Enable`,
    so the loop keeps cooking and nothing pops when they come in.
  - the limiter: a mono copy of the chain, Fit 40 x 40, Analyze average, TOP to CHOP, an
    Expression CHOP `min(1, ceiling / max(x, 0.001))`, a Lag CHOP fast down (0.05 s) and slow
    up (0.5 s), into a Level TOP's brightness. Feedforward, one-sided. `Ceiling` is a par on
    `fx`, default 0.18.
  - `out_g`: Null TOP. The mapper's `Texture` for the group's two strips points here.
- Timers, all in seconds, one callbacks DAT: `t_inner` (length `L - T - t`) starts the inner
  transition, `t_outer` (`L - t`) the outer, `tx_inner` and `tx_outer` (length `t`) drive
  `Progress` with `timer_fraction` and on done flip the group's current player and re-initialise
  so `Progress` reads 0 again; the outer one's done begins the next segment. `t_reroll` cycles
  every `Rerollevery` seconds. No segments table: four plain timers are simpler to reason about
  and cannot be re-initialised by a table edit mid-run.
- Custom pars on `fx`: `Ceiling`, `Brightmean`, `Brighthigh`, `Cap`, `Rerollevery`, `Seed`.

### 4. What goes

`folderRaw*`, `folder*`, `shuffled*`, `script1`, `select1`, `playlist`, `reorder1`,
`playlist_index`, `remaining`, `info`, `select2`, `math2`, `speed`, `chopto1`, `touchout1`,
`touchin1`, `datto1`, `reset`, `reset_index`, `movie`, `switch2`, `moviefilein2`, `fit2`,
`button1`, `mood_logo`, `moviefilein1`, and the old `fit`, `fit1`, `diff*`, `analyze*`,
`topto*`, `math1`, `math3`, `invert*`, `switch`, `switch1`, `white`, `movie_null`, and the
callback DATs next to them. Deleted by `td/build_fx.py` at the end of the build, after the
new chain is wired and started, so the file is never dark. `constant1` stays: it is the orange
alignment colour to point a strip at when the paper is re-hung. Rectangle6's `Texture`, which
pointed at the deleted `switch`, is cleared; it is hidden anyway.

### 5. Transitions

`td/glsl/xfade.glsl`, one shader, `uType` 0 melt, 1 displace:
- melt: `k = luma(nxt) - luma(cur) + (2p - 1) * 1.2; m = smoothstep(-0.15, 0.15, k); out =
  mix(cur, nxt, m)`.
- displace: `out = mix(cur sampled at uv + (luma(nxt) - 0.5) * p * a, nxt sampled at uv +
  (luma(cur) - 0.5) * (1 - p) * a, smoothstep(0.2, 0.8, p))`, `a = 0.08`.
Smear, TOPs: `fb = Feedback(target smear_out); z = Transform(fb, scale 1.015); d = Level(z,
brightness 0.94); base = Cross(cur, d, p); smear_out = Cross(base, nxt, smoothstep(p))`;
`resetpulse` at transition start.

## Reuse and skips

- Fit 340 x 1080 and the 40 x 40 Analyze: the file's own pattern, rebuilt in `fx` (rung 2).
- Timer CHOP with segments and callbacks: platform (rung 3), instead of a hand-rolled clock.
- ffmpeg signalstats: installed tool (rung 4), instead of measuring in TouchDesigner. Luma at
  one frame a second, motion at ten, both on a 160 px copy.
- GLSL for two transitions: new code, 25 lines, because the melt needs a per-pixel compare
  and the displace needs two dependent samples; TOP-only versions need six ops each.
- Skipped: audio, a UI, per-strip anything, Rectangle6 and 3, a second machine, effect
  presets saved between runs, LFS for the videos.
- Limits accepted: `shortcut: effects do not know about each other, a crush after an edge
  detect can go near black; upgrade to a small compatibility table in choose() when a
  combination is seen to fail on the wall.`

## Who runs what

Offline here: `clip_stats.py`, the tests. In TouchDesigner, in order: `build_fx.py` once,
then the file is saved. From then on the sequencer runs itself from `onStart` of `fx`'s
Execute DAT.
