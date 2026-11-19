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
| STG2C (dungeon) | `states/.mc2` | `STAGE2C.MMD` | 4 | captured orange-brick dungeon BAT/VRAM/CRAM | 16x16 prototype patrol (not the retail enemy table) |
| STG2C boss | root `.mc3` background | `STG2BOSS.MMD` | 1 | blue corridor capture | captured blue-knight pair plus captured fireball tiles |

The normal flow is
`STAGE2 -> STAGE2A2 -> STAGE2B -> STAGE2C -> STG2BOSS -> STAGE3A -> STAGE2`.
Every room starts on screen 0 and the player crosses every packed screen
before the exit; the boss remains selectable from the title menu (save ID 20).

## What matches the PCE stage

* Backgrounds, palettes and actor frames are packed from the original PCE
  save states, not redrawn.
* The captured player has four frames (idle, two walk poses and sword) in
  STAGE2, STAGE2A2 and STAGE2B, and is reused in the boss arena.
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

## Honest differences and remaining gaps

* There is no recovered retail enemy/placement table. Enemy positions, patrol
  limits, HP and the exit gate are port gameplay.
* The captured BAT's right columns 32-63 are blank/HUD, so the second
  STAGE2A2/STAGE2B screen is another captured vertical window from the same
  state, not a contiguous horizontal extension of the retail room.
* STAGE2C still uses the 16x16 prototype player and patrol sprites. Its
  background is captured, but its actors are not the retail dungeon actors.
* The PCE HUD sits at the bottom of the screen. The port draws a fixed HUD
  (top row in STAGE2, in-map HP row in the room modules). This is a layout
  adaptation used by all captured-scene prototypes.
* Collision surfaces are authored approximations; the continuous phase-2
  floors are a port addition that lets the normal route visit all screens.
