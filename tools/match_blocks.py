#!/usr/bin/env python3
"""Match map candidates to their tile block by rendered content.

For every map candidate in a range, try each known stage tile block and score
the render by how many cells produce a non-empty tile. A wrong block gives an
empty (black) screen; the correct one produces the playfield.
"""
import sys

sys.path.insert(0, "tools")
from pce_gfx import bg_tile_pixels  # noqa: E402

BLOCKS = [0x19440, 0x1AFD0, 0x1B900, 0x1DDC0, 0x2C5BC0, 0x2D81C0,
          0x2AA2C0, 0x2EA7C0, 0x6E40, 0x0]


def nonempty(t32):
    """A tile is 'empty' when all four planes are the same constant byte."""
    b = set(t32)
    return len(b) > 1


def score(b, map_off, tile_off, base=0x200):
    good = 0
    for i in range(896):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        tile = w & 0xFFF
        src = tile_off + (tile - base) * 32
        if src < 0 or src + 32 > len(b):
            continue
        if nonempty(b[src:src + 32]):
            good += 1
    return good / 896


def main():
    path = sys.argv[1]
    start = int(sys.argv[2], 0)
    end = int(sys.argv[3], 0)
    b = open(path, "rb").read()
    hits = []
    for off in range(start, end, 16):
        best = None
        for bl in BLOCKS:
            s = score(b, off, bl)
            if best is None or s > best[1]:
                best = (bl, s)
        if best[1] > 0.25:
            hits.append((best[1], off, best[0]))
    hits.sort(reverse=True)
    seen = []
    for s, off, bl in hits:
        if any(abs(off - o) < 0x600 for o in seen):
            continue
        seen.append(off)
        print("map $%06X -> block $%06X  content=%.2f" % (off, bl, s))
        if len(seen) >= 25:
            break


if __name__ == "__main__":
    main()
