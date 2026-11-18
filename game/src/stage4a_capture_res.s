.section .rodata
#include <macros.s>

GLABEL res_stage4a_capture_tiles
.incbin "../res/gfx/stage4a_hw2_tiles.bin"
.align 2

GLABEL res_stage4a_capture_pal
.byte 0
.byte 63
.incbin "../res/gfx/stage4a_hw2_pal.bin"
.align 2

GLABEL res_stage4a_capture_maps
.incbin "../res/gfx/stage4a_hw2_maps.bin"
.align 2

GLABEL res_stage4a_sprites
.incbin "../res/gfx/stage4a_sprites.bin"
.align 2
GLABEL res_stage4a_player_anim
.incbin "../res/gfx/stage4a_player_anim.bin"
.align 2
GLABEL res_stage4a_skull_anim
.incbin "../res/gfx/stage4a_skull_hw2.bin"
.align 2
GLABEL res_stage4a_column_anim
.incbin "../res/gfx/stage4a_column_hw2.bin"
.align 2
GLABEL res_stage4a_projectile
.incbin "../res/gfx/stage4a_projectile.bin"
.align 2
GLABEL res_stage4a_sprite_pal
.incbin "../res/gfx/stage4a_sprite_pal.bin"
.align 2
