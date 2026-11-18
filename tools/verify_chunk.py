#!/usr/bin/env python3
"""Print the stage-chunk entry using the raw track's de-striped CD payload."""
import sys

from disasm6280 import disasm_one
from logical_to_file import (
    TRACK,
    file_offset,
    load_user_bytes,
)

SECTOR = 1000
SECTOR_COUNT = 4
LOGICAL_BASE = 0x8000
ENTRY = 0x8004
ENTRY_BYTES = 0x200
EXPECTED_HEADER = bytes((0x01, 0x03, 0x15, 0x01))


def main():
    payload = load_user_bytes(TRACK, SECTOR, SECTOR_COUNT)
    if payload[:len(EXPECTED_HEADER)] != EXPECTED_HEADER:
        raise SystemExit(
            "unexpected sector %d chunk header: %s"
            % (SECTOR, payload[:4].hex(" "))
        )

    print("sector %d, %d sectors -> logical $%04X, header %s"
          % (SECTOR, SECTOR_COUNT, LOGICAL_BASE,
             payload[:4].hex(" ").upper()))
    pc = ENTRY
    stop = min(ENTRY + ENTRY_BYTES, LOGICAL_BASE + len(payload))
    while pc < stop:
        offset = pc - LOGICAL_BASE
        text, size = disasm_one(payload, offset, pc)
        if text is None:
            text = ".byte $%02X" % payload[offset]
            size = 1
        raw = file_offset(pc, SECTOR, SECTOR_COUNT, LOGICAL_BASE)
        print("file $%06X (logical $%04X): %s" % (raw, pc, text))
        pc += size


if __name__ == "__main__":
    sys.path.insert(0, "tools")
    main()
