# Stage migration status

There are ten `STG` blocks on PCE track 2. Ten experimental scene modules
use BAT/VRAM/CRAM captured from six of those blocks in Mednafen save states.
They display captured background windows with horizontal movement, jumping, and
manually approximated collision surfaces. STG2A and STG2B use the captured player;
some other scenes still use the small placeholder sprite. The earlier scene prototypes also have two authored patrol enemies each, basic attacks, contact
damage, three live heart indicators, and an experimental progression loop.
Enemy placement and movement are prototypes. The flying disc silhouette is
new placeholder art inspired by Genesis enemy captures, not an original game
sprite. HP resets to three when a scene module loads. Enemy positions, behavior,
combat values, exits, and collision surfaces are prototypes, not recovered
original data. The main progression loop follows the five-scene prototype; it
does not claim to match the Genesis or PC Engine story order. Captured windows
can overlap; falling outside an approximated surface returns the player to
the scene spawn.

Captured SAT entries include multi-cell sprites from gameplay, HUD and enemies.
`tools/render_pce_state.py` composites them over the saved BAT and can write a
labeled sprite atlas, so future sprite extraction can be checked in scene
context. The coast and forest use four player frames from their respective CDRAM
frame descriptors and VRAM patterns.

`tools/capture_runtime_state.py STATE.mcX OUTPUT.png` resumes a gameplay save
state in the local PCE emulator, advances with RIGHT, and renders the live
VRAM and SAT table. It also saves raw VRAM, CRAM, SAT and a JSON report beside
the image, without reading disc sectors. It restores the save state's 2 KiB
`SaveRAM` section as well. A STG2C trial confirms that movement updates the
live SAT, but did not expose a new BAT window. After 3,267,724 CPU steps the
emulator reaches `$2031` in work RAM; the preceding `RTS` at `$9BD2` returns to
`$1EC3` with `MPR0=$FF`, so `$6B` is a symptom of invalid control flow through
the I/O page rather than a missing HuC6280 instruction. Four STG blocks
(STG3B, STG4B, STG4C and STG5A) still need actual gameplay captures or
a working stage loader.

The newer `--real-bios-vsync` path uses the approximate frame clock in
`tools/pce_timing.py`. Resuming the root STG2C corridor state for 2.7M steps
with either RIGHT or neutral delivered nine VBlank IRQs, but both runs
rewrote all 4,096 BAT words and 30,720 VRAM words; the rendered result is blue
stripes, not a usable stage view. RIGHT and neutral differ by only two VRAM
bytes and two SAT bytes. This is not evidence of player movement or a
new BAT window, so it has not been integrated as a scene.

The unshimmed New Game trace now uses the complete `ValisDisc` TOC and runs
beyond the startup overlay into the executable track-20 `ACT0` visual module.
It reads LBA 4416–4427, track-2 data at LBA 4740–4751, 4752–4771 and
4770–4801, and track-20 data at LBA 52450–52473, 52478–52493 and
52494–52513, then starts CD-DA track 8. In the extended run, the CPU advances
through 1,127 VBlank interrupts and stops at `$20D8` on opcode `$0B`, after a
VBlank callback at `$4D3A` in the wrong MPR2 bank executes a `JSR $0000` at
`$4D41`. No `STG` block is read. This advances the boot investigation but
does not change the missing-stage list.

The original capture sets are:

* the **first set** sits in the repository root (`Valis III (Japan).…mc0` …
  `.mc4`) and produced the STAGE2 / STAGE2B modules and the original STAGE3A
  capture; its root `.mc3` is a separate STG2C corridor capture;
* the **second set** (re-saved by the user) sits in `states/` and produced
  STAGE2C (the dungeon) and STAGE2A2 (the seaside room).  Note that the file
  names collide with the first set but the contents differ: the old `.mc2` is
  STG2B, the new `.mc2` is STG2C.

