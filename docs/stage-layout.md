## Status: stages 2-10 are not delivered (honest state of the port)

The objective asks for all 10 stages plus the original soundtrack. What is
built and verified today:

| item | state | evidence |
|---|---|---|
| Original soundtrack (54 CD-DA tracks, ~50 min) | done | `dist/valis3_mcd.cue`, `dist/valis3_mcd.iso`, `dist/valis3_mcd_audio/*.wav`; `tools/audio_inventory.py` reports no silent track |
| Bootable Mega CD ISO with security code / IP / SP / kernel | done | `tools/verify_all.py` - `SEGADISCSYSTEM`, region `JUE`, ISO9660, contains `IPX.MMD`, `GAME.MMD`, `STAGE1.MMD`, `SPX.SMD` |
| Title screen (real PC Engine tiles/map/palette) + CD-DA music | done | `game/src/game.c`, `game/res/gfx/title_*`; rendered `build/gfx/title_final.png` |
| **Stage 1** - all 10 decoded screens, streaming + player sprite | done | `game/src/stage1.c`, `game/res/gfx/stage1_all_*` (1297 tiles), `tools/test_stage_logic.py` ALL PASS, contact sheet `build/gfx/stage1_screens.png` |
| Stages 2-10 | **not delivered** | - |

### Why 2-10 are blocked (tried this session, all evidence preserved)

1. The 0x600 map grid in `track_02` beyond stage 1 does not contain playfield
   BATs. Scans with a playfield signature (coverage in the tile block range +
   >=16-tile runs + >=150 distinct tiles) over:
   * `$17FF90-$240000` of `track_02`
   * `$000000-$B0000` of `track_02`
   * `$000000-$30000` of every stage track (`track_06`..`track_36`, 13-60
     candidates each)

   ...all render as tiles scattered over black (object/collision lists) or as
   dithered Japanese dialog frames, never as stage 1's terrain.
2. Block matching fails in every automatic form tried:
   `match_blocks.py` (render score), `assign_blocks.py` (art-tile fraction),
   `assign_by_range.py` (index-range coverage), `coherence.py` (4x4 pattern
   diversity), `palette_profile.py` (palette mix), tile bases
   `$100/$200/$300/$400/$500/$700/$800/$F00`, tiles from the stage tracks
   themselves, and `render_multi.py` (multi-VRAM-region tiles).
3. The stage tiles blocks are known (`tools/list_vram_reads.py`: sectors
   `$2C,$2F,$30,$34,$44,$4A4,$4D4,$4F4,$514`), but no map on the disc resolves
   against them except stage 1's.

### The two concrete ways forward (documented for the next turn)

1. **Decode the stage tracks' 4-byte records.** After ~190 KiB of dither
   artwork, each stage track carries records with an 86-byte structural
   period (`[00][lo][hi][flags]` then `[count][00][00][00]`, e.g.
   `track_06 @ $2E710`: `7DFE6B6A`/`062091F5`, `871FBDBE`/`0310C6`, ...).
   Simple `[count][lo][hi]` RLE decoding of the region after the artwork
   yields nonsense (tile values up to 65533), so the codec is not plain RLE and
   still needs its decoder written.
2. **Run the game and dump VRAM/BAT.** Blocked here by the missing PC Engine
   CD-ROM² System Card BIOS (no copyrighted BIOS is shipped in this repo). The
   next step is a HuC6280 core (opcode table already in
   `tools/disasm6280.py`) plus VDC/VCE register modelling and a CD BIOS shim
   implementing the nine functions the game actually calls (`cd_read`,
   `cd_exec`, `cd_play`, `cd_search`, `cd_base`, `cd_stat`, `cd_pause`,
   `cd_fade`, `ad_reset` - see `tools/find_bios_calls.py`).

Everything above is committed in `origin/main` (`6f98f8c`).
