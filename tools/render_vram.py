import sys
from PIL import Image

vram = open(sys.argv[1], 'rb').read()
# PCE VRAM is 16-bit words, little-endian in the file (low, high per word)
def word(addr):
    return vram[addr * 2] | (vram[addr * 2 + 1] << 8)

def tile_pixels(tile_word):
    """PCE 4bpp tile: 16 words; each row = 2 words (planes 0/1 then 2/3)."""
    base = tile_word * 16
    px = [[0] * 8 for _ in range(8)]
    for r in range(8):
        w0 = word(base + r * 2)
        w1 = word(base + r * 2 + 1)
        for x in range(8):
            bit = 7 - x
            v = ((w0 >> bit) & 1)
            v |= ((w0 >> (bit + 8)) & 1) << 1
            v |= ((w1 >> bit) & 1) << 2
            v |= ((w1 >> (bit + 8)) & 1) << 3
            px[r][x] = v
    return px

def render(bat_word, tile_base, out, w=32, h=28, scale=2):
    img = Image.new('RGB', (w * 8 * scale, h * 8 * scale), (0, 0, 0))
    pix = img.load()
    def gray(v):
        c = v * 17
        return (c, c, c)
    for i in range(w * h):
        e = word(bat_word + i)
        t = (e & 0xFFF) + tile_base
        pal = e >> 12
        px = tile_pixels(t)
        tx, ty = (i % w) * 8, (i // w) * 8
        for r in range(8):
            for x in range(8):
                c = gray((px[r][x] + pal * 3) & 15)
                for dy in range(scale):
                    for dx in range(scale):
                        pix[(tx + x) * scale + dx, (ty + r) * scale + dy] = c
    img.save(out)
    print('wrote', out, 'bat', hex(bat_word), 'base', hex(tile_base))

def sheet(tile_base, count, out, scale=2, cols=32):
    rows = (count + cols - 1) // cols
    img = Image.new('RGB', (cols * 8 * scale, rows * 8 * scale), (0, 0, 0))
    pix = img.load()
    for t in range(count):
        px = tile_pixels(tile_base + t)
        ox, oy = (t % cols) * 8, (t // cols) * 8
        for r in range(8):
            for x in range(8):
                c = px[r][x] * 17
                for dy in range(scale):
                    for dx in range(scale):
                        pix[(ox + x) * scale + dx, (oy + r) * scale + dy] = (c, c, c)
    img.save(out)
    print('wrote', out, 'tiles', hex(tile_base), count)

if __name__ == '__main__':
    mode = sys.argv[2]
    if mode == 'sheet':
        sheet(int(sys.argv[3], 0), int(sys.argv[4], 0), sys.argv[5])
    else:
        render(int(sys.argv[3], 0), int(sys.argv[4], 0), sys.argv[5],
               int(sys.argv[6]) if len(sys.argv) > 6 else 32,
               int(sys.argv[7]) if len(sys.argv) > 7 else 28)
