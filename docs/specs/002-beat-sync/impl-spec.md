# 002 Beat sync, implementation

## The tracker

Latency does not matter for this rig and a steady tempo does, so the tracker is not causal.
The first version (2026-11-06) was BeatNet's real-time particle filter, bpm from inter-beat
intervals; on a 128 bpm track it read 125 to 160 and dropped beats (2026-11-10, owner's test
on `ifax! - エミュー`). madmom's comb-filter tempo over a 30 s window read 128 on every window
of the same track, so that is the design now. madmom needs Python 3.10 or older, so the
tracker runs as its own process, a sidecar, in its own environment, and talks to
TouchDesigner over OSC. TouchDesigner's own Python stays untouched (DEV-1, and the free
licence is fine with OSC).

- `beat/beat_osc.py`: hears the mic (sounddevice, the Mac's default input or `--device`) or
  the system audio: `beat/systap.swift`, a Core Audio process tap on everything the Mac
  plays, built by the install into `beat/.venv/bin/systap`, piped as raw float32 and
  resampled to 44100 Hz. The fx par `Beatsource` (mic, system) picks: `osc_out` sends
  `/source` to port 7401 on change and in answer to the `/hello` the tracker sends at start,
  and the tracker switches its capture and starts its analysis over (owner, 2026-11-10).
  Either way it is 44100 Hz mono from there. Every 5 s, madmom's online beat network turns the new audio into
  a beat activation (10 ms frames), kept for the last 30 s; a comb filter over that gives the
  tempo, 81 to 160, held at the previous value while a candidate within 4 percent of it keeps
  60 percent of the top strength (an off-beat figure can top the filter for a few bars); the
  DBN beat tracker, within 4 percent of that tempo, places the beats, and a line through them
  gives the period to about 0.1 bpm and the phase. A window whose line disagrees with the comb
  tempo by over 2 percent is held (the last fit stays; after six held in a row the beats stop),
  and the period sent is the median of the last twelve good windows, since the tempo in the
  room hardly moves over a minute (owner, 2026-11-10). On the test track this reads 127.8 to
  128.1 throughout, where single windows wander to 129.6. A thread then sends the predicted
  beats as they fall, `/beat bpm kind` to `127.0.0.1:7400`, `kind` always 1 (downbeats are not
  detected). `--device` picks the input, `--list` lists them, `--file` runs the same analysis
  over a recording and prints a tempo per step, which is the test. `beat/.venv` is made by
  `beat/install.sh` (uv, Python 3.10, the pinned numpy madmom needs); both ignored by git
  except the scripts.

## TouchDesigner

- `beat_in`, an OSC In DAT on port 7400 with `beat_in_callbacks`, which calls
  `sequencer.on_beat(bpm, kind)`, and on `/hello` `sequencer.send_source()`, which sends
  `Beatsource` through `osc_out` (OSC Out DAT, 127.0.0.1:7401); `try_pars` sends it on change.
- The sequencer keeps `st["beat"] = {"t": absTime.seconds, "bpm": ..., "n": count}` and
  exposes, read by expressions every frame:
  - `beat_phase()`: `None` when sync is off or the last beat is older than 3 s, else
    `((now - t + Beatoffset) * bpm / 60) % 1`. A positive offset says the tracker is late by
    that much, so the beat is taken to have been earlier.
  - `beats_since(t0)`: beats elapsed since a time, for the spice.
  - `lfo_rate(free, beats)`: `bpm / 60 / beats` when synced, else `free`. Every LFO's
    frequency parameter becomes this expression with its own beat count.
  - `beat_pulse()`: `exp(-(time since beat) / 0.12)` when synced, else 0, for the bounce.
  - `reroll_seconds()`: 32 beats when synced, else `Rerollevery`.
- `spice_env` takes `beats`: when a beat phase is known the swell term uses beats since the
  current part began, one swell per two beats; the rise, the hold and the fall stay.
- `bounce_g`: a Transform TOP after `room_g`, scale `1 + Beatbounce * beat_pulse()`, edges
  mirrored.
- fx pars: `Beatsync` toggle (off), `Beatoffset` (seconds, -0.5 to 0.5, 0), `Beatbounce`
  (0 to 0.1, 0.03), `Bpm` (set by `on_beat`, a readout).
- Rates slide: the LFO CHOP changes frequency without a phase jump, and `beat_phase` going
  `None` only changes rates, so sync dropping or returning never cuts (AC-2).

## Pure, tested

`beat_phase_of(now, t, bpm, offset)`, `lfo_rate_of(free, beats, bpm)`, `spice_env(f,
pulses, beat=None)`: tests in `tests/test_sequencer.py`.

## Principles

DEV-1: the sidecar is the smallest way to run a PyTorch tracker beside a 3.11 TouchDesigner.
SV-1: the TD side is in `build_fx.py` and `sequencer.py` as everything else; the sidecar is a
script and an install script. SV-3: the tracker is a separate process; AC-3 checks the frame
rate. SV-2: nothing touches the mapping.
