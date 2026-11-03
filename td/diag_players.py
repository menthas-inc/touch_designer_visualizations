"""Print what both players are doing right now. Run it while a frozen clip is on screen:
    exec(open('~/dev/studio_visuals/td/diag_players.py').read())
"""
import os

fx = op("/project1/fx")
st = fx.fetch("state", {})
print("current player", st.get("player"), "lead", st.get("lead"))
for g, sel in (st.get("sel") or {}).items():
    print(g, "effects on:", {n: {k: v for k, v in d.items() if k != "Enable"} for n, d in sel.items() if d.get("Enable") and n != "framing"})
print("xfade active:", {g: int(fx.op("xfade_" + g).par.Active) for g in ("outer", "inner")})
for n in "AB":
    p = fx.op("player" + n)
    info = fx.op("diag_info") or fx.create(infoCHOP, "diag_info")
    info.par.op = p.path
    chans = {c.name: round(c[0], 2) for c in info.chans() if c.name in ("index", "true_index", "length", "fps", "open", "playing", "cue_point")}
    print(n, os.path.basename(p.par.file.eval())[:30], "play", int(p.par.play), "cue", int(p.par.cue),
          "cuepoint", p.par.cuepoint.eval(), "speed", p.par.speed.eval(), "plan", st.get("plan", {}).get(n), chans)
    print("   errors:", p.errors() or "none", "| warnings:", p.warnings() or "none")
