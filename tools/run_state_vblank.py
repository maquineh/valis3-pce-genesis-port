import sys
sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
BRAM = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
buf = decompress(STATE); v = parse(buf); get=lambda k: v[k][2]

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

N=int(sys.argv[1]) if len(sys.argv)>1 else 3000000
inject=0
for k in range(N):
    try:
        cpu.step()
    except RuntimeError as e:
        print('stop',k,e); break
    # VBlank only when the game is parked in the BIOS vsync wait
    if cpu.pc in (0xE3C1,0xE3C4) and not cpu.fI:
        emu.vdc_status |= 0x20
        cpu.interrupt(0xFFF8)
        inject+=1
    if k%500000==0 and k:
        print('  %8d pc=%04X mpr=%s reads=%d vramw=%d irq=%d' %
              (k,cpu.pc,' '.join('%02X'%m for m in cpu.mpr),len(disc.reads),len(emu.vram_writes),inject))

print('final pc=%04X mpr=%s sp=%02X irq=%d' % (cpu.pc,' '.join('%02X'%m for m in cpu.mpr),cpu.sp,inject))
print('reads',len(disc.reads),'distinct',len(set(disc.reads)),'last',sorted(set(disc.reads))[-24:])
emu.dump_vram('build/state_vblank_vram.bin'); emu.dump_cram('build/state_vblank_cram.bin')
print('vram writes',len(emu.vram_writes))
