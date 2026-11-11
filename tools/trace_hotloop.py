import sys
from collections import Counter
sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from pce_state import decompress, parse

STATE='Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
BRAM='Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
v=parse(decompress(STATE)); get=lambda k:v[k][2]
rom=open('syscard3.pce','rb').read()
disc=ValisDisc(); emu=PCESystem(disc,verbose=False)
for i,x in enumerate(rom): emu.mem[i]=x
emu._bios_enabled=False
cdr=get('CDRAM'); emu.mem[0x100000:0x100000+len(cdr)]=cdr
base=get('BaseRAM'); emu.mem[0x1F0000:0x1F0000+len(base)]=base
emu.vram[:]=get('VRAM')
crt=get('color_table')
for i in range(512): emu.cram[i]=crt[2*i]|(crt[2*i+1]<<8)
sv=open(BRAM,'rb').read(); emu.mem[0x1EE000:0x1EE000+len(sv)]=sv
cpu=emu.cpu
cpu.pc=get('PC')[0]|(get('PC')[1]<<8)
cpu.a=get('A')[0]; cpu.x=get('X')[0]; cpu.y=get('Y')[0]; cpu.sp=get('S')[0]
p=get('P')[0]
cpu.fN=(p>>7)&1; cpu.fV=(p>>6)&1; cpu.fD=(p>>3)&1; cpu.fI=(p>>2)&1; cpu.fZ=(p>>1)&1; cpu.fC=p&1
cpu.mpr=list(get('MPR'))

c=Counter(); sample=[]
for k in range(600000):
    pc=cpu.pc
    if not (0xE000 <= pc <= 0xFFFF):
        c[pc]+=1
        if len(sample)<8: sample.append((pc,tuple(cpu.mpr)))
    cpu.step()
    if cpu.pc in (0xE3C1,0xE3C4) and not cpu.fI:
        emu.vdc_status|=0x20; cpu.interrupt(0xFFF8)
print('top non-BIOS PCs:')
for pc,n in c.most_common(20):
    print('  %04X %6d mpr=%s' % (pc,n,' '.join('%02X'%m for m in sample[0][1])))
print('reads',sorted(set(disc.reads))[:20],'vramw',len(emu.vram_writes))
# dump hot region from CDRAM through CPU mapping
pc=c.most_common(1)[0][0]
page=(pc>>13)&7; off=pc&0x1FFF
phys=(cpu.mpr[page]<<13)|off
print('hot pc %04X -> phys %05X cdram_off %05X' % (pc,phys,phys-0x100000))
print('bytes:', ' '.join('%02X'%emu.mem[phys+i] for i in range(32)))
