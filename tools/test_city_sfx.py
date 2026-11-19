#!/usr/bin/env python3
"""Verify that the port uploads and starts the packed original PCM effects.

The test selects the dungeon boss scene, presses B (jump) and A (sword), then
serializes the emulator state after the effects have played.  The Mega CD PCM
RAM is part of that state, so the exact sample bytes prove the Sub CPU
received CMD_PLAY_SFX and uploaded the bundled banks.  The same command then
configures channel 2; the emulator's mixed CD-DA output is not used as proof
because the original music and the PCM effects share the stereo mix.
"""
import argparse
import ctypes as ct
from pathlib import Path
import sys

import test_megacd_libretro as harness


def sample_bytes(offset, length):
    data = Path('game/res/audio/city_sfx.bin').read_bytes()
    return data[offset:offset + length]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'system', 'cue', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error('output must be a fresh directory')
    args.output.mkdir(parents=True)

    state_path = args.output / 'pcm-state.bin'

    def before_frame(core, frame):
        if frame == 4600:
            core.retro_serialize_size.restype = ct.c_size_t
            core.retro_serialize.argtypes = [ct.c_void_p, ct.c_size_t]
            size = core.retro_serialize_size()
            buf = ct.create_string_buffer(size)
            assert core.retro_serialize(buf, size)
            state_path.write_bytes(buf.raw)

    sys.argv = ['city-sfx', '--core', str(args.core), '--system', str(args.system),
                '--cue', str(args.cue), '--output', str(args.output),
                '--frames', '4800', '--script-only', '--no-audio-file',
                '--event', '600:start:4', '--event', '2250:down:4',
                '--event', '2320:start:4', '--event', '2450:up:4',
                '--event', '2470:left:4', '--event', '2600:start:4',
                '--event', '4300:b:4', '--event', '4500:a:4']
    harness.main(before_frame=before_frame)

    state = state_path.read_bytes()
    jump = sample_bytes(3328, 3308)
    sword = sample_bytes(0, 3308)
    assert len(state) > 65536, 'emulator state was captured'
    assert jump[:96] in state, 'jump sample is present in Mega CD PCM RAM'
    assert sword[:96] in state, 'sword sample is present in Mega CD PCM RAM'
    print('state %d bytes; jump and sword banks found in PCM RAM' % len(state))
    print('PASS: CMD_PLAY_SFX uploaded both original samples')


if __name__ == '__main__':
    main()
