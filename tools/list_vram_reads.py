#!/usr/bin/env python3
"""List every cd_read that targets VRAM with its sector/dest/size (bytes).

VRAM reads use dh=$FE/$FF, the destination is a VRAM word address (bh:bl) and
the size is the 16-bit value ah:al in bytes.
"""
import sys

BIOS = {0xE009: "cd_read", 0xE00F: "cd_exec", 0xE012: "cd_play"}


def main():
    path = sys.argv[1]
    b = open(path, "rb").read()
    for off in range(0, len(b) - 3):
        if b[off] != 0x20:
            continue
        addr = b[off + 1] | (b[off + 2] << 8)
        if addr not in BIOS:
            continue
        # scan backwards for the immediate zp stores of the work area
        params = {}
        i = off - 1
        while i > off - 40:
            op = b[i]
            if op == 0x85 and b[i + 1] in range(0xF8, 0x100) and b[i - 2] == 0xA9:
                params.setdefault(b[i + 1], b[i - 1])
                i -= 3
                continue
            if op == 0x64 and b[i + 1] in range(0xF8, 0x100):
                params.setdefault(b[i + 1], 0)
                i -= 2
                continue
            i -= 1
        if params.get(0xFF) not in (0xFE, 0xFF):
            continue
        sector = (params.get(0xFC, 0) << 16) | (params.get(0xFD, 0) << 8) | params.get(0xFE, 0)
        dest = (params.get(0xFB, 0) << 8) | params.get(0xFA, 0)
        size = (params.get(0xF9, 0) << 8) | params.get(0xF8, 0)
        file_off = sector * 2352
        print("$%06X  %-8s sector $%06X (%d)  VRAM word $%04X (= tile %d)  size $%X (%d bytes)"
              % (off, BIOS[addr], sector, sector, dest, dest // 16, size, size)
              + ("   trackfile 0x%06X" % file_off if size else ""))


if __name__ == "__main__":
    main()
