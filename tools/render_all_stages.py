"""Render each stage segment's map with the common tile blocks + own palette."""
import os
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()

# stage segment: (sector, label, palette offset, map offset)
STAGES = [
    (304, 'STG1A', 0x0AEB50, 0x0B1300),
    (344, 'STG2A', 0x0C5A4C, 0x0C8280),
    (384, 'STG2B', 0x0DC9F2, 0x0DF200),
    (424, 'STG2C', 0x0F3972, 0x0F5B80),
    (464, 'STG3A', 0x10A8CC, 0x10CB00),
    (504, 'STG3B', 0x12184C, 0x123A80),
    (544, 'STG4A', 0x1387CC, 0x13B000),
    (584, 'STG4B', 0x14F6EA, 0x151F80),
    (624, 'STG4C', 0x1666CC, 0x168F00),
    (664, 'STG5A', 0x17D654, 0x17FE80),
]

# common tile blocks (raw, uncompressed) decoded from the loader
TILE_BLOCKS = [
    (0x019440, 0x200, 'sec $2C'),
    (0x01AFD0, 0x200, 'sec $2F'),
    (0x01B900, 0x300, 'sec $30'),
    (0x01DDC0, 0x200, 'sec $34'),
    (0x0270C0, 0x500, 'sec $44'),
]

ROWS, COLS = 24, 32
os.makedirs('build/gfx/stages', exist_ok=True)
cols = 5
rows = (len(STAGES) + cols - 1) // cols
scale = 2
sheet = Image.new('RGB', (cols * COLS * 8 * scale, rows * ROWS * 8 * scale),
                  (16, 16, 16))
d = ImageDraw.Draw(sheet)

for i, (sec, label, pal_off, map_off) in enumerate(STAGES):
    pal = load_palette_md(b, pal_off, 64)
    tile_off, base, blabel = TILE_BLOCKS[0]      # the verified stage-1 block
    img = Image.new('RGB', (COLS * 8 * scale, ROWS * 8 * scale), (0, 0, 0))
    dd = ImageDraw.Draw(img)
    ok = 0
    for c in range(ROWS * COLS):
        w = b[map_off + c * 2] | (b[map_off + c * 2 + 1] << 8)
        t = w & 0xFFF
        src = tile_off + (t - base) * 32
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
    d.text((cx + 4, cy + 2), '%s map $%06X pal $%06X %d cells'
           % (label, map_off, pal_off, ok), fill=(255, 255, 255))
    sheet.paste(img, (cx, cy + 14))
    img.save('build/gfx/stages/%s.png' % label)
    print('%s: map $%06X + tiles $%06X base $%03X + pal $%06X -> %d/%d cells'
          % (label, map_off, tile_off, base, pal_off, ok, ROWS * COLS))

out = 'build/gfx/stages/contact.png'
sheet.save(out)
print('wrote', out)
