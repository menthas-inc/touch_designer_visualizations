# Setup

## The machine

The show runs on a Mac (M1 Max) with TouchDesigner 2025.33230 on the free licence, which caps
every TOP at 1280 x 1280; the mapper's 1920 x 1080 render reaches the projector downscaled,
the 340 x 1080 strip chains are under the cap. One 1080p projector on HDMI. Four strips of
paper on the wall.

The project lives in `TD_Mapping/`. `Studio_Up_new.toe` is the working file. `Studio_Up.toe`
(December 2025) is the file as it arrived, from an older TouchDesigner, kept untouched.
`Backup/` is TouchDesigner's own autosave history, ignored. The clips sit next to them in
`VJ_Visuals/` and `Not_Used/`, on disk and out of git; `td/clips.json` lists them by name.

## The loop

The `.toe` is a compressed binary, so it is never edited by hand (SV-1).

1. Open `TD_Mapping/Studio_Up_new.toe` from the repo, so the relative paths in it resolve.
2. A change is a Python script in `td/`, run from the Textport (Alt+T):
   `exec(open(project.folder + '/../td/<script>.py').read())`
   `project.folder` is `TD_Mapping/`, so the line is the same on any machine.
3. Dump the network: `exec(open(project.folder + '/../td/dump_network.py').read())` writes
   `td/network.json`, every operator with its non-default parameters and wiring. Commit the
   script and a fresh dump together.
4. Save: `project.save(project.folder + '/Studio_Up_new.toe')`. TouchDesigner's own Save
   writes `Studio_Up_new.2.toe` next to it instead, and those are ignored.

`td/sequencer.py` and the two shaders in `td/glsl/` are synced into Text DATs, so an edit to
the file lands in the running show without a rebuild. Anything else in `td/build_fx.py` needs
the rebuild line from the README, then a save.

`docs/tech/network.md` is what the dump says the file does.

## The beat tracker

Spec 002. A separate process hears the room and sends beats to TouchDesigner over OSC. Once:
`bash beat/install.sh` (uv, Python 3.10 under `beat/.venv`, madmom with the numpy it needs,
and the Swift audio tap, a few minutes). Then, in a terminal, for as long as the show runs:

    beat/.venv/bin/python beat/beat_osc.py

`--list` shows the inputs, `--device N` picks one; the default is the Mac's default input. It
prints a bpm every five seconds; `--file` runs it over a recording. `Beatsource` on fx picks
the mic or the system audio (a Core Audio tap, `beat/systap.swift`, built into the venv by
the install; the terminal app it runs from needs the system audio recording permission, asked
once). On the fx node, `Beatsync` turns the following on and off, `Beatoffset` pulls the chain
back by the tracker's lag, tuned by eye against the bounce, and `Bpm` shows what is heard.

## Reading a save without TouchDesigner

`/Applications/TouchDesigner.app/Contents/MacOS/toeexpand <file.toe>` writes `<file>.toe.dir`
next to it: one `.parm` text file per operator, `.table` for tables, `.n` for wiring. It works
on any save, including `Backup/`, with TouchDesigner closed. Run it on a copy outside the repo.
The json dump stays the main read because it carries evaluated values; this is for history.
