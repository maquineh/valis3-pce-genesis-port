#!/usr/bin/env python3
"""Extract three candidate 32x48 PCE frames from the STG4A save into MD tiles.

Patterns 0x160, 0x170, and 0x180 are visually coherent poses in the captured
VRAM. Their use as run/run/attack frames is an adaptation, not a decoded timing
table. Output tiles are in Genesis sprite column-major order.
"""
import argparse
from pathlib import Path

from pce_state import decompress, parse
from render_pce_state import decode_sprite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    variables = parse(decompress(str(args.state)))
    vram = variables['VRAM'][2]
    result = bytearray()
    for start in (0x160, 0x170, 0x180):
        image = []
        for row in range(3):
            pixels = decode_sprite(vram, (start + row * 2) * 2, 0x100)
            # Mednafen's little-endian VRAM words put the second byte first
            # on screen within each 16-pixel sprite cell.
            image.extend([r[8:16] + r[0:8] + r[24:32] + r[16:24]
                          for r in pixels])
        for sy, height in ((0, 32), (32, 16)):
            for tx in range(4):
                for ty in range(height // 8):
                    for y in range(8):
                        row = image[sy + ty * 8 + y]
                        for x in range(0, 8, 2):
                            result.append(row[tx * 8 + x] * 16 +
                                          row[tx * 8 + x + 1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print('wrote %d bytes (%d frames) to %s' %
          (len(result), len(result) // 768, args.output))


if __name__ == '__main__':
    main()
