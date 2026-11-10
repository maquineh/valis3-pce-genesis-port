#!/usr/bin/env python3
"""Walk the whole level chain and print the stage/segment table.

Screen maps are 32x24 tiles (0x600 bytes) on a grid. Starting from the first
screen map, walk the grid with the current tile block until it stops, then try
the remaining stage tile blocks at that offset and continue with whichever
fits. This reproduces the disc's level/segment structure.

Usage: python3 tools/walk_stages.py [start]
"""
import sys

sys.path.insert(0, "tools")
from screen_chain import GRID, stats  # noqa: E402

BLOCKS = [
    (0x19440, "sector $2C (48K)"),
    (0x1AFD0, "sector $2F (48K)"),
    (0x1B900, "sector $30 (40K)"),
    (0x1DDC0, "sector $34 (24K)"),
    (0x2C5BC0, "sector $4D4 (48K)"),
    (0x2D81C0, "sector $4F4 (32K)"),
    (0x2AA2C0, "sector $4A4 (24K)"),
    (0x2EA7C0, "sector $514 (24K)"),
]


def main():
    path = "build/extracted/data/track_02.bin"
    start = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x17FF90
    b = open(path, "rb").read()

    off = start
    block_idx = 0
    seg_start = off
    count = 0
    seg_name = BLOCKS[0][1]
    stages = []
    while off + GRID <= len(b):
        bl = BLOCKS[block_idx][0]
        nt, bad = stats(b, off, bl)
        if nt > 40 and bad < 8:
            count += 1
            off += GRID
            continue
        # chain ended here: try skipping a blank slot, then another block
        resumed = False
        for skip in (1, 2):
            nxt = None
            for i, (bl2, name2) in enumerate(BLOCKS):
                nt2, bad2 = stats(b, off + skip * GRID, bl2)
                if nt2 > 40 and bad2 < 8:
                    nxt = i
                    break
            if nxt is not None:
                off += skip * GRID
                block_idx = nxt
                resumed = True
                break
        if not resumed:
            break
        if count:
            stages.append((seg_start, count, seg_name))
        seg_name = BLOCKS[block_idx][1]
        seg_start = off
        count = 0
    if count:
        stages.append((seg_start, count, seg_name))

    print("stage/segment table (first map, screens, tile block):")
    total = 0
    for i, (o, c, name) in enumerate(stages):
        print("  segment %2d: first map $%06X  %3d screens  tiles %s"
              % (i + 1, o, c, name))
        total += c
    print("%d segments, %d screens total" % (len(stages), total))


if __name__ == "__main__":
    main()
