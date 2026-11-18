#!/usr/bin/env python3
"""Play the captured STG4A prototype through its exit on Genesis Plus GX."""
import argparse
import ctypes as ct
import json
import re
import struct
import sys
from pathlib import Path
import test_megacd_libretro as harness


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('core','system','cue','artifacts','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args()
    sym=(args.artifacts/'build/stage4a.mmd.elf.sym').read_text()
    def symbol(name):
        m=re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+'+name+r'\s*$',sym,re.M)
        if not m: raise ValueError('missing symbol '+name)
        return int(m.group(1),16)&65535
    p,c,e=(symbol(n) for n in ('stage_player','stage_combat','stage_enemies'))
    core=ct.CDLL(str(args.core.resolve()))
    core.retro_get_memory_data.argtypes=[ct.c_uint]
    core.retro_get_memory_data.restype=ct.c_void_p
    state={'frame':-1,'keys':set(),'skull_hp':set(),'scene5':False,'column_alive':False,'last':None}
    events=[]
    def event(_,frame,button):
        if state['frame']==frame: return button in state['keys']
        state['frame']=frame; keys=set()
        if 600<=frame<604 or 2250<=frame<2254:keys.add(3)
        if 2100 <= frame < 2240 and (frame - 2100) % 20 < 4: keys.add(7)
        addr=core.retro_get_memory_data(2)
        if addr and frame>=2300:
            raw=ct.string_at(addr,65536)
            scene=raw[0xf501]
            if scene==5:state['scene5']=True
            if scene==10:
                x,y=struct.unpack_from('<HH',raw,p)
                ex,ey=struct.unpack_from('<hh',raw,e)
                hp=raw[(e+8)^1]; alive=raw[(e+9)^1]
                col=raw[(e+12+9)^1]
                player_hp=raw[c^1]
                state['skull_hp'].add(hp);state['column_alive'] |= bool(col)
                snap=(hp,alive,player_hp,col)
                if snap!=state['last']:
                    events.append(dict(frame=frame,player=[x,y,player_hp],skull=[ex,ey,hp,alive],column_alive=col))
                    state['last']=snap
                if alive:
                    if x < ex-23:keys.add(7)
                    elif x > ex+1:keys.add(6)
                    if frame%12<2:keys.add(8)
                elif x<224: keys.add(7)
        state['keys']=keys
        return button in keys
    harness.event_pressed=event
    sys.argv=['stg4a-combat-runtime','--core',str(args.core),'--system',str(args.system),
              '--cue',str(args.cue),'--output',str(args.output),'--frames','4500',
              '--script-only','--no-audio-file','--capture','2350','--capture','2420']
    harness.main()
    (args.output/'combat-events.json').write_text(json.dumps(events,indent=2))
    assert state['scene5'],'STG4A exit did not reach STG3A'
    assert {8,4,0}.issubset(state['skull_hp']),state['skull_hp']
    assert state['column_alive'],'column should recover instead of requiring defeat'
    print('PASS: skull 8 -> 4 -> 0, column alive, STG4A exit reached')


if __name__=='__main__':main()
