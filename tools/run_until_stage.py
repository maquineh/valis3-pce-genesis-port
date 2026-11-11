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

cmds = []
orig_exec = emu._scsi_exec


def exec_hook():
    cmds.append(bytes(emu.cd_params))
    return orig_exec()


emu._scsi_exec = exec_hook


def step():
    emu.cpu.step()
    emu.vdc_status |= 0x20
    if not emu.cpu.fI:
        emu.cpu.interrupt(0xFFF8)


def run(n, stop_on_stage=False):
    for k in range(n):
        step()
        if stop_on_stage:
            r = disc.reads[-1] if disc.reads else None
            if r is not None and 3480 <= r <= 3560:
                return True, k
    return False, n


run(5000000)
print('title reads=%d' % len(disc.reads))
emu.mem[0x1F3C00] = 1
emu.joy_low = 0x04
run(30000)
emu.joy_low = 0x0F
emu.joy_high = 0x0F

total = 0
hit = False
for i in range(24):
    hit, k = run(2500000, stop_on_stage=total > 0)
    total += k
    print('  %2dM pc=%04X reads=%d new=[%s]' %
          (total // 1000000, emu.cpu.pc, len(disc.reads),
           ' '.join(str(x) for x in sorted(set(disc.reads))[-12:])))
    if hit:
        print('*** reached stage LBA area at %d steps' % total)
        break

print('\nall SCSI commands:')
for p in cmds:
    print('  %s' % p.hex(' '))
print('\ndistinct LBAs:', sorted(set(disc.reads))[-80:])
emu.dump_vram('build/stage_hit_vram.bin')
emu.dump_cram('build/stage_hit_cram.bin')
print('VRAM writes', len(emu.vram_writes))
print('dumped build/stage_hit_vram.bin')
