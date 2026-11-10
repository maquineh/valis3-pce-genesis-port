#!/usr/bin/env python3
"""Boot the real game with the real System Card ROM in the emulator.

Verified boot chain (all offsets established from the System Card itself):

  * syscard1.pce maps 1:1 to physical $00000-$3FFFF
  * physical $00000-$01FFF  = System Card ROM, logical $E000-$FFFF (MPR7=$00)
  * physical $3E000-$3FFFF  = System Card bank accessed with MPR6=$1F
  * cd_boot reads disc sector 0, 2 sectors x 2048 bytes -> local RAM $2800
    (dh=1), verifies 0x4D5 bytes against the ROM reference at $3FAE1
    (which matches disc file 0x10 exactly), then JSR $2B26
  * the game's boot block therefore lives at logical $2800 <- disc file $0010
    and its entry is logical $2B26 <- disc file $0336

This tool installs that state and runs the game's own boot code.

Usage: python3 tools/emu_game.py [--steps N] [--out PREFIX] [--pc ADDR]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pce_system import PCESystem  # noqa: E402

ROM = "syscard1.pce"
TRACK = "build/extracted/data/track_02.bin"

BOOT_BLOCK_FILE = 0x0010         # disc sector 0 payload
BOOT_BLOCK_LOGICAL = 0x2800
BOOT_ENTRY = 0x2B26


class Disc(object):
    # The BIOS's recbase0 for this disc is 3215 (the drive LBA of the first
    # sector of track 2).  The extracted track_02.bin starts at that sector,
    # so absolute LBAs >= 3215 are rebased; early relative reads (0..5) pass
    # through unchanged.
    TRACK2_BASE = 3215

    def __init__(self, path):
        self.b = open(path, "rb").read()
        self.reads = []

    def read_sector(self, n):
        self.reads.append(n)
        if n >= self.TRACK2_BASE:
            n -= self.TRACK2_BASE
        off = n * 2352 + 16
        if off < 0 or off + 2048 > len(self.b):
            return b"\x00" * 2048
        return self.b[off:off + 2048]

    def read_sectors(self, n, count):
        return b"".join(self.read_sector(n + i) for i in range(count))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default=2000000, type=int)
    ap.add_argument("--pc", default=hex(BOOT_ENTRY))
    ap.add_argument("--out", default="build/game")
    ap.add_argument("--skip-check", action="store_true", default=True)
    args = ap.parse_args()

    rom = open(ROM, "rb").read()
    disc = Disc(TRACK)
    sysm = PCESystem(disc, verbose=False)

    # physical $00000-$3FFFF = the System Card image
    for i, byte in enumerate(rom):
        sysm.mem[i] = byte
    print("System Card ROM: %d bytes at physical $00000-$%05X"
          % (len(rom), len(rom) - 1))

    # boot block: disc file 0x10 -> logical $2800 (MPR1 = $F8 -> $1F0000)
    wr_base = 0xF8 << 13          # physical page for MPR1
    off = wr_base + (BOOT_BLOCK_LOGICAL & 0x1FFF)
    n = 2 * 2048
    for i in range(n):
        sysm.mem[off + i] = disc.b[BOOT_BLOCK_FILE + i]
    print("boot block: disc file $%04X (%d bytes) -> logical $%04X (physical $%06X)"
          % (BOOT_BLOCK_FILE, n, BOOT_BLOCK_LOGICAL, off))

    # MPRs exactly as cd_boot leaves them
    sysm.cpu.mpr = [0xFF, 0xF8, 0x04, 0x05, 0x06, 0x07, 0x1F, 0x00]
    print("MPR: %s" % " ".join("%02X" % m for m in sysm.cpu.mpr))
    print("  logical $4000-$5FFF -> physical $%05X" % (0x04 << 13))
    print("  logical $C000-$DFFF -> physical $%05X" % (0x1F << 13))

    # the boot code's $2007 pointer: point it at the continuation so the
    # indirect jump lands inside the boot block
    sysm.mem[wr_base + 0x2007] = 0x39
    sysm.mem[wr_base + 0x2008] = 0x2C

    sysm.cpu.pc = int(args.pc, 0)
    sysm.cpu.sp = 0xFF
    print("entry: logical $%04X" % sysm.cpu.pc)
    print()

    try:
        for _ in range(args.steps):
            sysm.cpu.step()
            sysm.steps += 1
    except StopIteration as e:
        print("control transfer:", e)
    except RuntimeError as e:
        print("stopped:", e)

    print("steps         : %d" % sysm.steps)
    print("BIOS calls    : %d" % len(sysm.bios_calls))
    from collections import Counter
    for name, k in Counter(n for _, n in sysm.bios_calls).most_common(12):
        print("   %-12s %d" % (name, k))
    print("sectors read  : %d distinct" % len(set(disc.reads)))
    print("             : %s" % sorted(set(disc.reads))[:16])
    print("VRAM writes   : %d" % len(sysm.vram_writes))
    print("CRAM colours  : %d" % sum(1 for c in sysm.cram if c))
    print("cpu           : pc=%04X a=%02X mpr=%s"
          % (sysm.cpu.pc, sysm.cpu.a,
             " ".join("%02X" % m for m in sysm.cpu.mpr)))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    print()
    print("VRAM dump:", sysm.dump_vram(args.out + "_vram.bin"))
    print("CRAM dump:", sysm.dump_cram(args.out + "_cram.bin"))
    print("VRAM non-zero: %d bytes" % sum(1 for x in sysm.vram if x))


if __name__ == "__main__":
    main()
