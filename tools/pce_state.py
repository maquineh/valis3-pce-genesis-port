"""Parse a Mednafen PCE save state (MDFNSVST).

Variable record layout (derived from the real Valis III state):
    [name_len:u8][name][type:u8][size:u24 LE][data]
`size` is the payload size in 256-byte blocks for arrays; scalars use
size=0 and `type` bytes of data (1/2/4/8).
"""
import gzip
import struct


def decompress(path):
    raw = open(path, 'rb').read()
    if raw[:2] == b'\x1f\x8b':
        return gzip.decompress(raw)
    return raw


def parse(buf):
    out = {}
    n = len(buf)
    i = 0
    while i + 5 < n:
        ln = buf[i]
        if not 1 <= ln <= 32:
            i += 1
            continue
        name = buf[i + 1:i + 1 + ln]
        if not all(32 <= c < 127 for c in name):
            i += 1
            continue
        typ = buf[i + 1 + ln]
        if typ not in (0, 1, 2, 4, 8):
            i += 1
            continue
        size3 = buf[i + 2 + ln:i + 5 + ln]
        size = size3[0] | (size3[1] << 8) | (size3[2] << 16)
        data_off = i + 5 + ln
        if typ == 0:
            length = size * 256
        else:
            length = typ
        if data_off + length > n:
            i += 1
            continue
        key = name.decode('ascii')
        if key not in out:
            out[key] = (data_off, length, bytes(buf[data_off:data_off + length]))
        i = data_off + length
    return out


def u16(b):
    return b[0] | (b[1] << 8)


def u32(b):
    return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)


if __name__ == '__main__':
    import sys
    buf = decompress(sys.argv[1])
    vars = parse(buf)
    print('parsed variables:', len(vars))
    for k in ('PC', 'A', 'X', 'Y', 'S', 'SP', 'P', 'MPR', 'BaseRAM',
              'VRAM', 'color_table', 'BG_XOffset', 'BG_YOffset'):
        if k in vars:
            off, ln, data = vars[k]
            if ln <= 8:
                print('%-16s off=%06X len=%d value=%s' % (k, off, ln, data.hex(' ')))
            else:
                print('%-16s off=%06X len=%d head=%s' % (k, off, ln, data[:16].hex(' ')))
