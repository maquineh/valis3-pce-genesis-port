#!/usr/bin/env python3
"""Extract STG4A animation 0x1F skull frames into Mega Drive sprite tiles.

The source state supplies the original frame descriptors and VRAM. The original
type-06 initializer selects palette 2. Map its colors to the supplied Mega
Drive palette. Timing is read in reverse order, as in the original HuC6280
animation update routine.
"""
import argparse
from pathlib import Path

from pce_state import decompress, parse
from render_pce_state import decode_sprite, word


def rgb_pce(value):
    return ((value >> 3) & 7, (value >> 6) & 7, value & 7)


def rgb_md(value):
    return ((value >> 1) & 7, (value >> 5) & 7, (value >> 9) & 7)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('state', type=Path)
    ap.add_argument('md_palette', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    state = parse(decompress(str(args.state)))
    data, vram, cram = (state[k][2] for k in ('CDRAM', 'VRAM', 'color_table'))
    if data[0xA000:0xA005] != b'STG4A':
        raise ValueError('expected STG4A')
    addr = word(data, 0xA744 + 0x1F * 2)
    if data[addr:addr + 5] != bytes.fromhex('02 05 34 05 33'):
        raise ValueError('unexpected STG4A animation 0x1F')
    md_raw = args.md_palette.read_bytes()
    if len(md_raw) != 32:
        raise ValueError('expected 16 Mega Drive palette words')
    md = [rgb_md(int.from_bytes(md_raw[i:i+2], 'big')) for i in range(0, 32, 2)]
    src = [rgb_pce(word(cram, 512 + (2 * 16 + i) * 2)) for i in range(16)]
    remap = [0] + [min(range(1, 16), key=lambda k: sum(
        (a - b) ** 2 for a, b in zip(src[i], md[k]))) for i in range(1, 16)]
    output = bytearray()
    for frame, expected in ((0x33, 0x01D8), (0x34, 0x01F8)):
        ptr = word(data, 0xA7E4 + frame * 2)
        if data[ptr:ptr + 4] != bytes.fromhex('01 11 E0 F0'):
            raise ValueError('unexpected skull sprite descriptor')
        pattern = word(data, ptr + 4)
        if pattern != expected:
            raise ValueError('unexpected skull pattern')
        rows = decode_sprite(vram, pattern, 0x1182)
        rows = [[remap[c] for c in
                 (r[8:16] + r[0:8] + r[24:32] + r[16:24])] for r in rows]
        for tx in range(4):
            for ty in range(4):
                for y in range(8):
                    row = rows[ty * 8 + y]
                    for x in range(0, 8, 2):
                        output.append((row[tx * 8 + x] << 4) | row[tx * 8 + x + 1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print('wrote %d bytes: frames 33, 34; 5 updates each' % len(output))


if __name__ == '__main__':
    main()
