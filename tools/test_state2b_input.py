import sys
sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from extract_state import load, find_var

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc2'
BRAM = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
d = load(STATE)
vram = find_var(d, b'VRAM'); cram = find_var(d, b'color_table')
cdr = find_var(d, b'CDRAM'); base = find_var(d, b'BaseRAM')
rom = open('syscard3.pce', 'rb').read()
disc = ValisDisc(); emu = PCESystem(disc, verbose=False)
for i, x in enumerate(rom): emu.mem[i] = x
emu._bios_enabled = False
emu.mem[0x100000:0x100000 + len(cdr)] = cdr
emu.mem[0x1F0000:0x1F0000 + len(base)] = base
emu.vram[:] = vram
for i in range(512): emu.cram[i] = cram[2*i] | (cram[2*i+1] << 8)
sv = open(BRAM,'rb').read(); emu.mem[0x1EE000:0x1EE000+len(sv)] = sv
cpu = emu.cpu
cpu.pc = d[0x33084] | (d[0x33085] << 8)
cpu.a = d[0x3308C]; cpu.x = d[0x330AE]; cpu.y = d[0x330B5]; cpu.sp = d[0x330BC]
p = d[0x33093]
cpu.fN=(p>>7)&1; cpu.fV=(p>>6)&1; cpu.fD=(p>>3)&1; cpu.fI=(p>>2)&1; cpu.fZ=(p>>1)&1; cpu.fC=p&1
cpu.mpr = list(d[0x330FF:0x33107])

def run(n):
    for k in range(n):
        cpu.step()
        if cpu.pc in (0xE3C1,0xE3C4) and not cpu.fI:
            emu.vdc_status |= 0x20; cpu.interrupt(0xFFF8)

def pad():
    return (emu.mem[0x1F0228], emu.mem[0x1F022D], emu.mem[0x1F2241] if False else 0)

run(200000)
print('settle pc=%04X pad2228=%02X 222D=%02X reads=%d vramw=%d' %
      (cpu.pc, emu.mem[0x1F0228], emu.mem[0x1F022D], len(disc.reads), len(emu.vram_writes)))
tests = [
    ('run', 0x0B, 0x0F),
    ('left', 0x0F, 0x07),
    ('right', 0x0F, 0x0D),
    ('up', 0x0F, 0x0E),
    ('down', 0x0F, 0x0B),
    ('I', 0x0E, 0x0F),
    ('II', 0x0D, 0x0F),
]
for name, lo, hi in tests:
    emu.joy_low = lo; emu.joy_high = hi
    run(30000)
    print('%-6s pc=%04X pad2228=%02X 222D=%02X reads=%d vramw=%d' %
          (name, cpu.pc, emu.mem[0x1F0228], emu.mem[0x1F022D], len(disc.reads), len(emu.vram_writes)))
    emu.joy_low = 0x0F; emu.joy_high = 0x0F
    run(30000)
print('final pc=%04X reads=%d vramw=%d' % (cpu.pc, len(disc.reads), len(emu.vram_writes)))
