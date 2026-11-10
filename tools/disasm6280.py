#!/usr/bin/env python3
"""Minimal HuC6280 (65C02 + VDC) disassembler and code-density scanner.

Used to locate the game program inside the PCE CD data tracks and to dump
disassembly for reverse engineering the game logic.
"""
import os

# opcode -> (mnemonic, addressing mode)
# Modes: imp imm zp zpx zpy abs abx aby ind izx izy rel acc
OPCODES = {
    0x00: ("BRK", "imp"), 0x01: ("ORA", "izx"), 0x05: ("ORA", "zp"),
    0x04: ("TSB", "zp"), 0x06: ("ASL", "zp"), 0x07: ("RMB0", "zp"),
    0x08: ("PHP", "imp"), 0x09: ("ORA", "imm"), 0x0A: ("ASL", "acc"),
    0x0C: ("TSB", "abs"), 0x0D: ("ORA", "abs"), 0x0E: ("ASL", "abs"),
    0x10: ("BPL", "rel"), 0x11: ("ORA", "izy"), 0x12: ("ORA", "izp"),
    0x14: ("TRB", "zp"), 0x15: ("ORA", "zpx"), 0x16: ("ASL", "zpx"),
    0x18: ("CLC", "imp"), 0x19: ("ORA", "aby"), 0x1A: ("INC", "acc"),
    0x1D: ("ORA", "abx"), 0x1E: ("ASL", "abx"),
    0x20: ("JSR", "abs"), 0x21: ("AND", "izx"), 0x24: ("BIT", "zp"),
    0x25: ("AND", "zp"), 0x26: ("ROL", "zp"), 0x28: ("PLP", "imp"),
    0x29: ("AND", "imm"), 0x2A: ("ROL", "acc"), 0x2B: ("BVS", "rel"),
    0x2C: ("BIT", "abs"), 0x2D: ("AND", "abs"), 0x2E: ("ROL", "abs"),
    0x30: ("BMI", "rel"), 0x31: ("AND", "izy"), 0x32: ("AND", "izp"),
    0x34: ("BIT", "zpx"), 0x35: ("AND", "zpx"), 0x36: ("ROL", "zpx"),
    0x38: ("SEC", "imp"), 0x39: ("AND", "aby"), 0x3A: ("DEC", "acc"),
    0x3C: ("BIT", "abx"), 0x3D: ("AND", "abx"), 0x3E: ("ROL", "abx"),
    0x40: ("RTI", "imp"), 0x41: ("EOR", "izx"), 0x45: ("EOR", "zp"),
    0x46: ("LSR", "zp"), 0x48: ("PHA", "imp"), 0x49: ("EOR", "imm"),
    0x4A: ("LSR", "acc"), 0x4C: ("JMP", "abs"), 0x4D: ("EOR", "abs"),
    0x4E: ("LSR", "abs"), 0x50: ("BVC", "rel"), 0x51: ("EOR", "izy"),
    0x52: ("EOR", "izp"), 0x55: ("EOR", "zpx"), 0x56: ("LSR", "zpx"),
    0x58: ("CLI", "imp"), 0x59: ("EOR", "aby"), 0x5A: ("PHY", "imp"),
    0x5D: ("EOR", "abx"), 0x5E: ("LSR", "abx"),
    0x60: ("RTS", "imp"), 0x61: ("ADC", "izx"), 0x64: ("STZ", "zp"),
    0x65: ("ADC", "zp"), 0x66: ("ROR", "zp"), 0x68: ("PLA", "imp"),
    0x69: ("ADC", "imm"), 0x6A: ("ROR", "acc"), 0x6C: ("JMP", "ind"),
    0x6D: ("ADC", "abs"), 0x6E: ("ROR", "abs"), 0x70: ("BVS", "rel"),
    0x71: ("ADC", "izy"), 0x72: ("ADC", "izp"), 0x74: ("STZ", "zpx"),
    0x75: ("ADC", "zpx"), 0x76: ("ROR", "zpx"), 0x78: ("SEI", "imp"),
    0x79: ("ADC", "aby"), 0x7A: ("PLY", "imp"), 0x7D: ("ADC", "abx"),
    0x7E: ("ROR", "abx"), 0x81: ("STA", "izx"), 0x84: ("STY", "zp"),
    0x85: ("STA", "zp"), 0x86: ("STX", "zp"), 0x88: ("DEY", "imp"),
    0x8A: ("TXA", "imp"), 0x8B: ("TXY", "imp"), 0x8C: ("STY", "abs"),
    0x8D: ("STA", "abs"), 0x8E: ("STX", "abs"), 0x90: ("BCC", "rel"),
    0x91: ("STA", "izy"), 0x92: ("STA", "izp"), 0x94: ("STY", "zpx"),
    0x95: ("STA", "zpx"), 0x96: ("STX", "zpy"), 0x98: ("TYA", "imp"),
    0x99: ("STA", "aby"), 0x9A: ("TXS", "imp"), 0x9B: ("TXY", "imp"),
    0x9C: ("STZ", "abs"), 0x9D: ("STA", "abx"), 0x9E: ("STZ", "abx"),
    0xA0: ("LDY", "imm"), 0xA2: ("LDX", "imm"), 0xA4: ("LDY", "zp"),
    0xA5: ("LDA", "zp"), 0xA6: ("LDX", "zp"), 0xA8: ("TAY", "imp"),
    0xA9: ("LDA", "imm"), 0xAA: ("TAX", "imp"), 0xAC: ("LDY", "abs"),
    0xAD: ("LDA", "abs"), 0xAE: ("LDX", "abs"), 0xB0: ("BCS", "rel"),
    0xB1: ("LDA", "izy"), 0xB2: ("LDA", "izp"), 0xB4: ("LDY", "zpx"),
    0xB5: ("LDA", "zpx"), 0xB6: ("LDX", "zpy"), 0xB8: ("CLV", "imp"),
    0xB9: ("LDA", "aby"), 0xBA: ("TSX", "imp"), 0xBC: ("LDY", "abx"),
    0xBD: ("LDA", "abx"), 0xBE: ("LDX", "aby"), 0xC0: ("CPY", "imm"),
    0xC2: ("CPZ", "imm"), 0xC4: ("CPY", "zp"), 0xC5: ("CMP", "zp"),
    0xC6: ("DEC", "zp"), 0xC8: ("INY", "imp"), 0xC9: ("CMP", "imm"),
    0xCA: ("DEX", "imp"), 0xCC: ("CPY", "abs"), 0xCD: ("CMP", "abs"),
    0xCE: ("DEC", "abs"), 0xD0: ("BNE", "rel"), 0xD1: ("CMP", "izy"),
    0xD2: ("CMP", "izp"), 0xD4: ("CSZ", "zp"), 0xD5: ("CMP", "zpx"),
    0xD6: ("DEC", "zpx"), 0xD8: ("CLD", "imp"), 0xD9: ("CMP", "aby"),
    0xDA: ("PHX", "imp"), 0xDD: ("CMP", "abx"), 0xDE: ("DEC", "abx"),
    0xE0: ("CPX", "imm"), 0xE2: ("INC", "imm"), 0xE4: ("CPX", "zp"),
    0xE5: ("SBC", "zp"), 0xE6: ("INC", "zp"), 0xE8: ("INX", "imp"),
    0xE9: ("SBC", "imm"), 0xEA: ("NOP", "imp"), 0xEB: ("SWA", "imp"),
    0xEC: ("CPX", "abs"), 0xED: ("SBC", "abs"), 0xEE: ("INC", "abs"),
    0xF0: ("BEQ", "rel"), 0xF1: ("SBC", "izy"), 0xF2: ("SBC", "izp"),
    0xF4: ("PHW", "imm"), 0xF5: ("SBC", "zpx"), 0xF6: ("INC", "zpx"),
    0xF8: ("SED", "imp"), 0xF9: ("SBC", "aby"), 0xFA: ("PLX", "imp"),
    0xFD: ("SBC", "abx"), 0xFE: ("INC", "abx"),
}

