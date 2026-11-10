"""Find the (MPR0, MPR6) combination that lets the disc's 74-byte check pass.

$2B26 reads a pointer from zero page $FA/$FB and compares 74 bytes against the
pointer in $FC/$FD ($DFB6).  Both the zero-page window (MPR0) and the target
bank (MPR6) are unknown, so sweep both and detect which reaches $2B44.
"""
import glob
import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK, BOOT_BLOCK_FILE, BOOT_BLOCK_LOGICAL

ROM = sorted(glob.glob('*v3.0*.pce'))[0]
rom = open(ROM, 'rb').read()
disc_bytes = open(TRACK, 'rb').read()
WB = 0xF8 << 13
BOOT_OFF = WB + (BOOT_BLOCK_LOGICAL & 0x1FFF)

print('ROM:', ROM)
print('sweeping MPR0 x MPR6 for a passing 74-byte check ...')
passes = []
for mpr0 in range(256):
    for mpr6 in range(256):
        emu = PCESystem(Disc(TRACK), verbose=False)
        for i, x in enumerate(rom):
            emu.mem[i] = x
        for i in range(2 * 2048):
            emu.mem[BOOT_OFF + i] = disc_bytes[BOOT_BLOCK_FILE + i]
        emu.cpu.mpr = [mpr0, 0xF8, 0x04, 0x05, 0x06, 0x07, mpr6, 0x00]
        emu.cpu.pc = 0x2B26
        emu.cpu.sp = 0xFF
        reached = False
        try:
            for _ in range(300):
                emu.cpu.step()
                if emu.cpu.pc >= 0x2B44 and emu.cpu.pc < 0x2C00:
                    reached = True
                    break
        except (StopIteration, RuntimeError):
            pass
        if reached:
            passes.append((mpr0, mpr6))

print('%d passing combinations' % len(passes))
for mpr0, mpr6 in passes[:20]:
    print('   MPR0=$%02X MPR6=$%02X' % (mpr0, mpr6))
