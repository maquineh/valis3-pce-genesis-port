import sys
from PIL import Image

b = open('build/extracted/data/track_02.bin', 'rb').read()

def render(off, w, h, out, mode='packed', scale=2):
    img = Image.new('RGB', (w * scale, h * scale), (0, 0, 0))
    pix = img.load()
    if mode == 'packed':
        for y in range(h):
            for x in range(w):
                byte = b[off + y * (w // 2) + (x // 2)]
                v = (byte & 0x0F) if (x & 1) == 0 else (byte >> 4)
                c = v * 17
                for dy in range(scale):
                    for dx in range(scale):
                        pix[x * scale + dx, y * scale + dy] = (c, c, c)
    else:
        # 4 bitplanes, each plane is one bit per pixel, rows padded to bytes
        stride = (w + 7) // 8
        plane_size = stride * h
        for y in range(h):
            for x in range(w):
                v = 0
                for p in range(4):
                    byte = b[off + p * plane_size + y * stride + (x // 8)]
                    v |= ((byte >> (7 - (x % 8))) & 1) << p
                c = v * 17
                for dy in range(scale):
                    for dx in range(scale):
                        pix[x * scale + dx, y * scale + dy] = (c, c, c)
    img.save(out)
    print('wrote', out, 'off', hex(off), 'mode', mode, w, 'x', h)

if __name__ == '__main__':
    render(int(sys.argv[1], 0), int(sys.argv[2]), int(sys.argv[3]),
           sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else 'packed',
           int(sys.argv[6]) if len(sys.argv) > 6 else 2)
