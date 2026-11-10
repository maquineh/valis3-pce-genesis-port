import sys
from PIL import Image

b = open(sys.argv[1], 'rb').read()
off0 = int(sys.argv[2], 0)
count = int(sys.argv[3], 0)
out = sys.argv[4]

def tile_pixels(src):
    px = [[0] * 8 for _ in range(8)]
    for r in range(8):
        b0, b1 = src[r * 2], src[r * 2 + 1]
        b2, b3 = src[16 + r * 2], src[16 + r * 2 + 1]
        for x in range(8):
            bit = 7 - x
            v = (b0 >> bit) & 1
            v |= ((b1 >> bit) & 1) << 1
            v |= ((b2 >> bit) & 1) << 2
            v |= ((b3 >> bit) & 1) << 3
            px[r][x] = v
    return px

cols = 32
rows = (count + cols - 1) // cols
scale = 2
img = Image.new('RGB', (cols * 8 * scale, rows * 8 * scale), (0, 0, 0))
pix = img.load()
for t in range(count):
    src = b[off0 + t * 32:off0 + t * 32 + 32]
    if len(src) < 32:
        continue
    px = tile_pixels(src)
    ox, oy = (t % cols) * 8, (t // cols) * 8
    for r in range(8):
        for x in range(8):
            c = px[r][x] * 17
            for dy in range(scale):
                for dx in range(scale):
                    pix[(ox + x) * scale + dx, (oy + r) * scale + dy] = (c, c, c)
img.save(out)
print('wrote', out, hex(off0), count)
