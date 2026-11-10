"""Render the stage screen with base=VRAM word/16 and an 11-bit tile field."""
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()
MAP = 0x17FF90
PAL = 0x9352
TILES = 0x19440          # sector $2C block (VRAM word $1000)
ROWS, COLS = 24, 32

pal = load_palette_md(b, PAL, 64)

variants = [
    ('base $100 mask $FFF', 0x100, 0xFFF),
    ('base $100 mask $7FF', 0x100, 0x7FF),
    ('base $200 mask $FFF', 0x200, 0xFFF),
    ('base $200 mask $7FF', 0x200, 0x7FF),
]

for name, base, mask in variants:
    img = Image.new('RGB', (COLS * 8 * 3, ROWS * 8 * 3), (0, 0, 0))
    d = ImageDraw.Draw(img)
    ok = 0
    for i in range(ROWS * COLS):
        w = b[MAP + i * 2] | (b[MAP + i * 2 + 1] << 8)
        t = w & mask
        paln = (w >> 12) & 0xF
        src = TILES + (t - base) * 32
        if src < 0 or src + 32 > len(b):
            continue
        ok += 1
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (i % COLS) * 8, (i // COLS) * 8
        for r in range(8):
            for x in range(8):
                d.point(((tx + x) * 3, (ty + r) * 3),
                        pal[(paln * 16 + px[r][x]) % 64])
    out = 'build/gfx/v_%s.png' % name.replace(' ', '_').replace('$', '')
    img.save(out)
    print('%-22s %d/%d cells -> %s' % (name, ok, ROWS * COLS, out))
