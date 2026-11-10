#!/usr/bin/env python3
"""PC Engine graphics tooling: tile/sprite renderers + palette helpers.

BG tile (8x8, 4bpp, 32 bytes):
  bytes[0..15]  : planes 0&1 interleaved per row -> [2r]=p0, [2r+1]=p1
  bytes[16..31] : planes 2&3                      -> [16+2r]=p2, [16+2r+1]=p3
  pixel index = p0 | p1<<1 | p2<<2 | p3<<3

Sprite (16x16, 4bpp, 128 bytes):
  plane p (0..3) occupies bytes [p*32 .. p*32+31], row r at +2r/+2r+1,
  big-endian words: first byte of the pair is the HIGH byte (pixels 8..15).

VCE colour word (little endian): value = B | (R<<3) | (G<<6)
"""
import os
import sys

from PIL import Image

GRAY = [(int(255 * i / 15),) * 3 for i in range(16)]


def bg_tile_pixels(t32):
    """32 bytes -> 8 rows x 8 indices."""
    rows = []
    for r in range(8):
        row = []
        p0 = t32[r * 2]
        p1 = t32[r * 2 + 1]
        p2 = t32[16 + r * 2]
        p3 = t32[16 + r * 2 + 1]
        for x in range(8):
            bit = 0x80 >> x
            v = 0
            if p0 & bit:
                v |= 1
            if p1 & bit:
                v |= 2
            if p2 & bit:
                v |= 4
            if p3 & bit:
                v |= 8
            row.append(v)
        rows.append(row)
    return rows


def sprite16_pixels(s128):
    """128 bytes -> 16 rows x 16 indices."""
    rows = []
    for r in range(16):
        row = []
        for p in range(4):
            hi = s128[p * 32 + r * 2]
            lo = s128[p * 32 + r * 2 + 1]
            for x in range(8):
                b = 0x80 >> x
                v = 0
                if hi & b:
                    v |= 1
                if lo & b:
                    v |= 2
                row.append((p, v))
        # row currently has 32 (p,v) pairs; combine planes 0..3
        out = []
        for x in range(16):
            v = 0
            for p in range(4):
                bit, val = row[p * 8 + x] if False else (None, None)
            # recompute cleanly below
            out.append(None)
        # clean recompute
        pixels = []
        for x in range(16):
            v = 0
            for p in range(4):
                hi = s128[p * 32 + r * 2]
                lo = s128[p * 32 + r * 2 + 1]
                if x < 8:
                    b = 0x80 >> x
                    if hi & b:
                        v |= (1 << (2 * p + 1)) if False else (1 << p)
                else:
                    b = 0x80 >> (x - 8)
                    if lo & b:
                        v |= (1 << p)
            # NOTE: plane p uses one bit per pixel spread over hi/lo bytes:
            # hi byte holds bits 8..15 of the 16-pixel plane row, lo 0..7.
            pixels.append(v)
        rows.append(pixels)
    return rows


def sprite16_pixels2(s128):
    """Correct 16x16 decoder: plane p row r = 16 bits, hi byte = pixels 8..15."""
    rows = []
    for r in range(16):
        plane_bits = []
        for p in range(4):
            hi = s128[p * 32 + r * 2]
            lo = s128[p * 32 + r * 2 + 1]
            bits = []
            for x in range(8):
                bits.append(1 if hi & (0x80 >> x) else 0)
            for x in range(8):
                bits.append(1 if lo & (0x80 >> x) else 0)
            plane_bits.append(bits)
        row = []
        for x in range(16):
            v = 0
            for p in range(4):
                if plane_bits[p][x]:
                    v |= 1 << p
            row.append(v)
        rows.append(row)
    return rows


def vce_word_to_rgb(w):
    b = w & 7
    r = (w >> 3) & 7
    g = (w >> 6) & 7
    # 3-bit -> 8-bit by bit replication
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def load_palette(data, off, count=16):
    """Read `count` consecutive 16-bit VCE words starting at byte offset."""
    out = []
    for i in range(count):
        lo, hi = data[off + i * 2], data[off + i * 2 + 1]
        out.append(vce_word_to_rgb(lo | (hi << 8)))
    return out


