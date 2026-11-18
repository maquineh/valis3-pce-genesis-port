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
        w = (pals[2 * i] << 8) | pals[2 * i + 1]
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
                e = (maps[p] << 8) | maps[p + 1]
                tile = e & 0x7FF
                pal = (e >> 13) & 3
                base = tile * 32
                if base + 32 > len(tiles):
                    continue
                for py in range(8):
                    for px in range(8):
                        packed = tiles[base + py * 4 + px // 2]
                        v = (packed >> 4) if px % 2 == 0 else (packed & 15)
                        pix[s * cols * 8 + x * 8 + px, y * 8 + py] = cram[pal * 16 + v]
    img.save(OUT)
    print('wrote', OUT, img.size)


if __name__ == '__main__':
    main()
