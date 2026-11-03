# Technical decisions

> Newest at the top. One entry per decision: what, why, and what it rules out.

## Decided

### 2026-11-03: the show runs on this Mac on the free licence, at 1280 x 720
The owner's Mac (M1 Max) is the show machine and the licence is non-commercial, which caps
every TOP at 1280 x 1280. Rather than let TouchDesigner silently downscale the mapper's
1920 x 1080 render, the mapper's project resolution is set to 1280 x 720 so what the projector
gets is what the file says. The strip chains at 340 x 1080 are under the cap.
Rules out: 1080p output to the projector without a paid licence. If the look needs it, buy the
licence and raise the resolution back; nothing else changes.

### 2026-11-03: the Touch In and Out index loop goes
No second machine listens to it (owner). The sequencer in spec 001 replaces the Count CHOP
and the loop in one piece.
Rules out: a follower machine without a new publish step in the sequencer.

### 2026-11-03: the network is edited by script, read by dump
The `.toe` is a compressed binary, so it cannot be read or edited here. Every read is a dump
script run inside TouchDesigner that writes the operators, parameters and wiring to text in
`td/`; every edit is a Python script in `td/`, run inside TouchDesigner and committed. Driving
the editor by screenshot is the fallback for visual checks, not the main channel.
Rules out: hand edits in the editor as a way of changing the network (SV-1).

## Open, needing a call

- Where the source videos live and whether they are tracked (git LFS, a shared drive, or
  ignored). Nothing is ignored yet.
- How a script gets into TouchDesigner. Today: `exec` in the Textport. Spec 001 adds a Text DAT
  synced to `td/sequencer.py` for the code that runs every frame; the one-shot build scripts
  stay on `exec`.
