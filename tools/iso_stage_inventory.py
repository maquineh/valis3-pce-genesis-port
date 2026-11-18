"""Inventory the ten STG stage blocks on the retail ISO and render their tiles.

Outputs:
  build/gfx/stg_inventory/<NAME>_tiles.png   raw tile sheet (palette 0)
  build/gfx/stg_inventory/contact.png        contact sheet of all ten
  docs/iso-stage-inventory.md                table + save-state coverage
"""
import json
import os
import sys

sys.path.insert(0, 'tools')
from PIL import Image, ImageDraw

TRACK = 'build/extracted/data/track_02.bin'
OUT = 'build/gfx/stg_inventory'
DOC = 'docs/iso-stage-inventory.md'

BLOCKS = [
    (304, 'STG1A'), (344, 'STG2A'), (384, 'STG2B'), (424, 'STG2C'),
    (464, 'STG3A'), (504, 'STG3B'), (544, 'STG4A'), (584, 'STG4B'),
    (624, 'STG4C'), (664, 'STG5A'),
]
TILES = 0x6E40
PAL = 0x264
TEXT = 0xC00
BLOCK = 0x14000

# save-state coverage found by scanning every .mcX in the root and states/
COVER = {
    'STG1A': 'states `…stg1a.mc1`',
    'STG2A': 'root `.mc0`, states `.mc0`/`.mc1` (room 1 + seaside)',
    'STG2B': 'root `.mc2`',
    'STG2C': 'root `.mc3`, states `.mc2`/`.mc3` (dungeon + green room)',
    'STG3A': 'root `.mc4`, states `.mc4`',
    'STG4A': 'states `.mc9`',
}


def color(v):
    b = v & 7
    r = (v >> 3) & 7
    g = (v >> 6) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def render_tiles(blk, name):
    cram = [blk[PAL + i * 2] | (blk[PAL + i * 2 + 1] << 8) for i in range(16)]
    pal = [color(c) for c in cram]
    count = (len(blk) - TILES) // 32
    cols = 32
    rows = (count + cols - 1) // cols
    img = Image.new('RGB', (cols * 8, rows * 8 + 12), (0, 0, 0))
    pix = img.load()
    draw = ImageDraw.Draw(img)
    draw.text((2, 0), '%s (%d tiles)' % (name, count), fill=(255, 255, 255))
    for t in range(count):
        base = TILES + t * 32
        tx = (t % cols) * 8
        ty = (t // cols) * 8 + 12
        for py in range(8):
            w0 = blk[base + py * 2] | (blk[base + py * 2 + 1] << 8)
            w1 = blk[base + 16 + py * 2] | (blk[base + 16 + py * 2 + 1] << 8)
            for px in range(8):
                bit = 7 - px
                v = (w0 >> bit) & 1
                v |= ((w0 >> (bit + 8)) & 1) << 1
                v |= ((w1 >> bit) & 1) << 2
                v |= ((w1 >> (bit + 8)) & 1) << 3
                pix[tx + px, ty + py] = pal[v]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, '%s_tiles.png' % name)
    img.save(path)
    return path, count


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs('docs', exist_ok=True)
    disc = open(TRACK, 'rb').read()
    rows = []
    thumbs = []
    for sector, name in BLOCKS:
        off = sector * 2352 + 16
        blk = disc[off:off + BLOCK]
        assert blk[:5] == name.encode(), (name, blk[:5])
        idx = blk[0x10]
        rooms = blk[0x11]
        chapter = blk[0x13]
        text = blk[TEXT:TEXT + 0x400].split(b'\x00')[0]
        try:
            text = text.decode('shift_jis', errors='replace')
        except Exception:
            text = ''
        text = ''.join(ch for ch in text if 32 <= ord(ch) < 127 or ord(ch) > 0x3000)[:28]
        path, count = render_tiles(blk, name)
        rows.append((name, sector, idx, rooms, chapter, count,
                     COVER.get(name, '**no save state**'), text))
        thumbs.append((name, path))
        print('%s sector %3d idx %d rooms %d ch %d tiles %d  %s' %
              (name, sector, idx, rooms, chapter, count,
               COVER.get(name, 'NO STATE')))

    # contact sheet
    cell_w, cell_h = 192, 320
    sheet = Image.new('RGB', (cell_w * 5, cell_h * 2), (20, 20, 20))
    for i, (name, path) in enumerate(thumbs):
        im = Image.open(path)
        im.thumbnail((cell_w - 8, cell_h - 24))
        x = (i % 5) * cell_w + 4
        y = (i // 5) * cell_h + 20
        sheet.paste(im, (x, y))
        ImageDraw.Draw(sheet).text((x, y - 14), name, fill=(255, 255, 255))
    sheet.save(os.path.join(OUT, 'contact.png'))

    with open(DOC, 'w', encoding='utf-8') as fh:
        fh.write('# ISO stage inventory\n\n')
        fh.write('Track 2 of `Valis_3_(NTSC-J)_[TJCD0009].cue` contains ten '
                 '`STG` blocks of 40 user sectors (81920 B) each.  The header '
                 'at `+0x10` is the stage index, `+0x11` the room/area count, '
                 '`+0x13` the chapter.  Raw 4bpp tiles start at `+0x6E40`; '
                 'palette data at `+0x264`; Shift-JIS text at `+0xC00`.\n\n')
        fh.write('| block | sector | idx | rooms | ch | tiles | save state | module |\n')
        fh.write('|-------|--------|-----|-------|----|-------|------------|--------|\n')
        mods = {'STG1A': '`STAGE1A.MMD`', 'STG2A': '`STAGE2.MMD` + `STAGE2A2.MMD`', 'STG2B': '`STAGE2B.MMD`',
                'STG2C': '`STAGE2C.MMD`', 'STG3A': '`STAGE3A.MMD`',
                'STG4A': '`STAGE4A.MMD` + `STAGE4AX.MMD`'}
        for name, sector, idx, rooms, chapter, count, cover, text in rows:
            fh.write('| %s | %d | %d | %d | %d | %d | %s | %s |\n' %
                     (name, sector, idx, rooms, chapter, count, cover,
                      mods.get(name, '—')))
        fh.write('\nTile sheets: `build/gfx/stg_inventory/<NAME>_tiles.png`; '
                 'contact sheet: `build/gfx/stg_inventory/contact.png`.\n\n')
        fh.write('The four blocks **STG3B, STG4B, STG4C and STG5A** '
                 'are present in the ISO with their tiles, palettes, text and '
                 'object records, but no save state covers them.  Their BAT is '
                 'generated at runtime, so a gameplay F5 state is required to '
                 'pack them like the others.\n')


if __name__ == '__main__':
    main()
