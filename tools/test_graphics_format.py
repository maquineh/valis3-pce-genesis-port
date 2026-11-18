import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pce2md import pce_tile_to_md, pce_color_to_md, cmd_bat, cmd_pal
from gen_player_spr import md_tile, player_tile, enemy_tiles, heart_tile
from render_scrolled import tile_pixel, words

class GraphicFormatTests(unittest.TestCase):
    def test_pixels_and_plane_order(self):
        pce = bytearray(32)
        pce[0], pce[1], pce[16], pce[17] = 0x55, 0x33, 0x0f, 0x01
        md = pce_tile_to_md(pce)
        self.assertEqual(md[:4], bytes.fromhex('01 23 45 6f'))
        self.assertEqual(md[4:], bytes(28))
    def test_sprite_packed_nibbles(self):
        self.assertEqual(md_tile([[0,1,2,3,4,5,6,15]] * 8)[:4], bytes.fromhex('01 23 45 6f'))
    def test_placeholder_sprite_layout(self):
        enemy = enemy_tiles()
        self.assertEqual(len(heart_tile()), 32)
        self.assertEqual(len(enemy), 4 * 32)
        self.assertEqual({n for byte in enemy for n in (byte >> 4, byte & 15)},
                         {0, 8, 9, 15})
        self.assertNotEqual(enemy[:32], player_tile(0))
    def test_scrolled_renderer_reads_pce_planes_from_same_row(self):
        pce = bytearray(32)
        # Row 3, pixel 0 has all four plane bits set. Row 4 has only p0,
        # ensuring the decoder does not accidentally use adjacent rows.
        pce[6:8] = bytes((0x80, 0x80))
        pce[22:24] = bytes((0x80, 0x80))
        pce[8] = 0x80
        vram = words(pce, 'le')
        self.assertEqual(tile_pixel(vram, 0, 3, 0), 15)
        self.assertEqual(tile_pixel(vram, 0, 3, 1), 0)
        self.assertEqual(tile_pixel(vram, 0, 4, 0), 1)
    def test_words_big_endian(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d)/'in', Path(d)/'out'
            src.write_bytes(bytes.fromhex('34 22'))
            cmd_bat(str(src), 0, 1, 1, str(out), tile_base=0)
            self.assertEqual(out.read_bytes(), bytes.fromhex('42 34'))
            src.write_bytes(bytes.fromhex('38 00'))
            cmd_pal(str(src), 0, 1, str(out))
            self.assertEqual(out.read_bytes(), bytes.fromhex('00 0e'))
            self.assertEqual(pce_color_to_md(0x1ff), 0xeee)

if __name__ == '__main__': unittest.main()
