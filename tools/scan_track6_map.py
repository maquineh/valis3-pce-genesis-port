import sys
from collections import Counter

b = open('build/track_06_payload.bin', 'rb').read()
ROWS, COLS = 24, 32
GRID = ROWS * COLS * 2
cands = []
for off in range(0, len(b) - GRID, 0x100):
    words = [b[off + i * 2] | (b[off + i * 2 + 1] << 8) for i in range(ROWS * COLS)]
    tiles = [w & 0xFFF for w in words]
    pals = [w >> 12 for w in words]
    inrange = sum(1 for t in tiles if 0x100 <= t < 0x300)
    distinct = len(set(tiles))
    # prefer a narrow tile range and few palettes
    if inrange >= 500 and distinct <= 300:
        cands.append((inrange, distinct, off, Counter(pals)))
cands.sort(key=lambda x: (-x[0], x[1]))
print('candidates', len(cands))
for i, (n, d, off, pals) in enumerate(cands[:12]):
    print('%2d off=%06X inrange=%d distinct=%d pals=%s'
          % (i, off, n, d, dict(sorted(pals.items()))))
