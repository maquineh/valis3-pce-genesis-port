# Stage migration status

The ten playable areas are the ten `STG` blocks on PCE track 2.  Each one is
migrated from a real Mednafen save state: the captured BAT/VRAM/CRAM are
packed into a Mega CD module by `tools/pack_state_window.py`.

| PCE block | sector | save state | Mega CD module | status |
|-----------|--------|------------|----------------|--------|
| STG1A | 304 | — | stage1 (placeholder) | pending state |
| STG2A | 344 | `.mc0` | `STAGE2.MMD` (9084 B) | **done** |
| STG2B | 384 | `.mc2` | `STAGE2B.MMD` (10308 B) | **done** |
| STG2C | 424 | — | — | pending state |
| STG3A | 464 | — | — | pending state |
| STG3B | 504 | — | — | pending state |
| STG4A | 544 | — | — | pending state |
| STG4B | 584 | — | — | pending state |
| STG4C | 624 | — | — | pending state |
| STG5A | 664 | — | — | pending state |

## Adding a new stage from a save state

1. Put the Mednafen `.mcX` state in the project root.
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
   the stage is the lower half, so `32 40` was used.
4. Add `game/src/stageN_state.c` + `stageN_state_res.s` (copy the Stage 2B
   files and change the resource prefix, `STAGE_SCREENS`, `STAGE_TILES` and
   `PLAYER_TILE` to the packer's JSON values).
5. Register the module in `shared.h` / `spx.c` and add the makefile target.
6. Rebuild: `tools/build_megacd.ps1` -> `tools/mcd_make_disc.py` ->
   `tools/verify_all.py`.

The title currently selects `STAGE2.MMD` on START (hold LEFT for
`STAGE2B.MMD`).  Once all ten states exist, the same selector can be extended
to a real stage menu.
