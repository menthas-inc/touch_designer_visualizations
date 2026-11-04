"""Where the frame time goes. Run in the Textport during a slow moment:
exec(open('~/dev/studio_visuals/td/diag_cook.py').read())
Lists the operators under /project1 with the longest last cook, CPU and GPU, in ms.
"""
_rows = []
_kids = op("/project1").findChildren(maxDepth=12)
for _o in _kids:
    _rows.append((_o.cookTime + _o.gpuCookTime, _o.cookTime, _o.gpuCookTime, _o.cookAbsFrame, _o.path))
_rows.sort(reverse=True)
print("fps target", project.cookRate, "| frame", absTime.frame, "| ops", len(_kids), "| top cooks (total, cpu, gpu ms, last cook frame)")
for _t, _c, _g, _f, _p in _rows[:20]:
    print(f"{_t:7.2f} {_c:7.2f} {_g:7.2f} {_f:8d}  {_p}")
for _n in "AB":
    _p = op("/project1/fx/player" + _n)
    print(_n, "speed", _p.par.speed.eval(), "hw", _p.par.hwdecode.eval(), _p.par.file.eval().split("/")[-1])
