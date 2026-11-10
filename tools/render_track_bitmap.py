import sys
from PIL import Image

src = open(sys.argv[1], 'rb').read()
off = int(sys.argv[2], 0)
w = int(sys.argv[3], 0)
h = int(sys.argv[4], 0)
out = sys.argv[5]
pal_file = sys.argv[6]
pal_off = int(sys.argv[7], 0)
order = sys.argv[8] if len(sys.argv) > 8 else 'low'

palb = open(pal_file, 'rb').read()
def color(v):
    b = v & 7
    r = (v >> 3) & 7
    g = (v >> 6) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)
pal = [color(palb[pal_off + i * 2] | (palb[pal_off + i * 2 + 1] << 8)) for i in range(64)]

S = 2
img = Image.new('RGB', (w * S, h * S), (0, 0, 0))
px = img.load()
for y in range(h):
    for x in range(w):
        byte = src[off + y * (w // 2) + (x // 2)]
        v = (byte & 0x0F) if (order == 'low') == ((x & 1) == 0) else (byte >> 4)
        c = pal[v & 63]
        for dy in range(S):
            for dx in range(S):
                px[x * S + dx, y * S + dy] = c
img.save(out)
print('wrote', out, 'off', hex(off), order)
