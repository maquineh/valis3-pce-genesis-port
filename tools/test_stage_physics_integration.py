#!/usr/bin/env python3
"""Exercise stage motion and persistent position on an isolated libretro core.

Requires the built ISO's matching native-artifacts build directory (ELF symbol
files), a Genesis Plus GX core, a BIOS directory and the disc CUE. The test
uses separate backup RAM for every case and does not touch the user's saves.
The native core exposes 68000 work RAM as host-endian 16-bit words.
"""
import argparse
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image

from test_title_menu_integration import crc16_ccitt, save_records

HARNESS = Path(__file__).resolve().with_name('test_megacd_libretro.py')
CASES = (
    ('stage2', 3, (32, 160), 4),
    ('stage2a2', 7, (80, 172), 4),
    ('stage2b', 4, (32, 128), 2),
    ('stage2c', 6, (100, 50), 4),
    ('stage3a', 5, (32, 160), 2),
)


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    print('PASS:', description, flush=True)


def symbol(artifacts, module):
    path = artifacts / 'build' / (module + '.mmd.elf.sym')
    text = path.read_text(encoding='ascii')
    match = re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+stage_player\s*$', text, re.M)
    if not match:
        raise ValueError('stage_player symbol missing from %s' % path)
    address = int(match.group(1), 16)
    if not 0xff0000 <= address <= 0xfffff8:
        raise ValueError('stage_player outside 68000 work RAM: %x' % address)
    return address & 0xffff


def state(path, offset):
    data = path.read_bytes()
    if len(data) != 65536:
        raise ValueError('expected 64 KiB Genesis Plus GX work RAM: %s' % path)
    return struct.unpack_from('<HHhH', data, offset)


def state_slide(path, offset):
    data = path.read_bytes()
    if len(data) != 65536:
        raise ValueError('expected 64 KiB Genesis Plus GX work RAM: %s' % path)
    x, y, vy, grounded = struct.unpack_from('<HHhH', data, offset)
    # The core exposes 68000 words in host byte order, so the two adjacent
    # byte fields swap inside their word: 68000 slide_timer lives at +8.
    return x, y, vy, grounded, data[offset + 9], data[offset + 8]


def check_scene_background(first, second, label):
    """Compare fixed map anchors while allowing actors to move between loads."""
    a = Image.open(first).convert('RGB')
    b = Image.open(second).convert('RGB')
    check(a.size == b.size == (256, 224), label + ' screenshot dimensions')
    # The HUD updates with HP and the player/enemy sprites occupy the centre
    # band. Compare a left background window and the ground strip; both catch
    # a camera or BAT restore regression without reading dynamic actors.
    for box in ((0, 32, 64, 64), (0, 200, 256, 224)):
        check(a.crop(box).tobytes() == b.crop(box).tobytes(),
              label + ' restores the same visible stage background')


