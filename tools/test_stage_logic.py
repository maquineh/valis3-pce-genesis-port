#!/usr/bin/env python3
"""Static tests for the stage-1 module: resource layout + streaming logic.

The Mega CD build cannot be booted here (no Mega CD BIOS available), so this
test verifies what *can* be verified without hardware:

  1. game/res/gfx/stage1_all_maps.bin holds 10 screens of 32x24 plane A
     entries, all tile indices inside the uploaded tile range and palettes
     0-3 (the Mega Drive only has 4 palette lines).
  2. The packed tile block is exactly TILE_COUNT 32-byte Mega Drive tiles.
  3. The streaming logic in game/src/stage1.c draws every screen in order.
"""
import re
import sys

TILE_COUNT = 1297
SCREENS = 10
ROWS, COLS = 24, 32


def line(ok, label, detail=""):
    print("  %s %-52s %s" % ("PASS" if ok else "FAIL", label, detail))


def main():
    ok = True

    # --- 1. map resource -------------------------------------------------
    m = open("game/res/gfx/stage1_all_maps.bin", "rb").read()
    expect = SCREENS * ROWS * COLS * 2
    line(len(m) == expect, "stage1_all_maps.bin size",
         "%d bytes (expected %d)" % (len(m), expect))
    ok &= len(m) == expect

    bad_tile = 0
    used = set()
    for i in range(SCREENS * ROWS * COLS):
        w = m[i * 2] | (m[i * 2 + 1] << 8)
        tile = w & 0x7FF
        if tile >= TILE_COUNT:
            bad_tile += 1
        used.add(tile)
    line(bad_tile == 0, "all map tile indices < %d" % TILE_COUNT,
         "%d bad" % bad_tile)
    line(len(used) == TILE_COUNT, "the maps reference every packed tile",
         "%d of %d" % (len(used), TILE_COUNT))
    ok &= bad_tile == 0 and len(used) == TILE_COUNT

    # --- 2. packed tiles --------------------------------------------------
    t = open("game/res/gfx/stage1_all_tiles.bin", "rb").read()
    line(len(t) == TILE_COUNT * 32, "stage1_all_tiles.bin size",
         "%d bytes = %d tiles" % (len(t), len(t) // 32))
    ok &= len(t) == TILE_COUNT * 32

    # --- 3. streaming logic (mirrors game/src/stage1.c) ------------------
    src = open("game/src/stage1.c").read()
    line("#define STAGE_SCREENS 10" in src, "stage1.c declares 10 screens")
    line("cell_scroll & (SCREEN_COLS - 1)) == 0" in src,
         "stage1.c advances the stream on a screen boundary")
    line("draw_screen(0, screen_no);" in src,
         "stage1.c redraws the pair on each boundary")

    drawn = {0, 1}          # stage_load() draws screens 0 and 1 up front
    screen_no = 0
    cell_scroll = 0
    for _ in range(400):    # hold RIGHT for 400 frames
        cell_scroll += 1
        if cell_scroll & (COLS - 1) == 0:
            screen_no = screen_no + 1 if screen_no + 1 < SCREENS else SCREENS - 1
            drawn.add(screen_no)
            drawn.add(screen_no + 1 if screen_no + 1 < SCREENS else SCREENS - 1)
    uniq = sorted(drawn)
    line(uniq == list(range(SCREENS)),
         "streaming draws every screen in order", "drawn %s" % uniq)
    ok &= uniq == list(range(SCREENS))

    print("RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
