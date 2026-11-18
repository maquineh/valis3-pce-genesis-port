/* Host test of the exact movement function used by all captured stages. */
#include "../game/src/stage_scroll.h"

int main(void)
{
  unsigned short cell = 0;
  unsigned short i;
  if (stage_scroll_step(cell, 4, 1, 0) != 0) return 1;
  if (stage_scroll_step(cell, 4, 1, 1) != 0) return 2;
  for (i = 1; i <= 96; ++i) {
    cell = stage_scroll_step(cell, 4, 0, 1);
    if (cell != i || cell / 32 != i / 32) return 3;
  }
  if (stage_scroll_step(cell, 4, 0, 1) != 96) return 4;
  for (i = 96; i > 0; --i) {
    cell = stage_scroll_step(cell, 4, 1, 0);
    if (cell != i - 1 || cell / 32 != (i - 1) / 32) return 5;
  }
  if (stage_scroll_step(32, 2, 0, 1) != 32) return 6;
  if (stage_scroll_step(32, 2, 1, 0) != 31) return 7;
  return 0;
}
