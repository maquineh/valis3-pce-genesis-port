"""Pick the common tile block that best covers each stage's map, then render."""
import os
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()

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

# (file offset, byte size, VRAM word, loader site)
TILE_BLOCKS = [
    (0x019440, 0xC000, 0x1000, 'sec $2C'),
    (0x01AFD0, 0xC000, 0x1000, 'sec $2F'),
    (0x01B900, 0xA000, 0x3000, 'sec $30'),
    (0x01DDC0, 0x6000, 0x2000, 'sec $34'),
    (0x0270C0, 0x2000, 0x5000, 'sec $44'),
    (0x006E40, 0xA000, 0x1000, 'sec $0C title'),
]

ROWS, COLS = 24, 32


def coverage(map_off, blk):
    off, size, word, label = blk
    base = word // 16
    ntiles = size // 32
    n = 0
    for i in range(ROWS * COLS):
        t = (b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)) & 0xFFF
        if base <= t < base + ntiles:
            n += 1
    return n / (ROWS * COLS), base


print('%-7s %-9s %-22s %7s %7s' % ('stage', 'map', 'best tile block', 'cov', 'tiles'))
picks = []
for sec, label, pal_off, map_off in STAGES:
    rows = []
    for blk in TILE_BLOCKS:
        cov, base = coverage(map_off, blk)
        rows.append((cov, blk, base))
    rows.sort(reverse=True)
    cov, blk, base = rows[0]
    picks.append((label, pal_off, map_off, blk, base, cov))
    print('%-7s $%06X  %-22s %7.2f  base $%03X'
          % (label, map_off, blk[3], cov, base))

os.makedirs('build/gfx/stages2', exist_ok=True)
cols = 5
rowsn = (len(picks) + cols - 1) // cols
scale = 2
sheet = Image.new('RGB', (cols * COLS * 8 * scale, rowsn * ROWS * 8 * scale),
                  (16, 16, 16))
d = ImageDraw.Draw(sheet)

for i, (label, pal_off, map_off, blk, base, cov) in enumerate(picks):
    pal = load_palette_md(b, pal_off, 64)
    off, size, word, blabel = blk
    img = Image.new('RGB', (COLS * 8 * scale, ROWS * 8 * scale), (0, 0, 0))
    dd = ImageDraw.Draw(img)
    ok = 0
    for c in range(ROWS * COLS):
        w = b[map_off + c * 2] | (b[map_off + c * 2 + 1] << 8)
        t = w & 0xFFF
        src = off + (t - base) * 32
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
    d.text((cx + 4, cy + 2), '%s %s cov=%.2f' % (label, blabel, cov),
           fill=(255, 255, 255))
    sheet.paste(img, (cx, cy + 14))
    img.save('build/gfx/stages2/%s.png' % label)
    print('%s rendered with %s (%d/%d cells) -> build/gfx/stages2/%s.png'
          % (label, blabel, ok, ROWS * COLS, label))

out = 'build/gfx/stages2/contact.png'
sheet.save(out)
print('wrote', out)
