#!/usr/bin/env python3
"""Boot the PC Engine game in the HuC6280 emulator and dump its real VRAM.

The game's boot block lives in the first sectors of data track 2.  On the
real hardware the System Card BIOS copies it into work RAM and jumps to the
game's entry point, which then sets up the MPR banks (MPR0=$FF for the I/O
page, MPR1=$F8 for work RAM) and starts loading stage data through the CD
BIOS calls that tools/pce_system.py shims.

Because the exact IPL behaviour differs between System Card revisions, the
bootstrap parameters are exposed on the command line so the correct
combination can be found from the evidence (what ends up in VRAM).

Usage:
    python3 tools/emulate_boot.py [--entry ADDR] [--boot-logical ADDR]
            [--boot-sectors N] [--mpr0 PAGE] [--data-off N]
            [--steps N] [--out PREFIX] [--stop-vram N] [--quiet]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from pce_system import PCESystem  # noqa: E402

TRACK = "build/extracted/data/track_02.bin"


class Disc(object):
    """Data track 2 exposed as 2352-byte CD frames with a tunable payload."""

    def __init__(self, path, data_off=0, frame=2352):
        self.b = open(path, "rb").read()
        self.data_off = data_off
        self.frame = frame
        self.reads = []

    def read_sector(self, n):
        off = n * self.frame + self.data_off
        self.reads.append(n)
        # user data: the 2048 bytes after the 16-byte sector header
        return self.b[off + 16:off + 16 + 2048]

    def read_sectors(self, n, count):
        return b"".join(self.read_sector(n + i) for i in range(count))


def build(args):
    disc = Disc(TRACK, args.data_off)
    sysm = PCESystem(disc, verbose=not args.quiet)
    data = open(TRACK, "rb").read()

    # install the boot block at the physical page MPR0 selects, so that the
    # logical address the System Card jumps to resolves to the same bytes.
    # A PCE data sector frame is: 16-byte header, 2048 bytes of user data,
    # 288 bytes of ECC - the game only ever sees the 2048-byte payload.
    n_sectors = args.boot_sectors
    block = bytearray()
    for n in range(n_sectors):
        block += disc.read_sector(n)
    page = args.boot_logical >> 13
    off = args.boot_logical & 0x1FFF
    base = (args.mpr0 << 13) | off
    for i, byte in enumerate(block):
        sysm.mem[(base + i) & 0x1FFFFF] = byte

    # MPR setup: MPR0 selects the first 8 KiB (I/O page when $FF), MPR1 the
    # work RAM page ($F8 -> physical $1F0000)
    sysm.cpu.mpr[0] = args.mpr0
    sysm.cpu.mpr[1] = 0xF8
    for i in range(2, 8):
        sysm.cpu.mpr[i] = 0
    sysm.cpu.pc = args.entry
    sysm.cpu.sp = 0xFF
    return sysm, data


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", default="0x400", type=lambda x: int(x, 0))
    ap.add_argument("--boot-logical", default="0x0", type=lambda x: int(x, 0))
    ap.add_argument("--boot-sectors", default=8, type=int)
    ap.add_argument("--mpr0", default="0xF8", type=lambda x: int(x, 0))
    ap.add_argument("--data-off", default=0, type=lambda x: int(x, 0))
    ap.add_argument("--steps", default=200000, type=int)
    ap.add_argument("--stop-vram", default=0, type=int,
                    help="stop after this many VRAM writes")
    ap.add_argument("--out", default="build/emu")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    sysm, data = build(args)
    disc = sysm.disc
    orig_store = sysm._vram_store

    def store(word):
        orig_store(word)
        if args.stop_vram and len(sysm.vram_writes) >= args.stop_vram:
            raise StopIteration

    sysm._vram_store = store

    try:
        sysm.run(args.steps)
    except StopIteration:
        pass
    except RuntimeError as e:
        if not args.quiet:
            print("stopped:", e)

    print("steps           : %d" % sysm.steps)
    print("BIOS calls      : %d" % len(sysm.bios_calls))
    from collections import Counter
    c = Counter(n for _, n in sysm.bios_calls)
    for name, n in c.most_common():
        print("   %-14s %d" % (name, n))
    print("VRAM writes     : %d" % len(sysm.vram_writes))
    print("sectors read    : %d (%d distinct)" %
          (len(disc.reads), len(set(disc.reads))))
    print("first sectors   : %s" % sorted(set(disc.reads))[:12])

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    print("VRAM dump       : %s" % sysm.dump_vram(args.out + "_vram.bin"))
    print("CRAM dump       : %s" % sysm.dump_cram(args.out + "_cram.bin"))
    with open(args.out + "_sectors.txt", "w") as fh:
        fh.write("\n".join(str(s) for s in disc.reads))
    print("cpu state       : pc=%04X a=%02X x=%02X y=%02X mpr=%s" %
          (sysm.cpu.pc, sysm.cpu.a, sysm.cpu.x, sysm.cpu.y,
            " ".join("%02X" % m for m in sysm.cpu.mpr)))


if __name__ == "__main__":
    main()
