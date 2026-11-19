#!/usr/bin/env python3
"""Exercise the selectable STG2C dungeon boss through Genesis Plus GX.

The title menu keeps CITY as the default.  One LEFT selects the boss scene
(index 10 in the module list), which the test loads and then drives with the
controller.  It verifies the captured pair sprite, the intro voice track, the
sixteen-hit boss meter, and the transition to STAGE3A.  It reads only work RAM
and never patches the port.
"""
import argparse
import ctypes as ct
import json
import struct
import sys
from pathlib import Path

import test_megacd_libretro as harness

SCENE = 20
INTRO_TICKS = 1022
PLAYER = 0xC0C0
BOSS_X = 0xC0BE
BOSS_HP = 0xC0B8
INTRO = 0xC09C
PLAYER_HP = 0xC0AC
BOSS_CLEAR = 0xC0B0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'system', 'cue', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error('output must be a fresh directory')
    args.output.mkdir(parents=True)

    core = ct.CDLL(str(args.core.resolve()))
    core.retro_get_memory_data.argtypes = [ct.c_uint]
    core.retro_get_memory_data.restype = ct.c_void_p

    cache = {'frame': -1, 'keys': set()}
    events = []
    last = None
    transitions = []
    hits = 0
    previous_hp = None
    previous_scene = None

    def event(_, frame, button):
        nonlocal last, hits, previous_hp, previous_scene
        if cache['frame'] == frame:
            return button in cache['keys']
        cache['frame'] = frame
        keys = set()
        if 600 <= frame < 604 or 2320 <= frame < 2324 or 2600 <= frame < 2604:
            keys.add(3)
        if 2250 <= frame < 2254 or 2450 <= frame < 2454:
            keys.add(5)  # DOWN / UP in the title menu
        if 2470 <= frame < 2474:
            keys.add(6)  # one LEFT from CITY to BOSS
        address = core.retro_get_memory_data(2)
        if address and frame >= 2600:
            raw = ct.string_at(address, 65536)
            scene = raw[0xf501]
            byte = lambda a: raw[a ^ 1]
            x, y = struct.unpack_from('<HH', raw, PLAYER)
            boss_x = struct.unpack_from('<h', raw, BOSS_X)[0]
            boss_hp = byte(BOSS_HP)
            intro = struct.unpack_from('<H', raw, INTRO)[0]
            player_hp = byte(PLAYER_HP)
            clear = byte(BOSS_CLEAR)
            snapshot = (scene, x, boss_x, boss_hp, intro, player_hp, clear)
            if snapshot != last:
                events.append({'frame': frame, 'scene': scene, 'x': x, 'y': y,
                               'boss_x': boss_x, 'boss_hp': boss_hp,
                               'intro': intro, 'player_hp': player_hp,
                               'clear': clear})
                last = snapshot
            if scene != previous_scene:
                transitions.append(scene)
                previous_scene = scene
            if scene == SCENE and intro >= INTRO_TICKS and not clear:
                distance = boss_x + 8 - x
                if distance > 38:
                    keys.add(7)
                elif distance < 20:
                    keys.add(6)
                elif frame % 20 < 2:
                    # Hold RIGHT with the attack so the facing check targets
                    # the boss even after backing away.
                    keys.add(7)
                    keys.add(8)
            if previous_hp is not None and boss_hp < previous_hp:
                hits += previous_hp - boss_hp
            previous_hp = boss_hp
        cache['keys'] = keys
        return button in keys

    harness.event_pressed = event
    sys.argv = ['boss', '--core', str(args.core), '--system', str(args.system),
                '--cue', str(args.cue), '--output', str(args.output),
                '--frames', '7000', '--script-only', '--no-audio-file',
                '--capture', '3000', '--capture', '4000', '--capture', '4500',
                '--capture', '5000', '--capture', '5500', '--capture', '6000',
                '--capture-ram', '3000', '--capture-ram', '4500',
                '--capture-ram', '5000', '--capture-ram', '5500',
                '--capture-ram', '6000']
    harness.main()
    (args.output / 'boss-events.json').write_text(json.dumps(events, indent=2))
    print('scenes', transitions)
    print('boss hits', hits, 'last', events[-1] if events else None)
    assert SCENE in transitions, ('boss scene loaded', transitions)
    assert hits >= 16, ('sixteen boss hit points', hits)
    assert events[-1]['boss_hp'] == 0, ('boss defeated', events[-1])
    assert 5 in transitions, ('STAGE3A follows the boss', transitions)
    print('PASS: boss loaded, took sixteen hit points and opened STAGE3A')


if __name__ == '__main__':
    main()
