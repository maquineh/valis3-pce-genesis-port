import sys
from PIL import Image, ImageDraw

b = open('build/extracted/data/track_02.bin', 'rb').read()

def mapview(off, out, w=32, h=24, scale=4, mode='index'):
    img = Image.new('RGB', (w * scale, h * scale), (0, 0, 0))
    pix = img.load()
    for i in range(w * h):
        word = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
        t = word & 0xFFF
        pal = word >> 12
        if mode == 'index':
            # spread the 12-bit index over hue-ish RGB
            r = (t * 37) & 0xFF
            g = (t * 91) & 0xFF
            bl = (t * 53) & 0xFF
        elif mode == 'pal':
            r = (pal * 17) & 0xFF
            g = (pal * 37) & 0xFF
            bl = (pal * 71) & 0xFF
        else:
            v = (t & 0xFF)
            r = g = bl = v
        for dy in range(scale):
            for dx in range(scale):
                pix[(i % w) * scale + dx, (i // w) * scale + dy] = (r, g, bl)
    img.save(out)
    print('wrote', out)

if __name__ == '__main__':
    mapview(int(sys.argv[1], 0), sys.argv[2],
            int(sys.argv[3]) if len(sys.argv) > 3 else 32,
            int(sys.argv[4]) if len(sys.argv) > 4 else 24,
            int(sys.argv[5]) if len(sys.argv) > 5 else 4,
            sys.argv[6] if len(sys.argv) > 6 else 'index')
