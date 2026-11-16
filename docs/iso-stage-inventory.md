# ISO stage inventory

Track 2 of `Valis_3_(NTSC-J)_[TJCD0009].cue` contains ten `STG` blocks of 40 user sectors (81920 B) each.  The header at `+0x10` is the stage index, `+0x11` the room/area count, `+0x13` the chapter.  Raw 4bpp tiles start at `+0x6E40`; palette data at `+0x264`; Shift-JIS text at `+0xC00`.

| block | sector | idx | rooms | ch | tiles | save state | module |
|-------|--------|-----|-------|----|-------|------------|--------|
| STG1A | 304 | 0 | 4 | 3 | 1678 | **no save state** | — |
| STG2A | 344 | 1 | 3 | 4 | 1678 | root `.mc0`, states `.mc0`/`.mc1` (room 1 + seaside) | `STAGE2.MMD` + `STAGE2A2.MMD` |
| STG2B | 384 | 2 | 2 | 4 | 1678 | root `.mc2` | `STAGE2B.MMD` |
| STG2C | 424 | 3 | 4 | 4 | 1678 | root `.mc3`, states `.mc2`/`.mc3` (dungeon + green room) | `STAGE2C.MMD` |
| STG3A | 464 | 4 | 3 | 5 | 1678 | root `.mc4`, states `.mc4` | `STAGE3A.MMD` |
| STG3B | 504 | 5 | 2 | 5 | 1678 | **no save state** | — |
| STG4A | 544 | 6 | 2 | 5 | 1678 | states `.mc9` | `STAGE4A.MMD` |
| STG4B | 584 | 7 | 3 | 5 | 1678 | **no save state** | — |
| STG4C | 624 | 8 | 3 | 5 | 1678 | **no save state** | — |
| STG5A | 664 | 9 | 4 | 6 | 1678 | **no save state** | — |

Tile sheets: `build/gfx/stg_inventory/<NAME>_tiles.png`; contact sheet: `build/gfx/stg_inventory/contact.png`.

The five blocks **STG1A, STG3B, STG4B, STG4C and STG5A** are present in the ISO with their tiles, palettes, text and object records, but no save state covers them.  Their BAT is generated at runtime, so a gameplay F5 state is required to pack them like the others.
