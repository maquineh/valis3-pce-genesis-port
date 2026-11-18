"""Render a PCE screen from a raw VRAM/CRAM dump with BAT scrolling.

Usage: python3 tools/render_scrolled.py VRAM CRAM OUT BX BY [BAT_W] [WO]
WO=le|be selects the byte order of the 16-bit words.
"""
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


def tile_pixel(vram, tile, y, x):
    """Decode one PCE 8x8 background pixel from VRAM words.

    Each tile is 32 bytes (16 little-endian words). Planes 0/1 are
    interleaved in words 0..7 and planes 2/3 in words 8..15.
    """
    base = tile * 16
    bit = 7 - x
    low_planes = vram[base + y]
    high_planes = vram[base + 8 + y]
    return ((low_planes >> bit) & 1) \
        | (((low_planes >> (bit + 8)) & 1) << 1) \
        | (((high_planes >> bit) & 1) << 2) \
        | (((high_planes >> (bit + 8)) & 1) << 3)


def main():
    vram_path, cram_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    bx = int(sys.argv[4], 0)
    by = int(sys.argv[5], 0)
    bat_w = int(sys.argv[6], 0) if len(sys.argv) > 6 else 64
    order = sys.argv[7] if len(sys.argv) > 7 else 'le'
    vram = words(open(vram_path, 'rb').read(), order)
    cram = words(open(cram_path, 'rb').read(), order)
    pal = [color(c) for c in cram]
    img = Image.new('RGB', (256, 224), (0, 0, 0))
    pix = img.load()
    for sy in range(224):
        my = (by + sy) & 511
        row = my >> 3
        py = my & 7
        for sx in range(256):
            mx = (bx + sx) & 511
            col = mx >> 3
            px = mx & 7
            e = vram[(row * bat_w + col) & (len(vram) - 1)]
            tile = e & 0x7FF
            palno = (e >> 12) & 0xF
            if tile * 16 + 16 > len(vram):
                continue
            v = tile_pixel(vram, tile, py, px)
            pix[sx, sy] = pal[(palno * 16 + v) & 0xFF]
    img = img.resize((512, 448), Image.NEAREST)
    img.save(out)
    print('wrote', out, 'bx', bx, 'by', by, 'bat_w', bat_w, 'order', order)


if __name__ == '__main__':
    main()
