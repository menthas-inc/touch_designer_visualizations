"""One-time clip curation across VJ_Visuals and Not_Used.

    python3 td/curate.py                    # builds TD_Mapping/curate/index.html and opens it
    python3 td/curate.py apply <selection.json>

The page shows every clip from both folders with three frames and its length, the show's
ticked and Not_Used's not. Untick what goes, tick what comes back, press Save: the browser downloads selection.json. Applying it moves unticked
clips to Not_Used, ticked ones back to VJ_Visuals, and updates td/clips.json (stats measured
for anything coming back). Keys are paths relative to TD_Mapping, as in the table.
"""
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clip_stats import MOVIE_EXT, probe, stats_for  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TD = os.path.join(HERE, "..", "TD_Mapping")
TABLE = os.path.join(HERE, "clips.json")
KEEP, GONE = "VJ_Visuals", "Not_Used"
OUT = os.path.join(TD, "curate")
FRAMES = (0.2, 0.5, 0.8)


def clips():
    for folder in (KEEP, GONE):
        for dirpath, _, files in os.walk(os.path.join(TD, folder)):
            for f in sorted(files):
                if os.path.splitext(f)[1].lower() in MOVIE_EXT:
                    yield os.path.relpath(os.path.join(dirpath, f), TD)


def build():
    thumbs = os.path.join(OUT, "thumbs")
    os.makedirs(thumbs, exist_ok=True)
    rows = []
    for i, key in enumerate(clips()):
        path = os.path.join(TD, key)
        length = probe(path)[0]
        imgs = []
        for j, at in enumerate(FRAMES):
            # cached by the file's name, which survives a move between the folders; by list index
            # it did not, and after a move every card showed another clip's frames (2026-11-10)
            png = os.path.join(thumbs, f"{hashlib.md5(os.path.basename(key).encode()).hexdigest()[:12]}_{j}.jpg")
            if not os.path.exists(png):
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{length * at:.2f}", "-i", path, "-frames:v", "1",
                                "-vf", "scale=240:240:force_original_aspect_ratio=decrease", "-q:v", "4", png], check=False)
            imgs.append(os.path.relpath(png, OUT))
        rows.append((key, length, imgs))
        print(key, round(length, 1), "s")
    cards = "\n".join(
        f'<label class="card {"gone" if k.startswith(GONE) else ""}"><input type="checkbox" value="{html.escape(k)}"{"" if k.startswith(GONE) else " checked"}>'
        f'<div class="imgs">{"".join(f"<img src=\"{html.escape(p)}\">" for p in imgs)}</div>'
        f'<div class="meta"><b>{k.split("/")[0]}{"/Long" if "/Long/" in k else ""}</b> {length:.0f} s<br>'
        f'<span>{html.escape(os.path.basename(k))}</span></div></label>'
        for k, length, imgs in rows)
    page = f"""<!doctype html><meta charset="utf-8"><title>curate</title>
<style>
body{{font:14px -apple-system,sans-serif;background:#111;color:#ddd;margin:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(760px,1fr));gap:12px}}
.card{{display:flex;gap:10px;align-items:center;background:#1c1c1c;padding:8px;border:2px solid transparent}}
.card.gone{{background:#2a1a1a}}
.card:has(input:not(:checked)){{opacity:.35;border-color:#a33}}
.card input{{width:22px;height:22px}}
.imgs{{display:flex;gap:4px}} .imgs img{{height:240px;width:240px;object-fit:contain;background:#000}}
.meta span{{color:#888;font-size:11px;word-break:break-all}}
#bar{{position:sticky;top:0;background:#111;padding:8px 0;margin-bottom:8px;display:flex;gap:16px;align-items:center}}
button{{font-size:16px;padding:8px 16px}}
</style>
<div id="bar"><button onclick="save()">Save selection.json</button><span id="n"></span>
<span>red cards are in Not_Used now; ticked means in the show after apply</span></div>
<div class="grid">{cards}</div>
<script>
const boxes=[...document.querySelectorAll('input')];
const count=()=>document.getElementById('n').textContent=boxes.filter(b=>b.checked).length+' of '+boxes.length+' ticked';
boxes.forEach(b=>b.onchange=count);count();
function save(){{const sel={{keep:boxes.filter(b=>b.checked).map(b=>b.value),drop:boxes.filter(b=>!b.checked).map(b=>b.value)}};
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(sel,null,1)],{{type:'application/json'}}));
a.download='selection.json';a.click();}}
</script>"""
    index = os.path.join(OUT, "index.html")
    with open(index, "w") as fh:
        fh.write(page)
    print("wrote", index, "with", len(rows), "clips")
    return index


def apply(selection):
    with open(selection) as fh:
        sel = json.load(fh)
    with open(TABLE) as fh:
        table = json.load(fh)
    moved = []
    for key in sel["drop"]:
        if key.startswith(KEEP) and os.path.exists(os.path.join(TD, key)):
            dst = os.path.join(TD, GONE, os.path.basename(key))
            shutil.move(os.path.join(TD, key), dst)
            moved.append(("out", key))
        table.pop(key, None)
    for key in sel["keep"]:
        if key.startswith(GONE) and os.path.exists(os.path.join(TD, key)):
            dst_key = os.path.join(KEEP, os.path.basename(key))
            shutil.move(os.path.join(TD, key), os.path.join(TD, dst_key))
            table[dst_key] = stats_for(os.path.join(TD, dst_key))
            moved.append(("back", dst_key))
    with open(TABLE, "w") as fh:
        json.dump(table, fh, indent=1, sort_keys=True)
    for how, key in moved:
        print(how, key)
    print(len(table), "clips in the table")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "apply":
        apply(sys.argv[2])
    else:
        subprocess.run(["open", build()])
