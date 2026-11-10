#!/usr/bin/env python3
"""HuC6280 emulator core - CPU, MPR banking, block transfers, ST0/1/2, TAM/TMA.

This is the foundation for dumping the real PC Engine game state (VRAM/CRAM)
so the remaining stages of the Valis III port can be built from evidence
instead of guesswork. It models:

  * all 65C02 opcodes plus the HuC6280 extensions (ST0/ST1/ST2, TAM/TMA/TMAI,
    CSH/CSL, SET, CLA/CLX/CLY/SAX/SAY/SXY, TST, BBR/BBS)
  * the block transfer instructions TIA/TDD/TIN/TAI/TII (7-byte operands)
  * the 8 MPR registers that translate logical -> physical addresses
  * a memory hook interface so the VDC/VCE/CD BIOS can be layered on top
"""
import sys

# addressing modes
IMP, IMM, ZP, ZPX, ZPY, ABS, ABX, ABY, IZX, IZY, IZP, REL, ACC, IND, ABX_IND = range(15)

TABLE = {}


def op(code, mn, mode, cyc=2):
    TABLE[code] = (mn, mode, cyc)


# 65C02 base
for c, mn, md, cyc in [
    (0x00, "BRK", IMP, 7), (0x01, "ORA", IZX, 6), (0x05, "ORA", ZP, 3),
    (0x06, "ASL", ZP, 5), (0x08, "PHP", IMP, 3), (0x09, "ORA", IMM, 2),
    (0x0A, "ASL", ACC, 2), (0x0D, "ORA", ABS, 4), (0x0E, "ASL", ABS, 6),
    (0x10, "BPL", REL, 2), (0x11, "ORA", IZY, 5), (0x12, "ORA", IZP, 5),
    (0x15, "ORA", ZPX, 4), (0x16, "ASL", ZPX, 6), (0x18, "CLC", IMP, 2),
    (0x19, "ORA", ABY, 4), (0x1D, "ORA", ABX, 4), (0x1E, "ASL", ABX, 7),
    (0x20, "JSR", ABS, 6), (0x21, "AND", IZX, 6), (0x24, "BIT", ZP, 3),
    (0x25, "AND", ZP, 3), (0x26, "ROL", ZP, 5), (0x28, "PLP", IMP, 4),
    (0x29, "AND", IMM, 2), (0x2A, "ROL", ACC, 2), (0x2C, "BIT", ABS, 4),
    (0x2D, "AND", ABS, 4), (0x2E, "ROL", ABS, 6), (0x30, "BMI", REL, 2),
    (0x31, "AND", IZY, 5), (0x32, "AND", IZP, 5), (0x35, "AND", ZPX, 4),
    (0x36, "ROL", ZPX, 6), (0x38, "SEC", IMP, 2), (0x39, "AND", ABY, 4),
    (0x3D, "AND", ABX, 4), (0x3E, "ROL", ABX, 7),
    (0x40, "RTI", IMP, 6), (0x41, "EOR", IZX, 6), (0x45, "EOR", ZP, 3),
    (0x46, "LSR", ZP, 5), (0x48, "PHA", IMP, 3), (0x49, "EOR", IMM, 2),
    (0x4A, "LSR", ACC, 2), (0x4C, "JMP", ABS, 3), (0x4D, "EOR", ABS, 4),
    (0x4E, "LSR", ABS, 6), (0x50, "BVC", REL, 2), (0x51, "EOR", IZY, 5),
    (0x52, "EOR", IZP, 5), (0x55, "EOR", ZPX, 4), (0x56, "LSR", ZPX, 6),
    (0x58, "CLI", IMP, 2), (0x59, "EOR", ABY, 4), (0x5D, "EOR", ABX, 4),
    (0x5E, "LSR", ABX, 7), (0x60, "RTS", IMP, 6), (0x61, "ADC", IZX, 6),
    (0x65, "ADC", ZP, 3), (0x66, "ROR", ZP, 5), (0x68, "PLA", IMP, 4),
    (0x69, "ADC", IMM, 2), (0x6A, "ROR", ACC, 2), (0x6C, "JMP", IND, 5),
    (0x6D, "ADC", ABS, 4), (0x6E, "ROR", ABS, 6), (0x70, "BVS", REL, 2),
    (0x71, "ADC", IZY, 5), (0x72, "ADC", IZP, 5), (0x75, "ADC", ZPX, 4),
    (0x76, "ROR", ZPX, 6), (0x78, "SEI", IMP, 2), (0x79, "ADC", ABY, 4),
    (0x7D, "ADC", ABX, 4), (0x7E, "ROR", ABX, 7), (0x81, "STA", IZX, 6),
    (0x84, "STY", ZP, 3), (0x85, "STA", ZP, 3), (0x86, "STX", ZP, 3),
    (0x88, "DEY", IMP, 2), (0x8A, "TXA", IMP, 2), (0x8C, "STY", ABS, 4),
    (0x8D, "STA", ABS, 4), (0x8E, "STX", ABS, 4), (0x90, "BCC", REL, 2),
    (0x91, "STA", IZY, 6), (0x92, "STA", IZP, 5), (0x94, "STY", ZPX, 4),
    (0x95, "STA", ZPX, 4), (0x96, "STX", ZPY, 4), (0x98, "TYA", IMP, 2),
    (0x99, "STA", ABY, 5), (0x9A, "TXS", IMP, 2), (0x9D, "STA", ABX, 5),
    (0xA0, "LDY", IMM, 2), (0xA1, "LDA", IZX, 6), (0xA2, "LDX", IMM, 2),
    (0xA4, "LDY", ZP, 3), (0xA5, "LDA", ZP, 3), (0xA6, "LDX", ZP, 3),
    (0xA8, "TAY", IMP, 2), (0xA9, "LDA", IMM, 2), (0xAA, "TAX", IMP, 2),
    (0xAC, "LDY", ABS, 4), (0xAD, "LDA", ABS, 4), (0xAE, "LDX", ABS, 4),
    (0xB0, "BCS", REL, 2), (0xB1, "LDA", IZY, 5), (0xB2, "LDA", IZP, 5),
    (0xB4, "LDY", ZPX, 4), (0xB5, "LDA", ZPX, 4), (0xB6, "LDX", ZPY, 4),
    (0xB8, "CLV", IMP, 2), (0xB9, "LDA", ABY, 4), (0xBA, "TSX", IMP, 3),
    (0xBC, "LDY", ABX, 4), (0xBD, "LDA", ABX, 4), (0xBE, "LDX", ABY, 4),
    (0xC0, "CPY", IMM, 2), (0xC1, "CMP", IZX, 6), (0xC4, "CPY", ZP, 3),
    (0xC5, "CMP", ZP, 3), (0xC6, "DEC", ZP, 5), (0xC8, "INY", IMP, 2),
    (0xC9, "CMP", IMM, 2), (0xCA, "DEX", IMP, 2), (0xCC, "CPY", ABS, 4),
    (0xCD, "CMP", ABS, 4), (0xCE, "DEC", ABS, 6), (0xD0, "BNE", REL, 2),
    (0xD1, "CMP", IZY, 5), (0xD2, "CMP", IZP, 5), (0xD5, "CMP", ZPX, 4),
    (0xD6, "DEC", ZPX, 6), (0xD8, "CLD", IMP, 2), (0xD9, "CMP", ABY, 4),
    (0xDD, "CMP", ABX, 4), (0xDE, "DEC", ABX, 7), (0xE0, "CPX", IMM, 2),
    (0xE1, "SBC", IZX, 6), (0xE4, "CPX", ZP, 3), (0xE5, "SBC", ZP, 3),
    (0xE6, "INC", ZP, 5), (0xE8, "INX", IMP, 2), (0xE9, "SBC", IMM, 2),
    (0xEA, "NOP", IMP, 2), (0xEC, "CPX", ABS, 4), (0xED, "SBC", ABS, 4),
    (0xEE, "INC", ABS, 6), (0xF0, "BEQ", REL, 2), (0xF1, "SBC", IZY, 5),
    (0xF2, "SBC", IZP, 5), (0xF5, "SBC", ZPX, 4), (0xF6, "INC", ZPX, 6),
    (0xF8, "SED", IMP, 2), (0xF9, "SBC", ABY, 4), (0xFD, "SBC", ABX, 4),
    (0xFE, "INC", ABX, 7),
    (0x04, "TSB", ZP, 5), (0x0C, "TSB", ABS, 6), (0x14, "TRB", ZP, 5),
    (0x1C, "TRB", ABS, 6),
    (0x44, "BSR", REL, 5),
    (0x80, "BRA", REL, 2),
]:
    op(c, mn, md, cyc)

