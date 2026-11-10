## 7. Where the levels are (decoded)

Screen maps are **32x24 cells, one 0x600-byte block per screen**, laid out
consecutively on a grid. A screen's tile indices are **relative to the tile
block the loader read for that screen**, with `base $200` verified by render:

* `tools/render_bat.py … $19440 base $200` → terrain/platforms (correct)
* `tools/render_bat.py … $19440 base $100` → dense dither (wrong)

### Stage 1 (fully decoded)

| item | value |
|---|---|
| first map | `$17FF90` (track 2) |
| screens | 10 (`tools/screen_chain.py`) |
| tile block | `$19440` (loader: sector `$2C` → VRAM word `$1000`, 48 KiB) |
| palette | `$9352` (64 BG colours) |
| packed | `game/res/gfx/stage1_all_{tiles,maps,pal}` (1297 tiles, 41504 B) |
| rendered | `build/gfx/stage1_screens.png` (contact sheet) |

The stage-1 module (`game/src/stage1.c`) loads all 10 screens and streams them
through the 64-cell plane A like the original (current screen at columns 0-31,
next at 32-63, pair redrawn on each screen boundary).

### Why stages 2-10 are not split yet

The map grid runs from `$17FF90` to `$238D90+` (≈341 slots), but most slots do
**not** render as playfields with any of the nine known stage tile blocks -
they render as tiles scattered over black or as dithered text (cutscene and
dialog frames). Evidence gathered this pass:

| tool | finding |
|---|---|
| `tools/match_blocks.py` | per-block render scoring: no block separates playfields from object data |
| `tools/assign_blocks.py` | "art tile" fraction prefers `s514` everywhere → misleading |
| `tools/assign_by_range.py` | maps only cover 31-41% of their block's tile range → screens use tiles from several VRAM regions, so range coverage cannot identify the block |
| `tools/palette_profile.py` | palette nibble mix changes at *every* screen → not a stage boundary signal |
| `tools/coherence.py` | 4x4 pattern diversity is similar for right and wrong blocks → not a separator |

Screen-group "leaders" (maps with a strong `$200-$2FF` tile concentration,
`tools/assign_by_range.py` reference run) are at `$0B1200`, `$123E00` (title),
`$0F5C00`, `$152000`, `$0DEE00`, `$0C8000`, `$10CA00`, `$13B200`, `$17FC00`
(stage 1) ... plus more in `$0C0000-$170000`. Rendering them with the stage-1
block shows title/menu/cutscene frames (one clearly shows Japanese dialog text
at `$13B200`), not new playfields.

So stages 2-10 are **present on the disc** (the loader reads nine distinct
stage tile blocks: sectors `$2C`, `$2F`, `$30`, `$34`, `$44`, `$4A4`, `$4D4`,
`$4F4`, `$514`) but their *playfield* maps still have to be matched per screen.
The next step is a per-screen visual match: render each candidate screen with
each block and keep the pair whose render shows terrain (the same procedure
that produced stage 1).
