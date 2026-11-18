import tempfile
import unittest
import wave
from pathlib import Path

import cue_split

S = cue_split.SECTOR


class CueSplitTest(unittest.TestCase):
    def test_single_image_and_multifile_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocks = [bytes([i]) * S for i in range(1, 6)]
            (root / 'disc.bin').write_bytes(b''.join(blocks))
            cue = root / 'disc.cue'
            cue.write_text('FILE "disc.bin" BINARY\n TRACK 01 MODE1/2352\n  INDEX 01 00:00:01\n TRACK 02 AUDIO\n  INDEX 01 00:00:03\n')
            manifest = cue_split.split(cue, None, root / 'single')
            self.assertEqual([t['frames'] for t in manifest['tracks']], [2, 2])
            self.assertEqual((root / 'single/data/track_01.bin').read_bytes(), b''.join(blocks[1:3]))
            with wave.open(str(root / 'single/audio/track_02.wav'), 'rb') as wav:
                self.assertEqual(wav.readframes(wav.getnframes()), b''.join(blocks[3:]))
            (root / 'a.bin').write_bytes(b''.join(blocks[:3]))
            (root / 'b.bin').write_bytes(b''.join(blocks[3:]))
            cue.write_text('FILE "a.bin" BINARY\n TRACK 01 MODE1/2352\n  INDEX 00 00:00:00\n  INDEX 01 00:00:01\nFILE "b.bin" BINARY\n TRACK 02 AUDIO\n  INDEX 01 00:00:00\n')
            manifest = cue_split.split(cue, None, root / 'multi')
            self.assertEqual([t['frames'] for t in manifest['tracks']], [2, 2])
            self.assertEqual((root / 'multi/data/track_01.bin').read_bytes(), b''.join(blocks[1:3]))
            with wave.open(str(root / 'multi/audio/track_02.wav'), 'rb') as wav:
                self.assertEqual(wav.readframes(wav.getnframes()), b''.join(blocks[3:]))
            # Old callers can override the CUE file with a single image.
            cue.write_text('FILE "missing.iso" BINARY\n TRACK 01 AUDIO\n  INDEX 01 00:00:03\n')
            manifest = cue_split.split(cue, root / 'disc.bin', root / 'legacy')
            self.assertEqual(manifest['tracks'][0]['frames'], 2)

    def test_invalid_ranges_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'disc.bin').write_bytes(b'x' * S)
            cue = root / 'disc.cue'
            cue.write_text('FILE "disc.bin" BINARY\n TRACK 01 AUDIO\n  INDEX 01 00:00:02\n')
            with self.assertRaises(ValueError):
                cue_split.split(cue, None, root / 'out')
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
