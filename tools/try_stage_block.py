"""Render a stage block (palette + map + tiles) from its own 40-sector group."""
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()

# stage block: sector -> palette file offset, map "leader" offset
BLOCKS = [
    (304, 0x0AEB50, 0x0B1200),
    (308, 0x0B0DF8, None),
    (344, 0x0C5A4C, 0x0C8000),
    (384, 0x0DC9F2, 0x0DEE00),
    (424, 0x0F3972, 0x0F5C00),
    (464, 0x10A8CC, 0x10CA00),
    (504, 0x12184C, None),
    (544, 0x1387CC, None),
    (584, 0x14F6EA, None),
    (624, 0x1666CC, None),
    (664, 0x17D654, 0x17FC00),
]

sec = int(sys.argv[1], 0) if len(sys.argv) > 1 else 344
map_off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x0C8000

row = [r for r in BLOCKS if r[0] == sec]
pal_off = row[0][1] if row else 0x0C5A4C
pal = load_palette_md(b, pal_off, 64)

block_start = sec * 2352
block_end = block_start + 40 * 2352

# try candidate tile offsets inside the stage block
print('stage block sector %d: $%06X-$%06X, palette $%06X, map $%06X'
      % (sec, block_start, block_end, pal_off, map_off))

cands = []
off = block_start + 0x2000
while off < block_end - 0x8000:
    cands.append(off)
    off += 0x1000

ROWS, COLS = 24, 32
for tile_off in cands[:14]:
    img = Image.new('RGB', (COLS * 8 * 3, ROWS * 8 * 3), (0, 0, 0))
    d = ImageDraw.Draw(img)
    ok = 0
    for i in range(ROWS * COLS):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        t = w & 0xFFF
        src = tile_off + (t - 0x200) * 32
        if src < 0 or src + 32 > len(b):
            continue
        ok += 1
        px = bg_tile_pixels(b[src:src + 32])
        tx, ty = (i % COLS) * 8, (i // COLS) * 8
        for r in range(8):
            for x in range(8):
                d.point(((tx + x) * 3, (ty + r) * 3),
                        pal[((w >> 12) * 16 + px[r][x]) % 64])
    out = 'build/gfx/stage_s%d_t%06X.png' % (sec, tile_off)
    img.save(out)
    print('   tiles $%06X: %d/%d cells -> %s' % (tile_off, ok, ROWS * COLS, out))
