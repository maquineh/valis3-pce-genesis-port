"""Try to align the STG map word region with the captured Stage 2 BAT.

The STG tile data uses a bank layout: VRAM bank start 0x100+k*0x80 maps to
block tile 0x100+k*0x93.  We build that mapping by content matching against
the live VRAM, convert the 0x27C8..0x6E40 word region to VRAM tile indices,
and look for the longest common run with the captured BAT.
"""
import sys
sys.path.insert(0, 'tools')
import numpy as np
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
v = parse(decompress(STATE))
vram = v['VRAM'][2]
w = np.frombuffer(vram, dtype='<u2')
d = open('build/extracted/data/track_02.bin', 'rb').read()
base = 344 * 2352 + 16
blk = d[base:base + 0x14000]
TILES = 0x6E40


def block_tile_off(t):
    if t < 0x100:
        return None
    k = (t - 0x100) // 0x80
    within = (t - 0x100) % 0x80
    if within >= 0x40:
        return None
    bt = 0x100 + k * 0x93 + within
    off = TILES + (bt - 0x100) * 32
    return off if off + 32 <= len(blk) else None


# content map block tile -> VRAM tile
vmap = {}
for t in range(0x100, 0x800):
    vmap.setdefault(vram[t * 32:(t + 1) * 32], []).append(t)
b2v = {}
for t in range(0x100, 0x800):
    off = block_tile_off(t)
    if off is None:
        continue
    hit = vmap.get(blk[off:off + 32])
    if hit:
        b2v[t] = hit[0]
print('b2v mapped', len(b2v), 'of', 0x700)

# convert the map region to VRAM-order words
region = blk[0x27C8:0x6E40]
rw = np.frombuffer(region, dtype='<u2')
conv = np.full(len(rw), 0xFFFF, dtype=np.uint16)
for i, x in enumerate(rw):
    t = x & 0xFFF
    if t in b2v:
        conv[i] = ((x >> 12) << 12) | b2v[t]
print('converted', int((conv != 0xFFFF).sum()), 'of', len(conv))

# longest common run between conv and BAT bottom half (row-major 64)
bat = w[2048:4096]
# search conv for long runs of bat
best = (0, 0, 0)
for off in range(0, len(bat) - 8):
    # find how many consecutive words of bat[off:] appear in conv
    pat = bat[off:off + 8]
    hits = np.where(np.lib.stride_tricks.sliding_window_view(conv, 8) == pat)[0]
    if len(hits):
        for h in hits[:1]:
            ln = 0
            while off + ln < len(bat) and h + ln < len(conv) and bat[off + ln] == conv[h + ln]:
                ln += 1
            if ln > best[0]:
                best = (ln, off, int(h))
print('best run: %d words  bat_off=%d conv_off=%05X' %
      (best[0], best[1], (best[2] * 2 + 0x27C8) if best[0] else 0))
# also direct 16-bit equality count in the first 2048 words for a few offsets
for start in (0, 0x400, 0x800, 0xC00, 0x1000, 0x2000):
    seg = conv[start:start + 2048]
    if len(seg) == 2048:
        eq = int((seg == bat).sum())
        print('conv[%05X:+2048] == bat words: %d/2048' % (start * 2 + 0x27C8, eq))
