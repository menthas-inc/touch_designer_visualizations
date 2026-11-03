"""Make the four strips full-height columns, keeping each one's x position.

Run inside TouchDesigner, from the Textport:
    exec(open('~/dev/studio_visuals/td/set_columns.py').read())

Widths are the saved ones, except Rectangle2, which was an 86 by 70 box and gets 300 like its
neighbours until it is sized in the room. Corner drags are untouched (run reset_corners.py
first if they are back).
"""
H = 1080
COLUMNS = {  # item: (width, centre x), canvas pixels
    "item5": (328, -694),
    "item4": (310, -187),
    "item2": (300, 302),
    "item1": (292, 753),
}

for item, (w, cx) in COLUMNS.items():
    shape = op("/project1/kantanMapper1/project/allShapes/" + item)
    shape.par.xformmatrixop.expr = (
        f"tdu.Matrix([{w}.0, 0.0, 0.0, 0.0, 0.0, {H}.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, {cx}.0, 0.0, 0.0, 1.0])"
    )
    # The editor rotates and scales around this pivot; keep it on the column's centre.
    shape.ext.Shape.Custompivotx = cx
    shape.ext.Shape.Custompivoty = 0
    print(shape.ext.Shape.Name, f"{w} x {H} at x={cx}")
