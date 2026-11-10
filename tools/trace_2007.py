import re
import sys

sys.path.insert(0, 'tools')
from disasm6280 import disasm_one

disc = open('build/extracted/data/track_02.bin', 'rb').read()
BASE = 0x27F0          # logical = file + BASE for the boot block

block = disc[0x10:0x1010]
print('searching the boot block for writes to work RAM $2000-$2007:')
for off in range(len(block) - 2):
    if block[off] in (0x85, 0x8D, 0x9C, 0x84, 0x86):
        addr = None
        if block[off] == 0x85 and 0x00 <= block[off + 1] <= 0x07:
            addr = 0x2000 + block[off + 1]
        elif block[off] == 0x8D:
            addr = block[off + 1] | (block[off + 2] << 8)
        if addr is not None and 0x2000 <= addr <= 0x2008:
            print('   file $%04X (logical $%04X): addr $%04X'
                  % (0x10 + off, 0x2800 + off, addr))
print()

print('disassembly of the boot from $2C43 (file $0453):')
pc = 0x453
seen = set()
for _ in range(40):
    if pc in seen:
        print('   (loop)')
        break
    seen.add(pc)
    txt, n = disasm_one(disc, pc)
    print('   file $%04X logical $%04X: %s' % (pc, pc + BASE, txt))
    pc += n
