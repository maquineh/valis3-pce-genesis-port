"""Run the retail disc with the real 72-track TOC and the user BRAM save.

This is the decisive test: before, DINFO() for track 6 (a MODE1 data track)
returned MSF 00:00:00, so the BIOS computed base LBA -150 and the game read
audio from the lead-in forever.  With the real TOC the game should read
track 6's program and continue past the act-title card.
"""

import os
import sys
from collections import Counter, deque

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from pce_timing import PCEFrameClock

SAVE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.sav'
OUT_PREFIX = sys.argv[1] if len(sys.argv) > 1 else 'build/full_disc'
ACTION = sys.argv[2] if len(sys.argv) > 2 else 'new-game'
BASE_STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 5000000
POST_STEPS = int(sys.argv[4]) if len(sys.argv) > 4 else 6000000


def parse_mid_action(value):
    """Parse a post-start input as STEP[:ACTIVE_LOW_MASK]."""
    if ':' in value:
        step_text, mask_text = value.split(':', 1)
        mask = int(mask_text, 0)
    else:
        step_text, mask = value, 0x07  # backwards-compatible Run pulse
    step = int(step_text, 0)
    if not 0 <= mask <= 0x0F:
        raise SystemExit('mid-run mask must be an active-low nibble (0..0x0F)')
    return step, mask


MID_ACTIONS = [parse_mid_action(arg) for arg in sys.argv[5:]]
out_dir = os.path.dirname(OUT_PREFIX)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)
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

last = []
recent_ops = deque(maxlen=32)
pc_history = deque(maxlen=32)
call_probe = deque(maxlen=16)
transitions = deque(maxlen=80)
step_count = [0]
pc_hits = Counter()
input_snapshots = []
cmds = []
orig_exec = emu._scsi_exec
vector_writes = deque(maxlen=64)
orig_cpu_write = emu.cpu.write


def traced_cpu_write(addr, value):
    if addr in (0x2208, 0x2209):
        vector_writes.append((step_count[0], emu.cpu.pc, addr, value & 0xFF,
                              tuple(emu.cpu.mpr),
                              emu.mem[0x1F0208:0x1F020A]))
    orig_cpu_write(addr, value)


emu.cpu.write = traced_cpu_write


def exec_hook():
    p = bytes(emu.cd_params)
    cmds.append((step_count[0], p, emu.cpu.pc))
    return orig_exec()


emu._scsi_exec = exec_hook

joy_reads = Counter()
joy_events = deque(maxlen=32)
phase = ['boot']
base_read = emu.cpu.read


def traced_read(addr):
    value = base_read(addr)
    if addr == 0x1000:
        joy_reads[(phase[0], emu.joy_select, value)] += 1
        joy_events.append((phase[0], emu.cpu.pc, emu.joy_select, value,
                           emu.mem[0x1F0228], emu.mem[0x1F022D]))
    return value


emu.cpu.read = traced_read
emu.read = traced_read


def run(n):
    for k in range(n):
        step_count[0] += 1
        last.append(emu.cpu.pc)
        if len(last) > 12:
            last.pop(0)
        pc = emu.cpu.pc
        if pc in (0x412C, 0x4132, 0x4139, 0x4141, 0x4146, 0x4167,
                  0x4181, 0x42AA, 0x42E8, 0x430F, 0x4310, 0x4315,
                  0x4338, 0x4360,
                  0xE00F, 0xEBEC, 0xE3C4, 0xE4D5):
            pc_hits[pc] += 1
        mpr_before = tuple(emu.cpu.mpr)
        opcode = emu.mem[emu.cpu.phys(pc)]
        pc_history.append((step_count[0], pc, opcode))
        if 0x4D3F <= pc <= 0x4D43:
            phys = emu.cpu.phys(pc)
            call_probe.append((step_count[0], pc, phys,
                               emu.mem[phys:phys + 8], tuple(emu.cpu.mpr),
                               emu.cpu.a, emu.cpu.x, emu.cpu.y, emu.cpu.sp,
                               tuple(pc_history)))
        recent_ops.append((phase[0], pc, opcode, tuple(emu.cpu.mpr)))
        emu.cpu.step()
        frame_clock.after_instruction(emu, pc, opcode)
        if (pc >= 0x2000 > emu.cpu.pc or emu.cpu.pc >= 0x2000 > pc or
                mpr_before != tuple(emu.cpu.mpr)):
            transitions.append((phase[0], step_count[0], pc, emu.cpu.pc,
                                opcode, mpr_before, tuple(emu.cpu.mpr)))


