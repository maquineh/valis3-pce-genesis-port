#!/usr/bin/env python3
"""Resolve logical PC Engine addresses to file offsets in track 2.

VERIFIED: the System Card's cd_exec at $4CA0 loads 8 sectors starting at
sector $20 (= file offset $12600) to logical $4000.  That overlay stays
resident and holds the engine's core routines, so every absolute address the
game's loader code refers to can be resolved with:

    file_offset = 0x12600 + (logical_address - 0x4000)

The mapping is proven by three independent routines that are only reachable
through it (all produce coherent 6502):

    logical $8660 (file $16C60)  decompressor: BSR + STA ($FA) + INC $FA loop
    logical $6C39 (file $15239)  entity routine: indexed table reads ($2A16,X)
    logical $8CD9 (file $16CD9)  CD drive control: writes I/O $1802/$1808/$180D

Usage:
    python3 tools/logical_to_file.py $8660 $8652 $8CD9 $6C39
    python3 tools/logical_to_file.py --disasm $8660 40
"""
import sys

TRACK = "build/extracted/data/track_02.bin"
OVERLAY_FILE = 0x12600        # sector $20, loaded by cd_exec at $4CA0
OVERLAY_LOGICAL = 0x4000
OVERLAY_SECTORS = 8


def to_file(logical):
    return OVERLAY_FILE + (logical - OVERLAY_LOGICAL)


def to_logical(file_off):
    return OVERLAY_LOGICAL + (file_off - OVERLAY_FILE)


def in_overlay(file_off):
    end = OVERLAY_FILE + OVERLAY_SECTORS * 2352
    return OVERLAY_FILE <= file_off < end


def main():
    sys.path.insert(0, "tools")
    from disasm6280 import disasm_one

    args = sys.argv[1:]
    disasm = False
    if args and args[0] == "--disasm":
        disasm = True
        args = args[1:]
    count = int(args[1], 0) if disasm and len(args) > 1 else 24
    args = args[:1] if disasm else args

    b = open(TRACK, "rb").read()
    if not args:
        print(__doc__)
        return
    for a in args:
        logical = int(a.replace("$", "0x"), 16) if not a.isdigit() \
            else int(a, 16)
        f = to_file(logical)
        inside = "inside the resident overlay" if in_overlay(f) \
            else "OUTSIDE the resident overlay"
        print("logical $%04X -> file $%06X (%s)" % (logical, f, inside))
        if disasm:
            pc = f
            for _ in range(count):
                txt, n = disasm_one(b, pc)
                print("   $%06X (logical $%04X): %s"
                      % (pc, to_logical(pc), txt or ".byte $%02X" % b[pc]))
                pc += n


if __name__ == "__main__":
    main()
