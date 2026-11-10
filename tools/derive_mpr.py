"""Derive the MPR4 value the boot code would compute.

The boot ends with `JMP ($2007)` -> $838D, which lives in MPR4's page
($8000-$9FFF).  MPR4 = work RAM $300A + a System Card ROM byte at $FFF5 that
is not in the repository, so the value has to be derived.  The game's real
entry point must be executable 6502 code that talks to the CD BIOS and the
VDC, so a page qualifies when the code at $838D is dense and contains the
signatures of those accesses.
"""
import sys

sys.path.insert(0, 'tools')
from disasm6280 import disasm_one, code_density  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
ENTRY = 0x838D

# signatures that real game code contains
SIGS = {
    '20 09 E0': 'JSR $E009  (cd_read)',
    '20 0F E0': 'JSR $E00F  (cd_exec)',
    '8D 02 00': 'STA $0002  (VDC data)',
    '8D 03 00': 'STA $0003  (VDC data hi)',
    '03': 'ST0 (VDC register select)',
}

b = open(TRACK, 'rb').read()
print('scanning MPR4 values for a valid entry point at $%04X:' % ENTRY)
hits = []
for page in range(0x00, 0x100):
    phys = (page << 13) | (ENTRY & 0x1FFF)
    if phys + 0x800 > len(b):
        continue
    for pay in (0, 16):
        p = phys + pay
        if p + 0x800 > len(b):
            continue
        d = code_density(b, p, p + 0x400)
        if d < 0.5:
            continue
        window = b[p:p + 0x800]
        found = []
        for hexs, label in SIGS.items():
            if bytes.fromhex(hexs) in window:
                found.append(label)
        if found:
            hits.append((d, page, pay, found))

hits.sort(reverse=True)
print('%d candidate pages:' % len(hits))
for d, page, pay, found in hits[:15]:
    print('  MPR4=$%02X payload+%d  density=%.2f  %s'
          % (page, pay, d, '; '.join(found[:3])))
print()
if hits:
    page = hits[0][1]
    phys = (page << 13) | (ENTRY & 0x1FFF)
    print('best candidate MPR4=$%02X -> physical $%06X (file offset)' % (page, phys))
    print('code at the entry point:')
    pc = phys
    for _ in range(14):
        txt, n = disasm_one(b, pc)
        print('   $%06X: %s' % (pc, txt or '.byte $%02X' % b[pc]))
        pc += n
