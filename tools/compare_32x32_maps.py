"""Test: the STG +0x27C8 region holds N 32x32 maps (N = header byte +0x11)."""
import sys
sys.path.insert(0, 'tools')
from extract_state import load, find_var

CASES = [
    ('Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc2',
     'build/extracted/data/track_02.bin', 384, 'STG2B'),
    ('Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc4',
     'build/extracted/data/track_02.bin', 464, 'STG3A'),
]

for state, track, sector, name in CASES:
    d = load(state)
    vram = find_var(d, b'VRAM')
    w = [vram[2 * i] | (vram[2 * i + 1] << 8) for i in range(0x1000)]
    disc = open(track, 'rb').read()
    base = sector * 2352 + 16
    blk = disc[base:base + 0x14000]
    print('===', name, 'header byte +0x11 =', blk[0x11])
    quads = {
        'TL': [w[(0 + y) * 64 + (0 + x)] & 0xFFF for y in range(32) for x in range(32)],
        'TR': [w[(0 + y) * 64 + (32 + x)] & 0xFFF for y in range(32) for x in range(32)],
        'BL': [w[(32 + y) * 64 + (0 + x)] & 0xFFF for y in range(32) for x in range(32)],
        'BR': [w[(32 + y) * 64 + (32 + x)] & 0xFFF for y in range(32) for x in range(32)],
    }
    best = []
    for off in range(0x27C8, 0x6E40 - 0x800 + 1, 0x800):
        src = [blk[off + (y * 32 + x) * 2] | (blk[off + (y * 32 + x) * 2 + 1] << 8)
               for y in range(32) for x in range(32)]
        for qname, q in quads.items():
            eq = sum(1 for a, b in zip([v & 0xFFF for v in src], q) if a == b)
            best.append((eq, qname, off))
    best.sort(reverse=True)
    for b in best[:6]:
        print('  %4d/1024 %s at %05X' % (b[0], b[1], b[2]))
