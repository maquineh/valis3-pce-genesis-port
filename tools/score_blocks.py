"""Score (map, tile block) pairs by how many cells resolve to solid tiles.

A correct pairing puts real terrain in front of the viewer: flat ground, sky
and platform surfaces are single-colour 8x8 tiles.  Dithered artwork and
scattered object data resolve to multi-value tiles instead, so the fraction of
solid cells separates the two.

Calibrated on the known-good stage 1 screen.
"""
import sys

sys.path.insert(0, 'tools')
from pce_gfx import bg_tile_pixels  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
GRID = 0x600
CELLS = 768

# (file offset, byte size, VDC word, loader site)
BLOCKS = [
    (0x006E40, 0xA000, 0x1000, "$49CD"),
    (0x016F80, 0x2000, 0x7000, "$49F0"),
    (0x019440, 0xC000, 0x1000, "$237605 sec $2C"),
    (0x01AFD0, 0xC000, 0x1000, "$2553C5 sec $2F"),
    (0x01B900, 0xA000, 0x3000, "$235133 sec $30"),
    (0x01DDC0, 0x6000, 0x2000, "$23255B sec $34"),
    (0x0270C0, 0x2000, 0x5000, "$23259D sec $44"),
    (0x2AA2C0, 0x6000, 0x5000, "$2A1072 sec $4A4"),
    (0x2C5BC0, 0xC000, 0x1000, "$287BEC sec $4D4"),
    (0x2D81C0, 0x8000, 0x1000, "$287D4C sec $4F4"),
    (0x2EA7C0, 0x6000, 0x5000, "$22BE32 sec $514"),
    (0x000000, 0xC000, 0x2000, "$230792 sec 0"),
]

# the empirically verified stage-1 pairing, used as the calibration point
KNOWN = (0x019440, 0x200, "$237605 sec $2C base $200")


def score(b, map_off, off, base, ntiles):
    solid = 0
    resolved = 0
    for i in range(CELLS):
        w = b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8)
        t = w & 0xFFF
        d = t - base
        if d < 0 or d >= ntiles:
            continue
        src = off + d * 32
        if src < 0 or src + 32 > len(b):
            continue
        resolved += 1
        px = bg_tile_pixels(b[src:src + 32])
        first = px[0][0]
        if all(px[r][x] == first for r in range(8) for x in range(8)):
            solid += 1
    return solid / max(resolved, 1), resolved / CELLS


def main():
    b = open(TRACK, 'rb').read()
    print('calibration on the known stage-1 screen $17FF90:')
    ref = None
    for off, base, label in [KNOWN] + [(o, wo // 16, l) for o, s, wo, l in BLOCKS]:
        size = {KNOWN[0]: 0xC000}.get(off)
        if size is None:
            for o2, s2, w2, l2 in BLOCKS:
                if o2 == off:
                    size = s2
                    break
        f, r = score(b, 0x17FF90, off, base, size // 32)
        print('   %-28s solid=%.3f resolved=%.2f' % (label, f, r))
        if label == KNOWN[2]:
            ref = f
    print('   -> calibration solid ratio for a correct pairing: %.3f' % ref)
    print()

    start = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x184190
    count = int(sys.argv[2], 0) if len(sys.argv) > 2 else 40
    print('scanning %d grid slots from $%06X:' % (count, start))
    print('%-9s %-28s %7s %7s' % ('slot', 'best block', 'solid', 'resolv'))
    for k in range(count):
        off = start + k * GRID
        if off + GRID > len(b):
            break
        rows = []
        for bo, size, word, label in BLOCKS:
            base = word // 16
            f, r = score(b, off, bo, base, size // 32)
            rows.append((f, r, label, base))
        rows.sort(reverse=True)
        f, r, label, base = rows[0]
        flag = ' <<<' if f >= (ref or 0) * 0.7 and r > 0.9 else ''
        print('$%06X %-28s %7.3f %7.2f%s' % (off, label, f, r, flag))


if __name__ == '__main__':
    main()
