"""Decode every cd_exec site: which sector is loaded to which address."""
import sys

sys.path.insert(0, 'tools')
from decode_cd_calls import decode_params  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
OVERLAY_BASE_FILE = 0x12600      # logical $4000 <- file 0x12600 (verified)
OVERLAY_BASE_LOG = 0x4000

b = open(TRACK, 'rb').read()

sites = []
for off in range(0, len(b) - 3):
    if b[off] == 0x20:
        addr = b[off + 1] | (b[off + 2] << 8)
        if addr == 0xE00F:                     # cd_exec
            p = decode_params(b, off)
            sector = ((p.get('cl', 0) << 16) | (p.get('ch', 0) << 8)
                      | p.get('dl', 0))
            dest = (p.get('bh', 0) << 8) | p.get('bl', 0)
            cnt = p.get('al', 0)
            dh = p.get('dh')
            sites.append((off, sector, dest, cnt, dh))

print('%-9s %8s %8s %6s %4s %s' %
      ('site', 'sector', 'dest', 'sects', 'dh', 'file range loaded'))
for off, sector, dest, cnt, dh in sites:
    f0 = sector * 2352
    f1 = f0 + cnt * 2352
    print('$%06X %8d $%06X %6d $%02X  $%06X-$%06X'
          % (off, sector, dest, cnt, dh or 0, f0, f1))
print()
print('%d cd_exec sites' % len(sites))
