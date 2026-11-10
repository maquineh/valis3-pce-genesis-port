/* Tile/palette/map resources converted from the PC Engine original.
 *
 * - title_tiles.bin : 1280 8x8 tiles, PC Engine 4bpp planar already converted
 *                     to Mega Drive tile order by tools/pce2md.py
 * - title_pal.bin   : 64 VCE colour words converted to Mega Drive CRAM words
 * - title_map.bin   : 32x28 plane A entries (tile index + palette line)
 *
 * Sources (PC Engine disc, track 2):
 *   tiles  : file offset $6E40  (cd_read sector $0C -> VRAM word $1000)
 *   map    : file offset $123D40 (PC Engine BAT, 32x28 words)
 *   palette: file offset $1F00  (VCE colour words, first 64 = BG palettes 0-3)
 */

.section .rodata
#include <macros.s>

GLABEL res_title_tiles
.incbin "../res/gfx/title_tiles.bin"
.align 2

/* Palette in megadev's Palette format: [cram_offset][count-1][words] */
GLABEL res_title_pal
.byte 0
.byte 63
.incbin "../res/gfx/title_pal.bin"
.align 2

GLABEL res_title_map
.incbin "../res/gfx/title_map.bin"
.align 2
