#!/usr/bin/env python3
"""Find how many consecutive stage screens follow a confirmed map.

Screens are 32x24 tiles (0x600 bytes) on a grid. Starting from a confirmed
map offset, walk the grid while the renders keep producing a playfield (many
distinct tiles, structured rows) with the same tile block.

Usage: python3 tools/screen_chain.py <first_map> <tile_block> [max]
"""
import sys

sys.path.insert(0, "tools")
from pce_gfx import bg_tile_pixels  # noqa: E402

GRID = 0x600
ROWS, COLS = 24, 32


def stats(b, off, tile_off, base=0x200):
    distinct = 0
    bad = 0
    tiles = set()
    for i in range(ROWS * COLS):
        w = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
        tile = w & 0xFFF
        src = tile_off + (tile - base) * 32
        if src < 0 or src + 32 > len(b):
            bad += 1
            continue
        tiles.add(tile)
    return len(tiles), bad


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
        ok = nt > 40 and bad < 8
        print("screen %2d at $%06X: distinct tiles %3d, bad %2d %s"
              % (k + 1, off, nt, bad, "OK" if ok else "STOP"))
        if ok:
            n += 1
        else:
            break
    print("%d consecutive stage screens decoded" % n)


if __name__ == "__main__":
    main()
