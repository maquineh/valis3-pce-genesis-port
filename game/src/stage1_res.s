/* Stage 1 resources packed from the PC Engine original.
 *
 *   tiles  : PC Engine track 2, file offset $19440 (cd_read sector $2C ->
 *            VRAM word $1000, 48 KiB) - 451 distinct tiles used by the map
 *   map    : PC Engine track 2, file offset $17FF90 (BAT, 32x28 words)
 *   palette: VCE colour block at $9352 (64 BG colours)
 * Packed + converted to Mega Drive format by tools/pack_stage.py.
 * player_spr.bin is engine test art (tools/gen_player_spr.py) until the real
 * character sprites are decoded (docs/findings.md, Open items).
 */

.section .rodata
#include <macros.s>

GLABEL res_stage1_tiles
.incbin "../res/gfx/stage1_tiles.bin"
.align 2

GLABEL res_stage1_pal
.byte 0
.byte 63
.incbin "../res/gfx/stage1_pal.bin"
.align 2

GLABEL res_stage1_map
.incbin "../res/gfx/stage1_map.bin"
.align 2

GLABEL res_player_spr
.incbin "../res/gfx/player_spr.bin"
.align 2
