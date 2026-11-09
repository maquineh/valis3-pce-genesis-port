#!/usr/bin/env python3
"""Decode CD BIOS call sites: recover the cd_read/cd_exec parameters.

The game stores CD BIOS parameters in the zero page mirror of the BIOS work
area ($F8=al $F9=ah $FA=bl $FB=bh $FC=cl $FD=ch $FE=dl $FF=dh) using
LDA #imm / STA $F8.. sequences placed right before the JSR.

cd_read:  cl:ch:dl = sector number (relative to the code track)
          dh       = destination type ($01 local RAM, $02-$06 MPR, $FE/$FF VRAM)
          bl:bh    = destination address (VRAM word address for $FE/$FF)
          al       = number of sectors
cd_exec:  same, then jumps to bl:bh

We map sector numbers to file offsets in the data track they belong to.
"""
import re
import sys

ZP = {0xF8: "al", 0xF9: "ah", 0xFA: "bl", 0xFB: "bh",
      0xFC: "cl", 0xFD: "ch", 0xFE: "dl", 0xFF: "dh"}

BIOS = {0xE009: "cd_read", 0xE00F: "cd_exec", 0xE012: "cd_play",
        0xE015: "cd_search", 0xE006: "cd_base"}


def decode_params(b, site):
    """Scan backwards from the JSR for immediate zp stores."""
    params = {}
    i = site - 1
    while i >= 0 and i > site - 48:
        op = b[i]
        if op == 0x85 and b[i + 1] in ZP:          # STA zp  (A already loaded)
            imm = None
            if b[i - 2] == 0xA9:
                imm = b[i - 1]
            if imm is not None and ZP[b[i + 1]] not in params:
                params[ZP[b[i + 1]]] = imm
                i -= 3
                continue
        if op == 0x64 and b[i + 1] in ZP:          # STZ zp
            params.setdefault(ZP[b[i + 1]], 0)
            i -= 2
            continue
        i -= 1
    return params


def main():
    path = sys.argv[1]
    track_first_frame = int(sys.argv[2], 0)   # absolute frame of track index01
    track_len = int(sys.argv[3], 0)           # bytes
    b = open(path, "rb").read()
    print("call sites with decodable parameters:")
    for off in range(0, len(b) - 3):
        if b[off] != 0x20:
            continue
        addr = b[off + 1] | (b[off + 2] << 8)
        if addr not in BIOS:
            continue
        name = BIOS[addr]
        p = decode_params(b, off)
        if len(p) < 5:
            print("  %06X %-9s (partial %s)" % (off, name, p))
            continue
        cl = p.get("cl", 0)
        ch = p.get("ch", 0)
        dl = p.get("dl", 0)
        dh = p.get("dh", 0)
        bl = p.get("bl", 0)
        bh = p.get("bh", 0)
        al = p.get("al", 0)
        sector = (cl << 16) | (ch << 8) | dl
        dest = (bh << 8) | bl
        size = al
        file_off = sector * 2048
        note = ""
        if dh in (0xFE, 0xFF):
            note = "-> VRAM word $%04X" % dest
        elif dh == 1:
            note = "-> RAM $%04X" % dest
        elif 2 <= dh <= 6:
            note = "-> MPR%d bank %d" % (dh - 1, dest)
        fr = track_first_frame + sector
        print("  %06X %-9s sector $%06X (%d) %d sectors %s  fileoff=$%X"
              % (off, name, sector, sector, size, note, fr * 2352 - 0 + 0))


if __name__ == "__main__":
    main()
