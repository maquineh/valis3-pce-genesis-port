import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

SAVE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
rom = open('syscard2.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x

# install startup overlay from track-relative sector 8 (4 sectors)
b = open(TRACK, 'rb').read()
off = 0x100000
for s in range(8, 12):
    for byte in b[s * 2352 + 16:s * 2352 + 16 + 2048]:
        emu.mem[off] = byte
        off += 1
# BRAM save at MPR4=$F7 window
sv = open(SAVE, 'rb').read()
emu.mem[0x1EE000:0x1EE000 + len(sv)] = sv

emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0x80, 0x81, 0x82, 0x83, 0x01, 0x00]
emu.cpu.pc = 0x4000
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
    emu.mem[0x1F3C00] = 1
    emu.joy_low = 0x04
    run(30000)
    emu.joy_low = 0x0F
    run(10000000)
except RuntimeError as e:
    print('CPU stopped:', e)
    print('pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
    print('last pcs:', ' '.join('%04X' % x for x in trace[-40:]))

print('final pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('new reads:', sorted(set(emu.disc.reads) - before)[:40])
print('all reads count', len(emu.disc.reads), 'distinct', len(set(emu.disc.reads)))
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
emu.dump_vram('build/v2_save_vram.bin')
emu.dump_cram('build/v2_save_cram.bin')
print('dumped build/v2_save_vram.bin')