def make_sheet(pixel_rows, tile_w, tile_h, tw, th, palette, scale=3,
               margin=2, out="out.png", labels=None):
    cols = tw
    rows = (th + cols - 1) // cols
    w = cols * (tile_w * scale + margin) + margin
    h = rows * (tile_h * scale + margin) + margin
    img = Image.new("RGB", (w, h), (32, 32, 32))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for t in range(th):
        cx = t % cols
        cy = t // cols
        ox = margin + cx * (tile_w * scale + margin)
        oy = margin + cy * (tile_h * scale + margin)
        for r in range(tile_h):
            for x in range(tile_w):
                idx = pixel_rows(t)[r][x] if False else None
        # fill below
        pr = pixel_rows(t)
        for r in range(tile_h):
            for x in range(tile_w):
                col = palette[pr[r][x] % len(palette)]
                d.rectangle([ox + x * scale, oy + r * scale,
                             ox + x * scale + scale - 1,
                             oy + r * scale + scale - 1], fill=col)
        if labels:
            d.text((ox + 1, oy + tile_h * scale + 1), str(labels(t)), fill=(200, 200, 200))
    img.save(out)
    return out


def cmd_tiles(data, off, count, out, pal=None):
    palette = pal or GRAY
    tiles = []
    for t in range(count):
        base = off + t * 32
        blk = data[base:base + 32]
        if len(blk) < 32:
            break
        tiles.append(bg_tile_pixels(blk))
    if not tiles:
        return None
    cols = 16
    return make_sheet(lambda t: tiles[t], 8, 8, cols, len(tiles), palette,
                      3, 2, out)


def cmd_sprites(data, off, count, out, pal=None):
    palette = pal or GRAY
    sps = []
    for t in range(count):
        base = off + t * 128
        blk = data[base:base + 128]
        if len(blk) < 128:
            break
        sps.append(sprite16_pixels2(blk))
    if not sps:
        return None
    cols = 8
    return make_sheet(lambda t: sps[t], 16, 16, cols, len(sps), palette,
                      4, 2, out)


