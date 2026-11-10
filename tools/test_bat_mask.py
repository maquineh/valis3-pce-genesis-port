"""Test the BAT field split: pattern = word & 0x7FF vs word & 0xFFF."""
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()
MAP = 0x17FF90
TILES = 0x19440
PAL = 0x9352
ROWS, COLS = 24, 32

pal = load_palette_md(b, PAL, 64)

for name, mask in (('mask 0xFFF (12-bit tile)', 0xFFF),
                   ('mask 0x7FF (11-bit tile)', 0x7FF)):
    img = Image.new('RGB', (COLS * 8 * 3, ROWS * 8 * 3), (0, 0, 0))
    d = ImageDraw.Draw(img)
    ok = 0
    for i in range(ROWS * COLS):
        w = b[MAP + i * 2] | (b[MAP + i * 2 + 1] << 8)
        t = w & mask
        paln = (w >> 12) & 0xF
        src = TILES + (t - 0x200) * 32
        if src < 0 or src + 32 > len(b):
            continue
        ok += 1
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (i % COLS) * 8, (i // COLS) * 8
        for r in range(8):
            for x in range(8):
                d.point(((tx + x) * 3, (ty + r) * 3),
                        pal[(paln * 16 + px[r][x]) % 64])
    out = 'build/gfx/bat_%s.png' % name.split('(')[0].strip().replace(' ', '_')
    img.save(out)
    print('%-28s %d/%d cells resolved -> %s' % (name, ok, ROWS * COLS, out))