LEN = {
    "imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "izx": 2,
    "izy": 2, "izp": 2, "rel": 2, "abs": 3, "abx": 3, "aby": 3, "ind": 3,
}


# --- HuC6280 specific / extended 65C02 opcodes (per HuC6280 manual) ---
OPCODES.update({
    0x02: ("SXY", "imp"), 0x03: ("ST0", "imm"), 0x12: ("ORA", "izp"),
    0x13: ("ST1", "imm"), 0x22: ("SAX", "imp"), 0x23: ("ST2", "imm"),
    0x32: ("AND", "izp"), 0x42: ("SAY", "imp"), 0x43: ("TMA", "imm"),
    0x52: ("EOR", "izp"), 0x53: ("TAM", "imm"), 0x62: ("CLA", "imp"),
    0x72: ("ADC", "izp"), 0x73: ("TII", "block"), 0x82: ("CLX", "imp"),
    0x83: ("TST", "tst_zp"), 0x92: ("STA", "izp"), 0x93: ("TST", "tst_abs"),
    0xA3: ("TST", "tst_zpx"), 0xB2: ("LDA", "izp"), 0xB3: ("TST", "tst_absx"),
    0xC2: ("CLY", "imp"), 0xC3: ("TDD", "block"), 0xD2: ("CMP", "izp"),
    0xD3: ("TIN", "block"), 0xD4: ("CSH", "imp"), 0xE3: ("TIA", "block"),
    0xF2: ("SBC", "izp"), 0xF3: ("TAI", "block"), 0xF4: ("SET", "imp"),
    0x54: ("CSL", "imp"), 0x44: ("BSR", "rel"), 0x80: ("BRA", "rel"),
    0x07: ("RMB0", "zp"), 0x17: ("RMB1", "zp"), 0x27: ("RMB2", "zp"),
    0x37: ("RMB3", "zp"), 0x47: ("RMB4", "zp"), 0x57: ("RMB5", "zp"),
    0x67: ("RMB6", "zp"), 0x77: ("RMB7", "zp"),
    0x87: ("SMB0", "zp"), 0x97: ("SMB1", "zp"), 0xA7: ("SMB2", "zp"),
    0xB7: ("SMB3", "zp"), 0xC7: ("SMB4", "zp"), 0xD7: ("SMB5", "zp"),
    0xE7: ("SMB6", "zp"), 0xF7: ("SMB7", "zp"),
    0x0F: ("BBR0", "bbr"), 0x1F: ("BBR1", "bbr"), 0x2F: ("BBR2", "bbr"),
    0x3F: ("BBR3", "bbr"), 0x4F: ("BBR4", "bbr"), 0x5F: ("BBR5", "bbr"),
    0x6F: ("BBR6", "bbr"), 0x7F: ("BBR7", "bbr"),
    0x8F: ("BBS0", "bbr"), 0x9F: ("BBS1", "bbr"), 0xAF: ("BBS2", "bbr"),
    0xBF: ("BBS3", "bbr"), 0xCF: ("BBS4", "bbr"), 0xDF: ("BBS5", "bbr"),
    0xEF: ("BBS6", "bbr"), 0xFF: ("BBS7", "bbr"),
    0x6C: ("JMP", "ind"), 0x7C: ("JMP", "abx"),
    0xDC: ("???", "imp"), 0x5C: ("???", "imp"), 0xFC: ("???", "imp"),
    0x1C: ("TRB", "abs"), 0x0C: ("TSB", "abs"), 0x3C: ("BIT", "abx"),
})

