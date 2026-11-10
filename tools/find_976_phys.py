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

def step(n, irq=2000):
    for _ in range(n):
        emu.cpu.step()
        if emu.steps % irq == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)
        emu.steps += 1

# simple step loop with own counter
def run(n, stop_4202=False):
    for k in range(n):
        emu.cpu.step()
        if k % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)
        if stop_4202 and 4202 in emu.disc.reads and emu.disc.reads[-1] == 4202:
            return k + 1
    return n

run(3000000)
emu.cpu.pc = 0x4167
emu.mem[0x1F0000 + 0x3C00] = 0
r = run(12000000, stop_4202=True)
print('976 read done at', r, 'pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
needle = b'VALIS III ACT'
idx = emu.mem.find(needle)
print('string at physical', hex(idx) if idx >= 0 else 'NOT FOUND')
if idx >= 0:
    print('bytes:', emu.mem[idx-2:idx+40].hex(' '))
    print('mpr mapping for logical $4000:', hex(emu.cpu.mpr[2] << 13))
    # find all occurrences
    i = 0
    while True:
        i = emu.mem.find(needle, i)
        if i < 0: break
        print('  occurrence at', hex(i))
        i += 1
print('new reads', sorted(set(emu.disc.reads))[-20:])
