#!/usr/bin/env python3
"""Boot the game in the emulator and log every BIOS call + VDC write.

The game's boot code reads its load parameters out of the CD BIOS work area,
which the System Card fills in during the IPL.  This tool injects a realistic
work RAM image (the boot block's parameter area) and traces the whole boot
sequence so the real stage loading chain becomes visible.

Usage:
    python3 tools/trace_boot.py [--steps N] [--out PREFIX]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pce_system import PCESystem  # noqa: E402

TRACK = "build/extracted/data/track_02.bin"


class Disc(object):
    def __init__(self, path):
        self.b = open(path, "rb").read()
        self.reads = []

    def read_sector(self, n):
        self.reads.append(n)
        return self.b[n * 2352 + 16:n * 2352 + 16 + 2048]

    def read_sectors(self, n, count):
        return b"".join(self.read_sector(n + i) for i in range(count))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default=1000000, type=int)
    ap.add_argument("--out", default="build/trace")
    args = ap.parse_args()

    disc = Disc(TRACK)
    sysm = PCESystem(disc, verbose=False)
    b = disc.b

    # The System Card IPL loads the boot block into work RAM at logical $2000
    # and jumps to its entry point.  The boot code then sets MPR0=$FF (I/O page)
    # and MPR1=$F8 (work RAM), which is why it lives above $2000 in the first
    # place: with MPR0=$FF the code at $0000-$1FFF would be the I/O page.
    # So: MPR1 = $F8 (work RAM) holds the code at logical $2000-$3FFF.
    blk = bytearray()
    for s in range(8):
        blk += disc.read_sector(s)
    base = 0xF8 << 13
    for i, byte in enumerate(blk):
        sysm.mem[(base + i) & 0x1FFFFF] = byte

    # MPR0 = $F8 keeps the boot block executable while it runs; the code sets
    # MPR0 = $FF itself once it no longer needs to execute from that page.
    sysm.cpu.mpr = [0xF8, 0xF8, 0, 0, 0, 0, 0, 0]
    sysm.cpu.pc = 0x23E0
    sysm.cpu.sp = 0xFF

    # ---- System Card work RAM image --------------------------------
    # MPR1 = $F8 maps logical $2000-$3FFF to physical $1F0000-$1F1FFF, i.e.
    # the game's work RAM.  The IPL writes the CD boot parameters into the
    # game's parameter area at $3008-$301F, which the boot code reads:
    #     $3011 -> al  (sector count)
    #     $3012 -> bl  (destination low)
    #     $3013 -> bh  (destination high)
    #     $3017/$3018 -> ADPCM parameters
    # write through the CPU's MPR mapping so the game sees the same bytes
    def wr(addr, val):
        sysm.mem[sysm.cpu.phys(addr)] = val

    wr(0x3008, 0x00)
    wr(0x3011, 0x01)      # al: 1 sector
    wr(0x3012, 0x00)      # bl: dest low  -> $4000
    wr(0x3013, 0x40)      # bh: dest high
    wr(0x3017, 0x00)
    wr(0x3018, 0x00)
    # $2007 holds the pointer the boot jumps to at the very end.
    # The System Card IPL puts the entry point of the loaded program there;
    # the game's own code then keeps running from that address.
    wr(0x2007, 0xE0)
    wr(0x2008, 0x83)

    print("== boot trace ==")
    flow = []
    for _ in range(args.steps):
        pc0 = sysm.cpu.pc
        try:
            mn = sysm.cpu.step()
        except StopIteration as e:
            print("control transfer: %s" % e)
            break
        except RuntimeError as e:
            print("stopped: %s" % e)
            break
        sysm.steps += 1
        if mn in ("JMP", "JSR") and len(flow) < 60:
            flow.append((sysm.steps, pc0, mn, sysm.cpu.pc))
        if mn in ("JMP", "JSR", "RTS", "RTI") and len(flow) >= 60:
            break
    print("control flow (first 60 transfers):")
    for st, pc, mn, dst in flow:
        print("   step %8d  $%04X %-3s -> $%04X" % (st, pc, mn, dst))

    print("steps        : %d" % sysm.steps)
    print("BIOS calls   : %d" % len(sysm.bios_calls))
    for st, name in sysm.bios_calls[:40]:
        print("   step %7d  %s" % (st, name))
    print("VRAM writes  : %d" % len(sysm.vram_writes))
    print("sectors read : %d distinct %d" % (len(disc.reads), len(set(disc.reads))))
    print("cpu          : pc=%04X mpr=%s" %
          (sysm.cpu.pc, " ".join("%02X" % m for m in sysm.cpu.mpr)))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    sysm.dump_vram(args.out + "_vram.bin")
    sysm.dump_cram(args.out + "_cram.bin")


if __name__ == "__main__":
    main()
