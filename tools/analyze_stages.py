"""Analyse each stage segment header and map region on the disc.

Every 40-sector block starts with a frame header, a short parameter area and
an ASCII stage label ("STG1A", "STG2A", ...).  The first parameter is a
sequence number 00..09, so the disc literally enumerates the ten stage
segments.  This tool prints the headers and then, for each block, scans the
0x600 map grid for the screens whose tile indices concentrate in a narrow
range (the signature of a real playfield BAT).
"""
import sys

TRACK = 'build/extracted/data/track_02.bin'
GRID = 0x600
CELLS = 768

b = open(TRACK, 'rb').read()

# (sector, label) - read straight off the disc
BLOCKS = [
    (304, 'STG1A'), (344, 'STG2A'), (384, 'STG2B'), (424, 'STG2C'),
    (464, 'STG3A'), (504, 'STG3B'), (544, 'STG4A'), (584, 'STG4B'),
    (624, 'STG4C'), (664, 'STG5A'),
]

print('%-6s %-8s %-9s %s' % ('sect', 'label', 'file', 'header parameters'))
for sec, label in BLOCKS:
    off = sec * 2352 + 16
    raw = b[off:off + 40]
    # label starts after a 2-byte code and a 1-byte flag
    li = raw.find(label.encode())
    params = raw[li + len(label) + 10:li + len(label) + 26] if li >= 0 else b''
    print('%6d %-8s $%06X  %s' % (sec, label, sec * 2352, params.hex()))
print()

print('map slots per stage block (0x600 grid, tiles concentrated in $200-$2FF):')
for sec, label in BLOCKS:
    start = sec * 2352
    end = start + 40 * 2352
    found = []
    off = start
    while off + GRID <= end:
        n = 0
        distinct = set()
        for i in range(CELLS):
            w = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
            t = w & 0xFFF
            if 0x200 <= t <= 0x2FF:
                n += 1
            distinct.add(t)
        conc = n / CELLS
        if conc >= 0.15 and len(distinct) >= 40:
            found.append((off, conc, len(distinct)))
        off += GRID
    print('  %-8s sector %3d  $%06X-$%06X : %d map slots'
          % (label, sec, start, end, len(found)))
    for off, conc, d in found[:8]:
        print('        $%06X concentration=%.2f distinct=%d' % (off, conc, d))
