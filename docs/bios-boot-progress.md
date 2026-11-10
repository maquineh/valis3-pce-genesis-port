# Real System Card v3.0 boot — progress (this pass)

The emulator now runs the **real, unshimmed** Japanese Super System Card
(`syscard3.pce`) from its reset vector and gets as far as the game's own boot
block.

## What was wrong in the core

Several HuC6280 bugs had been masking the CD work.  All are fixed in
`tools/pce_cpu.py` and covered by `tools/test_cpu.py` (16/16 PASS):

| bug | fix |
|---|---|
| Block-transfer operands (`TII/TDD/TIN/TIA/TAI`) decoded **big-endian** | little-endian, as every 6502 word |
| `TIA` duplicated each source byte | alternates the destination (`dst`, `dst+1`) — this is how bytes stream into the VDC ports `$0002/$0003` as VRAM words (MAME `h6280.cpp`) |
| `TAI` repeated each byte four times | alternates the 2-byte source pattern |
| `BSR` pushed `pc-1` before fetching the operand | returns to the byte after the instruction |
| `NOP`, `PHX/PHY/PLX/PLY`, `STZ abs,X`, `BIT #imm` missing | implemented |
| `BBS/BBR` branch condition inverted | BBS branches when the bit is set, BBR when clear |
| `TSB/TRB` did not set/reset bits | implemented |
| `TST #imm,addr` decoded as a 2-byte immediate | dedicated 3/4-byte modes (`$83/$93/$A3/$B3`) |
| Zero page shared the MPR0 I/O bus | dedicated always-RAM zero-page bus (`$1F0000-$1F00FF`) |

The zero-page split matters most: with `MPR0=$FF`, the System Card's IRQ
handler does `STA $F6` (zero page) and later `LDA $0000` (absolute VDC
status).  Sharing one bus made `$F6` always read back 0, so the handler never
advanced the frame counter at `$2241` and every `ex_vsync` wait hung.

## Drive emulation (`tools/pce_system.py`)

The CD unit is a SCSI device:

* `$18C0` unlock: `$AA` then `$55`;
* unit signature: `$18C1/$18C2 = $AA/$55`, ID at `$18C3`; same at
  `$18C5/$18C6/$18C7` (ID bit 7 selects the Super CD path);
* command block: `$81` prefix on `$1801`, `$81` on `$1800`, then a 6-byte CDB;
* status phases: `$D0` parameter request, `$C8` data byte, `$D8` result byte,
  `$F8` final; `$1802` bit7 is the byte handshake;
* `$1808` is the bulk sector port;
* DINFO (`$DE`) returns the real TOC: 72 tracks, track 2 starts at
  `00:44:65`, control bit 2 set (data).

## Verified run

```
$ python3 tools/trace_boot_real.py syscard3.pce 2000000
ROM syscard3.pce reset=$E0F3
steps 2000000  pc=$E870  mpr=FF F8 80 81 82 83 84 00
disc reads: [0, 1, 2, 3, 4, 5] count 14
VRAM writes: 19931 CRAM: 370
```

The BIOS initialises the VDC, detects the CD unit, scans the TOC, reads the
IPL sectors, compares the 1237-byte boot signature against the card's table at
physical `$3FAE1`, and calls the game's boot block at `$2B26`.

## The 74-byte check was a false alarm

The boot block compares 74 bytes at `$3020` with `$DFB6` (MPR6=$1F ->
physical ROM `$3FFB6`).  The reference is the copyright string
`PC Engine CD-ROM SYSTEM / Copyright HUDSON SOFT / NEC Home Electronics`.
`$3020` is in **sector 1**, and sector payloads are 2048 bytes inside a
2352-byte frame.  The correct file offset is therefore
`1*2352 + 16 + 0x20 = 0x960`, not `0x820`.  At `0x960` the disc contains the
same 74-byte string and the check passes.

## Startup/title program

After the check, the boot block loads track-relative sector 8 (4 sectors) to
logical `$4000` with MPR2=$80 (physical `$100000`) and jumps there.  That
overlay is the disc's startup program ("Start up program by JUNPEH").  It:

* reads sector 12 (40 KB) to VRAM word `$1000` and sector 40 (8 KB) to
  VRAM word `$7000` — the title tiles;
* uploads the palettes and VDC tables;
* runs a title/menu loop at logical `$412C`, polling the BIOS joypad edge
  byte `$222D`.

The 2352-byte sector stride had been ignored in the earlier static analysis,
which is why the title tiles/maps never resolved.  With the real BIOS the
tiles are now in VRAM (see `build/gfx/game_boot_tiles100.png`).

The PCE pad is read as two active-low nibbles selected by `$1000`: the first
read is directions, the second is buttons (Run = bit 3).  This is now
emulated in `tools/pce_system.py`.

## Stage-block payload re-analysis

The earlier stage renders used raw 2352-byte sectors, which cross the CD
header/ECC every 2352 bytes.  A payload-contiguous image
(`build/track_02_payload.bin`, 2048 bytes/sector) was built and `STG1A` at
sector 304 re-examined.  The block starts cleanly with `STG1A`, but the
candidate maps at +0x29F0/+0x2A00 contain random-looking tile fields
(`0xd1d`, `0xc1c`, `0x222`, `0x303`, palettes 0..14), not a narrow BAT.
Regions of the block are all-zero, so the stage data is compressed/encoded
rather than a plain map+tile block.  No loader or decompressor for this
format has been identified.

The other data tracks were also checked.  Track 6 (payload-contiguous) has a
**coherent 4bpp tile sheet at offset 0**, but its 0x600-byte BAT candidates
render black (palette 0 dominates) and do not describe a screen.

