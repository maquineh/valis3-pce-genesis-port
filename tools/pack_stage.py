#!/usr/bin/env python3
"""Pack a PC Engine stage screen into Mega Drive resources.

The PC Engine screen map references VRAM tile indices relative to the tile
block that the loader read from the disc; the Mega Drive only has 64 KiB of
VRAM (2048 tiles), so we keep only the tiles the map actually uses and remap
the map accordingly. A palette is picked up from a given VCE colour block.

Usage:
  python3 tools/pack_stage.py <track> <map_off> <tile_off> <tile_base> \
      <pal_off> <name>

Outputs game/res/gfx/<name>_{tiles,map,pal}.bin
"""
import sys

sys.path.insert(0, "tools")
from pce2md import pce_tile_to_md, pce_color_to_md  # noqa: E402


def main():
    track = sys.argv[1]
    map_off = int(sys.argv[2], 0)
    tile_off = int(sys.argv[3], 0)
    tile_base = int(sys.argv[4], 0)
    pal_off = int(sys.argv[5], 0)
    name = sys.argv[6]
    b = open(track, "rb").read()

    words = [b[map_off + i * 2] | (b[map_off + i * 2 + 1] << 8) for i in range(896)]
    tiles = [w & 0xFFF for w in words]

    # collect the distinct tiles, index 0 reserved for the blank tile
    order = [0]                      # new index 0 == blank
    remap = {0: 0}
    for t in set(tiles):
        if t == 0 and tile_base != 0:
            continue
        order.append(t)
        remap[t] = len(order) - 1

    # blank tile: an all-top-plane tile renders as colour 0 of the palette
    blank = bytes(32)

    out_tiles = bytearray(blank)
    for t in order[1:]:
        src = tile_off + (t - tile_base) * 32
        if src < 0 or src + 32 > len(b):
            print("WARNING: tile %03X missing (src %X)" % (t, src))
            out_tiles += blank
            continue
        out_tiles += pce_tile_to_md(b[src:src + 32])

    open("game/res/gfx/%s_tiles.bin" % name, "wb").write(bytes(out_tiles))

    out_map = bytearray()
    for w in words:
        pal = w >> 12
        t = w & 0xFFF
        entry = (remap.get(t, 0) & 0x7FF) | ((pal & 3) << 13)
        out_map += bytes([entry & 0xFF, (entry >> 8) & 0xFF])
    open("game/res/gfx/%s_map.bin" % name, "wb").write(bytes(out_map))

    out_pal = bytearray()
    for i in range(64):
        w = b[pal_off + i * 2] | (b[pal_off + i * 2 + 1] << 8)
        m = pce_color_to_md(w)
        out_pal += bytes([m & 0xFF, (m >> 8) & 0xFF])
    open("game/res/gfx/%s_pal.bin" % name, "wb").write(bytes(out_pal))

    print("%s: %d tiles packed (%d bytes), map %d bytes, palette %d bytes"
          % (name, len(order), len(out_tiles), len(out_map), len(out_pal)))


if __name__ == "__main__":
    main()
