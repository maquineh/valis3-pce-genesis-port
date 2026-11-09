#!/usr/bin/env python3
"""Decode HuC6280 block-transfer instructions (TII/TDD/TIN/TIA/TAI) and
immediate VDC stores (ST0/ST1/ST2), plus VCE palette uploads.

Block transfer encoding: opcode, SS, ss, DD, dd, LL, ll
    src = SS:ss   dst = DD:dd   length = LL:ll bytes
    TIA dest alternates low/high byte of the 16-bit dest -> used to stream
    words into VCE colour data ($0404) and VDC VRAM data ($0002).
"""
import re
import sys

BLOCK = {0x73: "TII", 0xC3: "TDD", 0xD3: "TIN", 0xE3: "TIA", 0xF3: "TAI"}


def scan(path, start=0x4000, end=0x8000):
    b = open(path, "rb").read()
    out = []
    for pc in range(start, min(end, len(b) - 7)):
        op = b[pc]
        if op in BLOCK:
            SS, ss, DD, dd, LL, ll = b[pc + 1:pc + 7]
            src = (SS << 8) | ss
            dst = (DD << 8) | dd
            ln = (LL << 8) | ll
            out.append((pc, BLOCK[op], src, dst, ln))
    return out


def main():
    path = sys.argv[1]
    start = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x4000
    end = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x8000
    for pc, mn, src, dst, ln in scan(path, start, end):
        note = ""
        if dst == 0x0404:
            note = "  <== VCE palette data (colour upload)"
        elif dst == 0x0002:
            note = "  <== VDC VRAM data (tile upload)"
        elif dst == 0x0000:
            note = "  (VDC register select)"
        print("$%04X: %s $%04X, $%04X, $%04X%s" % (pc, mn, src, dst, ln, note))


if __name__ == "__main__":
    main()
