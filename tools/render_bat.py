#!/usr/bin/env python3
"""Render a full PC Engine screen from a BAT table + tile data.

BAT entry (16-bit LE): (palette << 12) | tile_index, where tile_index*32 is the
VRAM byte address of the tile. Tiles loaded from the CD at VRAM word $1000
(= tile index 256) come from the disc file offset of the cd_read source, so:
    file_offset_of_tile(t) = tile_base_offset + (t - tile_base_index) * 32
"""
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, "tools")
from pce_gfx import bg_tile_pixels, GRAY  # noqa: E402


def main():
    data_path = sys.argv[1]
    bat_off = int(sys.argv[2], 0)
    tile_off = int(sys.argv[3], 0)
    tile_base = int(sys.argv[4], 0)
    w = int(sys.argv[5], 0) if len(sys.argv) > 5 else 32
    h = int(sys.argv[6], 0) if len(sys.argv) > 6 else 28
    out = sys.argv[7] if len(sys.argv) > 7 else "build/gfx/screen_bat.png"
    scale = 3
    b = open(data_path, "rb").read()

    img = Image.new("RGB", (w * 8 * scale, h * 8 * scale), (0, 0, 0))
    d = ImageDraw.Draw(img)
    stats = {}
    for i in range(w * h):
        lo, hi = b[bat_off + i * 2], b[bat_off + i * 2 + 1]
        word = lo | (hi << 8)
        pal = word >> 12
        tile = word & 0xFFF
        stats[pal] = stats.get(pal, 0) + 1
        src = tile_off + (tile - tile_base) * 32
        if src < 0 or src + 32 > len(b):
            continue
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (i % w) * 8, (i // w) * 8
        for r in range(8):
            for x in range(8):
                col = GRAY[px[r][x]]
                d.rectangle([(tx + x) * scale, (ty + r) * scale,
                             (tx + x) * scale + scale - 1,
                             (ty + r) * scale + scale - 1], fill=col)
    img.save(out)
    print("saved", out)
    print("palette usage:", dict(sorted(stats.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
