#!/usr/bin/env python3
"""Inspect a Mega CD ISO: boot sector header, IP/SP, ISO files."""
import struct
import sys


def main():
    path = sys.argv[1]
    b = open(path, "rb").read()
    print("%s: %d bytes (%d sectors of 2048)" % (path, len(b), len(b) // 2048))
    print()
    print("--- boot sector (system area, sector 0) ---")
    print("disc type   : %r" % b[0:16])
    print("volume name : %r" % b[0x10:0x1C])
    print("system name : %r" % b[0x20:0x2C])
    ip_off, ip_size, ip_entry, ip_work, sp_off, sp_size, sp_entry, sp_work = \
        struct.unpack("<8I", b[0x30:0x50])
    print("IP  : off=$%X size=$%X entry=$%X work=$%X" % (ip_off, ip_size, ip_entry, ip_work))
    print("SP  : off=$%X size=$%X entry=$%X work=$%X" % (sp_off, sp_size, sp_entry, sp_work))
    print()
    print("--- disc header (0x100) ---")
    print("hardware    : %r" % b[0x100:0x110])
    print("copyright   : %r" % b[0x110:0x120])
    print("domestic    : %r" % b[0x120:0x150])
    print("overseas    : %r" % b[0x150:0x180])
    print("software id : %r" % b[0x180:0x190])
    print("region      : %r" % b[0x1F0:0x200])
    print()
    print("--- IP entry bytes (at $%X) ---" % (ip_off + 0x10))
    print(b[0x200:0x240].hex())
    print()
    # ISO9660 PVD at sector 16
    pvd_off = 16 * 2048
    if b[pvd_off:pvd_off + 1] == b"\x01":
        print("--- ISO9660 PVD ---")
        print("volume id   : %r" % b[pvd_off + 40:pvd_off + 72])
        print("block count : %d" % struct.unpack("<I", b[pvd_off + 80:pvd_off + 84])[0])
        print("block size  : %d" % struct.unpack("<H", b[pvd_off + 128:pvd_off + 130])[0])
    print()
    print("--- strings found in disc (file names) ---")
    for name in (b"IPX.MMD", b"GAME.MMD", b"SPX.SMD"):
        idx = b.find(name)
        print("  %-10s at %s" % (name.decode(), hex(idx) if idx >= 0 else "-"))


if __name__ == "__main__":
    main()
