#!/usr/bin/env python3
"""Drive actual combat and all five exits through Genesis Plus GX.

Use the matching native-artifacts directory for the disc under test. Captures,
event logs and isolated backup RAM remain in --output for inspection. This
tests authored prototype behavior, not parity with the retail Genesis game.
Run progress and death separately in fresh processes/output directories.
"""
import argparse
import ctypes as ct
import json
import re
import struct
import sys
from pathlib import Path

import test_megacd_libretro as harness
from test_title_menu_integration import save_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'system', 'cue', 'artifacts', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=('progress', 'death'), required=True)
    parser.add_argument('--frames', type=int, default=6500)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error('output must be a fresh directory (isolated backup RAM)')
    args.output.mkdir(parents=True)
    core = ct.CDLL(str(args.core.resolve()))
    core.retro_get_memory_data.argtypes = [ct.c_uint]
    core.retro_get_memory_data.restype = ct.c_void_p
    modules = {3: 'stage2', 7: 'stage2a2', 4: 'stage2b',
               6: 'stage2c', 20: 'stg2boss', 5: 'stage3a'}
    symbols = {}
    for scene, module in modules.items():
        text = (args.artifacts / 'build' / (module + '.mmd.elf.sym')).read_text()
        symbols[scene] = {}
        names = (('stage_player', 'boss_hp', 'boss_x', 'intro_tick',
                  'player_hp', 'boss_clear') if scene == 20 else
                 ('stage_player', 'stage_combat', 'stage_enemies'))
        for name in names:
            match = re.search(r'^([0-9a-fA-F]+)\s+[bB]\s+' + name + r'\s*$', text, re.M)
            if not match or not 0xff0000 <= int(match[1], 16) < 0x1000000:
                raise ValueError('missing/invalid work RAM symbol: ' + name)
            symbols[scene][name] = int(match[1], 16) & 65535
    exits = {3: 992, 7: 488, 4: 488, 6: 992, 20: 0, 5: 496}
    cache = {'frame': -1, 'buttons': set(), 'last': None}
    logs, sequence = [], []
    respawn = False

    def event(events, frame, button):
        nonlocal respawn
        if cache['frame'] == frame:
            return button in cache['buttons']
        cache['frame'] = frame
        keys = set()
        if 600 <= frame < 604 or 2250 <= frame < 2254:
            keys.add(3)
        if 2100 <= frame < 2104: keys.add(7)  # Select STG2A after CITY.
        address = core.retro_get_memory_data(2)
        if address and frame >= 2350:
            raw = ct.string_at(address, 65536)
            scene = raw[0xf501]
            if scene == 20:
                s = symbols[20]
                x, y, vy, ground = struct.unpack_from('<HHhH', raw, s['stage_player'])
                byte = lambda a: raw[a ^ 1]
                boss_hp = byte(s['boss_hp'])
                boss_x = struct.unpack_from('<h', raw, s['boss_x'])[0]
                intro = struct.unpack_from('<H', raw, s['intro_tick'])[0]
                player_hp = byte(s['player_hp'])
                clear = byte(s['boss_clear'])
                snap = (scene, x, boss_hp, player_hp, clear)
                if snap != cache['last']:
                    logs.append({'frame': frame, 'scene': scene,
                                 'player': [x, y, player_hp, clear],
                                 'enemies': [], 'boss_hp': boss_hp,
                                 'boss_x': boss_x})
                    cache['last'] = snap
                if not sequence or sequence[-1] != scene:
                    sequence.append(scene)
                if args.mode == 'progress' and not clear and intro >= 1022:
                    distance = boss_x + 8 - x
                    if distance > 38:
                        keys.add(7)
                    elif distance < 20:
                        keys.add(6)
                    elif frame % 20 < 2:
                        keys.add(7)
                        keys.add(8)
            elif scene in symbols:
                s = symbols[scene]
                x, y, vy, ground = struct.unpack_from('<HHhH', raw, s['stage_player'])
                byte = lambda a: raw[a ^ 1]
                hp, dead = byte(s['stage_combat']), byte(s['stage_combat'] + 5)
                enemies = []
                for index in range(2):
                    a = s['stage_enemies'] + 12 * index
                    ex, ey = struct.unpack_from('<hh', raw, a)
                    enemies.append((ex, ey, byte(a + 8), byte(a + 9)))
                snap = (scene, hp, dead, tuple((e[2], e[3]) for e in enemies))
                if snap != cache['last']:
                    if cache['last'] and cache['last'][2] and not dead and hp == 3:
                        respawn = True
                    logs.append({'frame': frame, 'scene': scene,
                                 'player': [x, y, hp, dead], 'enemies': enemies})
                    cache['last'] = snap
                if not sequence or sequence[-1] != scene:
                    sequence.append(scene)
                if args.mode == 'death':
                    if not respawn:
                        if x < 124:
                            keys.add(7)
                        elif x > 128:
                            keys.add(6)
                elif sequence != [3, 7, 4, 6, 20, 5, 3]:
                    live = [e for e in enemies if e[3]]
                    if live:
                        enemy = min(live, key=lambda e: abs(e[0] - x))
                        target = enemy[0] - 24
                        if x < target - 4:
                            keys.add(7)
                        elif x > target + 4:
                            keys.add(6)
                        elif frame % 20 < 2:
                            keys.add(8)
                    elif x < exits[scene]:
                        keys.add(7)
        cache['buttons'] = keys
        return button in keys

    harness.event_pressed = event
    sys.argv = ['combat-review', '--core', str(args.core), '--system', str(args.system),
                '--cue', str(args.cue), '--output', str(args.output),
                '--frames', str(args.frames), '--script-only', '--no-audio-file']
    for frame in range(2399, args.frames, 150):
        sys.argv += ['--capture', str(frame), '--capture-ram', str(frame)]
    try:
        harness.main()
    finally:
        (args.output / 'events.json').write_text(json.dumps(logs, indent=2))
        (args.output / 'sequence.json').write_text(json.dumps(sequence))
    if args.mode == 'progress':
        assert sequence == [3, 7, 4, 6, 20, 5, 3], \
            ('six transitions including the boss', sequence)
        for scene in modules:
            assert any(e['scene'] == scene and all(not n[3] for n in e['enemies'])
                       for e in logs), ('enemies defeated', scene)
        assert any(e['scene'] == 20 and e.get('boss_hp') == 0 for e in logs), \
            'dungeon boss defeated'
        for scene, name in ((3, 'stage2_state'), (7, 'stage2a2_state'),
                            (4, 'stage2b_state'), (6, 'stage2c_state')):
            meta = json.loads(Path('game/res/gfx/%s.json' % name).read_text())
            assert meta.get('screens', 0) >= 2, (name, 'multi-screen pack', meta)
        for scene, screens in ((3, 4), (7, 2), (4, 2), (6, 4)):
            xs = [e['player'][0] for e in logs if e['scene'] == scene]
            assert xs and max(xs) >= (screens - 1) * 256, \
                ('scene', scene, 'visited all packed screens', max(xs) if xs else None)
        bram = (args.output / 'scd_U.brm').read_bytes()
        records = [offset for offset, version in save_records(bram) if version == 2]
        assert records, 'valid BRAM checkpoint CRC'
        assert any(bram[o + 4] == 3 and bram[o + 5] & 1 and
                   bram[o + 6:o + 10] == b'\x00\x20\x00\xa0'
                   for o in records), 'final transition saved scene 2 spawn to BRAM'
        print('PASS: visited every packed phase-2 screen, defeated the dungeon boss '
              'and completed six transitions with a valid BRAM CRC')
    else:
        assert any(e['player'][2:] == [0, 1] for e in logs), 'lethal damage/game-over state'
        assert respawn, 'automatic respawn restores three HP'
        died_at = next(e['frame'] for e in logs if e['player'][3])
        assert any(e['player'] == [32, 160, 3, 0] and e['frame'] > died_at
                   for e in logs), 'respawn restores stage spawn'
        print('PASS: enemy contact causes lethal damage and automatic respawn restores three HP')


if __name__ == '__main__':
    main()
