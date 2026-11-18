#!/usr/bin/env python3
"""Extract the three knight frames referenced by STG3A animation 0x1F.

The caller provides the STG4A player state and STG3A enemy state. Frame
descriptors and their component patterns are read from the enemy CDRAM.
The STG3A knight is used by the STG4A prototype and is not verified there.
"""
import argparse
from pathlib import Path

from pce_state import decompress, parse
from render_pce_state import decode_sprite, word


def rgb(value):
    return ((value >> 3) & 7, (value >> 6) & 7, value & 7)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('player_state', type=Path)
    parser.add_argument('enemy_state', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    player = parse(decompress(str(args.player_state)))
    enemy = parse(decompress(str(args.enemy_state)))
    vram = enemy['VRAM'][2]
    player_cram, enemy_cram = player['color_table'][2], enemy['color_table'][2]
    player_pal = [word(player_cram, 512 + (5 * 16 + i) * 2) for i in range(16)]
    enemy_pal = [word(enemy_cram, 512 + (2 * 16 + i) * 2) for i in range(16)]
    mapping = [0] + [min(range(1, 16), key=lambda n: sum(
        (a - b) ** 2 for a, b in zip(rgb(enemy_pal[i]), rgb(player_pal[n]))))
        for i in range(1, 16)]
    cdram = enemy['CDRAM'][2]
    if cdram[0xA000:0xA005] != b'STG3A':
        raise ValueError('enemy snapshot is not STG3A')
    anim_ptr = word(cdram, 0xA744 + 0x1F * 2)
    count = cdram[anim_ptr]
    sequence = [(cdram[anim_ptr + i * 2], cdram[anim_ptr + i * 2 - 1])
                for i in range(count, 0, -1)]
    if sequence != [(0x36, 16), (0x37, 10), (0x38, 16), (0x37, 10)]:
        raise ValueError('unexpected knight animation sequence: %r' % (sequence,))
    result = bytearray()
    for frame in (0x36, 0x37, 0x38):
        frame_ptr = word(cdram, 0xA7E4 + frame * 2)
        if cdram[frame_ptr] != 2:
            raise ValueError('expected two components in frame %02X' % frame)
        pixels = []
        for part in range(2):
            off = frame_ptr + 1 + part * 5
            flags, y, x = cdram[off:off + 3]
            pattern = word(cdram, off + 3)
            if (flags, y, x) != ((0x09, 0xD0, 0xF0),
                                  (0x19, 0xE0, 0xF0))[part]:
                raise ValueError('unexpected frame %02X placement' % frame)
            rows = decode_sprite(vram, pattern, (flags << 8) | 0x82)
            pixels.extend([[mapping[p] for p in
                            (r[8:16] + r[0:8] + r[24:32] + r[16:24])]
                           for r in rows])
        if len(pixels) != 48:
            raise ValueError('expected 48-pixel frame')
        for sy, height in ((0, 32), (32, 16)):
            for tx in range(4):
                for ty in range(height // 8):
                    for y in range(8):
                        row = pixels[sy + ty * 8 + y]
                        for x in range(0, 8, 2):
                            result.append((row[tx * 8 + x] << 4) |
                                          row[tx * 8 + x + 1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print('wrote %d bytes (%d poses) to %s' %
          (len(result), len(result) // 768, args.output))


if __name__ == '__main__':
    main()
