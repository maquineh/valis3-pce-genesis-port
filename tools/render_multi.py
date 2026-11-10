#!/usr/bin/env python3
"""Render a screen map where tiles come from several VRAM tile regions.

The loader loads several tile blocks into VRAM at different word addresses
(dh=$FE reads with different destinations), so a screen's tile index t maps to
a different file offset depending on which region it lands in.

Usage: python3 tools/render_multi.py <map_off> <regions_spec> [pal_off]
  regions_spec is a comma separated list of tile_lo:file_offset pairs, e.g.
  0x200:0x19440,0x500:0x2EA7C0
"""
import sys

sys.path.insert(0, "tools")
from pce_gfx import bg_tile_pixels, GRAY, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROWS, COLS = 24, 32


def main():
    path = "build/extracted/data/track_02.bin"
    map_off = int(sys.argv[1], 0)
    spec = sys.argv[2]
    regions = []
    for part in spec.split(","):
        lo, off = part.split(":")
        regions.append((int(lo, 0), int(off, 0)))
    regions.sort()
    b = open(path, "rb").read()
    pal_off = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x9352
    palette = load_palette_md(b, pal_off, 64)

    def tile_src(t):
        """Pick the region covering tile t."""
        chosen = None
        for lo, off in regions:
            if t >= lo:
                chosen = (lo, off)
        if chosen is None:
            return None
        lo, off = chosen
        return off + (t - lo) * 32

    scale = 2
    img = Image.new("RGB", (COLS * 8 * scale, ROWS * 8 * scale), (0, 0, 0))
    d = ImageDraw.Draw(img)
    ok = 0
    for i in range(ROWS * COLS):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        pal = w >> 12
        tile = w & 0xFFF
        src = tile_src(tile)
        if src is None or src < 0 or src + 32 > len(b):
            continue
        ok += 1
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (i % COLS) * 8, (i // COLS) * 8
        for r in range(8):
            for x in range(8):
                d.point(((tx + x) * scale, (ty + r) * scale),
                        palette[(pal * 16 + px[r][x]) % len(palette)])
    out = "build/gfx/multi_%06X_%s.png" % (map_off, spec.replace(":", "").replace(",", "_"))
    img.save(out)
    print("wrote %s (%d/%d cells resolved)" % (out, ok, ROWS * COLS))


if __name__ == "__main__":
    main()
