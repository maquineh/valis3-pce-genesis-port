#!/usr/bin/env python3
"""Extract a whole stage: all its screens (0x600 grid) into one packed set.

Usage:
  python3 tools/pack_stage_all.py <track> <first_map> <screens> <tile_off> \
      <pal_off> <name>

Outputs game/res/gfx/<name>_{tiles,map,pal,mapindex}.bin where mapindex.json
lists the screen offsets so the game can stream them in.
"""
import json
import sys

sys.path.insert(0, "tools")
from pce2md import pce_tile_to_md, pce_color_to_md  # noqa: E402

GRID = 0x600
ROWS, COLS = 24, 32


def main():
    track = sys.argv[1]
    first = int(sys.argv[2], 0)
    n = int(sys.argv[3], 0)
    tile_off = int(sys.argv[4], 0)
    pal_off = int(sys.argv[5], 0)
    name = sys.argv[6]
    b = open(track, "rb").read()

    order = [0]              # index 0 = blank
    remap = {0: 0}
    entries = []
    for s in range(n):
        off = first + s * GRID
        w = [b[off + i * 2] | (b[off + i * 2 + 1] << 8) for i in range(ROWS * COLS)]
        row = []
        for word in w:
            t = word & 0xFFF
            if t not in remap:
                order.append(t)
                remap[t] = len(order) - 1
            row.append(remap[t])
        entries.append(row)

    out_tiles = bytearray(bytes(32))       # blank tile at index 0
    for t in order[1:]:
        src = tile_off + (t - 0x200) * 32
        if src < 0 or src + 32 > len(b):
            print("WARNING: tile %03X missing" % t)
            out_tiles += bytes(32)
        else:
            out_tiles += pce_tile_to_md(b[src:src + 32])
    open("game/res/gfx/%s_tiles.bin" % name, "wb").write(bytes(out_tiles))

    # one plane-A sized map per screen (32x24 cells), palettes preserved
    maps = bytearray()
    pal_use = []
    for s in range(n):
        off = first + s * GRID
        w = [b[off + i * 2] | (b[off + i * 2 + 1] << 8) for i in range(ROWS * COLS)]
        pal_use.append([])
        for word in w:
            t = word & 0xFFF
            pal = word >> 12
            pal_use[s].append(pal)
            entry = (remap.get(t, 0) & 0x7FF) | ((pal & 3) << 13)
            maps += bytes([entry & 0xFF, (entry >> 8) & 0xFF])
    open("game/res/gfx/%s_maps.bin" % name, "wb").write(bytes(maps))

    out_pal = bytearray()
    for i in range(64):
        w = b[pal_off + i * 2] | (b[pal_off + i * 2 + 1] << 8)
        m = pce_color_to_md(w)
        out_pal += bytes([m & 0xFF, (m >> 8) & 0xFF])
    open("game/res/gfx/%s_pal.bin" % name, "wb").write(bytes(out_pal))

    json.dump({"screens": n, "first_map": hex(first), "tiles": len(order)},
              open("game/res/gfx/%s.json" % name, "w"), indent=2)

    print("%s: %d screens, %d tiles (%d bytes), maps %d bytes"
          % (name, n, len(order), len(out_tiles), len(maps)))


if __name__ == "__main__":
    main()
