import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK
from disasm6280 import disasm_one

rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF

trace = []
def run(n):
    for k in range(n):
        trace.append(emu.cpu.pc)
        if len(trace) > 200:
            trace.pop(0)
        emu.cpu.step()
        if k % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)

run(3000000)
emu.joy_high = 0x06
emu.joy_low = 0x0C
run(120000)
emu.joy_low = 0x04
run(30000)
emu.joy_low = 0x0C
run(30000)
emu.joy_high = 0x0F
emu.joy_low = 0x0F

hit = False
for k in range(2000000):
    if emu.cpu.pc == 0x0194:
        hit = True
        break
    trace.append(emu.cpu.pc)
    if len(trace) > 200:
        trace.pop(0)
    emu.cpu.step()
    if k % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

print('hit0194', hit, 'steps', k, 'pc=%04X mpr=%s sp=%02X' %
      (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr), emu.cpu.sp))
print('last 50 pcs:', ' '.join('%04X' % x for x in trace[-50:]))
sp = emu.cpu.sp
st = [emu.read(0x100 | ((sp + i + 1) & 0xFF)) for i in range(16)]
print('stack:', ' '.join('%02X' % b for b in st))
print('ret candidates:', ['%04X' % (st[i] | (st[i+1] << 8)) for i in range(0, 14, 2)])
prev = trace[-1]
print('prev pc=%04X bytes=' % prev, emu.read(max(0, prev-3)) if False else '')
# dump bytes around prev using logical read through the CPU mapping
for a in range(prev - 4, prev + 4):
    print('  $%04X = %02X' % (a, emu.read(a & 0xFFFF)))
# current bytes at $0180-$01A0 and $0200
print('RAM0180:', ' '.join('%02X' % emu.read(0x180 + i) for i in range(0x30)))
print('reads:', sorted(set(emu.disc.reads))[:30])
