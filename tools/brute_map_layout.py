"""Brute-force map layouts: find the STG word region layout matching the BAT."""
import sys
sys.path.insert(0, 'tools')
import numpy as np
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
v = parse(decompress(STATE))
vram = v['VRAM'][2]
w = np.frombuffer(vram, dtype='<u2')
bat = (w[2048:4096] & 0x0FFF).astype(np.int32)
d = open('build/extracted/data/track_02.bin', 'rb').read()
base = 344 * 2352 + 16
blk = d[base:base + 0x14000]
bw = np.frombuffer(blk, dtype='<u2').astype(np.int32)
map_start = 0x27C8 // 2
map_end = 0x6E40 // 2
seg = bw[map_start:map_end]
print('segment words', len(seg), 'target', len(bat))

best = []
for W in (32, 34, 40, 64):
    H = len(bat) // W
    if len(bat) % W:
        continue
    for order in ('row', 'col'):
        for flip in (False, True):
            if order == 'row':
                need = W * H
            else:
                need = W * H
            for s in range(0, len(seg) - need, 0x20):
                if order == 'row':
                    g = seg[s:s + need].reshape(H, W)
                else:
                    g = seg[s:s + need].reshape(W, H).T
                tgt = bat.reshape(H, W)
                if flip:
                    g = g[::-1]
                eq = int((g == tgt).sum())
                if eq > 0:
                    best.append((eq, W, order, flip, s * 2 + 0x27C8))
best.sort(reverse=True)
print('best layouts:')
for b in best[:15]:
    print('  %4d/%d  W=%d %s flip=%s off=%05X' % (b[0], len(bat), b[1], b[2], b[3], b[4]))
