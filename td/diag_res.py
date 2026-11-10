"""Resolution along the path, file to screen. Run in the Textport:
    exec(open('~/dev/studio_visuals/td/diag_res.py').read())
"""
fx = op('/project1/fx')
print(app.product, app.build, "| TOP cap", "1280 (non-commercial)" if "Non-Commercial" in app.product else "none")
for name in ("playerA", "playerB", "playerC", "panA_outer", "fitA_outer", "frameA_outer", "wpanA_outer", "wfitA_outer", "winA_outer",
             "chain1_outer", "xfade_outer", "spice_outer", "limiter_outer", "room_outer", "bounce_outer", "out_outer",
             "upside_outer1", "orient_outer1", "orient_inner1"):
    o = fx.op(name)
    print(f"  {name:14s} {o.width} x {o.height}" if o else f"  {name:14s} missing")
for path in ("/project1/kantanMapper1/project/render1", "/project1/kantanMapper1/project/render2", "/project1/kantanMapper1/out1"):
    o = op(path)
    print(f"  {path.split('/')[-1]:14s} {o.width} x {o.height}")
for path in ("/project1/window", "/project1/kantanMapper1/project/window1"):
    w = op(path)
    print(f"  {path:40s} size {w.par.size.eval()} {w.par.winw.eval()} x {w.par.winh.eval()} open {w.isOpen}")
for m in monitors:
    print(f"  monitor {m.index} {m.description!r} {m.width} x {m.height} scale {m.scaleFactor} primary {m.isPrimary}")
print("  playerA file:", fx.op("playerA").par.file.eval())
