"""Pack the rooftop kidnapping and sword sequence from live Japanese Genesis VDP frames.

Use a capture starting at the original s7248 checkpoint from capture_genesis_city.py
(the last street frame). tools/capture_city_cinema.py generates the individual states.
"""
import argparse
from itertools import groupby
from pathlib import Path
import struct

from pack_genesis_city import ROOT, State, words

TILE_BASE = 384
# Completed original dialogue pages. Each interval includes its typewriter time.
DIALOGUE = ((9,59,45),(59,150,90),(150,240,185),(240,351,300),
            (553,604,580),(604,694,650),(694,805,755),(992,1043,1020),
            (1043,1154,1100),(1284,1356,1320),(2028,2082,2050))


def pack(source, name, start, stop, output):
    tiles = bytearray()
    patterns = {}
    def pattern(state, attr, length):
        address = (attr & 2047)*32
        data = state.vram[address:address+32*length]
        if data not in patterns:
            patterns[data] = TILE_BASE + len(tiles)//32
            tiles.extend(data)
        return attr & 0xf800 | patterns[data]

    def read(f):
        return State(source/f's{f}.z')

    pages = []
    page_ids = {}
    for lo,hi,full in DIALOGUE:
        if start <= full < stop:
            s = read(full)
            base = s.reg[3]*512 + 4*32
            page = words([pattern(s, a, 1) for a in s.words[base:base+10*32]])
            if page not in pages:
                pages.append(page)
            page_ids.update(dict.fromkeys(range(lo,hi), 1+pages.index(page)))

    # Reuse relative SAT assemblies independently of each actor's screen position.
    poses = {}
    groups = {}
    instances = bytearray()
    timeline = []
    last = None
    for frame in range(start,stop):
        s = read(frame)
        visible = [p for p in s.sat if p[0]+8*p[2]>0 and p[0]<256 and
                   p[1]+8*p[3]>32 and p[1]<224]
        def actor(p):
            tile = p[4] & 2047
            if tile >= 0x500: return 'captor'
            if tile >= 0x480: return 'captive'
            if 0x19c <= tile <= 0x1ab: return 'sword'
            return 'hero'
        actors = []
        foot = 0
        for who, pieces in groupby(visible, key=actor):
            pieces = list(pieces)
            x,y = pieces[0][:2]
            if who=='hero': foot=max(top+8*h for _,top,_,h,_ in pieces)
            relative = tuple((left-x,top-y,pattern(s,attr,w*h),(w-1)*4+h-1)
                             for left,top,w,h,attr in pieces)
            idx = poses.setdefault(relative,len(poses))
            actors.extend((idx,x,y))
        actors = tuple(actors)
        if actors not in groups:
            groups[actors] = len(instances)//2
            instances.extend(struct.pack('>H'+'h'*len(actors),len(actors)//3,*actors))
        vertical = (s.vs[0],s.vs[1],s.vs[14]) if name=='fall' else (0,0,0)
        record = (groups[actors],page_ids.get(frame,0),*vertical,foot)
        if record==last:
            timeline[-1][0]+=1
        else:
            timeline.append([1,*record])
            last=record
    pose_table = bytearray()
    offsets=[]
    for pose in poses:
        offsets.append(len(poses)*2+len(pose_table))
        pose_table.extend(words([len(pose)]))
        for piece in pose:
            pose_table.extend(struct.pack('>hhHH',*piece))
    assert len(poses)<256 and TILE_BASE+len(tiles)//32<=1280,(len(poses),len(tiles)//32)
    sections = [tiles,b''.join(pages),words(offsets)+pose_table,instances,
                b''.join(struct.pack('>3H4h',*r) for r in timeline)]
    offsets=[]
    length=20
    for data in sections:
        offsets.append(length)
        length+=len(data)
    header=words([TILE_BASE,len(tiles)//32,len(timeline),stop-start,len(pages),*offsets])
    dest=output/f'city_cinema_{name}.bin'
    dest.write_bytes(header+b''.join(sections))
    print(name,stop-start,'frames,',len(poses),'poses,',len(tiles)//32,'tiles,',length,'bytes')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'game/res/gfx')
    args=parser.parse_args()
    pack(args.source,'meeting',9,1560,args.output)
    pack(args.source,'fall',1734,2315,args.output)
