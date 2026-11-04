"""Where the frame time goes. Run in the Textport during a slow moment:
exec(open('~/dev/studio_visuals/td/diag_cook.py').read())
Lists the operators under /project1 with the longest last cook, CPU and GPU, in ms.
"""
_rows = []
for _o in op("/project1").findChildren(depth=12):
    _c, _g = _o.cookTime, _o.gpuCookTime
    if _c + _g > 0.2:
        _rows.append((_c + _g, _c, _g, _o.path))
_rows.sort(reverse=True)
print("fps target", project.cookRate, "| top cooks (total, cpu, gpu ms)")
for _t, _c, _g, _p in _rows[:20]:
    print(f"{_t:7.2f} {_c:7.2f} {_g:7.2f}  {_p}")
for _n in "AB":
    _p = op("/project1/fx/player" + _n)
    print(_n, "speed", _p.par.speed.eval(), "hw", _p.par.hwdecode.eval(), _p.par.file.eval().split("/")[-1])
