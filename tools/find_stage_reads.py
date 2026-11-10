"""Find every cd_read whose sector points into a stage segment block.

The stage segments live at sectors 304..763 in 40-sector groups.  If the
loader reads them, there is a cd_read site whose cl/ch/dl encode one of those
sector numbers - that tells us how the stage data is consumed (VRAM vs RAM vs
MPR) and how big each read is.
"""
import re
import sys

sys.path.insert(0, 'tools')
from decode_cd_calls import decode_params  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
b = open(TRACK, 'rb').read()

STAGE_SECTORS = [304 + 40 * i for i in range(12)]
print('stage segment base sectors:', STAGE_SECTORS)

sites = []
for off in range(0, len(b) - 3):
    if b[off] != 0x20:
        continue
    addr = b[off + 1] | (b[off + 2] << 8)
    if addr != 0xE009:
        continue
    p = decode_params(b, off)
    sector = ((p.get('cl', 0) << 16) | (p.get('ch', 0) << 8)
              | p.get('dl', 0))
    dest = (p.get('bh', 0) << 8) | p.get('bl', 0)
    size = (p.get('ah', 0) << 8) | p.get('al', 0)
    sites.append((off, sector, dest, size, p.get('dh')))

print('%-9s %8s %8s %8s %4s %s' % ('site', 'sector', 'dest', 'size', 'dh', 'in stage block'))
hits = 0
for off, sector, dest, size, dh in sites:
    inblock = any(0 <= sector - s < 40 * 2352 // 2352 for s in STAGE_SECTORS)
    near = [s for s in STAGE_SECTORS if abs(sector - s) < 40]
    if near:
        hits += 1
        print('$%06X %8d $%06X %8d $%02X  near sector %d'
              % (off, sector, dest, size, dh or 0, near[0]))
print('%d of %d cd_read sites point into a stage segment block' % (hits, len(sites)))

print()
print('all cd_read sector/dest/size:')
for off, sector, dest, size, dh in sorted(sites, key=lambda r: r[1]):
    print('  $%06X sector %5d dest $%06X size %6d dh $%02X'
          % (off, sector, dest, size, dh or 0))
