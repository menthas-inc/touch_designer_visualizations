"""Hear the room, find the beat, tell TouchDesigner. Spec 002.

    beat/.venv/bin/python beat/beat_osc.py            # the Mac's default input
    beat/.venv/bin/python beat/beat_osc.py --list     # the inputs, by index
    beat/.venv/bin/python beat/beat_osc.py --device 0

BeatNet (Heydari 2021: a causal CRNN plus a particle filter) in 20 ms hops over the input at
22050 Hz. On every beat it finds, one OSC message to 127.0.0.1:7400:
    /beat <bpm> <kind>     kind 1 = beat, 2 = downbeat
bpm is the median of the last eight inter-beat intervals, 0 until there are two. Ctrl-C stops.
The tracker's own loop (BeatNet's stream mode) captures with pyaudio on the default device
and keeps its beats to itself, so this is that loop written out with sounddevice and the
particle filter's path read after each hop.
"""
import argparse
import queue
import statistics
import time

import numpy as np
import sounddevice as sd
import torch
from BeatNet.BeatNet import BeatNet
from pythonosc.udp_client import SimpleUDPClient

HOST, PORT = "127.0.0.1", 7400
KINDS = {1: 2, 2: 1}  # BeatNet's path marks a downbeat 1 and a beat 2; on the wire 1 is a beat, 2 a downbeat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=None, help="input index from --list; default: the system's")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        print(sd.query_devices())
        return

    est = BeatNet(1, mode="realtime", inference_model="PF", plot=[], thread=False)  # realtime: no stream of its own
    hop, win = est.log_spec_hop_length, est.log_spec_win_length
    window = np.zeros(win + 2 * hop, dtype=np.float32)
    hops = queue.Queue()
    client = SimpleUDPClient(HOST, PORT)
    beat_times, seen = [], 0

    def on_audio(indata, frames, t, status):
        hops.put(indata[:, 0].copy())

    with sd.InputStream(device=args.device, channels=1, samplerate=est.sample_rate, blocksize=hop,
                        dtype="float32", callback=on_audio):
        print("listening on", sd.query_devices(args.device if args.device is not None else sd.default.device[0])["name"],
              "-> osc", HOST, PORT)
        counter = 0
        while True:
            window = np.append(window[hop:], hops.get())
            counter += 1
            if counter < 5:
                continue
            with torch.no_grad():
                feats = torch.from_numpy(est.proc.process_audio(window).T[-1]).unsqueeze(0).unsqueeze(0).to(est.device)
                pred = est.model.final_pred(est.model(feats)[0]).cpu().detach().numpy()
            path = est.estimator.process(np.transpose(pred[:2, :]))
            if len(path) > seen:
                now = time.time()
                beat_times.append(now)
                beat_times[:] = beat_times[-9:]
                gaps = [b - a for a, b in zip(beat_times, beat_times[1:])]
                bpm = 60.0 / statistics.median(gaps) if gaps else 0.0
                for _, kind in path[seen:]:
                    client.send_message("/beat", [float(bpm), KINDS.get(int(kind), 1)])
                seen = len(path)
                print(f"{bpm:6.1f} bpm", "downbeat" if int(path[-1][1]) == 1 else "beat", flush=True)


if __name__ == "__main__":
    main()
