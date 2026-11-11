import sys
from collections import Counter

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from disasm6280 import disasm_one

SAVE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
rom = open('syscard3.pce', 'rb').read()
disc = ValisDisc()
emu = PCESystem(disc, verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
sv = open(SAVE, 'rb').read()
emu.mem[0x1EE000:0x1EE000 + len(sv)] = sv
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF


def run(n, collect=None):
    for k in range(n):
        if collect is not None:
            collect.append((emu.cpu.pc, tuple(emu.cpu.mpr)))
        emu.cpu.step()
        if k % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)


run(5000000)
emu.mem[0x1F3C00] = 1
emu.joy_low = 0x04
run(30000)
emu.joy_low = 0x0F
emu.joy_high = 0x0F
run(4000000)

# now sample a long stretch with no injected interrupt
trace = []
for k in range(200000):
    trace.append((emu.cpu.pc, tuple(emu.cpu.mpr)))
    emu.cpu.step()

c = Counter(pc for pc, m in trace)
print('top PCs:', [(hex(p), n) for p, n in c.most_common(12)])
print('tail:', ' '.join('%04X' % pc for pc, m in trace[-24:]))
mp = trace[-1][1]
print('mpr:', ' '.join('%02X' % m for m in mp), 'sp=%02X' % emu.cpu.sp)

phys = lambda a: (mp[(a >> 13) & 7] << 13) | (a & 0x1FFF)
p = c.most_common(1)[0][0]
pa = phys(p)
print('hot pc %04X -> phys %05X' % (p, pa))
for off in range(pa - 8, pa + 24, 1):
    pass
off = pa - 8
while off < pa + 32:
    txt, ln = disasm_one(emu.mem, off)
    mark = ' <==' if off == pa else ''
    print('  %05X: %-28s%s' % (off, txt, mark))
    off += ln

print('\nRAM 0x2000-0x2100 (loaded track6 program):')
for r in range(0x1F2000, 0x1F2100, 16):
    print('  %04X %s' % (r - 0x1F0000, ' '.join('%02X' % emu.mem[r + i] for i in range(16))))
