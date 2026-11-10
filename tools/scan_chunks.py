b = open('build/extracted/data/track_02.bin', 'rb').read()
ZP = {0xF8: 'al', 0xF9: 'ah', 0xFA: 'bl', 0xFB: 'bh',
      0xFC: 'cl', 0xFD: 'ch', 0xFE: 'dl', 0xFF: 'dh'}
CHUNKS = [(988, 'ACT text'), (1000, 'code'), (1020, 'code'), (1040, 'ACT text'),
          (1060, 'code'), (1080, 'ACT text'), (1120, 'code'), (1128, 'OMAKE text')]

def decode(data, site):
    p = {}
    i = site - 1
    while i > site - 48 and i >= 0:
        if data[i] == 0x85 and data[i + 1] in ZP and i >= 2 and data[i - 2] == 0xA9:
            p.setdefault(ZP[data[i + 1]], data[i - 1])
            i -= 3
            continue
        if data[i] == 0x64 and data[i + 1] in ZP:
            p.setdefault(ZP[data[i + 1]], 0)
            i -= 2
            continue
        i -= 1
    return p

for sec, label in CHUNKS:
    data = b''.join(b[(sec + i) * 2352 + 16:(sec + i) * 2352 + 16 + 2048]
                    for i in range(4))
    print('=== %d %s ===' % (sec, label))
    for off in range(len(data) - 3):
        if data[off] == 0x20 and data[off + 1] in (0x09, 0x0F) and data[off + 2] == 0xE0:
            p = decode(data, off)
            sector = (p.get('cl', 0) << 16) | (p.get('ch', 0) << 8) | p.get('dl', 0)
            dest = (p.get('bh', 0) << 8) | p.get('bl', 0)
            print('  +$%04X %s sector=%d count=%s dest=$%04X dh=%02X'
                  % (off, 'read' if data[off + 1] == 9 else 'exec',
                     sector, p.get('al'), dest, p.get('dh', 0)))
