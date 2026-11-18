# STG4A Mega Drive scene

The selected 256 x 192 background is a 32 x 24 tile crop from BAT row 8, column 0 of the root `.mc9` save. It covers one captured window, not the full stage. The stage module uses manually approximated collision and prototype enemy placement and behavior.

The 286 captured tile/palette combinations and map retain their source shapes. The three background palette lines were recolored toward the generated art-direction concept at `build/gfx/stage4a_pyron_concept.png`. The concept was generated from the source capture with a request for 16-bit cemetery pixel art inspired by Pyron, preserving the composition; it is a visual reference, not hardware-ready art. Line 3 remains reserved for the existing placeholder sprites. `build/gfx/stage4a_capture_screen.png` shows the recolored packed assets.

The reproducible starting capture is `py -3 tools/pack_state_window.py "Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc9" stage4a_capture 8 --columns 0 --reserve-line3 8,9,15 --pack-all-palettes`. This command overwrites the edited palette with the original colors. The concept-based palette adjustment must be reapplied after repacking.

The stage is the eighth selector entry and saves as scene 10. Build includes `STAGE4A.MMD`. The native ISO builds successfully. Genesis Plus GX verified scene selection, background display, movement, jump and landing, two enemy defeats, transition to STG3A, and save/continue including after restarting the core. This does not establish original gameplay fidelity or physical hardware compatibility.

## Captured PCE actors

The player frame is assembled from SAT entries 2, 1 and 0 in the root `.mc9`
(STG4A); the knight frame is assembled from entries 0 and 1 of
`states/Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc4` (a different
capture, not proof that this knight appears in STG4A). Each has 32 x 48 pixels
and is split into 32 x 32 and 32 x 16 Genesis hardware sprites. PCE VRAM words
are little-endian: swapping the two bytes of each 16-pixel plane row is required
when using the existing sprite decoder, otherwise each 8-pixel half is reversed.

The 4-bit player palette occupies Genesis line 3; enemy colors are mapped to
the nearest nontransparent player palette color to share that line. The sprite palette is adapted for higher blue, cyan and red contrast, while preserving the original pixel clusters. The sword effect and heart retain recolored placeholder tiles. The collision body remains the prototype 16 x 16 box.

Genesis Plus GX screenshots are in `build/stg4a_original_sprites_test/`. The
jump test recorded y=128, 109 and 128 at rest, during jump and after landing.
`build/stg4a_original_sprites_combat/` records defeat of both prototype
enemies and transition to STG3A. No physical hardware test was performed.

## Additional player frames (2026-11-15)

The root `.mc9` VRAM also contains visually coherent player patterns starting at
16x16 cell indices `0x160`, `0x170` and `0x180`. They are exported by
`tools/extract_stg4a_player_anim.py` to `stage4a_player_anim.bin`: two are used
as a walking cycle and one as an attack pose. The original animation table and
timing have not been recovered, so these associations and timing are authored.
The existing standing frame is used while idle; both hardware sprite parts are
horizontally flipped when the player faces left. Enemy sprites are also flipped
as they change direction. At the time of that capture the knight had only one identified pose.
The knight is from a different PCE capture and is not verified as an STG4A
enemy. There are no recovered jump sequences or original enemy animation tables.

The player/enemy shared palette was adjusted at entries 1, 6 and 8 to emphasize
blue, cyan and red using 3-bit RGB values. This was an art-direction adjustment
inspired by the requested retro look, not a pixel-by-pixel Pyron repaint. A
generated concept is `build/gfx/stg4a_player_art_concept.png`; the input was the
original standing sprite and the prompt requested a high-contrast 16-bit
Mega Drive concept preserving its pose and blue/red armor. The built-in image
generator was used; the concept is not game-ready sprite data.

The final build was exercised in Genesis Plus GX: screenshots of standing, two
walking poses, left direction, jump and attack are in
`build/stg4a_animation_final/`. The separate combat run in
`build/stg4a_animation_combat_final/` defeated both enemies and reached STG3A.
No original timing, full-stage gameplay, or physical hardware fidelity is
established by these checks.

## Knight patrol frames (2026-11-15)

In `states/Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc4`,
the knight's observed SAT combines a 32x16 upper part at PCE sprite cell
`0xDE` with a 32x32 lower part at `0xF4`. Two further visually coherent
lower-body poses exist in the same VRAM at `0xE4` and `0xF0`.
`tools/extract_stg4a_knight_anim.py` combines each with the captured upper
part, applies the existing nearest-color mapping to the shared player palette,
and writes `stage4a_knight_anim.bin` (two 32x48 frames, 1536 bytes).
The extracted body parts are original PCE pixels; the pairing, walk-cycle use
and timing have been inferred visually, not recovered from the game engine.
The full set of poses and the source's animation table are not established.
The knight itself is from a different PCE stage, not confirmed in STG4A.

