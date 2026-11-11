import sys
sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
BRAM = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
buf = decompress(STATE); v = parse(buf)
get = lambda k: v[k][2]

rom = open('syscard3.pce', 'rb').read()
disc = ValisDisc()
emu = PCESystem(disc, verbose=False)
for i, x in enumerate(rom): emu.mem[i] = x
emu._bios_enabled = False
scr = get('SysCardRAM'); emu.mem[0x100000:0x100000+len(scr)] = scr
base = get('BaseRAM'); emu.mem[0x1F0000:0x1F0000+len(base)] = base
emu.vram[:] = get('VRAM')
crt = get('color_table')
for i in range(512): emu.cram[i] = crt[2*i] | (crt[2*i+1] << 8)
sv = open(BRAM,'rb').read(); emu.mem[0x1EE000:0x1EE000+len(sv)] = sv
cpu = emu.cpu
cpu.pc = get('PC')[0] | (get('PC')[1]<<8)
cpu.a=get('A')[0]; cpu.x=get('X')[0]; cpu.y=get('Y')[0]; cpu.sp=get('S')[0]
p=get('P')[0]
cpu.fN=(p>>7)&1; cpu.fV=(p>>6)&1; cpu.fD=(p>>3)&1; cpu.fI=(p>>2)&1
cpu.fZ=(p>>1)&1; cpu.fC=p&1
cpu.mpr=list(get('MPR'))

print('stack at 1F01F8:', ' '.join('%02X'%emu.mem[0x1F01F8+i] for i in range(8)))
sp=cpu.sp
print('return candidates:', ['%04X'%(emu.mem[0x1F0000|((sp+1+i)&0xFF)] | (emu.mem[0x1F0000|((sp+2+i)&0xFF)]<<8)) for i in range(0,8,2)])
print('start pc=%04X sp=%02X fI=%d' % (cpu.pc,cpu.sp,cpu.fI))

last=[]
for k in range(300000):
    last.append((cpu.pc, tuple(cpu.mpr)))
    if len(last)>40: last.pop(0)
    try:
        cpu.step()
    except RuntimeError as e:
        print('stop at',k,e); break
    if k % 2000 == 0:
        emu.vdc_status |= 0x20
        if not cpu.fI: cpu.interrupt(0xFFF8)
    if k % 50000 == 0:
        print('  %6d pc=%04X mpr=%s reads=%d' % (k,cpu.pc,' '.join('%02X'%m for m in cpu.mpr),len(disc.reads)))

print('final pc=%04X mpr=%s sp=%02X reads=%d' % (cpu.pc,' '.join('%02X'%m for m in cpu.mpr),cpu.sp,len(disc.reads)))
print('last pcs:', ' '.join('%04X'%p for p,m in last[-30:]))
print('last mprs:', [' '.join('%02X'%x for x in m) for p,m in last[-6:]])
if disc.reads:
    print('reads:', sorted(set(disc.reads))[:40])
