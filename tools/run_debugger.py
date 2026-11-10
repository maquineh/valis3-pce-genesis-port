import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False

# install the 4-sector VISUAL DEBUGGER overlay (sector 956) at physical $100000
b = open(TRACK, 'rb').read()
off = 0x100000
for s in range(956, 960):
    for byte in b[s * 2352 + 16:s * 2352 + 16 + 2048]:
        emu.mem[off] = byte
        off += 1

emu.cpu.mpr = [0xFF, 0xF8, 0x80, 0x81, 0x82, 0x83, 0x01, 0x00]
emu.cpu.pc = 0x4000
emu.cpu.sp = 0xFF

for n in range(1, 3000001):
    emu.cpu.step()
    if n % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

print('steps', n, 'pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('disc reads:', sorted(set(emu.disc.reads))[:40], 'count', len(emu.disc.reads))
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
print('physical $100000:', emu.mem[0x100000:0x100040].hex(' '))
emu.dump_vram('build/debugger_vram.bin')
emu.dump_cram('build/debugger_cram.bin')
print('dumped build/debugger_vram.bin')