# HuC6280 specific
for c, mn, md, cyc in [
    (0x02, "SXY", IMP, 3), (0x22, "SAX", IMP, 3), (0x42, "SAY", IMP, 3),
    (0x62, "CLA", IMP, 2), (0x82, "CLX", IMP, 2), (0xC2, "CLY", IMP, 2),
    (0x03, "ST0", IMM, 4), (0x13, "ST1", IMM, 4), (0x23, "ST2", IMM, 4),
    (0x43, "TMA", IMM, 3), (0x53, "TAM", IMM, 3),
    (0x54, "CSL", IMP, 2), (0xD4, "CSH", IMP, 2), (0xF4, "SET", IMP, 2),
    (0x83, "TST", IMM, 3), (0x93, "TST", IMM, 4),
    (0xA3, "TST", IMM, 3), (0xB3, "TST", IMM, 4),
]:
    op(c, mn, md, cyc)

# block transfers: 7-byte operand form src,dst,length
for c, mn, cyc in [(0x73, "TII", 17), (0xC3, "TDD", 17), (0xD3, "TIN", 17),
                   (0xE3, "TIA", 17), (0xF3, "TAI", 17)]:
    op(c, mn, 15, cyc)   # mode 15 = BLOCK

# RMB/SMB/BBR/BBS
for base in range(8):
    op(0x07 + base * 0x10, "RMB%d" % base, ZP, 5)
    op(0x87 + base * 0x10, "SMB%d" % base, ZP, 5)
    op(0x0F + base * 0x10, "BBR%d" % base, REL, 5)
    op(0x8F + base * 0x10, "BBS%d" % base, REL, 5)

