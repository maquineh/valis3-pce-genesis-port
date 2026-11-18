/* Two adjacent display windows packed from the STAGE4A capture. */
#include "captured_window.h"

#define STAGE_SCREENS 2
#define STAGE_TILES 303

extern u8 res_stage4a_state_tiles[], res_stage4a_state_pal[], res_stage4a_state_maps[];

void main(void)
{
  captured_window(FILE_STAGE4A_ALT_MMD, STAGE_SCREENS, STAGE_TILES,
                  res_stage4a_state_tiles, res_stage4a_state_pal, res_stage4a_state_maps);
}
