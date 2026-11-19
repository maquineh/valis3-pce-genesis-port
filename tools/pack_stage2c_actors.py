#!/usr/bin/env python3
"""Add the captured STG2C player and fire actors to the dungeon module.

The original STG2C capture uses PCE sprite palette 5 for the player and
palette 7 for the fire effect. The dungeon background already occupies four
Mega Drive palette lines. This tool frees line 3 for the player by moving the
few background tiles that used line 3 onto the nearest of lines 0-2, then adds
the two brightest fire colors to unused slots of line 2.

The background tiles that stay on lines 0-2 keep their exact colors. Only the
tiles that used line 3 (about 0.4% of the captured background pixels) are
remapped to the nearest available color.

Usage:
  py -3 tools/pack_stage2c_actors.py [--state STATE] [--base DIR] [--output DIR]
"""
import argparse
import json
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from extract_state import load, find_var
from pce2md import pce_color_to_md
from pack_stage_state import components

STATE = ROOT / 'states' / ('Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc2')
GFX = ROOT / 'game' / 'res' / 'gfx'
PLAYER_PTRS = (0x865c, 0x8667, 0x8672, 0x868d)
FIRE_PTRS = (0x89b8, 0x89bd)
PLAYER_TILE = 159
PLAYER_FRAMES = 4
ENEMY_TILE = PLAYER_TILE + PLAYER_FRAMES * 48
ENEMY_FRAMES = 2
HEART_TILE = ENEMY_TILE + ENEMY_FRAMES * 48


def rgb(color):
    return ((color >> 1) & 7, (color >> 5) & 7, (color >> 9) & 7)


