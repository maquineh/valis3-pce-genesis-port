"""Render a PCE VRAM tile sheet (word-addressed 4bpp tiles) with a 16-colour palette."""
import sys
from PIL import Image


def words(buf):
    return [buf[2 * i] | (buf[2 * i + 1] << 8) for i in range(len(buf) // 2)]


def color(v):
    b = v & 7
    r = (v >> 3) & 7
    g = (v >> 6) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def main():
    vram = words(open(sys.argv[1], 'rb').read())
    cram = words(open(sys.argv[2], 'rb').read())
    out = sys.argv[3]
    start = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
    count = int(sys.argv[5], 0) if len(sys.argv) > 5 else 2048
    palno = int(sys.argv[6], 0) if len(sys.argv) > 6 else 0
    per_row = 32
    rows = (count + per_row - 1) // per_row
    img = Image.new('RGB', (per_row * 8, rows * 8), (0, 0, 0))
    pix = img.load()
    for t in range(count):
        base = (start + t) * 16
        if base + 16 > len(vram):
            break
        tx = (t % per_row) * 8
        ty = (t // per_row) * 8
        for py in range(8):
            w0 = vram[base + py * 2]
            w1 = vram[base + py * 2 + 1]
            for px in range(8):
                bit = 7 - px
                v = (w0 >> bit) & 1
                v |= ((w0 >> (bit + 8)) & 1) << 1
                v |= ((w1 >> bit) & 1) << 2
                v |= ((w1 >> (bit + 8)) & 1) << 3
                pix[tx + px, ty + py] = color(cram[(palno * 16 + v) & 0x1FF])
    img.save(out)
    print('wrote', out, 'tiles', count, 'from', start)


if __name__ == '__main__':
    main()
