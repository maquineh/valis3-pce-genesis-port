#!/usr/bin/env python3
"""Compare STG4A direction arithmetic with captured HuC6280 code."""
import argparse
from pathlib import Path
import random
from pce_state import decompress, parse
from pce_system import PCESystem


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('state',type=Path)
    args=ap.parse_args()
    data=parse(decompress(str(args.state)))['CDRAM'][2]
    if data[0xa000:0xa005]!=b'STG4A': raise ValueError('expected STG4A')
    for addr,record in ((0x826e,'01 ff 11 00 02 03 20 00 12 dc 00 00'),
                        (0x827a,'01 ff 11 00 02 03 20 f8 ee ec 00 00'),
                        (0x8286,'01 ff 11 00 02 03 20 00 12 fc 00 00')):
        if data[addr:addr+12]!=bytes.fromhex(record):
            raise AssertionError('unexpected projectile spawn record')
    emu=PCESystem(None,verbose=False)
    emu.mem[0x100000:0x110000]=data
    emu.cpu.mpr=[255,248,128,129,130,133,131,0]
    random.seed(4)
    for _ in range(1000):
        dx=random.randint(-1280,1280); dy=random.randint(-1280,1280)
        for addr,value in ((0xd2,dx&255),(0xd3,(dx>>8)&255),
                           (0xd6,dy&255),(0xd7,(dy>>8)&255)):
            emu.cpu.zp_write(addr,value)
        emu.cpu.pc=0x7a34
        for __ in range(1000):
            if emu.cpu.pc in (0x7a94,0x7a7f): break
            emu.cpu.step()
        else: raise RuntimeError('direction routine did not return')
        ratio=min(80,(abs(dy)*16)//abs(dx)) if dx else 80
        i=sum(ratio>=q for q in (3,6,10,16,23,38,80))
        expected=(8+i if dy>=0 else 7-i) if dx>=0 else (23-i if dy>=0 else 24+i)
        if emu.cpu.a!=expected: raise AssertionError((dx,dy,expected,emu.cpu.a))
    vx=(0,3,5,7,8,7,5,3,0,-3,-5,-7,-8,-7,-5,-3)
    vy=(-8,-7,-5,-3,0,3,5,7,8,7,5,3,0,-3,-5,-7)
    for direction in range(16):
        emu.cpu.zp_write(0xd0,8)
        emu.cpu.zp_write(0xd1,direction)
        emu.cpu.pc=0x7b0c
        for _ in range(1000):
            if emu.cpu.pc==0x7b53: break
            emu.cpu.step()
        else: raise RuntimeError('velocity routine did not return')
        def signed(n): return n-256 if n&128 else n
        actual=(signed(emu.cpu.zp_read(0xd7)),signed(emu.cpu.zp_read(0xd6)))
        if actual!=(vx[direction],vy[direction]): raise AssertionError((direction,actual))
    print('PASS: spawn records, 1000 directions and 16 velocities match PCE HuC6280')


if __name__=='__main__': main()
