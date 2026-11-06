# 002 Beat sync

> Draft 1, 2026-11-05. Owner's brief: no VJ runs this, so it should react to the music itself.

## Why

Every rhythm in the chain is free-running: the clip changes, the mid-clip swaps, the spice
swells and the slow drifts all run on timers and LFOs at rates drawn once. The room has music
and the wall ignores it.

## What

A beat tracker listens to the room through the Mac's audio input and the chain follows the
beat it finds. Nothing is tapped or typed; when there is no music the chain runs as it does
today.

What follows the beat, when sync is on and a beat is being heard:

- **The spice swells** land on the beat, one swell every two beats, instead of their own
  exponential spacing. Count, length, cap and entry stay as they are.
- **The slow drifts** (the LFOs on feedback, displace, echo, mirror and chroma, and the two
  groups' pans) run at musical rates: one cycle per 16, 32, 64 or 128 beats, each drift at its
  own count, so they breathe with the track rather than near it.
- **The reroll tick** runs at 32 beats instead of a fixed 20 s, so mid-clip swaps start near
  a bar line.
- **A bounce** on the beat: both groups' pictures zoom a few percent on each beat and settle
  before the next. Small, and the one thing that visibly reacts. Its amount is a parameter,
  0 turns it off.

Two controls on the fx node, for the owner to tune on site:

- **Beatsync**, on or off. Off is exactly today's behaviour.
- **Beatoffset**, in seconds, either way. The tracker hears the beat late, by the distance to
  the speakers plus its own delay, and the offset pulls the chain back onto the beat. It is
  tuned by eye against the bounce.

A read-only **Bpm** shows what the tracker hears, 0 when it hears nothing.

## Not in this

Downbeats and bars (the tracker reports them, nothing uses them yet), onset or loudness
reaction, any change to which effects are chosen, and the clip changes themselves, which stay
on their own clock since a 7 to 22 s meld has no beat to land on.

## Acceptance criteria

- AC-1: with music playing and sync on, the bounce lands on the beat as heard in the room
  once the offset is tuned, and stays on it for a minute without drifting.
- AC-2: with sync off, or with no beat heard for 3 s, every rate and the spice are exactly as
  in spec 001; nothing jumps when sync drops or returns, rates slide over a few seconds.
- AC-3: the tracker runs on this Mac beside TouchDesigner at the frame rate spec 001 holds
  (SV-3): no dip in the top bar when it starts.
- AC-4: the tracker is started by one command and survives TouchDesigner restarting.
