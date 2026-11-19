#!/usr/bin/env python3
"""Extract the STG2C blue knight and fireball as Mega Drive sprite tiles.

The source is the same PC Engine gameplay capture used by STAGE2C.  The boss
keeps its captured 32x32 silhouette; its PCE sprite-palette colours are mapped
to the nearest entries of the player's existing line-3 palette so the arena
needs no extra CRAM line.  The output is ready for the 2x2-cell hardware sprite
at the module's boss tile base.
"""
import os
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import render_pce_state as rps
from pce_gfx import sprite16_pixels2, vce_word_to_rgb

VRAM = ROOT / 'build/gfx/stage2c_runtime_neutral.vram.bin'
SAT = ROOT / 'build/gfx/stage2c_runtime_neutral.sat.bin'
CRAM = ROOT / 'build/gfx/stage2c_runtime_neutral.cram.bin'
TARGET_PAL = ROOT / 'game/res/gfx/stage2_state_pal.bin'
OUT_BOSS = ROOT / 'game/res/gfx/stage2_boss_tiles.bin'
OUT_FIRE = ROOT / 'game/res/gfx/stage2_boss_fire_tiles.bin'
PREVIEW = ROOT / 'build/gfx/stage2_boss_preview.png'

# SAT entries: #1 is the blue armoured knight, #5 is the fireball.
BOSS_ENTRY = 1
FIRE_ENTRY = 5


def gen_color(value):
    return (((value >> 1) & 7) * 255 // 7,
            ((value >> 5) & 7) * 255 // 7,
            ((value >> 9) & 7) * 255 // 7)


def nearest(rgb, palette):
    return min(range(1, 16), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb, palette[i])))


def md_tile(rows):
    out = bytearray()
    for row in rows:
        for x in range(0, 8, 2):
            out.append((row[x] << 4) | row[x + 1])
    return out


def pack_sprite(pixels, palette):
    """16/32/64-pixel sprite -> contiguous 8x8 MD tiles in sprite order."""
    height = len(pixels)
    width = len(pixels[0])
    out = bytearray()
    for cell_y in range(0, height, 8):
        for cell_x in range(0, width, 8):
            rows = [pixels[cell_y + y][cell_x:cell_x + 8] for y in range(8)]
            out += md_tile(rows)
    return out


def main():
    vram = VRAM.read_bytes()
    sat = SAT.read_bytes()
    cram = CRAM.read_bytes()
    target = [gen_color(v) for v in __import__('struct').unpack('>64H', TARGET_PAL.read_bytes())[48:64]]

    def entry(index):
        return [int.from_bytes(sat[index * 8 + i:index * 8 + i + 2], 'little') for i in (0, 2, 4, 6)]

    def mapped(index):
        _, _, pattern, attr = entry(index)
        pixels = rps.decode_sprite(vram, pattern, attr)
        source = attr & 15
        source_colors = [vce_word_to_rgb(int.from_bytes(cram[2 * (256 + source * 16 + i):
                                                              2 * (256 + source * 16 + i) + 2], 'little'))
                         for i in range(16)]
        out = []
        for row in pixels:
            line = []
            for value in row:
                line.append(0 if not value else nearest(source_colors[value], target))
            out.append(line)
        return out

    boss = mapped(BOSS_ENTRY)
    fire = mapped(FIRE_ENTRY)
    OUT_BOSS.write_bytes(pack_sprite(boss, target))
    OUT_FIRE.write_bytes(pack_sprite(fire, target))
    print('boss %dx%d -> %d bytes; fire %dx%d -> %d bytes' %
          (len(boss[0]), len(boss), OUT_BOSS.stat().st_size,
           len(fire[0]), len(fire), OUT_FIRE.stat().st_size))

    # A simple preview against the target line.
    scale = 6
    preview = Image.new('RGB', ((len(boss[0]) + len(fire[0]) + 8) * scale,
                                max(len(boss), len(fire)) * scale), (20, 20, 24))
    px = preview.load()
    for n, (sprite, ox) in enumerate(((boss, 0), (fire, len(boss[0]) + 8))):
        for y, row in enumerate(sprite):
            for x, value in enumerate(row):
                if value:
                    rgb = target[value]
                    for dy in range(scale):
                        for dx in range(scale):
                            px[(ox + x) * scale + dx, y * scale + dy] = rgb
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    preview.save(PREVIEW)
    print('preview', PREVIEW)


if __name__ == '__main__':
    main()
