#!/usr/bin/env python3
"""Run the stage loader chunk in the emulator and capture the real VRAM writes.

The chunk at sector 1000 (4 sectors) is read by `cd_read` at $2252C4 to local
RAM $8000, so its entry runs at logical $8004.  The emulator installs

  * the resident overlay (sectors 32-39) at physical $40000  (MPR2)
  * the stage chunk      (sectors 1000-1003) at physical $08000 (MPR4)

and then executes the stage entry.  Every write the loader makes to the VDC
(through ex_setwrt + STA $0002/$0003, or TIA to the data port) is captured in
`PCESystem.vram`, which is exactly the per-screen VRAM state that the static
analysis could not reconstruct.

Usage:
    python3 tools/emu_stage.py [--dh-ff vram|ram] [--steps N] [--out PREFIX]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pce_system import PCESystem  # noqa: E402

TRACK = "build/extracted/data/track_02.bin"
CHUNK_SECTOR = 1000          # the stage loader chunk
RESIDENT_SECTOR = 32         # the resident overlay


class Disc(object):
    def __init__(self, path):
        self.b = open(path, "rb").read()
        self.reads = []

    def read_sector(self, n):
        self.reads.append(n)
        return self.b[n * 2352 + 16:n * 2352 + 16 + 2048]

    def read_sectors(self, n, count):
        return b"".join(self.read_sector(n + i) for i in range(count))


def install(mem, sectors, phys):
    """Install sector payloads contiguously at a physical address."""
    b = open(TRACK, "rb").read()
    off = phys
    for s in range(sectors, sectors + 4):
        for byte in b[s * 2352 + 16:s * 2352 + 16 + 2048]:
            mem[off] = byte
            off += 1
    return off


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dh-ff", default="vram", choices=["vram", "ram"])
    ap.add_argument("--steps", default=400000, type=int)
    ap.add_argument("--out", default="build/emu_stage")
    args = ap.parse_args()

    disc = Disc(TRACK)
    sysm = PCESystem(disc, verbose=False)

    # install the resident overlay and the stage chunk
    end_res = install(sysm.mem, RESIDENT_SECTOR, 0x40000)
    end_chunk = install(sysm.mem, CHUNK_SECTOR, 0x08000)
    print("resident overlay  sectors %d-%d -> physical $40000-$%06X"
          % (RESIDENT_SECTOR, RESIDENT_SECTOR + 3, end_res))
    print("stage chunk       sectors %d-%d -> physical $08000-$%06X"
          % (CHUNK_SECTOR, CHUNK_SECTOR + 3, end_chunk))

    # MPR setup so the logical addresses the code uses resolve to them
    sysm.cpu.mpr = [0xFF, 0xF8, 0x20, 0x00, 0x04, 0x00, 0x00, 0x00]
    print("MPR: %s   (logical $4000 -> $40000, $8000 -> $08000)"
          % " ".join("%02X" % m for m in sysm.cpu.mpr))

    # dh=$FF destination semantics
    orig = sysm._load_sectors

    def load(unit_bytes):
        if args.dh_ff == "vram" and sysm.wa[0xFF] == 0xFF:
            wa_ff = sysm.wa[0xFF]
            sysm.wa[0xFF] = 0xFE
            try:
                return orig(unit_bytes)
            finally:
                sysm.wa[0xFF] = wa_ff
        return orig(unit_bytes)

    sysm._load_sectors = load

    # work RAM: the IPL parameters the stage entry reads
    def wr(addr, val):
        sysm.mem[sysm.cpu.phys(addr)] = val

    wr(0x2007, 0x04)     # not used by the stage entry
    wr(0x2008, 0x80)

    sysm.cpu.pc = 0x8004
    sysm.cpu.sp = 0xFF
    print("entry: logical $8004 (stage chunk)")
    print()

    calls = []
    try:
        for _ in range(args.steps):
            pc0 = sysm.cpu.pc
            sysm.cpu.step()
            sysm.steps += 1
            if sysm.bios_calls and sysm.bios_calls[-1][0] == sysm.steps - 1:
                name = sysm.bios_calls[-1][1]
                wa = dict(sorted(sysm.wa.items()))
                calls.append((sysm.steps, name, wa, sysm.cpu.pc))
    except StopIteration as e:
        print("control transfer:", e)
    except RuntimeError as e:
        print("stopped:", e)

    print("steps          : %d" % sysm.steps)
    print("BIOS calls     : %d" % len(sysm.bios_calls))
    from collections import Counter
    for name, n in Counter(n for _, n in sysm.bios_calls).most_common():
        print("   %-12s %d" % (name, n))
    print("sectors read   : %d distinct" % len(set(disc.reads)))
    print("first sectors  : %s" % sorted(set(disc.reads))[:12])
    print("VRAM writes    : %d" % len(sysm.vram_writes))
    print("cpu            : pc=%04X mpr=%s"
          % (sysm.cpu.pc, " ".join("%02X" % m for m in sysm.cpu.mpr)))
    print()
    print("first 20 BIOS calls with work area:")
    for st, name, wa, pc in calls[:20]:
        print("   step %7d %-10s wa=%s -> pc=%04X"
              % (st, name, {k: hex(v) for k, v in wa.items()}, pc))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    print()
    print("VRAM dump:", sysm.dump_vram(args.out + "_vram.bin"))
    print("CRAM dump:", sysm.dump_cram(args.out + "_cram.bin"))
    nz = sum(1 for x in sysm.vram if x)
    print("VRAM non-zero bytes: %d" % nz)


if __name__ == "__main__":
    main()