Treating the STG1A map as byte-swapped and 28 rows (the PCE screen height)
produces coherent repeated bands, but the words are `0x0100` runs and
pattern-like tile values (`0x51d`, `0x41c`, `0x222`, `0x303`) with many
zeros — not a valid 32x28 BAT.  Rendering the first 896 track-6 tiles in
sequential screen order is almost entirely black, so the track-6 tile sheet
is a tileset, not a screen-order stream.  The stage map/palette encoding is
therefore still unknown.

## Remaining blocker

The title/menu loop runs.  Forcing the START branch (`$4167` -> `$42AA`)
leads to a fade/wait loop at `$44DA`.  Forcing the resident-overlay path
(`$42E8`) reads sectors 32–39 (absolute 3247–3254) and executes the overlay,
but it returns to the title loop at `$412C`; it is the title/menu engine, not
the game.

With enough emulated frames (IRQ every 2000 steps, 12M steps) the START path
also reads **sectors 976–987**.  That payload starts with

```
80 21 "VALIS III ACT0 visual by Junpeh "
```

and is a **graphic act-title card, not code**: after the read the string is
found in VRAM, not in physical RAM, and a `cd_exec`-pattern scan of the image
only finds false positives inside the bitmap data.  The loader sites reported
for this overlay in the old notes are therefore not executable entry points.

The overlays at 968/1172 are also visual programs
(`"VALIS III OPENING visual by Junpeh"`).  They execute 976 (the act card),
32 (resident overlay) and 956 (a **VISUAL DEBUGGER Ver1.40 by Junpeh**).
Running the 956 overlay directly loads sectors 40–43 and writes 40 KB of
VRAM, but the resulting screen is a blank debugger panel (the tool expects a
development/serial side), not a stage selector reachable from the joypad.

A scan of all eight 4-sector code chunks (988, 1000, 1020, 1040, 1060, 1080,
1120, 1128) shows that none reads the stage blocks at sectors 304–704.  They
load only visual/opening/omake sectors (24/32/44/56/1124/1236/1268/1284…):

```
1000: read 32 (24 sectors) -> $1000 dh=FF ; read 56 (8) -> $1000 dh=05
1020: read 29 (20) -> $1000 ; read 49 (12) -> $1000
1040: read 27 (20) -> $0000 ; read 47 -> $1000 dh=FE
1060: read 0 (24) -> $1000 ; read 55 (12) -> $0000
1080: read 24 (20) -> $0000 ; read 44 -> $1000 dh=FE
1120: read 1124 (2) -> $0000 ; read 32 (8) -> $0000 ; read 64 (20) -> $2000
1128: read 1236/1268 -> $1000 dh=FE ; read 1284 (16) -> $1000
```

The separate `Valis III (Japan).zip` is the **retail cue/bin set** (72
tracks).  Its track 2 has an explicit 225-sector pregap (INDEX 00 at
00:00:00, INDEX 01 at 00:03:00), and:

```
zip track2[225*2352:] MD5 = e885c79e62e348de85822917b7809fdb
current track_02.bin MD5  = e885c79e62e348de85822917b7809fdb
```

So the data is identical; the project cue had simply placed track 2 at the
**pregap start** (`00:44:65`) instead of INDEX 01 (`00:47:65`).  The TOC in
`tools/pce_system.py` now reports `00:47:65` and `tools/emu_game.py` rebases
absolute LBAs at 3440 instead of 3215.

The game still stops after the act-title card and issues reads with the
24-bit LBA `-150` (track-1 lead-in/audio).  The emulator now maps negative
LBAs to the retail CD-DA track 1 (`build/retail/...Track 01.bin`), enables an
audio phase for positive LBAs below 3440, implements vendor SCSI `D8/D9` and
a bounded `cd_stat` "playing" state (5000 polls), and can stub
`cd_play/search/pause/stat` at the BIOS jump table.  Even with all of that,
the opening stops after reading lead-in sectors `-150..-25` (126 distinct
reads) and never reaches the stage engine.  No per-stage VRAM/BAT dump
exists yet.

## Hidden stage-select attempt

The Japanese title screen has a documented hidden stage select: hold
Up+Left+I+II, then press RUN.  The emulator now feeds the two active-low
joypad nibbles (`joy_high=0x06`, `joy_low=0x0C`, then `0x04` with RUN) and the
combo does reach a new code path.  It then jumps into work RAM at `$0194`,
walks a data table (`E2 E8 E2 E8 ...`) and dies at `$0202`; the MPRs end up
holding code bytes (`F8 80 C0 A9 45 85 C1 20`).  This is a title/CPU/stack
issue, not a missing disc overlay: no new sector is read.  No stage-select
screen or stage VRAM was captured.

The follow-up trace shows the CPU entering zero-filled work RAM at `$0162`
(return address `$4183`) and walking forward to `$0194`; the MPRs become
`F8 80 C0 A9 45 85 C1 20` (code bytes).  No `TII/TIA/TDD/TIN` with
destination `$0162` exists in the disc code, so the intended routine/vector
is not being set up correctly by the emulated title path.  This remains a
title/MPR/stack emulation bug, not a missing stage-select overlay.

The stack return `$4183` corresponds to the startup overlay's
`$4181 JSR $4360`, i.e. the title's **CONTINUE** branch, not the hidden
stage-select code.  The combo is being interpreted as CONTINUE/confirm and
`$4360` calls a RAM routine that is not populated (likely the save-manager
path).  The hidden stage-select trigger itself has not been reached.

**Stages 2–10 are still not delivered.**  The soundtrack, bootable Mega CD
ISO and the BIOS/title execution are verified; the game stages are not.
