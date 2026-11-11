"""Render the packed Mega CD stage2_state resources back to a PNG."""
import sys
from PIL import Image

OUT = 'build/gfx/%s_screen.png' % (__import__("sys").argv[1] if len(__import__("sys").argv)>1 else "stage2_state")


def main():
    tiles = open('game/res/gfx/%s_tiles.bin' % (__import__("sys").argv[1] if len(__import__("sys").argv)>1 else "stage2_state"), 'rb').read()
    maps = open('game/res/gfx/%s_maps.bin' % (__import__("sys").argv[1] if len(__import__("sys").argv)>1 else "stage2_state"), 'rb').read()
    pals = open('game/res/gfx/%s_pal.bin' % (__import__("sys").argv[1] if len(__import__("sys").argv)>1 else "stage2_state"), 'rb').read()
    cram = []
    for i in range(64):
        w = pals[2 * i] | (pals[2 * i + 1] << 8)
        r = (w >> 1) & 7
        g = (w >> 5) & 7
        b = (w >> 9) & 7
        cram.append((r * 255 // 7, g * 255 // 7, b * 255 // 7))
    cols, rows = 32, 24
    screens = max(1, len(maps) // (cols * rows * 2))
    img = Image.new('RGB', (cols * 8 * screens, rows * 8), (0, 0, 0))
    pix = img.load()
    for s in range(screens):
        for y in range(rows):
            for x in range(cols):
                p = ((s * rows + y) * cols + x) * 2
                e = maps[p] | (maps[p + 1] << 8)
                tile = e & 0x7FF
                pal = (e >> 13) & 3
                base = tile * 32
                if base + 32 > len(tiles):
                    continue
                for py in range(8):
                    p0 = tiles[base + py * 4 + 0]
                    p1 = tiles[base + py * 4 + 1]
                    p2 = tiles[base + py * 4 + 2]
                    p3 = tiles[base + py * 4 + 3]
                    for px in range(8):
                        bit = 7 - px
                        v = ((p0 >> bit) & 1)
                        v |= ((p1 >> bit) & 1) << 1
                        v |= ((p2 >> bit) & 1) << 2
                        v |= ((p3 >> bit) & 1) << 3
                        pix[s * cols * 8 + x * 8 + px, y * 8 + py] = cram[pal * 16 + v]
    img.save(OUT)
    print('wrote', OUT, img.size)


if __name__ == '__main__':
    main()
