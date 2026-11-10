"""Hear the room, find the beat, tell TouchDesigner. Spec 002.

    beat/.venv/bin/python beat/beat_osc.py                  # the Mac's default input
    beat/.venv/bin/python beat/beat_osc.py --source system  # what the Mac is playing (a Chrome tab, say)
    beat/.venv/bin/python beat/beat_osc.py --list           # the inputs, by index
    beat/.venv/bin/python beat/beat_osc.py --device 0
    beat/.venv/bin/python beat/beat_osc.py --file song.wav  # the same analysis over a file, for testing

The source is also set from TouchDesigner: the fx par Beatsource sends /source mic|system to
port 7401, on change and in answer to the /hello this sends at start. "system" runs
beat/.venv/bin/systap, a Core Audio tap on everything the Mac plays, whatever the output
device (its first run asks for system audio recording permission for the terminal app).

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
import fractions
import os
import queue
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd
from madmom.audio.signal import Signal
from madmom.features.beats import DBNBeatTrackingProcessor, RNNBeatProcessor
from madmom.features.tempo import TempoEstimationProcessor
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from scipy.signal import resample_poly

HOST, PORT, CONTROL_PORT = "127.0.0.1", 7400, 7401  # beats out to TouchDesigner; /source in from it
BPM_RANGE = (81, 160)  # the comb filter looks only here, so 64 reads as 128 and 180 as 90
SR, FPS = 44100, 100  # what madmom's network was trained on
RATES = (16000, 22050, 24000, 32000, 44100, 48000, 88200, 96000)  # what a tap's measured rate is snapped to
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


def capture(source, device, blocks):
    """Start hearing `source` into `blocks` (float32 mono at SR, about a tenth of a second
    each). Returns (stop, description)."""
    if source == "system":
        tap = os.path.join(os.path.dirname(sys.executable), "systap")
        proc = subprocess.Popen([tap], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        head = proc.stderr.readline().decode().split()  # "rate 48000 channels 2", or the error
        if len(head) != 4:
            proc.terminate()
            raise RuntimeError("systap: " + " ".join(head))
        ch = int(head[3])
        what = ["system audio"]

        def pump():
            # the tap's own rate: neither its format nor its device says it truly (48000 and
            # 16000 were claimed while 44100 arrived, 2026-11-10), so time the frames: two
            # seconds of warm-up, three seconds measured, snapped to a standard rate, and
            # re-measured every ten seconds in case the output device changes
            n = ch * 4 * 1024
            ratio, held, t0, got = None, [], None, 0
            while True:
                raw = proc.stdout.read(n)
                if len(raw) < n:
                    return
                x = np.frombuffer(raw, dtype=np.float32).reshape(-1, ch).mean(axis=1)
                now = time.time()
                if t0 is None:
                    t0, warm = now, True
                    continue
                if warm:
                    if now - t0 > 2.0:
                        warm, t0, got = False, now, 0
                    continue
                got += len(x)
                if ratio is None:
                    held.append(x)
                if now - t0 >= (3.0 if ratio is None else 10.0):
                    rate = min(RATES, key=lambda r: abs(r - got / (now - t0)))
                    new = fractions.Fraction(SR, rate)
                    if new != ratio:
                        if ratio is not None:
                            print(f"tap rate now {rate} Hz", flush=True)
                        ratio, what[0] = new, f"system audio, {rate} Hz tap"
                    t0, got = now, 0
                    for h in held:
                        blocks.put(resample_poly(h, ratio.numerator, ratio.denominator).astype(np.float32) if ratio != 1 else h)
                    held = []
                elif ratio is not None:
                    blocks.put(resample_poly(x, ratio.numerator, ratio.denominator).astype(np.float32) if ratio != 1 else x)

        threading.Thread(target=pump, daemon=True).start()
        time.sleep(5.5)  # until the rate is known, so the name below is right
        return proc.terminate, what[0]
    stream = sd.InputStream(device=device, channels=1, samplerate=SR, blocksize=SR // 10, dtype="float32",
                            callback=lambda indata, nframes, t, status: blocks.put(indata[:, 0].copy()))
    stream.start()
    return stream.close, sd.query_devices(device if device is not None else sd.default.device[0])["name"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=None, help="input index from --list; default: the system's")
    ap.add_argument("--source", choices=("mic", "system"), default="mic", help="the mic (--device) or what the Mac plays")
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
    wanted = [args.source]  # the source TouchDesigner asks for, picked up by the loop

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
    dispatcher = Dispatcher()
    dispatcher.map("/source", lambda address, *a: wanted.__setitem__(0, str(a[0])) if a and a[0] in ("mic", "system") else None)
    server = ThreadingOSCUDPServer((HOST, CONTROL_PORT), dispatcher)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client.send_message("/hello", [args.source])  # TouchDesigner answers with its Beatsource

    source, stop = None, None
    buf = np.zeros(0, dtype=np.float32)
    held = 0
    while True:
        if wanted[0] != source:  # first time, or TouchDesigner switched it
            if stop:
                stop()
            source = wanted[0]
            try:
                stop, what = capture(source, args.device, blocks)
            except Exception as e:  # no tap built, no such device
                print(f"cannot hear {source}: {e}; staying on mic", flush=True)
                wanted[0] = source = "mic"
                stop, what = capture(source, args.device, blocks)
            act, buf, prev, held = act[:0], buf[:0], None, 0
            periods.clear()
            with lock:
                fit[0] = None
            print(f"listening to {what} -> osc {HOST} {PORT}", flush=True)
        try:
            buf = np.append(buf, blocks.get(timeout=1.0))
        except queue.Empty:
            continue
        if len(buf) < step:
            continue
        t_end = time.time()
        quiet = float(np.abs(buf[:step]).max()) < 1e-4
        act = np.append(act, rnn(buf[:step], reset=False))[-frames:]
        buf = buf[step:]
        new = analyse(act, tempo, t_end, prev) if len(act) >= frames / 2 and not quiet else None
        held = 0 if new else held + 1
        if new:
            periods.append(new[0])
            new = (float(np.median(periods)), new[1], new[2])
        if new or held >= HOLD:
            prev = new[2] if new else None
            periods.clear() if not new else None
            with lock:
                fit[0] = new
        print(f"{60 / new[0]:6.2f} bpm" if new else ("silence" + (" (if music is playing, allow system audio recording for this terminal app in Privacy & Security)" if quiet and source == "system" else "") if quiet else "held" if fit[0] else "listening..."), flush=True)


if __name__ == "__main__":
    c = [(153.8, 1.0), (84.5, 0.98), (127.7, 0.9)]
    assert pick_tempo(c, None) == 153.8 and pick_tempo(c, 128.0) == 127.7 and pick_tempo(c, 100.0) == 153.8
    main()
