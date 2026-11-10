"""Render STG2A's map against candidate tile origins inside its own block."""
import os
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()

SEC = 344
START = SEC * 2352
END = START + 40 * 2352
MAP = 0x0C8280
PAL = 0x0C5A80
BASE = 0x200

pal = load_palette_md(b, PAL, 64)
ROWS, COLS = 24, 32

# candidate tile origins: starts of the bigger TILE runs in the block
CANDS = [0x0C5A80, 0x0C6280, 0x0C6C80, 0x0C7280, 0x0C7A80, 0x0C8880,
         0x0C9080, 0x0CA480, 0x0CBA80, 0x0CC480, 0x0CD080, 0x0CE280,
         0x0CF480, 0x0D0280, 0x0D1A80, 0x0D2C80, 0x0D3E80, 0x0D5080]

os.makedirs('build/gfx/stg2a', exist_ok=True)
cols = 6
rows = (len(CANDS) + cols - 1) // cols
scale = 2
sheet = Image.new('RGB', (cols * COLS * 8 * scale, rows * ROWS * 8 * scale),
                  (16, 16, 16))
d = ImageDraw.Draw(sheet)

for i, tile_off in enumerate(CANDS):
    img = Image.new('RGB', (COLS * 8 * scale, ROWS * 8 * scale), (0, 0, 0))
    dd = ImageDraw.Draw(img)
    ok = 0
    for c in range(ROWS * COLS):
        w = b[MAP + c * 2] | (b[MAP + c * 2 + 1] << 8)
        t = w & 0xFFF
        src = tile_off + (t - BASE) * 32
        if src < 0 or src + 32 > len(b):
            continue
        ok += 1
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (c % COLS) * 8, (c // COLS) * 8
        for r in range(8):
            for x in range(8):
                dd.point(((tx + x) * scale, (ty + r) * scale),
                         pal[((w >> 12) * 16 + px[r][x]) % 64])
    cx = (i % cols) * COLS * 8 * scale
    cy = (i // cols) * ROWS * 8 * scale
    d.rectangle([cx, cy, cx + COLS * 8 * scale, cy + 12], fill=(32, 32, 32))
    d.text((cx + 4, cy + 2), 'tiles $%06X  %d cells' % (tile_off, ok),
           fill=(255, 255, 255))
    sheet.paste(img, (cx, cy + 14))
    print('tiles $%06X: %d/%d cells' % (tile_off, ok, ROWS * COLS))

out = 'build/gfx/stg2a/contact.png'
sheet.save(out)
print('wrote', out)
