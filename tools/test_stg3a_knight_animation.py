#!/usr/bin/env python3
"""Execute the captured STG3A knight animation stepper in the local HuC core.

Requires the user's STG3A .mc4 state. This checks the original RAM code and
table together; it does not establish full system timing or STG4A enemies.
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
    args = parser.parse_args()
    values = parse(decompress(str(args.state)))
    cdram = values['CDRAM'][2]
    if cdram[0xA000:0xA005] != b'STG3A':
        raise ValueError('expected an STG3A state')
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

    emu.cpu.a = 0x1F
    call(0x67F7)
    frames = []
    for _ in range(53):
        frames.append(emu.read(0x2C7A))
        call(0x67DD)
    expected = [0x36] * 16 + [0x37] * 10 + [0x38] * 16 + [0x37] * 10 + [0x36]
    if frames != expected:
        raise AssertionError('unexpected frame progression: %s' % frames)
    print('PASS: 36/37/38/37 = 16/10/16/10 original update calls; loop repeats')


if __name__ == '__main__':
    main()
