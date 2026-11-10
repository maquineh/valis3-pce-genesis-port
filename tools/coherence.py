#!/usr/bin/env python3
"""Score how 'coherent' a rendered stage screen is.

For the correct tile block the screen shows terrain: large areas built from a
handful of 4x4 pixel patterns. For a wrong block the render is noise: every
4x4 block is a different pattern. Score = 1 - (distinct 4x4 patterns / blocks),
validated against the known stage-1 screens.

Usage: python3 tools/coherence.py <map_off> <tile_off> [more offsets...]
"""
import sys

sys.path.insert(0, "tools")
from pce_gfx import bg_tile_pixels, GRAY  # noqa: E402

GRID = 0x600
ROWS, COLS = 24, 32


def render_patterns(b, off, tile_off, base=0x200):
    """Return (blocks, distinct 4x4 patterns)."""
    pats = set()
    blocks = 0
    for i in range(ROWS * COLS):
        w = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
        tile = w & 0xFFF
        src = tile_off + (tile - base) * 32
        if src < 0 or src + 32 > len(b):
            continue
        px = bg_tile_pixels(b[src:src + 32])
        for ty in (0, 4):
            for tx in (0, 4):
                p = tuple(tuple(r[tx:tx + 4]) for r in px[ty:ty + 4])
                pats.add(p)
                blocks += 1
    return blocks, len(pats)


def main():
    path = "build/extracted/data/track_02.bin"
    b = open(path, "rb").read()
    args = [int(a, 0) for a in sys.argv[1:]]
    off = args[0]
    blocks_list = [0x19440, 0x1AFD0, 0x1B900, 0x1DDC0, 0x2C5BC0, 0x2D81C0,
                   0x2AA2C0, 0x2EA7C0]
    if len(args) > 1 and args[1] > 0x1000:
        blocks_list = [args[1]]
    print("map $%06X (coherence = 1 - distinct4x4/4x4blocks):" % off)
    for bl in blocks_list:
        n, d = render_patterns(b, off, bl)
        print("  block $%06X: %3d 4x4 blocks, %3d distinct patterns -> coherence %.2f"
              % (bl, n, d, 1 - d / max(n, 1)))


if __name__ == "__main__":
    main()
