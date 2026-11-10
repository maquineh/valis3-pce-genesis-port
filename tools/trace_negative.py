import sys

sys.path.insert(0, 'tools')
from pce_system import PCESystem
from emu_game import Disc, TRACK

rom = open('syscard3.pce', 'rb').read()
emu = PCESystem(Disc(TRACK), verbose=False)
for i, x in enumerate(rom):
    emu.mem[i] = x
emu._bios_enabled = False
emu.cpu.mpr = [0xFF, 0xF8, 0, 0, 0, 0, 0, 0]
emu.cpu.pc = 0xE0F3
emu.cpu.sp = 0xFF

trace = []
calls = []
orig = emu._scsi_exec
hit = {}

def scsi():
    p = bytes(emu.cd_params)
    if p and p[0] == 0x08:
        lba = (p[1] << 16) | (p[2] << 8) | p[3]
        if lba > 0x800000 and not hit:
            sp = emu.cpu.sp
            st = [emu.read(0x100 | ((sp + k + 1) & 0xFF)) for k in range(16)]
            hit['pc'] = emu.cpu.pc
            hit['lba'] = lba
            hit['sp'] = sp
            hit['stack'] = st
            hit['last'] = list(trace)
            hit['calls'] = list(calls[-20:])
    orig()

emu._scsi_exec = scsi

for n in range(1, 3000001):
    pc = emu.cpu.pc
    trace.append(pc)
    if len(trace) > 60: trace.pop(0)
    mn = emu.cpu.step()
    if mn in ('JSR', 'JMP', 'RTS', 'RTI'):
        calls.append((n, pc, mn, emu.cpu.pc))
    if n % 2000 == 0 and not emu.cpu.fI:
        emu.vdc_status |= 0x20
        emu.cpu.interrupt(0xFFF8)
    if hit:
        break

if not hit:
    emu.cpu.pc = 0x4167
    emu.mem[0x1F0000 + 0x3C00] = 0
    for n in range(1, 8000001):
        pc = emu.cpu.pc
        trace.append(pc)
        if len(trace) > 60: trace.pop(0)
        mn = emu.cpu.step()
        if mn in ('JSR', 'JMP', 'RTS', 'RTI'):
            calls.append((n, pc, mn, emu.cpu.pc))
        if n % 2000 == 0 and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(0xFFF8)
        if hit:
            break

if not hit:
    print('no negative read hit; pc=%04X' % emu.cpu.pc)
    sys.exit(0)

print('negative read at pc=%04X lba=0x%06X sp=%02X' % (hit['pc'], hit['lba'], hit['sp']))
print('stack:', ' '.join('%02X' % b for b in hit['stack']))
print('return candidates:', ['%04X' % (hit['stack'][i] | (hit['stack'][i+1] << 8)) for i in range(0, 14, 2)])
print('last pcs:', ' '.join('%04X' % p for p in hit['last']))
print('last calls:')
for t in hit['calls']:
    print('  %7d %04X %-3s -> %04X' % t)
