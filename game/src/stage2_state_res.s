.section .rodata
#include <macros.s>

GLABEL res_stage2_state_tiles
.incbin "../res/gfx/stage2_state_tiles.bin"
.align 2

GLABEL res_stage2_state_pal
.byte 0
.byte 63
.incbin "../res/gfx/stage2_state_pal.bin"
.align 2

GLABEL res_stage2_state_maps
.incbin "../res/gfx/stage2_state_maps.bin"
.align 2

GLABEL res_stage2_actors
.incbin "../res/gfx/stage2_state_actors.bin"
.align 2

GLABEL res_stage2_hud
.incbin "../res/gfx/stage2_state_hud.bin"
.align 2
