"""Verify Stage 2C palette packing preserves every captured PCE pixel color."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from extract_state import find_var, load
from pce2md import pce_color_to_md

STATE = ROOT / 'states' / 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc2'
ROWS = (0, 8, 16, 24)


def pce_pixel(tile, x, y):
    bit = 7 - x
    return (((tile[y * 2] >> bit) & 1)
            | (((tile[y * 2 + 1] >> bit) & 1) << 1)
            | (((tile[16 + y * 2] >> bit) & 1) << 2)
            | (((tile[17 + y * 2] >> bit) & 1) << 3))


class Stage2CPaletteTests(unittest.TestCase):
    def test_all_bat_colors_survive_four_line_repack(self):
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run(
                [sys.executable, str(ROOT / 'tools' / 'pack_state_window.py'),
                 str(STATE), 'stage2c_state', *map(str, ROWS),
                 '--palette-order', '2,3,0,14', '--reserve-line3', '8,9,15',
                 '--pack-all-palettes'],
                cwd=temp, check=True, capture_output=True, text=True)
            gfx = Path(temp) / 'game' / 'res' / 'gfx'
            tiles = (gfx / 'stage2c_state_tiles.bin').read_bytes()
            maps = (gfx / 'stage2c_state_maps.bin').read_bytes()
            palette = (gfx / 'stage2c_state_pal.bin').read_bytes()

        self.assertEqual(len(tiles), 159 * 32)
        self.assertEqual(len(maps), 4 * 32 * 24 * 2)
        self.assertEqual(len(palette), 4 * 16 * 2)

        state = load(str(STATE))
        vram = find_var(state, b'VRAM')
        cram = find_var(state, b'color_table')
        cram_words = [cram[i] | (cram[i + 1] << 8)
                      for i in range(0, len(cram), 2)]
        for screen, row0 in enumerate(ROWS):
            for y in range(24):
                for x in range(32):
                    cell = screen * 32 * 24 + y * 32 + x
                    entry = int.from_bytes(maps[cell * 2:cell * 2 + 2], 'big')
                    md_tile, md_line = entry & 0x7ff, (entry >> 13) & 3
                    source_word = (vram[(row0 + y) * 128 + x * 2]
                                   | (vram[(row0 + y) * 128 + x * 2 + 1] << 8))
                    source_tile, source_pal = source_word & 0xfff, source_word >> 12
                    source = vram[source_tile * 32:source_tile * 32 + 32]
                    for py in range(8):
                        for px in range(8):
                            source_index = pce_pixel(source, px, py)
                            packed = tiles[md_tile * 32 + py * 4 + px // 2]
                            packed_index = packed >> 4 if px % 2 == 0 else packed & 15
                            actual = int.from_bytes(
                                palette[(md_line * 16 + packed_index) * 2:
                                        (md_line * 16 + packed_index) * 2 + 2], 'big')
                            expected = pce_color_to_md(
                                cram_words[source_pal * 16 + source_index])
                            self.assertEqual(actual, expected,
                                             (screen, x, y, px, py, source_pal, source_index))


if __name__ == '__main__':
    unittest.main()
