# Native city continuation and boss

`STAGE1.MMD` now continues beyond the first recovered roof instead of exiting to
STG2A there. It loads the later roofs, then a fixed boss arena. STG2A opens only
after the boss loses all 16 hit points and its defeat effect finishes.

## Source and conversion

The source is the user's Japanese Genesis cartridge, run in Genesis Plus GX
1.7.6. These are native Genesis patterns and palette lines; no pixels were
redrawn. `tools/pack_city_late.py` streams columns from the closest live viewport
before the original game reuses its name-table ring. It retains the native 8x8
patterns, all four CRAM lines, the fixed HUD, composite SAT pieces and the floor
edge tile (source index 752). Sprite pattern blocks are padded to their hardware
width alignment. Yuko's attack and damage sequences are supplied separately by
the common combat bank.

The generated assets are:

| Pack | Source roof interval | Size | Tiles | Map |
|---|---|---:|---:|---:|
| `city_late.bin` | x=0..2039 | 40,076 bytes | 648 | 255x28 cells |
| `city_boss.bin` | x=1784..2039 | 26,374 bytes | 624 | 32x28 cells |

Both playable rooftop stretches use the same continuous foreground ring. The skyline scrolls one pixel for every four pixels of absolute camera motion, reaching -446 at the arena. The cloud phase continues across the encounter boundary.

The late pack retains the brown fire thrower, flying creature and sign. The boss
pack retains the purple cloaked boss's idle, airborne and attack silhouettes,
and the original projectile pieces. The later roofs keep the brown enemy's
CRAM; the arena loads the boss's purple CRAM. Both packs leave tiles 1022..1279
free for the common combat and dynamic HP bank. The active video mode is H32 (256x224).

## Capture provenance and replay

The packed source states are under these ignored build directories:

- `build/city-genesis`: original player and rooftop creature poses.
- `build/city-late5`: later rooftop traversal, sampled every eight frames.
- `build/city-late7`: grounded entrance and scripted camera advance.
- `build/city-boss`: dialogue advanced, followed by actual boss animation.

Capturing the roofs used temporary HP/lives replenishment and a Y-position clamp
in the emulated cartridge's work RAM. The clamp was removed at the entrance so
the retail ground trigger could run. These aids change capture traversal only;
the ROM and graphics data remain unchanged. They are not evidence that the port
can be completed using normal controls. `tools/capture_city_late.py` exposes the
aids explicitly and requires the caller's core, system directory, cartridge and
resume state. START advances the cartridge dialogue; it does not add dialogue
to this port.

To regenerate with these existing states:

```powershell
py -3 tools/pack_city_late.py
py -3 tools/test_city_late_assets.py
```

## Playable approximation and remaining differences

The integral roof map preserves horizontal continuity between the first and
later encounters. The arena keeps the skyline phase at global x=1784. The map's
recovered floor heights are native. The three stationary fire throwers use centers measured from the cartridge SAT. Other enemy placements, enemy HP,
patrol limits, fire intervals and damage boxes are authored gameplay. The boss
uses a 90-frame introduction, then repeats a 240-frame float/fire/dash pattern;
this is an approximation of the observed cartridge moves, not recovered retail
AI. The boss introduction uses an adapted encounter script. The earlier kidnapping and sword transformation use the native Genesis dialogue and sprite sequence. The
sign is a captured static composite. Enemy and boss state resets when the room
loads or a checkpoint is restored.

Yuko has 24 HP, matching the observed cartridge counter; ordinary enemy contact
removes two. B jumps; A or C attacks. The sword wave and charge behavior come from the common
combat code. The boss's remaining health appears as sixteen native HUD cells on
the right of the fourth window row. START saves a position with disjoint ranges:
late roofs at origin 2048, boss arena at origin 8192.

`tools/test_city_integration.py` drives all six rooms through controller input,
checks the hardware palettes, background scroll phase and continuous roof seam, defeats the two first rooftop enemies, traverses
the new roofs and waits for STG2A after the boss. It never patches port RAM. It
must run against matching symbols and an ISO built from the same sources.

## Final runtime verification

The full controller-only run against artifact `e85b3008043f43e18300a4c8e4700892`
completed all six city rooms in 16,000 emulated frames, defeated the boss and
opened STG2A. The boss reached zero HP at frame 15,600. The transition from the
first to later roofs moved Yuko zero screen pixels. Plane B matched the expected
global scroll phase in both later rooms, with no failed samples. Runtime inputs
read positions/timers but did not patch port RAM. The run includes normal deaths
and restarts; it is a reachability check, not a claim of exact retail behavior.
Logs, JSON traces, screenshots and `proof.png` are under
`build/city-finale/final-traversal/`; the stage after the boss is visible in
`frame_15999.png`.
