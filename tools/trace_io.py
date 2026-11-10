#!/usr/bin/env python3
"""Run the real System Card from its reset vector and log every I/O access.

My earlier runs intercepted the BIOS entry points with a shim, which prevents
the real boot code from running.  This tool disables the shim, starts at the
6502 reset vector and records every I/O read/write so the CD-ROM drive
registers that must be emulated become explicit.
"""
import glob
import sys
from collections import Counter

sys.path.insert(0, 'tools')
from pce_system import PCESystem, WRAM_BASE
from emu_game import Disc, TRACK

ROM = sorted(glob.glob('syscard3.pce'))[0] if glob.glob('syscard3.pce') \
    else sorted(glob.glob('*v3.0*.pce'))[0]
rom = open(ROM, 'rb').read()

reset_lo = rom[0x1FFC] | (rom[0x1FFD] << 8)
print('ROM            :', ROM)
print('reset vector   : $%04X (image[0x1FFC])' % reset_lo)

emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x

# no BIOS shim: let the real ROM run
emu._bios_enabled = False

# standard reset state
emu.cpu.mpr = [0xFF, 0xF8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
emu.cpu.pc = reset_lo
emu.cpu.sp = 0xFF

io_reads = Counter()
io_writes = Counter()

orig_read = emu.read
orig_write = emu.write


def read(addr):
    if addr < 0x2000 and emu.cpu.mpr[0] == 0xFF:
        io_reads[addr] += 1
    return orig_read(addr)


def write(addr, val):
    if addr < 0x2000 and emu.cpu.mpr[0] == 0xFF:
        io_writes[addr] += 1
    return orig_write(addr, val)


emu.read = read
emu.write = write
emu.cpu.read = read
emu.cpu.write = write

steps = 0
try:
    for _ in range(300000):
        emu.cpu.step()
        steps += 1
except StopIteration as e:
    print('control transfer:', e)
except RuntimeError as e:
    print('stopped after %d steps: %s' % (steps, e))

print('steps          :', steps)
print('cpu            : pc=%04X a=%02X mpr=%s'
      % (emu.cpu.pc, emu.cpu.a, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print()
print('I/O writes (address: count):')
for addr, n in io_writes.most_common(30):
    print('   $%04X  %6d' % (addr, n))
print()
print('I/O reads (address: count):')
for addr, n in io_reads.most_common(30):
    print('   $%04X  %6d' % (addr, n))
