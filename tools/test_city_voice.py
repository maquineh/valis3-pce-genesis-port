#!/usr/bin/env python3
"""Verify that Cham's original voice bank is uploaded before the meeting.

The script follows the same early city route used by test_city_cdda.py,
serializes the emulator state during the abduction scene, and searches the
Mega CD PCM RAM for the checked-in city_cham.pcm bytes.  The voice source is
track 19 at 7.98-11.60 s, extracted by tools/pack_cham_voice.py.
"""
import argparse
import ctypes as ct
from pathlib import Path
import sys

import test_megacd_libretro as harness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'system', 'cue', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error('output must be a fresh directory')
    args.output.mkdir(parents=True)
    state_path = args.output / 'voice-state.bin'

    def before_frame(core, frame):
        if frame == 3300:
            core.retro_serialize_size.restype = ct.c_size_t
            core.retro_serialize.argtypes = [ct.c_void_p, ct.c_size_t]
            size = core.retro_serialize_size()
            buf = ct.create_string_buffer(size)
            assert core.retro_serialize(buf, size)
            state_path.write_bytes(buf.raw)

    sys.argv = ['city-voice', '--core', str(args.core), '--system', str(args.system),
                '--cue', str(args.cue), '--output', str(args.output),
                '--frames', '3600', '--script-only', '--no-audio-file',
                '--event', '600:start:4', '--event', '2250:start:4',
                '--event', '2420:start:4', '--event', '2650:right:880']
    harness.main(before_frame=before_frame)

    state = state_path.read_bytes()
    voice = Path('game/res/audio/city_cham.pcm').read_bytes()
    assert len(state) > 65536, 'emulator state was captured'
    assert voice[:128] in state, 'Cham voice bank is present in Mega CD PCM RAM'
    print('state %d bytes; Cham voice sample found in PCM RAM' % len(state))
    print('PASS: the original Cham voice is uploaded for the meeting scene')


if __name__ == '__main__':
    main()
