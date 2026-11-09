#!/usr/bin/env python3
"""Find VCE palette blocks on the disc: 9-bit RGB words => high byte is 0x00/0x01."""
import os
import sys

DIR = "build/extracted/data"
STEP = 2


def palette_score(b, off, length):
    """Count fraction of 16-bit words whose high byte is 0 or 1 and low byte valid."""
    n = length // 2
    ok = 0
    for i in range(n):
        hi = b[off + i * 2 + 1]
        if hi in (0x00, 0x01):
            ok += 1
    return ok / n if n else 0.0


def main():
    files = sys.argv[1:] or sorted(os.path.join(DIR, f) for f in os.listdir(DIR))
    for p in files:
        b = open(p, "rb").read()
        print("== %s" % os.path.basename(p))
        best = []
        W = 2048  # 1024 words = a full 16x16 palette set
        for off in range(0, len(b) - W, W):
            s = palette_score(b, off, W)
            best.append((s, off))
        best.sort(reverse=True)
        for s, off in best[:6]:
            print("   $%06X palettelike %.3f" % (off, s))


if __name__ == "__main__":
    main()
