# studio visuals

The TouchDesigner file that drives the four paper strips, and the scripts that build and run
it. The file is `TD_Mapping/Studio_Up_new.toe`; everything in it comes from `td/`.

## Running the show

Open the file in TouchDesigner. The sequencer starts on its own. Then, in the Textport
(Alt+T), one line each as needed:

| what | line |
|---|---|
| preview window on this screen | `exec(open('~/dev/studio_visuals/td/open_output.py').read())` |
| preview full screen, mouse on the screen you want | `w = op('/project1/window'); w.par.borders = False; w.par.size = next(n for n in w.par.size.menuNames if 'fill' in n.lower()); w.par.winclose.pulse(); w.par.winopen.pulse()` |
| close the preview | `op('/project1/window').par.winclose.pulse()` |
| projector output, on the extended display | `op('/project1/kantanMapper1/project/window1').par.winopen.pulse()` |
| close it | `op('/project1/kantanMapper1/project/window1').par.winclose.pulse()` |
| strips solid, for lining up the paper | `for it in ('item5', 'item4', 'item2', 'item1'): op('/project1/kantanMapper1/project/allShapes/' + it + '/parameters').par.Showtexture = False` |
| video back on the strips | the same line with `True` |
| rebuild the chain after a script change | `exec(open('~/dev/studio_visuals/td/build_fx.py').read())` |
| restart the sequencer | `op('/project1/fx/sequencer').module.start()` |
| save | `project.save('~/dev/studio_visuals/TD_Mapping/Studio_Up_new.toe')` |
| dump the network for git | `exec(open('~/dev/studio_visuals/td/dump_network.py').read())` |
| record five minutes | `exec(open('~/dev/studio_visuals/td/record.py').read())` |
| stop a recording early | `op('/project1/rec').par.record = 0; op('/project1/rec_cook').par.active = 0` |
| where the frame time goes | `exec(open('~/dev/studio_visuals/td/diag_cook.py').read())` |
| what the players are doing | `exec(open('~/dev/studio_visuals/td/diag_players.py').read())` |
| resolution at each step, file to screen | `exec(open('~/dev/studio_visuals/td/diag_res.py').read())` |

The knobs are on the `fx` node, `/project1/fx`: hover a parameter's name for what it does.
`Darkness`, `Roomdark` and `Roomcontrast` set the brightness for the room; the `Try` page
steps through effects and transitions by hand.

A recording is a Motion JPEG `.mov` in `TD_Mapping/Recordings/`; to send it:

    ffmpeg -i studio_<date>.mov -c:v libx264 -crf 20 -pix_fmt yuv420p studio_<date>.mp4

## The beat tracker

The chain can follow the music in the room. Once, from the repo root:

    bash beat/install.sh

Then, in a terminal, for as long as the show runs:

    cd ~/dev/studio_visuals && beat/.venv/bin/python beat/beat_osc.py

It prints a bpm every five seconds. `--list` shows the inputs, `--device N` picks one, the
Mac's default input is used otherwise; `--file song.wav` runs the same analysis over a
recording, to test it. On `fx`, turn `Beatsync` on, watch `Bpm`, and tune
`Beatoffset` until the bounce lands on the beat. Ctrl-C stops it.

## The clips

`TD_Mapping/VJ_Visuals/` is what plays, `Long/` inside it for clips over a minute;
`TD_Mapping/Not_Used/` is what does not. After adding or removing clips:

    python3 td/clip_stats.py

To pick through them by eye, a page with three frames per clip:

    python3 td/curate.py
    python3 td/curate.py apply ~/Downloads/selection.json

## Tests and docs

    python3 -m unittest discover tests

`docs/tech/network.md` says what the network does, `docs/tech/setup.md` how to work on it,
`docs/specs/` what was asked for and how it was built.
