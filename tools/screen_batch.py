#!/usr/bin/env python3
"""Render candidate screen layouts at 1:1 from a data track (identity tilemap)."""
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, "tools")
from pce_gfx import bg_tile_pixels, GRAY  # noqa: E402


def render(data, off, w, h, out, palette=None):
    pal = palette or GRAY
    img = Image.new("RGB", (w * 8, h * 8), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for t in range(w * h):
        base = off + t * 32
        blk = data[base:base + 32]
        if len(blk) < 32:
            return None
        px = bg_tile_pixels(blk)
        tx, ty = (t % w) * 8, (t // w) * 8
        for r in range(8):
            for x in range(8):
                d.point((tx + x, ty + r), pal[px[r][x] % len(pal)])
    img.save(out)
    return out


def main():
    path = sys.argv[1]
    data = open(path, "rb").read()
    for off in [int(a, 0) for a in sys.argv[2].split(",")]:
        for (w, h) in [(32, 28), (40, 28), (64, 16), (16, 32)]:
            out = "build/gfx/sb_%s_%dx%d_%d.png" % (path.split("/")[-1][:-4], w, h, off)
            r = render(data, off, w, h, out)
            print(r or ("too short: %d" % off))


if __name__ == "__main__":
    main()
