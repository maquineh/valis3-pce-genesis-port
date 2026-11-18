#!/usr/bin/env python3
"""Drive the column's damage threshold and recovery inside the MD core."""
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
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--contact-test',action='store_true')
    a=ap.parse_args()
    sym=(a.artifacts/'build/stage4a.mmd.elf.sym').read_text()
    def symbol(n):
        m=re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+'+n+r'\s*$',sym,re.M)
        if not m: raise ValueError('missing symbol '+n)
        return int(m.group(1),16)&65535
    enemies,combat,rec,timer=(symbol(n) for n in
                               ('stage_enemies','stage_combat','column_recovery','column_timer'))
    player,shots=symbol('stage_player'),symbol('column_shots')
    core=ct.CDLL(str(a.core.resolve()))
    core.retro_get_memory_data.argtypes=[ct.c_uint]
    core.retro_get_memory_data.restype=ct.c_void_p
    trace=[]; injected=False; last_frame=-1
    def event(_,frame,button):
        nonlocal injected,last_frame
        if frame!=last_frame:
            last_frame=frame
            addr=core.retro_get_memory_data(2)
            if addr and frame>=2450:
                raw=ct.string_at(addr,65536)
                if raw[0xf501]==10:
                    if not injected:
                        # A simulated hit has just left the counter at 196.
                        ct.memset(addr+((enemies+12+8)^1),196,1)
                        ct.memset(addr+((enemies+12+11)^1),0,1)
                        if a.contact_test:
                            ct.memset(addr+((enemies+9)^1),0,1)
                            ct.memset(addr+(combat^1),24,1)
                            ct.memset(addr+((combat+1)^1),0,1)
                            for i in range(6):ct.memset(addr+((shots+i*8+6)^1),0,1)
                        else: ct.memset(addr+((combat+1)^1),255,1)
                        injected=True
                    else:
                        state=(raw[rec^1],raw[timer^1],raw[(enemies+12+8)^1],
                               raw[combat^1],raw[(combat+1)^1],
                               struct.unpack_from('<HH',raw,player),
                               struct.unpack_from('<hh',raw,enemies+12),
                               raw[(enemies+12+9)^1],raw[(combat+5)^1],
                               raw[(enemies+12+11)^1])
                        if not trace or state[0]!=trace[-1][0] or (state[0]==2 and state[1]==59):trace.append(state)
        return ((button==3 and (600<=frame<604 or 2250<=frame<2254)) or
                (a.contact_test and button==7 and 2340<=frame<2404) or
                (button == 7 and 2100 <= frame < 2240 and (frame - 2100) % 20 < 4))
    harness.event_pressed=event
    sys.argv=['column-recovery','--core',str(a.core),'--system',str(a.system),
              '--cue',str(a.cue),'--output',str(a.output),'--frames','2700',
              '--script-only','--no-audio-file']
    harness.main()
    phases=[item for i,item in enumerate(trace) if i==0 or item[0]!=trace[i-1][0]]
    assert (len(phases)>=3 and phases[0][:3]==(1,120,212) and
            phases[1][:3]==(2,60,212) and phases[2][0]==0 and phases[2][2]==212),trace
    if a.contact_test:
        assert phases[0][3]==24 and phases[1][3:5]==(21,90),trace
    print('PASS: controlled damage triggered 212 HP reset and 120/60 recovery: %s' % trace[:3])
    if a.contact_test: print('PASS: contact disabled for first recovery phase, enabled in second')


if __name__=='__main__':main()
