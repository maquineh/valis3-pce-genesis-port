#!/usr/bin/env python3
"""Convert STG4A type-11 projectile frame 32 from captured PCE VRAM."""
import argparse
from pathlib import Path
from pce_state import decompress, parse
from render_pce_state import decode_sprite, word
from extract_stg4a_skull_anim import rgb_md, rgb_pce


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('state', type=Path)
    ap.add_argument('palette', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    v = parse(decompress(str(args.state)))
    data, vram, cram = (v[k][2] for k in ('CDRAM', 'VRAM', 'color_table'))
    # Type 11 table: flags, frame, palette, horizontal and vertical radii.
    if data[0x2884:0x2889] != bytes.fromhex('00 32 02 04 04'):
        raise ValueError('unexpected projectile type 11 configuration')
    ptr = word(data, 0xA7E4 + 0x32 * 2)
    if data[ptr:ptr+6] != bytes.fromhex('01 00 f8 f8 ba 01'):
        raise ValueError('unexpected projectile frame 32')
    raw = args.palette.read_bytes()
    if len(raw) != 32:
        raise ValueError('expected 16 MD palette words')
    md = [rgb_md(int.from_bytes(raw[i:i+2], 'big')) for i in range(0,32,2)]
    src = [rgb_pce(word(cram, 512+(2*16+i)*2)) for i in range(16)]
    mapping = [0] + [min(range(1,16), key=lambda j: sum(
        (a-b)**2 for a,b in zip(src[i],md[j]))) for i in range(1,16)]
    rows = decode_sprite(vram, 0x01BA, 0x0082)
    rows = [[mapping[c] for c in (row[8:16]+row[0:8])] for row in rows]
    out = bytearray()
    for tx in range(2):
        for ty in range(2):
            for y in range(8):
                row = rows[ty*8+y]
                for x in range(0,8,2):
                    out.append((row[tx*8+x]<<4)|row[tx*8+x+1])
    args.output.write_bytes(out)
    print('wrote %d bytes: PCE type 11 frame 32, palette 2' % len(out))


if __name__ == '__main__':
    main()
