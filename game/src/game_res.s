/* Title/menu capture converted to Mega Drive tile, palette and map data.
 * Tile zero is transparent; the map has 32x28 big-endian plane A entries
 * and the palette consists of four shared 16-color Mega Drive lines.
 * See the title resource metadata for the capture and conversion details. */

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
