#!/usr/bin/env python3
"""Generate simple placeholder sprite tiles (player, heart and test enemy).

Emits a 16x16 player, one 8x8 heart and a distinct 16x16 flying-disc enemy,
all using indices 8, 9, and 15 on shared palette line 3 (index 0 is
transparent). They are engine test art, not original game sprites.
"""
import os

OUT = "game/res/gfx/player_spr.bin"


def md_tile(rows):
    """rows: 8 lists of 8 colour indices -> 32 bytes of MD tile data."""
    return bytes((row[x] << 4) | row[x + 1]
                 for row in rows for x in range(0, 8, 2))


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
    palette_indices = (0, 8, 9, 15)
    return md_tile([[palette_indices[pixel] for pixel in row] for row in rows])


def heart_tile():
    """One high-contrast 8x8 heart using only the reserved sprite colors."""
    rows = [
        [0, 0, 8, 8, 0, 8, 8, 0],
        [0, 8, 9, 9, 8, 9, 9, 8],
        [8, 9, 9, 15, 9, 9, 9, 8],
        [8, 9, 9, 9, 9, 9, 9, 8],
        [0, 8, 9, 9, 9, 9, 8, 0],
        [0, 0, 8, 9, 9, 8, 0, 0],
        [0, 0, 0, 8, 8, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ]
    return md_tile(rows)


def enemy_tiles():
    """Four tiles for a compact flying disc, inspired by Genesis captures."""
    pixels = [[0] * 16 for _ in range(16)]
    for y in range(2, 14):
        dy = abs(y - 7.5)
        half = int(7 * (1.0 - (dy / 6.0) ** 2) ** 0.5)
        for x in range(8 - half, 9 + half):
            if x == 8 - half or x == 8 + half or y in (2, 13):
                pixels[y][x] = 15
            elif y < 6 and 6 <= x <= 9:
                pixels[y][x] = 8
            else:
                pixels[y][x] = 9
    # Fins and eyes distinguish the silhouette from the player sprite.
    for y in (7, 8):
        pixels[y][1] = pixels[y][2] = pixels[y][13] = pixels[y][14] = 8
    pixels[7][6] = pixels[7][9] = 15
    pixels[10][7] = pixels[10][8] = 8
    return b''.join(md_tile(pixels[y:y + 8][r][x:x + 8]
                            for r in range(8))
                    for y, x in ((0, 0), (8, 0), (0, 8), (8, 8)))


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = (b"".join(player_tile(k) for k in (0, 2, 1, 3)) +
            heart_tile() + enemy_tiles())
    open(OUT, "wb").write(data)
    print("%s: %d bytes (4 player + 1 heart + 4 enemy tiles)" % (OUT, len(data)))


if __name__ == "__main__":
    main()
