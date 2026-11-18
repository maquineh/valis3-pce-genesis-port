#!/usr/bin/env python3
"""Render a Mednafen PC Engine state, including the captured SAT sprites.

Usage:
    py -3 tools/render_pce_state.py STATE.mc4 [OUTPUT.png]

The renderer reads the 64x64 BAT from VRAM, applies the saved background
scroll, and composites the 64-entry SAT using the HuC6270 pattern addressing
and sprite size fields. The default viewport is 256x224 pixels.
"""
import argparse
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pce_gfx import bg_tile_pixels, vce_word_to_rgb, sprite16_pixels2
from pce_state import decompress, parse


WIDTH, HEIGHT = 256, 224
BAT_SIZE = 64


def word(data, offset):
    return data[offset] | (data[offset + 1] << 8)


def palette_colors(raw):
    return [vce_word_to_rgb(word(raw, i * 2))
            for i in range(len(raw) // 2)]


def render_background(vram, colors, scroll_x, scroll_y):
    image = Image.new('RGB', (WIDTH, HEIGHT))
    pixels = image.load()
    opaque = bytearray(WIDTH * HEIGHT)
    decoded_tiles = {}
    for y in range(HEIGHT):
        world_y = (scroll_y + y) & 511
        bat_y, tile_y = divmod(world_y, 8)
        for x in range(WIDTH):
            world_x = (scroll_x + x) & 511
            bat_x, tile_x = divmod(world_x, 8)
            entry = word(vram, (bat_y * BAT_SIZE + bat_x) * 2)
            tile = entry & 0x0fff
            palette = entry >> 12
            decoded = decoded_tiles.get(tile)
            if decoded is None:
                base = (tile * 32) & 0xffff
                decoded = bg_tile_pixels(vram[base:base + 32])
                decoded_tiles[tile] = decoded
            color = decoded[tile_y][tile_x]
            if color:
                color += palette * 16
            pixels[x, y] = colors[color]
            opaque[y * WIDTH + x] = color != 0
    return image, opaque


def sprite_size(attr):
    width = 32 if attr & 0x0100 else 16
    cgy = (attr >> 12) & 3
    height = (16, 32, 64, 64)[cgy]
    return width, height, cgy


def decode_sprite(vram, raw_pattern, attr):
    width, height, cgy = sprite_size(attr)
    pattern = raw_pattern >> 1
    if cgy & 1:
        pattern &= ~2
    if cgy & 2:
        pattern &= ~6
    if width == 32:
        pattern &= ~1

    pixels = [[0] * width for _ in range(height)]
    for cell_y in range(height // 16):
        for cell_x in range(width // 16):
            cell_pattern = pattern + cell_y * 2 + cell_x
            offset = cell_pattern * 128
            if offset + 128 > len(vram):
                continue
            cell = sprite16_pixels2(vram[offset:offset + 128])
            for y in range(16):
                for x in range(16):
                    pixels[cell_y * 16 + y][cell_x * 16 + x] = cell[y][x]

    if attr & 0x8000:
        pixels.reverse()
    if attr & 0x0800:
        pixels = [row[::-1] for row in pixels]
    return pixels


def composite_sprites(image, bg_opaque, vram, colors, sat):
    output = image.copy()
    out = output.load()
    occupied = bytearray(WIDTH * HEIGHT)
    for index in range(64):
        y, x, raw_pattern, attr = [word(sat, index * 8 + i)
                                   for i in (0, 2, 4, 6)]
        if y >= 512 or x >= 512:
            continue
        sprite = decode_sprite(vram, raw_pattern, attr)
        palette = attr & 0x0f
        front = bool(attr & 0x0080)
        for sy, row in enumerate(sprite):
            screen_y = y + sy
            if not 0 <= screen_y < HEIGHT:
                continue
            for sx, color in enumerate(row):
                screen_x = x + sx
                if not color or not 0 <= screen_x < WIDTH:
                    continue
                position = screen_y * WIDTH + screen_x
                if occupied[position]:
                    continue
                if not front and bg_opaque[position]:
                    continue
                occupied[position] = 1
                out[screen_x, screen_y] = colors[256 + palette * 16 + color]
    return output


def render_sprite_atlas(vram, colors, sat, output_path):
    entries = []
    for index in range(64):
        y, x, raw_pattern, attr = [word(sat, index * 8 + i)
                                   for i in (0, 2, 4, 6)]
        if y >= 512 or x >= 512:
            continue
        sprite = decode_sprite(vram, raw_pattern, attr)
        if any(pixel for row in sprite for pixel in row):
            entries.append((index, y, x, raw_pattern, attr, sprite))

    scale = 2
    cell_width, cell_height, columns = 144, 150, 4
    rows = max(1, (len(entries) + columns - 1) // columns)
    atlas = Image.new('RGB', (columns * cell_width, rows * cell_height),
                      (28, 28, 32))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(atlas)
    for n, (index, y, x, pattern, attr, sprite) in enumerate(entries):
        cell_x = (n % columns) * cell_width
        cell_y = (n // columns) * cell_height
        draw.text((cell_x + 4, cell_y + 3),
                  '#%02d x%d y%d pat%03X a%04X' %
                  (index, x, y, pattern, attr), fill=(220, 220, 220))
        origin_x, origin_y = cell_x + 4, cell_y + 20
        palette = 256 + (attr & 0x0f) * 16
        for sy, row in enumerate(sprite):
            for sx, color in enumerate(row):
                if color:
                    rgb = colors[palette + color]
                    draw.rectangle((origin_x + sx * scale,
                                    origin_y + sy * scale,
                                    origin_x + sx * scale + scale - 1,
                                    origin_y + sy * scale + scale - 1),
                                   fill=rgb)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    atlas.save(output_path)
    print('%s: %d SAT sprites' % (output_path, len(entries)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state')
    parser.add_argument('output', nargs='?', default='build/pce_state.png')
    parser.add_argument('--atlas', help='also write a labeled SAT sprite atlas')
    args = parser.parse_args()
    state_path, output_path = args.state, args.output
    variables = parse(decompress(state_path))
    required = ('VRAM', 'color_table', 'SAT', 'BG_XOffset', 'BG_YOffset')
    missing = [key for key in required if key not in variables]
    if missing:
        raise SystemExit('state is missing: ' + ', '.join(missing))

    vram = variables['VRAM'][2]
    cram = variables['color_table'][2]
    sat = variables['SAT'][2]
    scroll_x = int.from_bytes(variables['BG_XOffset'][2], 'little') & 511
    scroll_y = int.from_bytes(variables['BG_YOffset'][2], 'little') & 511
    colors = palette_colors(cram)
    image, bg_opaque = render_background(vram, colors, scroll_x, scroll_y)
    image = composite_sprites(image, bg_opaque, vram, colors, sat)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    image.save(output_path)
    print('%s: %dx%d, scroll=(%d,%d)' %
          (output_path, WIDTH, HEIGHT, scroll_x, scroll_y))
    if args.atlas:
        render_sprite_atlas(vram, colors, sat, args.atlas)


if __name__ == '__main__':
    main()
