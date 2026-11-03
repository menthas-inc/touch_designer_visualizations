# Technical decisions

> Newest at the top. One entry per decision: what, why, and what it rules out.

## Decided

### 2026-11-03: the network is edited by script, read by dump
The `.toe` is a compressed binary, so it cannot be read or edited here. Every read is a dump
script run inside TouchDesigner that writes the operators, parameters and wiring to text in
`td/`; every edit is a Python script in `td/`, run inside TouchDesigner and committed. Driving
the editor by screenshot is the fallback for visual checks, not the main channel.
Rules out: hand edits in the editor as a way of changing the network (SV-1).

## Open, needing a call

- Where the source videos live and whether they are tracked (git LFS, a shared drive, or
  ignored). Nothing is ignored yet.
- Whether the free non-commercial TouchDesigner license is enough for the show machine. It caps
  output at 1280 by 1280.
- How a script gets into TouchDesigner: pasted into the Textport, or a Text DAT synced to a file
  in `td/` so edits land live.