def run_case(args, name, save_dir, events, captures, frames):
    output = args.output / name
    command = [sys.executable, str(HARNESS), '--core', str(args.core),
               '--system', str(args.system), '--cue', str(args.cue),
               '--output', str(output), '--save-dir', str(save_dir),
               '--frames', str(frames), '--script-only', '--no-audio-file']
    for event in events:
        command.extend(('--event', event))
    for frame in captures:
        command.extend(('--capture-ram', str(frame)))
        command.extend(('--capture', str(frame)))
    completed = subprocess.run(command, text=True, capture_output=True)
    (args.output / (name + '.log')).write_text(completed.stdout + '\n' + completed.stderr,
                                               encoding='utf-8')
    check(completed.returncode == 0, name + ' core execution')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--system', type=Path, required=True)
    parser.add_argument('--cue', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True,
                        help='matching build/native-artifacts/<id> directory')
    parser.add_argument('--output', type=Path, required=True,
                        help='new directory for screenshots, RAM and isolated saves')
    args = parser.parse_args()
    for name in ('core', 'system', 'cue', 'artifacts', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    if args.output.exists():
        parser.error('output directory must not already exist')
    args.output.mkdir(parents=True)

    for index, (module, scene, spawn, screens) in enumerate(CASES):
        offset = symbol(args.artifacts, module)
        save = args.output / (module + '-save')
        events = ['600:start:4']
        events.extend('%d:right:4' % (2100 + 20 * i) for i in range(index + 1))
        # Ten frames of RIGHT are enough for the movement/checkpoint checks and
        # stop before the STG2C first patrol's contact box.
        events += ['2250:start:4', '2450:b:4', '2600:right:10',
                   '2800:start:4', '3100:down:4', '3120:start:4']
        # The 3A movement fixture lands between both patrols. Retreat after
        # recording movement, leaving a non-spawn checkpoint outside their
        # reach instead of saving the spawn after lethal contact/respawn.
        if module == 'stage3a':
            events.append('2642:left:22')
        first = run_case(args, module, save, events,
                         [2449, 2458, 2500, 2599, 2640, 2799, 3300], 3400)
        at = lambda frame: state(first / ('ram_%04d.bin' % frame), offset)
        before, rise, land = at(2449), at(2458), at(2500)
        movement, moved, saved, resumed = at(2599), at(2640), at(2799), at(3300)
        print(module, 'spawn/ground', before, 'jump', rise, 'land', land,
              'move', movement, moved, 'save', saved, 'resume', resumed, flush=True)
        check(before[3] == 1, module + ' settles on a surface')
        check(rise[1] < before[1] and rise[2] < 0, module + ' B causes an upward jump')
        check(land[1] == before[1] and land[3] == 1,
              module + ' falls back onto its starting surface')
        check(moved[0] > movement[0], module + ' RIGHT moves the character')
        check(0 <= saved[0] <= screens * 256 - 16 and 0 <= saved[1] <= 176,
              module + ' saved position is within scene bounds')
        check(saved[3] == 1, module + ' was grounded before saving')
        check(resumed[:2] == saved[:2], module + ' CONTINUE restores x/y in session')
        before_screen = first / 'frame_2799.png'
        check_scene_background(before_screen, first / 'frame_3300.png',
                               module + ' session CONTINUE')
        bram = (save / 'scd_U.brm').read_bytes()
        valid = [o for o, v in save_records(bram) if v == 2 and bram[o + 4] == scene
                 and bram[o + 5] & 1 and
                 int.from_bytes(bram[o + 6:o + 8], 'big') == saved[0] and
                 int.from_bytes(bram[o + 8:o + 10], 'big') == saved[1]]
        check(bool(valid), module + ' BRAM contains the actual x/y with valid CRC')

        reboot = run_case(args, module + '-reboot', save,
                          ['600:start:4', '2200:down:4', '2240:start:4'], [2400], 2450)
        restarted = state(reboot / 'ram_2400.bin', offset)
        print(module, 'after reboot', restarted, flush=True)
        check(restarted[:2] == saved[:2], module + ' CONTINUE restores x/y after reboot')
        check_scene_background(before_screen, reboot / 'frame_2400.png',
                               module + ' reboot CONTINUE')

        # START is a new run, even when the prior checkpoint belongs to this
        # scene. Re-select the same scene and compare with its original spawn.
        new_events = ['600:start:4']
        new_events.extend('%d:right:4' % (2100 + 20 * i) for i in range(index + 1))
        new_events.append('2250:start:4')
        new = run_case(args, module + '-new-game', save, new_events, [2449], 2500)
        fresh = state(new / 'ram_2449.bin', offset)
        print(module, 'new game', fresh, flush=True)
        check(saved[:2] != before[:2], module + ' checkpoint differs from spawn')
        check(fresh[:2] == before[:2], module + ' START begins a new run at spawn')

    # Stage 2C has a visible solid wall occupying x=[0,32), providing a
    # real side-collision scenario. Hold LEFT after reaching its edge.
    wall = run_case(args, 'wall-2c', args.output / 'wall-save',
                    ['600:start:4', '2100:right:4', '2120:right:4', '2140:right:4', '2160:right:4',
                     '2250:start:4', '2450:left:100'], [2520, 2549], 2600)
    wall_offset = symbol(args.artifacts, 'stage2c')
    early = state(wall / 'ram_2520.bin', wall_offset)
    late = state(wall / 'ram_2549.bin', wall_offset)
    print('wall 2C', early, late, flush=True)
    check(early[0] == late[0] == 0, '2C left boundary stops LEFT at x=0')

    # Reach the upper boundary using a valid synthetic checkpoint in an
    # isolated copy of BRAM: the continuous 2C floor is y=66, so y=50 is
    # grounded and jumping reaches y=0.
    source_save = args.output / 'stage2c-save'
    ceiling_dir = args.output / 'ceiling-save'
    ceiling_dir.mkdir()
    ceiling_bram = bytearray((source_save / 'scd_U.brm').read_bytes())
    records = [(o, v) for o, v in save_records(ceiling_bram) if v == 2]
    check(bool(records), '2C ceiling fixture has a valid position-aware save')
    for offset, _ in records:
        ceiling_bram[offset + 4:offset + 10] = bytes((6, 1, 0x01, 0x90, 0x00, 0x32))
        ceiling_bram[offset + 12:offset + 14] = crc16_ccitt(
            ceiling_bram[offset:offset + 12]).to_bytes(2, 'big')
    (ceiling_dir / 'scd_U.brm').write_bytes(ceiling_bram)
    cart = source_save / '4Mbit_cart.brm'
    if cart.exists():
        shutil.copyfile(cart, ceiling_dir / cart.name)
    ceiling = run_case(args, 'ceiling-2c', ceiling_dir,
                       ['600:start:4', '2200:down:4', '2240:start:4', '2400:b:4'],
                       [2399, 2402, 2403, 2404, 2405, 2406, 2407, 2408, 2420], 2450)
    roof = [state(ceiling / ('ram_%04d.bin' % frame), wall_offset)
            for frame in (2399, 2402, 2403, 2404, 2405, 2406, 2407, 2408, 2420)]
    print('ceiling 2C', roof, flush=True)
    check(roof[0][:2] == (400, 50) and roof[0][3] == 1,
          '2C checkpoint starts grounded on the continuous floor')
    check(any(p[1] < 50 and p[2] < 0 for p in roof[1:]) and
          roof[-1][1] == 50 and roof[-1][3] == 1,
          '2C jump rises and lands on the continuous floor')

    # In 2A the first captured platform ends at x=255. Holding RIGHT across
    # its edge makes the character fall out of the visible window and respawn.
    fall = run_case(args, 'fall-2a', args.output / 'fall-save',
                    ['600:start:4', '2100:right:4', '2250:start:4', '2450:right:160'],
                    [2559, 2609], 2650)
    fall_offset = symbol(args.artifacts, 'stage2')
    edge = state(fall / 'ram_2559.bin', fall_offset)
    after_fall = state(fall / 'ram_2609.bin', fall_offset)
    print('fall 2A', edge, after_fall, flush=True)
    check(edge[0] > 200 and after_fall[0] > 256 and after_fall[0] > edge[0],
          '2A crosses the old one-screen edge without respawning')

    # DOWN + B performs the PCE slide: no jump, a lowered body and 3 px/frame
    # for 18 frames. The stage is entered with the same menu sequence as above.
    slide = run_case(args, 'slide-2a', args.output / 'slide-save',
                     ['600:start:4', '2100:right:4', '2250:start:4',
                      '2450:down:4', '2450:b:4'],
                     [2449, 2452, 2460, 2466, 2472], 2520)
    at_slide = lambda frame: state_slide(slide / ('ram_%04d.bin' % frame),
                                         fall_offset)
    before_slide = at_slide(2449)
    sliding = at_slide(2452)
    advanced = at_slide(2460)
    travelled = at_slide(2466)
    finished = at_slide(2472)
    print('slide 2A', before_slide, sliding, advanced, travelled, finished,
          flush=True)
    check(before_slide[3] == 1, 'slide fixture starts grounded')
    check(sliding[4] > 0 and sliding[1] == before_slide[1] and sliding[3] == 1,
          'DOWN + B starts a grounded slide instead of a jump')
    check(advanced[0] > sliding[0] + 15,
          'slide advances faster than the walk step')
    check(travelled[0] - before_slide[0] >= 40,
          'slide covers at least 40 pixels in 16 frames')
    check(finished[4] == 0 and finished[3] == 1,
          'slide ends grounded and control returns')

    # Save while airborne. A control run establishes the exact physics state
    # in the frame when START will be pressed; a second run verifies that the
    # checkpoint records that state, rather than the previous or landing frame.
    air_events = ['600:start:4', '2100:right:4', '2250:start:4', '2450:b:4']
    baseline = run_case(args, 'air-baseline', args.output / 'air-baseline-save',
                        air_events, [2453, 2454], 2460)
    expected_air = state(baseline / 'ram_2454.bin', fall_offset)
    check(expected_air[2] < 0 and expected_air[3] == 0, 'air checkpoint fixture is rising')
    air_save = args.output / 'air-save'
    run_case(args, 'air-checkpoint', air_save,
             air_events + ['2454:start:4'], [2453], 2550)
    data = (air_save / 'scd_U.brm').read_bytes()
    check(any(version == 2 and data[offset + 4] == 3 and data[offset + 5] & 1 and
              int.from_bytes(data[offset + 6:offset + 8], 'big') == expected_air[0] and
              int.from_bytes(data[offset + 8:offset + 10], 'big') == expected_air[1]
              for offset, version in save_records(data)),
          'START during jump records the exact current x/y')
    airborne = run_case(args, 'air-continue', air_save,
                        ['600:start:4', '2200:down:4', '2240:start:4'],
                        list(range(2260, 2321)), 2322)
    trajectory = [state(airborne / ('ram_%04d.bin' % frame), fall_offset)
                  for frame in range(2260, 2321)]
    exact = next((i for i, p in enumerate(trajectory)
                  if p[:2] == expected_air[:2] and p[2:] == (0, 0)), None)
    check(exact is not None, 'CONTINUE restores the exact airborne x/y with velocity reset')
    check(any(p[0] == expected_air[0] and p[1] > expected_air[1] for p in trajectory[exact + 1:])
          and any(p[0] == expected_air[0] and p[3] == 1 for p in trajectory[exact + 1:]),
          'gravity resumes and the character lands after an airborne CONTINUE')
    print('All stage movement, jump, collision and position checks passed.')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, struct.error) as exc:
        print('FAIL:', exc, file=sys.stderr)
        raise SystemExit(1)
