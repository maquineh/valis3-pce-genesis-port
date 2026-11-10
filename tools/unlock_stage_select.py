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

trace = []

def run(n):
    for k in range(n):
        trace.append(emu.cpu.pc)
        if len(trace) > 100:
            trace.pop(0)
        emu.cpu.step()
        if k % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)

# boot to the title screen
run(3000000)
print('title: pc=%04X mpr=%s reads=%d' %
      (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr), len(emu.disc.reads)))
before = set(emu.disc.reads)

# Hold Up+Left (directions) + I+II (buttons)
emu.joy_high = 0x06       # Up+Left active-low
emu.joy_low = 0x0C        # I+II active-low
run(120000)               # ~60 frames
# Press RUN while keeping the combo held
emu.joy_low = 0x04        # I+II+Run
run(30000)                # ~15 frames
# Release RUN, keep the combo
emu.joy_low = 0x0C
run(30000)
# Release everything
emu.joy_high = 0x0F
emu.joy_low = 0x0F
try:
    run(2000000)
except RuntimeError as e:
    print('CPU stopped:', e)
    print('reads at stop:', sorted(set(emu.disc.reads) - before))
    print('pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
    print('last pcs:', ' '.join('%04X' % x for x in trace))
    print('RAM200:', emu.mem[0x1F0200:0x1F0240].hex(' '))
    from disasm6280 import disasm_one
    off = 0x1F0200
    for _ in range(20):
        txt, ln = disasm_one(emu.mem, off)
        print('  $%04X: %s' % (0x0200 + (off - 0x1F0200), txt))
        off += ln

print('after combo: pc=%04X mpr=%s' %
      (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('new reads:', sorted(set(emu.disc.reads) - before)[:40])
print('all reads:', len(emu.disc.reads), 'distinct', len(set(emu.disc.reads)))
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
emu.dump_vram('build/stage_select_vram.bin')
emu.dump_cram('build/stage_select_cram.bin')
print('dumped build/stage_select_vram.bin')
