#!/usr/bin/env python3
"""Check the STG4A enemies in a matching Genesis Plus GX native build."""
import argparse
import ctypes as ct
import re
import struct
import sys
from pathlib import Path
import test_megacd_libretro as harness


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('core','system','cue','artifacts','output'):
        ap.add_argument('--'+name, type=Path, required=True)
    ap.add_argument('--hit-test', action='store_true',
                    help='place player on a projectile to verify damage in the running core')
    args=ap.parse_args()
    symbols=(args.artifacts/'build/stage4a.mmd.elf.sym').read_text()
    def symbol(name):
        m=re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+'+name+r'\s*$',symbols,re.M)
        if not m: raise ValueError('missing symbol '+name)
        return int(m.group(1),16)&0xffff
    shots, motion = symbol('column_shots'), symbol('skull_motion')
    player, combat, enemies = (symbol(n) for n in ('stage_player','stage_combat','stage_enemies'))
    core=ct.CDLL(str(args.core.resolve()))
    core.retro_get_memory_data.argtypes=[ct.c_uint]
    core.retro_get_memory_data.restype=ct.c_void_p
    observed=set()
    positions=set()
    hit={'frame':None, 'hp':None, 'confirmed':False, 'confirm_frame':None,
         'invulnerability':None, 'stable':False}
    def event(events,frame,button):
        if frame>=2260:
            addr=core.retro_get_memory_data(2)
            if addr:
                raw=ct.string_at(addr,65536)
                if raw[0xf501]==10:
                    positions.add(struct.unpack_from('<hh',raw,motion))
                    if hit['frame'] is not None and frame>hit['frame']:
                        if not hit['confirmed'] and raw[combat^1] == hit['hp']-3:
                            hit['confirmed']=True; hit['confirm_frame']=frame
                            hit['invulnerability']=raw[(combat+1)^1]
                        if (hit['confirmed'] and frame>=hit['confirm_frame']+10 and
                            raw[combat^1]==hit['hp']-3 and raw[(combat+1)^1]>0):
                            hit['stable']=True
                    for i in range(6):
                        a=shots+i*8
                        x,y,vx=struct.unpack_from('<hhh',raw,a)
                        if raw[(a+6)^1]:
                            observed.add((y,vx))
                            if (args.hit_test and hit['frame'] is None and
                                frame>=2440 and not raw[(enemies+9)^1] and
                                200<=x//16<=232 and 16<=y//16<=160):
                                hit['frame'],hit['hp']=frame,raw[combat^1]
                                ct.memmove(addr+player,struct.pack('<HH',x//16-8,y//16-8),4)
                                ct.memset(addr+((combat+1)^1),0,1)
        return ((button==3 and (600<=frame<604 or 2250<=frame<2254)) or
                (button == 7 and 2100 <= frame < 2240 and (frame - 2100) % 20 < 4) or
                (button==8 and 2340<=frame<2440 and frame%20<2))
    harness.event_pressed=event
    sys.argv=['stg4a-enemy-runtime','--core',str(args.core),'--system',str(args.system),
              '--cue',str(args.cue),'--output',str(args.output),'--frames','3000',
              '--script-only','--no-audio-file','--capture','2330','--capture','2410']
    harness.main()
    expected={(108*16,32),(124*16,-32),(140*16,32)}
    if not expected.issubset(observed):
        raise AssertionError('missing shot origins/directions: %s; observed %s' % (expected-observed,observed))
    if len({y for x,y in positions})<2 or len({x for x,y in positions})<2:
        raise AssertionError('skull did not move on both axes: %s' % (positions,))
    if args.hit_test and not (hit['confirmed'] and hit['invulnerability']==90 and hit['stable']):
        raise AssertionError('projectile hit did not reduce HP: %s' % hit)
    print('PASS: all three projectile paths and skull movement in both axes')
    if args.hit_test: print('PASS: projectile caused 3 HP damage and 90-update invulnerability')


if __name__=='__main__': main()
