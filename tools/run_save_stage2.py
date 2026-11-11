import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

SAVE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
# PCE BRAM window at MPR4=$F7 -> physical $1EE000
sv = open(SAVE, 'rb').read()
emu.mem[0x1EE000:0x1EE000 + len(sv)] = sv
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF

trace = []
def run(n):
    for k in range(n):
        trace.append(emu.cpu.pc)
        if len(trace) > 100: trace.pop(0)
        emu.cpu.step()
        if k % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)

try:
    run(5000000)
    print('title pc=%04X mpr=%s reads=%d' %
          (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr), len(emu.disc.reads)))
    before = set(emu.disc.reads)
    # select CONTINUE and press RUN
    emu.mem[0x1F3C00] = 1
    emu.joy_low = 0x04
    run(30000)
    emu.joy_low = 0x0F
    run(8000000)
except RuntimeError as e:
    print('CPU stopped:', e)
    print('pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
    print('last pcs:', ' '.join('%04X' % x for x in trace[-40:]))

print('final pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('new reads:', sorted(set(emu.disc.reads) - before)[:40])
print('all reads count', len(emu.disc.reads), 'distinct', len(set(emu.disc.reads)))
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
emu.dump_vram('build/save2_vram.bin')
emu.dump_cram('build/save2_cram.bin')
print('dumped build/save2_vram.bin')
