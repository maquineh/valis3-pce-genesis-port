import sys

path = sys.argv[1]
off = int(sys.argv[2], 0)
n = int(sys.argv[3], 0)
base = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
d = open(path, 'rb').read()
for r in range(off, off + n, 16):
    row = d[r:r + 16]
    asc = ''.join(chr(x) if 32 <= x < 127 else '.' for x in row)
    print('%05X %-47s %s' % (r - base, ' '.join('%02X' % x for x in row), asc))
