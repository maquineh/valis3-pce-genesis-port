"""Render a raw STG word region as a PCE BAT using live Stage 2 VRAM/CRAM."""
import sys
sys.path.insert(0, 'tools')
from PIL import Image
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
v = parse(decompress(STATE))
vram = v['VRAM'][2]
cram = v['color_table'][2]
wv = [vram[2 * i] | (vram[2 * i + 1] << 8) for i in range(len(vram) // 2)]
wc = [cram[2 * i] | (cram[2 * i + 1] << 8) for i in range(len(cram) // 2)]


def color(v):
    b = v & 7
    r = (v >> 3) & 7
    g = (v >> 6) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


pal = [color(c) for c in wc]


def render(path, off, width, height, out):
    d = open(path, 'rb').read()
    img = Image.new('RGB', (width * 8, height * 8), (0, 0, 0))
    pix = img.load()
    for y in range(height):
        for x in range(width):
            p = off + (y * width + x) * 2
            e = d[p] | (d[p + 1] << 8)
            tile = e & 0x7FF
            palno = (e >> 12) & 0xF
            base = tile * 16
            if base + 16 > len(wv):
                continue
            for py in range(8):
                w0 = wv[base + py * 2]
                w1 = wv[base + py * 2 + 1]
                for px in range(8):
                    bit = 7 - px
                    vv = (w0 >> bit) & 1
                    vv |= ((w0 >> (bit + 8)) & 1) << 1
                    vv |= ((w1 >> bit) & 1) << 2
                    vv |= ((w1 >> (bit + 8)) & 1) << 3
                    pix[x * 8 + px, y * 8 + py] = pal[(palno * 16 + vv) & 0x1FF]
    img.save(out)
    print('wrote', out, 'off', hex(off), 'size', width, 'x', height)


base = 344 * 2352 + 16
d = open('build/extracted/data/track_02.bin', 'rb').read()
for off, w, h, name in (
        (0x27C8, 34, 32, 'm27c8_34x32'),
        (0x27C8, 32, 32, 'm27c8_32x32'),
        (0x2A48, 34, 32, 'm2a48_34x32'),
        (0x2A48, 32, 32, 'm2a48_32x32'),
        (0x27C8, 64, 32, 'm27c8_64x32')):
    # temporarily write the block region to a file so render() can read it
    open('build/_stg2a.blk', 'wb').write(d[base:base + 0x14000])
    render('build/_stg2a.blk', off, w, h, 'build/gfx/%s.png' % name)
