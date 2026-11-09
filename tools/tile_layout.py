#!/usr/bin/env python3
"""Find the correct PCE 8x8 tile bit-plane layout by testing coherence.

For each candidate layout we decode a region and measure how often neighbouring
pixels share the same colour index. Real graphics have smooth neighbours;
random / mis-decoded data does not.
"""
import itertools
import sys


def decode(blk, order, interleave="row"):
    """blk: 32 bytes. order: permutation of the 4 plane slots.
    interleave 'row': plane pair per row (16 bytes for planes 0/1 then 2/3)
               'block': 8 bytes per plane (0..7, 8..15, 16..23, 24..31)
    """
    rows = []
    if interleave == "row":
        for r in range(8):
            vals = [blk[r * 2], blk[r * 2 + 1], blk[16 + r * 2], blk[16 + r * 2 + 1]]
            # vals[0],[1] are plane pair A; vals[2],[3] pair B
            pix = []
            for x in range(8):
                bit = 0x80 >> x
                v = 0
                if vals[order[0]] & bit:
                    v |= 1
                if vals[order[1]] & bit:
                    v |= 2
                if vals[order[2]] & bit:
                    v |= 4
                if vals[order[3]] & bit:
                    v |= 8
                pix.append(v)
            rows.append(pix)
    else:
        for r in range(8):
            pix = []
            for x in range(8):
                bit = 0x80 >> x
                v = 0
                for p in range(4):
                    if blk[p * 8 + r] & bit:
                        v |= 1 << p
                pix.append(v)
            rows.append(pix)
    return rows


def score(data, off, count, order, interleave):
    same = 0
    total = 0
    for i in range(count):
        base = off + i * 32
        blk = data[base:base + 32]
        if len(blk) < 32:
            break
        rows = decode(blk, order, interleave)
        for r in rows:
            for a, b in zip(r, r[1:]):
                total += 1
                if a == b:
                    same += 1
    return same / max(total, 1)


def main():
    path = sys.argv[1]
    off = int(sys.argv[2], 0)
    count = int(sys.argv[3], 0) if len(sys.argv) > 3 else 512
    data = open(path, "rb").read()
    print("%s @ $%X, %d tiles" % (path, off, count))
    res = []
    for order in itertools.permutations(range(4)):
        res.append((score(data, off, count, order, "row"), order, "row"))
    res.append((score(data, off, count, (0, 1, 2, 3), "block"), tuple(range(4)), "block"))
    res.sort(reverse=True)
    for s, order, mode in res[:8]:
        print("   interleave=%-5s order=%s  neighbour-same %.3f" % (mode, order, s))


if __name__ == "__main__":
    main()
