#!/usr/bin/env python3
"""Find CD BIOS calls (JSR $E0xx) and dump the surrounding code to see the
arguments the game passes. This reveals the disc -> VRAM loading sequence."""
import re
import sys

BIOS = {
    0xE000: "cd_boot", 0xE003: "cd_reset", 0xE006: "cd_base",
    0xE009: "cd_read", 0xE00C: "cd_seek", 0xE00F: "cd_exec",
    0xE012: "cd_play", 0xE015: "cd_search", 0xE018: "cd_pause",
    0xE01B: "cd_stat", 0xE030: "ad_reset", 0xE033: "ad_trans",
    0xE036: "ad_read", 0xE039: "ad_write", 0xE03C: "ad_play",
    0xE042: "ad_stop", 0xE057: "bm_files", 0xE05A: "ex_getver",
    0xE05D: "ex_setvec", 0xE060: "ex_getfnt", 0xE063: "ex_joysns",
    0xE066: "ex_joyrep", 0xE069: "ex_scrsiz", 0xE06C: "ex_dotmod",
    0xE06F: "ex_scrmod", 0xE072: "ex_imode", 0xE075: "ex_vmode",
    0xE078: "ex_hmode", 0xE07B: "ex_vsync", 0xE07E: "ex_rcron",
    0xE081: "ex_rcroff", 0xE084: "ex_irqon", 0xE087: "ex_irqoff",
    0xE08A: "ex_bgon", 0xE08D: "ex_bgoff", 0xE090: "ex_spron",
    0xE093: "ex_sproff", 0xE096: "ex_dspon", 0xE099: "ex_dspoff",
    0xE09C: "ex_dmamod", 0xE09F: "ex_sprdma", 0xE0A2: "ex_satclr",
    0xE0A5: "ex_sprput", 0xE0A8: "ex_setrcr", 0xE0AB: "ex_setred",
    0xE0AE: "ex_setwrt", 0xE0B1: "ex_setdma", 0xE0B4: "ex_binbcd",
    0xE0B7: "ex_bcdbin", 0xE0BA: "ex_rnd", 0xE0D8: "psg_bios",
    0xE0DB: "grp_bios", 0xE0DE: "key_bios", 0xE0E1: "psg_driver",
    0xE0E4: "ex_colorcmd",
}

PATTERN = None


def main():
    path = sys.argv[1]
    start = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x4000
    end = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x6000
    b = open(path, "rb").read()
    hits = []
    for off in range(start, min(end, len(b)) - 2):
        if b[off] == 0x20:
            addr = b[off + 1] | (b[off + 2] << 8)
            if addr in BIOS:
                hits.append((off, addr, BIOS[addr]))
    print("%s $%X-$%X: %d CD BIOS calls" % (path, start, end, len(hits)))
    for off, addr, name in hits:
        print("  $%04X  JSR $%04X  %s" % (off, addr, name))


if __name__ == "__main__":
    main()
