# Setup

As it stands on 2026-11-03: TouchDesigner 2025.33230 is installed. The project lives in
`TD_Mapping/`, unzipped from the studio's export. `Studio_Up_new.toe` is the working file, saved
from this version. `Studio_Up.toe` (December 2025) is the file as received, from an older
TouchDesigner, kept untouched. `Backup/` is TouchDesigner's own autosave history. The source videos next to them are
on disk but not in git.

## The loop

1. Open `TD_Mapping/Studio_Up_new.toe` from this repo, so relative media paths resolve.
2. In the Textport (Alt+T), run one line:
   `exec(open('~/dev/studio_visuals/td/dump_network.py').read())`
   It writes `td/network.json`, every operator with its non-default parameters and wiring.
3. Changes arrive as scripts in `td/`, run with the same `exec` line. Commit the script and a
   fresh dump together.
4. Saving: `project.save('~/dev/studio_visuals/TD_Mapping/Studio_Up_new.toe')` in
   the Textport. TouchDesigner's own Save writes `Studio_Up_new.2.toe` next to it instead, and those are
   gitignored.

`docs/tech/network.md` is what the dump says the file does.

## The beat tracker

Spec 002. A separate process hears the room and sends beats to TouchDesigner over OSC. Once:
`bash beat/install.sh` (Python 3.10 under `beat/.venv`, a few minutes). Then, in a terminal,
for as long as the show runs:

    beat/.venv/bin/python beat/beat_osc.py

`--list` shows the inputs, `--device N` picks one; the default is the Mac's default input. It
prints a bpm every five seconds; `--file` runs it over a recording. On the fx node, `Beatsync` turns the following on and off, `Beatoffset`
pulls the chain back by the tracker's lag, tuned by eye against the bounce, and `Bpm` shows
what is heard.

## Reading a save without TouchDesigner

`/Applications/TouchDesigner.app/Contents/MacOS/toeexpand <file.toe>` writes `<file>.toe.dir`
next to it: one `.parm` text file per operator, `.table` for tables, `.n` for wiring. It works
on any save, including `Backup/`, with TouchDesigner closed. Run it on a copy outside the repo.
The json dump stays the main read because it carries evaluated values; this is for history.

