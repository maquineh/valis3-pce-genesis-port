#!/usr/bin/env python3
"""Fine-grained map of non-zero / code-like regions in a data track."""
import sys


def main():
    path = sys.argv[1]
    b = open(path, "rb").read()
    print("%s (%d bytes)" % (path, len(b)))
    BLK = 4096
    regions = []
    cur = None
    for off in range(0, len(b), BLK):
        blk = b[off:off + BLK]
        nz = sum(1 for x in blk if x != 0)
        frac = nz / len(blk)
        active = frac > 0.02
        if active and cur is None:
            cur = [off, off + BLK, frac]
        elif active:
            cur[1] = off + BLK
            cur[2] = max(cur[2], frac)
        else:
            if cur:
                regions.append(tuple(cur))
            cur = None
    if cur:
        regions.append(tuple(cur))
    for s, e, f in regions:
        print("  $%06X - $%06X  (%6d bytes)  maxnonzerofrac %.2f" % (s, e, e - s, f))


if __name__ == "__main__":
    main()
