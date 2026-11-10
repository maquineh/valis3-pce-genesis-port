"""Emulate the real boot chain: IPL -> boot block -> cd_exec overlay -> game."""
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
    disc = Disc(TRACK)
    emu = PCESystem(disc, verbose=False)

    # The System Card IPL loads the boot block into work RAM.  The game's boot
    # code then runs at $23E0 with MPR0 = $F8 so it stays executable.
    blk = bytearray()
    for s in range(8):
        blk += disc.read_sector(s)
    for i, byte in enumerate(blk):
        emu.mem[(0xF8 << 13) + i] = byte

    emu.cpu.mpr = [0xF8, 0xF8, 0, 0, 0, 0, 0, 0]
    emu.cpu.pc = 0x23E0
    emu.cpu.sp = 0xFF

    def wr(addr, val):
        emu.mem[emu.cpu.phys(addr)] = val

    # IPL parameters: the first cd_read loads sector 1 -> $4000.
    # $3011=al, $3012=bl, $3013=bh are copied to the work area by the boot
    # code, and the sector number ($FC-$FE) must already be there.
    wr(0x3011, 0x01)
    wr(0x3012, 0x00)
    wr(0x3013, 0x40)
    wr(0xFC, 0x00)     # cl
    wr(0xFD, 0x00)     # ch
    wr(0xFE, 0x01)     # dl  -> sector 1
    # and the game's entry point is the end of the boot block
    wr(0x2007, 0x00)
    wr(0x2008, 0x24)

    transfers = []
    for _ in range(2_000_000):
        pc0 = emu.cpu.pc
        try:
            mn = emu.cpu.step()
        except StopIteration as e:
            transfers.append(("STOP", str(e)))
            break
        except RuntimeError as e:
            transfers.append(("ERR", str(e)))
            break
        emu.steps += 1
        if mn in ("JMP", "JSR") and len(transfers) < 80:
            transfers.append((emu.steps, pc0, mn, emu.cpu.pc))
        if mn in ("JMP", "JSR", "RTS", "RTI") and len(transfers) >= 80:
            break

    print("== boot chain ==")
    for t in transfers:
        if t[0] in ("STOP", "ERR"):
            print("  %s: %s" % t)
        else:
            print("  step %8d  $%04X %s -> $%04X" % t)
    print("steps         : %d" % emu.steps)
    print("BIOS calls    : %d" % len(emu.bios_calls))
    from collections import Counter
    for name, n in Counter(n for _, n in emu.bios_calls).most_common():
        print("   %-12s %d" % (name, n))
    print("MPR           : %s" % " ".join("%02X" % m for m in emu.cpu.mpr))
    print("VRAM writes   : %d" % len(emu.vram_writes))
    print("sectors read  : %d distinct %d" %
          (len(disc.reads), len(set(disc.reads))))
    d = open("build/emu_boot_vram.bin", "wb")
    d.write(bytes(emu.vram))
    d.close()
    print("VRAM dumped to build/emu_boot_vram.bin")


if __name__ == "__main__":
    main()
