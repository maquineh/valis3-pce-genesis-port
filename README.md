# Valis III — PC Engine CD → Sega Mega CD port

Port of **Valis III** (PC Engine CD-ROM², `Valis_3_(NTSC-J)_[TJCD0009]`,
Telenet/Laser Soft, 1990) to the **Sega Mega CD**.

## Honest status

| Piece | State |
|---|---|
| Disc split (18 data tracks + 54 CD-DA audio tracks) | ✅ `tools/cue_split.py` |
| Original soundtrack (54 tracks, ~50 min, all non-silent) | ✅ `tools/audio_inventory.py` |
| HuC6280 disassembler + CD BIOS loader table decoded | ✅ `tools/disasm6280.py`, `tools/decode_cd_calls.py` |
| PCE → Mega Drive tile/palette/map converter | ✅ `tools/pce2md.py` |
| Mega CD build toolchain (megadev + m68k gcc + mkisofs) | ✅ `tools/build_megacd.ps1` |
| Bootable Mega CD ISO (security code, IP/SP, IPX, game module) | ✅ `tools/verify_all.py` (41 checks, 0 FAIL) |
| Original soundtrack burned as CD-DA + `.cue` | ✅ `tools/mcd_make_disc.py` |
| Title screen (real PC Engine tiles/map/palette + CD-DA music) | ✅ `game/src/game.c` |
| HuC6280 CPU core + VDC/VCE + CD BIOS shim | ✅ `tools/test_cpu.py` (16/16 PASS) |
| **Real System Card v3.0 boot (unshimmed)** | ✅ from reset `$E0F3`: VDC init → CD unit detection → TOC scan → sector reads → 1237-byte signature verify → game boot block at `$2B26` (`tools/trace_boot_real.py`, `docs/bios-boot-progress.md`) |
| **Stages 2–10** | ❌ **not delivered** |
| Stage 1 | ⚠️ module present, but its graphics are an **unverified placeholder** with the wrong tile base (`docs/stage-1-correction.md`) |

**The objective — a port with all ten stages — is not met.** What is
delivered and verified is the complete original soundtrack, the title screen,
and a bootable Mega CD disc.

## Why stages 2–10 are missing

The game does **not** store ready-made background maps for the stages on the
disc; the BAT only exists in VRAM at run time.  Earlier notes described a
~64 KiB playfield buffer shifted by 8 tiles at logical `$8790`; that reading
came from decoding the HuC6280 block-transfer operands big-endian.  The
operands are little-endian (like every 6502 word), so the real instruction is
a **one-byte** buffer shift, not an 8-tile shift.  The stage upload sequence
therefore still has to be traced from the game once it boots.

The real System Card v3.0 now boots and reads the disc in `tools/` (see
`docs/bios-boot-progress.md`).  The remaining blocker is the game boot block's
own 74-byte integrity check at `$2B26`, which compares `$3020` with the card's
signature table; until it passes the game code is not entered.

Recovering the stages requires **running the game**, and that work is
documented but incomplete:

- `docs/system-card-boot.md` — the verified System Card boot chain (the
  disc's boot sector matches the card's 1237-byte reference exactly).
- `docs/cd-protocol.md` — the CD drive register map (`$1800` status/command,
  `$1801` parameter/data, `$18C0` unlock, `$18C1-$18C7` results) derived from
  the card's own driver, plus the verified v3.0 boot path that ends in
  `JMP $4000` with `MPR2-6 = $04..$08`.
- `docs/stage-segments.md` — the ten stage segments (`STG1A`, `STG2A/B/C`,
  `STG3A/B`, `STG4A/B/C`, `STG5A`) at 40-sector intervals with their own VCE
  palettes.

The emulator reaches the point of executing the disc's boot code and issuing
a real `cd_read`, but the drive handshake is not complete, so the game never
boots to a playable screen and no per-stage VRAM dump exists.

## Fastest way to finish

Provide emulator **save states** (Mednafen or RetroArch + Beetle PCE) with
each stage loaded. `tools/pack_stage_all.py` can then pack the real VRAM
contents directly, without completing the CD drive emulation.

## Where things are

- `tools/` – extraction, conversion and build tools (Python 3).
- `game/` – the Mega CD source (megadev project: `src/`, `res/`, `makefile`).
- `dist/` – `valis3_mcd.iso` + `valis3_mcd.cue` + `valis3_mcd_audio/`
  (the original soundtrack as WAV) + `valis3_mcd.json`.
- `docs/` – all findings, including the honest gaps.

## Build

```powershell
docker build -t megacd-build C:\projetos\tools\megacd-build
powershell -ExecutionPolicy Bypass -File tools/build_megacd.ps1
python3 tools/mcd_make_disc.py build/valis3.iso dist/valis3_mcd all
python3 tools/verify_all.py
```
