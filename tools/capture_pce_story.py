"""Capture the Japanese PCE story from the title or the defeated city boss.

Supply Beetle PCE Fast, its BIOS directory and the original Japanese CUE.
Writes the original 256x243 RGB565 raster at six-frame intervals.
"""
import argparse
import ctypes as ct
import gzip
from pathlib import Path
import struct
import sys
import zlib

import test_megacd_libretro as harness

ROOT = Path(__file__).resolve().parents[1]
# Input frame numbering is relative to the supplied checkpoint, before retro_run.
# The clip intervals start on the first sample of each CD-DA cue.
CHAPTERS = {
    'prologue': [(408, 1950, 6), (2070, 2970, 7), (3078, 4926, 8),
                 (5028, 8070, 9), (8160, 11250, 10)],
    'opening': [(2568, 5670, 11)],
    'rescue': [(143, 3593, 12)],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene', choices=CHAPTERS)
    for key in ('core', 'system', 'cue', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args()
    chapters = CHAPTERS[args.scene]
    if args.scene == 'rescue':
        raw = gzip.decompress((ROOT/'states/city_pce_after_boss.mednafen.gz').read_bytes())
    else:
        raw = (ROOT/'states/title_pce_menu.mednafen').read_bytes()

    def restore(core, frame):
        if frame == 0:
            core.retro_unserialize.argtypes = [ct.c_void_p, ct.c_size_t]
            core.retro_unserialize.restype = ct.c_bool
            if not core.retro_unserialize(ct.create_string_buffer(raw), len(raw)):
                raise RuntimeError('the PCE core rejected the checkpoint')

    def capture(frame, image):
        if any(start <= frame < stop and (frame-start) % 6 == 0 for start, stop, _ in chapters):
            width, height, pitch, fmt, data = image
            if (width, height, fmt) != (256, 243, 2):
                raise ValueError(f'expected 256x243 RGB565, got {width}x{height}, format {fmt}')
            record = struct.pack('<4H', width, height, pitch, fmt) + data
            (args.output/f'{frame:05}.z').write_bytes(zlib.compress(record, 1))

    sys.argv = ['capture', '--core', str(args.core), '--system', str(args.system),
                '--cue', str(args.cue), '--output', str(args.output), '--script-only',
                '--no-audio-file', '--frames', str(chapters[-1][1])]
    if args.scene == 'prologue':
        sys.argv += ['--event', '0:start:4']
    elif args.scene == 'opening':
        for tick in range(0, 2401, 600):
            sys.argv += ['--event', f'{tick}:start:8']
        sys.argv += ['--event', '2000:a:400']
    harness.main(before_frame=restore, after_frame=capture, frontend_variables=False)
    for start, stop, track in chapters:
        print(f'pack_pce_story.py "{args.output}" {start} {stop} {track} game/res/gfx/story{track:02}.bin')


if __name__ == '__main__':
    main()
