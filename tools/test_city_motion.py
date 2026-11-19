"""Check city movement cadence and hardware parallax on the built disc."""
import argparse
import ctypes as ct
from pathlib import Path
import re
import struct
import sys

import test_megacd_libretro as harness


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('core','system','cue','artifacts','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    symbols=(args.artifacts/'build/stage1.mmd.elf.sym').read_text()
    names=('xpos','feet','camera','scene_tick')
    offsets=[int(re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+'+k+r'$',symbols,re.M)[1],16)&65535
             for k in names]
    core=ct.CDLL(str(args.core.resolve()))
    core.retro_get_memory_data.argtypes=[ct.c_uint]
    core.retro_get_memory_data.restype=ct.c_void_p
    core.retro_serialize_size.restype=ct.c_size_t
    core.retro_serialize.argtypes=[ct.c_void_p,ct.c_size_t]
    core.retro_serialize.restype=ct.c_bool
    records={}
    bands={}
    # Start the control sequence after the CD and PCM banks have loaded.
    # Their startup time varies with the drive, while movement is measured in VBlanks.
    active = None
    script_input = harness.event_pressed
    def input_at(events,frame,button):
        nonlocal active
        if active is None and frame>=2300:
            ram=ct.string_at(core.retro_get_memory_data(2),65536)
            x,y,cam,t=(struct.unpack_from('<H',ram,n)[0] for n in offsets)
            if x==32 and y==192 and cam==0 and t==4:
                active=frame
        if active is None:
            return (frame<2300 and script_input(events,frame,button)) or (button==3 and 2420<=frame<2424)
        frame=2390+frame-active
        if frame not in records and 2390<=frame<=2930:
            ram=ct.string_at(core.retro_get_memory_data(2),65536)
            records[frame]=tuple(struct.unpack_from('<H',ram,n)[0] for n in offsets)
            if frame%17==0:
                size=core.retro_serialize_size()
                buf=ct.create_string_buffer(size)
                assert core.retro_serialize(buf,size)
                raw=buf.raw
                assert raw[:16]==b'GENPLUS-GX 1.7.6'
                base=0x12425+1024*raw[0x22525+13]
                bands[frame]=[tuple(v&1023 for v in struct.unpack_from('<2H',raw,base+32*r))
                              for r in range(4,28)]
        return script_input(events,frame,button)
    harness.event_pressed=input_at
    sys.argv=['motion','--core',str(args.core),'--system',str(args.system),'--cue',str(args.cue),
              '--output',str(args.output),'--script-only','--no-audio-file','--frames','3700',
              '--event','600:start:4','--event','2250:start:4','--event','2410:right:285',
              '--event','2650:b:3','--event','2710:left:191']
    harness.main()
    for start,end,dx in ((2420,2690,1),(2700,2710,0),(2720,2895,-1)):
        assert all(records[f][0]-records[f-1][0]==dx for f in range(start+1,end)), ('stride',start)
    assert all(records[f][3]-records[f-1][3]==1 for f in range(2400,2921)), 'missed display frame'
    heights=[records[f][1] for f in range(2650,2710)]
    assert min(heights)==132 and heights.count(132)==5 and heights[-1]==192, ('jump',heights)
    stationary=records[2705][2]
    assert stationary and all(records[f][2]==stationary for f in range(2710,2810))
    assert records[2685][0]-records[2685][2]==160 and records[2890][0]-records[2890][2]==48
    for f,rows in bands.items():
        _,_,cam,t=records[f]
        assert rows[:3]==[((-cam)&1023,(t>>1)&1023)]*3, ('cloud band',f,rows[:3],records[f])
        assert rows[3:]==[((-cam)&1023,(-((cam+3)>>2))&1023)]*21, ('skyline band',f)
    print('PASS: 521 consecutive game updates; 1px stride both ways; 60px jump; native camera limits and scroll bands')


if __name__=='__main__':
    main()
