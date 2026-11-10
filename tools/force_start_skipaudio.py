import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False

# Stub only the audio/search/stat BIOS entries: LDA #$00 ; RTS.
# cd_read ($E009) and cd_exec ($E00F) stay real.
for entry in (0x12, 0x15, 0x18, 0x1B):
    emu.mem[entry:entry + 3] = bytes([0xA9, 0x00, 0x60])

emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF

for n in range(1, 3000001):
    emu.cpu.step()
    if n % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

emu.disc.audio_phase = True
emu.cpu.pc = 0x4167
emu.mem[0x1F0000 + 0x3C00] = 0
before = set(emu.disc.reads)
for n in range(1, 12000001):
    emu.cpu.step()
    if n % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)

print('pc=%04X mpr=%s' % (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('new reads:', sorted(set(emu.disc.reads) - before)[:40])
print('all reads count', len(emu.disc.reads), 'distinct', len(set(emu.disc.reads)))
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
emu.dump_vram('build/skipaudio_vram.bin')
emu.dump_cram('build/skipaudio_cram.bin')
print('dumped build/skipaudio_vram.bin')
