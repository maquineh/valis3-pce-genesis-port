"""Pack native retail city continuation and boss SAT art, without redrawing pixels.

Requires assisted captures from build/city-late5 (roof traversal), city-late7
(grounded exit) and city-boss (battle). Assist changes are capture-only; stage
collision/AI in city_late.h is a playable approximation, not retail code.
"""
from pathlib import Path
from functools import lru_cache
import argparse, struct, json
from pack_genesis_city import State, words
ROOT=Path(__file__).resolve().parents[1]
@lru_cache(maxsize=12)
def state(path):return State(path)

def pack(name, captures, start, columns, out):
    ref=state(ROOT/'build/city-late5/s1200.z' if name=='late' else captures[0][1])
    tiles=bytearray(32);blocks={bytes(32):0}
    def pattern(s,a,n=1,align=1):
        b=s.vram[(a&2047)*32:((a&2047)+n)*32]
        key=(b,align)
        if key not in blocks:
            while len(tiles)//32%align:tiles.extend(bytes(32))
            blocks[key]=len(tiles)//32;tiles.extend(b)
        return (a&0xf800)|blocks[key]
    fg=[];floors=[]
    for col in range(columns):
        world=start+col*8
        s=state(min(captures,key=lambda cf:abs(cf[0]+128-world))[1])
        src=[s.cell(0,world//8,y) for y in range(28)]
        fg.extend(pattern(s,a) if y>=4 else 0 for y,a in enumerate(src))
        floors.append(next((y*8 for y,a in enumerate(src) if y>=12 and a&2047==752),0))
    bg=[pattern(ref,ref.cell(1,x,y)) if y>=4 else 0 for y in range(28) for x in range(64)]
    # Match room start to the existing quarter-speed skyline phase.
    hud=[pattern(ref,a) for a in ref.words[ref.reg[3]*512:ref.reg[3]*512+128]]
    poses=[[] for _ in range(32)]
    def pose(slot,path,select,anchor=None):
        s=state(path);parts=[v for v in s.sat if v[1]>30 and v[0]>-40 and select(v)]
        if not parts:raise ValueError((name,slot,str(path)))
        if anchor is None:anchor=((min(v[0] for v in parts)+max(v[0]+v[2]*8 for v in parts))//2,max(v[1]+v[3]*8 for v in parts))
        poses[slot]=[(x-anchor[0],y-anchor[1],pattern(s,a,w*h,w),(w-1)*4+h-1) for x,y,w,h,a in parts]
    roof=ROOT/'build/city-genesis'
    hero=lambda p:p[4]&2047<0x180
    for slot,f in enumerate((11988,12000,11991,11970,12018)):
        pose(slot,roof/f's{f}.z',hero)
    for slot,f in ((15,6368),(16,12135),(17,12006),(18,12045)):
        pose(slot,roof/f's{f}.z',hero)
    for slot,f in enumerate((12150,12000,12018,12048),11):
        pose(slot,roof/f's{f}.z',lambda p:0x380<=p[4]&2047<=0x3bf)
    late=ROOT/'build/city-late5'
    pose(19,late/'s800.z',lambda p:0x3c0<=p[4]&2047<=0x41f)
    pose(20,late/'s2000.z',lambda p:0x3c0<=p[4]&2047<=0x41f)
    pose(21,late/'s800.z',lambda p:0x418<=p[4]&2047<=0x43f and p[0]<220)
    pose(22,late/'s1200.z',lambda p:0x3b0<=p[4]&2047<0x3c0)
    pose(23,late/'s2800.z',lambda p:0x4c4<=p[4]&2047<=0x50f)
    boss=ROOT/'build/city-boss'
    for slot,f in ((24,400),(25,600),(26,800),(27,1400)):
        pose(slot,boss/f's{f}.z',lambda p:0x480<=p[4]&2047<0x4c0 or 0x4e1<=p[4]&2047<=0x53f)
    pose(28,boss/'s600.z',lambda p:0x4c9<=p[4]&2047<=0x4d0 and p[0]>190)
    assert len(tiles)//32<=1024, (name,len(tiles)//32)
    offsets=[];records=bytearray()
    for parts in poses:
        offsets.append(len(poses)*2+len(records));records.extend(words([len(parts)]))
        for x,y,a,shape in parts:records.extend(struct.pack('>hhHH',x,y,a,shape))
    pal=[(v&7)*2+((v>>3)&7)*32+((v>>6)&7)*512 for v in ref.pal]
    data=words([columns,len(tiles)//32])+bytes([0,63])+words(pal)+tiles+words(hud)+words(bg)+words(fg)+words(floors)+words(offsets)+records
    (out/f'city_{name}.bin').write_bytes(data)
    print(name,len(data),'bytes',len(tiles)//32,'tiles',sorted(set(floors)))
    return dict(name=name,bytes=len(data),tiles=len(tiles)//32,source_left=start,columns=columns,floors=floors)

def pack_boss_dialogue(out):
    # Three complete Japanese pages, after the camera reaches the arena.
    tiles = {}
    pages = []
    for folder, frame in (('city-late7', 800), ('city-boss', 80), ('city-boss', 200)):
        original = state(ROOT/'build'/folder/f's{frame}.z')
        assert original.reg[18] == 14
        window = original.reg[3]*512 + 128
        for attr in original.words[window:window+320]:
            offset = (attr & 2047)*32
            tile = original.vram[offset:offset+32]
            index = tiles.setdefault(tile, 700+len(tiles))
            pages.append((attr & 0xf800) | index)
    assert 700+len(tiles) <= 1022
    (out/'city_boss_dialogue.bin').write_bytes(words([len(tiles)])+b''.join(tiles)+words(pages))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'game/res/gfx');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    captures=[];previous=0;camera=0
    for dirname,stop in [('city-late5',2800),('city-late7',400)]:
        for f in range(0,stop+1,8):
            path=ROOT/'build'/dirname/f's{f}.z'
            s=state(path);cur=(-s.scroll(24,0))&1023
            delta=(cur-previous)&1023
            if delta<100:camera+=delta
            previous=cur;captures.append((camera,path))
    boss=[(1784,ROOT/'build/city-boss/s400.z')]
    pack_boss_dialogue(a.output)
    reports=[pack('late',captures,0,255,a.output),pack('boss',boss,1784,32,a.output)]
    (ROOT/'build/city-late-packs.json').write_text(json.dumps(reports,indent=2))
if __name__=='__main__':main()
