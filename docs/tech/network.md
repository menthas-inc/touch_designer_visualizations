# The network, as read from td/network.json

> What the file does, operator by operator, so the next change does not start from a dump.
> Re-read the dump before trusting a value here. Last rewrite: 2026-11-03, after spec 001
> replaced the playlist chain with `/project1/fx`.

## The picture

```
td/clips.json (offline, ffmpeg)            td/sequencer.py (synced into fx/sequencer)
        │                                          │ picks clip, window, tease, effects
        └──────────────► playerA / playerB ◄───────┘ cues the idle one, flips the switches
                              │       │
             outer: fitA/fitB (340 x 1080) ──► chainA/chainB ──► cur, nxt ──► xfade_outer ──► limiter ──► out_outer
             inner: fitA/fitB (340 x 1080) ──► chainA/chainB ──► cur, nxt ──► xfade_inner ──► limiter ──► out_inner
                                                                                                           │
                                   kantanMapper1: Rectangle5 + Rectangle1 .Texture = out_outer             │
                                                  Rectangle4 + Rectangle2 .Texture = out_inner ◄───────────┘
                                                  ──► out1 ──► project/window1 (display 1, the projector)
```

Everything that changes lives in `/project1/fx`, built by `td/build_fx.py` from the spec in
`docs/specs/001-dynamic-effects/`. The old playlist, the brightness invert, the Touch loop,
the Switch button and the reel are gone. `constant1`, the orange alignment colour, stays.

## fx, piece by piece

- **Players.** `playerA`, `playerB`, Movie File In. One plays, the other holds the next clip
  cued at its window start. `interp` on, 30 frames preread. Speed per clip from the table.
- **Groups.** `outer` is Rectangle5 and Rectangle1 (panels 1 and 4), `inner` is Rectangle4
  and Rectangle2 (panels 2 and 3). Per group: `fitA_g` and `fitB_g` (340 x 1080, fit
  outside), two chain slots `chain1_g` and `chain2_g` each fed by either player through
  `src1_g` and `src2_g`, `cur_g` and `nxt_g` Switch TOPs over the two slots, `xfade_g`,
  `limiter_g`, `out_g`, and `pair_g` for the pair's mirrored strip: `out_g` crossed with its
  x flip on `pair_lag_g` (3 s) toward `pair_tgt_g`, which the sequencer sets to 1 four times
  in five at a clip change. A transition melds the shown slot into the other, which carries
  the next clip at a clip change or the same clip with a new look for a mid-clip swap.
- **xfade_g.** Pars `Progress` (from `tx_g`'s `timer_fraction`), `Type` (0 burn, 1
  distort, 2 patches, 3 colour, all in `glsl` from `td/glsl/xfade.glsl`, synced from the
  file; 4 smear, a Feedback loop on `smear_out`), `Active` (off: `cur` passes straight
  through, nothing else cooks).
- **chainN_g.** Twelve Bases in a fixed order, each `in1`, a wet path, a Switch on `Enable`,
  `out1`: `framing, highlights, crush, edges, tint, selfmask, feedback, displace, echo,
  mirror, chroma`. Slow LFOs drift `feedback`, `displace`, `echo`, `mirror` and `chroma` so
  a held effect still moves. `feedback` and `echo` have no Switch,
  their Cross sits at `Mix * Enable` so the loop keeps cooking. Custom pars per effect are
  the `CORPUS` in `td/sequencer.py`; the sequencer sets them. On a dark clip a group gets an
  effect only one time in five. `limiter_g` after the transition: `lim_mono`,
  `lim_small` 40 x 40, `lim_avg`, `lim_val`, `lim_gain` (`min(1, Ceiling / mean)`),
  `lim_lag` (0.5 s up, 0.05 s down), `lim_level` brightness. Feedforward, one-sided.
