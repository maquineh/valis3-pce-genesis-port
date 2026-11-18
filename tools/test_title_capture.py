#!/usr/bin/env python3
"""Validate the committed title assets against the captured frame."""
import json
import unittest
from pathlib import Path
from PIL import Image
import pack_title_capture as pack


class TitleCaptureTest(unittest.TestCase):
    def test_reproducible_and_faithful(self):
        out = pack.OUT
        expected_tiles, expected_map, expected_pal, info, reference = pack.build()
        tiles = (out / 'title_tiles.bin').read_bytes()
        tilemap = (out / 'title_map.bin').read_bytes()
        palette = (out / 'title_pal.bin').read_bytes()
        self.assertEqual((tiles, tilemap, palette),
                         (expected_tiles, expected_map, expected_pal))
        self.assertEqual(json.loads((out / 'title.json').read_text(encoding='utf-8')), info)
        self.assertEqual(len(tiles), info['tile_count'] * 32)
        self.assertLessEqual(info['tile_count'], 2048)
        self.assertEqual(tiles[:32], bytes(32))
        self.assertEqual(len(tilemap), 32 * 28 * 2)
        self.assertEqual(len(palette), 4 * 16 * 2)
        self.assertEqual([palette[i * 32:i * 32 + 2] for i in range(4)], [b'\0\0'] * 4)
        self.assertLessEqual(info['max_absolute_channel_error'], 4)
        img = Image.open(out / 'title_reference.png').convert('RGB')
        self.assertEqual(img.size, (256, 224))
        self.assertEqual(list(img.getdata()), reference)
        decoded = [(0, 0, 0)] * (256 * 224)
        for pos in range(896):
            word = int.from_bytes(tilemap[pos * 2:pos * 2 + 2], 'big')
            self.assertEqual(word & 0x9800, 0)  # no priority or flips
            tile, line = word & 0x7ff, (word >> 13) & 3
            self.assertLess(tile, info['tile_count'])
            for y in range(8):
                for x in range(8):
                    byte = tiles[tile * 32 + y * 4 + x // 2]
                    index = (byte >> (4 if x % 2 == 0 else 0)) & 15
                    col = int.from_bytes(palette[line * 32 + index * 2:line * 32 + index * 2 + 2], 'big')
                    self.assertEqual(col & ~0x0eee, 0)
                    rgb = tuple((v * 255 + 3) // 7 for v in
                                ((col >> 1) & 7, (col >> 5) & 7, (col >> 9) & 7))
                    decoded[(pos // 32 * 8 + y) * 256 + pos % 32 * 8 + x] = rgb
        self.assertEqual(decoded, reference)


if __name__ == '__main__':
    unittest.main()
