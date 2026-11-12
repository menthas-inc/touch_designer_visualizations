# Technical decisions

> Newest at the top. One entry per decision: what, why, and what it rules out.

## Decided

### 2026-11-12: the repo is public; the clips and the tracker's environment stay out
Code, docs, the two `.toe` files and the network dump are tracked. The clips (2.4 GB) and
`beat/.venv` are ignored; `td/clips.json` names the clips, so a table entry with no file is
skipped, not an error. Before publishing, the history was rewritten once: one author identity
and no home paths in the tracked text. Scripts and file parameters are relative to
`project.folder` from here on, so a save carries no machine path.
Rules out: git LFS for the videos, and a clip that is not on the machine playing.

### 2026-11-05: scripts reach TouchDesigner by `exec` in the Textport; what runs every frame is synced
One-shot scripts (the build, the dump, the diagnostics) are `exec`'d by hand. `td/sequencer.py`
and the shaders are Text DATs synced to the files, so an edit lands live.
Rules out: nothing. A launcher would be one more thing to keep working.

### 2026-11-03: the show runs on this Mac; the free licence's cap is accepted for now
The owner's Mac (M1 Max) is the show machine. The licence is non-commercial, which caps every
TOP at 1280 x 1280, so the mapper's 1920 x 1080 render reaches the projector downscaled. The
file keeps 1920 x 1080: the owner will buy a licence later and nothing then has to change. The
strip chains at 340 x 1080 are under the cap either way.
Rules out: nothing. Until the licence, judge sharpness on the wall knowing it is capped.

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

- None right now.
