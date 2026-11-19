# Mega CD build and validation

## City audio

The Japanese PC Engine CD requests sectors 112021 through 122667 for the
street, the abduction, the fall and the first rooftops. This is original track
38, which maps to track 22 in the full Mega CD CUE. The PC Engine loops this
track. During Cham's abduction its text boxes advance over the same music;
the ADPCM playback flag stays clear. A replay with 300 frames between button
presses allowed the dialogue to remain on screen.

The port adds one voiced line to Cham's opening box. It adapts her later
post-rescue explanation of needing the sword's power, using the Japanese
performance from original track 19 at 7.98–11.60 s. The RF5C164 plays the
11,025 Hz mono sample while the drive continues the city music. Resuming later
in the abduction skips this opening line.

`tools/test_city_cdda.py` boots the published CUE in Genesis Plus GX. It
samples the stereo mix in the street and matches it against the extracted
track at 48, 83 and 190 seconds of emulation. The last sample exercises the
loop. Put all CUE-referenced files together: this core resolves a relative
audio filename using the previous file's directory.

## 2026-11-17 — integration of 2f80903

The Windows build produced `dist/valis3_mcd.iso` with SHA-256
`5b2c2258ca9222b608d8bfded227745f319b563cbeb1a639c520daee12050b8e`.
Genesis Plus GX opened the distributed CUE and all ten menu entries.
`test_scene_id_upgrade.py` created a checkpoint in each of the eight scenes on
the previous local build and reopened each on the integrated disc with the
same scene and coordinates. Both added scenes also saved and resumed. A
separate test opened a pre-existing v1 save for scene 4 and wrote a v2
checkpoint to the other BRAM slot while preserving the original record.
The title, movement, progression and local graveyard combat tests passed.
The disc verifier found all 55 tracks and reported zero failures.

## 2026-11-15

The data ISO was rebuilt on Windows using the native workflow in the README.
The CUE references that image and 54 extracted CD-DA tracks. That ISO
has SHA-256 `1559DF1D24AA4E147C9384F61DC8D5FB5ACD7EC82D6683885020EC383213D74E`.

On 2026-11-15, the native build recompiled the current source into all ten
MMD modules and the SPX boot module, then regenerated the data ISO and
the final CUE/ISO/manifest in `dist/`. The 54 audio WAVs matched their source
hashes and were reused. This refresh was a compile/package run; the emulator
was not started again afterward.

Using the user's US Sega CD BIOS with Genesis Plus GX, a headless libretro
test reached the game, displayed the original logo and interactive menu, played
the title track and stopped it when a scene was selected. The tests verified
movement, jumping, landing, and saving/restoring the actual x/y position in
all five scenes, including after restarting the core. They also verified a
visible wall, falling and respawning, a checkpoint taken in mid-jump (with
velocity reset and gravity resuming), recovery from a corrupt latest slot,
rejection of two corrupt slots, and migration of a real v1 scene-only save.
`tools/test_stage_physics_integration.py` and
`tools/test_title_menu_integration.py` repeat these tests with isolated save
directories, given a core, BIOS directory and CUE. Screenshots and logs are
under `build/test-physics/`. These tests do not validate physical hardware.

This test exposed and drove fixes to the main/sub CPU acknowledgement,
Word RAM ownership for CD audio, duplicate controller reads, Word RAM DMA,
plane-fill dimensions and initial stage drawing. The player now shares
three unused colors in line 3 with the background; see `palette-sharing.md`.

The title combines logo and menu from two original captures. CONTINUE restores
the position saved by returning to the title; velocity is reset. Older
scene-only saves start at the scene spawn. The stage scenes use partial,
sometimes overlapping captures and placeholder sprites. Collision geometry
is manually approximated. Prototype enemies, attacks, damage, respawn and
scene progression are implemented; the local Genesis Plus GX progress/death
runs in build/final-review-6d226369-progress.log and
build/final-review-6d226369-death.log report PASS. They do not establish
parity with the original game's behavior or validate physical hardware.
Those emulator runs predate the recaptured Stage 3A assets and the STG2C
green-room and corridor menu options. The current binaries compile and package
successfully, but those updated scenes have not yet been run in the emulator.
`title-capture.md` records a separately captured original PC Engine menu.

Earlier testing with the built-in BIOS HLE of EmilDrive 1.6 failed during
startup; the official Megadev Hello World example also failed there. The
installed Mednafen 1.32.1 can capture the original PC Engine game, but its own
documentation says its Sega CD emulation is nonfunctional. The successful
Mega CD test above used the real user-provided BIOS and Genesis Plus GX.

The Docker Desktop Linux engine could not start because WSL requests hung and
the WSL service remained in `StopPending`. Restarting Windows is required to
retry recovery; no Docker images or WSL distributions were reset or removed.

## 2026-11-18 - phase 2 assets, effects and dungeon boss

