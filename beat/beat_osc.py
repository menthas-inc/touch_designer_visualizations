"""Hear the room, find the beat, tell TouchDesigner. Spec 002.

    beat/.venv/bin/python beat/beat_osc.py            # the Mac's default input
    beat/.venv/bin/python beat/beat_osc.py --list     # the inputs, by index
    beat/.venv/bin/python beat/beat_osc.py --device 0
    beat/.venv/bin/python beat/beat_osc.py --file song.wav   # the same analysis over a file, for testing

Every STEP seconds the last WINDOW seconds are analysed: madmom's beat network (the online,
forward-only one, fed as the audio arrives) gives a beat activation per 10 ms; a comb filter
over the window gives the tempo, 81 to 160, and the tempo stays where it was while that is
still a strong candidate (a section's off-beat figure can top the comb filter for a few bars:
on the test track 156 took over 128 for 15 s); the DBN beat tracker, held within 4 percent of
that tempo, places the beats, and a straight line through them gives the period to a tenth
of a bpm and the phase; the period used is the median of the last MEMORY such fits, since the
tempo in the room hardly moves over a minute. From there the beats are predicted ahead and sent as they fall, one
OSC message each to 127.0.0.1:7400:
    /beat <bpm> <kind>     kind 1 = beat (2, a downbeat, is not detected)
Latency does not matter here and a steady number does, so there is no causal tracker: an
earlier version ran BeatNet's particle filter per hop and read 125 to 160 on a 128 bpm track
(2026-11-10). Ctrl-C stops.
"""
import argparse
import collections
import queue
import threading
import time

import numpy as np
import sounddevice as sd
from madmom.audio.signal import Signal
from madmom.features.beats import DBNBeatTrackingProcessor, RNNBeatProcessor
from madmom.features.tempo import TempoEstimationProcessor
from pythonosc.udp_client import SimpleUDPClient

HOST, PORT = "127.0.0.1", 7400
BPM_RANGE = (81, 160)  # the comb filter looks only here, so 64 reads as 128 and 180 as 90
SR, FPS = 44100, 100  # what madmom's network was trained on
STEP, WINDOW = 5.0, 30.0  # seconds between analyses, seconds analysed
MEMORY = 12  # reliable fits the period is the median of: a minute at STEP
STICK = 0.6  # keep the last tempo while a candidate within 4 percent of it has this much of the top strength


def pick_tempo(candidates, prev):
    """The strongest tempo, unless one near `prev` is still strong (candidates: rows of bpm,
    strength, strongest first, as madmom's comb filter returns them)."""
    near = [(b, s) for b, s in candidates if prev and abs(b - prev) <= 0.04 * prev and s >= STICK * candidates[0][1]]
    return float(near[0][0] if near else candidates[0][0])


def analyse(act, tempo, t_end, prev=None):
    """(period, time of the last beat, comb tempo) for `act`, the activation of the window
    ending at t_end. None when the window is unreliable: too few beats, or beats whose line
    disagrees with the comb tempo by over 2 percent, as happens while an off-beat figure
    confuses both; the caller then keeps the last good fit."""
    bpm = pick_tempo(tempo(act), prev)
    beats = DBNBeatTrackingProcessor(fps=FPS, min_bpm=bpm * 0.96, max_bpm=bpm * 1.04)(act)
    if len(beats) < 8:
        return None
    period = np.polyfit(np.arange(len(beats)), beats, 1)[0]  # the line through the beats: finer than the 10 ms grid
    if abs(60 / period - bpm) > 0.02 * bpm:
        return None
    return period, t_end - len(act) / FPS + beats[-1], bpm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=None, help="input index from --list; default: the system's")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--file", help="analyse this audio file instead of listening; prints a tempo per step")
    args = ap.parse_args()
    if args.list:
        print(sd.query_devices())
        return

    rnn = RNNBeatProcessor(online=True)
    tempo = TempoEstimationProcessor(fps=FPS, min_bpm=BPM_RANGE[0], max_bpm=BPM_RANGE[1])
    act = np.zeros(0, dtype=np.float32)
    step, frames = int(STEP * SR), int(WINDOW * FPS)

    prev = None  # the last comb tempo, for pick_tempo
    periods = collections.deque(maxlen=MEMORY)

    if args.file:
        y = np.asarray(Signal(args.file, sample_rate=SR, num_channels=1), dtype=np.float32)
        for i in range(0, len(y) - step + 1, step):
            act = np.append(act, rnn(y[i:i + step], reset=False))[-frames:]
            t_end = (i + step) / SR
            fit = analyse(act, tempo, t_end, prev) if len(act) >= frames / 2 else None
            prev = fit[2] if fit else prev
            if fit:
                periods.append(fit[0])
            print(f"{t_end:6.1f}s  " + (f"{60 / np.median(periods):6.2f} bpm (this window {60 / fit[0]:.2f}), last beat at {fit[1]:.3f}" if fit else "held"), flush=True)
        return

    client = SimpleUDPClient(HOST, PORT)
    blocks = queue.Queue()
    lock = threading.Lock()
    fit = [None]  # (period, time of a beat, comb tempo), replaced at every reliable step
    HOLD = 6  # unreliable steps in a row before the beats stop: 30 s of silence or confusion

    def emit():  # predicted beats, sent as they fall, from the latest fit
        while True:
            with lock:
                cur = fit[0]
            if cur is None:
                time.sleep(0.1)
                continue
            period, anchor = cur[:2]
            nxt = anchor + period * (np.floor((time.time() - anchor) / period) + 1)
            time.sleep(max(0.0, nxt - time.time()))
            with lock:
                if fit[0] is not cur:
                    continue  # a new fit landed meanwhile; let it place the beat
            client.send_message("/beat", [60.0 / period, 1])

    threading.Thread(target=emit, daemon=True).start()
    with sd.InputStream(device=args.device, channels=1, samplerate=SR, blocksize=step // 10, dtype="float32",
                        callback=lambda indata, nframes, t, status: blocks.put(indata[:, 0].copy())):
        print("listening on", sd.query_devices(args.device if args.device is not None else sd.default.device[0])["name"],
              "-> osc", HOST, PORT, flush=True)
        buf = np.zeros(0, dtype=np.float32)
        held = 0
        while True:
            buf = np.append(buf, blocks.get())
            if len(buf) < step:
                continue
            t_end = time.time()
            act = np.append(act, rnn(buf[:step], reset=False))[-frames:]
            buf = buf[step:]
            new = analyse(act, tempo, t_end, prev) if len(act) >= frames / 2 else None
            held = 0 if new else held + 1
            if new:
                periods.append(new[0])
                new = (float(np.median(periods)), new[1], new[2])
            if new or held >= HOLD:
                prev = new[2] if new else None
                periods.clear() if not new else None
                with lock:
                    fit[0] = new
            print(f"{60 / new[0]:6.2f} bpm" if new else ("held" if fit[0] else "listening..."), flush=True)


if __name__ == "__main__":
    c = [(153.8, 1.0), (84.5, 0.98), (127.7, 0.9)]
    assert pick_tempo(c, None) == 153.8 and pick_tempo(c, 128.0) == 127.7 and pick_tempo(c, 100.0) == 153.8
    main()
