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

## Remaining blocker

The title/menu loop runs.  Forcing the START branch (`$4167` -> `$42AA`)
leads to a fade/wait loop at `$44DA`.  Forcing the resident-overlay path
(`$42E8`) does read sectors 32–39 (absolute 3247–3254) and execute the
overlay, but it returns to the title loop at `$412C`; it is the title/menu
engine, not the game.

The game engine/stages are not entered, so no per-stage VRAM/BAT dump exists
yet.

**Stages 2–10 are still not delivered.**  The soundtrack, bootable Mega CD
ISO and the BIOS/title execution are verified; the game stages are not.
