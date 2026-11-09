#!/usr/bin/env python3
"""Find MPR bank-switch sequences (LDA #imm ; TAM/TMA) and CL writes in code."""
import sys


def main():
    path = sys.argv[1]
    start = int(sys.argv[2], 0)
    end = int(sys.argv[3], 0)
    b = open(path, "rb").read()
    print("== TAM/TMA bank switches ==")
    for off in range(max(start, 2), min(end, len(b)) - 2):
        if b[off - 2] == 0xA9 and b[off] in (0x53, 0x43):
            mn = "TAM" if b[off] == 0x53 else "TMA"
            print("  %04X: LDA #$%02X ; %s #$%02X" % (off - 2, b[off - 1], mn, b[off + 1]))
    print("== writes to zp $FC/$F8-$FF (BIOS work area) ==")
    for off in range(start, min(end, len(b)) - 2):
        op = b[off]
        if op in (0x85, 0x64, 0x86, 0x84, 0x9C) and b[off + 1] in (0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF):
            mn = {0x85: "STA", 0x64: "STZ", 0x86: "STX", 0x84: "STY", 0x9C: "STZ"}[op]
            print("  %04X: %s $%02X   (ctx: %s)" % (off, mn, b[off + 1],
                                                     b[max(0, off - 4):off + 2].hex()))


if __name__ == "__main__":
    main()
