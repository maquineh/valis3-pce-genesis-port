import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF

PRE = 3000000
HOLD = 500000
POST = 2500000
before = None
for n in range(1, PRE + HOLD + POST + 1):
    if n == PRE + 1:
        before = set(emu.disc.reads)
        emu.joy_low = 0x07         # press Run/Start (button nibble, bit3 low)
        print('pressed START at step', n, 'reads so far', len(before))
    if n == PRE + HOLD + 1:
        emu.joy_low = 0x0F
        print('released START at step', n)
    emu.cpu.step()
    if n % 20000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

print('steps', n, 'pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('new reads after press:', sorted(set(emu.disc.reads) - before)[:40])
print('all reads count', len(emu.disc.reads), 'distinct', len(set(emu.disc.reads)))
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
emu.dump_vram('build/game_after_start_vram.bin')
emu.dump_cram('build/game_after_start_cram.bin')
print('dumped build/game_after_start_vram.bin')
