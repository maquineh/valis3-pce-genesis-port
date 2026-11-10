#!/usr/bin/env python3
"""Assign each stage screen map to the tile block that renders real artwork.

A screen map's tile indices resolve against several candidate tile blocks, but
only the correct one produces the game's artwork. "Art" tiles have many
distinct bytes (real sprites/terrain); blank tiles are constant-filled and
dither tiles are 2-3 byte checkerboards. For each screen we score every known
stage tile block by how many cells render as art and keep the best.

Usage: python3 tools/assign_blocks.py [start] [end]
"""
import sys

GRID = 0x600
ROWS, COLS = 24, 32

BLOCKS = [
    (0x19440, "s2C_48K"),
    (0x1AFD0, "s2F_48K"),
    (0x1B900, "s30_40K"),
    (0x1DDC0, "s34_24K"),
    (0x2C5BC0, "s4D4_48K"),
    (0x2D81C0, "s4F4_32K"),
    (0x2AA2C0, "s4A4_24K"),
    (0x2EA7C0, "s514_24K"),
]


def tile_kind(t32):
    u = set(t32)
    if len(u) == 1:
        return "blank"
    if len(u) <= 3:
        return "dither"
    return "art"


def score(b, map_off, tile_off, base=0x200):
    art = 0
    blank = 0
    for i in range(ROWS * COLS):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        tile = w & 0xFFF
        src = tile_off + (tile - base) * 32
        if src < 0 or src + 32 > len(b):
            blank += 1
            continue
        k = tile_kind(b[src:src + 32])
        if k == "art":
            art += 1
        elif k == "blank":
            blank += 1
    return art / (ROWS * COLS)


def main():
    path = "build/extracted/data/track_02.bin"
    start = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x17FF90
    end = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x240000
    b = open(path, "rb").read()

    # reference: stage 1 screens must score high with their known block
    print("reference (stage 1):")
    for k in range(3):
        off = start + k * GRID
        best = max((score(b, off, bl), name) for bl, name in BLOCKS)
        print("  $%06X best=%s art=%.2f" % (off, best[1], best[0]))

    rows = []
    off = start
    while off + GRID <= min(end, len(b)):
        best = None
        for bl, name in BLOCKS:
            s = score(b, off, bl)
            if best is None or s > best[0]:
                best = (s, name, bl)
        rows.append((off, best))
        off += GRID

    # compress into runs of (block, count)
    print("\nscreen assignment runs:")
    cur = None
    run_start = None
    n = 0
    out = []
    for off, (s, name, bl) in rows:
        if name != cur:
            if cur is not None:
                out.append((run_start, n, cur))
            cur = name
            run_start = off
            n = 0
        n += 1
    if cur is not None:
        out.append((run_start, n, cur))
    for o, c, name in out:
        print("  $%06X  %3d screens  %s" % (o, c, name))
    print("\n%d screens scanned" % len(rows))


if __name__ == "__main__":
    main()
