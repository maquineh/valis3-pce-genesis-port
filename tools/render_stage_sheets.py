#!/usr/bin/env python3
"""Render every screen of a stage into a contact sheet (evidence / review).

Usage: python3 tools/render_stage_sheets.py <first_map> <screens> <tile_off> \
      <pal_off> <name>
"""
import sys

sys.path.insert(0, "tools")
from pce_gfx import GRAY, bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

GRID = 0x600
ROWS, COLS = 24, 32


def render(b, off, tile_off, palette, out, scale=2):
    img = Image.new("RGB", (COLS * 8 * scale, ROWS * 8 * scale), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(ROWS * COLS):
        w = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
        pal = w >> 12
        tile = w & 0xFFF
        src = tile_off + (tile - 0x200) * 32
        if src < 0 or src + 32 > len(b):
            continue
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (i % COLS) * 8, (i // COLS) * 8
        for r in range(8):
            for x in range(8):
                d.point(((tx + x) * scale, (ty + r) * scale),
                        palette[(pal * 16 + px[r][x]) % len(palette)])
    img.save(out)


def main():
    path = sys.argv[1]
    first = int(sys.argv[2], 0)
    n = int(sys.argv[3], 0)
    tile_off = int(sys.argv[4], 0)
    pal_off = int(sys.argv[5], 0)
    name = sys.argv[6]
    b = open(path, "rb").read()
    palette = load_palette_md(b, pal_off, 64)
    cols = 5
    rows = (n + cols - 1) // cols
    scale = 2
    sheet = Image.new("RGB", (cols * COLS * 8 * scale, rows * ROWS * 8 * scale), (8, 8, 8))
    d = ImageDraw.Draw(sheet)
    for s in range(n):
        off = first + s * GRID
        tmp = "/tmp/_scr.png"
        render(b, off, tile_off, palette, tmp, scale)
        im = Image.open(tmp)
        cx = (s % cols) * COLS * 8 * scale
        cy = (s // cols) * ROWS * 8 * scale
        d.rectangle([cx, cy, cx + COLS * 8 * scale, cy + 12], fill=(20, 20, 20))
        d.text((cx + 4, cy + 2), "screen %d" % (s + 1), fill=(255, 255, 255))
        sheet.paste(im, (cx, cy + 14))
    out = "build/gfx/%s_screens.png" % name
    sheet.save(out)
    print("wrote", out, "%d screens" % n)


if __name__ == "__main__":
    main()
