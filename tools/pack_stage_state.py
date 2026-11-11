"""Pack the real Stage 2 snapshot into the Mega CD port resource format.

Source: the Mednafen save state (VRAM/CRAM/BAT).  The port uses 32x24 plane-A
screens with 8x8 4bpp tiles; we take 32x24 windows from the captured 64x64
BAT (the stage map is the lower half of the BAT) and remap the tiles that
actually appear.

PCE palette -> MD palette mapping (the PCE stage uses 0,5,6,7,8,14,15):
    15 -> 0 (sky/background)
     0 -> 1 (ground)
    14 -> 2 (platforms)
  5,6,7,8 -> 3 (detail/HUD)
"""
import json
import os
import sys

sys.path.insert(0, 'tools')
from pce2md import pce_tile_to_md, pce_color_to_md
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
OUT = 'game/res/gfx'
SCREEN_COLS, SCREEN_ROWS = 32, 24

PAL_MAP = {15: 0, 0: 1, 14: 2, 5: 3, 6: 3, 7: 3, 8: 3}


def main():
    os.makedirs(OUT, exist_ok=True)
    v = parse(decompress(STATE))
    vram = v['VRAM'][2]
    cram = v['color_table'][2]
    words = [vram[2 * i] | (vram[2 * i + 1] << 8) for i in range(len(vram) // 2)]
    cw = [cram[2 * i] | (cram[2 * i + 1] << 8) for i in range(len(cram) // 2)]

    # Stage map = lower half of the captured 64x64 BAT.
    stage = words[2048:4096]

    # Screens: 32x24 windows over the stage map (two vertical positions).
    screens = [
        (32, 0),   # rows 32..55, columns 0..31
        (32, 32),  # rows 32..55, columns 32..63
        (40, 0),   # rows 40..63, columns 0..31
        (40, 32),  # rows 40..63, columns 32..63
    ]

    order = [0]
    remap = {0: 0}
    entries = []
    for r0, c0 in screens:
        row = []
        for y in range(SCREEN_ROWS):
            for x in range(SCREEN_COLS):
                word = stage[(r0 - 32 + y) * 64 + (c0 + x)]
                t = word & 0xFFF
                if t not in remap:
                    order.append(t)
                    remap[t] = len(order) - 1
                row.append((remap[t], PAL_MAP.get(word >> 12, 3)))
        entries.append(row)

    tiles = bytearray(bytes(32))            # blank tile 0
    for t in order[1:]:
        src = t * 32
        tile = vram[src:src + 32]
        tiles += pce_tile_to_md(tile) if len(tile) == 32 else bytes(32)
    open(os.path.join(OUT, 'stage2_state_tiles.bin'), 'wb').write(bytes(tiles))

    maps = bytearray()
    for row in entries:
        for idx, pal in row:
            e = (idx & 0x7FF) | ((pal & 3) << 13)
            maps += bytes([e & 0xFF, (e >> 8) & 0xFF])
    open(os.path.join(OUT, 'stage2_state_maps.bin'), 'wb').write(bytes(maps))

    # 4 MD palettes: source PCE palettes 15,0,14,5
    pal = bytearray()
    for pce_pal in (15, 0, 14, 5):
        for i in range(16):
            w = cw[pce_pal * 16 + i]
            m = pce_color_to_md(w)
            pal += bytes([m & 0xFF, (m >> 8) & 0xFF])
    open(os.path.join(OUT, 'stage2_state_pal.bin'), 'wb').write(bytes(pal))

    info = {
        'screens': len(screens), 'screen_cols': SCREEN_COLS,
        'screen_rows': SCREEN_ROWS, 'tiles': len(order),
        'tiles_bytes': len(tiles), 'maps_bytes': len(maps),
        'pal_bytes': len(pal), 'pal_map': PAL_MAP,
        'source': 'Mednafen state Stage 2 BAT/VRAM/CRAM',
    }
    json.dump(info, open(os.path.join(OUT, 'stage2_state.json'), 'w'), indent=2)
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
