import sys
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
scr=get('SysCardRAM'); emu.mem[0x100000:0x100000+len(scr)]=scr
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

def run(n,label=''):
    for k in range(n):
        cpu.step()
        if cpu.pc in (0xE3C1,0xE3C4) and not cpu.fI:
            emu.vdc_status|=0x20; cpu.interrupt(0xFFF8)
    if label:
        print('%-22s pc=%04X mpr=%s reads=%d vramw=%d' %
              (label,cpu.pc,' '.join('%02X'%m for m in cpu.mpr),len(disc.reads),len(emu.vram_writes)))

run(300000,'settle')
# try RUN on each of the two possible bits, one at a time
for name,val in (('run_bit2',0x0B),('run_bit3',0xF7),('start_I',0x0E)):
    emu.joy_low=val; run(40000,name+'_press')
    emu.joy_low=0x0F; run(200000,name+'_rel')
emu.joy_high=0x0F; emu.joy_low=0x0F
run(2000000,'after')
print('final pc=%04X reads=%d distinct=%d' % (cpu.pc,len(disc.reads),len(set(disc.reads))))
print('reads:',sorted(set(disc.reads))[-40:])
emu.dump_vram('build/state_input_vram.bin'); emu.dump_cram('build/state_input_cram.bin')