`states/stg3a_additional.mc4` preserves a later Mednafen capture found locally.
Its BAT supplies the current two-screen STAGE3A background: row 32, columns
0-63, with the captured colors repacked exactly into Mega Drive palette lines.
It is still a prototype scene with authored collision and enemy behavior. It
does not supply any of the five remaining uncaptured STG blocks.

The root `Valis III (Japan).…mc9` save state is STG4A (sequence byte `06`,
track-2 sector 544). Its CDRAM has the `STG4A` header at offset `0xA000`; with
MPR5=`$85`, that bank is visible at logical `$A000-$BFFF`. The header and next
`0x264` bytes match the disc block exactly, then runtime memory diverges at
block offset `0x464`. Its BAT contains a cemetery background in rows 6-31,
columns 0-33, using palettes 1-4. The saved BG scroll `(39,244)` points into
mostly empty BAT rows, so the normal viewport render is mostly black with the
HUD; the full BAT crop shows the captured terrain. Raw memory and extracted
background tiles are in `build/state_mc9/`, with previews in `build/gfx/`.
This capture now supplies the optional `STAGE4A.MMD` scene. Its palette is
recolored toward a generated retro-art concept inspired by Pyron; the tiles and
map retain their captured shapes. Collision and enemy behavior are prototypes. The player frame comes from the STG4A capture; the enemy frame comes from another PCE capture, with a shared reduced palette.

The root `Valis III (Japan).…mc3` capture is also STG2C. Its BAT row 34,
columns 32-63 gives a clean blue-and-gold corridor window, now packed into the
optional one-screen `STAGE2CB.MMD` scene. Its floor and enemy behavior remain
prototypes.

The second STG2C capture (`.mc3`) contains a landscape as well as the HUD.
At scroll 295,500, its single 64x64 BAT shows sky, mountains, forest and water.
The wrapped crop at column 32, row 62 avoids the HUD and is packed into the
single-screen `STAGE2CG.MMD` optional scene. Empty map bands remain, so it is
an experimental snapshot and not a complete room.
The capture is packed with:

```
py -3 tools/pack_state_window.py "states/Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc3" stage2c_green_state 1032 62 --reserve-line3 8,9,15 --pack-all-palettes
```

| PCE block | sector | save state | Mega CD module | status |
|-----------|--------|------------|----------------|--------|
| STG1A | 304 | `states/…stg1a.mc1` | `STAGE1A.MMD` | two captured windows with the retail palette |
| STG2A (room 1) | 344 | root `.mc0` | `STAGE2.MMD` (9084 B) | scene prototype |
| STG2A (room 2, seaside) | 344 | `states/…mc1` | `STAGE2A2.MMD` | coastal lance encounter |
| STG2B | 384 | root `.mc2` | `STAGE2B.MMD` | forest encounter |
| STG2C (dungeon) | 424 | `states/…mc2` | `STAGE2C.MMD` | scene prototype |
| STG2C (corridor) | 424 | root `.mc3` | `STAGE2CB.MMD` | one-screen corridor snapshot |
| STG2C (green room) | 424 | `states/…mc3` | `STAGE2CG.MMD` | one-screen landscape prototype |
| STG3A | 464 | `states/stg3a_additional.mc4` | `STAGE3A.MMD` | two-screen scene prototype |
| STG3B | 504 | — | — | pending state |
| STG4A | 544 | root `.mc9` | `STAGE4A.MMD` | one-screen prototype; emulator checked |
| STG4B | 584 | — | — | pending state |
| STG4C | 624 | — | — | pending state |
| STG5A | 664 | — | — | pending state |

Six of the ten blocks have data represented in ten scene prototypes.
The four uncaptured blocks (STG3B, STG4B, STG4C and STG5A) still need gameplay
save states. A capture alone does not make a complete stage.

## Adding a new stage from a save state

1. Put the Mednafen `.mcX` state in the repository root (or in `states/`).
2. Extract it:

