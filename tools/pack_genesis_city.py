"""Pack the Japanese Genesis city's VDP planes and live SAT poses for Mega CD.

Input: frame dumps from capture_genesis_city.py. Source lives in the user's
cartridge; the mode-5 VRAM/CRAM layout below is for Genesis Plus GX 1.7.6.
"""
import argparse
from functools import lru_cache
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]


class State:
    def __init__(self, path):
        raw = zlib.decompress(path.read_bytes())
        if raw[:16] != b'GENPLUS-GX 1.7.6':
            raise ValueError('unexpected core state layout')
        self.words = struct.unpack_from('<32768H', raw, 0x12425)
        self.vram = struct.pack('>32768H', *self.words)
        self.reg = raw[0x22525:0x22545]
        self.vs = struct.unpack_from('<64h', raw, 0x224a5)
        self.pal = struct.unpack_from('<64H', raw, 0x22425)
        self.hbase = self.reg[13] * 512
        self.sat = []
        index = 0
        for _ in range(80):
            pos = self.reg[5] * 256 + 4 * index
            y, size, attr, x = self.words[pos:pos + 4]
            self.sat.append((x % 512 - 128, y % 512 - 128,
                             1 + ((size >> 10) & 3), 1 + ((size >> 8) & 3), attr))
            index = size & 127
            if not index:
                break

    def scroll(self, row, plane):
        pos = row * 16 if self.reg[11] & 2 else 0
        return self.words[self.hbase + pos + plane] & 1023

    def cell(self, plane, col, row, raw_rows=False):
        offset = self.reg[2] * 512 if not plane else self.reg[4] * 4096
        column = (col % 32) // 2 * 2 if self.reg[11] & 4 else 0
        sy = row if raw_rows else (row + self.vs[column + plane] // 8) % 32
        return self.words[offset + 64 * sy + col % 64]


def words(values):
    return struct.pack('>' + str(len(values)) + 'H', *values)


def pack(name, base, cols, frames, state, dest, descent=b''):
    vertical = name == 'fall'
    rows = 32 if vertical else 28
    ref = state(base)
    tiles = bytearray(32)
    blocks = {bytes(32): 0}
    def pattern(s, attr, length=1):
        start = (attr & 2047) * 32
        data = s.vram[start:start + 32 * length]
        if data not in blocks:
            blocks[data] = len(tiles) // 32
            tiles.extend(data)
        return (attr & 0xf800) | blocks[data]

    cameras = sorted(((1024 - state(f).scroll(24, 0)) % 1024, f) for f in frames)
    # A tracks the stage in world coordinates. Read each column close to the
    # middle of a live viewport, before the original streamer reuses it.
    fg = []
    floors = []
    for x in range(cols):
        s = state(min(cameras, key=lambda cf: abs(cf[0] + 128 - x * 8))[1]) if cameras else ref
        source = [s.cell(0, x, y, vertical) for y in range(rows)]
        fg.extend(pattern(s, a) if vertical or y >= 4 else 0 for y, a in enumerate(source))
        top = next((y * 8 for y,a in enumerate(source) if y>=14 and a & 2047 == 752), 0)
        floors.append(top)
    # B scrolls independently. Retain the whole 64-cell ring. The upper
    # four rows behind the fixed HUD must stay clear.
    bg = [pattern(ref, ref.cell(1, x, y, vertical)) if vertical or y >= 4 else 0
          for y in range(rows) for x in range(64)]
    window = ref.reg[3] * 512
    hud = [pattern(ref, a) for a in ref.words[window:window + 32 * 4]]
    poses = [[] for _ in range(19)]
    def pose(slot, frame, select, anchor=None, art=None):
        s = state(frame)
        pieces = [v for v in s.sat if v[1] > 30 and v[0] > -40 and select(v)]
        assert pieces, (name, slot, frame)
        if anchor is None:
            left = min(x for x,y,w,h,a in pieces)
            right = max(x + 8*w for x,y,w,h,a in pieces)
            anchor = ((left + right)//2, max(y + 8*h for x,y,w,h,a in pieces))
        poses[slot] = [(x-anchor[0], y-anchor[1], pattern(art if art is not None else s,a,w*h), (w-1)*4+h-1)
                       for x,y,w,h,a in pieces]
    def hero(p):
        return (p[4] & 2047) < 0x180
    if name == 'street':
        for i,f in enumerate((6260,6352,6472,6450)):
            pose(i,f,hero)
    if name == 'meeting':
        pose(0,8070,lambda p:p[0]<50 and hero(p))
        for i,f in enumerate((6352,6472,6450),1):
            pose(i,f,hero)
        pose(4,8070,lambda p:p[0]==100)
        pose(5,8070,lambda p:120<p[0]<170)
    if name == 'fall':
        pose(0,10000,lambda p: (p[4]&2047)!=0x19c)
        pose(4,10000,lambda p: (p[4]&2047)==0x19c)
        pose(5,11490,lambda p: (p[4]&2047) in (0x184,0x194))
    if name == 'roof':
        for i,f in enumerate((11988,12000,11991,11970,12018)):
            pose(i,f,hero)
        # Foot anchors stay fixed through anticipation, contact and recovery.
        for i,f in enumerate((11973,11976,11982,12201,12204,12210),5):
            primary = state(f).sat[2]
            body = [v for v in state(f).sat if v[1]>30 and hero(v) and v[0]>-40]
            feet = max(y + h*8 for x,y,w,h,a in body)
            pose(i,f,lambda p:hero(p) or 0x1b4 <= (p[4]&2047) <= 0x1bc,
                 (primary[0]+16,feet))
        for i,f in enumerate((12150,12000,12018,12048),11):
            pose(i,f,lambda p:0x380 <= (p[4]&2047) <= 0x3bf)
    if name in ('street', 'meeting', 'roof'):
        # Pattern numbers are shared by both costumes. Preserve the SAT
        # arrangement of each stride and use the tiles from this room.
        for slot, frame in ((15, 6368), (16, 12135), (17, 12006), (18, 12045)):
            pose(slot, frame, hero, art=ref)
    offsets, records = [], bytearray()
    for parts in poses:
        offsets.append(len(poses)*2 + len(records))
        records.extend(words([len(parts)]))
        for x,y,a,shape in parts:
            records.extend(struct.pack('>hhHH',x,y,a,shape))
    assert len(tiles) <= 0xa000, 'art overlaps VDP window'
    pal = [(v & 7)*2 + ((v>>3)&7)*32 + ((v>>6)&7)*512 for v in ref.pal]
    output = (words([cols,len(tiles)//32]) + bytes([0,63]) + words(pal) + tiles +
              words(hud) + words(bg) + words(fg) + words(floors) + descent + words(offsets) + records)
    (dest/('city_'+name+'.bin')).write_bytes(output)
    print(name,len(output), 'bytes;', len(tiles)//32,'tiles;', 'surfaces',sorted(set(floors)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures',type=Path)
    args=parser.parse_args()
    @lru_cache(maxsize=6)
    def state(frame):
        return State(args.captures/f's{frame}.z')
    dest=ROOT/'game/res/gfx'
    pack('street',6450,96,range(6368,7025,16),state,dest)
    pack('meeting',7890,32,[],state,dest)
    pack('fall',10000,32,[],state,dest,(args.captures/'descent.bin').read_bytes())
    pack('roof',12000,74,range(12000,12641,16),state,dest)


if __name__=='__main__':
    main()
