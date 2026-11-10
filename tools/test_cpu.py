#!/usr/bin/env python3
"""Static tests for the HuC6280 emulator core in tools/pce_cpu.py.

Verifies the opcode/transfer logic that the booting of the PC Engine game
depends on, so the emulator stays trustworthy as it evolves:

  1. immediate / absolute addressing, arithmetic and flags
  2. the 7-byte block transfer instructions (TII / TDD / TIN / TIA / TAI)
  3. TAM switching the MPR banks and the resulting logical->physical mapping
  4. ST0/ST1/ST2 routed to the hardwired VDC ports (io hook)
  5. branches, JSR/RTS stack behaviour (including the stack page being RAM)
"""
import sys

sys.path.insert(0, "tools")
from pce_cpu import HuC6280  # noqa: E402


def line(ok, label, detail=""):
    print("  %s %-52s %s" % ("PASS" if ok else "FAIL", label, detail))


def cpu_with(prog, phys=0):
    mem = bytearray(1 << 21)
    for i, b in enumerate(prog):
        mem[phys + i] = b
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = phys
    cpu.sp = 0xFF
    return cpu, mem


def run_until(cpu, n=32, stop=("RTS", "RTI")):
    for _ in range(n):
        mn = cpu.step()
        if mn in stop:
            return mn
    return None


