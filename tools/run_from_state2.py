import sys
sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from extract_state import load, find_var

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc2'
BRAM = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
d = load(STATE)
vram = find_var(d, b'VRAM')
cram = find_var(d, b'color_table')
cdr = find_var(d, b'CDRAM')
base = find_var(d, b'BaseRAM')

rom = open('syscard3.pce', 'rb').read()
disc = ValisDisc()
emu = PCESystem(disc, verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False
emu.mem[0x100000:0x100000 + len(cdr)] = cdr
emu.mem[0x1F0000:0x1F0000 + len(base)] = base
emu.vram[:] = vram
for i in range(512):
    emu.cram[i] = cram[2 * i] | (cram[2 * i + 1] << 8)
sv = open(BRAM, 'rb').read()
emu.mem[0x1EE000:0x1EE000 + len(sv)] = sv
cpu = emu.cpu
# CPU section offsets are the same in both Mednafen states
cpu.pc = d[0x33084] | (d[0x33085] << 8)
cpu.a = d[0x3308C]
cpu.x = d[0x330AE]
cpu.y = d[0x330B5]
cpu.sp = d[0x330BC]
p = d[0x33093]
cpu.fN = (p >> 7) & 1; cpu.fV = (p >> 6) & 1; cpu.fD = (p >> 3) & 1
cpu.fI = (p >> 2) & 1; cpu.fZ = (p >> 1) & 1; cpu.fC = p & 1
cpu.mpr = list(d[0x330FF:0x33107])

print('loaded pc=%04X mpr=%s' % (cpu.pc, ' '.join('%02X' % m for m in cpu.mpr)))

def run(n, label=''):
    for k in range(n):
        cpu.step()
        if cpu.pc in (0xE3C1, 0xE3C4) and not cpu.fI:
            emu.vdc_status |= 0x20
            cpu.interrupt(0xFFF8)
    if label:
        print('%-18s pc=%04X reads=%d vramw=%d' %
              (label, cpu.pc, len(disc.reads), len(emu.vram_writes)))

run(400000, 'settle')
# try START / RUN and directions
for name, lo in (('start_run', 0x0B), ('run_alt', 0xF7), ('left', None)):
    if lo is not None:
        emu.joy_low = lo
    else:
        emu.joy_high = 0x0D  # Left pressed (active low)
    run(40000, name)
    emu.joy_low = 0x0F
    emu.joy_high = 0x0F
    run(300000, name + '_rel')
run(2000000, 'after')
print('final pc=%04X reads=%d distinct=%d' % (cpu.pc, len(disc.reads), len(set(disc.reads))))
print('reads sample:', sorted(set(disc.reads))[:30])
emu.dump_vram('build/state2b_run_vram.bin')
emu.dump_cram('build/state2b_run_cram.bin')
print('vram writes', len(emu.vram_writes))
