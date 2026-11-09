#!/usr/bin/env python3
"""Static survey of the PCE CD data tracks: strings, entropy, 65C02 code hunt."""
import math
import os
import sys
from collections import Counter

DIR = "build/extracted/data"


def entropy(b):
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def strings(b, minlen=3):
    """Extract printable ASCII and Shift-JIS-ish (double byte) strings."""
    out = []
    i = 0
    n = len(b)
    while i < n:
        # ASCII run
        if 0x20 <= b[i] < 0x7F:
            j = i
            while j < n and 0x20 <= b[j] < 0x7F:
                j += 1
            if j - i >= minlen:
                out.append((i, "asc", b[i:j].decode("ascii")))
            i = j
            continue
        # Shift-JIS double byte run (0x81-0x9F, 0xE0-0xEF lead)
        if 0x81 <= b[i] <= 0x9F or 0xE0 <= b[i] <= 0xEF:
            j = i
            ok = True
            while j + 1 < n and (0x81 <= b[j] <= 0x9F or 0xE0 <= b[j] <= 0xEF) and 0x40 <= b[j + 1] <= 0xFC:
                j += 2
            if j > i:
                try:
                    s = b[i:j].decode("shift_jis")
                    out.append((i, "sjis", s))
                except UnicodeDecodeError:
                    out.append((i, "sjis?", b[i:j].hex()))
                i = j
                continue
            i += 1
            continue
        i += 1
    return out


def code_score(b, base_off=0):
    """Heuristic HuC6280 code detector: fraction of 'plausible' opcode byte pairs."""
    # opcodes that appear frequently in 65C02 code (opcode, value)
    OPS = {
        0x4C, 0x6C, 0x20, 0x60, 0x40, 0xEA, 0xAD, 0x8D, 0x9D, 0x99, 0x9C, 0x8C,
        0xA9, 0xA2, 0xA0, 0x85, 0x84, 0x86, 0x95, 0x94, 0x8A, 0x98, 0x48, 0x68,
        0x78, 0x18, 0xD8, 0x58, 0x38, 0xF8, 0xB8, 0xE8, 0xC8, 0xCA, 0x88, 0x0A,
        0x4A, 0x2A, 0x6A, 0xAA, 0xA8, 0x8E, 0x9E, 0x90, 0xB0, 0xF0, 0x30, 0xD0,
        0x10, 0x50, 0x70, 0x24, 0x2C, 0x4C, 0x8A, 0xE0, 0xC0, 0xC9, 0xE9, 0x29,
        0x09, 0x49, 0x69, 0x0D, 0x2D, 0x4D, 0x6D, 0x8D, 0xAD, 0xCD, 0xED, 0x1D,
        0x3D, 0x5D, 0x7D, 0x9D, 0xBD, 0xDD, 0xFD, 0x05, 0x15, 0x25, 0x35, 0x45,
        0x55, 0x65, 0x75, 0xA5, 0xB5, 0xC5, 0xD5, 0xE5, 0xF5, 0x01, 0x21, 0x41,
        0x61, 0x81, 0xA1, 0xC1, 0xE1, 0x11, 0x31, 0x51, 0x71, 0x91, 0xB1, 0xD1,
        0xF1,
    }
    if len(b) < 64:
        return 0.0
    good = 0
    total = 0
    for i in range(0, len(b) - 2, 1):
        if b[i] in OPS:
            good += 1
        total += 1
    return good / max(total, 1)


def main():
    files = sorted(os.listdir(DIR))
    for fn in files:
        path = os.path.join(DIR, fn)
        b = open(path, "rb").read()
        print("=" * 78)
        print("%s  %d bytes  entropy %.2f" % (fn, len(b), entropy(b)))
        for off, kind, s in strings(b, minlen=4):
            if kind == "asc" and len(s) >= 4:
                print("  ASC  @%06X %r" % (off, s))
            elif kind.startswith("sjis"):
                print("  SJIS @%06X %r" % (off, s))


if __name__ == "__main__":
    main()
