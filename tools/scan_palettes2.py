#!/usr/bin/env python3
"""Scan data tracks for VCE palette blocks (16-bit words with high byte 0/1)."""
import os
import sys

DIR = "build/extracted/data"


def scan(path, W=512, min_frac=0.85, min_distinct=24):
    b = open(path, "rb").read()
    hits = []
    for off in range(0, len(b) - W, 32):
        ok = 0
        vals = set()
        for i in range(W // 2):
            lo, hi = b[off + i * 2], b[off + i * 2 + 1]
            if hi in (0, 1):
                ok += 1
            vals.add(lo | (hi << 8))
        if ok / (W // 2) >= min_frac and len(vals) >= min_distinct:
            hits.append((off, len(vals), ok / (W // 2)))
    return hits


def main():
    files = sys.argv[1:] or sorted(os.path.join(DIR, f) for f in os.listdir(DIR))
    for p in files:
        hits = scan(p)
        print("== %s : %d candidates" % (os.path.basename(p), len(hits)))
        # merge contiguous candidates
        for off, d, f in hits[:40]:
            print("   $%06X distinct=%3d frac=%.2f" % (off, d, f))


if __name__ == "__main__":
    main()
