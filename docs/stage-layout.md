## 7. Where the levels are (decoded in this pass)

Screen maps are **32x24 cells, one 0x600-byte block per screen**, laid out
consecutively on a grid. A screen's tile indices are relative to the tile block
that the loader read for that stage (base `$200`).

Stage 1, decoded end-to-end:

| item | value |
|---|---|
| first map | `$17FF90` (track 2) |
| screens | 10 (`tools/screen_chain.py`) |
| tile block | `$19440` (cd_read sector `$2C` -> VRAM word `$1000`, 48 KiB) |
| palette | `$9352` (64 BG colours) |
| packed as | `game/res/gfx/stage1_all_{tiles,maps,pal}` (1297 tiles, 41504 B) |
| rendered | `build/gfx/stage1_screens.png` (contact sheet) |

`tools/walk_stages.py` walks the whole chain from `$17FF90`: the map region
extends from `$17FF90` up to `$238D90`+ (about 344 screen-sized slots), with
long runs of 10/37/34 screens - i.e. the other stages are on the disc and still
need to be split into stage tables by tile block.

The stage-1 module (`game/src/stage1.c`) loads all 10 screens and streams them
through the 64-cell plane A the way the original does (current screen at
columns 0-31, next screen at 32-63, pair redrawn on each screen boundary).

## 8. Open items

- Split the remaining map region into the 10 stages: each stage's tile block
  has to be identified (8 VRAM-bound stage tile blocks are known from
  `tools/list_vram_reads.py`).
- Sprite (SAT/SG) data for the characters (Yuko/Cham/Valna), enemies, items
  and bosses; `game/res/gfx/player_spr.bin` is engine test art for now.
- Stage geometry/collision and the game logic (player physics, enemy AI, boss
  patterns). Stage 1 now scrolls and moves a sprite, but has no collisions or
  enemies yet.
