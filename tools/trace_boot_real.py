#!/usr/bin/env python3
"""Run a real System Card from its reset vector and report where it goes.

This is the unshimmed boot: the card's own reset code initialises the banks,
the VDC and the CD unit.  It is the ground truth for the CD drive handshake.
"""
import sys
from collections import Counter, deque

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from valis_disc import ValisDisc
from pce_timing import PCEFrameClock

ROM = sys.argv[1] if len(sys.argv) > 1 else 'syscard3.pce'
STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000000

rom = open(ROM, 'rb').read()
emu = PCESystem(ValisDisc(), verbose=False)
print('disc tracks=%d track2 DINFO=%s' %
      (len(emu.disc.tracks), emu.disc.toc_info(2).hex(' ')))
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
# HuC6280 vector table: $FFFE/$FFFF is RESET.  ($FFFC is IRQ2, which on the
# Super System Card points at the $E6A9 handler - not the reset code.)
reset = rom[0x1FFE] | (rom[0x1FFF] << 8)
if len(sys.argv) > 3:
    reset = int(sys.argv[3], 0)
emu.cpu.pc = reset
emu.cpu.sp = 0xFF

hist = Counter()
io_r = Counter()
io_w = Counter()
io_events = deque(maxlen=48)
protocol_events = deque(maxlen=96)
o_read, o_write = emu.read, emu.write

def rd(a):
    if a < 0x2000 and emu.cpu.mpr[0] == 0xFF:
        io_r[a] += 1
    value = o_read(a)
    if 0x1800 <= a <= 0x1803:
        protocol_events.append(('R', emu.cpu.pc, a, value, emu.cd_state,
                                emu.cd_ack, len(emu.cd_params)))
    if 0x1800 <= a <= 0x1808:
        io_events.append(('R', emu.cpu.pc, a, value, emu.cd_state,
                          emu.cd_ack, len(emu.cd_params)))
    return value

def wr(a, v):
    if a < 0x2000 and emu.cpu.mpr[0] == 0xFF:
        io_w[a] += 1
    result = o_write(a, v)
    if 0x1800 <= a <= 0x1803:
        protocol_events.append(('W', emu.cpu.pc, a, v & 0xFF, emu.cd_state,
                                emu.cd_ack, len(emu.cd_params)))
    if 0x1800 <= a <= 0x1808:
        io_events.append(('W', emu.cpu.pc, a, v & 0xFF, emu.cd_state,
                          emu.cd_ack, len(emu.cd_params)))
    return result

emu.read, emu.write = rd, wr
emu.cpu.read, emu.cpu.write = rd, wr
scsi_commands = Counter()
scsi_order = []
original_scsi_exec = emu._scsi_exec

def trace_scsi_exec():
    command = bytes(emu.cd_params)
    scsi_commands[command.hex(' ')] += 1
    scsi_order.append(command.hex(' '))
    original_scsi_exec()

emu._scsi_exec = trace_scsi_exec

print('ROM %s reset=$%04X steps=%d' % (ROM, reset, STEPS))
n = 0
irq_every = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
frame_clock = PCEFrameClock(high_speed=False)  # HuC6280 reset starts in CSL mode.
try:
    for _ in range(STEPS):
        pc = emu.cpu.pc
        opcode = emu.mem[emu.cpu.phys(pc)]
        hist[emu.cpu.pc] += 1
        emu.cpu.step()
        n += 1
        # An explicit step interval remains available for old traces; the
        # default follows approximate NTSC elapsed cycles.
        if irq_every and n % irq_every == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20          # VBlank IRQ pending
            emu.cpu.interrupt(0xFFF8)       # timer vector, which polls VDC status
        elif not irq_every:
            frame_clock.after_instruction(emu, pc, opcode)
except StopIteration as e:
    print('transfer:', e)
except RuntimeError as e:
    print('stop:', e)

print('steps %d  pc=$%04X  mpr=%s' %
      (n, emu.cpu.pc, ' '.join('%02X' % m for m in emu.cpu.mpr)))
print('cpu a=%02X x=%02X y=%02X sp=%02X p=%02X I=%d' %
      (emu.cpu.a, emu.cpu.x, emu.cpu.y, emu.cpu.sp, emu.cpu.p(), emu.cpu.fI))
stack = [emu.mem[0x1F0000 + 0x100 + ((emu.cpu.sp + i) & 0xFF)]
         for i in range(1, 17)]
print('stack from top:', ' '.join('%02X' % b for b in stack))
print('BIOS RAM $2241=%02X $222D=%02X zp[$F6]=%02X VDC status=%02X' %
      (emu.mem[0x1F0241], emu.mem[0x1F022D], emu.mem[0x1F00F6],
       emu.vdc_status))
print('IRQ handler hits: $E870=%d $E88A=%d $E8E2=%d' %
      (hist[0xE870], hist[0xE88A], hist[0xE8E2]))
print('disc reads:', sorted(set(emu.disc.reads))[:12], 'count', len(emu.disc.reads))
print('VRAM writes:', len(emu.vram_writes), 'CRAM:', sum(1 for c in emu.cram if c))
if irq_every:
    print('VBlank IRQs: step-interval mode (%d steps)' % irq_every)
else:
    print('VBlank IRQs: %d  elapsed high-speed cycles: %d' %
          (frame_clock.interrupts, frame_clock.cycles))
print('hot pcs:', [('$%04X' % a, c) for a, c in hist.most_common(8)])
print('io writes:', [('$%04X' % a, c) for a, c in io_w.most_common(12)])
print('io reads :', [('$%04X' % a, c) for a, c in io_r.most_common(12)])
print('SCSI commands:', scsi_commands.most_common(12))
print('last SCSI commands:', scsi_order[-12:])
print('CD state:', emu.cd_state, 'command=$%02X' % emu.cd_cmd,
      'pending=%s' % bytes(emu.cd_params).hex(' '),
      'result_pos=%d/%d' % (emu.cd_result_pos, len(emu.cd_result)),
      'ack=%s flags=$%02X' % (emu.cd_ack, emu.cd_flags))
print('recent CD I/O:')
for event in io_events:
    print('  %s pc=$%04X $%04X=$%02X state=%s ack=%s params=%d' % event)
print('recent command/status handshake:')
for event in protocol_events:
    print('  %s pc=$%04X $%04X=$%02X state=%s ack=%s params=%d' % event)