The two frames alternate every 16 pixels of enemy travel and flip with its
patrol direction. The original captured frame remains in `stage4a_sprites.bin`
but the patrol uses the two new combinations. The native build succeeded and
Genesis Plus GX showed both poses in `build/stg4a_knight_anim_check/` frames
2400 and 2416. The automated run in `build/stg4a_knight_combat_check/` defeated
both knights and reached scene 5 (STG3A). Physical hardware and original PCE
behavior were not tested.

## Original STG3A knight animation table

The state `states/Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc4`
has STG3A at CDRAM offset `0xA000` and MPR5 `$85`, placing the data at
logical `$A000`. Its enemy animation pointer table starts at `$A744`; entry
`0x1F` points to `$AD60`. The bytes there are
`04 0A 37 10 38 0A 37 10 36`. The original routine at `$67DD-$682D` counts
backward through these duration/frame pairs, giving frame `36` for 16 updates,
`37` for 10, `38` for 16, `37` for 10, then repeating (unless the object's
flags select termination). Frame pointer table `$A7E4` maps these frame IDs
to `$AD73`, `$AD7E`, `$AD89`; each record has two 5-byte sprite descriptors:

| Frame | Upper pattern | Lower pattern |
| --- | --- | --- |
| 36 | `$01B4` | `$01C8` |
| 37 | `$01B8` | `$01E0` |
| 38 | `$01BC` | `$01E8` |

The pointer-table ranges and animation/frame bytes above match the 2048-byte
user data of track 2 sector 464 (STG3A); comparisons removed raw-sector
headers. `tools/test_stg3a_knight_animation.py` initializes animation `0x1F`
and executes the original HuC6280 update routine for 53 calls. It observes
16/10/16/10 updates and the first repeated frame.

`tools/extract_stg4a_knight_anim.py` reads the original pointers and both
components for each frame. This supersedes the former visually inferred
combinations: those reused the upper half of frame 38 for every pose. The port
plays the recovered durations at one update per VBlank, using independent
counters per knight. The original code's elapsed duration is verified in
**animation-update calls**; the relation of those calls to every physical PCE
video frame has not been independently established. The cavaliers remain
prototype actors placed into STG4A; their presence in the original STG4A and
the original movement, collision and attack behavior have not been recovered.

Genesis Plus GX regression artifacts are in `build/stg4a_knight_table_runtime/`
and `build/stg4a_knight_table_combat/`. The former captured 54 consecutive
RAM snapshots and verified that the port counter advances once per frame and
wraps at 52; the latter defeated both prototype enemies and entered STG3A.
The screenshots show the recovered poses in context. No physical console was
tested.

The STG4A `.mc9` contains tables at the same logical addresses, but their
contents differ: animation index `0x1F` points to `$ADD7` and begins
`02 05 34 05 33`, rather than the STG3A knight sequence. The STG4A SAT has
no identified knight or complete enemy at the saved instant. Therefore the
STG3A sequence above must not be reported as the original STG4A enemy sequence.
A heuristic inventory of candidate pointers and records for both states is
`build/stg4a_animation_inventory.json`; candidate records have not all been
classified as enemies or verified by tracing runtime objects.

## STG4A skull animation (2026-11-15)

The `.mc9` STG4A save contains a skull in VRAM. Animation pointer table
`$A744`, index `$1F`, points at `$ADD7`, with bytes `02 05 34 05 33`. The
original HuC6280 update routine visits the pairs backwards: frame `$33` for
5 update calls, then `$34` for 5, and repeats. Frame pointer table `$A7E4`
resolves frame `$33` to `$ADDC` (`01 11 E0 F0 D8 01`) and frame `$34` to
`$ADE2` (`01 11 E0 F0 F8 01`): each is one 32x32 sprite, with original PCE
pattern `$01D8` or `$01F8`. The animation pointer, frame pointers and records
match the user payload of STG4A track-2 sector 544.

`tools/test_stg4a_skull_animation.py` executes the captured PCE animation code
for 21 updates and confirms the 5/5 cycle.
`tools/extract_stg4a_skull_anim.py` reads the pointers and VRAM from `.mc9`
and packs two 32x32 Mega Drive sprite frames (1024 bytes). The save has no
identified active skull SAT entry, so the choice of PCE palette 2 is visual
and unverified. Its colors are mapped to the shared Genesis sprite palette.

