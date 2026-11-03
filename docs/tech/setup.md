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