```
python3 tools/extract_state.py "STATE.mcX" build/state_NAME
```

   `summary.json` shows the `STG` block found in CDRAM, the BAT scroll and the
   palette set.
3. Pack BAT windows from the state — arguments give the top row of each
   32x24 crop:

```
python3 tools/pack_state_window.py "STATE.mcX" stageN_state ROW0 ROW1
```

   Row and column coordinates wrap around the 64x64 BAT. Prefix the first row
   with `1000+COL0` to choose the starting column. For STG2B the forest is in
   the upper-left, so `0 8` was used. For STG2A the stage is the lower half,
   so `32 40` was used. For the second capture
   set `0 8 16 24` was used; these 24-row crops overlap, and their order is
   not verified as a sequence of consecutive screens. Use `--columns C0,C1`
   to choose a separate BAT column for each packed screen.
4. Add `game/src/stageN_state.c` + `stageN_state_res.s` (copy the Stage 3A
   files and change the resource prefix, `STAGE_SCREENS`, `STAGE_TILES` and
   `PLAYER_TILE` to the packer's JSON values).
5. Register the module in `shared.h` / `spx.c` and add the makefile target.
6. Rebuild: `tools/build_megacd.ps1` -> `tools/mcd_make_disc.py` ->
   `tools/verify_all.py`.

Note: `tools/verify_all.py` cross-checks `STAGE_SCREENS` / `STAGE_TILES` in
the module against the packed JSON, so a wrong tile count fails the build
instead of shipping broken art.

## Title screen selector

Use UP/DOWN to choose START or CONTINUE. On START, LEFT/RIGHT selects one of
the experimental scenes; START or A/B/C confirms. CONTINUE opens the most
recently saved scene and position. The save is kept in the Mega CD backup
RAM. Without a valid save the
menu shows `NO SAVE`; if saving fails it shows `SAVE ERR` and a second
confirmation starts the scene without saving. The program never formats BRAM
or overwrites an unrecognized save file.

While in a scene, use LEFT/RIGHT to move, B to jump, A/C to attack, and START
to save the current world-space position and return to the title. Defeat both
prototype enemies and reach the scene exit to advance automatically. The
sequence remains STAGE2 → STAGE2A2 → STAGE2B → STAGE2C → STAGE3A → STAGE2; each
transition checkpoints the next scene's spawn, so CONTINUE resumes there.
STAGE2CG and STAGE2CB are optional sixth and seventh menu options outside that
loop; both exits lead to STAGE3A.
This control mapping adapts the existing port: the Genesis manual describes
B as attack and A as character change, and those original character and
weapon mechanics are not implemented here. After restart, CONTINUE restores
the saved position with velocity reset. An older scene-only save opens at the
scene spawn and is upgraded when a position is saved. The two alternating
project-owned BRAM slots use a checksum and preserve the previous valid save
if an update cannot be completed.

| Selection | Module | Scene |
|-----------|--------|-------|
| 1 | `STAGE2.MMD` | STG2A opening (sea and cliff) |
| 2 | `STAGE2A2.MMD` | STG2A room 2 (sea cliffs and tower) |
| 3 | `STAGE2B.MMD` | STG2B forest |
| 4 | `STAGE2C.MMD` | STG2C blue brick dungeon |
| 5 | `STAGE3A.MMD` | STG3A ice castle |
| 6 | `STAGE2CG.MMD` | STG2C green landscape (single captured window) |
| 7 | `STAGE2CB.MMD` | STG2C blue-and-gold corridor (single captured window) |
| 8 | `STAGE4A.MMD` | Local graveyard with combat (save ID 10) |
| 9 | `STAGE1A.MMD` | Imported shrine (save ID 11) |
| 10 | `STAGE4AX.MMD` | Alternate two-window graveyard (save ID 12) |

The green room and the corridor retain save IDs 8 and 9. The new entries support horizontal movement and START/CONTINUE position checkpoints. The shrine uses `--pal build/stg_extract/STG1A_pal.bin:0x64` in place of the faded capture palette. See [the disc inventory](iso-stage-inventory.md) for the source blocks.

## STG2A opening art

`tools/pack_stage_state.py` uses the root `.mc0` and the seaside `states/…mc1`. The first state's embedded 288×232 Mednafen preview identifies the raster split: in the 256×224 view, HUD rows 17–21 precede landscape row 39. The port draws the HUD on the fixed plane and scrolls the landscape on the other. The HP segments track combat health; the remaining HUD indicators depict the captured frame.

The player uses VRAM and four frame descriptors from the opening capture, with two walking poses and a sword pose. The two prototype patrols use a knight assembled from the seaside state's sprite table. Their encounter begins when the player moves right. The platform layout beyond the captured window and the fight are adaptations. Save ID 3 and existing world coordinates are preserved.

## STG4A emulator check (2026-11-15)

With Genesis Plus GX and the US Sega CD BIOS, the rebuilt `build/valis3.iso`
(SHA-256 `bcd0417e386f5ed09115258fbefb37150b21fd156b97ae6a4b33c6fb51fd7c19`)
loaded selection 8. At spawn the player was `(32,128)`, rose to `y=109` after
a jump and landed at `y=128`. Moving left reached `(16,128)` and returning
to the title then choosing CONTINUE restored that position in the same session
and after a core restart. An automated combat run defeated both prototype
enemies and transitioned from scene 10 to scene 5 (STG3A). Screenshots and
RAM captures are under `build/stg4a_runtime_fixed/`, with combat events under
`build/stg4a_combat_check/`.

The initial run revealed that using tile zero to clear planes could show stage
pixels, because tile zero is part of this captured tileset. STG4A now loads a
separate blank tile for clearing, and the attack sprite uses palette line 3
where its colors are reserved. The scene still covers only one captured window;
actor animation, collision, enemy behavior and exit remain prototypes. Hardware has not
been checked.

The STG4A scene now uses original captured PCE player and knight frames; provenance, color reduction, static animation, and emulator checks are recorded in `game/res/gfx/stage4a_capture_notes.md`.

The STG4A prototype now uses the skull frames and 5/5 update sequence from its own `.mc9` tables in place of the earlier STG3A knight. Its palette and gameplay remain provisional; see `game/res/gfx/stage4a_capture_notes.md`.

STG4A now includes a skull and a skull-column using frames and durations from its `.mc9` tables. Palette assignment and object behaviors remain approximations; see `game/res/gfx/stage4a_capture_notes.md`.

## Coast and forest after the opening

Run `py -3 tools/pack_phase2_rooms.py` to extract the two 256x224 playfields.
Both saves display BAT rows 49�53 for the HUD and rows 7�29 underneath. The
coast uses the lance wielder from the seaside save, with four frames. The
forest uses the red-outlined figure from the forest save, with three frames.
Each room preserves the two actor palettes and fits the remaining background
colors into the four shared Mega Drive palette lines. The patrol, damage and
exit rules are port gameplay. Defeating the resident enemy unlocks the right
edge. The coast leads to the forest, which leads to the blue dungeon.

## Genesis city on START

CITY is the default selection. Save ID 2 stores the city in STAGE1.MMD. The
existing numbered selectors retain their IDs. The route follows the Japanese
cartridge through the residential street, rooftop encounter, descent to the
sword and first rooftop fight. At the right end of the recovered rooftop
segment the port continues to STG2A. The rooftop edge heights are read from
the cartridge foreground map. B jumps and A or C swings the sword after the
transformation. START saves the current world position and opens the title.

To recreate the artwork, use `tools/capture_genesis_city.py` with the Japanese
ROM and the Genesis Plus GX core, then pass its output directory to
`tools/pack_genesis_city.py`. The packer keeps both planes, the fixed HUD,
the four CRAM lines and the linked sprite pieces for the player, the encounter
and combat. The port controls the encounter timing, leaper movement and damage.
