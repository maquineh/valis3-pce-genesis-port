## Stage 2-10: what blocks the split (evidence this pass)

### What is on the disc

The 0x600 map grid in `track_02` runs from `$17FF90` (stage 1) to `$238D90+`
(≈341 slots). A scan requiring *playfield structure* (>=25% of tiles inside the
stage tile-block range, a >=16-cell horizontal run of identical tiles, and
>=100 distinct tiles) yields ~30 groups. Rendering them shows:

| offset range | what renders |
|---|---|
| `$17FF90`-`$183590` | **stage 1 playfields** (10 screens) - the only playfields found |
| `$0B0000`-`$170000` | title screen, config menu, and **Japanese dialog / cutscene frames** (`$0F64F0`, `$151FA0`, `$13B020`, `$0DEE90` all show text over dithered art) |
| `$180000`-`$240000` | tiles scattered over black (object / collision tables) |

So the *other nine stage terrains are not stored as plain 32x24 BATs in
track_02*.

### Where they must be
Each stage has its own data track (`track_06`, `track_08`, ... `track_36`) with
~190 KiB at the start that renders as the game's dither artwork, followed by
records of **4 bytes** at regular intervals (e.g. `track_06 @ $2E000`:
78 records per 4 KiB, patterns `[00][lo][hi][flags]` then `[count][00][00][00]`).
Those records are the next thing to decode - they are the compressed stage
description (and/or the object/collision list) for the remaining stages.

### Tools that are ready for it
- `tools/render_multi.py` - render a map whose tiles come from several VRAM
  regions (needed once the multi-block VRAM layout per stage is known).
- `tools/match_blocks.py`, `tools/assign_by_range.py` - block matching helpers.
- `tools/pack_stage_all.py` - packs any stage's screens once the maps are
  found (already used for stage 1).
- `game/src/stage1.c` - the streaming engine to copy for `stageN.c`.

### Done already (verified)
- Stage 1: 10 screens, 1297 tiles, streaming module, all static tests pass
  (`tools/test_stage_logic.py`), contact sheet `build/gfx/stage1_screens.png`.
