"""Match every map slot on the 0x600 grid to the tile block that covers it.

A stage screen's tile indices are VRAM tile indices, and each stage tile block
is read by the loader to a known VRAM word address.  So for the correct
(screen, block) pair *every* referenced tile must land inside that block's
range.  That is a decidable test, unlike render scoring.

Usage:
    python3 tools/match_grid.py [track] [start] [end] [--min-cov 0.9]
"""
import argparse
import os
import sys

# (file offset, byte size, VDC word address, loader site) - list_vram_reads.py
BLOCKS = [
    (0x006E40, 0xA000, 0x1000, "$49CD title"),
    (0x016F80, 0x2000, 0x7000, "$49F0"),
    (0x019440, 0xC000, 0x1000, "$237605 sec $2C"),
    (0x01AFD0, 0xC000, 0x1000, "$2553C5 sec $2F"),
    (0x01B900, 0xA000, 0x3000, "$235133 sec $30"),
    (0x01DDC0, 0x6000, 0x2000, "$23255B sec $34"),
    (0x0270C0, 0x2000, 0x5000, "$23259D sec $44"),
    (0x2AA2C0, 0x6000, 0x5000, "$2A1072 sec $4A4"),
    (0x2C5BC0, 0xC000, 0x1000, "$287BEC sec $4D4"),
    (0x2D81C0, 0x8000, 0x1000, "$287D4C sec $4F4"),
    (0x2EA7C0, 0x6000, 0x5000, "$22BE32 sec $514"),
    (0x000000, 0xC000, 0x2000, "$230792 sec 0"),
]

GRID = 0x600
CELLS = 768


def coverage(b, map_off, blk):
    off, size, word, label = blk
    base = word // 16
    ntiles = size // 32
    inr = 0
    distinct = set()
    for i in range(CELLS):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        t = w & 0xFFF
        if base <= t < base + ntiles:
            inr += 1
            distinct.add(t)
    return inr / CELLS, len(distinct), base, ntiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("track", nargs="?", default="track_02")
    ap.add_argument("start", nargs="?", default="0x17FF90")
    ap.add_argument("end", nargs="?", default="0x240000")
    ap.add_argument("--min-cov", type=float, default=0.9)
    ap.add_argument("--min-distinct", type=int, default=40)
    args = ap.parse_args()

    b = open("build/extracted/data/%s.bin" % args.track, "rb").read()
    start, end = int(args.start, 0), int(args.end, 0)

    print("%-9s %-30s %6s %6s %s" %
          ("offset", "block (loader site)", "cov", "tiles", "range"))
    hits = 0
    off = start
    while off + GRID <= min(end, len(b)):
        rows = []
        for blk in BLOCKS:
            cov, nd, base, nt = coverage(b, off, blk)
            if cov >= args.min_cov and nd >= args.min_distinct:
                rows.append((nd, cov, blk, base, nt))
        rows.sort(reverse=True)
        for nd, cov, blk, base, nt in rows[:2]:
            print("$%06X %-30s %6.2f %6d $%03X-$%03X" %
                  (off, blk[3], cov, nd, base, base + nt - 1))
            hits += 1
        off += GRID
    print("%d (slot, block) pairs with coverage >= %.2f" % (hits, args.min_cov))


if __name__ == "__main__":
    main()
