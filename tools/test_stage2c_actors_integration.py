#!/usr/bin/env python3
"""Verify that STAGE2C draws the captured PCE player frame in-game.

The test selects STAGE2C from the title, reads the live stage_player position
from work RAM, and compares the nontransparent pixels of the packed idle frame
with the same rectangle in the emulator screenshot. The emulator expands the
Mega Drive 3-bit colors with its own brightness curve, so each channel allows a
small tolerance; the sprite mask and frame position must match exactly.
"""
import argparse
import re
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image

HARNESS = Path(__file__).resolve().with_name('test_megacd_libretro.py')
ROOT = Path(__file__).resolve().parents[1]
SCENE_STAGE2C = 6
FRAME = 2550


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    print('PASS:', description, flush=True)


def symbol(artifacts, name):
    path = artifacts / 'build' / 'stage2c.mmd.elf.sym'
    text = path.read_text(encoding='ascii')
    match = re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+' + name + r'\s*$', text, re.M)
    if not match:
        raise ValueError('missing %s in %s' % (name, path))
    address = int(match.group(1), 16)
    if not 0xff0000 <= address <= 0xfffff8:
        raise ValueError('%s outside 68000 work RAM: %x' % (name, address))
    return address & 0xffff


def read_byte(data, address):
    return data[address ^ 1]


def unpack_frame(data, width=64, height=48):
    pixels = [[0] * width for _ in range(height)]
    p = 0
    for top in range(0, height, 32):
        for left in range(0, width, 32):
            for tx in range(left, min(left + 32, width), 8):
                for ty in range(top, min(top + 32, height), 8):
                    for y in range(ty, ty + 8):
                        for x in range(tx, tx + 8, 2):
                            value = data[p]
                            p += 1
                            pixels[y][x] = value >> 4
                            pixels[y][x + 1] = value & 15
    return pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--system', type=Path, required=True)
    parser.add_argument('--cue', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for name in ('core', 'system', 'cue', 'artifacts', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    if args.output.exists():
        parser.error('output directory must not already exist')
    args.output.mkdir(parents=True)
    run = args.output / 'run'
    events = ['600:start:4']
    events += ['%d:right:4' % (2100 + 20 * i) for i in range(4)]
    events += ['2250:start:4']
    command = [sys.executable, str(HARNESS), '--core', str(args.core),
               '--system', str(args.system), '--cue', str(args.cue),
               '--output', str(run), '--save-dir', str(args.output / 'save'),
               '--frames', '2600', '--script-only', '--no-audio-file',
               '--capture', str(FRAME), '--capture-ram', str(FRAME)]
    for event in events:
        command.extend(('--event', event))
    completed = subprocess.run(command, text=True, capture_output=True)
    (args.output / 'actors.log').write_text(completed.stdout + '\n' + completed.stderr,
                                            encoding='utf-8')
    check(completed.returncode == 0, 'STAGE2C actor case core execution')

    player = symbol(args.artifacts, 'stage_player')
    combat = symbol(args.artifacts, 'stage_combat')
    enemies = symbol(args.artifacts, 'stage_enemies')
    enemy_tick = symbol(args.artifacts, 'enemy_tick')
    ram = (run / ('ram_%04d.bin' % FRAME)).read_bytes()
    check(ram[0xf501] == SCENE_STAGE2C, 'the STAGE2C scene is loaded')
    x, y = struct.unpack_from('<HH', ram, player)
    facing = read_byte(ram, combat + 3)
    camera_x = max(0, x - 120)
    camera_x = min(camera_x, (4 - 1) * 256)
    flip = 0 if facing else 1
    left = x - camera_x - (40 if flip else 8)
    top = y - 32
    print('player', x, y, 'facing', facing, 'camera', camera_x,
          'sprite', left, top, flush=True)

    actors = (ROOT / 'game' / 'res' / 'gfx' / 'stage2c_state_actors.bin').read_bytes()
    palette = (ROOT / 'game' / 'res' / 'gfx' / 'stage2c_state_pal.bin').read_bytes()
    line = struct.unpack_from('>16H', palette, 3 * 32)
    pixels = unpack_frame(actors[:48 * 32])
    if flip:
        pixels = [row[::-1] for row in pixels]

    shot = Image.open(run / ('frame_%04d.png' % FRAME)).convert('RGB')
    check(shot.size == (256, 224), 'screenshot dimensions')
    expected = 0
    matched = 0
    worst = 0
    observed_colors = set()
    for py in range(48):
        for px in range(64):
            index = pixels[py][px]
            if not index:
                continue
            expected += 1
            color = line[index]
            want = (((color >> 1) & 7) * 255 // 7,
                    ((color >> 5) & 7) * 255 // 7,
                    ((color >> 9) & 7) * 255 // 7)
            got = shot.getpixel((left + px, top + py))
            observed_colors.add(got)
            error = max(abs(got[c] - want[c]) for c in range(3))
            worst = max(worst, error)
            if error <= 20:
                matched += 1
    print('sprite pixels', expected, 'matched', matched, 'worst', worst,
          'colors', len(observed_colors), flush=True)
    check(expected > 500, 'the captured player frame covers its 64x48 box')
    check(matched == expected,
          'every captured player pixel matches the emulator within tolerance')
    check(len(observed_colors) >= 6,
          'the sprite shows the captured multi-colour player art')
    check((left, top) == (92, 18),
          'the captured frame is drawn at the live STAGE2C spawn position')

    # The two dungeon patrols use the captured fire frames on palette line 2.
    # The video buffer can be one patrol step ahead of the post-frame RAM, so
    # accept either adjacent draw position and require a full pixel match.
    tick = read_byte(ram, enemy_tick)
    enemy_frame = (tick >> 3) & 1
    fire = actors[(4 + enemy_frame) * 48 * 32:(5 + enemy_frame) * 48 * 32]
    fire_line = struct.unpack_from('>16H', palette, 2 * 32)
    for slot in range(2):
        base = enemies + slot * 12
        ex, ey = struct.unpack_from('<hh', ram, base)
        alive = read_byte(ram, base + 9)
        direction = read_byte(ram, base + 10)
        if not alive:
            continue
        fire_pixels = unpack_frame(fire, 48, 64)
        if direction:
            fire_pixels = [row[::-1] for row in fire_pixels]
        results = []
        for dx in (0, 1 if direction == 0 else -1):
            fx = ex - camera_x - 16 + dx
            fy = ey - 48
            total = 0
            good = 0
            for py in range(64):
                for px in range(48):
                    value = fire_pixels[py][px]
                    if not value:
                        continue
                    total += 1
                    color = fire_line[value]
                    want = (((color >> 1) & 7) * 255 // 7,
                            ((color >> 5) & 7) * 255 // 7,
                            ((color >> 9) & 7) * 255 // 7)
                    got = shot.getpixel((fx + px, fy + py))
                    if max(abs(got[c] - want[c]) for c in range(3)) <= 20:
                        good += 1
            results.append((good, total, dx, fx, fy))
        best = max(results)
        print('enemy', slot, 'frame', enemy_frame,
              'candidates', results, 'best', best, flush=True)
        check(best[1] > 30 and best[0] == best[1],
              'dungeon enemy %d draws the captured fire frame' % slot)

    print('PASS: STAGE2C draws the captured PCE player frame in game', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, struct.error) as exc:
        print('FAIL:', exc, file=sys.stderr)
        raise SystemExit(1)
