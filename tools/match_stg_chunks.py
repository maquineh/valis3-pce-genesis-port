"""Match STG 8x8 chunks to the captured BAT using content-based tile mapping."""
import sys
sys.path.insert(0, 'tools')
import numpy as np
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
v = parse(decompress(STATE))
vram = v['VRAM'][2]
d = open('build/extracted/data/track_02.bin', 'rb').read()
base = 344 * 2352 + 16
blk = d[base:base + 0x14000]
T = 0x6E40

# vram tile -> content
vmap = {}
for t in range(0x100, 0x800):
    vmap.setdefault(vram[t * 32:(t + 1) * 32], []).append(t)
# block tile index -> first matching VRAM tile
bt2v = {}
for i in range((len(blk) - T) // 32):
    data = blk[T + i * 32:T + (i + 1) * 32]
    hit = vmap.get(data)
    if hit:
        bt2v[0x100 + i] = hit[0]
print('bt2v mapped', len(bt2v), 'of', (len(blk) - T) // 32)

w = np.frombuffer(vram, dtype='<u2')
# block chunks every 0x80 bytes from 0x27C8
chunks = []
off = 0x27C8
while off + 0x80 <= 0x6E40:
    words = [blk[off + i * 2] | (blk[off + i * 2 + 1] << 8) for i in range(64)]
    conv = [((x >> 12) << 12) | bt2v[x & 0xFFF] if (x & 0xFFF) in bt2v else None
            for x in words]
    chunks.append((off, conv))
    off += 0x80
print('chunks', len(chunks))

# BAT 8x8 windows, scored by how many of 64 tiles match (content indices)
bat = w[2048:4096]
best = []
for by in range(25):
    for bx in range(57):
        target = [int(bat[(by + y) * 64 + bx + x]) for y in range(8) for x in range(8)]
        for coff, conv in chunks:
            sc = sum(1 for a, b in zip(target, conv) if b is not None and a == b)
            if sc >= 48:
                best.append((sc, by + 32, bx, coff))
best.sort(reverse=True)
print('top matches (score, bat_row, bat_col, chunk_off):')
for b in best[:20]:
    print('  ', b)
