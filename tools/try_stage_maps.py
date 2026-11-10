import sys, os
from PIL import Image, ImageDraw
sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md

track6 = open('build/track_06_payload.bin', 'rb').read()
t2 = open('build/track_02_payload.bin', 'rb').read()
pal = load_palette_md(t2, 304 * 2048 + 0x240, 64)
ROWS, COLS = 28, 32

def render(src, map_off, tile_off, base, swap, out):
    img = Image.new('RGB', (COLS * 8 * 2, ROWS * 8 * 2), (0, 0, 0))
    pix = img.load()
    for i in range(ROWS * COLS):
        lo, hi = src[map_off + i * 2], src[map_off + i * 2 + 1]
        w = (hi | (lo << 8)) if swap else (lo | (hi << 8))
        t = w & 0xFFF
        p = w >> 12
        s = tile_off + (t - base) * 32
        if s < 0 or s + 32 > len(src):
            continue
        px = bg_tile_pixels(src[s:s + 32])
        tx, ty = (i % COLS) * 8, (i // COLS) * 8
        for r in range(8):
            for x in range(8):
                c = pal[(p * 16 + px[r][x]) % 64]
                for dy in range(2):
                    for dx in range(2):
                        pix[(tx + x) * 2 + dx, (ty + r) * 2 + dy] = c
    img.save(out)

os.makedirs('build/gfx/fmt', exist_ok=True)
cases = [
    ('stg1a_map_swap_t6_b0', t2, 304 * 2048 + 0x29F0, track6, 0, 0, True),
    ('stg1a_map_swap_t6_b100', t2, 304 * 2048 + 0x29F0, track6, 0, 0x100, True),
    ('stg1a_map_swap_t6_b200', t2, 304 * 2048 + 0x29F0, track6, 0, 0x200, True),
    ('t6_25700_swap_b0', track6, 0x25700, track6, 0, 0, True),
    ('t6_25700_swap_b100', track6, 0x25700, track6, 0, 0x100, True),
    ('t6_7F00_swap_b0', track6, 0x7F00, track6, 0, 0, True),
]
for name, src, mo, ts, to, base, swap in cases:
    # map and tile data come from potentially different files
    # render() uses src for both; write a two-file version
    img = Image.new('RGB', (COLS * 8 * 2, ROWS * 8 * 2), (0, 0, 0))
    pix = img.load()
    for i in range(ROWS * COLS):
        lo, hi = src[mo + i * 2], src[mo + i * 2 + 1]
        w = (hi | (lo << 8)) if swap else (lo | (hi << 8))
        t = w & 0xFFF
        p = w >> 12
        s = to + (t - base) * 32
        if s < 0 or s + 32 > len(ts):
            continue
        px = bg_tile_pixels(ts[s:s + 32])
        tx, ty = (i % COLS) * 8, (i // COLS) * 8
        for r in range(8):
            for x in range(8):
                c = pal[(p * 16 + px[r][x]) % 64]
                for dy in range(2):
                    for dx in range(2):
                        pix[(tx + x) * 2 + dx, (ty + r) * 2 + dy] = c
    img.save('build/gfx/fmt/%s.png' % name)
    print('wrote', name)
