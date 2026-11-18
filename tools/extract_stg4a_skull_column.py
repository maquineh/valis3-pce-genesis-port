#!/usr/bin/env python3
"""Extract two STG4A skull-column poses into 32x80 Mega Drive sprites.

Animation 0x1A contains frame 0x2D and 0x2E for six updates each. The original
type-05 initializer selects PCE palette 2.
Each output frame is split into 32x32, 32x32, and 32x16 VDP sprite pieces.
"""
import argparse
from pathlib import Path

from pce_state import decompress, parse
from render_pce_state import decode_sprite, word
from extract_stg4a_skull_anim import rgb_md, rgb_pce


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', type=Path)
    parser.add_argument('md_palette', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    v = parse(decompress(str(args.state)))
    data, vram, cram = (v[k][2] for k in ('CDRAM', 'VRAM', 'color_table'))
    if data[0xA000:0xA005] != b'STG4A':
        raise ValueError('expected STG4A')
    anim = word(data, 0xA744 + 0x1A * 2)
    if data[anim:anim + 5] != bytes.fromhex('02 06 2e 06 2d'):
        raise ValueError('unexpected column animation')
    palette = args.md_palette.read_bytes()
    if len(palette) != 32:
        raise ValueError('expected 16 Mega Drive palette words')
    md = [rgb_md(int.from_bytes(palette[i:i+2], 'big')) for i in range(0, 32, 2)]
    src = [rgb_pce(word(cram, 512 + (2 * 16 + i) * 2)) for i in range(16)]
    mapping = [0] + [min(range(1, 16), key=lambda k: sum(
        (a - b) ** 2 for a, b in zip(src[i], md[k]))) for i in range(1, 16)]
    out = bytearray()
    for frame, expected in ((0x2D, (0x01D0, 0x01C0)),
                            (0x2E, (0x01F0, 0x01E0))):
        ptr = word(data, 0xA7E4 + frame * 2)
        if data[ptr] != 2:
            raise ValueError('unexpected column frame size')
        canvas = [[0] * 32 for _ in range(80)]
        for part in (1, 0):
            off = ptr + 1 + part * 5
            flags, y, x = data[off:off + 3]
            pattern = word(data, off + 3)
            if (flags, y, x, pattern) != ((0x01, 0xF0, 0xF0, expected[0]),
                                          (0x31, 0xB0, 0xF0, expected[1]))[part]:
                raise ValueError('unexpected column sprite descriptor')
            y = (y if y < 128 else y - 256) + 80
            rows = decode_sprite(vram, pattern, (flags << 8) | 0x82)
            for yy, row in enumerate(rows):
                row = row[8:16] + row[:8] + row[24:32] + row[16:24]
                for x, color in enumerate(row):
                    if color:
                        canvas[y + yy][x] = mapping[color]
        for sy, height in ((0, 32), (32, 32), (64, 16)):
            for tx in range(4):
                for ty in range(height // 8):
                    for y in range(8):
                        row = canvas[sy + ty * 8 + y]
                        for x in range(0, 8, 2):
                            out.append((row[tx * 8 + x] << 4) | row[tx * 8 + x + 1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out)
    print('wrote %d bytes: frames 2D and 2E' % len(out))


if __name__ == '__main__':
    main()
