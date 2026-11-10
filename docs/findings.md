# Valis III (TJCD0009) - PC Engine CD findings

Everything below is derived from the shipped disc image in this repository
(`tools/` = the scripts that produced it). Identifications are marked
**[observed]** (read directly from bytes), **[inferred]** (deduced, not proven).

## 1. Disc / image layout

- `Valis_3_(NTSC-J)_[TJCD0009].iso` = 555,725,856 B = 236,278 × 2352 B.
- The image contains **no CD sector metadata at all** (no `00 FF…FF 00` sync
  pattern anywhere in 555 MB, no 4-byte headers). It is a continuous stream
  where each 2352-byte block corresponds to one CD frame (75 frames/s).
  **[observed]**
- The `.cue` declares 72 tracks: 16 `MODE1/2352` data tracks and 56 `CD-DA`
  audio tracks, alternating data/audio up to track 72.
- Consequence: a data track's payload is the **continuous** byte range
  `[index01_frame*2352 .. next_index01_frame*2352)`; audio tracks are 16-bit
  stereo 44.1 kHz PCM at 2352 B/frame. `tools/cue_split.py` implements this.

## 2. Soundtrack (original, complete)

- 55 CD-DA tracks extracted (`build/extracted/audio/track_01..71.wav`).
- Total ≈ 44 minutes; every track is real music (no silent tracks).
  `tools/audio_inventory.py` prints duration/RMS/peak per track.
- Mega CD can play CD-DA tracks natively, so the original soundtrack can be
  burned unchanged onto the port's disc.

## 3. Track roles

- `track_02.bin` (3,551,520 B) = main program + title/menu + overlays.
- `track_06..track_36` (16 tracks, ~1.2 MB each) = per-stage/segment asset
  blocks, each with a ~150-190 KB dense region at the start.
- `track_72.bin` (3,205,776 B) = second large block (ending/staff-roll data).

## 4. CPU-side loading (the important part)

The game is HuC6280 (65C02 + HuC6280 extensions). `tools/disasm6280.py`
implements the full opcode set including `ST0/ST1/ST2`, `TAM/TMA/TMAI`,
`TII/TDD/TIN/TIA/TAI` (7-byte block transfers), `BBR/BBS`, `CSH/CSL`, `SET`.

The game calls the **CD-ROM² System Card BIOS** through the jump table at
$E000-$E0F0 (function list recovered: `cd_read` $E009, `cd_exec` $E00F,
`cd_play` $E012, `ex_setwrt` $E0AE, `ex_satclr` $E0A2, `ex_sprdma` $E09F …).

Parameters are passed through the zero-page mirror of the BIOS work area:

| zp | BIOS word | meaning (cd_read)                     |
|----|-----------|----------------------------------------|
| F8 | al        | sector count (local) / size low        |
| F9 | ah        | size high (for VRAM: size in bytes)    |
| FA | bl        | destination address low / bank #       |
| FB | bh        | destination address high               |
| FC | cl        | sector number bits 16-23               |
| FD | ch        | sector number bits 8-15                |
| FE | dl        | sector number bits 0-7                 |
| FF | dh        | destination type: $01 RAM, $02-$06 MPR, $FE/$FF VRAM |

**Sector ↔ file mapping (verified):** CD sector N of a data track = byte offset
`N × 2352` inside that track. Verified because track 2 sector 12 = offset
$6E00 is exactly where the title-screen tiles start (see below).

`tools/find_bios_calls.py` and `tools/decode_cd_calls.py` enumerate and decode
every call site. Decoded boot sequence (track 2, code at $49CD):

| site    | call    | sector | dest            | size     |
|---------|---------|--------|-----------------|----------|
| $49CD   | cd_read | 12     | VRAM word $1000 | $A000 B  |
| $49F0   | cd_read | 40     | VRAM word $7000 | $2000 B  |
| $4CA0   | cd_exec | 32     | RAM $4000 (jump)| 8 sectors|
| $4CC8   | cd_exec | 976    | RAM $4000 (jump)| 12 sect. |

Per-stage loaders exist at $22503E, $22BE32, $230792, $2311D4, $232535,
$23510D, $2375E2, $23E852, $249FB5, $2553A2, $260F5A, $26C339, $283757,
$287BEC, $2A1072 … (one group per stage/segment).

