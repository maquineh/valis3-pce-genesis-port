"""Check sprite palette reservations and lossless stage palette reordering."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GFX = ROOT / 'game' / 'res' / 'gfx'
STEM = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48'
RESERVED = {8, 9, 15}
STAGES = ('stage2_state', 'stage2c_state', 'stage2c_green_state', 'stage2c_b_state',
          'stage3a_state', 'stage1a_state', 'stage4a_state')


def palette_pixels(tiles, maps):
    """Yield palette line, color index, and tile number for each map pixel."""
    if len(maps) % 2 or len(tiles) % 32:
        raise ValueError('invalid packed resource size')
    for i in range(0, len(maps), 2):
        word = int.from_bytes(maps[i:i + 2], 'big')
        tile, line = word & 0x7ff, (word >> 13) & 3
        tiledata = tiles[tile * 32:(tile + 1) * 32]
        if len(tiledata) != 32:
            raise ValueError('map references an unavailable tile')
        for byte in tiledata:
            yield line, byte >> 4, tile
            yield line, byte & 15, tile


class StagePaletteTests(unittest.TestCase):
    def test_sprite_slots_are_unused_by_all_stage_backgrounds(self):
        sprite = (GFX / 'player_spr.bin').read_bytes()
        indices = {n for byte in sprite for n in (byte >> 4, byte & 15)}
        self.assertEqual(indices, {0, *RESERVED})
        for stage in STAGES:
            with self.subTest(stage=stage):
                tiles = (GFX / (stage + '_tiles.bin')).read_bytes()
                maps = (GFX / (stage + '_maps.bin')).read_bytes()
                used = {index for line, index, _ in palette_pixels(tiles, maps) if line == 3}
                self.assertFalse(used & RESERVED, (stage, used))

    def test_phase2_actors_use_their_captured_palettes(self):
        import struct
        from extract_state import load, find_var
        from pce2md import pce_color_to_md
        for stage, source, enemy_line, enemy_frames in (
                ('stage2a2_state', ROOT / 'states' / (STEM + '.mc1'), 0, 4),
                ('stage2b_state', ROOT / (STEM + '.mc2'), 2, 3)):
            with self.subTest(stage=stage):
                raw = find_var(load(source), b'color_table')
                colors = [pce_color_to_md(v) for v in struct.unpack('<512H', raw)]
                pal = struct.unpack('>64H', (GFX / (stage + '_pal.bin')).read_bytes())
                off = 256 + enemy_line * 16
                self.assertEqual(list(pal[32:]), colors[off:off + 16] + colors[336:352])
                actors = (GFX / (stage + '_actors.bin')).read_bytes()
                poses = [actors[i:i + 1536] for i in range(0, len(actors), 1536)]
                self.assertEqual(len(set(poses)), 4 + enemy_frames)
                self.assertTrue(all(len(frame) == 1536 and any(frame) for frame in poses))
                maps = (GFX / (stage + '_maps.bin')).read_bytes()
                self.assertEqual(len(maps), 32 * 28 * 2)
                tiles = (GFX / (stage + '_tiles.bin')).read_bytes()
                self.assertTrue(any(index for _, index, _ in palette_pixels(tiles, maps)))

    def test_reserved_color_conflict_fails_before_writing(self):
        state = ROOT / (STEM + '.mc4')
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, str(ROOT / 'tools' / 'pack_state_window.py'),
                 str(state), 'conflict', '0', '8', '--reserve-line3', '8,9,15'],
                cwd=temp, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('uses reserved pixel indices', result.stderr)
            self.assertFalse((Path(temp) / 'game' / 'res' / 'gfx').exists())

    def test_reordered_palettes_preserve_the_generated_background(self):
        cases = (
            ('stage3a_state', ROOT / 'states' / 'stg3a_additional.mc4',
             ['32', '32', '--columns', '0,32', '--reserve-line3', '8,9,15',
              '--pack-all-palettes'], '2,1,0,2'),
        )
        for stage, state, pack_args, order in cases:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temp:
                args = [sys.executable, str(ROOT / 'tools' / 'pack_state_window.py'),
                        str(state), stage, *pack_args]
                subprocess.run(args, cwd=temp, check=True, capture_output=True, text=True)
                folder = Path(temp) / 'game' / 'res' / 'gfx'
                original = {kind: (folder / (stage + '_' + kind + '.bin')).read_bytes()
                            for kind in ('tiles', 'maps', 'pal')}
                subprocess.run(args + ['--palette-order', order],
                               cwd=temp, check=True, capture_output=True, text=True)
                updated = {kind: (folder / (stage + '_' + kind + '.bin')).read_bytes()
                           for kind in ('tiles', 'maps', 'pal')}
                def rendered_colors(resources):
                    return [resources['pal'][(line * 16 + index) * 2:
                                             (line * 16 + index + 1) * 2]
                            for line, index, _ in palette_pixels(
                                resources['tiles'], resources['maps'])]

                self.assertEqual(rendered_colors(original), rendered_colors(updated))
                for kind, data in updated.items():
                    self.assertEqual(data, (GFX / (stage + '_' + kind + '.bin')).read_bytes())


if __name__ == '__main__':
    unittest.main()
