"""Pack the two horizontally adjacent captured screens for STG2A2 and STG2B.

The source BAT is the same live 64x64 ring used by pack_phase2_rooms.py.  The
left screen is BAT columns 0-31 and the right screen columns 32-63; the status
rows 49-53 and playfield rows 7-29 keep the same raster split.  The output map
is therefore 64x28 cells: two complete 256-pixel screens with one shared tile
and palette catalogue.
"""
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image

from extract_state import find_var, load
from pack_phase2_rooms import palette_map, components
from pack_stage_state import OUT, ROOT, STEM, packed
from pce2md import pce_color_to_md
from pce_gfx import bg_tile_pixels


def map_words(vram, colors, starts):
    bat = struct.unpack_from('<4096H', vram)
    words = []
    for start in starts:
        for y in range(28):
            row = 49 + y if y < 5 else start + (y - 5)
            for x in range(32):
                words.append(bat[(row & 63) * 64 + x])
    entries, inverse, counts = np.unique(words, return_inverse=True, return_counts=True)
    pixels = []
    for word in entries:
        start = (int(word) & 0xfff) * 32
        bank = int(word >> 12) * 16
        pixels.append([colors[bank + i] if i else 0
                       for row in bg_tile_pixels(vram[start:start + 32]) for i in row])
    return np.array(pixels), inverse, counts


def preview(name, tiles, maps, palette, screens=2):
    cram = [(((w >> 1) & 7) * 255 // 7, ((w >> 5) & 7) * 255 // 7,
             ((w >> 9) & 7) * 255 // 7) for w in palette]
    cols, rows = 32, 28
    image = Image.new('RGB', (cols * 8 * screens, rows * 8))
    px = image.load()
    for s in range(screens):
        for y in range(rows):
            for x in range(cols):
                entry = struct.unpack_from('>H', maps,
                                           ((s * rows + y) * cols + x) * 2)[0]
                tile = entry & 0x7ff
                line = (entry >> 13) & 3
                base = tile * 32
                if base + 32 > len(tiles):
                    continue
                for py in range(8):
                    for pxx in range(8):
                        packed_byte = tiles[base + py * 4 + pxx // 2]
                        v = (packed_byte >> 4) if pxx % 2 == 0 else packed_byte & 15
                        px[s * cols * 8 + x * 8 + pxx, y * 8 + py] = cram[line * 16 + v]
    (ROOT / 'build/gfx').mkdir(parents=True, exist_ok=True)
    image.save(ROOT / 'build/gfx' / ('%s_wide.png' % name))


def generate(name, source, forest):
    raw = load(source)
    vram, cram, sat, cd = [find_var(raw, key) for key in
                            (b'VRAM', b'color_table', b'SAT', b'CDRAM')]
    colors = [pce_color_to_md(w) for w in struct.unpack('<512H', cram)]
    pieces = [struct.unpack_from('<4H', sat, i * 8) for i in (3, 4)]
    line = pieces[0][3] & 15
    assert all((attr & 15) == line for _, _, _, attr in pieces)
    starts = (7, 20) if not forest else (0, 8)
    pixels, inverse, counts = map_words(vram, colors, starts)
    tiles, entries, palette = palette_map(pixels, counts, colors, 256 + 16 * line)
    maps = entries[inverse]
    actors = bytearray()
    for ptr in (0x8636, 0x8651, 0x865c, 0x86c3):
        parts = []
        for n in range(cd[ptr]):
            flags, y, x, pattern = struct.unpack_from('<BbbH', cd, ptr + 1 + n * 5)
            parts.append((x + 16, y + 48, pattern, flags << 8))
        actors.extend(components(vram, parts, 64, 48))
    pointers = (0xaf42, 0xaf2c, 0xaf37) if forest else (0xb016, 0xb021, 0xb02c, 0xb041)
    for i, ptr in enumerate(pointers):
        frame = [struct.unpack_from('<BbbH', cd, ptr + 1 + n * 5) for n in range(cd[ptr])]
        if i == 0:
            assert [p[3] for p in frame] == [p[2] for p in pieces]
        baseline = max(64, -min(y for _, y, _, _ in frame))
        parts = []
        for flags, y, x, pattern in frame:
            width = 32 if flags & 1 else 16
            parts.append((24 - x - width, baseline + y, pattern, (flags ^ 8) << 8))
        actors.extend(components(vram, parts, 48, 64))
    prefix = OUT / name
    for key, data in dict(tiles=tiles, maps=maps.astype('>u2').tobytes(),
                          pal=struct.pack('>64H', *palette), actors=actors).items():
        prefix.with_name(name + '_' + key + '.bin').write_bytes(data)
    meta = dict(screens=2, screen_rows=28, screen_cols=32, tiles=len(tiles) // 32,
                tiles_bytes=len(tiles), maps_bytes=maps.size * 2, pal_bytes=128,
                source=source.relative_to(ROOT).as_posix(), actor_bytes=len(actors),
                enemy_pce_palette=line)
    prefix.with_suffix('.json').write_text(json.dumps(meta, indent=2) + '\n')
    preview(name, tiles, maps.astype('>u2').tobytes(), palette)
    print(name, meta['tiles'], 'tiles, screens', meta['screens'])


if __name__ == '__main__':
    generate('stage2a2_state', ROOT / 'states' / (STEM + '.mc1'), False)
    generate('stage2b_state', ROOT / (STEM + '.mc2'), True)
