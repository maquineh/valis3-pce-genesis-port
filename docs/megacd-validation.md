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
