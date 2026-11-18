#!/usr/bin/env python3
"""Rebuild the captured PCE title menu as a single MD plane.

Both captures include the original sprite compositing. Compose the menu below
the logo, quantize RGB to 3-bit channels, and allocate each 8x8 cell to four shared
15-colour lines. Entry zero is transparent on every line; the backdrop is black.
"""
from pathlib import Path
from hashlib import sha256
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MENU_SOURCE = ROOT / 'states/title_pce_menu.bmp'
LOGO_SOURCE = ROOT / 'states/title_pce_logo.bmp'
OUT = ROOT / 'game/res/gfx'
W, H = 256, 224


def quantize(rgb):
    return tuple((c * 7 + 127) // 255 for c in rgb)


def allocate(sets):
    # Exact search; processing maximal sets first and breaking equal-line
    # symmetry keeps this fast and deterministic. Never silently lose colours.
    maximal = sorted((s for s in sets if s and not any(s < t for t in sets)),
                     key=lambda s: (-len(s), sorted(s)))
    def visit(i, lines):
        if i == len(maximal):
            return lines
        seen = set()
        for n in range(4):
            if lines[n] in seen:
                continue
            seen.add(lines[n])
            merged = lines[n] | maximal[i]
            if len(merged) <= 15:
                new = list(lines)
                new[n] = merged
                result = visit(i + 1, new)
                if result is not None:
                    return result
        return None
    result = visit(0, [frozenset()] * 4)
    if result is None:
        raise ValueError('capture cannot fit four 15-colour palette lines')
    return [sorted(line) for line in result]


def build():
    logo = Image.open(LOGO_SOURCE).convert('RGB')
    menu = Image.open(MENU_SOURCE).convert('RGB')
    if logo.size != (256, 243) or menu.size != (256, 243):
        raise ValueError('unexpected capture dimensions')
    source = logo.crop((0, 0, W, H))
    # Remove the title's PUSH RUN BUTTON; replace it with the original menu.
    source.paste((0, 0, 0), (0, 145, W, 190))
    source.paste(menu.crop((64, 56, 160, 96)), (64, 144))
    pixels = list(source.getdata())
    quant = [quantize(p) for p in pixels]
    black = (0, 0, 0)
    cells = []
    for ty in range(H // 8):
        for tx in range(W // 8):
            cells.append([quant[(ty * 8 + y) * W + tx * 8 + x]
                          for y in range(8) for x in range(8)])
    lines = allocate({frozenset(c) - {black} for c in cells})
    palettes = [[black] + line for line in lines]
    tiles = [bytes(32)]
    tile_index = {tiles[0]: 0}
    tilemap = bytearray()
    for cell in cells:
        colors = set(cell) - {black}
        line = next(i for i, pal in enumerate(palettes) if colors <= set(pal))
        lookup = {color: i for i, color in enumerate(palettes[line])}
        indices = [lookup[c] for c in cell]
        tile = bytes(indices[i] << 4 | indices[i + 1] for i in range(0, 64, 2))
        if tile not in tile_index:
            tile_index[tile] = len(tiles)
            tiles.append(tile)
        tilemap += (tile_index[tile] | (line << 13)).to_bytes(2, 'big')
    if len(tiles) > 2048:
        raise ValueError('title exceeds MD tile index space')
    palbytes = bytearray()
    for pal in palettes:
        for r, g, b in pal + [black] * (16 - len(pal)):
            palbytes += ((r << 1) | (g << 5) | (b << 9)).to_bytes(2, 'big')
    rgb = [tuple((v * 255 + 3) // 7 for v in p) for p in quant]
    errors = [abs(a - b) for p, q in zip(pixels, rgb) for a, b in zip(p, q)]
    info = dict(width=W, height=H, source_width=256, source_height=243,
                tile_count=len(tiles), palette_count=4, palette_entries=16,
                palette_used=[len(p) for p in palettes],
                source_sha256={ 'menu': sha256(MENU_SOURCE.read_bytes()).hexdigest(),
                                'logo': sha256(LOGO_SOURCE.read_bytes()).hexdigest()},
                quantization='(channel*7+127)//255; expand (level*255+3)//7',
                mean_absolute_channel_error=round(sum(errors) / len(errors), 6),
                max_absolute_channel_error=max(errors),
                changed_pixels=sum(a != b for a, b in zip(pixels, rgb)))
    return b''.join(tiles), bytes(tilemap), bytes(palbytes), info, rgb


def main():
    tiles, tilemap, palette, info, rgb = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in [('title_tiles.bin', tiles), ('title_map.bin', tilemap),
                       ('title_pal.bin', palette)]:
        (OUT / name).write_bytes(data)
    (OUT / 'title.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    image = Image.new('RGB', (W, H))
    image.putdata(rgb)
    image.save(OUT / 'title_reference.png')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
