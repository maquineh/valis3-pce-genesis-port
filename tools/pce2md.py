#!/usr/bin/env python3
"""Convert PC Engine graphics data into Sega Genesis / Mega Drive resources.

PCE BG tile (8x8, 4bpp, 32 B):
    p0=byte[2r], p1=byte[2r+1], p2=byte[16+2r], p3=byte[16+2r+1]
Mega Drive tile (8x8, 4bpp, 32 B):
    row r: byte[4r]=p0, byte[4r+1]=p1, byte[4r+2]=p2, byte[4r+3]=p3

PCE VCE colour word: B | (R<<3) | (G<<6)          (B,R,G are 3-bit)
Mega Drive CRAM word: (R<<1) | (G<<5) | (B<<9)    (same bit order per channel)

PCE BAT entry: (palette<<12) | tile_index
Mega Drive plane A entry: tile | (hflip<<11) | (vflip<<12) | (pal<<13) | (pri<<15)
Tile indices are rebased when uploading (uploaded tile #k gets MD index k).
"""
import sys


def pce_tile_to_md(t32):
    out = bytearray(32)
    for r in range(8):
        out[r * 4 + 0] = t32[r * 2]
        out[r * 4 + 1] = t32[r * 2 + 1]
        out[r * 4 + 2] = t32[16 + r * 2]
        out[r * 4 + 3] = t32[16 + r * 2 + 1]
    return bytes(out)


def pce_color_to_md(w):
    b = w & 7
    r = (w >> 3) & 7
    g = (w >> 6) & 7
    return (r << 1) | (g << 5) | (b << 9)


def cmd_tiles(src, off, count, out, tile_base=0, pal_off=None, pal_count=16):
    data = open(src, "rb").read()
    res = bytearray()
    for i in range(count):
        base = off + i * 32
        if base + 32 > len(data):
            break
        res += pce_tile_to_md(data[base:base + 32])
    open(out, "wb").write(res)
    print("%s: %d tiles (%d bytes) [PCE %s +$%X -> MD green order]"
          % (out, count, len(res), src, off))


def cmd_pal(src, off, count, out):
    data = open(src, "rb").read()
    res = bytearray()
    for i in range(count):
        w = data[off + i * 2] | (data[off + i * 2 + 1] << 8)
        m = pce_color_to_md(w)
        res += bytes([m & 0xFF, (m >> 8) & 0xFF])
    open(out, "wb").write(res)
    print("%s: %d colours" % (out, count))


def cmd_bat(src, off, w, h, out, tile_base=256, tile_offset=0, pal_shift=True):
    """Convert a PCE BAT into a Mega Drive plane A nametable.

    tile_base  = PCE tile index of the first uploaded tile (VRAM tile base)
    tile_offset= MD tile index of that same tile after upload
    """
    data = open(src, "rb").read()
    res = bytearray()
    for i in range(w * h):
        lo, hi = data[off + i * 2], data[off + i * 2 + 1]
        word = lo | (hi << 8)
        pal = word >> 12
        tile = (word & 0xFFF) - tile_base + tile_offset
        mdpal = pal & 3  # Mega Drive has 4 palette lines
        entry = (tile & 0x7FF) | (mdpal << 13)
        res += bytes([entry & 0xFF, (entry >> 8) & 0xFF])
    open(out, "wb").write(res)
    print("%s: %dx%d plane entries (%d bytes)" % (out, w, h, len(res)))


def cmd_ramp(out, ramp_type="gray"):
    """Emit a 4-line x 16-colour CRAM ramp (placeholder palette)."""
    res = bytearray()
    for line in range(4):
        for i in range(16):
            if ramp_type == "gray":
                v = int(round(i * 14 / 15))
                m = (v << 1) | (v << 5) | (v << 9)
            else:
                m = (i << 1)
            res += bytes([m & 0xFF, (m >> 8) & 0xFF])
    open(out, "wb").write(res)
    print("%s: 64-colour ramp written" % out)


def main():
    cmd = sys.argv[1]
    if cmd == "tiles":
        off = int(sys.argv[3], 0)
        count = int(sys.argv[4], 0)
        cmd_tiles(sys.argv[2], off, count, sys.argv[5])
    elif cmd == "pal":
        cmd_pal(sys.argv[2], int(sys.argv[3], 0), int(sys.argv[4], 0), sys.argv[5])
    elif cmd == "bat":
        cmd_bat(sys.argv[2], int(sys.argv[3], 0), int(sys.argv[4], 0),
                int(sys.argv[5], 0), sys.argv[6],
                tile_base=int(sys.argv[7], 0) if len(sys.argv) > 7 else 256)
    elif cmd == "ramp":
        cmd_ramp(sys.argv[2])


if __name__ == "__main__":
    main()
