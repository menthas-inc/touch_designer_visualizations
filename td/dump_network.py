"""Write the open TouchDesigner network to td/network.json so it can be read outside TD.

Run inside TouchDesigner, from the Textport:
    exec(open('~/dev/studio_visuals/td/dump_network.py').read())

Records every operator under / except the UI and system trees: type, position, flags,
non-default parameters (with expression, bind or export source where one is set), input
wiring by connector index, and the text of DATs. Sorted by path so the file diffs cleanly.
"""
import json
import os

SKIP_TOP = {"ui", "sys", "local"}
MAX_DAT_CHARS = 200000  # the Kantan extensions are 600 lines; 20000 cut them short
OUT = "~/dev/studio_visuals/td/network.json"

# Scripts exec'd in the Textport share its globals, so a stray `project = ...` in one of them
# hides TouchDesigner's own `project` for every later one. Undo that before using it.
if not hasattr(project, "folder"):
    del project


def par_record(p):
    rec = {}
    mode = p.mode
    if mode == ParMode.EXPRESSION:
        rec["expr"] = p.expr
    elif mode == ParMode.EXPORT:
        src = p.exportSource
        rec["export"] = src.path if src is not None else None
    elif mode == ParMode.BIND:
        rec["bind"] = p.bindExpr
    try:
        rec["val"] = p.val
        json.dumps(rec["val"])
    except Exception:
        rec["val"] = str(p.eval())
    return rec


def op_record(o):
    rec = {
        "type": o.OPType,
        "optype": o.type,
        "pos": [o.nodeX, o.nodeY],
    }
    flags = {k: getattr(o, k) for k in ("bypass", "lock", "display", "render", "viewer") if getattr(o, k, False)}
    if flags:
        rec["flags"] = flags
    if o.comment:
        rec["comment"] = o.comment
    pars = {}
    try:
        for p in o.pars():
            if p.isDefault and p.mode == ParMode.CONSTANT:
                continue
            if p.name == "pageindex":
                continue
            pars[p.name] = par_record(p)
    except Exception as e:
        rec["pars_error"] = str(e)
    if pars:
        rec["pars"] = pars
    wires = []
    for i, conn in enumerate(o.inputConnectors):
        for c in conn.connections:
            wires.append([i, c.owner.path, c.index])
    if wires:
        rec["inputs"] = wires
    if o.isDAT:
        try:
            text = o.text
            rec["text"] = text[:MAX_DAT_CHARS]
            if len(text) > MAX_DAT_CHARS:
                rec["text_truncated"] = len(text)
        except Exception:
            pass
    return rec


def walk(comp, out):
    for child in comp.children:
        out[child.path] = op_record(child)
        if child.isCOMP:
            walk(child, out)


ops = {}
for top in op("/").children:
    if top.name in SKIP_TOP:
        continue
    ops[top.path] = op_record(top)
    walk(top, ops)

doc = {
    "project": project.name,
    "folder": project.folder,
    "td_version": app.version,
    "op_count": len(ops),
    "ops": dict(sorted(ops.items())),
}
with open(OUT, "w") as f:
    json.dump(doc, f, indent=1, sort_keys=False)
print("dumped", len(ops), "operators to", OUT)
