"""Enumerate the CD-ROM drive registers the real System Card touches.

Disassembles the whole BIOS and collects every absolute / zero-page access in
the CD interface ranges ($1400-$17FF and $1800-$1BFF).  That list is exactly
what has to be emulated before the BIOS can boot.
"""
import sys
from collections import Counter

sys.path.insert(0, 'tools')
from disasm6280 import OPCODES, LEN, disasm_one

ROM = 'syscard3.pce'
rom = open(ROM, 'rb').read()

# The 8 KiB System Card ROM is image[0x0000:0x2000] -> logical $E000-$FFFF.
code = rom[0:0x2000]

refs = Counter()
detail = {}
pc = 0
while pc < len(code) - 3:
    op = code[pc]
    if op not in OPCODES:
        pc += 1
        continue
    mn, mode = OPCODES[op]
    n = LEN.get(mode, 1)
    txt, n2 = disasm_one(code, pc)
    if txt:
        # absolute operands
        if mode in ('abs', 'abx', 'aby'):
            addr = code[pc + 1] | (code[pc + 2] << 8)
            if 0x1400 <= addr <= 0x1BFF:
                refs[addr] += 1
                detail.setdefault(addr, (mn, txt))
    pc += n if n else 1

print('CD interface registers referenced by %s ($E000-$FFFF):' % ROM)
for addr in sorted(refs):
    mn, txt = detail[addr]
    print('   $%04X  %-4s  %-22s  %d refs' % (addr, mn, txt, refs[addr]))
print()
print('%d distinct addresses in $1400-$1BFF' % len(refs))
