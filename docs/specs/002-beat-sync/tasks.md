# 002 Beat sync, tasks

- [x] T1 `beat/install.sh` and `beat/beat_osc.py`: environment, capture, BeatNet real-time,
      OSC out; `--list` and `--device`. Verified against a played track with the Textport's
      OSC In DAT showing beats. AC-3, AC-4.
- [x] T2 sequencer: beat state, `on_beat`, `beat_phase`, `lfo_rate`, `beat_pulse`,
      `reroll_seconds`, `spice_env` with `beat`; pure functions tested. AC-2.
- [~] T3 build: `beat_in` and its callbacks, the four pars, LFO frequency expressions, the
      reroll length, `bounce_g`. Rebuilt with zero misses. AC-1, AC-2.
- [ ] T4 on site: offset tuned against the bounce, frame rate checked with the tracker
      running. AC-1, AC-3.
- [x] T5 docs: `docs/tech/network.md`, `docs/tech/setup.md` (how to start the tracker). SV-1.
