import sys

b = open('build/extracted/data/track_02.bin', 'rb').read()
sectors = list(range(976, 988))
data = b''.join(b[s * 2352 + 16:s * 2352 + 16 + 2048] for s in sectors)
open('build/overlay976.bin', 'wb').write(data)

ZP = {0xF8: 'al', 0xF9: 'ah', 0xFA: 'bl', 0xFB: 'bh',
      0xFC: 'cl', 0xFD: 'ch', 0xFE: 'dl', 0xFF: 'dh'}
BIOS = {0xE009: 'cd_read', 0xE00F: 'cd_exec', 0xE006: 'cd_base',
        0xE012: 'cd_play', 0xE018: 'cd_pause', 0xE015: 'cd_search'}

def params(site):
    p = {}
    i = site - 1
    while i > site - 48 and i >= 0:
        op = data[i] if i < len(data) else 0
        if op == 0x85 and i + 1 < len(data) and data[i + 1] in ZP:
            if i >= 2 and data[i - 2] == 0xA9:
                p.setdefault(ZP[data[i + 1]], data[i - 1])
                i -= 3
                continue
        if op == 0x64 and i + 1 < len(data) and data[i + 1] in ZP:
            p.setdefault(ZP[data[i + 1]], 0)
            i -= 2
            continue
        i -= 1
    return p

print('overlay size', len(data), 'loaded at logical $4000')
for off in range(len(data) - 3):
    if data[off] == 0x20 and data[off + 1] == 0x0F and data[off + 2] == 0xE0:
        p = params(off)
        sec = (p.get('cl', 0) << 16) | (p.get('ch', 0) << 8) | p.get('dl', 0)
        dest = (p.get('bh', 0) << 8) | p.get('bl', 0)
        print('$%04X (overlay +$%04X) cd_exec sec=%d count=%s dest=$%04X dh=%02X'
              % (0x4000 + off, off, sec, p.get('al'), dest, p.get('dh', 0)))
    if data[off] == 0x20 and data[off + 1] == 0x09 and data[off + 2] == 0xE0:
        p = params(off)
        sec = (p.get('cl', 0) << 16) | (p.get('ch', 0) << 8) | p.get('dl', 0)
        dest = (p.get('bh', 0) << 8) | p.get('bl', 0)
        print('$%04X (overlay +$%04X) cd_read sec=%d count=%s dest=$%04X dh=%02X'
              % (0x4000 + off, off, sec, p.get('al'), dest, p.get('dh', 0)))
