"""Extract the ten STG stage blocks from the retail disc.

Verified layout (from the real Stage 2 save state and STG2A):
    +0x000  header ('STG1A'..'STG5A')
    +0x200  palette / colour tables (the live CRAM words appear from $264)
    +0x800  compressed stream (BAT / tilemap)
    +0xC00  Shift-JIS stage text
    +0x1000 object/level records
    +0x6E40 raw 4bpp tile graphics (tile index 0x100 upward, 32 bytes/tile)
Every block is exactly 40 user sectors (81920 bytes).

Outputs (build/stg_extract/):
    <name>_header.bin, <name>_pal.bin, <name>_text.bin,
    <name>_objects.bin, <name>_tiles.bin, manifest.json

The raw tiles of STG2A are cross-checked against the live VRAM dump taken
from the user's Mednafen save state.
"""
import json
import os
import sys

sys.path.insert(0, 'tools')

from pce_state import decompress, parse as parse_state

TRACK = 'build/extracted/data/track_02.bin'
STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
OUT = 'build/stg_extract'

BLOCKS = [
    (304, 'STG1A'), (344, 'STG2A'), (384, 'STG2B'), (424, 'STG2C'),
    (464, 'STG3A'), (504, 'STG3B'), (544, 'STG4A'), (584, 'STG4B'),
    (624, 'STG4C'), (664, 'STG5A'),
]

HEADER = 0x200
PAL = 0x200
TEXT = 0xC00
OBJECTS = 0x1000
TILES = 0x6E40
BLOCK = 0x14000


def main():
    os.makedirs(OUT, exist_ok=True)
    disc = open(TRACK, 'rb').read()
    manifest = {'source': TRACK, 'block_bytes': BLOCK, 'tile_base': 0x100,
                'tile_offset': TILES, 'stages': []}

    # live Stage 2 VRAM for verification
    vram = None
    if os.path.exists(STATE):
        v = parse_state(decompress(STATE))
        if 'VRAM' in v:
            vram = v['VRAM'][2]

    for sector, name in BLOCKS:
        off = sector * 2352 + 16
        blk = disc[off:off + BLOCK]
        assert blk[:5] == name.encode(), (name, blk[:5])
        open(os.path.join(OUT, '%s_header.bin' % name), 'wb').write(blk[:HEADER])
        open(os.path.join(OUT, '%s_pal.bin' % name), 'wb').write(blk[PAL:PAL + 0x400])
        open(os.path.join(OUT, '%s_text.bin' % name), 'wb').write(blk[TEXT:TEXT + 0x400])
        open(os.path.join(OUT, '%s_objects.bin' % name), 'wb').write(blk[OBJECTS:TILES])
        tiles = blk[TILES:BLOCK]
        open(os.path.join(OUT, '%s_tiles.bin' % name), 'wb').write(tiles)
        count = len(tiles) // 32

        matched = None
        if name == 'STG2A' and vram is not None:
            matched = 0
            for t in range(count):
                tile = tiles[t * 32:(t + 1) * 32]
                if vram[(0x100 + t) * 32:(0x101 + t) * 32] == tile:
                    matched += 1

        manifest['stages'].append({
            'name': name, 'sector': sector, 'tiles': count,
            'tile_bytes': len(tiles), 'vram_matched_tiles': matched,
        })
        print('%s sector %3d: %4d tiles  vram_match=%s' %
              (name, sector, count, matched))

    json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=2)
    print('wrote', os.path.join(OUT, 'manifest.json'))


if __name__ == '__main__':
    main()
