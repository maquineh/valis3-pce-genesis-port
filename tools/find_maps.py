#!/usr/bin/env python3
"""Locate PC Engine background maps (BAT tables) inside a data track.

A real 32x28 screen map has:
  * tile indices confined to a plausible range (the loaded tile set)
  * several different palette nibbles in use
  * flat areas (runs of identical tile indices)
  * a fair number of distinct tiles
We scan every 16-byte aligned offset and score candidates.
"""
import sys


def words_at(b, off, n=896):
    return [b[off + i * 2] | (b[off + i * 2 + 1] << 8) for i in range(n)]


def score_window(w):
    t = [x & 0xFFF for x in w]
    p = [x >> 12 for x in w]
    lo, hi = min(t), max(t)
    if hi - lo > 2048:
        return None
    np_ = len(set(p))
    if np_ < 4:
        return None
    nt = len(set(t))
    if nt < 80:
        return None
    flat = sum(1 for i in range(1, 896) if t[i] == t[i - 1]) / 895
    if flat < 0.008:
        return None
    return (nt + flat * 100, lo, hi, np_, nt, flat)


def main():
    path = sys.argv[1]
    end = int(sys.argv[2], 0) if len(sys.argv) > 2 else None
    b = open(path, "rb").read()
    if end is None:
        end = len(b)
    hits = []
    for off in range(0, end - 1792, 16):
        s = score_window(words_at(b, off))
        if s:
            hits.append((s[0], off, s[1], s[2], s[3], s[4], s[5]))
    hits.sort(reverse=True)
    # merge overlapping
    seen = []
    for s, off, lo, hi, npal, nt, flat in hits:
        if any(off - o < 0x800 for o in seen):
            continue
        seen.append(off)
        print("$%06X  tiles $%03X-$%03X  palettes=%d distinct=%d flat=%.3f score=%.0f"
              % (off, lo, hi, npal, nt, flat, s))
        if len(seen) > 40:
            break


if __name__ == "__main__":
    main()
