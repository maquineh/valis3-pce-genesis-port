"""Rebuild STG2A's split HUD/background and actors from the supplied Mednafen states."""
import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np
from pce_state import decompress, parse
from pce2md import pce_color_to_md
from pce_gfx import bg_tile_pixels
from render_pce_state import decode_sprite

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'game/res/gfx'
STEM = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48'
PREFIX = 'stage2_state_'


def load(path):
    return {key: value[2] for key, value in parse(decompress(str(path))).items()}


def packed(pixels):
    return bytes(a * 16 + b for a, b in zip(pixels[::2], pixels[1::2]))


def components(vram, parts, width, height):
    canvas = [[0] * width for _ in range(height)]
    for x, y, pattern, attr in reversed(parts):
        # In each 16-pixel VDC cell the two bytes of a plane are little-endian.
        for dy, row in enumerate(decode_sprite(vram, pattern, attr)):
            for dx in range(len(row)):
                value = row[dx ^ 8]
                if value:
                    assert 0 <= y + dy < height and 0 <= x + dx < width
                    canvas[y + dy][x + dx] = value
    result = bytearray()
    for top in range(0, height, 32):
        for left in range(0, width, 32):
            for tx in range(left, min(left + 32, width), 8):
                for ty in range(top, min(top + 32, height), 8):
                    result.extend(packed([canvas[y][x] for y in range(ty, ty+8) for x in range(tx, tx+8)]))
    return result


def generate():
    first = load(ROOT / (STEM + '.mc0'))
    seaside = load(ROOT / 'states' / (STEM + '.mc1'))
    vram = first['VRAM']
    words = struct.unpack('<32768H', vram)
    colors = [pce_color_to_md(w) for w in struct.unpack('<512H', first['color_table'])]
    sea_colors = [pce_color_to_md(w) for w in struct.unpack('<512H', seaside['color_table'])]
    palettes = [colors[:16], [], sea_colors[256:272], colors[336:352]]
    hud = []
    for row in range(17, 22):
        for entry in words[row*64:row*64+32]:
            start = (entry & 0xfff)*32
            hud.append([colors[(entry >> 12)*16+i] if i else 0
                        for line in bg_tile_pixels(vram[start:start+32]) for i in line])

    # Reserve the two full actor banks and the landscape bank. Choose the
    # fourth bank by minimizing HUD error with one palette per hardware tile.
    freq = Counter(v for tile in hud for v in tile if v)
    values = sorted({0, *freq, *palettes[0], *palettes[2], *palettes[3]})
    vi = {v:i for i,v in enumerate(values)}
    rgb = np.array([[(v>>s)&7 for s in (1,5,9)] for v in values])
    distance = ((rgb[:, None]-rgb[None, :]) ** 2).sum(axis=2)
    hist = np.array([[tile.count(v) for v in values] for tile in hud])
    def errors(bank):
        # Index 0 shows the black backdrop. Sprite palettes have a different
        # hardware color zero, which is transparent on plane B as well.
        return distance[:,[vi[v] for v in [0,*bank[1:]]]].min(axis=1)
    fixed = np.minimum.reduce([hist @ errors(palettes[i]) for i in (0,2,3)])
    bank = [0]+[v for v,_ in freq.most_common(15)]
    def score(b):
        return np.minimum(fixed, hist @ errors(b)).sum()
    while True:
        best = score(bank)
        replacement = None
        for i in range(1,len(bank)):
            for v in sorted(freq.keys()-set(bank)):
                trial = bank.copy(); trial[i] = v
                cost = score(trial)
                if cost < best:
                    replacement, best = trial, cost
        if replacement is None:
            break
        bank = replacement
    palettes[1] = bank
    banks = [[0, *b[1:]] for b in palettes]
    lookup = [distance[:,[vi[v] for v in b]].argmin(axis=1) for b in banks]
    costs = np.array([hist @ errors(b) for b in banks])
    tiles = {bytes(32):0}
    def entry(indices, line):
        tile = packed(indices)
        return tiles.setdefault(tile,len(tiles)) | line<<13

    hud_map = []
    for t, tile in enumerate(hud):
        line = int(costs[:,t].argmin())
        hud_map.append(entry([int(lookup[line][vi[v]]) for v in tile], line))
    # Rows 17..21 are the fixed HUD. At screen y=40 the raster split
    # displays BAT row 39. These offsets match the state's embedded preview.
    maps = []
    for screen in range(4):
        for y in range(28):
            for x in range(32):
                if y < 5:
                    maps.append(0)
                    continue
                sy = min(63, 34 + y + (8 if screen >= 2 else 0))
                if screen % 2:
                    sy = 39 + (y % 12)  # sea below the gap between platforms
                word = words[sy*64+x]
                assert word >> 12 == 0
                addr = (word & 0xfff)*32
                maps.append(entry([p for row in bg_tile_pixels(vram[addr:addr+32]) for p in row],0))

    actors = bytearray()
    # Frame descriptors in this capture specify offsets relative to the feet.
    # Idle, two strides and drawn sword. Keep the original component positions.
    for ptr in [0x8636,0x8651,0x865c,0x86c3]:
        c = first['CDRAM']
        parts = []
        for n in range(c[ptr]):
            flags,y,x,pattern = struct.unpack_from('<BbbH',c,ptr+1+n*5)
            parts.append((x+16,y+48,pattern,flags<<8))
        actors.extend(components(vram,parts,64,48))
    parts = []
    for idx in (3,4):
        y,x,pattern,attr = struct.unpack_from('<4H',seaside['SAT'],idx*8)
        assert attr & 15 == 0
        parts.append((x-212,y-184,pattern,attr))
    actors.extend(components(seaside['VRAM'],parts,48,64))
    def write(name, data):
        (OUT/(PREFIX+name+'.bin')).write_bytes(data)
    def words_be(data):
        return struct.pack('>'+str(len(data))+'H',*data)
    write('tiles',b''.join(tiles))
    write('maps',words_be(maps))
    write('hud',words_be(hud_map))
    write('pal',words_be(sum(palettes,[])))
    write('actors',actors)
    (OUT/'stage2_state.json').write_text(json.dumps(dict(screens=4, screen_rows=28,
        screen_cols=32, tiles=len(tiles), tiles_bytes=32*len(tiles),maps_bytes=2*len(maps),
        pal_bytes=128, hud_rows=5, source=STEM+'.mc0', enemy_source='states/'+STEM+'.mc1'),indent=2)+'\n')
    print(len(tiles),'tiles;',len(actors),'actor bytes; HUD palette error',score(bank))


if __name__ == '__main__':
    generate()
