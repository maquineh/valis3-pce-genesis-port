"""Capture the original city's VDP state from a user-supplied Japanese cartridge."""
import argparse
import ctypes as ct
from pathlib import Path
import struct
import sys
import zlib

import test_megacd_libretro as harness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'system', 'rom', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    core = ct.CDLL(str(args.core.resolve()))
    core.retro_serialize_size.restype = ct.c_size_t
    core.retro_serialize.argtypes = [ct.c_void_p, ct.c_size_t]
    core.retro_serialize.restype = ct.c_bool
    wanted = {6260, 6352, 6450, 6472, 7248, 7890, 8070, 10000, 11490}
    wanted.update(range(6368, 7025, 16))
    wanted.update(range(11970, 12220, 3))
    wanted.update(range(12000, 12641, 16))
    presses = {3700, 6300, 7300, *range(7550, 10200, 75), *range(11250, 11900, 90)}
    recorded = set()
    descent = []
    sampled = -1

    def input_at(events, frame, button):
        nonlocal sampled
        save = frame in wanted and frame not in recorded
        falling = (9650 <= frame <= 11600 and frame != sampled and
                   (not descent or descent[-1][3] < 176))
        if save or falling:
            size = core.retro_serialize_size()
            buf = ct.create_string_buffer(size)
            if not core.retro_serialize(buf, size):
                raise RuntimeError('core failed to export city state')
            raw = buf.raw
            if save:
                (args.output / f's{frame}.z').write_bytes(zlib.compress(raw, 1))
                recorded.add(frame)
            if falling:
                sampled = frame
                regs = raw[0x22525:0x22545]
                if regs[11] == 4:
                    vs = struct.unpack_from('<16h', raw, 0x224a5)
                    sat = 0x12425 + regs[5] * 512
                    link = 0
                    for _ in range(80):
                        y, size, attr, x = struct.unpack_from('<4H', raw, sat + link*8)
                        if (attr & 2047) == 0xc6:
                            feet = (y & 511) - 128 + ((size >> 8 & 3)+1)*8
                            record = (vs[0], vs[1], vs[14], feet)
                            # The reference route contains deliberate START pauses.
                            if not descent or record != descent[-1]:
                                descent.append(record)
                            break
                        link = size & 127
                        if not link:
                            break
        if frame < 2800:
            return button == 3 and frame >= 120 and frame % 400 < 4
        if button == 3:
            return any(frame - i in presses for i in range(4))
        if frame > 10300 and button in (0, 1, 8):
            return (frame + 3 * button) % 57 < 5
        return button == 7 and frame >= 5400

    harness.event_pressed = input_at
    sys.argv = ['capture', '--core', str(args.core), '--system', str(args.system),
                '--cue', str(args.rom), '--output', str(args.output), '--script-only',
                '--no-audio-file', '--frames', str(max(wanted) + 2)]
    harness.main()
    if not descent or descent[0][3] > 48 or descent[-1][3] < 176:
        raise RuntimeError('incomplete column-scroll descent')
    (args.output/'descent.bin').write_bytes(
        struct.pack('>H', len(descent)) + b''.join(struct.pack('>4h', *r) for r in descent))
    if recorded != wanted:
        raise RuntimeError('incomplete city capture')


if __name__ == '__main__':
    main()
