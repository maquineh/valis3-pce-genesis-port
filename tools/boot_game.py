#!/usr/bin/env python3
"""Run the real System Card boot and, at the final `JMP $4000`, install the
MPR2-6 = $04..$08 mapping the card's success path uses.  The game's boot code
has already been loaded at physical $08000 by the IPL read.
"""
import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 6000000

rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF

forced = False
calls = []
for n in range(1, STEPS + 1):
    pc = emu.cpu.pc
    if pc == 0x4000 and not forced and emu.cpu.mpr[2] != 0x04:
        emu.cpu.mpr[2:7] = [0x04, 0x05, 0x06, 0x07, 0x08]
        forced = True
        print('forced MPR2-6=04..08 at step', n)
    mn = emu.cpu.step()
    if mn in ('JSR', 'JMP', 'RTS') and n > 100000:
        calls.append((n, pc, mn, emu.cpu.pc))
    if n % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

print('steps', n, 'pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('disc reads:', sorted(set(emu.disc.reads))[:20], 'count', len(emu.disc.reads))
print('VRAM writes:', len(emu.vram_writes), 'CRAM:', sum(1 for c in emu.cram if c))
print('last 20 transfers:')
for t in calls[-20:]:
    print('  %7d %04X %-3s -> %04X' % t)
for base, label in ((0x08000, 'game boot $08000'), (0x100000, 'super CD $100000')):
    print('%s: %s' % (label, emu.mem[base:base + 32].hex(' ')))
