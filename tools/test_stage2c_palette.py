"""Verify the STG2C background repack and captured player/fire actors.

The dungeon reserves MD palette line 3 for the exact PCE player palette. The
few background tiles that used line 3 are moved to lines 0-2; every other
background tile keeps its exact captured color. The test regenerates the pack,
checks the committed bytes, and compares the actor frames with the PCE
descriptor lists from the save state.
"""
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from extract_state import find_var, load
from pack_stage_state import components
from pce2md import pce_color_to_md

STATE = ROOT / 'states' / 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc2'
ROWS = (0, 8, 16, 24)
PLAYER_PTRS = (0x865c, 0x8667, 0x8672, 0x868d)
FIRE_PTRS = (0x89b8, 0x89bd)


def pce_pixel(tile, x, y):
    bit = 7 - x
    return (((tile[y * 2] >> bit) & 1)
            | (((tile[y * 2 + 1] >> bit) & 1) << 1)
            | (((tile[16 + y * 2] >> bit) & 1) << 2)
            | (((tile[17 + y * 2] >> bit) & 1) << 3))


def packed_pixel(tile, x, y):
    value = tile[y * 4 + x // 2]
    return value >> 4 if x % 2 == 0 else value & 15


def md_rgb(color):
    return ((color >> 1) & 7, (color >> 5) & 7, (color >> 9) & 7)


def nearest(color, line, allowed):
    r, g, b = md_rgb(color)
    return min(allowed, key=lambda i: (
        (md_rgb(line[i])[0] - r) ** 2 + (md_rgb(line[i])[1] - g) ** 2 +
        (md_rgb(line[i])[2] - b) ** 2, i))


class Stage2CPaletteTests(unittest.TestCase):
    def test_captured_actors_and_background_repack(self):
        committed = ROOT / 'game' / 'res' / 'gfx'
        with tempfile.TemporaryDirectory() as temp:
            # Recreate the original four-line background pack first, then run
            # the actor packer against that pristine base.
            base = Path(temp) / 'base'
            (base / 'game' / 'res' / 'gfx').mkdir(parents=True)
            subprocess.run(
                [sys.executable, str(ROOT / 'tools' / 'pack_state_window.py'),
                 str(STATE).replace('\\', '/'), 'stage2c_state', *map(str, ROWS),
                 '--palette-order', '2,3,0,14', '--reserve-line3', '8,9,15',
                 '--pack-all-palettes'],
                cwd=base, check=True, capture_output=True, text=True)
            out = Path(temp) / 'gfx'
            subprocess.run(
                [sys.executable, str(ROOT / 'tools' / 'pack_stage2c_actors.py'),
                 '--base', str(base / 'game' / 'res' / 'gfx'),
                 '--output', str(out)],
                cwd=temp, check=True, capture_output=True, text=True)
            for name in ('tiles', 'maps', 'pal', 'actors'):
                filename = 'stage2c_state_' + name + '.bin'
                generated = (out / filename).read_bytes()
                expected = (committed / filename).read_bytes()
                self.assertEqual(generated, expected, name)

        tiles = (committed / 'stage2c_state_tiles.bin').read_bytes()
        maps = (committed / 'stage2c_state_maps.bin').read_bytes()
        palette = (committed / 'stage2c_state_pal.bin').read_bytes()
        actors = (committed / 'stage2c_state_actors.bin').read_bytes()
        info = json.loads((committed / 'stage2c_state.json').read_text())
        lines = [list(struct.unpack_from('>16H', palette, i * 32)) for i in range(4)]

        self.assertEqual(len(tiles), 159 * 32)
        self.assertEqual(len(maps), 4 * 32 * 24 * 2)
        self.assertEqual(len(palette), 4 * 16 * 2)
        self.assertEqual(len(actors), (4 + 2) * 48 * 32 + 32)

        state = load(str(STATE))
        vram = find_var(state, b'VRAM')
        cram = find_var(state, b'color_table')
        cdram = find_var(state, b'CDRAM')
        cram_words = [cram[i] | (cram[i + 1] << 8)
                      for i in range(0, len(cram), 2)]
        pce = [pce_color_to_md(word) for word in cram_words]

        # Line 3 is the exact captured player palette; line 2 carries the two
        # brightest fire colors in previously unused slots.
        self.assertEqual(lines[3], pce[256 + 5 * 16:256 + 5 * 16 + 16])
        self.assertEqual(lines[2][14], pce[256 + 7 * 16 + 3])
        self.assertEqual(lines[2][15], pce[256 + 7 * 16 + 15])

        moved = {entry['tile'] for entry in info['background_moved_line3_tiles']}
        for screen, row0 in enumerate(ROWS):
            for y in range(24):
                for x in range(32):
                    cell = screen * 32 * 24 + y * 32 + x
                    entry = int.from_bytes(maps[cell * 2:cell * 2 + 2], 'big')
                    md_tile, md_line = entry & 0x1fff, (entry >> 13) & 3
                    self.assertLess(md_line, 3, ('background line 3', cell))
                    source_word = (vram[(row0 + y) * 128 + x * 2]
                                   | (vram[(row0 + y) * 128 + x * 2 + 1] << 8))
                    source_tile, source_pal = source_word & 0xfff, source_word >> 12
                    source = vram[source_tile * 32:source_tile * 32 + 32]
                    packed = tiles[md_tile * 32:(md_tile + 1) * 32]
                    for py in range(8):
                        for px in range(8):
                            source_index = pce_pixel(source, px, py)
                            packed_index = packed_pixel(packed, px, py)
                            expected = pce_color_to_md(
                                cram_words[source_pal * 16 + source_index])
                            actual = lines[md_line][packed_index]
                            if md_tile in moved:
                                allowed = [i for i in range(16)
                                           if not (md_line == 2 and i in (14, 15))]
                                self.assertEqual(packed_index,
                                                 nearest(expected, lines[md_line],
                                                         allowed),
                                                 (screen, x, y, px, py, 'moved'))
                            else:
                                self.assertEqual(actual, expected,
                                                 (screen, x, y, px, py,
                                                  source_pal, source_index))

        # The first four frames are the captured PCE player poses; line 3 uses
        # the same palette order, so their packed bytes are identical.
        for frame, pointer in enumerate(PLAYER_PTRS):
            parts = []
            for n in range(cdram[pointer]):
                flags, y, x, pattern = struct.unpack_from(
                    '<BbbH', cdram, pointer + 1 + n * 5)
                parts.append((x + 16, y + 48, pattern, flags << 8))
            expected = components(vram, parts, 64, 48)
            start = frame * 48 * 32
            self.assertEqual(actors[start:start + 48 * 32], expected,
                             ('player frame', frame, hex(pointer)))

        # The two fire frames are the captured descriptor composites after the
        # documented warm palette remap.
        fire_map = info['fire_palette_map']
        for frame, pointer in enumerate(FIRE_PTRS, start=4):
            parts = []
            for n in range(cdram[pointer]):
                flags, y, x, pattern = struct.unpack_from(
                    '<BbbH', cdram, pointer + 1 + n * 5)
                parts.append((x + 32, y + 64, pattern, flags << 8))
            source = components(vram, parts, 48, 64)
            expected = bytes((fire_map[b >> 4] << 4) | fire_map[b & 15]
                             for b in source)
            start = frame * 48 * 32
            self.assertEqual(actors[start:start + 48 * 32], expected,
                             ('fire frame', frame, hex(pointer)))

        # The last tile is the 8x8 HUD heart recoloured into the same line.
        heart = actors[-32:]
        self.assertTrue(any(heart))
        self.assertEqual(sorted({v for b in heart for v in (b >> 4, b & 15) if v}),
                         [1, 9, 15])


if __name__ == '__main__':
    unittest.main()
