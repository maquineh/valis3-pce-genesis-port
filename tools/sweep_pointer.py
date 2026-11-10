#!/usr/bin/env python3
"""Sweep the initial value of the work-RAM jump pointer at $2007/$2008.

The boot block adds $3000 to the pointer at work RAM $2007/$2008 (reached as
zero page $07/$08 with MPR0=$F8) and then does `JMP ($2007)`.  The initial
value is what the System Card's CD boot leaves there.  For the jump to land
inside the boot block ($2800-$3800) the high byte must be $F8..$FF or
$00..$07 after the +$30.  This tool runs the boot for every candidate and
reports which ones reach real BIOS calls / stay in code.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pce_system import PCESystem  # noqa: E402
from emu_game import Disc, TRACK, ROM, BOOT_BLOCK_FILE, BOOT_BLOCK_LOGICAL  # noqa: E402
from disasm6280 import code_density  # noqa: E402

ROM_IMG = open(ROM, 'rb').read()
DISC_BYTES = open(TRACK, 'rb').read()
WB = 0xF8 << 13
BOOT_LEN = 2 * 2048


def make_emulator():
    disc = Disc(TRACK)
    emu = PCESystem(disc, verbose=False)
    for i, x in enumerate(ROM_IMG):
        emu.mem[i] = x
    off = WB + (BOOT_BLOCK_LOGICAL & 0x1FFF)
    for i in range(BOOT_LEN):
        emu.mem[off + i] = DISC_BYTES[BOOT_BLOCK_FILE + i]
    emu.cpu.mpr = [0xF8, 0xF8, 0x04, 0x05, 0x06, 0x07, 0x1F, 0x00]
    return emu


def run_case(lo, hi, steps=40000):
    emu = make_emulator()
    emu.mem[WB + 0x2004] = 0x00
    emu.mem[WB + 0x2007] = lo
    emu.mem[WB + 0x2008] = hi
    emu.cpu.pc = 0x2B26
    emu.cpu.sp = 0xFF
    distinct = set()
    jumped = None
    try:
        for _ in range(steps):
            pc = emu.cpu.pc
            distinct.add(pc)
            emu.cpu.step()
            emu.steps += 1
            if jumped is None and pc >= 0x2800 and pc < 0x3800 and \
                    emu.steps > 500:
                jumped = pc
    except StopIteration:
        pass
    except RuntimeError:
        pass
    nbios = len(emu.bios_calls)
    names = set(n for _, n in emu.bios_calls)
    return dict(lo=lo, hi=hi, target=((hi + 0x30) & 0xFF) << 8 | lo,
                steps=emu.steps, distinct=len(distinct), bios=nbios,
                names=sorted(names), vram=len(emu.vram_writes),
                pc=emu.cpu.pc)


def main():
    best = []
    print('sweeping hi=$F8 (target $28xx) ...')
    for lo in range(256):
        r = run_case(lo, 0xF8, steps=30000)
        if r['bios'] or r['vram']:
            best.append(r)
            print('  lo=$%02X target $%04X  bios=%d %s vram=%d distinct=%d'
                  % (r['lo'], r['target'], r['bios'], r['names'], r['vram'],
                     r['distinct']))
    print()
    if not best:
        print('no candidate reached a BIOS call in 30k steps at hi=$F8')
        # fall back: report the most active ones
        acts = []
        for lo in range(0, 256, 8):
            r = run_case(lo, 0xF8, steps=20000)
            acts.append(r)
        acts.sort(key=lambda r: -r['distinct'])
        print('most active candidates (distinct PCs):')
        for r in acts[:10]:
            print('  lo=$%02X target $%04X distinct=%d steps=%d pc=%04X'
                  % (r['lo'], r['target'], r['distinct'], r['steps'], r['pc']))
    else:
        best.sort(key=lambda r: -r['bios'])
        print('BEST:', best[0])


if __name__ == '__main__':
    main()
