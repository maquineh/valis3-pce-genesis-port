# Valis III - PC Engine CD → Sega Mega CD port

Port of **Valis III** (PC Engine CD-ROM², `Valis_3_(NTSC-J)_[TJCD0009]`,
Telenet/Laser Soft, 1990) to the **Sega Mega CD**, with all stages and the
original CD audio soundtrack.

## Status

| Piece | State |
|---|---|
| Disc split (18 data tracks + 54 CD-DA audio tracks) | ✅ `tools/cue_split.py` |
| Original soundtrack extracted (54 tracks, ~44 min, all verified non-silent) | ✅ `tools/audio_inventory.py` |
| HuC6280 disassembler + CD BIOS loader table decoded | ✅ `tools/disasm6280.py`, `tools/find_bios_calls.py`, `tools/decode_cd_calls.py` |
| Sector → file offset mapping (sector N = byte N×2352) | ✅ verified (title tiles) |
| Title screen graphics: tiles + BAT + palette extracted & rendered | ✅ `tools/render_bat.py` |
| PCE → Mega Drive tile/palette/map converter | ✅ `tools/pce2md.py` |
| Mega CD build toolchain (megadev + m68k gcc + mkisofs) | ✅ `tools/megacd-build/` + `tools/build_megacd.ps1` |
| Bootable Mega CD ISO (boot sector, security code, IP/SP, IPX, game module) | ✅ `game/` → `dist/valis3_mcd.iso` |
| Original soundtrack burned as CD-DA tracks + `.cue` | ✅ `tools/mcd_make_disc.py` |
| Title screen running on Mega CD (tiles/map/palette + CD-DA music) | ✅ built (see `game/src/game.c`) |
| Stage 1 graphics + stage module (scrolling + player sprite) | 🚧 first screen in |

## Where things are

- `tools/` – all extraction / conversion / build tools (Python 3).
  - `tools/cue_split.py` – splits the source PC Engine image (18 data tracks +
    54 CD-DA audio tracks); the image has no per-sector CD metadata, so it is
    a continuous 2352-byte/frame stream.
  - `tools/disasm6280.py` – HuC6280 (65C02 + block transfers) disassembler.
  - `tools/find_bios_calls.py`, `tools/decode_cd_calls.py`,
    `tools/list_vram_reads.py` – decode the game's CD-ROM² System Card loader
    (sector → VRAM/RAM/MPR destinations).
  - `tools/find_maps.py`, `tools/render_bat.py`, `tools/extract_screens.py` –
    locate PC Engine screen maps (BATs) and render them with their tiles.
  - `tools/pce2md.py` – convert PC Engine tiles / palettes / maps to Mega
    Drive format.
  - `tools/build_megacd.ps1` – builds `game/` inside the `megacd-build`
    Docker image (megadev + m68k gcc + mkisofs).
  - `tools/mcd_make_disc.py` – assembles the final Mega CD disc (data ISO +
    the original soundtrack as CD-DA tracks + `.cue` + track manifest).
  - `tools/verify_all.py` – checks every deliverable end to end.
- `game/` – the Mega CD source (megadev project: `src/`, `res/`, `makefile`).
- `game/res/gfx/` – assets converted from the PC Engine disc (title screen).
- `dist/` – the built disc: `valis3_mcd.iso` + `valis3_mcd.cue` +
  `valis3_mcd_audio/` (the original soundtrack as WAV) + `valis3_mcd.json`
  (track manifest used by the game code).
- `docs/findings.md` – everything learned about the original disc.
- `docs/hardware-limits.md` – Mega Drive / Mega CD VDP limits (80 sprites,
  20 per line, 64 colours) that constrain this port.

## Build

```powershell
# 1) build the toolchain image once (megadev + m68k-gcc + mkisofs)
docker build -t megacd-build C:\projetos\tools\megacd-build

# 2) build the Mega CD ISO
powershell -ExecutionPolicy Bypass -File tools/build_megacd.ps1

# 3) assemble the final disc with the original soundtrack
python3 tools/mcd_make_disc.py build/valis3.iso dist/valis3_mcd all
```

`dist/valis3_mcd.cue` + `dist/valis3_mcd.iso` + `dist/valis3_mcd_audio/*.wav`
is the playable disc.