LEN.update({
    "block": 7, "tst_zp": 3, "tst_abs": 4, "tst_zpx": 3, "tst_absx": 4,
    "bbr": 3,
})


def disasm_one(code, pc):
    op = code[pc]
    if op not in OPCODES:
        return None, 1
    mn, mode = OPCODES[op]
    n = LEN[mode]
    b = code[pc:pc + n]
    if len(b) < n:
        return None, 1
    a = b[1] if n >= 2 else 0
    c = b[2] if n >= 3 else 0
    d = b[3] if n >= 4 else 0
    if mode == "imp":
        return "%s" % mn, n
    if mode == "acc":
        return "%s A" % mn, n
    if mode == "imm":
        return "%s #$%02X" % (mn, a), n
    if mode == "zp":
        return "%s $%02X" % (mn, a), n
    if mode == "zpx":
        return "%s $%02X,X" % (mn, a), n
    if mode == "zpy":
        return "%s $%02X,Y" % (mn, a), n
    if mode == "izx":
        return "%s ($%02X,X)" % (mn, a), n
    if mode == "izy":
        return "%s ($%02X),Y" % (mn, a), n
    if mode == "izp":
        return "%s ($%02X)" % (mn, a), n
    if mode == "rel":
        return "%s $%04X" % (mn, (pc + 2 + ((a ^ 0x80) - 0x80)) & 0xFFFF), n
    if mode == "abs":
        return "%s $%04X" % (mn, a | (c << 8)), n
    if mode == "abx":
        return "%s $%04X,X" % (mn, a | (c << 8)), n
    if mode == "aby":
        return "%s $%04X,Y" % (mn, a | (c << 8)), n
    if mode == "ind":
        return "%s ($%04X)" % (mn, a | (c << 8)), n
    if mode == "block":
        # opcode, ss, SS, dd, DD, ll, LL  (little-endian, like every 6502 word)
        src = b[1] | (b[2] << 8)
        dst = b[3] | (b[4] << 8)
        ln = b[5] | (b[6] << 8)
        return "%s $%04X, $%04X, $%04X" % (mn, src, dst, ln), n
    if mode == "tst_zp":
        return "%s #$%02X, $%02X" % (mn, a, c), n
    if mode == "tst_abs":
        return "%s #$%02X, $%04X" % (mn, a, c | (d << 8)), n
    if mode == "tst_zpx":
        return "%s #$%02X, $%02X,X" % (mn, a, c), n
    if mode == "tst_absx":
        return "%s #$%02X, $%04X,X" % (mn, a, c | (d << 8)), n
    if mode == "bbr":
        return "%s $%02X, $%04X" % (mn, a, (pc + 3 + ((c ^ 0x80) - 0x80)) & 0xFFFF), n
    return ".byte $%02X" % op, n


