"""Put the playlist video on the four strips.

Run inside TouchDesigner, from the Textport:
    exec(open(project.folder + '/../td/map_video.py').read())

Each strip is a Kantan rectangle whose Texture parameter names a TOP. The save had all four on
the orange alignment constant. /project1/switch1 is the strip-shaped (340 by 1080) cut of the
playing clip, auto-inverted when the clip is bright. Corner data is not touched (SV-2).
"""
STRIPS = ("item1", "item2", "item4", "item5")  # Rectangle1, 2, 4, 5. item3 and item6 are leftovers.
TEXTURE = "/project1/switch1"

for item in STRIPS:
    par = op("/project1/kantanMapper1/project/allShapes/" + item + "/parameters").par
    print(par.Name.eval(), par.Texture.eval(), "->", TEXTURE)
    par.Texture = TEXTURE
