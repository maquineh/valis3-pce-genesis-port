"""Pack a Mednafen state's BAT window into Mega CD resources.

Usage:
  python3 tools/pack_state_window.py STATE OUTNAME [1000+COL0] ROW0 [ROW1 ...]
      [--columns C0,C1,...] [--palette-order P0,P1,P2,P3]
      [--reserve-line3 I0,I1,...]

Each ROWn is the top row of a 32x24 screen taken from the captured 64x64 BAT.
"""
import json
import argparse
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, 'tools')
from pce2md import pce_tile_to_md, pce_color_to_md
from extract_state import load, find_var

SCREEN_COLS, SCREEN_ROWS = 32, 24


def comma_ints(value):
    try:
        return [int(part, 0) for part in value.split(',')]
    except ValueError as exc:
        raise argparse.ArgumentTypeError('expected comma-separated integers') from exc


def used_colors_by_line(screens, tiles):
    """Return pixel indices actually used on each of the four MD palette lines."""
    used = [set() for _ in range(4)]
    for screen in screens:
        for tile, line in screen:
            start = tile * 32
            for byte in tiles[start:start + 32]:
                used[line].add(byte >> 4)
                used[line].add(byte & 15)
    return used


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state')
    parser.add_argument('name')
    parser.add_argument('rows', nargs='*', type=lambda x: int(x, 0))
    parser.add_argument('--pal', metavar='FILE[:OFFSET]',
                        help='use a retail palette when a capture was taken during a fade')
    parser.add_argument('--columns', type=comma_ints,
                        help='BAT start column for each screen (default: same column)')
    parser.add_argument('--palette-order', type=comma_ints,
                        help='permutation of the four selected PCE palettes')
    parser.add_argument('--reserve-line3', type=comma_ints,
                        help='fail if any listed pixel index is used on MD palette line 3')
    parser.add_argument('--pack-all-palettes', action='store_true',
                        help='repack every PCE palette used by the BAT window into four MD lines')
    args = parser.parse_intermixed_args()
    state, name = args.state, args.name
    rows = args.rows or [0]
    col0 = 0
    if rows and rows[0] >= 1000:      # optional COL0 encoded as 1000+col
        col0 = rows[0] - 1000
        rows = rows[1:]
    if not 0 <= col0 < 64:
        parser.error('COL0 must be a BAT column in 0..63')
    if args.columns is not None:
        if rows and args.rows and args.rows[0] >= 1000:
            parser.error('use --columns or the legacy 1000+COL0 argument, not both')
        if len(args.columns) != len(rows):
            parser.error('--columns must contain one column per screen')
        screen_cols = args.columns
    else:
        screen_cols = [col0] * len(rows)
    if any(not 0 <= col < 64 for col in screen_cols):
        parser.error('screen columns must be BAT columns in 0..63')
    if any(not 0 <= row < 64 for row in rows):
        parser.error('screen rows must be BAT rows in 0..63')
    d = load(state)
    vram = find_var(d, b'VRAM')
    if args.pal:
        palette_path, separator, suffix = args.pal.rpartition(':')
        try:
            offset = int(suffix, 0) if separator else 0
        except ValueError:  # Windows drive prefix without a numeric offset
            palette_path, offset = args.pal, 0
        with Path(palette_path if separator else args.pal).open('rb') as palette:
            if offset < 0:
                parser.error('palette offset must be nonnegative')
            palette.seek(offset)
            cram = palette.read(512)
        if len(cram) != 512:
            parser.error('external palette must contain 512 bytes at the requested offset')
    else:
        cram = find_var(d, b'color_table')
    words = [vram[2 * i] | (vram[2 * i + 1] << 8) for i in range(0x1000)]
    cw = [cram[2 * i] | (cram[2 * i + 1] << 8) for i in range(len(cram) // 2)]

    order = [0]
    remap = {0: 0}
    screens = []
    pal_counts = Counter()
    raw_screens = []
    for r0, c0 in zip(rows, screen_cols):
        raw = []
        for y in range(SCREEN_ROWS):
            for x in range(SCREEN_COLS):
                # The PCE BAT is a 64x64 ring. A viewport near its right or
                # bottom edge crosses back to column/row zero.
                word = words[((r0 + y) & 63) * 64 + ((c0 + x) & 63)]
                raw.append(word)
                pal_counts[word >> 12] += 1
        raw_screens.append(raw)
    # Map the four most-used PCE palettes to the four Mega Drive palette lines.
    selected = [p for p, _ in pal_counts.most_common(4)]
    while len(selected) < 4:
        selected.append(selected[-1] if selected else 0)
    top = args.palette_order if args.palette_order is not None else selected
    if len(top) != 4 or sorted(top) != sorted(selected):
        parser.error('--palette-order must be a permutation of the four selected PCE palettes: %s' % selected)
    reserved = args.reserve_line3 or []
    if any(index < 1 or index > 15 for index in reserved) or len(set(reserved)) != len(reserved):
        parser.error('--reserve-line3 must contain unique nontransparent indices in 1..15')
    if args.pack_all_palettes:
        if not args.reserve_line3:
            parser.error('--pack-all-palettes requires --reserve-line3 for shared sprite colors')
        # Find every color actually used by each PCE palette, then place whole
        # source palettes on MD lines. Reindexing pixels lets sparse HUD
        # palettes share a line when their combined colors fit its 16 slots.
        pair_colors = {}
        palette_colors = {}
        pair_order = []
        pair_seen = set()
        for raw in raw_screens:
            for word in raw:
                key = (word & 0xFFF, word >> 12)
                if key in pair_seen:
                    continue
                pair_seen.add(key)
                pair_order.append(key)
                tile, pce_pal = key
                src = tile * 32
                source = vram[src:src + 32] if src + 32 <= len(vram) else bytes(32)
                md_tile = pce_tile_to_md(source)
                colors = set()
                for byte in md_tile:
                    for index in (byte >> 4, byte & 15):
                        colors.add(pce_color_to_md(cw[pce_pal * 16 + index]))
                pair_colors[key] = colors
                palette_colors.setdefault(pce_pal, set()).update(colors)

        line_indices = [list(range(16)) for _ in range(4)]
        line_indices[3] = [i for i in range(16) if i not in reserved]
        bins = [set() for _ in range(4)]
        capacities = [len(indices) for indices in line_indices]
        palettes = sorted(palette_colors, key=lambda p: (-len(palette_colors[p]), p))
        preferred = {p: i for i, p in enumerate(top)}
        pal_map = {}

        def assign_palette(n):
            if n == len(palettes):
                return True
            pce_pal = palettes[n]
            candidate_lines = list(range(4))
            if pce_pal in preferred:
                candidate_lines.remove(preferred[pce_pal])
                candidate_lines.insert(0, preferred[pce_pal])
            for line in candidate_lines:
                merged = bins[line] | palette_colors[pce_pal]
                if len(merged) > capacities[line]:
                    continue
                previous = bins[line]
                bins[line] = merged
                pal_map[pce_pal] = line
                if assign_palette(n + 1):
                    return True
                bins[line] = previous
                del pal_map[pce_pal]
            return False

        if not assign_palette(0):
            sizes = {p: len(palette_colors[p]) for p in palettes}
            parser.error('PCE palettes cannot fit exactly in four MD lines with reserved line-3 indices: %s' % sizes)

        color_slots = [{} for _ in range(4)]
        pal_words = [0] * 64
        for line in range(4):
            # Keep black at index zero when present. Other colors are stable.
            colors = sorted(bins[line])
            if 0 in colors:
                colors.remove(0)
                colors.insert(0, 0)
            for index, color in zip(line_indices[line], colors):
                color_slots[line][color] = index
                pal_words[line * 16 + index] = color

        pair_remap = {key: i for i, key in enumerate(pair_order)}
        screens = []
        for raw in raw_screens:
            row = []
            for word in raw:
                key = (word & 0xFFF, word >> 12)
                row.append((pair_remap[key], pal_map[key[1]]))
            screens.append(row)

        tiles = bytearray()
        for tile, pce_pal in pair_order:
            src = tile * 32
            source = vram[src:src + 32] if src + 32 <= len(vram) else bytes(32)
            converted = bytearray(pce_tile_to_md(source))
            line = pal_map[pce_pal]
            for offset, byte in enumerate(converted):
                hi = pce_color_to_md(cw[pce_pal * 16 + (byte >> 4)])
                lo = pce_color_to_md(cw[pce_pal * 16 + (byte & 15)])
                converted[offset] = (color_slots[line][hi] << 4) | color_slots[line][lo]
            tiles += converted
        pal = bytearray().join(word.to_bytes(2, 'big') for word in pal_words)
        order = pair_order
    else:
        pal_map = {p: i for i, p in enumerate(top)}
        fallback_line = pal_map[selected[-1]]
        for raw in raw_screens:
            row = []
            for word in raw:
                t = word & 0xFFF
                if t not in remap:
                    order.append(t)
                    remap[t] = len(order) - 1
                row.append((remap[t], pal_map.get(word >> 12, fallback_line)))
            screens.append(row)

        tiles = bytearray(bytes(32))
        for t in order[1:]:
            src = t * 32
            tiles += pce_tile_to_md(vram[src:src + 32]) if src + 32 <= len(vram) else bytes(32)
    used = used_colors_by_line(screens, tiles)
    conflict = sorted(set(reserved) & used[3])
    if conflict:
        parser.error('palette line 3 uses reserved pixel indices: %s' % conflict)

    maps = bytearray()
    for row in screens:
        for idx, palette_line in row:
            e = (idx & 0x7FF) | ((palette_line & 3) << 13)
            maps += e.to_bytes(2, "big")

    if not args.pack_all_palettes:
        pal = bytearray()
        for pce_pal in top:
            for i in range(16):
                m = pce_color_to_md(cw[pce_pal * 16 + i])
                pal += m.to_bytes(2, "big")
    os.makedirs('game/res/gfx', exist_ok=True)
    for suffix, data in (('tiles', tiles), ('maps', maps), ('pal', pal)):
        with open('game/res/gfx/%s_%s.bin' % (name, suffix), 'wb') as output:
            output.write(data)

    info = {'source': state, 'screens': len(screens), 'rows': rows,
            'columns': screen_cols, 'col0': col0,
            'tiles': len(order), 'tiles_bytes': len(tiles),
            'maps_bytes': len(maps), 'pal_bytes': len(pal),
            'pce_palettes': top, 'pal_map': pal_map,
            'fallback_pce_palette': None if args.pack_all_palettes else selected[-1],
            'palette_mode': 'exact-color-pack' if args.pack_all_palettes else 'top-four-with-fallback',
            'line3_used_indices': sorted(used[3]), 'reserved_line3': reserved}
    if args.pal:
        info['palette_source'] = args.pal
    with open('game/res/gfx/%s.json' % name, 'w') as output:
        json.dump(info, output, indent=2)
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
