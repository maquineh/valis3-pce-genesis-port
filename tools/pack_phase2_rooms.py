"""Pack the observed STG2A coast and STG2B forest raster splits and live actors."""
import itertools
import json
import struct

import numpy as np

from extract_state import find_var, load
from pack_stage_state import OUT, ROOT, STEM, components, packed
from pce2md import pce_color_to_md
from pce_gfx import bg_tile_pixels


def map_tiles(vram, colors):
    bat = struct.unpack_from('<4096H', vram)
    # Both saves switch from the status bar to the playfield at scanline 40.
    words = [bat[((49 if y < 5 else 2) + y) * 64 + x]
             for y in range(28) for x in range(32)]
    entries, inverse, counts = np.unique(words, return_inverse=True, return_counts=True)
    pixels = []
    for word in entries:
        start = (int(word) & 0xfff) * 32
        bank = int(word >> 12) * 16
        pixels.append([colors[bank + i] if i else 0
                       for row in bg_tile_pixels(vram[start:start + 32]) for i in row])
    return np.array(pixels), inverse, counts


def palette_map(pixels, counts, colors, enemy_palette):
    # Keep actor colors exact. Choose the other two lines by minimizing the
    # pixel-weighted RGB error with a single hardware line per map cell.
    actor_lines = [colors[enemy_palette:enemy_palette + 16], colors[336:352]]
    values = np.unique([*pixels.flat, *colors, 0])
    rgb = np.stack([(values >> shift) & 7 for shift in (1, 5, 9)], axis=1)
    distances = ((rgb[:, None] - rgb[None, :]) ** 2).sum(axis=2)
    ids = np.searchsorted(values, pixels)
    hist = np.array([np.bincount(tile, minlength=len(values)) for tile in ids])
    def bank_ids(line):
        return np.searchsorted(values, [0, *line[1:]])
    def errors(line):
        return hist @ distances[:, bank_ids(line)].min(axis=1)
    candidates = [colors[n:n + 16] for n in range(0, 256, 16)]
    def score(lines):
        return np.minimum.reduce([errors(line) for line in lines + actor_lines]) @ counts
    lines = list(min(itertools.combinations(candidates, 2), key=lambda pair: score(list(pair))))
    while True:
        assignment = np.argmin([errors(line) for line in lines + actor_lines], axis=0)
        improved = False
        for n in range(2):
            weights = (counts * (assignment == n)) @ hist
            line = bank_ids(lines[n]).copy()
            for slot in range(1, 16):
                other = distances[:, np.delete(line, slot)].min(axis=1)
                costs = weights @ np.minimum(other[:, None], distances)
                best = int(costs.argmin())
                if costs[best] < costs[line[slot]]:
                    line[slot] = best
                    improved = True
            lines[n] = values[line].tolist()
        if not improved:
            break
    lines += actor_lines
    banks = np.argmin([errors(line) for line in lines], axis=0)
    mappings = np.array([distances[:, bank_ids(line)].argmin(axis=1) for line in lines])
    catalog = {bytes(32): 0}
    entries = []
    for tile, bank in zip(ids, banks):
        data = packed(mappings[bank, tile].tolist())
        entries.append(catalog.setdefault(data, len(catalog)) | int(bank) << 13)
    return b''.join(catalog), np.array(entries), sum(lines, [])


def generate(name, source, forest):
    raw = load(source)
    vram, cram, sat, cd = [find_var(raw, key) for key in
                            (b'VRAM', b'color_table', b'SAT', b'CDRAM')]
    colors = [pce_color_to_md(w) for w in struct.unpack('<512H', cram)]
    pieces = [struct.unpack_from('<4H', sat, i * 8) for i in (3, 4)]
    line = pieces[0][3] & 15
    assert all((attr & 15) == line for _, _, _, attr in pieces)
    pixels, inverse, counts = map_tiles(vram, colors)
    tiles, entries, palette = palette_map(pixels, counts, colors, 256 + 16 * line)
    maps = entries[inverse]
    actors = bytearray()
    for ptr in (0x8636, 0x8651, 0x865c, 0x86c3):
        parts = []
        for n in range(cd[ptr]):
            flags, y, x, pattern = struct.unpack_from('<BbbH', cd, ptr + 1 + n * 5)
            parts.append((x + 16, y + 48, pattern, flags << 8))
        actors.extend(components(vram, parts, 64, 48))
    # The live SAT faces left. Mirror the game's frame offsets/flags into
    # that same orientation before composing the Genesis hardware pieces.
    # Coast: idle then the three frames of animation  $4a/$4b/$4c.
    # Forest: the three poses that share the captured enemy's upper body.
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
    meta = dict(screens=1, screen_rows=28, screen_cols=32, tiles=len(tiles) // 32,
                tiles_bytes=len(tiles), maps_bytes=maps.size * 2, pal_bytes=128,
                source=source.relative_to(ROOT).as_posix(), actor_bytes=len(actors),
                enemy_pce_palette=line)
    prefix.with_suffix('.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(name, meta['tiles'], 'tiles')


if __name__ == '__main__':
    generate('stage2a2_state', ROOT / 'states' / (STEM + '.mc1'), False)
    generate('stage2b_state', ROOT / (STEM + '.mc2'), True)
