#!/usr/bin/env python3
"""Inventory the extracted CD-DA soundtrack: duration, RMS, peak, silence check."""
import json
import os
import struct
import wave

M = json.load(open("build/extracted/tracks.json"))
print("%-9s %8s %9s %8s %8s  %s" % ("track", "frames", "dur", "RMS", "peak", "note"))
for t in M["tracks"]:
    if t["type"] != "AUDIO":
        continue
    p = os.path.join("build/extracted/audio", "track_%02d.wav" % t["number"])
    if not os.path.exists(p):
        print("track_%02d MISSING" % t["number"])
        continue
    w = wave.open(p, "rb")
    n = w.getnframes()
    d = w.readframes(n)
    s = struct.unpack("<%dh" % (len(d) // 2), d)
    rms = (sum(x * x for x in s) / len(s)) ** 0.5
    pk = max(abs(x) for x in s)
    note = "SILENCE" if rms < 20 else ("quiet" if rms < 500 else "music")
    print("track_%02d %8d %6d:%02d %8.0f %8d  %s" % (
        t["number"], n, n // 44100 // 60, (n // 44100) % 60, rms, pk, note))