The native Windows build produced `build/valis3.iso` with SHA-256
`854c8a58ad198d773e0c42f218e1418d41819ab90cae2b709da4234991b4fb8b`
(3,063,808 bytes).  The isolated tests used `build/disc-test.cue`, which
references the same ISO and the 54 extracted CD-DA WAVs.

- `tools/test_city_integration.py` completed rooms 0-6, defeated both
  rooftop enemies, cleared the gap and passed the six hardware-palette checks
  after the original HUD icons replaced the generated item motifs.
- `tools/test_stage_combat_integration.py` completed the full phase-2 chain
  (scenes 3, 7, 4, 6, 20, 5, 3), visited every packed screen of the coast,
  seaside, forest and dungeon, defeated every prototype enemy and the dungeon
  boss, and verified the final BRAM checkpoint.
- `tools/test_stage2_boss_integration.py` selected scene 20 from the title,
  waited out the voiced intro, landed sixteen sword hits and verified the
  transition to STAGE3A. Output: `build/verify-boss-final/`.
- `tools/test_city_sfx.py` serialized the running emulator after a jump and
  an attack and found the exact packed jump and sword sample bytes in Mega CD
  PCM RAM. This proves the Sub CPU loaded the effects; the audio mixing test
  is not used because CD-DA and PCM share the captured stereo output.
- `tools/test_city_voice.py` found the extracted Cham voice bank in PCM RAM
  during the meeting scene. `tools/test_city_cdda.py` matched the city music
  at 48, 83 and 190 seconds (scores 0.980/0.984/0.984) and found Cham's track
  19 line at 56.17 s of emulation.
- `tools/test_title_menu_integration.py` passes title audio, menu selection,
  CONTINUE restore, a reload, the failed-save path and the final CITY
  selection. The comparison windows now exclude the story prologue and the
  emulator's 16-byte BRAM header normalization.
- `tools/test_stage_physics_integration.py` passes motion, jump, landing,
  save, CONTINUE and the post-reboot background anchor. The background
  windows exclude the dynamic HP HUD and the actor sprites.

These are emulator checks with the user's BIOS; they do not validate physical
hardware.

## 2026-11-19 - complete stage 2 assets and slide

The native rebuild produced `build/valis3.iso` and `dist/valis3_mcd.iso` with
SHA-256 `12b8dfc575ea4425394dc6fe84bf1b568545b02abdef207796f0f7debab1bf8b`
(3,076,096 bytes). The ISO carries the DOWN+B slide in the shared stage physics
and the captured STG2C player/fire actor frames.

- `tools/test_stage_combat_integration.py` completed
  `STAGE2 -> STAGE2A2 -> STAGE2B -> STAGE2C -> STG2BOSS -> STAGE3A -> STAGE2`,
  visited every packed screen (STAGE2/2C x=948/958, STAGE2A2/2B x=406/488),
  defeated the per-screen enemies and the dungeon boss, and passed the BRAM
  checkpoint check.
- `tools/test_stage_slide_integration.py` entered STAGE2A2, walked to the
  captured lance enemy and slid through it. The enemy lost one HP
  (2 -> 1), the player kept all three HP and the slide timer returned to zero:

```text
before  player x=128 hp=3  enemy hp=2 slide=0
sliding player x=152 hp=3  enemy hp=1 slide=10
after   player x=182 hp=3  enemy hp=1 slide=0
PASS: DOWN+B slide crosses the STAGE2A2 enemy with damage and no contact
```

- `tools/test_stage_physics_integration.py` verified that DOWN + B starts a
  grounded slide instead of a jump, covers at least 40 pixels and ends
  grounded. `tools/test_stage2_boss_integration.py` repeated its sixteen-hit
  defeat and STAGE3A transition.
- `tools/test_stage2c_palette.py` regenerated the STG2C pack from the `.mc2`
  state and matched every committed tile, map, palette and actor byte. It
  verified the exact PCE player palette on line 3, the two added fire colors
  on line 2, the captured four player frames and two fire frames, and the
  remapped background tiles.
- `tools/test_stage2c_actors_integration.py` selected STAGE2C from the title
  and matched the live screenshot against the packed frames: 539 of 539
  player pixels and 401 of 401 pixels for each of the two fire enemies at the
  adjacent patrol position. This is the in-game proof that the dungeon uses
  the captured actor tiles.
- `tools/test_city_integration.py`, `tools/test_title_menu_integration.py`,
  `tools/test_city_sfx.py`, `tools/test_city_voice.py` and
  `tools/test_city_cdda.py` all passed on the same build. The CD-DA checks
  scored 0.980/0.984/0.984 and found Cham's line at 56.17 s.
- `tools/verify_all.py` reported `== 0 failure(s) ==`.

The room-by-room PCE comparison, palette remap details and remaining limits
(the optional STAGE2CB/2CG menu scenes still use the placeholder actor) are
documented in `docs/stage2-comparison.md`.
