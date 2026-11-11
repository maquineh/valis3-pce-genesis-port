"""Pack a Mednafen state's BAT window into Mega CD resources.

Usage:
  python3 tools/pack_state_window.py STATE OUTNAME ROW0 COL0 [ROW1 [ROW2 ...]]

Each ROWn is the top row of a 32x24 screen taken from the captured 64x64 BAT.
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, 'tools')
from pce2md import pce_tile_to_md, pce_color_to_md
from extract_state import load, find_var

SCREEN_COLS, SCREEN_ROWS = 32, 24


def main():
    state, name = sys.argv[1], sys.argv[2]
    rows = [int(x, 0) for x in sys.argv[3:]] or [0]
    col0 = 0
    if rows and rows[0] >= 1000:      # optional COL0 encoded as 1000+col
        col0 = rows[0] - 1000
        rows = rows[1:]
    d = load(state)
    vram = find_var(d, b'VRAM')
    cram = find_var(d, b'color_table')
    words = [vram[2 * i] | (vram[2 * i + 1] << 8) for i in range(0x1000)]
    cw = [cram[2 * i] | (cram[2 * i + 1] << 8) for i in range(len(cram) // 2)]

    order = [0]
    remap = {0: 0}
    screens = []
    pal_counts = Counter()
    raw_screens = []
    for r0 in rows:
        raw = []
        for y in range(SCREEN_ROWS):
            for x in range(SCREEN_COLS):
                word = words[(r0 + y) * 64 + (col0 + x)]
                raw.append(word)
                pal_counts[word >> 12] += 1
        raw_screens.append(raw)
    # Map the four most-used PCE palettes to the four Mega Drive palette lines.
    top = [p for p, _ in pal_counts.most_common(4)]
    while len(top) < 4:
        top.append(top[-1] if top else 0)
    pal_map = {p: i for i, p in enumerate(top)}
    for raw in raw_screens:
        row = []
        for word in raw:
            t = word & 0xFFF
            if t not in remap:
                order.append(t)
                remap[t] = len(order) - 1
            row.append((remap[t], pal_map.get(word >> 12, 3)))
        screens.append(row)

    tiles = bytearray(bytes(32))
    for t in order[1:]:
        src = t * 32
        tiles += pce_tile_to_md(vram[src:src + 32]) if src + 32 <= len(vram) else bytes(32)
    os.makedirs('game/res/gfx', exist_ok=True)
    open('game/res/gfx/%s_tiles.bin' % name, 'wb').write(bytes(tiles))

    maps = bytearray()
    for row in screens:
        for idx, pal in row:
            e = (idx & 0x7FF) | ((pal & 3) << 13)
            maps += bytes([e & 0xFF, (e >> 8) & 0xFF])
    open('game/res/gfx/%s_maps.bin' % name, 'wb').write(bytes(maps))

    pal = bytearray()
    for pce_pal in top:
        for i in range(16):
            m = pce_color_to_md(cw[pce_pal * 16 + i])
            pal += bytes([m & 0xFF, (m >> 8) & 0xFF])
    open('game/res/gfx/%s_pal.bin' % name, 'wb').write(bytes(pal))

    info = {'source': state, 'screens': len(screens), 'rows': rows,
            'col0': col0, 'tiles': len(order), 'tiles_bytes': len(tiles),
            'maps_bytes': len(maps), 'pal_bytes': len(pal),
            'pce_palettes': top, 'pal_map': pal_map}
    json.dump(info, open('game/res/gfx/%s.json' % name, 'w'), indent=2)
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
