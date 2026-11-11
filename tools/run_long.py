import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc

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

def run(n, label=''):
    for k in range(n):
        emu.cpu.step()
        if k % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)
    if label:
        print('%s pc=%04X frame=%d reads=%d vram=%d cram=%d mpr=%s' %
              (label, emu.cpu.pc, emu.mem[0x1F2241], len(disc.reads),
               len(emu.vram_writes), sum(1 for c in emu.cram if c),
               ' '.join('%02X' % m for m in emu.cpu.mpr)))

run(5000000, 'title')
emu.mem[0x1F3C00] = 1
emu.joy_low = 0x04
run(30000)
emu.joy_low = 0x0F
emu.joy_high = 0x0F
for i in range(12):
    run(2500000, 't+%2dM' % ((i + 1) * 5 // 2))

emu.dump_vram('build/long_vram.bin')
emu.dump_cram('build/long_cram.bin')
emu.dump_bat('build/long_bat.bin') if hasattr(emu, 'dump_bat') else None
print('dumped build/long_vram.bin')
