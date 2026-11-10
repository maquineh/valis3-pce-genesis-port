#!/usr/bin/env python3
"""Run a real System Card from its reset vector and report where it goes.

This is the unshimmed boot: the card's own reset code initialises the banks,
the VDC and the CD unit.  It is the ground truth for the CD drive handshake.
"""
import sys
from collections import Counter

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

ROM = sys.argv[1] if len(sys.argv) > 1 else 'syscard3.pce'
STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000000

rom = open(ROM, 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
# HuC6280 vector table: $FFFE/$FFFF is RESET.  ($FFFC is IRQ2, which on the
# Super System Card points at the $E6A9 handler - not the reset code.)
reset = rom[0x1FFE] | (rom[0x1FFF] << 8)
if len(sys.argv) > 3:
    reset = int(sys.argv[3], 0)
emu.cpu.pc = reset
emu.cpu.sp = 0xFF

hist = Counter()
io_r = Counter()
io_w = Counter()
o_read, o_write = emu.read, emu.write

def rd(a):
    if a < 0x2000 and emu.cpu.mpr[0] == 0xFF:
        io_r[a] += 1
    return o_read(a)

def wr(a, v):
    if a < 0x2000 and emu.cpu.mpr[0] == 0xFF:
        io_w[a] += 1
    return o_write(a, v)

emu.read, emu.write = rd, wr
emu.cpu.read, emu.cpu.write = rd, wr

print('ROM %s reset=$%04X steps=%d' % (ROM, reset, STEPS))
n = 0
irq_every = int(sys.argv[4], 0) if len(sys.argv) > 4 else 2000
try:
    for _ in range(STEPS):
        hist[emu.cpu.pc] += 1
        emu.cpu.step()
        n += 1
        # The card's timer handler ($FFF8 -> $E870) bumps the frame counter
        # at $2241, which every vsync wait polls.  Without a periodic IRQ
        # the BIOS hangs in $E3C1 forever.
        if irq_every and n % irq_every == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20          # VBlank IRQ pending
            emu.cpu.interrupt(0xFFF8)       # timer vector, which polls VDC status
except StopIteration as e:
    print('transfer:', e)
except RuntimeError as e:
    print('stop:', e)

print('steps %d  pc=$%04X  mpr=%s' %
      (n, emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('disc reads:', sorted(set(emu.disc.reads))[:12], 'count', len(emu.disc.reads))
print('VRAM writes:', len(emu.vram_writes), 'CRAM:', sum(1 for c in emu.cram if c))
print('hot pcs:', [('$%04X' % a, c) for a, c in hist.most_common(8)])
print('io writes:', [('$%04X' % a, c) for a, c in io_w.most_common(12)])
print('io reads :', [('$%04X' % a, c) for a, c in io_r.most_common(12)])
