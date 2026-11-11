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

## BAT row writer found (2026-11-11)

CDRAM `$7190` is a BAT row writer:

```
LDA ($D8),Y      ; next tile byte from the map stream
BEQ end_of_row   ; 0x00 terminates the row
...
LDA #$00; ST0 #$00; STA $0002/$0003   ; VRAM address from $D6/$D7
LDA #$02; ST0 #$02
PLA; CLC; ADC $3059                    ; base 0x00 or 0x40
STA $0002; LDA #$F7; STA $0003         ; BAT word 0xF7xx (palette 15)
INC $D6 (and #$3F)
```

`$7187` is the variant that sets base `$3059 = 0x40`; `$7190` uses base 0.
The table at CDRAM `$7100-$7186` is **45 entries of 3-byte little-endian
row offsets** (0x5C, 0x64, 0x6C, 0x84, ... 0x460); the differences are row
lengths 8..64 bytes.  This is the row table for the palette-15 background
layer.

The state's zero-page `$D8/$D9` is `0x3E00`, but that work-RAM region holds
the 8-byte sprite table (`$D8..`), not the map stream: the pointer is
overwritten after the map is built.  The map stream is not stored as plain
bytes in the STG block (the 0x800 region is high-entropy), so it is
decompressed/copied into RAM before `$7190` runs.  The decompressor has not
been located yet.

## Correction: $7190 is the text/menu renderer

The only caller found (`JSR $CCB1` at CDRAM 0x6C7B/0x6C7E) sets
`$D8/$D9 = 0xCCCC`, which points at the ASCII string **"PUSH RUN BUTTON"**
at CDRAM 0x6CCC.  Therefore the `$7190` row writer is the **text/menu BAT
renderer** (palette-15 tile rows), and the 45-entry 24-bit table at `$7100`
is its text/font row table, not the stage map.

The stage terrain (palettes 0/5/6/7/8/14) is still produced by an unlocated
routine.  Gameplay save states remain the fastest reliable path.
