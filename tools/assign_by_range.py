#!/usr/bin/env python3
"""Assign each screen map to the tile block whose size matches its tile range.

The loader reads a different tile block per stage; each block covers a known
number of tiles (size/32). A screen's map references tiles relative to base
$200, so the block whose range covers the map's tiles best is the right one.

Usage: python3 tools/assign_by_range.py [start] [end]
"""
import sys

GRID = 0x600
ROWS, COLS = 24, 32

# (file offset, byte size, label) from tools/list_vram_reads.py
BLOCKS = [
    (0x19440, 0xC000, "s2C 48K"),
    (0x1AFD0, 0xC000, "s2F 48K"),
    (0x1B900, 0xA000, "s30 40K"),
    (0x1DDC0, 0x6000, "s34 24K"),
    (0x2C5BC0, 0xC000, "s4D4 48K"),
    (0x2D81C0, 0x8000, "s4F4 32K"),
    (0x2AA2C0, 0x6000, "s4A4 24K"),
    (0x2EA7C0, 0x6000, "s514 24K"),
    (0x270C0, 0x2000, "s44 8K"),
]


def main():
    path = "build/extracted/data/track_02.bin"
    start = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x17FF90
    end = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x240000
    b = open(path, "rb").read()

    def best_block(off):
        tiles = []
        for i in range(ROWS * COLS):
            w = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
            tiles.append(w & 0xFFF)
        best = None
        for bl, size, name in BLOCKS:
            hi = 0x200 + size // 32
            inr = sum(1 for t in tiles if 0x200 <= t < hi)
            frac = inr / (ROWS * COLS)
            # prefer the block covering more of the map (ties -> bigger block)
            if best is None or frac > best[0] + 1e-9:
                best = (frac, name, bl, hi)
        return best

    print("reference (stage 1, first 3 screens):")
    for k in range(3):
        f, name, bl, hi = best_block(start + k * GRID)
        print("  $%06X -> %s (coverage %.2f)" % (start + k * GRID, name, f))

    print("\nruns:")
    off = start
    cur, run_start, n = None, None, 0
    while off + GRID <= min(end, len(b)):
        f, name, bl, hi = best_block(off)
        if name != cur:
            if cur is not None:
                print("  $%06X  %3d screens  %s" % (run_start, n, cur))
            cur, run_start, n = name, off, 0
        n += 1
        off += GRID
    if cur is not None:
        print("  $%06X  %3d screens  %s" % (run_start, n, cur))


if __name__ == "__main__":
    main()
