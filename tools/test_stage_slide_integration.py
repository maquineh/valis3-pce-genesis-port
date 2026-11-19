#!/usr/bin/env python3
"""Drive the STAGE2A2 lance encounter with the DOWN+B slide.

Requires the built ISO's matching native-artifacts directory (ELF symbols), a
Genesis Plus GX core, a BIOS directory and the disc CUE. The test uses an
isolated backup-RAM directory. It enters the seaside room from the title menu,
walks up to the captured lance enemy, slides through it and checks that:
  * the slide starts instead of a jump and advances three pixels per frame;
  * the enemy loses exactly one hit point per slide;
  * the lowered slide body does not take contact damage;
  * the slide ends and normal control returns.
"""
import argparse
import re
import subprocess
import sys
import struct
from pathlib import Path

HARNESS = Path(__file__).resolve().with_name('test_megacd_libretro.py')
SCENE_STAGE2A2 = 7


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    print('PASS:', description, flush=True)


def symbol(artifacts, module, name):
    path = artifacts / 'build' / (module + '.mmd.elf.sym')
    text = path.read_text(encoding='ascii')
    match = re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+' + name + r'\s*$', text, re.M)
    if not match:
        raise ValueError('missing %s in %s' % (name, path))
    address = int(match.group(1), 16)
    if not 0xff0000 <= address <= 0xfffff8:
        raise ValueError('%s outside 68000 work RAM: %x' % (name, address))
    return address & 0xffff


def read_byte(data, address):
    """Genesis Plus GX stores 68000 words byte-swapped on little-endian hosts."""
    return data[address ^ 1]


def snapshot(path, player, combat, enemies):
    data = path.read_bytes()
    x, y, vy, grounded = struct.unpack_from('<HHhH', data, player)
    ex, ey = struct.unpack_from('<hh', data, enemies)
    return {
        'x': x, 'y': y, 'vy': vy, 'grounded': grounded,
        'slide': read_byte(data, player + 8),
        'player_hp': read_byte(data, combat),
        'enemy_x': ex, 'enemy_y': ey,
        'enemy_hp': read_byte(data, enemies + 8),
        'enemy_alive': read_byte(data, enemies + 9),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--system', type=Path, required=True)
    parser.add_argument('--cue', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True,
                        help='matching build/native-artifacts/<id> directory')
    parser.add_argument('--output', type=Path, required=True,
                        help='new directory for RAM captures and logs')
    args = parser.parse_args()
    for name in ('core', 'system', 'cue', 'artifacts', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    if args.output.exists():
        parser.error('output directory must not already exist')
    args.output.mkdir(parents=True)
    save_dir = args.output / 'save'
    frames = 2620
    captures = (2439, 2450, 2462)
    events = ['600:start:4',            # title -> menu
              '2100:right:4', '2120:right:4',  # select STAGE2A2
              '2250:start:4',
              '2400:right:24',          # walk toward the lance enemy
              '2440:down:4', '2440:b:4']  # DOWN + B -> slide

    command = [sys.executable, str(HARNESS), '--core', str(args.core),
               '--system', str(args.system), '--cue', str(args.cue),
               '--output', str(args.output / 'run'),
               '--save-dir', str(save_dir), '--frames', str(frames),
               '--script-only', '--no-audio-file']
    for event in events:
        command.extend(('--event', event))
    for frame in captures:
        command.extend(('--capture-ram', str(frame)))
    completed = subprocess.run(command, text=True, capture_output=True)
    (args.output / 'slide.log').write_text(completed.stdout + '\n' + completed.stderr,
                                           encoding='utf-8')
    check(completed.returncode == 0, 'slide case core execution')

    player = symbol(args.artifacts, 'stage2a2', 'stage_player')
    combat = symbol(args.artifacts, 'stage2a2', 'stage_combat')
    enemies = symbol(args.artifacts, 'stage2a2', 'stage_enemies')
    run = args.output / 'run'
    ram = lambda frame: run / ('ram_%04d.bin' % frame)
    before = snapshot(ram(captures[0]), player, combat, enemies)
    sliding = snapshot(ram(captures[1]), player, combat, enemies)
    after = snapshot(ram(captures[2]), player, combat, enemies)
    print('before', before, flush=True)
    print('sliding', sliding, flush=True)
    print('after', after, flush=True)

    check(run.joinpath('ram_2439.bin').read_bytes()[0xf501] == SCENE_STAGE2A2,
          'the seaside STAGE2A2 scene is loaded')
    check(before['slide'] == 0 and before['grounded'] == 1,
          'the player stands grounded before the slide')
    check(sliding['slide'] > 0 and sliding['y'] == before['y'],
          'DOWN + B starts a grounded slide instead of a jump')
    check(sliding['x'] >= before['x'] + 20,
          'the slide advances at three pixels per frame')
    check(before['enemy_hp'] == 2 and sliding['enemy_hp'] == 1,
          'the captured lance enemy loses one hit point to the slide')
    check(sliding['player_hp'] == before['player_hp'],
          'the lowered slide body takes no contact damage')
    check(after['slide'] == 0 and after['grounded'] == 1,
          'the slide ends and normal control returns')
    check(after['x'] > before['x'] and after['enemy_hp'] == 1,
          'the player crosses the enemy position without a second hit')
    print('PASS: DOWN+B slide crosses the STAGE2A2 enemy with damage and no contact',
          flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, struct.error) as exc:
        print('FAIL:', exc, file=sys.stderr)
        raise SystemExit(1)
