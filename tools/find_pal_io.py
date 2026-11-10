#!/usr/bin/env python3
"""Find VCE palette register writes inside a byte range."""
import re
import sys

path = sys.argv[1]
start = int(sys.argv[2], 0)
end = int(sys.argv[3], 0)
b = open(path, "rb").read()
seg = b[start:end]
for pat, name in [(bytes.fromhex("8d0204"), "STA $0402 color-index"),
                  (bytes.fromhex("8d0404"), "STA $0404 color-data"),
                  (bytes.fromhex("8d0304"), "STA $0403 color-index-hi"),
                  (bytes.fromhex("8d0004"), "STA $0400 clock")]:
    idx = [m.start() + start for m in re.finditer(re.escape(pat), seg)]
    print("%-24s %3d hits: %s" % (name, len(idx),
                                  " ".join(hex(i) for i in idx[:12])))
