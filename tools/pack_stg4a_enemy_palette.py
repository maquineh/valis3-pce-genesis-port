#!/usr/bin/env python3
"""Free one MD palette line for original STG4A enemy colors.

Repack background lines 1 and 2 into one line, merging their closest pair of
used colors by pixel-weighted RGB error. Line 0 is unchanged; line 2 receives
the STG4A type-05/06 PCE sprite palette. Input assets are preserved.
"""
import json
from collections import Counter
from pathlib import Path

from pce_state import decompress, parse
from pce2md import pce_color_to_md
from render_pce_state import word

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / 'game/res/gfx'
STATE = ROOT / 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc9'


def rgb(w):
    return ((w >> 1) & 7, (w >> 5) & 7, (w >> 9) & 7)


def main():
    v = parse(decompress(str(STATE)))
    cdram, cram = v['CDRAM'][2], v['color_table'][2]
    if cdram[0xA000:0xA005] != b'STG4A':
        raise ValueError('expected STG4A')
    if cdram[0xA09C + 5 * 19 + 3] != 2 or cdram[0xA09C + 6 * 19 + 3] != 2:
        raise ValueError('type 05/06 sprite palette no longer matches')
    tiles = (GFX / 'stage4a_capture_tiles.bin').read_bytes()
    maps = (GFX / 'stage4a_capture_maps.bin').read_bytes()
    pal = bytearray((GFX / 'stage4a_capture_pal.bin').read_bytes())
    if len(pal) != 128 or len(maps) != 1536 or len(tiles) % 32:
        raise ValueError('unexpected input resource sizes')
    counts = Counter()
    for off in range(0, len(maps), 2):
        e = int.from_bytes(maps[off:off+2], 'big')
        line, tile = (e >> 13) & 3, e & 0x7FF
        if line not in (0, 1, 2) or tile * 32 + 32 > len(tiles):
            raise ValueError('unexpected map entry')
        if line in (1, 2):
            for byte in tiles[tile*32:tile*32+32]:
                for idx in (byte >> 4, byte & 15):
                    if idx:
                        counts[int.from_bytes(pal[(line*16+idx)*2:(line*16+idx)*2+2], 'big')] += 1
    if len(counts) != 16:
        raise ValueError('expected 16 colors across the two background lines')
    def cost(a, b):
        return counts[a] * sum((x-y)**2 for x, y in zip(rgb(a), rgb(b)))
    source, target = min(((a, b) for a in counts for b in counts if a != b),
                         key=lambda pair: (cost(*pair), pair))
    colors = sorted(set(counts) - {source})
    lookup = {value: i + 1 for i, value in enumerate(colors)}
    lookup[source] = lookup[target]
    output_tiles, output_map, indices = bytearray(), bytearray(), {}
    changed_pixels = 0
    for off in range(0, len(maps), 2):
        e = int.from_bytes(maps[off:off+2], 'big')
        line, tile = (e >> 13) & 3, e & 0x7FF
        raw = tiles[tile*32:tile*32+32]
        if line in (1, 2):
            conversion = [0]
            for idx in range(1, 16):
                value = int.from_bytes(pal[(line*16+idx)*2:(line*16+idx)*2+2], 'big')
                conversion.append(lookup.get(value, 0))
            changed_pixels += sum((byte >> 4 != 0 and
                int.from_bytes(pal[(line*16+(byte >> 4))*2:(line*16+(byte >> 4))*2+2], 'big') == source) +
                ((byte & 15) != 0 and
                int.from_bytes(pal[(line*16+(byte & 15))*2:(line*16+(byte & 15))*2+2], 'big') == source)
                for byte in raw)
            raw = bytes((conversion[byte >> 4] << 4) | conversion[byte & 15] for byte in raw)
            line = 1
        key = (raw, line)
        if key not in indices:
            indices[key] = len(indices)
            output_tiles.extend(raw)
        output_map.extend((indices[key] | line << 13).to_bytes(2, 'big'))
    for i in range(16):
        pal[(16+i)*2:(16+i)*2+2] = (colors[i-1] if i else 0).to_bytes(2, 'big')
    enemy = b''.join(pce_color_to_md(word(cram, 512 + (2*16+i)*2)).to_bytes(2, 'big') for i in range(16))
    pal[64:96] = enemy
    (GFX / 'stage4a_hw2_tiles.bin').write_bytes(output_tiles)
    (GFX / 'stage4a_hw2_maps.bin').write_bytes(output_map)
    (GFX / 'stage4a_hw2_pal.bin').write_bytes(pal)
    (GFX / 'stage4a_enemy_pal.bin').write_bytes(enemy)
    info = {'tiles': len(indices), 'screens': 1, 'background_lines': [0, 1],
            'enemy_line': 2, 'pce_enemy_palette': 2,
            'merged_color': hex(source), 'replacement_color': hex(target),
            'changed_pixels': changed_pixels, 'weighted_squared_rgb_error': cost(source, target)}
    (GFX / 'stage4a_hw2.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
