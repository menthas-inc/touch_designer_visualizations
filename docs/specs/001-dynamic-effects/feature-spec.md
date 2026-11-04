# 001 Dynamic effects

> Draft 2, 2026-11-03. Owner's brief, shaped into a plan, reviewed, questions answered.

## Why

Two problems with the rig as it runs today:

1. **Too bright.** Some clips are bright, the four strips are a big canvas, and at a night party
   they light the room. The current fix, inverting any clip whose average goes above 0.4, is
   blunt and looks dull.
2. **Boring.** The same clip on all four strips, the same treatment every time, short clips
   repeated, long clips outstaying their welcome.

## What

A dynamic chain between the playlist and the mapper. Four pieces.

### A. Two video streams and a sequencer

Two Movie File In players, A and B. While one plays, the other has the next clip cued, so a
switch is instant. A Timer CHOP owns the clock and fires callbacks at the four moments of a
clip change; the sequencer (Python in a Text DAT synced to `td/sequencer.py`, so the logic is
a real file in the repo) only answers "which clip, which effects" at those moments. It
replaces the Count CHOP and the Touch In and Out loop (no second machine listens; owner,
2026-11-03).

Each clip plays for a bounded segment of at most 120 s on the wall (the cap is a parameter):
a long clip gets a random window of it, a clip under 45 s plays twice so it lasts longer. That is the answer to long clips and to short ones.

Playback speed is per clip, from the table: 0.6 by default, and lower (down to 0.4) for clips
whose measured motion is high and whose frame rate is 25 or above. Low frame rate clips stay
at 0.6, since slowing them stutters.

### B. Two groups, two chains

The strips, left to right on the wall, are Rectangle5, Rectangle4, Rectangle2, Rectangle1.
The **outer group** (panels 1 and 4) is Rectangle5 and Rectangle1; the **inner group** (panels
2 and 3) is Rectangle4 and Rectangle2. Each group has one effect chain ending in one TOP, and
the only write to the mapper is pointing those four `Texture` parameters at the two outputs
(corner data untouched, SV-2). This assumes the file after `reset_corners.py` and
`set_columns.py`: four full columns.

Each chain is a serial run of effect components in a fixed order (the order is part of the
look and makes a selection reproducible), each with a Bypass flag and a few parameters. A
selection is a set of flags and parameter values. Only enabled effects cook, with one
exception: feedback and cache effects pop when re-enabled, so they stay cooking with their mix
at 0 and are only re-rolled at a transition, where the pop is masked.

Each chain ends in a limiter, not a governor: a 40 x 40 copy of the chain output (the existing
`fit` and `analyze` pattern, reused per group) measures the mean before the Level TOP, the
gain is `min(1, ceiling / measured)` with a soft knee, lagged, and applied. Feedforward, so it
cannot pump, and one-sided, so it never brightens a dark clip and is off for anything under
the ceiling (a parameter, say 0.18). Under the ceiling the darkeners are the look; the limiter
only catches what they miss.

### C. The effect corpus and the chooser

Two families, all built from TOPs that ship with TouchDesigner:

- **Darkeners**, picked when the clip is bright. Remove highlights (threshold the luma, key
  them out over black), keep one channel or a two-channel mix, crush with a dark lookup ramp,
  edge detect (black field, bright lines), tint to a single colour and drop the rest,
  multiply the clip by its own inverted luma.
- **Treatments**, picked otherwise, and sometimes stacked on a darkener. Feedback with a
  slow zoom or drift, displacement from a noise field, time echo from a cache, mirror or
  tile, pixelate, slope or emboss, chroma offset.
- **Framing**, one per group per segment, always on: a crop and offset so the two groups do
  not show the same part of the clip, and a flip or 180 degree turn that varies per clip. The
  flip lives in the chain, not on the mapper's per-strip orientation flags, which stay as
  calibrated for how each strip hangs.

The chooser decides per segment per group: is the segment bright (one or two darkeners,
plus maybe one treatment) or not (one or two treatments), never the same selection for both
groups. Brightness is precomputed offline by `td/clip_stats.py` with ffmpeg `signalstats`
into `td/clips.json`: per clip its length, frame rate, a motion score, and, per 10 second
bucket, the mean and the high percentile of luma. The high percentile matters more than the mean here: a black clip with
one blown-out blob lights the room and has a low mean. The chooser reads the buckets under
the chosen window. A clip missing from the table counts as bright, because new files land in
`VJ_Visuals` without passing through the repo. The chooser also re-rolls the treatment every
N seconds inside a long segment, so a 90 second clip does not sit still.

### D. Teases and transitions

