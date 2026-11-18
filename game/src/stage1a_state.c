/* Two adjacent display windows packed from the STAGE1A capture. */
#include "captured_window.h"

#define STAGE_SCREENS 2
#define STAGE_TILES 187

extern u8 res_stage1a_state_tiles[], res_stage1a_state_pal[], res_stage1a_state_maps[];

void main(void)
{
  captured_window(FILE_STAGE1A_MMD, STAGE_SCREENS, STAGE_TILES,
                  res_stage1a_state_tiles, res_stage1a_state_pal, res_stage1a_state_maps);
}