The STG4A prototype now displays these skulls in place of the STG3A knights.
Their 5/5 timer runs once per port VBlank. The original routine durations are
known in update calls; equivalence to PCE display frames is not established.
Movement, spawn points, health, hitboxes and attack interaction remain authored
prototype behavior; this is not a complete reconstruction of the original
enemy. The PCE table also contains other candidates, including columns and
other figures, but their classification, original palette and behavior have not
been verified. The graveyard figures must not be assumed to be enemies.

After correcting the initial 16-pixel truncation, the rebuilt ISO was run in
Genesis Plus GX. `build/stg4a_skull_final/` contains both animation frames and
21 consecutive RAM snapshots; the modulo-10 port counter advanced on every
sampled frame and the two poses each lasted five updates.
`build/stg4a_skull_final_combat/` confirms both prototype skulls can be defeated
and the scene transitions to STG3A. No physical hardware test was performed.

## STG4A skull column (2026-11-15)

STG4A animation index `$1A` at pointer table `$A744` points to `$AD6D`,
bytes `02 06 2E 06 2D`: the HuC6280 routine plays frame `$2D` for six update
calls, then `$2E` for six, and loops. Frame table `$A7E4` points to `$AD83`
and `$AD8E`. Each frame is two original PCE sprites (32x16 and 32x64), which
compose into a 32x80 column of skulls. Animation and frame table ranges match
the user payload of track 2 sector 544. `tools/test_stg4a_skull_animation.py
STATE --column` executes the original stepper and confirms the sequence.

`tools/extract_stg4a_skull_column.py` converts these original pixels to two
Mega Drive frames, each split into 32x32, 32x32 and 32x16 sprites. The PCE
palette ID 2 is a provisional visual choice, as the captured SAT does not show
the column active. Both enemy graphics share the player sprite palette via
nearest-color remapping, so they are not a verified reproduction of original
PCE colors.

The prototype now places one moving skull and one stationary column. The
column's position, 16x16 lower hitbox, HP, ability to be attacked and exit gate
are authored approximations, not recovered original object behavior. Other
STG4A frame sequences, including a person holding a light and additional
objects, remain unclassified and are not asserted to be enemies. The captured
sequence durations are update calls; the PCE's exact correspondence between
update calls and displayed frames remains unverified.

Genesis Plus GX outputs are under `build/stg4a_column_runtime/` and
`build/stg4a_column_combat/`. Twenty-five consecutive memory captures confirm
the port's 12-update and 10-update counters advance and wrap; screenshots
show both graphics; an automated combat run defeated both prototypes and
reached STG3A. Build ISO SHA-256
`f767d0b771b4665356a80fbcfd8189cb07e63a9e809f92e58cbc058e8f41b5c6`.
No physical hardware test was performed.

## Palette and behavior investigation (2026-11-15)

This section supersedes the provisional palette guesses above. In the saved
STG4A CDRAM, the object configuration table at CPU `$A09C` has 19-byte
entries. Original initializer `$5765` loads type `$05` with dispatcher `$2C`,
animation `$1A`, palette `$02`; type `$06` gets dispatcher `$2D`, initial
animation `$FF` and palette `$02`. The sprite builder uses the palette field
in the SAT attribute. `tools/test_stg4a_skull_animation.py` now runs that
initializer as well as the animation routine in the local HuC6280 core.
This identifies the palette number from code, although the captured state
does not itself show either object active.

Both enemy assets now use the converted captured PCE palette 2 on Mega Drive
palette line 2. `tools/pack_stg4a_enemy_palette.py` combines background lines
1 and 2 to free that line, changing 10 opaque background pixel occurrences to
the closest available color. The player retains line 3. Generated resources
are `stage4a_hw2_*`, `stage4a_enemy_pal.bin`, `stage4a_skull_hw2.bin` and
`stage4a_column_hw2.bin`.

The skull's `$9283` dispatch enters the pursuit routine at `$8849`. Initially
it activates within approximately 80 horizontal pixels of the player, selects
animation `$1F`, sets a `$1E` update timer and calculates a two-dimensional
direction and velocity. The port implements a proximity trigger, but its
horizontal steering, speed, placement, health and collisions remain
approximations. The original timer does not prove the skull stays stationary.

The column's `$9212` routine cycles through three projectile spawn groups,
with a `$78` update timer set after each spawn. The group records in CDRAM
bank `$84` describe type `$11` projectiles at offsets (+18,-36), (-18,-20)
and (+18,-4). The port still uses a stationary, attackable column; it does
not yet implement these projectiles, original damage behavior or hitboxes.
These findings are not a claim of complete behavioral parity with the PCE.

