"""Map the internal structure of a stage segment block."""
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()


def classify(off, n=512):
    blk = b[off:off + n]
    nz = sum(1 for x in blk if x != 0)
    if nz == 0:
        return 'ZERO'
    ok = sum(1 for i in range(n // 2) if blk[i * 2 + 1] in (0, 1))
    if ok == n // 2:
        return 'PAL'
    same = tot = 0
    for i in range(0, n - 31, 32):
        t = blk[i:i + 32]
        if len(t) < 32:
            break
        for r in range(8):
            row = []
            for x in range(8):
                bit = 0x80 >> x
                v = ((1 if t[r * 2] & bit else 0) | (2 if t[r * 2 + 1] & bit else 0)
                     | (4 if t[16 + r * 2] & bit else 0)
                     | (8 if t[16 + r * 2 + 1] & bit else 0))
                row.append(v)
            for a, c in zip(row, row[1:]):
                tot += 1
                if a == c:
                    same += 1
    if same / max(tot, 1) > 0.35:
        return 'TILE'
    words = [blk[i] | (blk[i + 1] << 8) for i in range(0, n // 2 * 2, 2)]
    t = [w & 0xFFF for w in words]
    if max(t) - min(t) < 2048 and len(set(t)) > 20:
        return 'MAP?'
    if nz < n * 0.5:
        return 'sparse'
    return 'data'


sec = int(sys.argv[1], 0) if len(sys.argv) > 1 else 344
start = sec * 2352
end = start + 40 * 2352
print('stage block sector %d: $%06X-$%06X (%d bytes)'
      % (sec, start, end, end - start))
print('%-10s %-6s %s' % ('offset', 'kind', 'extra'))
from collections import Counter
runs = []
cur = None
for off in range(start, end, 512):
    k = classify(off)
    if cur is None or cur[0] != k:
        if cur:
            runs.append(cur)
        cur = [k, off, off + 512]
    else:
        cur[2] = off + 512
if cur:
    runs.append(cur)
for k, s, e in runs:
    print('$%06X-$%06X  %-6s %6d bytes' % (s, e, k, e - s))
