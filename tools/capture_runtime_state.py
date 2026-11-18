#!/usr/bin/env python3
"""Resume a gameplay save state in the local PCE emulator and render it.

This is useful when a Mednafen state is paused inside the System Card VSync
routine: the tool returns past that one in-flight call, advances the game, and
captures the live VRAM/CRAM result. It does not read sectors from a disc.

Usage:
    py -3 tools/capture_runtime_state.py STATE.mc3 [OUTPUT.png]
"""
import argparse
from collections import Counter, deque
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pce_state import decompress, parse
from pce_system import PCESystem
from pce_timing import NTSC_FRAME_CYCLES, PCEFrameClock
from render_pce_state import (composite_sprites, palette_colors,
                              render_background, render_sprite_atlas)


class NullDisc:
    """The stage is already resident in the save state; fail closed on reads."""
    def __init__(self):
        self.reads = []

    def read_sector(self, sector):
        self.reads.append(sector)
        return bytes(2048)


def u16(data):
    return int.from_bytes(data[:2], 'little')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state')
    parser.add_argument('output', nargs='?', default='build/runtime_capture.png')
    parser.add_argument('--settle-steps', type=int, default=100_000)
    parser.add_argument('--right-steps', type=int, default=2_500_000)
    parser.add_argument('--real-bios-vsync', action='store_true',
                        help='run the System Card VSync/IRQ code instead of the BIOS shim')
    parser.add_argument('--vblank-cycles', type=int, default=NTSC_FRAME_CYCLES,
                        help='approximate high-speed CPU cycles per NTSC frame')
    parser.add_argument('--atlas', help='also write a labeled SAT atlas')
    args = parser.parse_args()

    variables = parse(decompress(args.state))
    get = lambda name: variables[name][2]
    required = ('CDRAM', 'BaseRAM', 'VRAM', 'color_table', 'SAT', 'MPR',
                'PC', 'A', 'X', 'Y', 'S', 'P')
    missing = [name for name in required if name not in variables]
    if missing:
        parser.error('state is missing: ' + ', '.join(missing))

    emu = PCESystem(NullDisc(), verbose=False)
    if os.path.isfile('syscard3.pce'):
        rom = open('syscard3.pce', 'rb').read()
        emu.mem[:len(rom)] = rom
    emu.mem[0x100000:0x100000 + len(get('CDRAM'))] = get('CDRAM')
    emu.mem[0x1F0000:0x1F2000] = get('BaseRAM')[:0x2000]
    if 'SaveRAM' in variables:
        saveram = get('SaveRAM')
        emu.mem[0x1EE000:0x1EE000 + len(saveram)] = saveram
    emu.vram[:] = get('VRAM')
    for i in range(512):
        emu.cram[i] = get('color_table')[2 * i] | (get('color_table')[2 * i + 1] << 8)

    # Restore the VDC registers Mednafen stores separately from VRAM.
    register_names = {
        5: 'CR', 6: 'RCR', 7: 'BXR', 8: 'BYR', 9: 'MWR',
        10: 'HSR', 11: 'HDR', 12: 'VSR', 13: 'VDR', 14: 'VCR',
        15: 'DCR', 16: 'SOUR', 17: 'DESR', 18: 'LENR', 19: 'SATB',
    }
    for index, name in register_names.items():
        if name in variables:
            emu.regs[index] = u16(get(name))
    if 'MAWR' in variables:
        emu.mawr = u16(get('MAWR'))
    if 'MARR' in variables:
        emu.marr = u16(get('MARR'))

    cpu = emu.cpu
    cpu.pc = u16(get('PC'))
    cpu.a, cpu.x, cpu.y, cpu.sp = (get(name)[0] for name in ('A', 'X', 'Y', 'S'))
    p = get('P')[0]
    cpu.fN, cpu.fV, cpu.fD = (p >> 7) & 1, (p >> 6) & 1, (p >> 3) & 1
    cpu.fI, cpu.fZ, cpu.fC = (p >> 2) & 1, (p >> 1) & 1, p & 1
    cpu.mpr = list(get('MPR'))
    emu._bios_enabled = not args.real_bios_vsync
    frame_clock = PCEFrameClock(args.vblank_cycles) if args.real_bios_vsync else None
    joy_reads = Counter()
    original_io_read = emu.io_read

    def trace_io_read(addr):
        value = original_io_read(addr)
        if addr == 0x1000:
            joy_reads[(emu.joy_select, value)] += 1
        return value

    emu.io_read = trace_io_read

    # The saved CPU is inside the System Card's ex_vsync wait. In shim mode,
    # skip its active RTS frame; real-BIOS mode runs the wait and injects VBlank.
    initial_pc = cpu.pc
    if initial_pc == 0xE3C1 and not args.real_bios_vsync:
        stack = 0x1F0000 + 0x100
        lo = emu.mem[stack + ((cpu.sp + 1) & 0xFF)]
        hi = emu.mem[stack + ((cpu.sp + 2) & 0xFF)]
        cpu.pc = (((hi << 8) | lo) + 1) & 0xFFFF
        cpu.sp = (cpu.sp + 2) & 0xFF

    start_bxr, start_byr = emu.regs[7] & 0x3FF, emu.regs[8] & 0x1FF
    start_x = int.from_bytes(get('BG_XOffset')[:4], 'little') & 511 \
        if 'BG_XOffset' in variables else start_bxr
    start_y = int.from_bytes(get('BG_YOffset')[:4], 'little') & 511 \
        if 'BG_YOffset' in variables else start_byr

    stop_error = None
    vblank_irqs = 0
    last_ops = deque(maxlen=24)
    mpr6_changes = deque(maxlen=32)
    mpr0_changes = deque(maxlen=32)
    lowram_entries = deque(maxlen=32)
    stack_slot_writes = deque(maxlen=64)
    workram_entries = []

    original_cpu_write = cpu.write

    def trace_cpu_write(addr, value):
        if addr in (0x1F9, 0x1FA):
            stack_slot_writes.append({
                'pc': '%04X' % cpu.pc,
                'sp': '%02X' % cpu.sp,
                'addr': '%04X' % addr,
                'before': '%02X' % emu.mem[0x1F0000 + addr],
                'after': '%02X' % (value & 0xFF),
            })
        original_cpu_write(addr, value)

    cpu.write = trace_cpu_write

    def run(steps):
        nonlocal stop_error, vblank_irqs
        for step in range(steps):
            pc0 = cpu.pc
            opc = emu.mem[cpu.phys(pc0)]
            old_mpr0 = cpu.mpr[0]
            old_mpr6 = cpu.mpr[6]
            old_in_workram = 0x2000 <= pc0 < 0x4000
            rts_return = None
            if opc == 0x60:
                stack = 0x1F0100
                lo = emu.mem[stack + ((cpu.sp + 1) & 0xFF)]
                hi = emu.mem[stack + ((cpu.sp + 2) & 0xFF)]
                rts_return = (hi << 8) | lo
            last_ops.append({'pc': '%04X' % pc0, 'opcode': '%02X' % opc})
            try:
                cpu.step()
            except RuntimeError as exc:
                stop_error = str(exc)
                return step
            if frame_clock and frame_clock.after_instruction(emu, pc0, opc):
                vblank_irqs += 1
            if cpu.mpr[0] != old_mpr0:
                mpr0_changes.append({
                    'pc': '%04X' % pc0, 'opcode': '%02X' % opc,
                    'before': '%02X' % old_mpr0,
                    'after': '%02X' % cpu.mpr[0],
                })
            if (cpu.mpr[6] != old_mpr6 and
                    not (old_mpr6 in (0x83, 0x87) and
                         cpu.mpr[6] in (0x83, 0x87))):
                mpr6_changes.append({
                    'pc': '%04X' % pc0, 'opcode': '%02X' % opc,
                    'before': '%02X' % old_mpr6,
                    'after': '%02X' % cpu.mpr[6],
                })
            if (not 0 <= pc0 < 0x2000 and 0 <= cpu.pc < 0x2000):
                lowram_entries.append({
                    'from_pc': '%04X' % pc0, 'opcode': '%02X' % opc,
                    'to_pc': '%04X' % cpu.pc,
                    'mpr0': '%02X' % cpu.mpr[0],
                    'sp_before': '%02X' % ((cpu.sp - 2) & 0xFF)
                    if opc == 0x60 else None,
                    'rts_return': '%04X' % rts_return
                    if rts_return is not None else None,
                })
            if (not old_in_workram and 0x2000 <= cpu.pc < 0x4000
                    and len(workram_entries) < 128):
                workram_entries.append({
                    'from_pc': '%04X' % pc0, 'opcode': '%02X' % opc,
                    'to_pc': '%04X' % cpu.pc,
                    'mpr6': '%02X' % cpu.mpr[6],
                })
        return steps

    steps_done = run(args.settle_steps)
    if stop_error is None:
        emu.joy_high = 0x0D  # PCE active-low RIGHT; SEL=1 direction nibble
        steps_done += run(args.right_steps)
    if stop_error is None:
        emu.joy_high = 0x0F
        steps_done += run(args.settle_steps)

    dx = ((emu.regs[7] & 0x3FF) - start_bxr) & 0x3FF
    dy = ((emu.regs[8] & 0x1FF) - start_byr) & 0x1FF
    scroll_x, scroll_y = (start_x + dx) & 511, (start_y + dy) & 511
    vram = bytes(emu.vram)
    cram = bytearray()
    for color in emu.cram:
        cram.extend((color & 0xFF, (color >> 8) & 0xFF))
    # The state exposes the last completed SAT DMA separately. Gameplay code
    # can update the SATB source in VRAM after the save, so read that live
    # table instead of reusing the stale decoded SAT section.
    sat_base = ((emu.regs[19] & 0x7FFF) << 1) & 0xFFFF
    sat = vram[sat_base:sat_base + 512]
    colors = palette_colors(cram)
    image, opaque = render_background(vram, colors, scroll_x, scroll_y)
    image = composite_sprites(image, opaque, vram, colors, sat)

    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    image.save(output)
    stem, _ = os.path.splitext(output)
    open(stem + '.vram.bin', 'wb').write(vram)
    open(stem + '.cram.bin', 'wb').write(cram)
    open(stem + '.sat.bin', 'wb').write(sat)
    changed_bat = sum(
        1 for i in range(4096)
        if (get('VRAM')[2 * i] | (get('VRAM')[2 * i + 1] << 8)) !=
        (vram[2 * i] | (vram[2 * i + 1] << 8))
    )
    report = {
        'source': os.path.abspath(args.state),
        'output': output,
        'bios_mode': 'real-vsync' if args.real_bios_vsync else 'shim',
        'vblank_irqs': vblank_irqs,
        'vblank_cycles_per_frame': args.vblank_cycles
        if args.real_bios_vsync else None,
        'elapsed_cpu_cycles': frame_clock.cycles if frame_clock else None,
        'start_pc': '%04X' % initial_pc,
        'final_pc': '%04X' % cpu.pc,
        'final_cpu': {
            'a': '%02X' % cpu.a, 'x': '%02X' % cpu.x,
            'y': '%02X' % cpu.y, 'sp': '%02X' % cpu.sp,
            'p': '%02X' % cpu.p(),
            'mpr': ['%02X' % value for value in cpu.mpr],
        },
        'joypad': {
            'joy_low': '%X' % emu.joy_low,
            'joy_high': '%X' % emu.joy_high,
            'select': emu.joy_select,
            'read_counts_by_select_and_value': {
                '%d:%X' % key: count for key, count in sorted(joy_reads.items())
            },
            'workram_2220_223f': bytes(
                emu.mem[0x1F0000 + i] for i in range(0x220, 0x240)
            ).hex(' '),
        },
        'steps': steps_done,
        'scroll': [scroll_x, scroll_y],
        'bat_words_changed': changed_bat,
        'sat_bytes_changed': sum(a != b for a, b in zip(get('SAT'), sat)),
        'sat_vram_byte_offset': sat_base,
        'vram_words_written': len(emu.vram_writes),
        'disc_reads': emu.disc.reads,
        'mpr6_changes': list(mpr6_changes),
        'mpr0_changes': list(mpr0_changes),
        'lowram_entries': list(lowram_entries),
        'stack_slot_writes': list(stack_slot_writes),
        'workram_entries': workram_entries,
    }
    if stop_error:
        report['stop_error'] = stop_error
        pc0 = cpu.pc
        phys = cpu.phys(pc0)
        stack = 0x1F0000 + 0x100
        report['failure_context'] = {
            'registers': {
                'pc': '%04X' % cpu.pc, 'a': '%02X' % cpu.a,
                'x': '%02X' % cpu.x, 'y': '%02X' % cpu.y,
                'sp': '%02X' % cpu.sp, 'p': '%02X' % cpu.p(),
                'mpr': ['%02X' % v for v in cpu.mpr],
            },
            'physical_pc': '%06X' % phys,
            'bytes_at_pc': bytes(emu.mem[phys:phys + 16]).hex(' '),
            'stack_top': bytes(emu.mem[stack + ((cpu.sp + 1 + i) & 0xFF)]
                               for i in range(16)).hex(' '),
            'last_ops': list(last_ops),
        }
    with open(stem + '.json', 'w') as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))
    if args.atlas:
        render_sprite_atlas(vram, colors, sat, args.atlas)


if __name__ == '__main__':
    main()
