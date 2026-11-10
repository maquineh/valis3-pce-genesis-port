#!/usr/bin/env python3
"""Extract PC Engine screens: match each BAT map with its tile block.

The game reads per-screen tile blocks from the disc into VRAM at known word
addresses (decoded by tools/decode_cd_calls.py). A screen map therefore
references VRAM tile indices; tile index t of a block that was loaded at
VRAM word $B maps to disc offset (sector*2352 + (t - B/16)*32).

This tool tries every known tile block for every map candidate and keeps the
combination whose render covers the most cells (a wrong block makes most
cells invalid or produces noise).
"""
import os
import sys

from pce_gfx import bg_tile_pixels

# VRAM word base -> track-2 file offset (sector * 2352), from decode_cd_calls
TILE_BLOCKS = [
    0x000,      # sector 0   -> VRAM $2000 (font/HUD sets, many screens)
    0x16800,    # sector 24  -> VRAM $3000
    0x1D300,    # sector 29  -> VRAM $1000
    0x1F800,    # sector 32  -> VRAM $1000
    0x19440,    # sector 44  -> VRAM $1000
    0x1AFD0,    # sector 47  -> VRAM $1000
    0x1B900,    # sector 48  -> VRAM $3000
    0x1DD80,    # sector 52  -> VRAM $2000
    0x6E00,     # sector 12  -> VRAM $1000 (title screen)
    0x20A00,    # sector 56  -> VRAM $1000
    0x26A80,    # sector 60  -> VRAM $1000
]


def map_words(b, off, n=896):
    return [b[off + i * 2] | (b[off + i * 2 + 1] << 8) for i in range(n)]


def render_score(b, map_off, tile_off, base):
    """Fraction of cells that resolve to a real tile + tile coherence."""
    ok = 0
    coh = 0.0
    ncoh = 0
    for i in range(896):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        tile = w & 0xFFF
        src = tile_off + (tile - base) * 32
        if src < 0 or src + 32 > len(b):
            continue
        ok += 1
        blk = b[src:src + 32]
        same = 0
        tot = 0
        for r in range(8):
            row = []
            for x in range(8):
                bit = 0x80 >> x
                v = ((1 if blk[r * 2] & bit else 0) | (2 if blk[r * 2 + 1] & bit else 0)
                     | (4 if blk[16 + r * 2] & bit else 0)
                     | (8 if blk[16 + r * 2 + 1] & bit else 0))
                row.append(v)
            for a, c in zip(row, row[1:]):
                tot += 1
                if a == c:
                    same += 1
        if tot:
            coh += same / tot
            ncoh += 1
    return ok / 896, (coh / ncoh) if ncoh else 0.0


def find_maps(b, min_distinct=60, min_seq=0.03):
    out = []
    for off in range(0, len(b) - 1792, 16):
        w = map_words(b, off)
        t = [x & 0xFFF for x in w]
        p = [x >> 12 for x in w]
        if len(set(p)) < 3 or len(set(t)) < min_distinct:
            continue
        seq = sum(1 for i in range(1, 896) if 0 < t[i] - t[i - 1] < 3) / 895
        if seq < min_seq:
            continue
        out.append((off, min(t), max(t), len(set(p)), seq))
    return out


def main():
    path = sys.argv[1]
    b = open(path, "rb").read()
    maps = find_maps(b)
    # deduplicate overlapping windows
    maps.sort(key=lambda m: -(m[4]))
    chosen = []
    for m in maps:
        if any(abs(m[0] - c[0]) < 0x800 for c in chosen):
            continue
        chosen.append(m)
    print("%d map candidates" % len(chosen))
    for off, lo, hi, npal, seq in chosen[:12]:
        best = None
        for tb in TILE_BLOCKS:
            for base in (0x100, 0x200, 0x400, 0x800):
                f, c = render_score(b, off, tb, base)
                if f < 0.98:
                    continue
                if best is None or c > best[2]:
                    best = (tb, base, c, f)
        if best:
            print("map $%06X (palettes %d, seq %.2f) -> tiles $%06X base $%03X coherence %.2f"
                  % (off, npal, seq, best[0], best[1], best[2]))
        else:
            print("map $%06X (palettes %d, seq %.2f) -> no tile block matched"
                  % (off, npal, seq))


if __name__ == "__main__":
    main()
