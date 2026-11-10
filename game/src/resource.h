/* Valis III Mega CD - resources referenced from C */

#ifndef VALIS3_RESOURCE_H
#define VALIS3_RESOURCE_H

#include <types.h>

extern u8 res_title_tiles;
extern u8 res_title_pal;   /* megadev Palette: [cram_offset][count-1][words] */
extern u8 res_title_map;

/* packed resources are accessed as arrays (stage1_all_maps is 10 screens) */
extern u8 res_stage1_all_tiles[];
extern u8 res_stage1_all_pal[];
extern u8 res_stage1_all_maps[];

extern u8 res_player_spr[];

#endif