def distance(a, b):
    ar, ag, ab = rgb(a)
    br, bg, bb = rgb(b)
    return (ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2


def nearest(color, line, allowed=None):
    candidates = range(16) if allowed is None else allowed
    return min(candidates, key=lambda i: (distance(color, line[i]), i))


def decode(byte_data):
    pixels = []
    for y in range(8):
        row = []
        for x in range(8):
            value = byte_data[y * 4 + x // 2]
            row.append(value >> 4 if x % 2 == 0 else value & 15)
        pixels.append(row)
    return pixels


def encode(pixels):
    out = bytearray()
    for y in range(8):
        for x in range(0, 8, 2):
            out.append((pixels[y][x] << 4) | pixels[y][x + 1])
    return out


def remap_tile(data, table):
    out = bytearray()
    for value in data:
        out.append((table[value >> 4] << 4) | table[value & 15])
    return bytes(out)


def remap_pixels(data, table):
    out = bytearray()
    for value in data:
        out.append((table[value >> 4] << 4) | table[value & 15])
    return bytes(out)


def descriptor_frame(cdram, vram, pointer, width, height, offset_x, offset_y):
    parts = []
    for n in range(cdram[pointer]):
        flags, y, x, pattern = struct.unpack_from('<BbbH', cdram, pointer + 1 + n * 5)
        parts.append((x + offset_x, y + offset_y, pattern, flags << 8))
    return components(vram, parts, width, height)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=STATE)
    parser.add_argument('--base', type=Path, default=GFX,
                        help='directory with the existing stage2c background pack')
    parser.add_argument('--output', type=Path, default=GFX)
    args = parser.parse_args()

    base = args.base
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    tiles = bytearray((base / 'stage2c_state_tiles.bin').read_bytes())
    maps = bytearray((base / 'stage2c_state_maps.bin').read_bytes())
    pal = [list(struct.unpack_from('>16H', (base / 'stage2c_state_pal.bin').read_bytes(),
                                   line * 32)) for line in range(4)]
    info = json.loads((base / 'stage2c_state.json').read_text())

    entries = [(int.from_bytes(maps[i:i + 2], 'big') >> 13,
                int.from_bytes(maps[i:i + 2], 'big') & 0x1fff)
               for i in range(0, len(maps), 2)]
    tile_line = {}
    for line, tile in entries:
        if tile in tile_line and tile_line[tile] != line:
            raise ValueError('tile %d is used on lines %d and %d' %
                             (tile, tile_line[tile], line))
        tile_line[tile] = line

    # Move every background tile that used palette line 3 onto the nearest of
    # lines 0-2. Line 2 keeps slots 14/15 free for the fire colors.
    moved = []
    exact_pixels = 0
    approx_pixels = 0
    for tile, line in sorted(tile_line.items()):
        if line != 3:
            continue
        source = decode(tiles[tile * 32:(tile + 1) * 32])
        counts = Counter(value for row in source for value in row if value)
        best = None
        for target in (0, 1, 2):
            allowed = [i for i in range(16) if not (target == 2 and i in (14, 15))]
            table = [0] * 16
            error = 0
            exact = 0
            for index in range(1, 16):
                color = pal[3][index]
                hit = next((i for i in allowed if pal[target][i] == color), None)
                if hit is None:
                    hit = nearest(color, pal[target], allowed)
                else:
                    exact += 1
                table[index] = hit
                error += distance(color, pal[target][hit]) * counts.get(index, 0)
            score = (error, target, exact)
            if best is None or score < best[0]:
                best = (score, target, table)
        (error, _, exact), target, table = best
        tiles[tile * 32:(tile + 1) * 32] = remap_tile(
            tiles[tile * 32:(tile + 1) * 32], table)
        for i, (entry_line, entry_tile) in enumerate(entries):
            if entry_tile == tile:
                maps[i * 2:i * 2 + 2] = (
                    (entry_tile & 0x7ff) | (target << 13)).to_bytes(2, 'big')
                entries[i] = (target, entry_tile)
        moved.append({'tile': tile, 'target_line': target,
                      'color_error': error, 'exact_indices': exact})
        for index, count in counts.items():
            color = pal[3][index]
            if any(pal[target][i] == color for i in range(16)):
                exact_pixels += count
            else:
                approx_pixels += count
    if any(line == 3 for line, _ in entries):
        raise ValueError('background still references palette line 3')

    state = load(str(args.state))
    vram = find_var(state, b'VRAM')
    cram = find_var(state, b'color_table')
    cdram = find_var(state, b'CDRAM')
    pce = [pce_color_to_md(w) for w in struct.unpack('<512H', cram)]

    # Line 3 becomes the exact captured player palette (PCE sprite palette 5).
    pal[3] = pce[256 + 5 * 16:256 + 5 * 16 + 16]

    # Put the brightest fire colors into the two free line-2 slots.
    used2 = {i for line, tile in entries if line == 2
             for row in decode(tiles[tile * 32:(tile + 1) * 32])
             for i in row if i}
    free2 = [i for i in range(1, 16) if i not in used2]
    fire_colors = {i: pce[256 + 7 * 16 + i] for i in range(16)}
    added = {}
    for pce_index, color in ((3, fire_colors[3]), (15, fire_colors[15])):
        if color in pal[2]:
            continue
        if not free2:
            raise ValueError('no free palette slot for captured fire color')
        slot = free2.pop(0)
        pal[2][slot] = color
        added[pce_index] = slot

    fire_map = [0] * 16
    fire_exact = []
    for index in range(1, 16):
        color = fire_colors[index]
        hit = next((i for i in range(1, 16) if pal[2][i] == color), None)
        if hit is None:
            # Keep the fire in its warm red/orange/yellow range instead of
            # snapping dark pixels to the background's blue-grey slots.
            hit = nearest(color, pal[2], (4, 8, 9, 10, 11, 12, 13, 14, 15))
        else:
            fire_exact.append(index)
        fire_map[index] = hit

    actors = bytearray()
    for pointer in PLAYER_PTRS:
        actors.extend(descriptor_frame(cdram, vram, pointer, 64, 48, 16, 48))
    for pointer in FIRE_PTRS:
        frame = descriptor_frame(cdram, vram, pointer, 48, 64, 32, 64)
        actors.extend(remap_pixels(frame, fire_map))

    # Keep the original 8x8 heart, recoloured into the captured player palette.
    heart = (ROOT / 'game' / 'res' / 'gfx' / 'player_spr.bin').read_bytes()[4 * 32:5 * 32]
    heart_map = [0] * 16
    heart_map[8] = 1     # dark red outline
    heart_map[9] = 9     # light pink fill
    heart_map[15] = 15   # white highlight
    actors.extend(remap_tile(heart, heart_map))

    for name, data in (('tiles', tiles), ('maps', maps),
                       ('pal', bytearray().join(value.to_bytes(2, 'big')
                                                for line in pal for value in line)),
                       ('actors', actors)):
        (out / ('stage2c_state_' + name + '.bin')).write_bytes(data)

    info.update({
        'background_palette_lines': [0, 1, 2],
        'line3_used_indices': [],
        'reserved_line3': list(range(1, 16)),
        'background_moved_line3_tiles': moved,
        'background_exact_pixels': exact_pixels,
        'background_approx_pixels': approx_pixels,
        'actor_bytes': len(actors),
        'actor_frames': {'player': PLAYER_FRAMES, 'enemy': ENEMY_FRAMES},
        'actor_tile_indices': {'player': PLAYER_TILE, 'enemy': ENEMY_TILE,
                               'heart': HEART_TILE},
        'actor_frame_tiles': 48,
        'actor_palette_lines': {'player': 3, 'enemy': 2},
        'actor_sources': {
            'player': [hex(p) for p in PLAYER_PTRS],
            'enemy': [hex(p) for p in FIRE_PTRS],
        },
        'fire_palette_line': 2,
        'fire_palette_map': fire_map,
        'fire_exact_indices': fire_exact,
        'fire_added_palette_slots': added,
        'actor_mode': 'captured-pce-frames',
    })
    (out / 'stage2c_state.json').write_text(json.dumps(info, indent=2) + '\n')
    print('moved %d line-3 background tiles; %d exact / %d remapped pixels' %
          (len(moved), exact_pixels, approx_pixels))
    print('player frames %d, fire frames %d, actor bytes %d' %
          (PLAYER_FRAMES, ENEMY_FRAMES, len(actors)))
    print('fire palette map', fire_map, 'added', added)


if __name__ == '__main__':
    main()
