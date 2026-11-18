/* Bounded cell movement shared by captured stage modules. */
#ifndef STAGE_SCROLL_H
#define STAGE_SCROLL_H

static unsigned short stage_scroll_step(unsigned short cell, unsigned short screens,
                                        int left, int right)
{
  unsigned short last = (screens - 1) * 32;
  if (left && !right && cell > 0) return cell - 1;
  if (right && !left && cell < last) return cell + 1;
  return cell;
}

#endif
