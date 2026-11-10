# 002 Beat sync, implementation

## The tracker

Real-time beat tracking is a solved-enough problem: BeatNet (CRNN plus a particle filter,
Heydari 2021), BeatNet+ (2024), BEAST (streaming transformer, 2024) and madmom's online RNN
all sit around 75 to 80% beat F1 with under 50 ms latency. BeatNet is the one with a
maintained package and a real-time mode that takes audio chunks, so it is the pick. It needs
PyTorch, librosa and madmom, and madmom needs Python 3.10 or older, so the tracker runs as
its own process, a sidecar, in its own environment, and talks to TouchDesigner over OSC.
TouchDesigner's own Python stays untouched (DEV-1, and the free licence is fine with OSC).

- `beat/beat_osc.py`: sounddevice captures the chosen input (default: the Mac's default
  input) at 22050 Hz mono, feeds BeatNet in its real-time mode in 20 ms hops, and on every
  beat it reports sends `/beat bpm kind` to `127.0.0.1:7400`, `kind` 1 for a beat, 2 for a
  downbeat. Bpm is the median of the last eight inter-beat intervals. `--device` picks the
  input, `--list` lists them. `beat/.venv` is made by `beat/install.sh` (uv, Python 3.10,
  the pinned numpy madmom needs); both ignored by git except the scripts.

## TouchDesigner

- `beat_in`, an OSC In DAT on port 7400 with `beat_in_callbacks`, which calls
  `sequencer.on_beat(bpm, kind)`.
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
