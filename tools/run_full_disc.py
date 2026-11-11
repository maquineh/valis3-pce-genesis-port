"""Run the retail disc with the real 72-track TOC and the user BRAM save.

This is the decisive test: before, DINFO() for track 6 (a MODE1 data track)
returned MSF 00:00:00, so the BIOS computed base LBA -150 and the game read
audio from the lead-in forever.  With the real TOC the game should read
track 6's program and continue past the act-title card.
"""

import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc

SAVE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
rom = open('syscard3.pce', 'rb').read()
disc = ValisDisc()
emu = PCESystem(disc, verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
sv = open(SAVE, 'rb').read()
emu.mem[0x1EE000:0x1EE000 + len(sv)] = sv
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF

last = []
cmds = []
orig_exec = emu._scsi_exec


def exec_hook():
    p = bytes(emu.cd_params)
    cmds.append((emu.steps, p, emu.cpu.pc))
    return orig_exec()


emu._scsi_exec = exec_hook


def run(n):
    for k in range(n):
        last.append(emu.cpu.pc)
        if len(last) > 12:
            last.pop(0)
        emu.cpu.step()
        if k % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)


run(5000000)
print('title pc=%04X mpr=%s reads=%d' %
      (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr), len(disc.reads)))
before = len(disc.reads)
emu.mem[0x1F3C00] = 1
emu.joy_low = 0x04
run(30000)
emu.joy_low = 0x0F
emu.joy_high = 0x0F
try:
    run(6000000)
except RuntimeError as e:
    print('CPU stopped:', e)
    print('last pcs:', ' '.join('%04X' % x for x in last))

print('final pc=%04X mpr=%s sp=%02X' %
      (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr), emu.cpu.sp))
print('\nSCSI commands after CONTINUE:')
for steps, p, pc in cmds:
    print('  %8d %s' % (steps, p.hex(' ')))
print('\nnew LBA reads:', sorted(set(disc.reads[before:]))[:60])
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
emu.dump_vram('build/full_disc_vram.bin')
emu.dump_cram('build/full_disc_cram.bin')
emu.dump_satb('build/full_disc_satb.bin') if hasattr(emu, 'dump_satb') else None
print('dumped build/full_disc_vram.bin')
