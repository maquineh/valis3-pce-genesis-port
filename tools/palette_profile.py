#!/usr/bin/env python3
"""Find stage boundaries by looking at each screen's palette signature.

Each stage loads its own VCE palette block, so a screen's BG palette nibbles
cluster differently from the next stage's. Walking the map grid and printing
the palette profile exposes the boundaries.

Usage: python3 tools/palette_profile.py [start] [count]
"""
import sys
from collections import Counter

GRID = 0x600
ROWS, COLS = 24, 32


def main():
    path = "build/extracted/data/track_02.bin"
    start = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x17FF90
    count = int(sys.argv[2], 0) if len(sys.argv) > 2 else 120
    b = open(path, "rb").read()

    print("%-10s %-28s %s" % ("offset", "top palettes", "tiles in $100-$1FF / $200-$7FF"))
    prev = None
    for k in range(count):
        off = start + k * GRID
        if off + GRID > len(b):
            break
        pals = Counter()
        lo = hi = 0
        for i in range(ROWS * COLS):
            w = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
            pals[w >> 12] += 1
            t = w & 0xFFF
            if t < 0x200:
                lo += 1
            else:
                hi += 1
        sig = tuple(pals.most_common(3))
        mark = ""
        if prev is not None and sig != prev:
            mark = "  <-- change"
        print("$%06X  %s  %3d/%3d%s"
              % (off, " ".join("%X:%d" % (p, n) for p, n in sig), lo, hi, mark))
        prev = sig


if __name__ == "__main__":
    main()
