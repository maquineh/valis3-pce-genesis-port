"""Render a raw STG word region using the STG block's own raw tiles."""
import sys
sys.path.insert(0, 'tools')
from PIL import Image
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
v = parse(decompress(STATE))
cram = v['color_table'][2]
wc = [cram[2 * i] | (cram[2 * i + 1] << 8) for i in range(len(cram) // 2)]


def color(v):
    b = v & 7
    r = (v >> 3) & 7
    g = (v >> 6) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


pal = [color(c) for c in wc]
d = open('build/extracted/data/track_02.bin', 'rb').read()
base = 344 * 2352 + 16
blk = d[base:base + 0x14000]
TILES = 0x6E40


def render(off, width, height, out):
    img = Image.new('RGB', (width * 8, height * 8), (0, 0, 0))
    pix = img.load()
    for y in range(height):
        for x in range(width):
            p = off + (y * width + x) * 2
            e = blk[p] | (blk[p + 1] << 8)
            tile = e & 0x7FF
            palno = (e >> 12) & 0xF
            src = TILES + (tile - 0x100) * 32
            if src < 0 or src + 32 > len(blk):
                continue
            for py in range(8):
                w0 = blk[src + py * 2] | (blk[src + py * 2 + 1] << 8)
                w1 = blk[src + 16 + py * 2] | (blk[src + 16 + py * 2 + 1] << 8)
                for px in range(8):
                    bit = 7 - px
                    vv = (w0 >> bit) & 1
                    vv |= ((w0 >> (bit + 8)) & 1) << 1
                    vv |= ((w1 >> bit) & 1) << 2
                    vv |= ((w1 >> (bit + 8)) & 1) << 3
                    pix[x * 8 + px, y * 8 + py] = pal[(palno * 16 + vv) & 0x1FF]
    img.save(out)
    print('wrote', out, 'off', hex(off), 'size', width, 'x', height)


for off, w, h, name in (
        (0x27C8, 34, 32, 'b27c8_34x32'),
        (0x2A48, 34, 32, 'b2a48_34x32'),
        (0x27C8, 32, 32, 'b27c8_32x32'),
        (0x2A48, 32, 32, 'b2a48_32x32')):
    render(off, w, h, 'build/gfx/%s.png' % name)
