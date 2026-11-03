# 001 tasks

- [ ] T1 `td/clip_stats.py` and `td/clips.json` for the 74 clips; a test on a synthetic clip
      made with ffmpeg (black then white) checks the buckets. AC-2 input. DEV-3, QUAL-1.
- [ ] T2 `td/sequencer.py` pure layer: `Playlist`, `plan_segment`, `window_stats`, `is_bright`,
      `choose`, `reroll`; `tests/test_sequencer.py` covers AC-2, AC-3, AC-5 and the clamps.
      QUAL-1.
- [ ] T3 `td/build_fx.py` part one: `fx` container, players, per-group `cur`, `nxt`, `xfade`,
      `fit`, `framing`, limiter, `out`; textures repointed; preview shows video through the
      new path. AC-7, SV-2.
- [ ] T4 `td/build_fx.py` part two: the thirteen effect Bases in order, each checked on the
      preview with `Enable` on by hand. AC-3.
- [ ] T5 `td/glsl/xfade.glsl`, the smear loop, the three timers and callbacks, `Fx` glue in
      `sequencer.py`; the sequencer runs on start. AC-4.
- [ ] T6 delete the old chain (impl-spec 4), save, dump, `docs/tech/network.md` rewritten for
      the new network. DEV-2, SV-1.
- [ ] T7 AC-1 and AC-4 log: a Script CHOP writes the per-group mean per frame and flags black
      and repeated frames in transition windows to `td/run.log`; run 10 minutes on the
      preview, read the log. AC-1, AC-4, AC-6.
