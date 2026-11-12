# Stage migration status

The ten playable areas are the ten `STG` blocks on PCE track 2.  Each one is
migrated from a real Mednafen save state: the captured BAT/VRAM/CRAM are
packed into a Mega CD module by `tools/pack_state_window.py`.

Two capture sets exist:

* the **first set** sits in the repository root (`Valis III (Japan).…mc0` …
  `.mc4`) and produced the STAGE2 / STAGE2B / STAGE3A modules;
* the **second set** (re-saved by the user) sits in `states/` and produced
  STAGE2C (the dungeon) and STAGE2A2 (the seaside room).  Note that the file
  names collide with the first set but the contents differ: the old `.mc2` is
  STG2B, the new `.mc2` is STG2C.

| PCE block | sector | save state | Mega CD module | status |
|-----------|--------|------------|----------------|--------|
| STG1A | 304 | — | stage1 (placeholder) | pending state |
| STG2A (room 1) | 344 | root `.mc0` | `STAGE2.MMD` (9084 B) | **done** |
| STG2A (room 2, seaside) | 344 | `states/…mc1` | `STAGE2A2.MMD` | **done** |
| STG2B | 384 | root `.mc2` | `STAGE2B.MMD` (10308 B) | **done** |
| STG2C (dungeon) | 424 | `states/…mc2` | `STAGE2C.MMD` | **done** |
| STG2C (green room) | 424 | `states/…mc3` | — | captured, but the visible window is the HUD layer only |
| STG3A | 464 | root `.mc4` | `STAGE3A.MMD` (7236 B) | **done** |
| STG3B | 504 | — | — | pending state |
| STG4A | 544 | — | — | pending state |
| STG4B | 584 | — | — | pending state |
| STG4C | 624 | — | — | pending state |
| STG5A | 664 | — | — | pending state |

Five of the ten stages are now migrated from real captured state data; the
remaining five (STG1A, STG3B, STG4A/B/C, STG5A) still need a gameplay save
state.

## Adding a new stage from a save state

1. Put the Mednafen `.mcX` state in the repository root (or in `states/`).
2. Extract it:

```
python3 tools/extract_state.py "STATE.mcX" build/state_NAME
```

   `summary.json` shows the `STG` block found in CDRAM, the BAT scroll and the
   palette set.
3. Pack the playable BAT window (the state's stage half) — rows are the top
   row of each 32x24 screen:

```
python3 tools/pack_state_window.py "STATE.mcX" stageN_state ROW0 ROW1
```

   For STG2B the forest is in the upper-left, so `0 8` was used.  For STG2A
   the stage is the lower half, so `32 40` was used.  For the second capture
   set the stage sits at the top of the BAT, so `0 8 16 24` gives four
   consecutive screens.
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

The title screen keeps the "hold a direction while pressing START" scheme:

| input | module | scene |
|-------|--------|-------|
| `START` | `STAGE2.MMD` | STG2A room 1 (sky and rocks) |
| `UP` + `START` | `STAGE2A2.MMD` | STG2A room 2 (sea cliffs and tower) |
| `LEFT` + `START` | `STAGE2B.MMD` | STG2B forest |
| `RIGHT` + `START` | `STAGE3A.MMD` | STG3A ice castle |
| `DOWN` + `START` | `STAGE2C.MMD` | STG2C blue brick dungeon |

Once all ten states exist, the same selector can be extended to a real stage
menu.
