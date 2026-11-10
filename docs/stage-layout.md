## Stage 2-10: exhaustive search results (this pass)

I could not turn the decoded map grid into stages 2-10. Everything I tried, and
why it failed, is recorded here so the next attempt starts from the evidence
instead of repeating it.

### What is confirmed
- **Stage 1 works**: 10 real screens (`$17FF90` + k*`$600`), tile block
  `$19440`, palette `$9352`, packed into `game/res/gfx/stage1_all_*`, running in
  `game/src/stage1.c` with plane-A streaming. Verified by
  `tools/test_stage_logic.py` (all PASS) and `build/gfx/stage1_screens.png`.
- The map grid runs from `$17FF90` to `$238D90+` (≈341 slots of 32x24 cells).
- Nine stage tile blocks are read by the loader (`tools/list_vram_reads.py`):
  sectors `$2C`, `$2F`, `$30`, `$34`, `$44`(8K), `$4A4`, `$4D4`, `$4F4`, `$514`.

### What fails (all attempted)
| attempt | result |
|---|---|
| `tools/match_blocks.py` per-block render score | no block separates playfields from object data |
| `tools/assign_blocks.py` "art tile" fraction | prefers `s514` everywhere - dither tiles count as art |
| `tools/assign_by_range.py` tile-range coverage | ties always go to the biggest block; maps only cover 23-41% of any block's range |
| `tools/coherence.py` 4x4 pattern diversity | right and wrong blocks score the same |
| `tools/palette_profile.py` | palette mix changes at *every* screen |
| tile bases `$100`, `$200`, `$400`, `$800`, `$F00` | only `$200` renders stage 1 correctly; the others render dither |
| tiles from the stage tracks (`track_06`/`track_08` at 0 and `$20000`) | render as scattered/noise |
| `render_multi.py` multi-VRAM-region tiles (`$200:$19440`,`$500:$2EA7C0`) | worse than the single block |
| "playfield signature" scan (cov>=0.25, run>=16, distinct>=100) | finds the title/menu/dialog frames, not new playfields |
| delta heuristic (map = tile block - 0x14B0) | candidate `$181B20` with `$2F` starts a 40-screen chain but renders as scattered art |
| `tools/screen_chain.py` with maxrun>=16 / distinct>40 | only stage 1 forms a coherent playfield chain |

### Conclusion
The stage-2..10 **terrain is not stored as plain 32x24 BATs in track 2**. The
remaining decoded region is dialog/cutscene frames (`$0B0000-$170000`, several
show Japanese text over dithered art) and object/collision lists
(`$180000-$240000`, tiles scattered over black). The game builds the terrain
from something else - the next candidate is the per-stage data track content
(`track_06`..`track_36`), whose ~190 KiB of dither artwork is followed by
**4-byte records with an 86-byte structural period** (e.g. `track_06 @ $2E000`:
`[00][lo][hi][flags]` then `[count][00][00][00]`), i.e. a compressed stage
description that still has to be decoded.

### Ready for the next attempt
- `tools/render_multi.py` - render a map whose tiles come from several VRAM
  regions (needed once a stage's multi-block VRAM layout is known).
- `tools/pack_stage_vram.py` - pack a stage by loading its block at its natural
  VRAM tile slot (no remap), the layout the original uses.
- `game/src/stage1.c` - the streaming engine to copy for `stageN.c`.
