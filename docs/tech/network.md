# The network, as read from td/network.json

> What the file does, operator by operator, so the next change does not start from a dump.
> Re-read the dump before trusting a value here. Last read: 2026-11-03 from `Studio_Up_new.toe`,
> 5453 operators, of which 5379 are inside Kantan Mapper and 74 are ours.

## The picture

```
VJ_Visuals (53 clips) ──folderRaw──folder──shuffled──┐
VJ_Visuals/Long (21)  ──folderRaw1─folder1─shuffled1─┤
                                                     ▼
                    script1 (merge, shuffle, short clips twice) ──select1 (drop None)──playlist
                                                                                           │
playlist_index (count CHOP) ──chopto1──touchout1 ~~network~~ touchin1──datto1──► movie.file = playlist[index]
        ▲ advances when `remaining` (clip length minus frame) drops below 2 frames
        └ reset (button) jumps to reset_index (field)

movie ──┐
        switch2 ◄── button1 "Switch" picks the reel instead
fit2 ◄── moviefilein2 "Mesme x SL Reel_v3.mp4" (file missing)
        │
     movie_null
      ├── fit  (40 x 40)     ──analyze1──topto1──math1──invert ──► switch  = fit  or diff  (negative)
      └── fit1 (340 x 1080)  ──analyze2──topto2──math3──invert1 ──► switch1 = fit1 or diff1 (negative)
                                                                           │
                                   kantanMapper1: Rectangle1, 2, 4, 5 .Texture = /project1/switch1
                                                  ──► out1 ──► project/window1 (display 1, the projector)
```

## The playlist

- Two Folder DATs list every movie file under `VJ_Visuals` and `VJ_Visuals/Long`. Both lists
  are shuffled with a Sort DAT, seed 0, so the order is the same every launch.
- `script1_callbacks` concatenates them, shuffles again with Python's `random.shuffle` (not
  seeded, so this part differs per launch), and appends every short clip a second time. Result:
  127 rows. Long clips appear once, short clips twice.
- `movie` (Movie File In) plays row N at speed 0.75. N is `playlist_index`, a Count CHOP that
  increments when `remaining` (`info.length - info.index`) drops below 2 and loops at
  `playlist.numRows - 1`. The Reset button sets it to the number typed in `reset_index`.
- The index takes a detour through the network: `chopto1` to `touchout1` to `touchin1` to
  `datto1`, which is what `movie.file` actually reads. Touch In and Out are on default ports, so
  on one machine it is a loopback. It looks built for a second machine to follow the same index.
  If `touchin1` ever shows nothing, the playlist is stuck on one clip.
- `speed` (0.75 to 1.0 from clip length) is computed and not used by anything.

## The two cuts of the clip

`movie_null` is the clip (or the reel, when the Switch button is down). It is fitted twice,
both `fitoutside`, that is cropped to fill:

| chain | size | then | used by |
|---|---|---|---|
| `fit` | 40 x 40 | `diff` against `white` = negative | `switch`, Rectangle6 (hidden) |
| `fit1` | 340 x 1080 | `diff1` against `white` = negative | `switch1`, the four strips |

Each cut is analysed (`analyze` TOP, default is average) and the average goes through
`math` (`floor(avg + 0.6)`) and a Logic CHOP: average brightness at or above 0.4 flips the
Switch TOP to the negative. Bright clips are shown inverted, so the strips stay mostly dark.
Change the 0.6 preoffset in `math1` and `math3` to move the threshold.

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

### The six shapes, as saved

| item | name | base w x h at centre | corners | texture | orient | flip | tree |
|---|---|---|---|---|---|---|---|
| 1 | Rectangle1 | 292 x 1070 at (753, 3) | bottom corners raised 0.84 | switch1 (was constant1) | 2 | no | locked |
| 2 | Rectangle2 | 86 x 70 at (302, 344) | dragged up to 3.8 widths out | switch1 (was constant1) | 0 | no | locked |
| 3 | Rectangle3 | 130 x 62 at (-443, -635) | none | none (test grid) | 0 | no | unlocked, off canvas |
| 4 | Rectangle4 | 310 x 544 at (-187, 270) | bottom corners raised 0.74 | switch1 (was constant1) | 0 | yes | locked |
| 5 | Rectangle5 | 328 x 1078 at (-694, -1) | bottom corners raised 0.88 | switch1 (was constant1) | 2 | yes | locked |
| 6 | Rectangle6 | 58 x 56 at (0, -465) | none | switch (40 x 40) | 0 | no | locked, hidden |

What this means: the four strips start as tall rectangles and have their bottom corners dragged
up, so on the canvas each is a short band in the top 15 percent of the projector's frame, about
y = 370 to 540. The strip's long axis is the band's short on-screen axis, which is why the
340 x 1080 portrait cut is the right texture. That geometry fits a projector at a steep angle to
hanging strips, where the paper is foreshortened. **Which band is which physical strip, and which
way is up on each, is not in the file. Ask.** Rectangle3 and 6 are leftovers.

The "was constant1" column is the state the file arrived in: all four strips on the orange
Constant TOP, the alignment colour. `td/map_video.py` set them to `switch1`, saved in `Studio_Up_new.toe`.

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

- `project1` is the perform window's target and had `top = ./out1`, which does not exist.
  `open_output.py` points it at the mapper's output.
- Kantan's own output window, the Toggle Output button, is `project/window1`: borderless on
  display 1, which is the projector when one is attached.
- `/project1/window` (1920 x 1080) and `window1` (1080 x 1920) are two spare Window COMPs with no
  operator set. `open_output.py` uses the first as the laptop preview.

## Not in the zip

- `Mesme x SL Reel_v3.mp4`, the reel behind the Switch button.
- `mood_M_.png`, loaded by `mood_logo`, which nothing reads.
- `kantan.json`, the mapper's project file. Its embedded copy is Kantan's demo, not ours.
- The file last ran on a Windows machine (`C:/Users/.../...`). Folder paths re-resolve on load.
