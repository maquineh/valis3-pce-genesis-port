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

def z(a):
    return emu.mem[0x1F0000 + (a & 0x1FFF)]

# boot + title
for n in range(1, 3000001):
    emu.cpu.step()
    if n % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

# START -> act title overlay 976
emu.cpu.pc = 0x4167
emu.mem[0x1F0000 + 0x3C00] = 0
for n in range(1, 12000001):
    emu.cpu.step()
    if n % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)
    if 4202 in emu.disc.reads and 4202 == emu.disc.reads[-1]:
        break

print('976 loaded: steps', n, 'pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('reads', sorted(set(emu.disc.reads))[:30])

before = set(emu.disc.reads)
emu.mem[0x1F0000 + 0x3C01] = 0        # select overlay 968
emu.cpu.pc = 0x6176                  # loader branch -> cd_exec sector 968
for n in range(1, 4000001):
    emu.cpu.step()
    if n % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)
    if len(set(emu.disc.reads) - before) >= 8:
        break

print('after loader: steps', n, 'pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('new reads', sorted(set(emu.disc.reads) - before)[:20])
print('physical $100000:', emu.mem[0x100000:0x100030].hex(' '))
emu.dump_vram('build/stage_attempt_vram.bin')
emu.dump_cram('build/stage_attempt_cram.bin')
print('dumped build/stage_attempt_vram.bin')
