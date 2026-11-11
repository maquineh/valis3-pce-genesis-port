import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

SAVE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
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
    sp = emu.cpu.sp
    ret = emu.mem[0x1F0000 | (0x100 | ((sp + 1) & 0xFF))] | \
          (emu.mem[0x1F0000 | (0x100 | ((sp + 2) & 0xFF))] << 8)
    cmds.append((emu.steps, p, emu.cpu.pc, ret, list(last)))
    return orig_exec()


emu._scsi_exec = exec_hook


def run(n):
    for k in range(n):
        last.append(emu.cpu.pc)
        if len(last) > 10:
            last.pop(0)
        emu.cpu.step()
        if k % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)


run(5000000)
print('title pc=%04X reads=%d' % (emu.cpu.pc, len(emu.disc.reads)))
emu.mem[0x1F3C00] = 1
emu.joy_low = 0x04
run(30000)
emu.joy_low = 0x0F
emu.joy_high = 0x0F
run(2000000)

print('\nlast 60 SCSI commands:')
for steps, p, pc, ret, pcs in cmds[-60:]:
    print('  %8d op=%02X params=%s pc=%04X ret=%04X pcs=%s' %
          (steps, p[0] if p else 0, p.hex(' '), pc, ret,
           ' '.join('%04X' % x for x in pcs[-6:])))
