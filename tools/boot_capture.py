import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK
from disasm6280 import disasm_one

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 2500000

rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF

calls = []
for n in range(1, STEPS + 1):
    pc = emu.cpu.pc
    mn = emu.cpu.step()
    if mn in ('JSR', 'JMP', 'RTS') and n > 500000:
        calls.append((n, pc, mn, emu.cpu.pc))
    if n % 20000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

print('steps', n, 'pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('disc reads:', sorted(set(emu.disc.reads))[:30], 'count', len(emu.disc.reads))
print('VRAM writes:', len(emu.vram_writes), 'CRAM:', sum(1 for c in emu.cram if c))
print('last 12 transfers:')
for t in calls[-12:]:
    print('  %7d %04X %-3s -> %04X' % t)
for base, label in ((0x100000, 'physical $100000'), (0x08000, 'physical $08000')):
    print('%s: %s' % (label, emu.mem[base:base + 48].hex(' ')))
print('logical $4000 (MPR2=$80):')
off = 0x100000
for _ in range(12):
    txt, ln = disasm_one(emu.mem, off)
    print('   $%04X: %s' % (0x4000 + (off - 0x100000), txt))
    off += ln
emu.dump_vram('build/game_boot_vram.bin')
emu.dump_cram('build/game_boot_cram.bin')
print('dumped build/game_boot_vram.bin / build/game_boot_cram.bin')
