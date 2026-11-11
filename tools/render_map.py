"""Render a full PCE BAT map (bat_w x bat_w tiles) from VRAM/CRAM."""
import sys
from PIL import Image


def words(buf, order):
    n = len(buf) // 2
    if order == 'be':
        return [(buf[2 * i] << 8) | buf[2 * i + 1] for i in range(n)]
    return [buf[2 * i] | (buf[2 * i + 1] << 8) for i in range(n)]


def color(v):
    b = v & 7
    r = (v >> 3) & 7
    g = (v >> 6) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def main():
    vram_path, cram_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    bat_w = int(sys.argv[4], 0) if len(sys.argv) > 4 else 64
    order = sys.argv[5] if len(sys.argv) > 5 else 'le'
    vram = words(open(vram_path, 'rb').read(), order)
    cram = words(open(cram_path, 'rb').read(), order)
    pal = [color(c) for c in cram]
    img = Image.new('RGB', (bat_w * 8, bat_w * 8), (0, 0, 0))
    pix = img.load()
    for ty in range(bat_w):
        for tx in range(bat_w):
            e = vram[(ty * bat_w + tx) & (len(vram) - 1)]
            tile = e & 0x7FF
            palno = (e >> 12) & 0xF
            base = tile * 16
            if base + 16 > len(vram):
                continue
            for py in range(8):
                w0 = vram[base + py * 2]
                w1 = vram[base + py * 2 + 1]
                for px in range(8):
                    bit = 7 - px
                    v = (w0 >> bit) & 1
                    v |= ((w0 >> (bit + 8)) & 1) << 1
                    v |= ((w1 >> bit) & 1) << 2
                    v |= ((w1 >> (bit + 8)) & 1) << 3
                    pix[tx * 8 + px, ty * 8 + py] = pal[(palno * 16 + v) & 0xFF]
    img.save(out)
    print('wrote', out, 'map', bat_w)


if __name__ == '__main__':
    main()
