#!/usr/bin/env python3
"""Execute a captured STG4A skull animation in the local HuC core.

Requires the user's STG4A .mc9 state. This checks the original RAM code and
table together; it does not establish full system timing or enemy behavior.
"""
import argparse
from pathlib import Path

from pce_state import decompress, parse
from pce_system import PCESystem


class NullDisc:
    def read_sector(self, sector):
        raise RuntimeError('unexpected disc read: %d' % sector)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', type=Path)
    parser.add_argument('--column', action='store_true',
                        help='verify skull-column animation 0x1A instead of 0x1F')
    args = parser.parse_args()
    values = parse(decompress(str(args.state)))
    cdram = values['CDRAM'][2]
    if cdram[0xA000:0xA005] != b'STG4A':
        raise ValueError('expected an STG4A state')
    # Run the game's object initializer, so the relationship between the
    # object type, dispatch, animation and palette is independently checked.
    init = PCESystem(NullDisc(), verbose=False)
    init.mem[0x100000:0x110000] = cdram
    init.cpu.mpr = [0xFF, 0xF8, 0x80, 0x81, 0x82, 0x85, 0x83, 0]
    init.cpu.x = 0
    init.cpu.a = 5 if args.column else 6
    init.cpu.pc = 0x5765
    for _ in range(5000):
        if init.cpu.pc == 0x5844:
            break
        init.cpu.step()
    else:
        raise RuntimeError('object initializer did not reach its return')
    actual = tuple(init.read(a) for a in (0x26E0, 0x243D, 0x2424))
    expected_init = ((0x2C, 0x1A, 2) if args.column else
                     (0x2D, 0xFF, 2))
    if actual != expected_init:
        raise AssertionError('unexpected object initialization: %s' % (actual,))
    print('PASS: original object dispatch, animation and palette: %s' %
          (actual,))
    emu = PCESystem(NullDisc(), verbose=False)
    emu.mem[0x100000:0x110000] = cdram
    emu.cpu.mpr = [0xFF, 0xF8, 0x80, 0x81, 0x82, 0x85, 0x83, 0]
    emu.cpu.x = 0
    for address, value in ((0x2AAF, 0x10), (0x2C14, 0), (0x2CAD, 0)):
        emu.write(address, value)

    def call(entry):
        emu.cpu.pc = entry
        for _ in range(300):
            # Return sites of the initializer and stepping routine, before RTS.
            if emu.cpu.pc in (0x67F6, 0x681C):
                return
            emu.cpu.step()
        raise RuntimeError('animation routine did not return')

    emu.cpu.a = 0x1A if args.column else 0x1F
    call(0x67F7)
    frames = []
    expected = ([0x2D] * 6 + [0x2E] * 6 + [0x2D] if args.column else
                [0x33] * 5 + [0x34] * 5 + [0x33] * 5 + [0x34] * 5 + [0x33])
    for _ in range(len(expected)):
        frames.append(emu.read(0x2C7A))
        call(0x67DD)
    if frames != expected:
        raise AssertionError('unexpected frame progression: %s' % frames)
    print('PASS: %s original update calls; loop repeats' %
          ('2D/2E = 6/6' if args.column else '33/34 = 5/5'))


if __name__ == '__main__':
    main()
