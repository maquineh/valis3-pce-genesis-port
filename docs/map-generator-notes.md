# STG BAT generator notes (negative results)

The ten STG blocks contain raw 4bpp tiles at `+0x6E40` and a word region at
`+0x27C8`, but the BAT is **generated** by the game, not copied:

- Raw 16-bit BAT at `0x27C8` (row/column-major, widths 32/34/40/64, every
  offset): best **26/2048** words — noise.
- Content-based tile mapping (block tile -> VRAM tile): 802/1678 tiles
  mapped; no 8x8 chunk matches the BAT above 15/64 pixels.
- 32x32 map hypothesis indexed by header byte `+0x11`: best **18/1024**.
- Room jump table `$6DD7`/`$2DD7` (handlers `$704A` STG2A, `$7056` STG2B,
  `$7163` STG2C): sets room state, scroll and palette copies.  The block
  transfers found there copy palette blocks:
  - `TII $A504, $3CA0, $0060`
  - `TII $A666, $A466, $009E`
  - `TII $A464, $3C00, $00A0`
- Block transfers from `$A000-$BFFF` to VRAM (`$0002/$0003`): only palette
  and scroll transfers were found, no BAT/tile transfer.

Conclusion: the BAT is built by a routine not yet located (most likely the
CD room loader / object interpreter).  The fastest reliable path remains a
gameplay Mednafen F5 state per stage; the state pipeline is ready
(`tools/extract_state.py` + `tools/pack_state_window.py`).
