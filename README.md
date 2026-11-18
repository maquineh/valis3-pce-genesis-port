# Valis III — PC Engine CD → Sega Mega CD port

Port of **Valis III** (PC Engine CD-ROM², `Valis_3_(NTSC-J)_[TJCD0009]`,
Telenet/Laser Soft, 1990) to the **Sega Mega CD**.

## Honest status

| Piece | State |
|---|---|
| Disc split (18 data tracks + 54 CD-DA audio tracks) | ✅ `tools/cue_split.py` |
| Original soundtrack inventory | ⚠️ `tools/audio_inventory.py` checks extracted tracks when available |
| HuC6280 disassembler + CD BIOS loader table decoded | ✅ `tools/disasm6280.py`, `tools/decode_cd_calls.py` |
| PCE → Mega Drive tile/palette/map converter | ✅ `tools/pce2md.py` |
| Mega CD build toolchain (megadev + m68k gcc + mkisofs) | ⚠️ `tools/build_megacd.ps1` requires a working Docker daemon and a locally available `megacd-build` image |
| Mega CD ISO and CD-DA disc builder | ⚠️ Build scripts provided; run `tools/verify_all.py` to check the artifacts available locally |
| Original soundtrack as CD-DA + `.cue` | ⚠️ Disc builder provided; the soundtrack files and final disc must be present locally |
| Title screen | ✅ Original PC Engine logo and menu captures combined with an interactive selector; CONTINUE restores the last saved prototype scene (`docs/title-capture.md`) |
| HuC6280 CPU core + VDC/VCE + CD BIOS shim | ✅ `tools/test_cpu.py` (16/16 PASS) |
| **Real System Card v3.0 boot (unshimmed)** | ✅ New Game reaches and executes track-20 `ACT0`; the extended run stops at `$20D8` on opcode `$0B` before any `STG` read. See `docs/bios-boot-progress.md` for verified sector ranges. |
| **Ten selectable scenes** | Captures cover six STG blocks. The sanctuary and alternate graveyard support horizontal exploration and checkpoints (`docs/stage-status.md`) |
| **Stages 3B, 4B, 4C, 5A** | Gameplay captures are still needed |
| Stage 1 module | ⚠️ present, but its graphics are an **unverified placeholder** with the wrong tile base (`docs/stage-1-correction.md`) |

**The objective — a port with all ten stages — is not met.** What is
provided in source are an interactive menu built from original captures and
ten experimental scenes based on real game snapshots. The earlier prototypes support
movement and jumping using manually approximated collision geometry, plus
placeholder enemies, attacks, damage and scene progression. They are not
complete stages and do not reproduce the original gameplay. CONTINUE restores
the saved position after returning to the menu. Local disc and audio artifacts
must be checked with the verifier.

## Why the remaining stages are missing

The game does **not** store ready-made background maps for the stages on the
disc: the BAT is **generated at run time** by a routine that has not been
located yet (`docs/map-generator-notes.md`).  What the disc *does* contain is
the raw 4bpp tile art and the palettes of all ten stages — they are extracted
into `build/stg_extract/` (`docs/stg-format.md`) — but the map stream itself is
compressed and its decompressor is still unknown.

The emulator in `tools/` runs the **real Japanese Super System Card v3.0**
from reset against the complete 72-track TOC. A RUN press on New Game reads
the opening program, later data on track 2, and executes the track-20 `ACT0`
visual module. A longer run advances beyond its VSync animation but stops at
`$20D8` on opcode `$0B`, before another CD read or any `STG` block. The ACT0
exit and stage BAT decoder remain unresolved (`docs/bios-boot-progress.md`).

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
- `docs/megacd-validation.md` — the latest disc build, runtime test limits,
  and the known title-map issue.

## Next step: resolve the ACT0 exit

The current reset path reaches and executes the timed `ACT0` module, then
stops at `$20D8` on opcode `$0B`. Trace the invalid control flow and the
preceding `$4D41` call before expecting a stage read. Save states remain
available for filling the missing scenes:

Provide Mednafen **save states** for each remaining uncaptured block — STG3B, STG4B, STG4C and STG5A (press F5 during play, with the terrain on
screen). STG4A now has an experimental scene based on its captured BAT. `tools/extract_state.py` +
`tools/pack_state_window.py` can turn a state into a Mega CD scene module
without touching the CD drive emulation. Additional work is still required to
reconstruct complete stages and gameplay.

## Where things are

- `tools/` – extraction, conversion and build tools (Python 3).
- `game/` – the Mega CD source (megadev project: `src/`, `res/`, `makefile`).
- `dist/` – destination for the generated disc image, cue, soundtrack WAVs,
  and manifest; these artifacts may not be present in a fresh checkout.
- `docs/` – all findings, including the honest gaps.

## Build

Extract the original disc first. The extractor supports a CUE that references
one raw image or multiple BIN files; the generated audio is used by the disc
builder. Data tracks remain in their source sector format, so raw MODE1/2352
tracks retain their headers and are not interchangeable with headerless dumps.

```powershell
py -3 tools/cue_split.py "PATH\TO\Valis III (Japan).cue" build/extracted
```

With Docker running and the `megacd-build` toolchain image installed locally:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_megacd.ps1
py -3 tools/mcd_make_disc.py build/valis3.iso dist/valis3_mcd all
py -3 tools/verify_all.py
```

### Native Windows alternative

`tools/build_megacd_native.ps1` builds the same data ISO without Docker or
WSL. The tested dependencies are Git for Windows; the Windows binaries in
[SGDK v2.11](https://github.com/Stephane-D/SGDK/releases/tag/v2.11) (GCC
13.2); [Megadev](https://github.com/drojaazu/megadev) at commit
`7a7246c14b845ad2f1bd3c7d73afb04cf67d83ef`; and xorriso 1.5.2. The tested
Windows xorriso executable and its Cygwin DLLs are a
[third-party Windows build](https://github.com/PeyTy/xorriso-exe-for-windows),
commit `9236798071b26ab7032cd82b4a5635fcf7c1409c`.

The current machine has these dependencies under `%TEMP%`, where they may be
removed by the operating system. They can be restored with:

```powershell
git clone https://github.com/drojaazu/megadev.git "$env:TEMP\valis-megadev"
git -C "$env:TEMP\valis-megadev" checkout 7a7246c14b845ad2f1bd3c7d73afb04cf67d83ef
curl.exe -L --fail -o "$env:TEMP\valis-sgdk.7z" https://github.com/Stephane-D/SGDK/releases/download/v2.11/sgdk211.7z
New-Item -ItemType Directory -Force "$env:TEMP\valis-sgdk" | Out-Null
tar -xf "$env:TEMP\valis-sgdk.7z" -C "$env:TEMP\valis-sgdk"
git clone https://github.com/PeyTy/xorriso-exe-for-windows.git "$env:TEMP\valis-xorriso"
git -C "$env:TEMP\valis-xorriso" checkout 9236798071b26ab7032cd82b4a5635fcf7c1409c
powershell -ExecutionPolicy Bypass -File tools/build_megacd_native.ps1
```

The tested SGDK archive has SHA-256
`5cc704b7e3a15183c33e721a1d7f84c067cf78808754556d03bb14764df51437`.
For dependencies installed elsewhere, pass `-Megadev`, `-Sgdk` and `-Xorriso`
with their full paths; the last parameter is the path to `xorriso.exe`.
The Megadev path cannot contain spaces. Build logs, modules and ELF symbols
are kept under `build/native-artifacts/`. After building, run the disc builder
and verifier shown above.
