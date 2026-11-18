#!/usr/bin/env python3
"""Map HuC6280 addresses into a raw MODE1/2352 track read.

CD reads copy 2048 user bytes per sector, while the extracted track contains
2352-byte sectors.  This tool strips the 16-byte header from each sector in a
specified read before disassembling, so addresses crossing sector boundaries
remain aligned.

By default it uses the verified System Card overlay read: sector 32, 8 sectors
loaded at logical $4000.  Supply `--range SECTOR COUNT LOGICAL_BASE` for another
known `cd_exec`/`cd_read` mapping, for example the stage chunk at sector 1000,
4 sectors, logical $8000.

Usage:
    py -3 tools/logical_to_file.py '$4CA0'
    py -3 tools/logical_to_file.py --range 1000 4 0x8000 --disasm '$9366' 48
"""
import sys

TRACK = "build/extracted/data/track_02.bin"
SECTOR_BYTES = 2352
USER_BYTES = 2048
DEFAULT_SECTOR = 32
DEFAULT_COUNT = 8
DEFAULT_LOGICAL = 0x4000


def number(value, default_base=0):
    value = value.strip()
    if value.startswith("$"):
        return int(value[1:], 16)
    if default_base == 16 and not value.lower().startswith("0x"):
        return int(value, 16)
    return int(value, 0)


def file_offset(logical, sector, count, logical_base):
    delta = logical - logical_base
    if delta < 0 or delta >= count * USER_BYTES:
        raise ValueError("logical address is outside the selected CD read")
    page, within = divmod(delta, USER_BYTES)
    return (sector + page) * SECTOR_BYTES + 16 + within


def load_user_bytes(track, sector, count):
    data = bytearray()
    with open(track, "rb") as f:
        for s in range(sector, sector + count):
            f.seek(s * SECTOR_BYTES + 16)
            chunk = f.read(USER_BYTES)
            if len(chunk) != USER_BYTES:
                raise ValueError("short CD sector %d" % s)
            data.extend(chunk)
    return bytes(data)


def main():
    from disasm6280 import disasm_one

    args = sys.argv[1:]
    sector, count, logical_base = DEFAULT_SECTOR, DEFAULT_COUNT, DEFAULT_LOGICAL
    disasm = False
    disasm_count = 24
    parsed = []
    i = 0
    while i < len(args):
        if args[i] == "--range":
            if i + 3 >= len(args):
                raise SystemExit("--range needs SECTOR COUNT LOGICAL_BASE")
            sector = number(args[i + 1])
            count = number(args[i + 2])
            logical_base = number(args[i + 3])
            i += 4
        elif args[i] == "--disasm":
            disasm = True
            if i + 2 < len(args) and not args[i + 2].startswith("--"):
                disasm_count = number(args[i + 2])
                parsed.append(args[i + 1])
                i += 3
            elif i + 1 < len(args):
                parsed.append(args[i + 1])
                i += 2
            else:
                raise SystemExit("--disasm needs an ADDRESS")
        else:
            parsed.append(args[i])
            i += 1

    if not parsed:
        print(__doc__)
        return

    payload = load_user_bytes(TRACK, sector, count)
    for arg in parsed:
        logical = number(arg, default_base=16)
        try:
            f = file_offset(logical, sector, count, logical_base)
        except ValueError as e:
            raise SystemExit("logical $%04X: %s" % (logical, e))
        print("logical $%04X -> file $%06X (sector %d payload +$%03X)"
              % (logical, f, (f - 16) // SECTOR_BYTES,
                 (f - 16) % SECTOR_BYTES))
        if disasm:
            pc = logical - logical_base
            for _ in range(disasm_count):
                txt, n = disasm_one(payload, pc, logical)
                f = file_offset(logical, sector, count, logical_base)
                print("   file $%06X (logical $%04X): %s" % (f, logical, txt or ".byte $%02X" % payload[pc]))
                pc += n
                logical += n
                if pc >= len(payload):
                    break


if __name__ == "__main__":
    sys.path.insert(0, "tools")
    main()
