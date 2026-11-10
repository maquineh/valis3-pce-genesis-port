#!/usr/bin/env python3
"""Find the real stage playfields by matching maps to tile blocks correctly.

Every stage tile block is read by the game's loader to a *known* VRAM word
address (tools/list_vram_reads.py), so a screen map's tile index t refers to
VRAM tile t.  The mapping from a map tile index to a disc file offset is
therefore:

    file_offset = block_file_offset + (t - vram_tile_base) * 32

where vram_tile_base = vram_word / 16.

To separate real terrain from dither/object data we score the render by the
fraction of 4x4 pixel blocks that are flat (all 16 pixels the same colour):
a playfield has large flat areas, dithered artwork and scattered tiles do not.

Usage:
    python3 tools/find_playfields.py [track] [start] [end] [step] [--top N]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pce_gfx import bg_tile_pixels  # noqa: E402

# (file offset, byte size, VDC word address, loader site) from list_vram_reads
BLOCKS = [
    (0x006E40, 0xA000, 0x1000, "$49CD  title"),
    (0x016F80, 0x2000, 0x7000, "$49F0"),
    (0x019440, 0xC000, 0x1000, "$237605 sector $2C"),
    (0x01AFD0, 0xC000, 0x1000, "$2553C5 sector $2F"),
    (0x01B900, 0xA000, 0x3000, "$235133 sector $30"),
    (0x01DDC0, 0x6000, 0x2000, "$23255B sector $34"),
    (0x0270C0, 0x2000, 0x5000, "$23259D sector $44"),
    (0x2AA2C0, 0x6000, 0x5000, "$2A1072 sector $4A4"),
    (0x2C5BC0, 0xC000, 0x1000, "$287BEC sector $4D4"),
    (0x2D81C0, 0x8000, 0x1000, "$287D4C sector $4F4"),
    (0x2EA7C0, 0x6000, 0x5000, "$22BE32 sector $514"),
]

MAP_GRID = 0x600          # one 32x24-cell screen
ROWS, COLS = 24, 32


def render_flat(b, map_off, blk, n=ROWS * COLS):
    """Render a map against a block and measure flat 4x4 coverage."""
    off, size, word, label = blk
    base = word // 16                     # VRAM tile index of block tile 0
    ntiles = size // 32
    flat = 0
    blocks = 0
    resolved = 0
    for i in range(n):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        t = w & 0xFFF
        src = off + (t - base) * 32
        if not (0 <= t - base < ntiles):
            continue
        if src < 0 or src + 32 > len(b):
            continue
        resolved += 1
        px = bg_tile_pixels(b[src:src + 32])
        for ty in (0, 4):
            for tx in (0, 4):
                blocks += 1
                v = px[ty][tx]
                if all(px[y][x] == v for y in range(ty, ty + 4)
                       for x in range(tx, tx + 4)):
                    flat += 1
    return (flat / blocks if blocks else 0.0), resolved / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("track", nargs="?", default="track_02")
    ap.add_argument("start", nargs="?", default="0x17FF90")
    ap.add_argument("end", nargs="?", default="0x240000")
    ap.add_argument("step", nargs="?", default="0x600")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    path = "build/extracted/data/%s.bin" % args.track
    b = open(path, "rb").read()
    start, end, step = (int(args.start, 0), int(args.end, 0), int(args.step, 0))

    # calibration: the known stage-1 screen must score high
    print("calibration - known stage 1 screen at $17FF90:")
    for blk in BLOCKS:
        f, r = render_flat(b, 0x17FF90, blk)
        if r > 0.5:
            print("   block %s base $%03X  flat=%.3f resolved=%.2f" %
                  (blk[3], blk[2] // 16, f, r))
    print()

    results = []
    off = start
    while off + MAP_GRID <= min(end, len(b)):
        best = None
        for blk in BLOCKS:
            f, r = render_flat(b, off, blk)
            if r < 0.95:
                continue
            if best is None or f > best[0]:
                best = (f, blk)
        if best:
            results.append((best[0], off, best[1]))
        off += step

    results.sort(reverse=True)
    print("%d map slots rendered, top %d by flat-area ratio:" %
          (len(results), min(args.top, len(results))))
    seen = []
    for f, off, blk in results:
        if any(abs(off - o) < MAP_GRID for o in seen):
            continue
        seen.append(off)
        print("  $%06X  flat=%.3f  block %s (base $%03X, file $%06X)" %
              (off, f, blk[3], blk[2] // 16, blk[0]))
        if len(seen) >= args.top:
            break


if __name__ == "__main__":
    main()
