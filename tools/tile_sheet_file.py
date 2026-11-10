import sys
from PIL import Image

b = open('build/extracted/data/track_02.bin', 'rb').read()

def tile_pixels(src):
    px = [[0] * 8 for _ in range(8)]
    for r in range(8):
        b0, b1 = src[r * 2], src[r * 2 + 1]
        b2, b3 = src[16 + r * 2], src[16 + r * 2 + 1]
        for x in range(8):
            bit = 7 - x
            v = ((b0 >> bit) & 1)
            v |= ((b1 >> bit) & 1) << 1
            v |= ((b2 >> bit) & 1) << 2
            v |= ((b3 >> bit) & 1) << 3
            px[r][x] = v
    return px

def sheet(off, count, out, cols=32, scale=2):
    rows = (count + cols - 1) // cols
    img = Image.new('RGB', (cols * 8 * scale, rows * 8 * scale), (0, 0, 0))
    pix = img.load()
    for t in range(count):
        src = b[off + t * 32:off + t * 32 + 32]
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
    print('wrote', out, 'off', hex(off), 'count', count)

if __name__ == '__main__':
    sheet(int(sys.argv[1], 0), int(sys.argv[2], 0), sys.argv[3])