- **Spice.** A third player, `playerC`, through `fitC` and `chainC` (the same twelve
  effects, a look chosen like the groups') and `spice_drift` (a small wander), crossed over
  one pair or both by `spice_g` between the transition and the limiter. `t_spicewait` (40 to
  120 s) then `t_spice` (5 to 10 s): the cross follows `spice_env`, 0 to 0.9 and back with 2
  to 4 dips, so it comes in, pulses and leaves. Player C only plays during a spice.
- **Timers.** `t_turn` cues a short clip back to its start when it reaches its end, `t_preroll`
  releases the cued player 1 s before it is shown, `t_inner` and
  `t_outer` fire the two transitions, `tx_inner` and `tx_outer` run them and flip `cur_g` when
  done, `t_reroll` ticks every `Rerollevery` seconds: one group in turn, three times in ten,
  swaps to a new look on the same clip over 6 to 12 s, unless its clip change is near. All
  share `timers_callbacks`, which calls into `sequencer`. `run`, an Execute DAT, calls
  `start()` on file open.
- **Pars on fx.** `Ceiling` 0.18, `Brightmean` 0.33, `Brighthigh` 0.65, `Cap` 60, `Rerollevery`
  20, `Seed` 0 (random). `Darkness` is a macro: `none` (Ceiling 1, never bright), `default`,
  `darker` and `darkest`. The two upper levels keep the default ceiling and thresholds, push
  the darkeners' draws toward the dark end of their ranges, and force a full highlights cut on
  every clip, bright patches above 0.55 to 0.75 (`darker`) or 0.3 to 0.5 (`darkest`) going
  black. The `Try` page holds the random choosing (`Hold`) and steps through
  effects and transitions by hand (`Effect`, `Preveffect`, `Nexteffect`, `Reroll`,
  `Xfadetype`), through `try_pars`, a Parameter Execute DAT.
- **State.** A plain dict in `fx`'s storage: which player is current, clip and plan per
  player, selection per group, the playlist queue, the lead. The module is stateless, so
  editing `td/sequencer.py` mid-show keeps the show running.

## A clip change

```
now                      end - T - t       end - T          end - t        end
│ outer A, inner A        │ inner A to B     │ outer A, inner B │ outer A to B │ both B
```

At the start of a segment the idle player is cued with the next clip. `t_inner` fires at
`L - T - t`: the inner group gets a new selection, a random transition type, and runs
`tx_inner` for `t` seconds, during which the cued player plays. `t_outer` fires at `L - t`
and does the same for the outer group; when `tx_outer` is done the next segment begins with
the roles swapped and `lead = T + t` taken off the new clip's play. T is 0 half the time,
else 1 to 6 s; t is 7.5 to 22.5 s, half the meld in its first third; the plain play before a
change is never under 6 s.

## The table

`td/clips.json`, from `python3 td/clip_stats.py` after any change to `VJ_Visuals`: per clip
the length, frame rate, a motion score, and per 10 s bucket the mean and high luma. A clip
not in the table counts as bright.

## The mapper

`kantanMapper1` is Kantan Mapper 2.14 from the palette, a container whose `project` base holds
the shapes and renders them with an orthographic camera whose width is the project resolution,
1920 x 1080. Canvas coordinates are pixels centred on (0, 0), y up.

Every shape is a Geo COMP `project/allShapes/itemN`, cloned from `masterShapes/rectangle`,
with these parts that matter:

- `itemN/parameters`: custom pars. `Name`, `Texture` (a TOP path; empty means Kantan's test
  grid), `Textureorientation` (0 to 3, times 90 degrees), `Fliptexture`, `Rows` and `Cols`
  (warp grid), `Softedge`, `Colorr/g/b` (the fill when no texture shows), pivots.
- `itemN.par.xformmatrixop`: the base rectangle as a matrix expression, `tdu.Matrix([sx,0,0,0,
  0,sy,0,0, 0,0,1,0, tx,ty,0,1])`. sx and sy are the width and height in canvas pixels, tx and
  ty the centre.
- `itemN/keyOffset`: the four corner drags, as fractions of the base width and height. Corner
  0 is bottom-left, 1 bottom-right, 2 top-left, 3 top-right. The homography in `itemN/homography`
  is derived from these by `Transform.findRectHomography`, not edited by hand.
- `itemN/pointOffset`, `uvOffset`: the warp grid, empty here, nobody warped.
- `project/tree`: one row per shape, `id type owner layer lock visible`. This is where hidden
  and locked live, not on the shape.

### The six shapes, now

| item | name | base w x h at centre | corners | texture | orient | flip | tree |
|---|---|---|---|---|---|---|---|
| 1 | Rectangle1 | 292 x 1080 at (753, 0) | none | fx/out_outer | 2 | no | locked |
| 2 | Rectangle2 | 300 x 1080 at (302, 0) | none | fx/out_inner | 0 | no | locked |
| 3 | Rectangle3 | 130 x 62 at (-443, -635) | none | none (test grid) | 0 | no | unlocked, off canvas |
| 4 | Rectangle4 | 310 x 1080 at (-187, 0) | none | fx/pair_inner | 0 | in pair_inner | locked |
| 5 | Rectangle5 | 328 x 1080 at (-694, 0) | none | fx/pair_outer | 2 | in pair_outer | locked |
| 6 | Rectangle6 | 58 x 56 at (0, -465) | none | none, cleared | 0 | no | locked, hidden |

How they got here, in canvas pixels (centre 0,0, y up, frame x -960..960, y -540..540): the
file arrived with every strip's bottom corners dragged up to y = 400 and the tops on the frame
edge, so each was a short band in the top 15 percent of the frame with the video squashed six
times. The base columns underneath already described four strips side by side across 85 percent
of the frame, which is the room. `td/reset_corners.py` removed the drags (the values stay in
git), `td/set_columns.py` made all four 1080 tall, and `map_video.py` first put video on them
before spec 001 took over the textures. The orientation and flip flags per strip are
intentional (owner, 2026-11-03): they match how each strip hangs. The flip on 4 and 5 moved
into `fx/pair_g` on 2026-11-04 (owner): a Flip TOP crossed in over a 3 s lag, on four times
in five per clip change, so a pair is sometimes the same way round, with no cut. Rectangle3 and 6 are
leftovers. The saves in `Backup/` are a different installation (2022 to 2023).

### Driving Kantan from a script

Promoted extension methods on `kantanMapper1/project` (`parent.KanProj` inside Kantan):

- `AddRect(pnt1=[x,y], pnt2=[x,y])`, `AddFree(...)`, `AddLayer()`, `CopyShape(shapeId=[...])`,
  `DeleteShape(shapeId=N)`, `MoveShape(...)`. These append to `tree` and let the replicator build
  the Geo COMP.
- `SelectShape(itemId=N)`, `LockShape(itemId=N)`, `ShowShape(itemId=N)` toggle tree columns.
- `Collect()` and `Load()` save and load the whole project as json, through a file dialog.

On a shape (`itemN`, extension `Shape` for pars, `Transform` for geometry):

- `shape.GetDefinition()` returns pars plus the offset tables plus the matrix; `SetDefinition(d,
  undo=False)` writes them back. This is the clean way to move corner data between shapes.
- `shape.Translate(translate={'x':..,'y':..})`, `Scale(scale={'x':..,'y':..})`, `Rotate(...)`,
  `TranslateKey(keyId=[0..3], tx, ty)` for corners, `Reset(key=True)` to undo the corner drags.
- `shape.Setpar('Texture', '/project1/switch1')` or just `shape.op('parameters').par.Texture`.

The repeating Textport tracebacks from `tools/rectDetail/script*_script` are Kantan's own
row-and-column tool cooking with no shape selected. They are noise, not ours.

## Output

- `project1` is the perform window's target; `open_output.py` pointed it at the mapper's
  output (it arrived pointing at a `./out1` that did not exist).
- Kantan's own output window, the Toggle Output button, is `project/window1`: borderless on
  display 1, which is the projector when one is attached.
- `/project1/window` (1920 x 1080) and `window1` (1080 x 1920) are two spare Window COMPs with no
  operator set. `open_output.py` uses the first as the laptop preview.

## Not in the zip

- `Mesme x SL Reel_v3.mp4` and `mood_M_.png`, referenced by the old chain, now deleted.
- `kantan.json`, the mapper's project file. Its embedded copy is Kantan's demo, not ours.
- The file last ran on a Windows machine (`C:/Users/.../...`). Folder paths re-resolve on load.
