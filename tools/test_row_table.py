"""Test the 0x7100 table as 45 x 24-bit row offsets against STG stream bases."""
import sys
sys.path.insert(0, 'tools')

cdr = open('build/mc0_cdram.bin', 'rb').read()
offsets = []
p = 0x7100
while p + 3 <= 0x7187:
    offsets.append(cdr[p] | (cdr[p + 1] << 8) | (cdr[p + 2] << 16))
    p += 3
print('entries', len(offsets), 'first', [hex(x) for x in offsets[:8]],
      'last', [hex(x) for x in offsets[-4:]])

cases = [
    ('build/extracted/data/track_02.bin', 304, 'STG1A'),
    ('build/extracted/data/track_02.bin', 344, 'STG2A'),
    ('build/extracted/data/track_02.bin', 384, 'STG2B'),
    ('build/extracted/data/track_02.bin', 464, 'STG3A'),
]
for track, sector, name in cases:
    disc = open(track, 'rb').read()
    base = sector * 2352 + 16
    blk = disc[base:base + 0x14000]
    best = []
    for B in range(0, len(blk) - offsets[-1] - 1, 0x10):
        good = 0
        for i in range(len(offsets) - 1):
            a = B + offsets[i]
            b = B + offsets[i + 1]
            if b <= a or b > len(blk) or b - a > 128:
                continue
            seg = blk[a:b]
            if seg[-1] == 0 and all(x < 0x80 for x in seg[:-1]):
                good += 1
        if good > 0:
            best.append((good, B))
    best.sort(reverse=True)
    print('%s best bases:' % name, [(g, hex(B)) for g, B in best[:8]])
