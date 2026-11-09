#!/usr/bin/env python3
"""Locate PC Engine VDC/VCE register accesses in the extracted data tracks."""
import os
import re
import sys

DIR = "build/extracted/data"
PATS = {
    "STA $0002 (VDC data)": "8d0200",
    "STA $0000 (VDC reg)": "8d0000",
    "STA $0003 (VDC status)": "8d0300",
    "STA $0400 (VCE ctrl)": "8d0004",
    "STA $0402 (VCE idx)": "8d0204",
    "STA $0404 (VCE data)": "8d0404",
    "STA $0005 (SATB DMA)": "8d0500",
    "STA $0006 (SATB)": "8d0600",
    "STA $0007 (BXR)": "8d0700",
    "STA $0008 (BYR)": "8d0800",
    "STA $0009 (CR)": "8d0900",
    "STA $000a (RCR)": "8d0a00",
    "STA $1800-ish CD call": "8d0020",  # rough: any $2000 page store (CD BIOS region)
}


def main():
    files = sys.argv[1:] or sorted(os.path.join(DIR, f) for f in os.listdir(DIR))
    for p in files:
        b = open(p, "rb").read()
        print("== %s" % os.path.basename(p))
        for name, hexs in PATS.items():
            needle = bytes.fromhex(hexs)
            idx = [m.start() for m in re.finditer(re.escape(needle), b)]
            if idx:
                print("   %-24s %4d hits  first: %s" % (
                    name, len(idx), " ".join(hex(i) for i in idx[:8])))


if __name__ == "__main__":
    main()
