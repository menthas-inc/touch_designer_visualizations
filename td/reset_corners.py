"""Clear the corner drags on the four strips, leaving each one's base rectangle.

Run inside TouchDesigner, from the Textport:
    exec(open(project.folder + '/../td/reset_corners.py').read())

Every strip's base rectangle is a tall column, and on top of that its bottom corners were
dragged up to the top 15 percent of the frame. This removes the drags. The dragged values stay
in git (td/network.json and TD_Mapping/Studio_Up.toe), which is the SV-2 backup. Base sizes
are not touched: Rectangle2 is an 86 by 70 box and Rectangle4 a half-height column, and they
will look like that afterwards until someone sizes them in the room.
"""
STRIPS = ("item1", "item2", "item4", "item5")

for item in STRIPS:
    shape = op("/project1/kantanMapper1/project/allShapes/" + item)
    before = shape.op("keyOffset").text.replace("\n", " | ")
    shape.Reset(key=True)
    # Reset only clears the table; the material reads the homography, so recompute it.
    shape.ext.Transform.findRectHomography(rectSop=shape.op("keyHandles"))
    print(shape.ext.Shape.Name, "corners cleared; was:", before)