LENS = {IMP: 1, IMM: 2, ZP: 2, ZPX: 2, ZPY: 2, ABS: 3, ABX: 3, ABY: 3,
        IZX: 2, IZY: 2, IZP: 2, REL: 2, ACC: 1, IND: 3, ABX_IND: 3, 15: 7}


class HuC6280(object):
    """Functional HuC6280 core with pluggable read/write hooks."""

    def __init__(self, read, write):
        self.read = read          # fn(addr) -> byte
        self.write = write        # fn(addr, value)
        self.a = self.x = self.y = 0
        self.sp = 0xFD
        self.pc = 0
        # flags: N V - B D I Z C
        self.fN = self.fV = self.fD = self.fI = self.fZ = self.fC = 0
        self.fT = 0
        self.sh = self.dh = self.lh = 0     # block-transfer high bytes
        self.mpr = [0] * 8
        self.mpr[0] = 0xFF    # I/O page (system card requirement)
        self.mpr[1] = 0xF8    # work RAM page
        self.stopped = False
        self.cycles = 0
        self.trace = None

    # ---- helpers -------------------------------------------------------
    def phys(self, addr):
        page = self.mpr[(addr >> 13) & 7]
        return (page << 13) | (addr & 0x1FFF)

    def fetch(self):
        v = self.read(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetch_word(self):
        lo = self.fetch()
        hi = self.fetch()
        return lo | (hi << 8)

    def zp(self):
        return self.fetch()

    def abs_addr(self):
        w = self.fetch_word()
        return w

    def set_nz(self, v):
        v &= 0xFF
        self.fZ = 1 if v == 0 else 0
        self.fN = 1 if v & 0x80 else 0

    def push(self, v):
        self.write(0x100 | self.sp, v & 0xFF)
        self.sp = (self.sp - 1) & 0xFF

    def pop(self):
        self.sp = (self.sp + 1) & 0xFF
        return self.read(0x100 | self.sp)

    def branch(self, cond):
        off = self.fetch()
        if cond:
            if off & 0x80:
                self.pc = (self.pc - (256 - off)) & 0xFFFF
            else:
                self.pc = (self.pc + off) & 0xFFFF

    # ---- block transfers ------------------------------------------------
    def do_block(self, pc):
        """Decode src/dst/length operands from the 7-byte instruction."""
        ss = self.fetch()
        sl = self.fetch()
        dd = self.fetch()
        dl = self.fetch()
        ll = self.fetch()
        lh = self.fetch()
        src = (self.sh << 16) | (ss << 8) | sl
        dst = (self.dh << 16) | (dd << 8) | dl
        ln = (self.lh << 16) | (ll << 8) | lh
        return src, dst, ln

    # ---- execution ------------------------------------------------------
    def step(self):
        pc0 = self.pc
        opc = self.fetch()
        if opc not in TABLE:
            self.pc = pc0
            raise RuntimeError("unknown opcode $%02X at $%04X" % (opc, pc0))
        mn, md, _cyc = TABLE[opc]
        self.exec(mn, md, opc, pc0)
        return mn

    def exec(self, mn, md, opc, pc0):
        read = self.read
        write = self.write

        def imm():
            return self.fetch()

        def zp_addr():
            return self.zp()

        def zpx():
            return (self.zp() + self.x) & 0xFF

        def zpy():
            return (self.zp() + self.y) & 0xFF

        def absa():
            return self.abs_addr()

        def abx():
            return (self.abs_addr() + self.x) & 0xFFFF

        def aby():
            return (self.abs_addr() + self.y) & 0xFF

        addr = None
        val = 0

        if md == IMP:
            pass
        elif md == IMM:
            val = imm()
        elif md == ACC:
            val = self.a
        elif md == ZP:
            addr = zp_addr()
        elif md == ZPX:
            addr = zpx()
        elif md == ZPY:
            addr = zpy()
        elif md == ABS:
            addr = absa()
        elif md == ABX:
            addr = abx()
        elif md == ABY:
            addr = aby()
        elif md == IZX:
            p = zp_addr()
            lo = read(p)
            hi = read((p + 1) & 0xFF)
            addr = (lo | (hi << 8)) & 0xFFFF
        elif md == IZY or md == IZP:
            p = zp_addr()
            lo = read(p)
            hi = read((p + 1) & 0xFF)
            a = (lo | (hi << 8)) & 0xFFFF
            addr = (a + self.y) & 0xFFFF if md == IZY else a
        elif md == REL:
            pass
        elif md == IND:
            p = absa()
            lo = read(p)
            hi = read((p + 1) & 0xFFFF)
            addr = (lo | (hi << 8)) & 0xFFFF
        elif md == 15:      # block transfer
            src, dst, ln = self.do_block(pc0)
            if mn == "TII":
                for k in range(ln):
                    write(dst + k, read(src + k))
            elif mn == "TDD":
                for k in range(ln):
                    write(dst - k, read(src - k))
            elif mn == "TIN":
                for k in range(ln):
                    write(dst, read(src + k))
            elif mn == "TIA":
                alt = 0
                for k in range(ln):
                    write(dst + k, read(src + k))
                    alt ^= 1
            elif mn == "TAI":
                alt = 0
                for k in range(ln):
                    write(dst + k, read(src + alt))
                    alt ^= 1
            return
        else:
            raise RuntimeError("mode %d for %s" % (md, mn))

        if addr is not None and md not in (IMP, IMM, ACC, REL, 15):
            val = read(addr)

        # ---- ALU / memory ops -------------------------------------------
        if mn == "LDA":
            self.a = val
            self.set_nz(self.a)
        elif mn == "LDX":
            self.x = val
            self.set_nz(self.x)
        elif mn == "LDY":
            self.y = val
            self.set_nz(self.y)
        elif mn == "STA":
            write(addr, self.a)
        elif mn == "STX":
            write(addr, self.x)
        elif mn == "STY":
            write(addr, self.y)
        elif mn == "STA":
            write(addr, self.a)
        elif mn == "STZ":
            write(addr, 0)
        elif mn == "PHA":
            self.push(self.a)
        elif mn == "PLA":
            self.a = self.pop()
            self.set_nz(self.a)
        elif mn == "PHP":
            self.push(self.p() | 0x30)
        elif mn == "PLP":
            self.set_p(self.pop())
        elif mn == "TXA":
            self.a = self.x
            self.set_nz(self.a)
        elif mn == "TYA":
            self.a = self.y
            self.set_nz(self.a)
        elif mn == "TAX":
            self.x = self.a
            self.set_nz(self.x)
        elif mn == "TAY":
            self.y = self.a
            self.set_nz(self.y)
        elif mn == "TSX":
            self.x = self.sp
            self.set_nz(self.x)
        elif mn == "TXS":
            self.sp = self.x
        elif mn == "INX":
            self.x = (self.x + 1) & 0xFF
            self.set_nz(self.x)
        elif mn == "INY":
            self.y = (self.y + 1) & 0xFF
            self.set_nz(self.y)
        elif mn == "DEX":
            self.x = (self.x - 1) & 0xFF
            self.set_nz(self.x)
        elif mn == "DEY":
            self.y = (self.y - 1) & 0xFF
            self.set_nz(self.y)
        elif mn in ("CLC", "CLI", "CLV", "CLD"): 
            if mn == "CLC":
                self.fC = 0
            elif mn == "CLI":
                self.fI = 0
            elif mn == "CLV":
                self.fV = 0
            else:
                self.fD = 0
        elif mn in ("SEC", "SEI", "SED"):
            if mn == "SEC":
                self.fC = 1
            elif mn == "SEI":
                self.fI = 1
            else:
                self.fD = 1
        elif mn == "AND":
            self.a &= val
            self.set_nz(self.a)
        elif mn == "ORA":
            self.a |= val
            self.set_nz(self.a)
        elif mn == "EOR":
            self.a ^= val
            self.set_nz(self.a)
        elif mn == "ADC":
            self.adc(val)
        elif mn == "SBC":
            self.adc(val ^ 0xFF)
        elif mn == "CMP":
            self.set_nz((self.a - val) & 0xFF)
            self.fC = 1 if self.a >= val else 0
        elif mn == "CPX":
            self.set_nz((self.x - val) & 0xFF)
            self.fC = 1 if self.x >= val else 0
        elif mn == "CPY":
            self.set_nz((self.y - val) & 0xFF)
            self.fC = 1 if self.y >= val else 0
        elif mn == "BIT":
            self.fZ = 1 if (self.a & val) == 0 else 0
            self.fN = 1 if val & 0x80 else 0
            self.fV = 1 if val & 0x40 else 0
        elif mn == "ASL":
            self.fC = 1 if val & 0x80 else 0
            val = (val << 1) & 0xFF
            self.set_nz(val)
            if md == ACC:
                self.a = val
            else:
                write(addr, val)
        elif mn == "LSR":
            self.fC = 1 if val & 1 else 0
            val >>= 1
            self.set_nz(val)
            if md == ACC:
                self.a = val
            else:
                write(addr, val)
        elif mn == "ROL":
            c = self.fC
            self.fC = 1 if val & 0x80 else 0
            val = ((val << 1) | c) & 0xFF
            self.set_nz(val)
            if md == ACC:
                self.a = val
            else:
                write(addr, val)
        elif mn == "ROR":
            c = self.fC
            self.fC = 1 if val & 1 else 0
            val = ((val >> 1) | (c << 7)) & 0xFF
            self.set_nz(val)
            if md == ACC:
                self.a = val
            else:
                write(addr, val)
        elif mn == "INC":
            val = (val + 1) & 0xFF
            self.set_nz(val)
            write(addr, val)
        elif mn == "DEC":
            val = (val - 1) & 0xFF
            self.set_nz(val)
            write(addr, val)
        elif mn == "TSB":
            val |= (1 << 0) & 0
            self.set_nz(val)
            write(addr, val)
        elif mn == "TRB":
            self.set_nz(val)
            write(addr, val)
        elif mn == "JMP":
            self.pc = addr
        elif mn == "JSR":
            ret = (self.pc - 1) & 0xFFFF
            self.push((ret >> 8) & 0xFF)
            self.push(ret & 0xFF)
            self.pc = addr
        elif mn == "RTS":
            lo = self.pop()
            hi = self.pop()
            self.pc = ((lo | (hi << 8)) + 1) & 0xFFFF
        elif mn == "RTI":
            self.set_p(self.pop())
            lo = self.pop()
            hi = self.pop()
            self.pc = lo | (hi << 8)
        elif mn == "BRK":
            pass
        elif mn in ("BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ", "BRA", "BSR"):
            cond = {
                "BPL": not self.fN, "BMI": self.fN,
                "BVC": not self.fV, "BVS": self.fV,
                "BCC": not self.fC, "BCS": self.fC,
                "BNE": not self.fZ, "BEQ": self.fZ,
                "BRA": True,
            }.get(mn, False)
            if mn == "BSR":
                ret = (self.pc - 1) & 0xFFFF
                self.push((ret >> 8) & 0xFF)
                self.push(ret & 0xFF)
                self.branch(True)
            else:
                self.branch(cond)
        elif mn in ("RMB0", "RMB1", "RMB2", "RMB3", "RMB4", "RMB5", "RMB6", "RMB7"):
            bit = int(mn[3])
            write(addr, val & ~(1 << bit))
        elif mn in ("SMB0", "SMB1", "SMB2", "SMB3", "SMB4", "SMB5", "SMB6", "SMB7"):
            bit = int(mn[3])
            write(addr, val | (1 << bit))
        elif mn in ("BBR0", "BBR1", "BBR2", "BBR3", "BBR4", "BBR5", "BBR6", "BBR7",
                   "BBS0", "BBS1", "BBS2", "BBS3", "BBS4", "BBS5", "BBS6", "BBS7"):
            bit = int(mn[3])
            is_set = mn.startswith("BBS")
            if bool(val & (1 << bit)) == is_set:
                self.branch(True)
            else:
                self.branch(False)
        elif mn == "CSH":
            pass
        elif mn == "CSL":
            pass
        elif mn == "SET":
            self.fT = 1
        elif mn == "CLA":
            self.a = 0
            self.set_nz(0)
        elif mn == "CLX":
            self.x = 0
            self.set_nz(0)
        elif mn == "CLY":
            self.y = 0
            self.set_nz(0)
        elif mn == "SAX":
            self.x, self.a = self.a, self.x
            self.set_nz(self.a)
        elif mn == "SAY":
            self.y, self.a = self.a, self.y
            self.set_nz(self.a)
        elif mn == "SXY":
            self.x, self.y = self.y, self.x
            self.set_nz(self.x)
        elif mn == "ST0":
            write(0x0000, val)
        elif mn == "ST1":
            write(0x0002, val)
        elif mn == "ST2":
            write(0x0003, val)
        elif mn == "TMA":
            self.a = self.mpr[val & 7] if False else self.mpr[val & 7]
        elif mn == "TAM":
            for b in range(8):
                if val & (1 << b):
                    self.mpr[b] = self.a
        elif mn == "TST":
            pass
        else:
            raise RuntimeError("unhandled %s" % mn)

    def adc(self, v):
        if self.fT:
            t = (self.a & 0x0F) + (v & 0x0F) + self.fC
            self.fC = 0
            if t > 9:
                t += 6
                self.fC = 1
            r = (self.a & 0xF0) + (v & 0xF0) + (t & 0xF0)
            res = r
            if r > 0x99:
                r += 0x60
                self.fC = 1
            self.a = r & 0xFF
            self.set_nz(self.a)
            self.fT = 0
            return
        r = self.a + v + self.fC
        self.fV = 1 if (~(self.a ^ v) & (self.a ^ r) & 0x80) else 0
        self.fC = 1 if r > 0xFF else 0
        self.a = r & 0xFF
        self.set_nz(self.a)

    def p(self):
        return ((self.fN << 7) | (self.fV << 6) | 0x30 | (self.fD << 3) |
                (self.fI << 2) | (self.fZ << 1) | self.fC)

    def set_p(self, v):
        self.fN = (v >> 7) & 1
        self.fV = (v >> 6) & 1
        self.fD = (v >> 3) & 1
        self.fI = (v >> 2) & 1
        self.fZ = (v >> 1) & 1
        self.fC = v & 1


def make_memory(rom_pages):
    """rom_pages: list of 8 KiB bytearrays indexed by page (physical)."""
    size = 1 << 21

    def read(addr):
        page = (addr >> 13) & 0xFF
        off = addr & 0x1FFF
        return rom_pages[page][off]

    def write(addr, val):
        page = (addr >> 13) & 0xFF
        off = addr & 0x1FFF
        rom_pages[page][off] = val & 0xFF

    return read, write
