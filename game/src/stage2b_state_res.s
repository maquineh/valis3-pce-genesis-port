.section .rodata
#include <macros.s>

GLABEL room_tiles
.incbin "../res/gfx/stage2b_state_tiles.bin"
.align 2

GLABEL room_palette
.byte 0, 63
.incbin "../res/gfx/stage2b_state_pal.bin"
.align 2

GLABEL room_map
.incbin "../res/gfx/stage2b_state_maps.bin"
.align 2

GLABEL room_actors
.incbin "../res/gfx/stage2b_state_actors.bin"
.align 2