## 5. Graphics format (confirmed by rendering)

- BG tiles: standard PC Engine 8×8 4bpp, 32 B:
  `p0=byte[2r]`, `p1=byte[2r+1]`, `p2=byte[16+2r]`, `p3=byte[16+2r+1]`,
  pixel index = p0|p1<<1|p2<<2|p3<<3, bit 7 = leftmost.
  (`tools/pce_gfx.py` `tiles`)
- VRAM word addresses: a tile index occupies 16 words (32 B); the first cd_read
  writes at VRAM **word $1000 = byte $2000 = tile index 256**, so disc tile
  #k = VRAM tile index 256+k.
- BAT: 16-bit LE words `(palette<<12) | tile_index` covering 32×28 cells,
  at VRAM $0000. A BAT table for the title screen was located at
  **track_02 file offset $123D40** (entries reference tiles $100-$2FF and BG
  palettes 0-3) **[observed]**.
- Rendering the BAT + tiles reproduces the **title screen**: the "START" and
  "CONTINUE" menu entries and the Japanese copyright line are legible
  (`tools/render_bat.py`, `build/gfx/title_bat.png`) **[observed]**.
- Tile sets contain large amounts of dither-pattern tiles ⇒ the game displays
  dithered full-screen stills (cutscenes) using ramp palettes.

## 6. Screen layout on the disc

Decoded screens so far:

| Screen | Tiles (track 2 file offset) | Map (BAT) | Palette | How identified |
|---|---|---|---|---|
| Title / attract | `$6E00` (read: sector $0C → VRAM word $1000, 40 KiB) | `$123D40` | `$2B49` (64 BG colours) | decoded loader + rendered |
| Menu / config ("PRINT") | `$0000` (read: sector $00 → VRAM word $2000) | `$0B0EA0` | `$B0FC0` (64 BG colours) | BAT scan + rendered |

### Stage tile blocks
The stage loader (`tools/decode_cd_calls.py`, sites `$22529E`..`$2256A7`)
reads **8 × 4 sectors** with destination type `dh=$01` (local RAM) to
**RAM $8000** from disc sectors 988, 1000, 1020, 1040, 1060, 1080, 1120, 1128:

| block | sector | track-2 file offset | content |
|---|---|---|---|
| 1 | 988 | `$237540` | tiles (coherence 0.32) |
| 2 | 1000 | `$23E380` | tiles (0.29) |
| 3 | 1020 | `$249B40` | tiles (0.31) |
| 4 | 1040 | `$255300` | tiles (0.26) |
| 5 | 1060 | `$260AC0` | tiles (0.26) |
| 6 | 1080 | `$26C280` | tiles (0.42) |
| 7 | 1120 | `$283200` | tiles (0.27) |
| 8 | 1128 | `$287B80` | tiles (0.51) |

These are the gameplay tile sets (character/enemy/object artwork, mostly
transparent 16x16-style slots plus dither fills). The matching stage *maps*
are not present as plain 32x28 BATs anywhere on the disc, so they are either
generated from object/collision lists by the game code or stored in a format
that still needs decoding (see "Open items").

Map/PALETTE/TILE block layout in track 2 (`tools/` classifier in
`tools/find_maps.py`, block classifier: see `tools/map_tracks.py`):

```
$0000000  credits text + interleaved data
$018000-  ~576 KiB of 8x8 tile sets for many screens
$0B0000   maps, palettes and UI tile clusters (menu screens)
$0C8000-  further mixed data
```

`tools/find_maps.py` only locates **plain** 32x28 BATs (the menu/title maps).
The gameplay stage maps are *not* stored as plain BATs on the disc, so the
per-screen stage extraction needs the tile/VVRAM base of each screen, which is
still being reverse engineered (see "Open items").

## 7. Open items


- **Palette data** not yet located. Uploads are block transfers to the VCE
  colour-data port ($0404) from sources such as $4B49/$6B49/$8B49/$BA8D with
  length $2000; those addresses live in whichever 8 KB page the MPR registers
  have mapped, so static identification requires following the overlay loads.
  Greyscale rendering is used for identification in the meantime.
- BAT tables for the other screens/stages (only the title BAT pinned so far).
- Sprite (SAT/SG) layout per stage.
- Overlay → CPU address mapping table (needed to read the stage logic code).
