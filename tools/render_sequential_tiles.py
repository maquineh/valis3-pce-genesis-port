import sys
from PIL import Image
sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels, load_palette_md

data = open(sys.argv[1], 'rb').read()
off = int(sys.argv[2], 0)
ntiles = int(sys.argv[3], 0)
pal_file = sys.argv[4]
pal_off = int(sys.argv[5], 0)
out = sys.argv[6]

pal = load_palette_md(open(pal_file, 'rb').read(), pal_off, 64)
COLS, ROWS = 32, 28
S = 2
img = Image.new('RGB', (COLS * 8 * S, ROWS * 8 * S), (0, 0, 0))
pix = img.load()
for t in range(ntiles):
    s = off + t * 32
    if s + 32 > len(data):
        break
    px = bg_tile_pixels(data[s:s + 32])
    ox, oy = (t % COLS) * 8, (t // COLS) * 8
    for r in range(8):
        for x in range(8):
            c = pal[px[r][x] % 64]
            for dy in range(S):
                for dx in range(S):
                    pix[(ox + x) * S + dx, (oy + r) * S + dy] = c
img.save(out)
print('wrote', out, 'tiles', ntiles, 'pal', hex(pal_off))