def disasm(code, start, count, base=0):
    pc = start
    out = []
    for _ in range(count):
        txt, n = disasm_one(code, pc)
        if txt is None:
            out.append("%04X: %-14s ???" % (base + pc, code[pc:pc + 1].hex()))
            pc += 1
            continue
        out.append("%04X: %-14s %s" % (base + pc, code[pc:pc + n].hex(), txt))
        pc += n
    return "\n".join(out)


def code_density(code, start, end, step=1):
    """Fraction of positions that decode as a known opcode."""
    total = 0
    good = 0
    pc = start
    while pc < end - 1:
        txt, n = disasm_one(code, pc)
        total += 1
        if txt is not None:
            good += 1
        pc += n
    return good / total if total else 0


def scan(path, window=512, top=25):
    code = open(path, "rb").read()
    print("%s (%d bytes)" % (os.path.basename(path), len(code)))
    scores = []
    for off in range(0, len(code) - window, window):
        d = code_density(code, off, off + window)
        scores.append((d, off))
    scores.sort(reverse=True)
    for d, off in scores[:top]:
        print("  @%06X density %.2f" % (off, d))


def dump(path, start, count, base=0):
    code = open(path, "rb").read()
    print(disasm(code, start, count, base))


if __name__ == "__main__":
    import sys
    if sys.argv[1] == "scan":
        for p in sys.argv[2:]:
            scan(p)
    elif sys.argv[1] == "dump":
        dump(sys.argv[2], int(sys.argv[3], 0), int(sys.argv[4], 0),
             int(sys.argv[5], 0) if len(sys.argv) > 5 else 0)