def cmd_screen(data, off, w=32, h=28, out="screen.png", pal=None):
    """Render `w*h` consecutive 8x8 tiles as one screen (identity tilemap)."""
    palette = pal or GRAY
    scale = 3
    img = Image.new("RGB", (w * 8 * scale, h * 8 * scale), (0, 0, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for t in range(w * h):
        base = off + t * 32
        blk = data[base:base + 32]
        if len(blk) < 32:
            break
        px = bg_tile_pixels(blk)
        tx = (t % w) * 8
        ty = (t // w) * 8
        for r in range(8):
            for x in range(8):
                col = palette[px[r][x] % len(palette)]
                d.rectangle([(tx + x) * scale, (ty + r) * scale,
                             (tx + x) * scale + scale - 1,
                             (ty + r) * scale + scale - 1], fill=col)
    img.save(out)
    return out


def sprite_slot_pixels(s, cells_wide=2):
    """Decode one 16x16 PCE sprite stored in a 32-pixel-wide VRAM slot.

    VDC doc: 'a sprite is always aligned like a 32 pixel wide sprite'. A 1-cell
    wide sprite therefore only uses the first cell of each row; the remaining
    16 pixels belong to the interleaved neighbour.
    Slot layout: plane p (0..3) at bytes [p*64..], row r at +4r, cell c at
    +2c, each cell row = 2 big-endian bytes (16 pixels).
    """
    rows = []
    for r in range(16):
        cells = []
        for c in range(cells_wide):
            word = []
            for x in range(16):
                v = 0
                for p in range(4):
                    base = p * 64 + r * 4 + c * 2
                    hi, lo = s[base], s[base + 1]
                    if x < 8:
                        if hi & (0x80 >> x):
                            v |= 1 << p
                    else:
                        if lo & (0x80 >> (x - 8)):
                            v |= 1 << p
                word.append(v)
            cells.append(word)
        rows.append(cells)
    return rows


def cmd_slots(data, off, count, out, pal=None, cells_wide=2):
    palette = pal or GRAY
    sps = []
    for t in range(count):
        base = off + t * (64 * 4)
        blk = data[base:base + 256]
        if len(blk) < 256:
            break
        sps.append(sprite_slot_pixels(blk, cells_wide))
    if not sps:
        return None
    from PIL import ImageDraw
    cols = 8
    rows = (len(sps) + cols - 1) // cols
    cellpx = cells_wide * 16
    scale = 3
    img = Image.new("RGB", (cols * cellpx * scale + 8, rows * 16 * scale + 8), (24, 24, 24))
    d = ImageDraw.Draw(img)
    for t, sp in enumerate(sps):
        cx = t % cols
        cy = t // cols
        ox = 4 + cx * cellpx * scale
        oy = 4 + cy * 16 * scale
        for r in range(16):
            for c in range(cells_wide):
                for x in range(16):
                    col = palette[sp[r][c][x] % len(palette)]
                    d.rectangle([ox + (c * 16 + x) * scale, oy + r * scale,
                                 ox + (c * 16 + x) * scale + scale - 1,
                                 oy + r * scale + scale - 1], fill=col)
    img.save(out)
    return out


def load_palette_md(data, off, count=64):
    """Read `count` VCE palette words and return Mega Drive colours."""
    out = []
    for i in range(count):
        lo, hi = data[off + i * 2], data[off + i * 2 + 1]
        w = lo | (hi << 8)
        b = w & 7
        r = (w >> 3) & 7
        g = (w >> 6) & 7
        out.append((r * 255 // 7, g * 255 // 7, b * 255 // 7))
    return out


def cmd_pal(data, off, count):
    for i in range(count):
        w = data[off + i * 2] | (data[off + i * 2 + 1] << 8)
        r, g, b = vce_word_to_rgb(w)
        print("  [%2d] $%03X  R%d G%d B%d   #%02X%02X%02X" % (i, w, w & 7,
              (w >> 3) & 7, (w >> 6) & 7, r, g, b))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    data = open(sys.argv[2], "rb").read()
    if cmd == "tiles":
        off = int(sys.argv[3], 0)
        n = int(sys.argv[4], 0)
        out = sys.argv[5]
        pal = None
        if len(sys.argv) > 7:
            pal = load_palette(data, int(sys.argv[6], 0), int(sys.argv[7], 0))
        print(cmd_tiles(data, off, n, out, pal), "written")
    elif cmd == "sprites":
        off = int(sys.argv[3], 0)
        n = int(sys.argv[4], 0)
        out = sys.argv[5]
        pal = None
        if len(sys.argv) > 7:
            pal = load_palette(data, int(sys.argv[6], 0), int(sys.argv[7], 0))
        print(cmd_sprites(data, off, n, out, pal), "written")
    elif cmd == "screen":
        off = int(sys.argv[3], 0)
        w = int(sys.argv[4], 0) if len(sys.argv) > 4 else 32
        h = int(sys.argv[5], 0) if len(sys.argv) > 5 else 28
        out = sys.argv[6] if len(sys.argv) > 6 else "build/gfx/screen.png"
        print(cmd_screen(data, off, w, h, out), "written")
    elif cmd == "slots":
        off = int(sys.argv[3], 0)
        n = int(sys.argv[4], 0)
        out = sys.argv[5]
        cw = int(sys.argv[6], 0) if len(sys.argv) > 6 else 2
        pal = None
        if len(sys.argv) > 8:
            pal = load_palette(data, int(sys.argv[7], 0), int(sys.argv[8], 0))
        print(cmd_slots(data, off, n, out, pal, cw), "written")
    elif cmd == "pal":
        off = int(sys.argv[3], 0)
        n = int(sys.argv[4], 0) if len(sys.argv) > 4 else 32
        cmd_pal(data, off, n)


if __name__ == "__main__":
    main()
