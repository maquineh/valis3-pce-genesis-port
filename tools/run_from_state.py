"""Load a Mednafen PCE state into the project emulator and continue running."""
import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
BRAM = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'

buf = decompress(STATE)
v = parse(buf)
get = lambda k: v[k][2]


def u16(b):
    return b[0] | (b[1] << 8)


rom = open('syscard3.pce', 'rb').read()
disc = ValisDisc()
emu = PCESystem(disc, verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False

# Super CD / System Card RAM (192 KiB) at physical $100000
scr = get('SysCardRAM')
emu.mem[0x100000:0x100000 + len(scr)] = scr
# 8 KiB work RAM
base = get('BaseRAM')
emu.mem[0x1F0000:0x1F0000 + len(base)] = base
# VRAM / CRAM
emu.vram[:] = get('VRAM')
crt = get('color_table')
for i in range(512):
    emu.cram[i] = crt[2 * i] | (crt[2 * i + 1] << 8)
# BRAM
sv = open(BRAM, 'rb').read()
emu.mem[0x1EE000:0x1EE000 + len(sv)] = sv

# CPU registers
cpu = emu.cpu
cpu.pc = u16(get('PC'))
cpu.a = get('A')[0]
cpu.x = get('X')[0]
cpu.y = get('Y')[0]
cpu.sp = get('S')[0]
p = get('P')[0]
cpu.fN = (p >> 7) & 1
cpu.fV = (p >> 6) & 1
cpu.fD = (p >> 3) & 1
cpu.fI = (p >> 2) & 1
cpu.fZ = (p >> 1) & 1
cpu.fC = p & 1
cpu.mpr = list(get('MPR'))
# VDC scroll/cached registers
if 'BG_XOffset' in v:
    emu.regs[7] = v['BG_XOffset'][2][0]
if 'BG_YOffset' in v:
    emu.regs[8] = v['BG_YOffset'][2][0]

print('loaded PC=%04X MPR=%s VRAM nonzero=%d CRAM nonzero=%d' %
      (cpu.pc, ' '.join('%02X' % m for m in cpu.mpr),
       sum(1 for x in emu.vram if x), sum(1 for x in emu.cram if x)))
print('reads before', len(disc.reads))
steps = int(sys.argv[1]) if len(sys.argv) > 1 else 2000000
for k in range(steps):
    try:
        emu.cpu.step()
    except RuntimeError as e:
        print('CPU stopped at step', k, e)
        break
    if k % 2000 == 0:
        emu.vdc_status |= 0x20
        if not emu.cpu.fI:
            emu.cpu.interrupt(0xFFF8)
    if k % 250000 == 0 and k:
        print('  %8d pc=%04X reads=%d vramw=%d' %
              (k, emu.cpu.pc, len(disc.reads), len(emu.vram_writes)))
print('final pc=%04X mpr=%s sp=%02X a=%02X x=%02X y=%02X' %
      (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr),
       emu.cpu.sp, emu.cpu.a, emu.cpu.x, emu.cpu.y))
print('reads', len(disc.reads), 'distinct', len(set(disc.reads)),
      'last', sorted(set(disc.reads))[-20:])
emu.dump_vram('build/state_run_vram.bin')
emu.dump_cram('build/state_run_cram.bin')
print('VRAM writes', len(emu.vram_writes))
