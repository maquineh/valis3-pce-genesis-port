#!/usr/bin/env python3
"""Render every screen-map candidate with every tile block that fully covers
its tile indices, and save PNGs for visual confirmation."""
import os
import sys

sys.path.insert(0, "tools")
from pce_gfx import GRAY, bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TILE_BLOCKS = [0x000, 0x16800, 0x1D300, 0x1F800, 0x19440, 0x1AFD0, 0x1B900,
               0x1DD80, 0x6E00, 0x20A00, 0x26A80, 0x237540]
OUT = "build/gfx/screens"


def map_words(b, off, n=896):
    return [b[off + i * 2] | (b[off + i * 2 + 1] << 8) for i in range(n)]


def coverage(b, map_off, tile_off, base):
    ok = 0
    for i in range(896):
        tile = (b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)) & 0xFFF
        src = tile_off + (tile - base) * 32
        if src >= 0 and src + 32 <= len(b):
            ok += 1
    return ok / 896


def render(b, map_off, tile_off, base, palette, out):
    img = Image.new("RGB", (32 * 8 * 3, 28 * 8 * 3), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(896):
        lo, hi = b[map_off + i * 2], b[map_off + i * 2 + 1]
        word = lo | (hi << 8)
        pal = word >> 12
        tile = word & 0xFFF
        src = tile_off + (tile - base) * 32
        if src < 0 or src + 32 > len(b):
            continue
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (i % 32) * 8, (i // 32) * 8
        for r in range(8):
            for x in range(8):
                d.point(((tx + x) * 3, (ty + r) * 3), palette[(pal * 16 + px[r][x]) % len(palette)])
    img.save(out)


def main():
    path = sys.argv[1]
    b = open(path, "rb").read()
    pal_off = int(sys.argv[2], 0) if len(sys.argv) > 2 else None
    palette = load_palette_md(b, pal_off, 64) if pal_off else GRAY * 4
    os.makedirs(OUT, exist_ok=True)

    # map candidates
    cands = []
    for off in range(0, len(b) - 1792, 16):
        w = map_words(b, off)
        t = [x & 0xFFF for x in w]
        p = [x >> 12 for x in w]
        if len(set(p)) < 3 or len(set(t)) < 60:
            continue
        seq = sum(1 for i in range(1, 896) if 0 < t[i] - t[i - 1] < 3) / 895
        if seq < 0.03:
            continue
        cands.append((seq + len(set(t)) / 100, off))
    cands.sort(reverse=True)
    seen = []
    for s, off in cands:
        if any(abs(off - o) < 0x800 for o in seen):
            continue
        seen.append(off)
        for tb in TILE_BLOCKS:
            for base in (0x100, 0x200, 0x400, 0x800):
                if coverage(b, off, tb, base) < 0.98:
                    continue
                out = "%s/m_%06X_b%06X_base%03X.png" % (OUT, off, tb, base)
                render(b, off, tb, base, palette, out)
                print("wrote", out)
                break
            else:
                continue
            break
        if len(seen) > 14:
            break


if __name__ == "__main__":
    main()
