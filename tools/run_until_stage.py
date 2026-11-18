import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from valis_toc import BY_TRACK
from pce_timing import PCEFrameClock

SAVE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
TRACK2_LBA1 = BY_TRACK[2]['lba1']
STG_BLOCKS = [
    (304, 'STG1A'), (344, 'STG2A'), (384, 'STG2B'), (424, 'STG2C'),
    (464, 'STG3A'), (504, 'STG3B'), (544, 'STG4A'), (584, 'STG4B'),
    (624, 'STG4C'), (664, 'STG5A'),
]
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
frame_clock = PCEFrameClock(high_speed=False)  # HuC6280 reset starts in CSL mode.

cmds = []
orig_exec = emu._scsi_exec


def exec_hook():
    cmds.append(bytes(emu.cd_params))
    return orig_exec()


emu._scsi_exec = exec_hook


def stage_for_lba(lba):
    sector = lba - TRACK2_LBA1
    for start, name in STG_BLOCKS:
        if start <= sector < start + 40:
            return name
    return None


def run(n, stop_on_stage=False):
    for k in range(n):
        read_start = len(disc.reads)
        pc = emu.cpu.pc
        opcode = emu.mem[emu.cpu.phys(pc)]
        emu.cpu.step()
        frame_clock.after_instruction(emu, pc, opcode)
        if stop_on_stage:
            for r in disc.reads[read_start:]:
                name = stage_for_lba(r)
                if name:
                    return True, k, name, r
    return False, n, None, None


hit, used, hit_name, hit_lba = run(5000000, stop_on_stage=True)
print('title reads=%d' % len(disc.reads))
total = used
if hit:
    print('*** read %s at LBA %d during startup' % (hit_name, hit_lba))
    run(5000000)
else:
    emu.mem[0x1F3C00] = 1
    emu.joy_low = 0x04
    pressed, k, name, lba = run(30000, stop_on_stage=True)
    total += k
    emu.joy_low = 0x0F
    emu.joy_high = 0x0F
    if pressed:
        hit, hit_name, hit_lba = True, name, lba
        print('*** read %s at LBA %d while starting' % (name, lba))

    for i in range(24):
        if hit:
            break
        hit, k, name, lba = run(2500000, stop_on_stage=True)
        total += k
        print('  %2dM pc=%04X reads=%d new=[%s]' %
              (total // 1000000, emu.cpu.pc, len(disc.reads),
               ' '.join(str(x) for x in sorted(set(disc.reads))[-12:])))
        if hit:
            hit_name, hit_lba = name, lba
            print('*** read %s at LBA %d after %d steps; continuing 5M for stage setup'
                  % (name, lba, total))
            run(5000000)
            break

print('\nall SCSI commands:')
for p in cmds:
    print('  %s' % p.hex(' '))
print('\ndistinct LBAs:', sorted(set(disc.reads))[-80:])
if not hit:
    ranges = ', '.join('%s=%d-%d' % (name, TRACK2_LBA1 + start,
                                     TRACK2_LBA1 + start + 39)
                       for start, name in STG_BLOCKS)
    print('no STG block reads observed; watched INDEX 01 ranges: ' + ranges)
else:
    print('first STG block read: %s at LBA %d' % (hit_name, hit_lba))
emu.dump_vram('build/stage_hit_vram.bin')
emu.dump_cram('build/stage_hit_cram.bin')
print('VRAM writes', len(emu.vram_writes))
print('VBlank IRQs', frame_clock.interrupts,
      'elapsed high-speed cycles', frame_clock.cycles)
print('dumped build/stage_hit_vram.bin')
