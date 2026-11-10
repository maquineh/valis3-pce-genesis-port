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

for n in range(1, 3000001):
    emu.cpu.step()
    if n % 20000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

before = set(emu.disc.reads)
print('title loaded, reads', len(before), 'pc', hex(emu.cpu.pc), 'mpr', emu.cpu.mpr)
# Enter the START branch directly (the pad edge is lost between IRQ and the loop)
emu.cpu.pc = 0x42E8
emu.mem[0x1F0000 + 0x3C00] = 0

calls = []
for n in range(1, 4000001):
    pc = emu.cpu.pc
    mn = emu.cpu.step()
    if mn in ('JSR', 'JMP', 'RTS') and n > 1000:
        calls.append((n, pc, mn, emu.cpu.pc))
    if n % 20000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

print('after start: pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('new reads:', sorted(set(emu.disc.reads) - before)[:40])
print('all reads count', len(emu.disc.reads), 'distinct', len(set(emu.disc.reads)))
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
print('last 20 transfers:')
for t in calls[-20:]:
    print('  %7d %04X %-3s -> %04X' % t)
emu.dump_vram('build/game_start_vram.bin')
emu.dump_cram('build/game_start_cram.bin')
print('dumped build/game_start_vram.bin')
