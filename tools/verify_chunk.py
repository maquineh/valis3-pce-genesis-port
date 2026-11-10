"""Verify that the stage chunk loaded at $8000 is self-contained.

The cd_read at $2252C4 loads sector 1000 (4 sectors) to local RAM $8000, and
the code at the start of that payload (file $23E394) is the stage entry.  Its
internal JSR targets ($847C, $8790, ...) must therefore resolve inside the
same chunk with base logical $8000 <- file $23E380.
"""
import sys

sys.path.insert(0, 'tools')
from disasm6280 import disasm_one, code_density  # noqa: E402

TRACK = 'build/extracted/data/track_02.bin'
CHUNK_FILE = 0x23E380        # sector 1000, loaded by cd_read at $2252C4
CHUNK_LOGICAL = 0x8000
b = open(TRACK, 'rb').read()

print('chunk: logical $%04X <- file $%06X (4 sectors = %d bytes)'
      % (CHUNK_LOGICAL, CHUNK_FILE, 4 * 2352))
print()
print('%-14s %-10s %-8s %s' % ('logical', 'file', 'density', 'first insn'))
refs = [0x8000, 0x8014, 0x847C, 0x8790, 0x959B, 0x88E2, 0x8839, 0x8AF4,
        0x8660, 0x8652, 0x8CD9]
for lg in refs:
    f = CHUNK_FILE + (lg - CHUNK_LOGICAL)
    d = code_density(b, f, f + 0x40)
    txt, n = disasm_one(b, f)
    print('$%04X -> $%06X  %.2f     %s' % (lg, f, d, txt))
print()
print('disassembly of the stage entry (logical $8014, file $23E394):')
pc = 0x23E394
for _ in range(24):
    txt, n = disasm_one(b, pc)
    print('   $%06X (logical $%04X): %s'
          % (pc, CHUNK_LOGICAL + (pc - CHUNK_FILE), txt))
    pc += n
