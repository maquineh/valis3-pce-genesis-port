# Stage 2: PCE original vs the Mega CD port

There is no official Sega Genesis/Mega Drive release of Valis III. This
document compares the PC Engine CD Stage 2 material with the Mega CD
reconstruction in this repository. The port is assembled from the user's PCE
Mednafen save states; it is not a port of an existing Genesis level.

## Room-by-room comparison

| PCE block | PCE capture | Mega CD module | Screens | Background source | Enemy asset |
|-----------|-------------|----------------|---------|-------------------|-------------|
| STG2A opening (coast) | root `.mc0` | `STAGE2.MMD` | 4 | captured BAT/VRAM/CRAM, rows 32/40 | captured lance knight (from the seaside sprite table) |
| STG2A room 2 (seaside) | `states/.mc1` | `STAGE2A2.MMD` | 2 | captured BAT windows at rows 7 and 20 | four-frame captured lance knight |
| STG2B (forest) | root `.mc2` | `STAGE2B.MMD` | 2 | captured BAT windows at rows 0 and 8 | three-frame captured red-outlined figure |
| STG2C (dungeon) | `states/.mc2` | `STAGE2C.MMD` | 4 | captured orange-brick dungeon BAT/VRAM/CRAM | four-frame captured player and two-frame captured fire patrol |
| STG2C boss | root `.mc3` background | `STG2BOSS.MMD` | 1 | blue corridor capture | captured blue-knight pair plus captured fireball tiles |

The normal flow is
`STAGE2 -> STAGE2A2 -> STAGE2B -> STAGE2C -> STG2BOSS -> STAGE3A -> STAGE2`.
Every room starts on screen 0 and the player crosses every packed screen
before the exit; the boss remains selectable from the title menu (save ID 20).

## What matches the PCE stage

* Backgrounds, palettes and actor frames are packed from the original PCE
  save states, not redrawn.
* The captured player has four frames (idle, two walk poses and sword) in
  STAGE2, STAGE2A2, STAGE2B and STAGE2C, and is reused in the boss arena.
* STAGE2C uses the four player poses and two captured fire/animation frames
  from its own `.mc2` save state. Palette line 3 is the exact PCE sprite
  palette 5, and the captured fire uses line 2 with its two brightest colors
  added to unused slots.
* STAGE2A2 and STAGE2B use two different captured vertical windows; STAGE2 and
  STAGE2C use four windows. The screen switch happens at the 256-pixel
  boundary, like the PCE's 256-pixel viewport.
* All phase-2 rooms start the original coast recording (PCE track 40, disc
  track 24). The boss plays the original voice (track 23) followed by the
  original boss music (track 27).
* Jump, sword and hit effects are the original PCM samples packed into
  `city_sfx.bin` and uploaded to Sub-CPU PCM RAM.
* The captured boss pair and fireballs use the PCE shapes; the 16 HP bar and
  attack timing are port gameplay.

## Slide (new)

The PCE slide is available in every phase-2 room and in the boss arena:

* **Down + B** while grounded starts the slide (it does not jump).
* The slide lasts 18 frames and moves 3 pixels per frame (54 pixels), faster
  than the 2-pixel walk.
* The body is lowered for the whole slide, enemy contact is ignored, and each
  enemy takes one hit point per slide. The boss also takes one slide hit.
* Slide entry and slide damage use the original PCM jump/hit banks.
* After the slide the normal walk/jump/attack controls return.

Deterministic evidence:

```text
tools/test_stage_slide_integration.py
before  player x=128 hp=3  enemy hp=2 slide=0
sliding player x=152 hp=3  enemy hp=1 slide=10
after   player x=182 hp=3  enemy hp=1 slide=0
PASS: DOWN+B slide crosses the STAGE2A2 enemy with damage and no contact
```

`tools/test_stage_physics_integration.py` additionally checks that DOWN + B
does not jump, covers at least 40 pixels and ends grounded.

## STG2C captured actors

`tools/pack_stage2c_actors.py` extracts the dungeon actors from the same
`.mc2` state used for the background:

* four player poses at CDRAM descriptor lists `$865c`, `$8667`, `$8672` and
  `$868d` (idle, two strides and attack), packed into 64x48 frames;
* two fire patrol frames at `$89b8` and `$89bd`, packed into 48x64 frames;
* the original 8x8 HUD heart recoloured into the captured player palette.

The MD sprite palette line 3 is the exact PCE sprite palette 5. The dungeon
background keeps its exact colors on lines 0-2; the twelve background tiles
that used line 3 are remapped to their nearest line-0/1/2 colors (318 of the
196,608 captured background pixels, about 0.16%). Line 2 keeps two unused
slots for the fire's bright yellow and white; the remaining fire colors map to
the closest warm slots on line 2.

In-game evidence: `tools/test_stage2c_actors_integration.py` selects STAGE2C
from the title, reads the live player and enemy positions from work RAM, and
compares the screenshot against the packed frames:

```text
player 100 50 facing 1 camera 0 sprite 92 18
sprite pixels 539 matched 539 worst 17 colors 15
enemy 0 candidates [(221, 401, 0, 150, 2), (401, 401, 1, 151, 2)]
enemy 1 candidates [(221, 401, 0, 210, 2), (401, 401, 1, 211, 2)]
PASS: STAGE2C draws the captured PCE player frame in game
```

The two enemy candidates reflect the video buffer being one patrol step ahead
of the post-frame RAM; the adjacent draw position matches all 401 fire pixels
for both enemies. `tools/test_stage2c_palette.py` also regenerates the pack and
compares every tile, map, palette and actor byte with the committed assets.

## Honest differences and remaining gaps

* There is no recovered retail enemy/placement table. Enemy positions, patrol
  limits, HP and the exit gate are port gameplay.
* The captured BAT's right columns 32-63 are blank/HUD, so the second
  STAGE2A2/STAGE2B screen is another captured vertical window from the same
  state, not a contiguous horizontal extension of the retail room.
* The optional STAGE2CB and STAGE2CG one-screen menu scenes are outside the
  normal phase-2 route and still use the small placeholder actor; the dungeon
  in the normal route uses the captured frames.
* The fire uses two exact warm colors added to line 2; its dark outline shades
  are approximated by the nearest slots on that shared background line.
* The PCE HUD sits at the bottom of the screen. The port draws a fixed HUD
  (top row in STAGE2, in-map HP row in the room modules). This is a layout
  adaptation used by all captured-scene prototypes.
* Collision surfaces are authored approximations; the continuous phase-2
  floors are a port addition that lets the normal route visit all screens.
