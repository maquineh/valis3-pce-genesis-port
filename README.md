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
| **Real System Card v3.0 boot (unshimmed)** | ✅ from reset `$E0F3`: VDC init → CD unit detection → TOC scan → 1237-byte signature verify → boot block at `$2B26` → disc startup/title program (`$100000`) with title tiles in VRAM (`tools/trace_boot_real.py`, `tools/boot_capture.py`, `docs/bios-boot-progress.md`) |
| **Stages 2, 2A room 2, 2B, 2C, 3A** | ✅ migrated from real Mednafen save states → `STAGE2/2A2/2B/2C/3A.MMD` (`docs/stage-status.md`) |
| **Stages 1, 3B, 4A/B/C, 5A** | ❌ **not delivered** (no gameplay save state captured yet) |
| Stage 1 module | ⚠️ present, but its graphics are an **unverified placeholder** with the wrong tile base (`docs/stage-1-correction.md`) |

**The objective — a port with all ten stages — is not met.** What is
delivered and verified is the complete original soundtrack, the title screen,
a bootable Mega CD disc and five stages captured from the real game.

## Why the remaining stages are missing

The game does **not** store ready-made background maps for the stages on the
disc: the BAT is **generated at run time** by a routine that has not been
located yet (`docs/map-generator-notes.md`).  What the disc *does* contain is
the raw 4bpp tile art and the palettes of all ten stages — they are extracted
into `build/stg_extract/` (`docs/stg-format.md`) — but the map stream itself is
compressed and its decompressor is still unknown.

The emulator in `tools/` now boots the **real Japanese Super System Card
v3.0** from reset, detects the CD unit, scans the 72-track TOC, reads the
disc, plays the CD-DA soundtrack and executes the title and overlay programs
(`docs/bios-boot-progress.md`).  It still does not reach the stage engine on
its own: the opening waits on the CD-DA playback state, and the hidden
stage-select path needs the save/BRAM flow emulated.

Because of that, the working path for the stages is **capture from a real
emulator**: one Mednafen save state per stage, decoded by
`tools/pce_state.py` / `tools/extract_state.py` and packed by
`tools/pack_state_window.py` into a Mega CD module.

- `docs/stg-format.md` — the ten `STG` blocks on track 2 (40 sectors each),
  their internal layout, the extracted tiles/palettes and the state pipeline.
- `docs/stage-status.md` — which stages are migrated, from which save state,
  and the exact steps to migrate the next one.
- `docs/map-generator-notes.md` — the static decoding attempts (and why the
  terrain loader is still unlocated).

## Fastest way to finish

Provide Mednafen **save states** with each remaining stage loaded — the
missing ones are STG1A, STG3B, STG4A, STG4B, STG4C and STG5A (press F5 during
play, with the terrain on screen).  `tools/extract_state.py` +
`tools/pack_state_window.py` then turn each state into a Mega CD stage module
without touching the CD drive emulation.

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
