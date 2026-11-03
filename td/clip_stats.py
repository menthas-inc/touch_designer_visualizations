"""Measure every clip once, offline, so the sequencer can choose before a clip plays.

    python3 td/clip_stats.py            # writes td/clips.json for TD_Mapping/VJ_Visuals
    python3 td/clip_stats.py <root> <out.json>

Per clip: length and frame rate from ffprobe; per 10 second bucket the mean and the high
percentile of luma (ffmpeg signalstats, one frame a second, 160 px wide); a motion score (mean
frame-to-frame difference at 10 fps). Values are 0 to 1. Keys are paths relative to the root's
parent (TD_Mapping), so the table works on any machine.
"""
import json
import os
import subprocess
import sys

MOVIE_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
BUCKET = 10.0


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=avg_frame_rate:format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    num, den = info["streams"][0]["avg_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    return float(info["format"]["duration"]), fps


def samples(path, vf):
    """Run ffmpeg with a signalstats filter chain and yield (time, {key: value}) per frame."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", vf + ",metadata=print:file=-", "-f", "null", "-"],
        capture_output=True, text=True, check=True).stdout
    t, vals = None, {}
    for line in out.splitlines():
        if line.startswith("frame:"):
            if vals:
                yield t, vals
            vals = {}
            t = float(line.split("pts_time:")[1].split()[0])
        elif "=" in line:
            k, v = line.split("=", 1)
            vals[k.split(".")[-1]] = float(v)
    if vals:
        yield t, vals


def stats_for(path):
    length, fps = probe(path)
    buckets = []
    for t, v in samples(path, "fps=1,scale=160:-2,signalstats"):
        i = int(t // BUCKET)
        while len(buckets) <= i:
            buckets.append({"n": 0, "mean": 0.0, "high": 0.0})
        b = buckets[i]
        b["n"] += 1
        b["mean"] += v["YAVG"] / 255.0
        b["high"] = max(b["high"], v["YHIGH"] / 255.0)
    for b in buckets:
        b["mean"] = round(b["mean"] / max(b["n"], 1), 4)
        b["high"] = round(b["high"], 4)
        del b["n"]
    diffs = [v["YAVG"] / 255.0 for _, v in samples(path, "fps=10,scale=160:-2,tblend=all_mode=difference,signalstats")]
    motion = round(sum(diffs[1:]) / max(len(diffs) - 1, 1), 4)  # frame 0 differs from nothing
    return {"length": round(length, 2), "fps": round(fps, 3), "motion": motion, "buckets": buckets}


def main(root, out):
    base = os.path.dirname(os.path.abspath(root))
    table = {}
    for dirpath, _, files in os.walk(root):
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in MOVIE_EXT:
                full = os.path.join(dirpath, f)
                key = os.path.relpath(full, base)
                try:
                    table[key] = stats_for(full)
                except subprocess.CalledProcessError as e:
                    print("skipped", key, e.stderr.strip()[:200], file=sys.stderr)
                    continue
                print(key, table[key]["length"], "s", "motion", table[key]["motion"])
    with open(out, "w") as fh:
        json.dump(table, fh, indent=1, sort_keys=True)
    print("wrote", len(table), "clips to", out)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "TD_Mapping", "VJ_Visuals")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "clips.json")
    main(root, out)
