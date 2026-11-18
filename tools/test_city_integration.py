"""Play the Genesis city on the built Mega CD and check combat, gaps and exit."""
import argparse
import ctypes as ct
import json
from pathlib import Path
import re
import struct
import sys

import test_megacd_libretro as harness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('core','system','cue','artifacts','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    symbols=(args.artifacts/'build/stage1.mmd.elf.sym').read_text()
    def symbol(name):
        return int(re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+'+name+r'$',symbols,re.M)[1],16)&65535
    offsets={key:symbol(key) for key in ('room','xpos','feet','camera','enemies','hp','attack','facing','late_foes','boss_hp','boss_x','boss_feet')}
    core=ct.CDLL(str(args.core.resolve()))
    core.retro_get_memory_data.argtypes=[ct.c_uint]
    core.retro_get_memory_data.restype=ct.c_void_p
    last=-1
    keys=set()
    rooms=[]
    trace=[]
    victories=set()
    jumped=False
    palette_checks=set()
    core.retro_serialize_size.restype=ct.c_size_t
    core.retro_serialize.argtypes=[ct.c_void_p,ct.c_size_t]
    core.retro_serialize.restype=ct.c_bool
    scroll_checks=set()
    scroll_failures=[]
    transition_deltas=[]
    previous_screen=None
    previous_room=None
    room_age=0
    brown_dead=set()
    hold_until=0
    palettes=[]
    for name in ('street','meeting','fall','roof','late','boss'):
        asset=(Path(__file__).resolve().parents[1]/'game/res/gfx'/('city_'+name+'.bin')).read_bytes()
        palettes.append(struct.unpack_from('>64H',asset,6))
    def event(events,f,button):
        nonlocal last,keys,jumped,previous_room,previous_screen,hold_until,room_age
        if f==last:return button in keys
        last=f
        keys=set()
        if 600<=f<604 or 2250<=f<2254:keys.add(3)
        if f>=2350:
            data=ct.string_at(core.retro_get_memory_data(2),65536)
            word=lambda o:struct.unpack_from('<H',data,o)[0]
            byte=lambda o:data[o^1]
            scene=data[0xf501]
            if scene==3 and rooms and rooms[-1]!=6:rooms.append(6)
            if scene==2:
                r,x,y=(word(offsets[k]) for k in ('room','xpos','feet'))
                if not rooms or rooms[-1]!=r:rooms.append(r)
                cam=struct.unpack_from('<h',data,offsets['camera'])[0]
                screen=x-cam
                if previous_room==3 and r==4:
                    transition_deltas.append(screen-previous_screen)
                    assert abs(screen-previous_screen)<=2,('roof seam',previous_screen,screen)
                room_age=room_age+1 if previous_room==r else 0
                previous_room,previous_screen=r,screen
                # Check the hardware CRAM, not the BIOS cache. An interrupt
                # during a map upload once left the rooftop almost black.
                if f%30==0 and r not in palette_checks and 0<=r<=5:
                    size=core.retro_serialize_size()
                    buf=ct.create_string_buffer(size)
                    assert core.retro_serialize(buf,size)
                    assert buf.raw[:16]==b'GENPLUS-GX 1.7.6'
                    cram=struct.unpack_from('<64H',buf.raw,0x22425)
                    native=tuple((v&7)*2+((v>>3)&7)*32+((v>>6)&7)*512 for v in cram)
                    if native==palettes[r]:palette_checks.add(r)
                if f%30==0 and r in (4,5) and room_age>6 and x>80:
                    size=core.retro_serialize_size();buf=ct.create_string_buffer(size)
                    assert core.retro_serialize(buf,size)
                    vram=struct.unpack_from('<32768H',buf.raw,0x12425)
                    regs=buf.raw[0x22525:0x22545]
                    value=vram[regs[13]*512+24*16+1]
                    expected=(-((cam+515)//4) if r==4 else -446)&65535
                    if value!=expected:scroll_failures.append((f,r,cam,value,expected))
                    scroll_checks.add(r)
                if r<=1:keys.add(7)
                foes=[]
                if r==3:
                    for i in range(2):
                        off=offsets['enemies']+16*i
                        foes.append((word(off),word(off+2),byte(off+12)))
                        if not foes[-1][2]:victories.add(i)
                    live=[foe for foe in foes if foe[2]]
                    target=live[0][0]-60 if live else 580
                    if x<target:keys.add(7)
                    elif x>target+30:keys.add(6)
                    if live and abs(live[0][0]-x)<80 and f%57<2:keys.add(8)
                    if (237<=x<=256 and y==192) or (466<=x<=478 and y==176):
                        keys.add(0)
                    if x>=512 and y<=160:jumped=True
                if r==4:
                    for i in range(7):
                        off=offsets['late_foes']+14*i
                        foes.append((word(off),word(off+2),byte(off+11),byte(off+10),byte(off+12)))
                    if x<64 and foes[0][2]:brown_dead.clear()
                    for i,foe in enumerate(foes):
                        if foe[3]==1 and not foe[2] and i not in brown_dead:
                            brown_dead.add(i);hold_until=f+100
                    live=[foe for foe in foes if foe[2]]
                    target=(392 if live[0][0]<600 else 900) if live and live[0][3]==2 else (110 if live[0][0]<400 else 624) if live and live[0][3]==0 else live[0][0]-(28 if live[0][3]==1 and live[0][0]<400 else 64) if live else 1250
                    if x<target:keys.add(7)
                    elif x>target+(12 if live and live[0][3]==1 else 8):keys.add(6)
                    if live and abs(live[0][0]-x)<80 and f%57<2:keys.add(8)
                    if live and live[0][3]==1 and y==live[0][1] and abs(x-target)<8 and 85<=live[0][4]<=88:keys.add(0)
                    if live and 0<=x-target<=(12 if live[0][3]==1 else 8):
                        desired=int(live[0][0]>x)
                        if byte(offsets['facing'])!=desired:
                            keys.discard(6);keys.discard(7)
                            keys.add(7 if desired else 6)
                    if live and live[0][3]==1 and live[0][0]<400 and y==live[0][1] and abs(x-target)<8 and 75<=live[0][4]<=78:keys.add(0)
                    if target>x+8 and any(edge<=x<=edge+5 and y==ground for edge,ground in ((256,192),(352,176),(448,160),(544,160))):keys.add(0)
                    if live and live[0][3]==2 and target==900 and abs(x-target)<14 and f%50<2:keys.add(0)
                    if f<hold_until:keys.clear()
                if r==5:
                    bx=word(offsets['boss_x']);by=word(offsets['boss_feet']);bh=byte(offsets['boss_hp'])
                    foes=[(bx,by,bh)]
                    # Stay across the arena and send charged sword waves.
                    target=bx-34 if bx>=128 else bx+34
                    if x<target:keys.add(7)
                    elif x>target+6:keys.add(6)
                    else:
                        if bx>x:keys.add(7)
                        else:keys.add(6)
                    if f%18<2:keys.add(8)
                    if by<145 and f%50<2:keys.add(0)
                if f%20==0:trace.append((f,r,x,y,foes,byte(offsets['hp'])))
        return button in keys
    harness.event_pressed=event
    sys.argv=['game','--core',str(args.core),'--system',str(args.system),'--cue',str(args.cue),
              '--frames','16000','--script-only','--output',str(args.output),'--no-audio-file']
    for f in range(2350,16000,200):sys.argv+=['--capture',str(f)]
    harness.main()
    (args.output/'play.json').write_text(json.dumps(trace))
    (args.output/'visual-checks.json').write_text(json.dumps(dict(scroll_rooms=sorted(scroll_checks),roof_seam_deltas=transition_deltas,scroll_failures=scroll_failures)))
    print('rooms',rooms,'defeated',sorted(victories),'cleared gap',jumped,flush=True)
    assert rooms==[0,1,2,3,4,5,6] and victories=={0,1} and jumped
    assert palette_checks=={0,1,2,3,4,5}, ('hardware palettes',palette_checks)
    assert scroll_checks=={4,5} and transition_deltas and all(abs(v)<=2 for v in transition_deltas),('scroll/seam',scroll_checks,transition_deltas)
    assert not scroll_failures,('hardware scroll',scroll_failures[:5])


if __name__=='__main__':
    main()

