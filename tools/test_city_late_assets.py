"""Check continuation packs against VDP budgets and every source floor cell."""
import struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def check(name):
    data=(ROOT/'game/res/gfx'/f'city_{name}.bin').read_bytes()
    cols,tiles=struct.unpack_from('>HH',data)
    assert 0<tiles<=1022
    maps_at=134+tiles*32
    words=lambda off,n:struct.unpack_from('>'+str(n)+'H',data,off)
    hud=words(maps_at,128)
    back=words(maps_at+256,1792)
    front=words(maps_at+3840,cols*28)
    floor_at=maps_at+3840+cols*56
    floor=words(floor_at,cols)
    for attr in hud+back+front:assert attr&2047<tiles,(name,'map tile')
    assert set(floor)<={0,160,176,192}
    poses_at=floor_at+cols*2
    for slot,offset in enumerate(words(poses_at,32)):
        at=poses_at+offset
        count=words(at,1)[0];at+=2
        assert count<=16
        for _ in range(count):
            x,y,attr,shape=struct.unpack_from('>hhHH',data,at);at+=8
            w=(shape>>2)+1;h=(shape&3)+1
            assert 1<=w<=4 and 1<=h<=4
            assert (attr&2047)+w*h<=tiles
            assert (attr&2047)%w==0,(name,slot,'sprite alignment')
    if name=='late':
        assert cols==255
        section=floor[64:223]
        changes=[(i*8,y) for i,y in enumerate(section) if i==0 or y!=section[i-1]]
        assert changes==[(0,160),(192,192),(256,0),(288,176),(352,0),(384,160),(448,0),(480,160),(544,0),(576,160),(736,176),(864,192)]
    else:assert floor==(192,)*32
    print(name,cols,'columns;',tiles,'tiles; valid map, collision and aligned sprite pieces')
for name in ('late','boss'):check(name)
