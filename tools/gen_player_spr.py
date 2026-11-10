#!/usr/bin/env python3
"""Generate simple placeholder sprite tiles (player + a test enemy).

Emits Mega Drive 4bpp tiles: a 16x16 player figure in 2x2 tiles and a 16x16
coin, written to game/res/gfx/player_spr.bin. The real character sprites are
still being decoded (docs/findings.md "Open items"), so this is engine test
art, not final art.
"""
import os

OUT = "game/res/gfx/player_spr.bin"


def md_tile(rows):
    """rows: 8 lists of 8 colour indices -> 32 bytes of MD tile data."""
    out = bytearray(32)
    for r in range(8):
        p = [0, 0, 0, 0]
        for x in range(8):
            v = rows[r][x] & 0xF
            bit = 0x80 >> x
            for plane in range(4):
                if v & (1 << plane):
                    p[plane] |= bit
        out[r * 4 + 0] = p[0]
        out[r * 4 + 1] = p[1]
        out[r * 4 + 2] = p[2]
        out[r * 4 + 3] = p[3]
    return bytes(out)


def blank():
    return md_tile([[0] * 8 for _ in range(8)])


def player_tile(kind):
    """kind 0=top-left 1=top-right 2=bottom-left 3=bottom-right."""
    rows = [[0] * 8 for _ in range(8)]
    if kind == 0:      # head
        rows[0] = [0, 1, 1, 1, 1, 1, 0, 0]
        rows[1] = [0, 1, 2, 2, 2, 1, 0, 0]
        rows[2] = [0, 1, 2, 2, 2, 1, 0, 0]
        rows[3] = [0, 1, 1, 1, 1, 1, 0, 0]
        rows[4] = [0, 0, 1, 1, 1, 1, 0, 0]
    elif kind == 1:
        rows[0] = [0, 0, 0, 0, 0, 0, 0, 0]
        rows[0] = [0, 0, 0, 0, 0, 0, 0, 0]
        rows[3] = [0, 0, 1, 1, 1, 1, 0, 0]
        rows[4] = [0, 0, 1, 1, 1, 1, 0, 0]
        # hair back
        rows[1] = [0, 0, 1, 1, 1, 1, 0, 0]
        rows[2] = [0, 0, 1, 1, 1, 1, 0, 0]
    elif kind == 2:    # body / dress
        rows[0] = [0, 0, 1, 1, 1, 1, 0, 0]
        rows[1] = [0, 1, 1, 1, 1, 1, 1, 0]
        rows[2] = [0, 1, 2, 1, 1, 2, 1, 0]
        rows[3] = [0, 1, 2, 1, 1, 2, 1, 0]
        rows[4] = [0, 1, 1, 1, 1, 1, 1, 0]
        rows[5] = [0, 0, 1, 2, 2, 1, 0, 0]
        rows[6] = [0, 0, 1, 2, 2, 1, 0, 0]
        rows[7] = [0, 0, 0, 2, 2, 0, 0, 0]
    else:              # kind == 3, feet / sword
        rows[0] = [0, 0, 0, 0, 0, 0, 0, 3]
        rows[1] = [0, 0, 0, 0, 0, 0, 0, 3]
        rows[2] = [0, 0, 0, 0, 0, 0, 0, 3]
        rows[3] = [0, 0, 0, 0, 0, 0, 0, 3]
        rows[4] = [0, 0, 0, 0, 0, 0, 0, 3]
        rows[5] = [0, 1, 0, 0, 0, 0, 0, 3]
        rows[6] = [0, 0, 1, 0, 0, 0, 0, 3]
        rows[7] = [0, 0, 0, 0, 1, 0, 0, 0]
    return md_tile(rows)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = b"".join(player_tile(k) for k in range(4))
    open(OUT, "wb").write(data)
    print("%s: %d bytes (4 tiles: 16x16 player figure)" % (OUT, len(data)))


if __name__ == "__main__":
    main()
