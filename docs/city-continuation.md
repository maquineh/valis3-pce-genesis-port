# Native city continuation and boss

`STAGE1.MMD` now continues beyond the first recovered roof instead of exiting to
STG2A there. It loads the later roofs, then a fixed boss arena. After the boss
loses all 16 hit points and the defeat effect finishes, the rescue leads to STG2A.

## PC Engine story on the full disc

New Game on CITY plays five prologue chapters, then the scene of Cham leaving
for the human world. At the end of the Mega Drive city, the encounter recording
plays once while the fighters face each other. A retry or CONTINUE in the arena
goes straight to the fight. Winning checkpoints the STG2A spawn, plays the
conversation between Yuko and Cham, and opens the playable coast. A fresh START
press skips the opening or rescue. CONTINUE after the victory checkpoint reopens
the coast.

| Passage | Japanese PCE track | Full Mega CD CUE track |
|---|---:|---:|
| Prologue | 7, 9, 11, 13, 15 | 6–10 |
| Cham's opening | 17 | 11 |
| Playable city | 38 | 22 |
| Boss conversation | 39 | 23 |
| Boss fight | 43 | 27 |
| Rescue | 19 | 12 |
| STG2A coast | 40 | 24 |

The PCE drive requested sector 122668 for the arrival dialogue, 135024 for
combat, 47877 for the rescue and 123946 for the coast. The Mega CD plays the
original stereo tracks. The arena uses the port's three adapted text pages.

The player samples every six PCE frames (about 10 fps). Its 256×224 picture
uses the original pixels from rows 11–234 of the 256×243 raster. Each 8×8
cell uses one of four MD palette lines. Three prologue chapters use nearest
colours on some cells. Both Cham movies fit the available lines after
conversion to the MD colour space. Larger chapters preload their remaining
tile and map updates in Sub CPU program RAM so the drive can play dialogue
throughout the chapter.

To regenerate, run `tools/capture_pce_story.py` for `prologue`, `opening`
and `rescue` with the Japanese CUE, Beetle PCE Fast and its System Card
directory. Each run prints the matching `tools/pack_pce_story.py` commands.
Packing requires NumPy and python-lz4. The rescue checkpoint comes from
the original game after the boss fell. Emulator assists kept Yuko alive,
helped her cross the roofs and positioned her to attack during source capture.
The rescue itself was recaptured with neutral input. All 2,829 sampled
rasters reproduced from the supplied checkpoints.

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
waits 90 frames after the voiced entrance, then repeats a 240-frame float/fire/dash pattern;
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

## Earlier city verification

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

## First-act playthrough

Genesis Plus GX played all six opening chapters and all six city rooms using
controller input. The boss reached zero HP by emulated frame 30,880. The
rescue started loading at 31,017 and the playable coast was visible by
35,650. Stereo captures from the encounter matched PCE track 39 near 6.9 s
and 13.9 s. Rescue captures matched track 19 near 6.7 s and 40.1 s. The coast
matched track 40. Local frames and audio are under `build/pce-story/route-audio/`.
