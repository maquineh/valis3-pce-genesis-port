#!/usr/bin/env python3
"""Map each PCE data track: code-likeness histogram + structural regions.

Better 65C02 code model than raw opcode density:
  * BRK (0x00) runs are data/zero fill, not code
  * count characteristic PCE idioms: STA $0002/$0003 (VDC), LDA $0002,
    bank ops TAM/TAI/TMA, JSR/JMP/RTS clustering, and immediate loads
"""
import os
import sys
from collections import Counter

DIR = "build/extracted/data"
BLK = 4096


def block_stats(b):
    n = len(b)
    codesig = 0          # typical code byte pairs
    zeros = 0
    for i in range(0, n - 2, 1):
        op = b[i]
        if op == 0x00:
            zeros += 1
        if op in (0x8D, 0xAD, 0x2C, 0x4C, 0x6C, 0x20, 0x60, 0x9D, 0x99,
                  0xBD, 0xB9, 0xDD, 0xD9, 0xFD, 0xF9, 0x1D, 0x19, 0x3D,
                  0x39, 0x5D, 0x59, 0x7D, 0x79):
            codesig += 1
    return codesig, zeros


def analyze(path, label):
    b = open(path, "rb").read()
    print("== %s  %d bytes (%.2f MiB)" % (label, len(b), len(b) / 1048576))
    rows = []
    for off in range(0, len(b), BLK):
        blk = b[off:off + BLK]
        c = Counter(blk)
        top = c.most_common(3)
        codesig, zeros = block_stats(blk)
        rows.append((off, codesig / max(len(blk), 1), zeros / max(len(blk), 1),
                     len(c), top))
    # print a coarse profile: average codesig ratio and distinct-byte count
    # per 64 KiB super-block, to reveal region boundaries
    SB = 65536
    for off in range(0, len(b), SB):
        seg = [r for r in rows if r[0] // SB == off // SB]
        if not seg:
            continue
        avg_code = sum(r[1] for r in seg) / len(seg)
        avg_zero = sum(r[2] for r in seg) / len(seg)
        avg_dist = sum(r[3] for r in seg) / len(seg)
        print("  $%06X  codesig %.3f  zero %.3f  distinct %.0f  (%d KiB)"
              % (off, avg_code, avg_zero, avg_dist, off // 1024))
    return b


if __name__ == "__main__":
    files = sys.argv[1:] or sorted(os.path.join(DIR, f) for f in os.listdir(DIR))
    for p in files:
        analyze(p, os.path.basename(p))