run(BASE_STEPS)
print('title pc=%04X mpr=%s reads=%d' %
      (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr), len(disc.reads)))
phase[0] = 'select'
before = len(disc.reads)
# The title starts on the new-game option ($3C00=0). CONTINUE is the option
# after SELECT toggles it to 1. Hold each input across several VBlanks.
if ACTION == 'continue':
    emu.joy_low = 0x0B   # active-low Select only (bit 2)
    run(240000)
    input_snapshots.append(('select-held', emu.cpu.pc, emu.mem[0x1F0228],
                            emu.mem[0x1F022D], emu.mem[0x1F1C00]))
    emu.joy_low = 0x0F
    phase[0] = 'release-select'
    run(240000)
elif ACTION != 'new-game':
    raise SystemExit('ACTION must be continue or new-game')
emu.joy_high = 0x0F
phase[0] = 'run'
emu.joy_low = 0x07       # active-low Run only (bit 3)
run(240000)
input_snapshots.append(('run-held', emu.cpu.pc, emu.mem[0x1F0228],
                        emu.mem[0x1F022D], emu.mem[0x1F1C00]))
emu.joy_low = 0x0F
phase[0] = 'post-run'
try:
    if MID_ACTIONS:
        if ACTION != 'new-game' or any(
                step + 240000 * (index + 1) > POST_STEPS
                for index, (step, _) in enumerate(MID_ACTIONS)):
            raise SystemExit('mid-run inputs require new-game and room in POST_STEPS')
        elapsed = 0
        for index, (step, mask) in enumerate(MID_ACTIONS, start=1):
            if step < elapsed:
                raise SystemExit('mid-run input steps must be increasing')
            run(step - elapsed)
            phase[0] = 'advance-input-%d' % index
            emu.joy_low = mask
            run(240000)
            input_snapshots.append(('advance-input-%d-held' % index,
                                    emu.cpu.pc, emu.mem[0x1F0228],
                                    emu.mem[0x1F022D], emu.mem[0x1F1C00], mask))
            emu.joy_low = 0x0F
            elapsed = step + 240000
        phase[0] = 'post-run'
        run(POST_STEPS - elapsed)
    else:
        run(POST_STEPS)
except RuntimeError as e:
    print('CPU stopped:', e)
    print('last pcs:', ' '.join('%04X' % x for x in last))
    print('recent instructions (phase pc opcode mpr0-7):')
    for phase_name, pc, opcode, mpr in recent_ops:
        print('  %s $%04X %02X %s' %
              (phase_name, pc, opcode, ' '.join('%02X' % m for m in mpr)))
    phys_pc = emu.cpu.phys(emu.cpu.pc)
    print('fault bytes phys=$%06X: %s' %
          (phys_pc, emu.mem[max(0, phys_pc - 8):phys_pc + 9].hex(' ')))
    stack = [emu.mem[0x1F0100 + ((emu.cpu.sp + i) & 0xFF)]
             for i in range(1, 17)]
    print('registers a=%02X x=%02X y=%02X p=%02X sp=%02X stack=%s' %
          (emu.cpu.a, emu.cpu.x, emu.cpu.y, emu.cpu.p(), emu.cpu.sp,
           ' '.join('%02X' % b for b in stack)))
    print('calls around $4D41 (step pc phys bytes mpr A X Y SP recent-pcs):')
    for event in call_probe:
        steps, pc, phys, data, mpr, a, x, y, sp, history = event
        print('  %d $%04X phys=$%06X %s mpr=%s A=%02X X=%02X Y=%02X SP=%02X PCs=%s' %
              (steps, pc, phys, data.hex(' '), ' '.join('%02X' % m for m in mpr),
               a, x, y, sp, ' '.join('%04X:%02X' % (p, op) for _, p, op in history)))

print('final pc=%04X mpr=%s sp=%02X' %
      (emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr), emu.cpu.sp))