The inner group switches to the next clip early. Per change, a coin flip decides whether
there is a tease at all; if yes its length T is drawn from 1 to 6 s, so it is not predictable.
Transition length t is 7.5 to 22.5 s, the first half of the meld in the first third of that
time and the second half over the rest, and the old look melds into the new one with the picture,
not before it. Now and then, not often, a group also melds to a new look mid clip, over 6 to
12 s, flips and tilts included. The two strips of a pair mirror each other four clips in five;
otherwise they hang the same way round, the change blended in, never cut.

Every minute or so a third clip, any from the table, drops in over one pair or both for 10 to
20 s: it comes in, pulses four to seven times, wanders a little and leaves, never fully taking
over. It gets its own look, chosen like the groups' and unlike theirs. Timeline for one change:

```
now                      end - T - t       end - T          end - t        end
│ outer A, inner A        │ inner A to B     │ outer A, inner B │ outer A to B │ both B
```

By the end, B has played T + t. The next segment counts from B's cue point, so its plain play
is shorter by that lead, and the plain play before any change is never under 6 s, which is the
time the idle player has to cue the clip after it.

Transitions are not crossfades. Five, chosen at random per switch: a burn (the next clip
appears in the bright parts of the current one and eats outward through a crisp edge), a
distortion (each picture warps the other by its brightness, the two smear into one before the
next settles), patches (the next clip arrives as growing noise blotches), a colour arrival
(red lands first, then green, then blue, each sliding in from its own offset), and a feedback
smear (the outgoing picture feeds back and dissolves under the incoming one). Each has one
parameter, the progress 0 to 1, driven by a Timer CHOP.

## Acceptance criteria

Each is checked headlessly over `td/clips.json` and a logged trace of the per-group
measurement, except where it says otherwise.

- AC-1: with the ceiling at 0.18, no group's logged mean sits above 0.22 for more than 2 s.
- AC-2: a bright segment (table above threshold) always gets at least one darkener; a dark
  segment never gets one; a clip missing from the table gets one.
- AC-3: the chooser never returns identical selections for the two groups in the same
  segment; both panels of a group read the same TOP.
- AC-4: the inner group leads by T and each group transitions over t; inside every transition
  window no frame has mean below 0.001 and no frame hash repeats the previous one.
- AC-5: a clip plays at most 120 s on the wall, and the treatment re-rolls at
  least once inside a segment.
- AC-6: 30 fps on this Mac with the mapper on, measured in the perform window. This Mac is
  the show machine.
- AC-7: everything is built by scripts in `td/` (SV-1); the only mapper write is the four
  `Texture` parameters (SV-2).

## Out of scope

- Audio reactivity.
- A control surface beyond a few parameters on one component.
- New source material.
- The second reel and the Switch button, the logo. The Touch In and Out loop stays until the
  owner says no second machine listens to it.

## Feasibility, as reviewed

- Everything above is native TouchDesigner: Movie File In with cue, Switch and Cross TOPs,
  Feedback, Displace, Cache, Mirror, Threshold, Lookup, Level, Analyze, Timer CHOP, Text DAT
  synced to a file. No external plugins. One 25 line GLSL shader for two of the three
  transitions, because a per-pixel compare and two dependent samples are six TOPs each the
  other way (impl-spec, Reuse and skips).
- Cost: two 1080p decodes plus two 340 x 1080 chains with a handful of effects each is well
  inside an M1 Max. A Windows show machine with a discrete GPU is also fine. The governor adds
  one Analyze per group, which is cheap at that size.
- The sequencer is the one piece with real logic, and it can be tested outside TouchDesigner:
  the timing and choosing are plain Python over the clip table, and the TD calls are thin.
- Risk: Movie File In cueing. A cue on a long H.264 file can take a few hundred ms; cueing
  15 s ahead covers it. Clips from Instagram are small and fast.
- Risk: feedback effects drift to white or to black over minutes. Each feedback has a decay
  and the governor sits after it.
- Risk: the look. Effects chosen at random can be ugly. The corpus starts small (about six
  darkeners, six treatments, three transitions) and each is checked on the preview before it
  joins the pool. Adding one later is one component and one line in the chooser.
- The show runs on this Mac on the free licence, which caps every TOP at 1280 x 1280. The
  mapper keeps its 1920 x 1080 and arrives at the projector downscaled until the owner buys a
  licence (decision logged in `docs/tech/decisions.md`). The strip chains at 340 x 1080 are
  under the cap.

## Answers that shaped draft 2 (owner, 2026-11-03)

Panels are numbered left to right facing the wall. No second machine, the Touch loop goes.
This Mac, free licence, is the show machine. Long clips: a random window, at most 60 s, raised to 120 on the wall. Same
clip on both groups, with a tease half the time, 1 to 6 s long when there is one. Speed 0.75 unless measurable
per clip, worried about low frame rate clips, so speed comes from the table. "Orientations"
meant both the same framing on every strip and the fixed flips, so framing is a treatment.
