#!/usr/bin/env python3
"""Execute captured PCE actor contact and enemy damage routines."""
import argparse
from pathlib import Path
from pce_state import decompress, parse
from pce_system import PCESystem


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('state',type=Path)
    args=ap.parse_args()
    v=parse(decompress(str(args.state)))
    data,ram=v['CDRAM'][2],v['BaseRAM'][2]
    if data[0xa000:0xa005]!=b'STG4A' or ram[0x378]!=0 or ram[0x38c]!=2:
        raise ValueError('expected captured STG4A Yuko, weapon level 2')
    def system():
        m=PCESystem(None,verbose=False)
        m.mem[0x100000:0x110000]=data
        m.cpu.mpr=[255,248,128,129,130,133,131,0]
        return m
    def run(m,start,stops,skips=None):
        m.cpu.pc=start
        for _ in range(5000):
            if m.cpu.pc in stops: return m.cpu.pc
            if skips and m.cpu.pc in skips:
                m.cpu.pc=skips[m.cpu.pc]
            else: m.cpu.step()
        raise RuntimeError('routine did not reach expected exit')
    def put16(m,a,n):
        m.write(a,n&255);m.write(a+25,(n>>8)&255)
    def actor(typ):
        m=system();m.cpu.x=1;m.cpu.a=typ
        run(m,0x5765,{0x5844})
        m.write(0x2470,1)  # valid animation/frame; skull is awake
        m.write(0x238d,24)
        put16(m,0x2536,144*16);put16(m,0x2568,100*16)
        put16(m,0x283f,144*16);put16(m,0x2871,100*16)
        return m
    for typ,damage,rad in ((5,3,19),(6,2,15)):
        for dx,hit in ((rad,True),(rad+1,False)):
            m=actor(typ);put16(m,0x2871,(100+dx)*16)
            run(m,0xc23c,{0xc2a6},{0xc766:0xc76b})  # skip only sound call
            assert m.read(0x238d)==24-(damage if hit else 0),(typ,dx)
            assert m.read(0x24eb)==(90 if hit else 0),(typ,dx)
            if hit:
                run(m,0xc23c,{0xc2a6},{0xc766:0xc76b})
                assert m.read(0x238d)==24-damage  # invulnerability prevents repeat
        # Standing player center is feet-24, enemy center is feet-40/-16.
        vrad=62 if typ==5 else 34
        offset=40 if typ==5 else 16
        for dy,hit in ((vrad,True),(vrad+1,False),(-vrad,True),(-vrad-1,False)):
            m=actor(typ);put16(m,0x283f,(120+dy+offset)*16)
            run(m,0xc23c,{0xc2a6},{0xc766:0xc76b})
            assert m.read(0x238d)==24-(damage if hit else 0),(typ,dy)
        m=actor(typ); m.cpu.x=1;m.cpu.a=4
        run(m,0xc795,{0xc7e4,0xc7e5},{0xc7d8:0xc7dd})
        hp=212 if typ==5 else 8
        assert m.read(0x26fa)==hp-4 and m.read(0x24ed)==10
        m.cpu.x=1;m.cpu.a=4
        run(m,0xc795,{0xc7e4,0xc7e5},{0xc7d8:0xc7dd})
        assert m.read(0x26fa)==hp-4  # 10-update enemy hit protection
    m=actor(5);m.cpu.x=1;m.write(0x26fa,200)
    assert run(m,0x9246,{0x9245,0x9261})==0x9245
    m.write(0x26fa,199)
    assert run(m,0x9246,{0x9245,0x9261})==0x9261
    assert (m.read(0x26fa),m.read(0x280d),m.read(0x27c2))==(212,120,3)
    run(m,0x9261,{0x9e57})
    assert m.read(0x23f3)&0x40  # first recovery phase disables contact and damage
    m.write(0x23da,m.read(0x23da)|4)
    assert run(m,0x9264,{0x9277,0x9282})==0x9277
    assert (m.read(0x280d),m.read(0x27c2))==(60,0)
    run(m,0x9277,{0x9e57})
    assert not (m.read(0x23f3)&0x40)
    # Type-11 projectile, slot 17, at player center; power 3, 4/4 radii.
    m=system();m.write(0x238d,24)
    put16(m,0x2536,144*16);put16(m,0x2568,100*16)
    y=17
    for a,n in ((0x2a16+y,2),(0x2a49+y,3),(0x2e78+y,4),(0x2eab+y,4)):
        m.write(a,n)
    # Projectile coordinates have arrays separated by 0x33, not 25 bytes.
    for a,n in ((0x2dac+y,100*16),(0x2e12+y,120*16)):
        m.write(a,n&255);m.write(a+0x33,n>>8)
    run(m,0xc23c,{0xc2a6},{0xc766:0xc76b})
    assert m.read(0x238d)==21 and m.read(0x24eb)==90
    print('PASS: PCE collision, damage, protection and column recovery routines')


if __name__=='__main__': main()
