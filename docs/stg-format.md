# STG stage-block format and the real Stage 2 snapshot

## Disc layout

`Valis III (Japan).cue` is a per-track cue with 72 tracks.  Tracks 2, 6, 8,
10, ..., 72 are MODE1/2352 data tracks; the rest are CD-DA.  Track 2 INDEX 01
is absolute MSF `00:47:65` = LBA 3440; its file keeps a 225-sector pregap at
the front (`INDEX 00`), so `build/retail/*Track 02*.bin[225:]` is the data-only
track used by the emulator.

The emulator's `DINFO` previously knew only tracks 1 and 2.  The game asks for
track 6 (the ADPCM sample track) after the act-title card, received MSF
`00:00:00`, computed base `-150` and read audio from the lead-in forever.  The
real 72-track TOC is now built by `tools/valis_toc.py` and served by
`tools/valis_disc.py`; `pce_system.py` returns it from the `0xDE` DINFO
command.  With that fix the game reads track 6 at LBA 24427 (24+20+32
sectors), runs the BIOS `ad_trans` transfer and starts the CD-DA music, so the
lead-in loop is gone.

A Mednafen state (`Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0`)
was supplied and decoded (see `tools/pce_state.py`).  It reveals the real
Stage 2 state:

```
BaseRAM    @ 0x031029   8192 B   work RAM
CDRAM      @ 0x045615  65536 B   CD-ROM2 code/data RAM (Mapped at $100000)
VRAM       @ 0x033B0C  65536 B   64 KiB VRAM (16-bit LE words)
color_table@ 0x033260   1024 B   512 CRAM words (16-bit LE)
```

The state has `STG2A` at CDRAM offset `0xA000`, MPR `FF F8 80 81 82 85 83 00`,
BG scroll `X=39 Y=500`, and a BAT with 84 distinct tiles using palettes
`0,5,6,7,8,14,15`.  `tools/extract_state_stage2.py` writes the live
`vram.bin`, `cram.bin`, `bat.bin` and `cdram.bin` plus `summary.json` to
`build/state_stage2/`.

> Note: the state's `SysCardRAM` section is all zero; Valis III is a CD-ROM²
> title, so its code/data live in the 64 KiB `CDRAM`, not in the Super CD RAM.

## The ten stage blocks

The data track contains exactly ten `STG` blocks, all on track 2:

| name | sector | name | sector |
|------|--------|------|--------|
| STG1A | 304 | STG4A | 544 |
| STG2A | 344 | STG4B | 584 |
| STG2B | 384 | STG4C | 624 |
| STG2C | 424 | STG5A | 664 |
| STG3A | 464 | | |
| STG3B | 504 | | |

Each block is exactly **40 user sectors = 81920 bytes** and starts with its
ASCII name.  Verified layout (`tools/extract_stg_assets.py`):

```
+0x000  header
+0x200  palette / colour tables (live CRAM words start around +0x264)
+0x800  compressed stream (BAT / tilemap)
+0xC00  Shift-JIS stage text
+0x1000 object / level records (5-6 byte records)
+0x6E40 raw 4bpp tile graphics, 32 bytes per tile
```

There are **1678 tiles** in every block (`0x14000 - 0x6E40 = 0xD1C0` bytes).
The first 64 tiles map one-to-one to VRAM `0x100-0x13F`; later groups map in
64-tile banks with a constant delta (VRAM `0x180-0x1BF`, `0x200-0x23F`,
`0x300-0x33F`, `0x400-0x43F`, ...), interleaved with 0x126-tile block chunks.
The live Stage 2 VRAM confirms 802 of the 1678 block tiles somewhere in VRAM
(gaps are duplicates/unused tiles); the first bank matches exactly.

The palette at `+0x264` is the same table family as the live CRAM: 61 of 64
16-byte CRAM chunks are found in that palette region of STG2A.

The BAT itself is not stored raw: the 64x64 map is built by the game from the
`+0x800` stream and/or the object records.  That is the remaining decode
step for stages other than Stage 2; the raw tile and palette data for all ten
stages are already extracted.

## Tools

```
python3 tools/extract_stg_assets.py     # ten blocks -> build/stg_extract/
python3 tools/extract_state_stage2.py   # live Stage 2 -> build/state_stage2/
python3 tools/valis_toc.py              # 72-track absolute TOC
python3 tools/run_full_disc.py          # full-disc run (track 6 / ADPCM)
python3 tools/pce_state.py STATE.mc0    # list Mednafen state variables
```

## Port integration (Stage 2, verified)

`tools/pack_stage_state.py` turns the captured Stage 2 snapshot into the
Mega CD resource format:

```
game/res/gfx/stage2_state_tiles.bin   46 tiles / 1472 B
game/res/gfx/stage2_state_maps.bin    4 screens x 32x24 / 6144 B
game/res/gfx/stage2_state_pal.bin     4 MD palettes / 128 B
```

`game/src/stage2_state.c` + `stage2_state_res.s` build `STAGE2.MMD`
(9084 B).  `game/src/spx.c` registers `"STAGE2.MMD;1"` as module 3 and
`game.c` jumps to it after START.  The final disc was rebuilt with
`tools/build_megacd.ps1` -> `tools/mcd_make_disc.py`; `tools/verify_all.py`
reports 41 PASS / 0 FAIL and the data ISO contains `STAGE2.MMD`.

Remaining: only Stage 2 has a captured BAT.  Stages 1 and 3-10 have their
raw tiles and palettes extracted, but their maps still need the BAT/object
decoder.
