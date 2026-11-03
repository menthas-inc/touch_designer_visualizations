# Setup

As it actually stands on 2026-11-03: nothing is installed and the `.toe` is not in the repo yet.

## Intended loop

1. Install TouchDesigner (non-commercial license is free and runs on macOS).
2. Put the `.toe` at the repo root.
3. Run `td/dump_network.py` in the Textport. It writes the network as text into `td/`.
4. Changes arrive as scripts in `td/`, run the same way. Commit the script and the fresh dump.

Steps 3 and 4 do not exist yet. They are the first thing to build once 1 and 2 are done.
