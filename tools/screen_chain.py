#!/usr/bin/env python3
"""Walk the stage screen chain with a coherence test.

A real playfield screen has long horizontal runs of identical tile indices
(terrain/walls); object/animation tables do not. We require
distinct tiles > 40, no out-of-range tiles, and max tile run >= 16.

Usage: python3 tools/screen_chain.py <first_map> <tile_block> [max]
"""
import sys

sys.path.insert(0, "tools")
from pce_gfx import bg_tile_pixels  # noqa: E402

GRID = 0x600
ROWS, COLS = 24, 32


def tile_kind(t32):
    u = set(t32)
    if len(u) == 1:
        return "blank"
    if len(u) <= 3:
        return "dither"
    return "art"


def stats(b, off, tile_off, base=0x200):
    distinct = set()
    bad = 0
    for i in range(ROWS * COLS):
        w = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
        tile = w & 0xFFF
        src = tile_off + (tile - base) * 32
        if src < 0 or src + 32 > len(b):
            bad += 1
            continue
        distinct.add(tile)
    return len(distinct), bad


def max_run(b, off):
    """Longest horizontal run of identical tile indices (terrain)."""
    best = 0
    for r in range(ROWS):
        run = 1
        for c in range(1, COLS):
            i = r * COLS + c
            j = r * COLS + c - 1
            w1 = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
            w2 = b[off + j * 2] | (b[off + j * 2 + 1] << 8)
            if (w1 & 0xFFF) == (w2 & 0xFFF):
                run += 1
            else:
                if run > best:
                    best = run
                run = 1
        if run > best:
            best = run
    return best


def main():
    path = "build/extracted/data/track_02.bin"
    first = int(sys.argv[1], 0)
    block = int(sys.argv[2], 0)
    limit = int(sys.argv[3], 0) if len(sys.argv) > 3 else 64
    b = open(path, "rb").read()

    n = 0
    for k in range(limit):
        off = first + k * GRID
        if off + GRID > len(b):
            break
        nt, bad = stats(b, off, block)
        run = max_run(b, off)
        ok = nt > 40 and bad < 8 and run >= 16
        print("screen %2d at $%06X: distinct %3d, bad %2d, maxrun %2d %s"
              % (k + 1, off, nt, bad, run, "OK" if ok else "STOP"))
        if ok:
            n += 1
        else:
            break
    print("%d consecutive stage screens decoded" % n)


if __name__ == "__main__":
    main()
