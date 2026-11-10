"""Verify the System Card's boot-sector signature check against the disc.

cd_boot compares 0x4D5 bytes of the loaded boot block (logical $2800) with a
reference at logical $DAE1 under MPR6 = $1F (physical $3FAE1), then 0x4A zero
bytes.  If it matches, it calls JSR $2B26 - the disc's entry point.
"""
import sys

rom = open('syscard1.pce', 'rb').read()
disc = open('build/extracted/data/track_02.bin', 'rb').read()

REF = 0x3FAE1
N = 0x4D5
ZERO = 0x4A

ref = rom[REF:REF + N]
zero_ref = rom[REF + N:REF + N + ZERO]

print('System Card reference at image $%06X (%d bytes), entropy check:' % (REF, N))
from collections import Counter
print('  distinct byte values: %d' % len(set(ref)))
print('  first 32: %s' % ref[:32].hex())
print('  following %d bytes are zero: %s' % (ZERO, all(x == 0 for x in zero_ref)))
print()

candidates = [
    ('disc file 0x0000 (frame start)', 0x0000),
    ('disc file 0x0010 (payload start)', 0x0010),
    ('disc file 0x2352 (sector 1)', 0x2352),
]
for name, off in candidates:
    chunk = disc[off:off + N]
    same = sum(1 for a, b in zip(chunk, ref) if a == b)
    print('%-34s matches %4d/%d bytes (%.1f%%)'
          % (name, same, N, 100 * same / N))
print()

# what if the disc data was Xored / transformed?
first_diff = next((i for i in range(N) if disc[i] != ref[i]), None)
print('first differing byte (frame start): %s' % first_diff)
if first_diff is not None:
    print('  disc[%04X]=%02X  ref[%04X]=%02X'
          % (first_diff, disc[first_diff], first_diff, ref[first_diff]))
