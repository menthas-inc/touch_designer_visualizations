# 001 tasks

- [x] T1 `td/clip_stats.py` and `td/clips.json` for the 74 clips; a test on a synthetic clip
      made with ffmpeg (black then white) checks the buckets. AC-2 input. DEV-3, QUAL-1.
- [x] T2 `td/sequencer.py` pure layer: `Playlist`, `plan_segment`, `window_stats`, `is_bright`,
      `choose`, `reroll`; `tests/test_sequencer.py` covers AC-2, AC-3, AC-5 and the clamps.
      QUAL-1.
- [x] T3 `td/build_fx.py`: `fx` container, players, per-group `cur`, `nxt`, fits, `xfade`,
      chain, limiter, `out`; textures repointed; the old chain deleted at the end; the sequencer
      started. One script, so the wall is never dark between tasks. AC-7, SV-2. Built, zero
      parameter misses, clips change on the preview.
- [x] T4 each effect checked on the wall through the `Try` page; ranges adjusted in `CORPUS`,
      LFOs added, keepchannel, pixelate and slope cut. The limiter checked (gain 0.62 on a
      bright clip). AC-3.
- [~] T5 the three transitions checked on the preview, a few clip changes watched. AC-4.
- [ ] T6 save, dump, `docs/tech/network.md` rewritten for the new network. DEV-2, SV-1.
- [ ] T7 AC-1 and AC-4 log: a Script CHOP writes the per-group mean per frame and flags black
      and repeated frames in transition windows to `td/run.log`; run 10 minutes on the
      preview, read the log. AC-1, AC-4, AC-6.
