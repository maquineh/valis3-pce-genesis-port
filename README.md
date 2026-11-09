# Valis III: PC Engine CD -> Sega Mega CD port

Goal: port **Valis III (Valis 3)**, the PC Engine CD-ROM² title
`Valis_3_(NTSC-J)_[TJCD0009]`, to the **Sega Mega CD / Genesis CD**, with
**all stages** and the **original soundtrack**.

## Source
- `Valis_3_(NTSC-J)_[TJCD0009].iso` - raw 2352-byte-sector CD image (530 MiB),
  236278 sectors (52:30), 1 file disc.
- `Valis_3_(NTSC-J)_[TJCD0009].cue` - 72 tracks:
  16 MODE1/2352 **data** tracks, 56 **CD-DA** audio tracks (the soundtrack).

## Pipeline
1. `tools/cue_split.py` - splits the raw image into data-track payloads and
   WAV audio tracks + `tracks.json` manifest.
2. `tools/disasm6280.py` - HuC6280 (65C02) disassembler / code-density scan
   used to locate the game program and data tables.
3. `tools/map_tracks.py`, `find_code.py`, `find_palettes.py` - data-track
   structure analysis.
4. asset extraction (in progress) -> Genesis tile/palette/sprite conversion ->
   SGDK source -> bootable Mega CD `.iso`/`.cue` with the original CD-DA tracks.

See `docs/` for hardware notes and findings.

## Repo layout
- `tools/` - extraction / conversion tooling (Python 3).
- `docs/` - format documentation and findings.
- `build/extracted/` - regenerated from the ISO (not committed).
