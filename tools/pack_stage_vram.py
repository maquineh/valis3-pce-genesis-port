#!/usr/bin/env python3
"""Pack a stage the way the original loads it: tile block at its VRAM slot.

The PC Engine loads each stage's tile block to a fixed VRAM tile range, so a
screen's map tile index t refers to VRAM tile t. This packer keeps those
indices (no remap) and clamps out-of-range tiles to the blank tile, which
keeps the Mega Drive VRAM budget at one 48 KiB block (1536 tiles).

Usage: pack_stage_vram.py <track> <first_map> <screens> <tile_off> <pal_off> \
       <name> <vram_tile_base> <block_tiles>
"""
import struct
import sys

GRID = 0x600
ROWS, COLS = 24, 32


def main():
    track = sys.argv[1]
    first = int(sys.argv[2], 0)
    n = int(sys.argv[3], 0)
    tile_off = int(sys.argv[4], 0)
    pal_off = int(sys.argv[5], 0)
    name = sys.argv[6]
    base = int(sys.argv[7], 0)      # VRAM tile slot of the block
    ntiles = int(sys.argv[8], 0)    # tiles in the block
    b = open(track, "rb").read()

    # the raw block as Mega Drive tiles (tile slot base .. base+ntiles)
    tiles = bytearray()
    for k in range(ntiles):
        src = tile_off + k * 32
        if src + 32 > len(b):
            tiles += bytes(32)
        else:
            tiles += md_tile(b[src:src + 32])
    open("game/res/gfx/%s_tiles.bin" % name, "wb").write(bytes(tiles))

    maps = bytearray()
    out_range = 0
    for s in range(n):
        off = first + s * GRID
        for i in range(ROWS * COLS):
            w = b[off + i * 2] | (b[off + i * 2 + 1] << 8)
            t = w & 0xFFF
            pal = w >> 12
            if not (base <= t < base + ntiles):
                t = 0
                out_range += 1
            entry = (t & 0x7FF) | ((pal & 3) << 13)
            maps += bytes([entry & 0xFF, (entry >> 8) & 0xFF])
    open("game/res/gfx/%s_maps.bin" % name, "wb").write(bytes(maps))

    out_pal = bytearray()
    for i in range(64):
        w = b[pal_off + i * 2] | (b[pal_off + i * 2 + 1] << 8)
        bl = w & 7
        r = (w >> 3) & 7
        g = (w >> 6) & 7
        m = (r << 1) | (g << 5) | (bl << 9)
        out_pal += bytes([m & 0xFF, (m >> 8) & 0xFF])
    open("game/res/gfx/%s_pal.bin" % name, "wb").write(bytes(out_pal))

    print("%s: %d screens, block %d tiles (%d bytes) at MD tile %d, maps %d bytes, %d out-of-range cells clamped"
          % (name, n, ntiles, len(tiles), base, len(maps), out_range))


def md_tile(t32):
    out = bytearray(32)
    for r in range(8):
        out[r * 4 + 0] = t32[r * 2]
        out[r * 4 + 1] = t32[r * 2 + 1]
        out[r * 4 + 2] = t32[16 + r * 2]
        out[r * 4 + 3] = t32[16 + r * 2 + 1]
    return bytes(out)


if __name__ == "__main__":
    main()
