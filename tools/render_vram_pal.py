import sys
from PIL import Image

vram = open(sys.argv[1], 'rb').read()
cram = open(sys.argv[2], 'rb').read()

def w(buf, a):
    return buf[a * 2] | (buf[a * 2 + 1] << 8)

def color(v):
    b = v & 7
    r = (v >> 3) & 7
    g = (v >> 6) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)

pal = [color(w(cram, i)) for i in range(256)]

def tile_pixels(t):
    t &= 0x7FF
    base = t * 16
    px = [[0] * 8 for _ in range(8)]
    if base + 16 > len(vram) // 2:
        return px
    for r in range(8):
        w0 = w(vram, base + r * 2)
        w1 = w(vram, base + r * 2 + 1)
        for x in range(8):
            bit = 7 - x
            v = (w0 >> bit) & 1
            v |= ((w0 >> (bit + 8)) & 1) << 1
            v |= ((w1 >> bit) & 1) << 2
            v |= ((w1 >> (bit + 8)) & 1) << 3
            px[r][x] = v
    return px

def render(bat_word, tile_base, out, ww=32, hh=28, scale=2):
    img = Image.new('RGB', (ww * 8 * scale, hh * 8 * scale), (0, 0, 0))
    pix = img.load()
    for i in range(ww * hh):
        e = w(vram, bat_word + i)
        t = (e & 0xFFF) + tile_base
        p = e >> 12
        px = tile_pixels(t)
        tx, ty = (i % ww) * 8, (i // ww) * 8
        for r in range(8):
            for x in range(8):
                c = pal[(p * 16 + px[r][x]) & 0xFF]
                for dy in range(scale):
                    for dx in range(scale):
                        pix[(tx + x) * scale + dx, (ty + r) * scale + dy] = c
    img.save(out)
    print('wrote', out, 'bat', hex(bat_word), 'tiles', hex(tile_base))

if __name__ == '__main__':
    render(int(sys.argv[3], 0), int(sys.argv[4], 0), sys.argv[5])
