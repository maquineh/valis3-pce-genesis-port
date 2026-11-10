b = open('build/extracted/data/track_02_payload.bin', 'rb').read()
base = 304 * 2048
print('block base', hex(base), 'size', hex(40 * 2048))
for off in range(0, 40 * 2048, 0x800):
    ch = b[base + off:base + off + 0x800]
    z = ch.count(0)
    print('+%05X zero %4d/%d  distinct %3d  first %s'
          % (off, z, len(ch), len(set(ch)), ch[:8].hex()))

for mo in (0x29F0, 0x2A00, 0x2800, 0x3000, 0x4000, 0x10000):
    off = base + mo
    if off + 0x600 > len(b):
        continue
    words = [b[off + i * 2] | (b[off + i * 2 + 1] << 8) for i in range(0x300)]
    tiles = [w & 0xFFF for w in words]
    pals = [w >> 12 for w in words]
    from collections import Counter
    print('map +%05X: tile min $%03X max $%03X distinct %d top %s'
          % (mo, min(tiles), max(tiles), len(set(tiles)),
             [(hex(t), c) for t, c in Counter(tiles).most_common(5)]))
    print('   pals', dict(sorted(Counter(pals).items())))
