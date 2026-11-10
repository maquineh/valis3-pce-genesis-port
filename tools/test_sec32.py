"""Render the stage screen with the 24-sector tile block from sector 32."""
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()
MAP = 0x17FF90
PAL = 0x9352
ROWS, COLS = 24, 32
pal = load_palette_md(b, PAL, 64)

# cd_read at $23E836: sector 32, 24 sectors, dest $1000 (dh=$FF)
BLOCKS = [
    ('sec32 x24 -> VRAM $100', 0x12600, 0x100, 24 * 2352),
    ('sec32 x24 -> VRAM $100 (mask 7FF)', 0x12600, 0x100, 24 * 2352),
]

for name, tiles, base, size in BLOCKS:
    mask = 0x7FF if 'mask' in name else 0xFFF
    ntiles = size // 32
    img = Image.new('RGB', (COLS * 8 * 3, ROWS * 8 * 3), (0, 0, 0))
    d = ImageDraw.Draw(img)
    ok = 0
    for i in range(ROWS * COLS):
        w = b[MAP + i * 2] | (b[MAP + i * 2 + 1] << 8)
        t = w & mask
        paln = (w >> 12) & 0xF
        if not (base <= t < base + ntiles):
            continue
        src = tiles + (t - base) * 32
        if src < 0 or src + 32 > len(b):
            continue
        ok += 1
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (i % COLS) * 8, (i // COLS) * 8
        for r in range(8):
            for x in range(8):
                d.point(((tx + x) * 3, (ty + r) * 3),
                        pal[(paln * 16 + px[r][x]) % 64])
    out = 'build/gfx/sec32_%d_%d.png' % (tiles, mask)
    img.save(out)
    print('%-34s %d/%d cells -> %s' % (name, ok, ROWS * COLS, out))