print('final registers A=%02X X=%02X Y=%02X P=%02X next-op=%02X' %
      (emu.cpu.a, emu.cpu.x, emu.cpu.y, emu.cpu.p(),
       emu.mem[emu.cpu.phys(emu.cpu.pc)]))
irq_frame = [emu.mem[0x1F0100 + ((emu.cpu.sp + i) & 0xFF)]
             for i in (1, 2, 3)]
print('stack top bytes=%s' % ' '.join('%02X' % b for b in irq_frame))
print('controller state joy_select=%d joy_low=%X joy_high=%X RAM $2228=%02X $222D=%02X $3C00=%02X' %
      (emu.joy_select, emu.joy_low, emu.joy_high, emu.mem[0x1F0228],
       emu.mem[0x1F022D], emu.mem[0x1F1C00]))
print('joy reads:', joy_reads)
print('recent joy samples (phase, pc, select, value, $2228, $222D):')
for event in joy_events:
    print('  %s $%04X sel=%d value=%X state=%02X trigger=%02X' % event)
print('recent PC/MPR transitions (phase step oldPC newPC opcode oldMPR newMPR):')
for event in transitions:
    phase_name, steps, old_pc, new_pc, opcode, before_mpr, after_mpr = event
    print('  %s %d $%04X->$%04X op=%02X %s => %s' %
          (phase_name, steps, old_pc, new_pc, opcode,
           ' '.join('%02X' % m for m in before_mpr),
           ' '.join('%02X' % m for m in after_mpr)))
print('\nSCSI commands after %s:' % ACTION)
for steps, p, pc in cmds:
    print('  %8d %s' % (steps, p.hex(' ')))
print('\nnew LBA reads:', sorted(set(disc.reads[before:]))[:60])
print('title branch hits:', {('$%04X' % pc): count for pc, count in pc_hits.items()})
print('input snapshots (phase, pc, $2228, $222D, $3C00[, active-low mask]):',
      input_snapshots)
print('CD state=%s cmd=$%02X cdda polls remaining=%d' %
      (emu.cd_state, emu.cd_cmd, emu.cdda_reads))
print('BIOS RAM $2241=%02X $222D=%02X ZP $F8-$FF=%s' %
      (emu.mem[0x1F0241], emu.mem[0x1F022D],
       ' '.join('%02X' % emu.mem[0x1F0000 + z] for z in range(0xF8, 0x100))))
print('BIOS vectors $2202-$220B:',
      emu.mem[0x1F0202:0x1F020C].hex(' '))
print('writes to BIOS vector $2208/$2209 (step pc addr value mpr vector-after):')
for event in vector_writes:
    steps, pc, addr, value, mpr, vector = event
    print('  %d $%04X $%04X=%02X mpr=%s vector=%s' %
          (steps, pc, addr, value, ' '.join('%02X' % m for m in mpr),
           vector.hex(' ')))
for bank in (0x80, emu.cpu.mpr[2]):
    for logical in (0x4D3A, 0x4D41):
        phys = (bank << 13) | (logical & 0x1FFF)
        print('bank=%02X logical=$%04X phys=$%06X bytes=%s' %
              (bank, logical, phys,
               emu.mem[phys:phys + 8].hex(' ')))
print('VDC regs:', ' '.join('%02X' % value for value in emu.regs[:20]))
print('common VRAM write addresses:', Counter(a for a, _ in emu.vram_writes).most_common(12))
print('VRAM writes', len(emu.vram_writes), 'CRAM', sum(1 for c in emu.cram if c))
print('VBlank IRQs', frame_clock.interrupts,
      'elapsed high-speed cycles', frame_clock.cycles)
emu.dump_vram(OUT_PREFIX + '_vram.bin')
emu.dump_cram(OUT_PREFIX + '_cram.bin')
emu.dump_satb(OUT_PREFIX + '_satb.bin') if hasattr(emu, 'dump_satb') else None
with open(OUT_PREFIX + '_cdram.bin', 'wb') as f:
    f.write(emu.mem[0x100000:0x110000])
with open(OUT_PREFIX + '_wram.bin', 'wb') as f:
    f.write(emu.mem[0x1F0000:0x1F2000])
with open(OUT_PREFIX + '_bankff.bin', 'wb') as f:
    f.write(emu.mem[0x1FE000:0x200000])
print('dumped ' + OUT_PREFIX + '_vram.bin')