## Projectile and pursuit integration (2026-11-15)

This section supersedes the movement and projectile status immediately above.
The type `$11` projectile configuration at `$6884` selects frame `$32`,
palette 2 and two size fields of 4. Frame descriptor `$ADCE` selects PCE
pattern `$01BA`, a 16x16 sprite. The extraction script converts it to four MD
sprite tiles using the original captured palette. The three records are
spawned at the documented offsets, with velocities +32, -32 and +32 in PCE
four-fractional-bit units; the port cycles every 120 updates. The PCE has ten
projectile slots for this class, while this captured single-screen port uses
six and removes shots after leaving its screen. These constraints and spawn
coordinates are not a full-stage reconstruction.

The skull uses the original direction thresholds at `$7B05`, velocity table
at `$7B54`, speed `$08`, the activation threshold and the timers from
`$8849`. The port follows the player in both axes with 4-bit fractional
coordinates. `tools/test_stg4a_pce_motion.py` checks the three raw spawn
records and compares a mathematical direction model against the captured
`$7A34` HuC routine over 1,000 vectors. The C logic additionally has a small
host test for its movement and projectile cadence. This does not prove that
every surrounding game update or every corner case is cycle-identical.

Projectile contact uses a provisional 8x8 area and the prototype combat's
one-HP damage and 60-update invulnerability. The relevant projectile table
contains 4/4 size fields, but their role in the original player collision
and its exact boundaries has not been established. Player and enemy health,
enemy hitboxes, weapon interactions, the column's damaged states and its
placement are also still prototype values. Do not treat these as validated
PCE combat behavior.

The final ISO was run in Genesis Plus GX. `tools/test_stg4a_enemy_runtime.py`
observed all three shot origins and directions, and changing skull X/Y. Its
optional controlled hit test writes the player position and clears the
invulnerability counter in emulated RAM, then verifies that projectile
contact reduces the prototype HP. A separate normal-input combat run defeated
both enemies and reached STG3A. These tests do not establish original damage
or hitbox parity.

## Combat reconstruction from bank 83 (2026-11-15)

This section supersedes the provisional collision and damage numbers above.
With MPR6 mapped to CDRAM bank `$83`, original `$C23C` checks a standing
Yuko's contact body: center at player feet minus 24 pixels vertically, half
width 3, half height 22. Actor config offsets and half sizes are: type `$06`
skull: center `(x, y-16)`, half size `(12,12)`, contact damage 2; type `$05`
column: center `(x, y-40)`, half size `(16,40)`, contact damage 3. Type
`$11` projectile half size is `(4,4)` and its spawn record has damage 3.
The routine compares `floor(abs(delta_fixed)/16)` against the sum of half
sizes, inclusively. Other player stances use different boxes and are not
implemented in this scene.

For Yuko (`$2378=0`) the contact damage field is used directly. `$C728`
subtracts it from `$238D`; the captured state has 24 HP and the game caps it
at 24. A successful hit sets `$24EB` to `$5A` (90 updates). `$C795` uses the
actor's two-byte resistance `$2712:$26F9` and sets `$24EC` to `$0A` after a
nonfatal hit; collision checks suppress repeated hits and contact while this
timer is nonzero. The skull starts with 8 resistance; the column starts with
212. Source calls and boundary cases are executed in
`tools/test_stg4a_pce_combat.py`; only the sound call is skipped.

The captured player has weapon level 2 (`$238C=2`). An uncharged attack at
`$48A4` selects projectile record 4 in bank `$84`, with power 4, lifetime
24, horizontal speed 32 in 1/16-pixel units and hitbox half size `(2,22)`.
The PCE has other characters, weapon levels and charged attacks. The port
implements only this captured uncharged variant, using up to three weapon
projectiles and a placeholder weapon visual. Its three-heart HUD summarizes
24 HP in eight-point segments rather than reproducing the original HUD.

When its counter falls below 200, the column's `$9246` routine restores 212,
sets a 120-update timer and disables its contact and damage flag via `$9E58`.
It subsequently clears the flag via `$9E5F` and waits another 60 updates.
The port reproduces the protection and timers but still displays its normal
animation rather than the original `$1B/$1C` damaged animations. The single
captured screen, enemy placements, floor, respawn and exit remain prototype
approximations. The exit no longer requires the recovering column to die.

The native ISO was tested in Genesis Plus GX. Normal input defeated the skull
with two power-4 attacks and reached STG3A while the column remained alive.
Controlled RAM-assisted tests checked 3 damage and 90-update protection from
a projectile, and checked the 120/60 column recovery and its change in contact
eligibility. These tests do not prove complete parity with the whole PCE game.
