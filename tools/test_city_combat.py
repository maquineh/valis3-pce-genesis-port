"""Play cartridge-derived combat on the built disc and inspect real VDP tiles."""
import argparse
import ctypes as ct
from pathlib import Path
import re
import struct
import sys

import test_megacd_libretro as harness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('core','system','cue','artifacts','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    symbols = (args.artifacts/'build/stage1.mmd.elf.sym').read_text()
    def symbol(name):
        return int(re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+'+name+r'$',symbols,re.M)[1],16)&65535
    offs = {k:symbol(k) for k in ('room','xpos','enemies','charge','attack','hurt','wave_life','hp')}
    core = ct.CDLL(str(args.core.resolve()))
    core.retro_get_memory_data.argtypes = [ct.c_uint]
    core.retro_get_memory_data.restype = ct.c_void_p
    core.retro_serialize_size.restype = ct.c_size_t
    core.retro_serialize.argtypes = [ct.c_void_p,ct.c_size_t]
    blob=(Path(__file__).resolve().parents[1]/'game/res/gfx/city_combat.bin').read_bytes()
    vbase, count=struct.unpack_from('>2H',blob)
    tab = 6+count*32
    bars = tab+2*struct.unpack_from('>H',blob,tab-2)[0]
    pose_tiles=[]
    for offset in struct.unpack_from('>17H',blob,tab):
        cursor=tab+offset
        pieces=struct.unpack_from('>H',blob,cursor)[0]
        pose_tiles.append(tuple(struct.unpack_from('>H',blob,cursor+6+8*i)[0]&2047 for i in range(pieces)))
    poses=set()
    charges=set()
    life=set()
    health=set()
    had_damage=False
    previous=-1
    roof_start=None
    keys=set()
    def event(events,f,b):
        nonlocal previous,roof_start,had_damage
        if f==previous:return b in keys
        previous=f
        keys.clear()
        if 600<=f<604 or 2250<=f<2254:keys.add(3)
        if f<2350:return b in keys
        ram=ct.string_at(core.retro_get_memory_data(2),65536)
        word=lambda n:struct.unpack_from('<H',ram,n)[0]
        byte=lambda k:ram[offs[k]^1]
        if ram[0xf501]!=2:return False
        room=word(offs['room'])
        if room<2:keys.add(7)
        if room!=3:return b in keys
        if roof_start is None:roof_start=f
        t=f-roof_start
        if t in (12,100):keys.add(8)
        if t==90:keys.add(0)
        had_damage |= byte('hurt')!=0
        if t>160:
            target=word(offs['enemies'])
            x=word(offs['xpos'])
            if x < target-(20 if had_damage else 0):keys.add(7)
            if had_damage and t%30==0:keys.add(8)
        if t<3 or t>1050:return b in keys
        size=core.retro_serialize_size()
        buf=ct.create_string_buffer(size)
        assert core.retro_serialize(buf,size)
        raw=buf.raw
        assert raw[:16]==b'GENPLUS-GX 1.7.6'
        reg=raw[0x22525:0x22545]
        window=0x12425+reg[3]*1024
        cells=tuple(v for row in (2,3) for v in struct.unpack_from('<11H',raw,window+2*(row*32+5)))
        hp=byte('hp')
        health_cells=struct.unpack_from('<12H',raw,window+8)
        empty_tile=0x8000|(vbase-1)
        if hp==24 and len(set(health_cells))==1 and health_cells[0]!=empty_tile:
            health.add(24)
        if hp==22 and health_cells[-1]==empty_tile and len(set(health_cells[:-1]))==1:
            # Read the graphic itself as well as its tilemap entry.
            addr=0x12425+(vbase-1)*32
            pattern=struct.pack('>16H',*struct.unpack_from('<16H',raw,addr))
            if pattern==blob[-32:]:health.add(22)
        ch=byte('charge')
        if cells==struct.unpack_from('>22H',blob,bars+44*ch):
            charges.add(ch)
        link=0
        ids=[]
        for _ in range(64):
            y,shape,tile,x=struct.unpack_from('<4H',raw,0x12425+reg[5]*512+8*link)
            if y>128 and x:ids.append(tile&2047)
            link=shape&127
            if not link:break
        for i,pattern in enumerate(pose_tiles):
            if any(tuple(ids[j:j+len(pattern)])==pattern for j in range(len(ids))):
                poses.add(i)
        if byte('wave_life') and 11 in poses:life.add(byte('wave_life'))
        return b in keys
    harness.event_pressed=event
    sys.argv=['combat','--core',str(args.core),'--system',str(args.system),'--cue',str(args.cue),
              '--output',str(args.output),'--script-only','--no-audio-file','--frames','8100']
    harness.main()
    print('HP states:',sorted(health),'Observed VDP charge states:',len(charges),'of 43; SAT poses:',sorted(poses),'wave:',sorted(life),flush=True)
    assert charges==set(range(43)), ('missing charge states',set(range(43))-charges)
    assert poses==set(range(17)), ('missing native poses',set(range(17))-poses)
    assert life==set(range(1,10))
    assert health=={24,22}, ('HP and native HUD tiles',health)


if __name__=='__main__':
    main()