def main():
    ok = True

    # --- 1. ALU / flags ------------------------------------------------
    cpu, mem = cpu_with([0xA9, 0x05, 0x85, 0x10, 0xA9, 0x04, 0x69, 0x02,
                         0x85, 0x11, 0x60])
    run_until(cpu)
    line(cpu.a == 6, "ADC #$02 with A=$04", "A=%d" % cpu.a)
    line(mem[0x10] == 5 and mem[0x11] == 6,
         "STA writes go to the zero page", "mem=$10:%02X $11:%02X" %
         (mem[0x10], mem[0x11]))
    ok &= cpu.a == 6 and mem[0x11] == 6

    cpu, mem = cpu_with([0xA9, 0x00, 0x38, 0x69, 0xFF, 0x60])   # SEC; ADC #$FF
    run_until(cpu)
    line(cpu.a == 0 and cpu.fC == 1, "ADC #$FF with carry set wraps to 0",
         "A=%02X C=%d" % (cpu.a, cpu.fC))
    ok &= cpu.a == 0 and cpu.fC == 1

    # --- 2. block transfers --------------------------------------------
    # TII is a plain forward copy.  TDD copies backwards (dst first, then
    # descending), TIN fills one destination byte from a rising source and
    # TAI re-reads each source byte twice.  TIA is tested separately below.
    for name, opcode in (("TII", 0x73), ("TAI", 0xF3)):
        mem = bytearray(1 << 21)
        for i in range(16):
            mem[0x100 + i] = 0xAA
        # block operands are little-endian: $0100 -> $0200, length $0010
        prog = [opcode, 0x00, 0x01, 0x00, 0x02, 0x10, 0x00, 0x60]
        for i, b in enumerate(prog):
            mem[i] = b
        cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
        cpu.mpr = [0xF8, 0xF8] + [0] * 6
        cpu.pc = 0
        run_until(cpu)
        dst = bytes(mem[0x200:0x210])
        line(set(dst) == {0xAA}, "%s moves 16 bytes $0100 -> $0200" % name,
             "dst=%s" % dst[:8].hex())
        ok &= set(dst) == {0xAA}

    # TIN copies the whole block into a *single* destination byte (the last
    # write wins) - the game uses it to seed one VRAM word.
    mem = bytearray(1 << 21)
    for i in range(16):
        mem[0x100 + i] = 0xAA
    prog = [0xD3, 0x00, 0x01, 0x00, 0x02, 0x10, 0x00, 0x60]
    for i, b in enumerate(prog):
        mem[i] = b
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = 0
    run_until(cpu)
    line(mem[0x200] == 0xAA and mem[0x201] == 0x00,
         "TIN writes the source block into one destination byte",
         "mem[200]=%02X mem[201]=%02X" % (mem[0x200], mem[0x201]))
    ok &= mem[0x200] == 0xAA

    # TDD copies backwards: source $0110..$0101 -> dest $0210..$0201.
    mem = bytearray(1 << 21)
    for i in range(16):
        mem[0x110 - i] = i          # mem[0x110]=0 ... mem[0x101]=15
    prog = [0xC3, 0x10, 0x01, 0x10, 0x02, 0x10, 0x00, 0x60]
    for i, b in enumerate(prog):
        mem[i] = b
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = 0
    run_until(cpu)
    ok &= bytes(mem[0x210 - i] for i in range(16)) == bytes(range(16))
    line(bytes(mem[0x210 - i] for i in range(16)) == bytes(range(16)),
         "TDD copies backwards from $0110 to $0210",
         "first=%s" % bytes(mem[0x210:0x218]).hex())

    # TIA alternates the destination between dst and dst+1 while the source
    # advances.  With dst=$0002 this streams bytes into the VDC's low/high
    # data ports as 16-bit VRAM words.  MAME h6280.cpp: write(to+alt, from++).
    mem = bytearray(1 << 21)
    mem[0x100] = 0x12
    mem[0x101] = 0x34
    mem[0x102] = 0x56
    mem[0x103] = 0x78
    prog = [0xE3, 0x00, 0x01, 0x00, 0x02, 0x04, 0x00, 0x60]
    for i, b in enumerate(prog):
        mem[i] = b
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = 0
    run_until(cpu)
    expect = bytes([0x56, 0x78])
    got = bytes(mem[0x200:0x202])
    line(got == expect,
         "TIA alternates the destination (VDC word stream)",
         "dst=%s (expect %s)" % (got.hex(), expect.hex()))
    ok &= got == expect

    # TAI increments the destination and alternates the source (2-byte pattern)
    mem = bytearray(1 << 21)
    mem[0x100] = 0x12
    mem[0x101] = 0x34
    prog = [0xF3, 0x00, 0x01, 0x00, 0x02, 0x04, 0x00, 0x60]
    for i, b in enumerate(prog):
        mem[i] = b
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = 0
    run_until(cpu)
    expect = bytes([0x12, 0x34, 0x12, 0x34])
    got = bytes(mem[0x200:0x204])
    line(got == expect,
         "TAI repeats a 2-byte source pattern",
         "dst=%s (expect %s)" % (got.hex(), expect.hex()))
    ok &= got == expect

    # BSR must push the instruction end (RTS goes to the byte after the
    # operand), not the operand itself.
    mem = bytearray(1 << 21)
    # BSR at 0 targets 4 (A9 42), RTS returns to 2 (the byte after the operand)
    prog = [0x44, 0x02, 0xEA, 0xEA, 0xA9, 0x42, 0x60]
    for i, b in enumerate(prog):
        mem[i] = b
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = 0
    run_until(cpu, n=3)
    line(cpu.pc == 0x02 and cpu.a == 0x42,
         "BSR returns to the instruction after the operand",
         "pc=%04X A=%02X" % (cpu.pc, cpu.a))
    ok &= cpu.pc == 0x02 and cpu.a == 0x42

    # --- 3. TAM / MPR mapping -------------------------------------------
    mem = bytearray(1 << 21)
    for i in range(16):
        mem[0x1234 + i] = i          # physical page $00, offset $1234
    for i in range(16):
        mem[0x1F0000 + 0x1234 + i] = 0x40 + i
    prog = [0xA9, 0x00, 0x53, 0x04,   # LDA #$00; TAM #$04 -> MPR2 = 0
            0x60]
    for i, b in enumerate(prog):
        mem[i] = b
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = 0
    run_until(cpu)
    line(cpu.mpr[2] == 0, "TAM #$04 sets MPR2", "MPR2=%02X" % cpu.mpr[2])
    line(cpu.phys(0x4FED) == 0x0FED, "logical $4FED maps into MPR2's page",
         "phys=%06X" % cpu.phys(0x4FED))
    ok &= cpu.mpr[2] == 0

    # --- 4. ST0/ST1/ST2 to the hardwired VDC ports ----------------------
    io = []
    prog = [0x03, 0x05,        # ST0 #$05  -> VDC register select
            0x13, 0x21,         # ST1 #$21  -> VDC data low
            0x23, 0x43,         # ST2 #$43  -> VDC data high
            0x60]
    mem = bytearray(1 << 21)
    for i, b in enumerate(prog):
        mem[i] = b
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF),
                  io_write=lambda a, v: io.append((a, v)))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = 0
    run_until(cpu)
    line(io == [(0x0000, 0x05), (0x0002, 0x21), (0x0003, 0x43)],
         "ST0/ST1/ST2 write the VDC ports directly",
         "%s" % ([(hex(a), hex(v)) for a, v in io],))
    ok &= io == [(0x0000, 0x05), (0x0002, 0x21), (0x0003, 0x43)]

    # --- 5. branches and the stack -------------------------------------
    mem = bytearray(1 << 21)
    prog = [0x20, 0x10, 0x00,     # JSR $0010
            0xEA, 0xEA,           # NOP NOP (the return address + 1)
            0x60]                 # RTS
    for i, b in enumerate(prog):
        mem[i] = b
    mem[0x10] = 0xA9              # LDA #$FF at $0010
    mem[0x11] = 0xFF
    mem[0x12] = 0x60              # RTS
    cpu = HuC6280(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v & 0xFF))
    cpu.mpr = [0xF8, 0xF8] + [0] * 6
    cpu.pc = 0
    run_until(cpu, n=16)
    line(cpu.a == 0xFF and cpu.pc == 0x03,
         "JSR/RTS return to the instruction after the call",
         "A=%02X pc=%04X" % (cpu.a, cpu.pc))
    ok &= cpu.a == 0xFF and cpu.pc == 0x03

    # the 6502 stack page must stay RAM even when MPR0 is switched to the
    # I/O page - the game does exactly that after its TAM setup.
    # (This behaviour lives in the PCESystem memory map, not the raw CPU.)
    from pce_system import PCESystem

    class _Disc(object):
        def read_sector(self, n):
            return b"\x00" * 2048

        def read_sectors(self, n, c):
            return b"\x00" * 2048 * c

    sysm = PCESystem(_Disc(), verbose=False)
    sysm.cpu.mpr[0] = 0xFF
    sysm.write(0x01FF, 0x42)
    got = sysm.read(0x01FF)
    line(got == 0x42 and sysm.mem[0x1F01FF] == 0x42,
         "stack page $0100-$01FF stays RAM with MPR0=$FF",
         "read=%02X" % got)
    ok &= got == 0x42 and sysm.mem[0x1F01FF] == 0x42

    print("RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
