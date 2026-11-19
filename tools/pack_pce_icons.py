#!/usr/bin/env python3
"""Pack the four original PC Engine HUD icons used as city item sprites.

The source is the HUD from the original PCE city capture
(build/city-audio/pce-06300.bmp, 256x243).  The icons are the two 8x16
equipment badges, the 16x16 character portrait and the 16x16 sword gem.

The pixel colours are mapped to the nearest entries of the captured city
palette line 1, which the background does not use in the rooftop rooms.  The
captured CRAM is therefore left untouched and the palette integrity tests keep
passing.
"""
from pathlib import Path
import struct

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'build/city-audio/pce-06300.bmp'
PALETTE_SOURCE = ROOT / 'game/res/gfx/city_late.bin'
OUT = ROOT / 'game/res/gfx/city_items.bin'

ICONS = (
    ('power', (32, 34, 48, 50), 0),   # sword gem
    ('health', (192, 19, 208, 35), 0),  # character portrait (extra life)
    ('magic', (136, 19, 144, 35), 4),   # gold/red ring badge
    ('mana', (176, 19, 184, 35), 4),    # gold/red bell badge
)


def gen_color(value):
    return (((value >> 1) & 7) * 255 // 7,
            ((value >> 5) & 7) * 255 // 7,
            ((value >> 9) & 7) * 255 // 7)


def main():
    image = Image.open(SOURCE).convert('RGB')
    data = PALETTE_SOURCE.read_bytes()
    line = struct.unpack_from('>16H', data, 2 * (3 + 16))[1:]
    palette = [gen_color(value) for value in line]

    def nearest(rgb):
        return min(range(1, 16), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb, palette[i - 1])))

    out = bytearray()
    for name, box, pad in ICONS:
        tile = Image.new('RGB', (16, 16), (0, 0, 0))
        tile.paste(image.crop(box), (pad, 0))
        pixels = [[nearest(tile.getpixel((x, y))) if tile.getpixel((x, y)) != (0, 0, 0) else 0
                   for x in range(16)] for y in range(16)]
        for cell_y in range(2):
            for cell_x in range(2):
                for y in range(8):
                    row = pixels[cell_y * 8 + y][cell_x * 8:cell_x * 8 + 8]
                    for x in range(0, 8, 2):
                        out.append((row[x] << 4) | row[x + 1])
        print('%-6s mapped' % name)
    OUT.write_bytes(out)
    print('wrote %s: %d bytes' % (OUT, len(out)))


if __name__ == '__main__':
    main()
