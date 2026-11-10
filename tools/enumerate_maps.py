#!/usr/bin/env python3
"""Enumerate stage screen maps on the 0x600 (32x24) grid and match blocks.

The stage screen maps live on a 1536-byte grid (32 wide x 24 high). For each
grid slot we try every known stage tile block and keep the best-scoring
render, which tells us which screen belongs to which tile block.

Usage: python3 tools/enumerate_maps.py [start] [end]
"""
import sys

sys.path.insert(0, "tools")
from pce_gfx import bg_tile_pixels  # noqa: E402

BLOCKS = [
    (0x19440, "sector $2C"),
    (0x1AFD0, "sector $2F"),
    (0x1B900, "sector $30"),
    (0x1DDC0, "sector $34"),
    (0x2C5BC0, "sector $4D4"),
    (0x2D81C0, "sector $4F4"),
    (0x2AA2C0, "sector $4A4"),
    (0x2EA7C0, "sector $514"),
]

GRID = 0x600
ROWS = 24
COLS = 32
BASE = 0x200


def nonempty(t32):
    return len(set(t32)) > 1


def score(b, map_off, tile_off, base=BASE):
    good = 0
    n = ROWS * COLS
    for i in range(n):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        tile = w & 0xFFF
        src = tile_off + (tile - base) * 32
        if src < 0 or src + 32 > len(b):
            continue
        if nonempty(b[src:src + 32]):
            good += 1
    return good / n


def main():
    path = "build/extracted/data/track_02.bin"
    start = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x100000
    end = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x300000
    b = open(path, "rb").read()

    # align to the grid: find the first offset >= start that fits the pattern
    base_off = None
    rows = []
    off = start
    while off + GRID <= end:
        best = None
        for bl, name in BLOCKS:
            s = score(b, off, bl)
            if best is None or s > best[2]:
                best = (bl, name, s)
        rows.append((off, best))
        off += GRID
    print("%d grid slots scanned" % len(rows))
    # print only the good ones
    good = 0
    for off, best in rows:
        if best[2] > 0.5:
            good += 1
    print("%d slots with a matching tile block (content > 0.5)" % good)
    prev = None
    for off, best in rows:
        if best[2] > 0.5:
            print("  $%06X  %s ($%06X)  content=%.2f"
                  % (off, best[1], best[0], best[2]))


if __name__ == "__main__":
    main()
