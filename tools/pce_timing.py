"""Approximate HuC6280 time and deliver NTSC VBlank interrupts.

The emulator core is instruction-functional and does not model the VDC scan
timing. This helper uses the core's opcode cycle table, tracks CSH/CSL, and
delivers one pending VBlank at the next instruction boundary. It is intended
for long-running asset captures, not cycle-perfect emulation.
"""
from pce_cpu import TABLE, LENS


NTSC_FRAME_CYCLES = 119_318
BLOCK_OPS = {0x73, 0xC3, 0xD3, 0xE3, 0xF3}
BRANCH_OPS = {
    0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0,
    0x80, 0x44,
    0x0F, 0x1F, 0x2F, 0x3F, 0x4F, 0x5F, 0x6F, 0x7F,
    0x8F, 0x9F, 0xAF, 0xBF, 0xCF, 0xDF, 0xEF, 0xFF,
}


class PCEFrameClock:
    def __init__(self, frame_cycles=NTSC_FRAME_CYCLES, high_speed=True):
        self.frame_cycles = frame_cycles
        self.cycles = 0
        self.next_frame = frame_cycles
        self.high_speed = high_speed
        self.pending = False
        self.interrupts = 0

    def _instruction_cycles(self, cpu, pc, opcode):
        _, mode, cycles = TABLE[opcode]
        if opcode in BLOCK_OPS:
            lo = cpu.read((pc + 5) & 0xFFFF)
            hi = cpu.read((pc + 6) & 0xFFFF)
            length = lo | (hi << 8)
            cycles += 6 * (length or 0x10000)
        elif opcode in BRANCH_OPS:
            linear = (pc + LENS[mode]) & 0xFFFF
            if cpu.pc != linear:
                cycles += 1
                if (cpu.pc & 0xFF00) != (linear & 0xFF00):
                    cycles += 1
        return cycles

    def after_instruction(self, emu, pc, opcode, vector=0xFFF8):
        cycles = self._instruction_cycles(emu.cpu, pc, opcode)
        self.cycles += cycles * (1 if self.high_speed else 4)
        if opcode == 0xD4:       # CSH: 7.16 MHz
            self.high_speed = True
        elif opcode == 0x54:     # CSL: 1.79 MHz
            self.high_speed = False

        if self.cycles >= self.next_frame:
            while self.next_frame <= self.cycles:
                self.next_frame += self.frame_cycles
            self.pending = True

        if self.pending and not emu.cpu.fI:
            emu.vdc_status |= 0x20
            emu.cpu.interrupt(vector)
            self.pending = False
            self.interrupts += 1
            self.cycles += 8
            return True
        return False
