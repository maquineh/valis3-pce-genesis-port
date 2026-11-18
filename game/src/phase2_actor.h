#ifndef VALIS_PHASE2_ACTOR_H
#define VALIS_PHASE2_ACTOR_H

/* Four linked hardware sprites cover each PCE actor. Flip the positions of
 * both horizontal pieces along with their pixels to keep the sword attached. */
static void draw_actor(u8 slot, u16 tile, s16 x, s16 y, u8 width, u8 height,
                       u8 palette, u8 flip, u8 visible, u8 last_slot)
{
  for (u8 row = 0; row < 2; ++row) {
    u8 h = row ? height - 32 : 32;
    for (u8 col = 0; col < 2; ++col, ++slot) {
      u8 w = col ? width - 32 : 32;
      s16 left = x + (flip ? width - col * 32 - w : col * 32);
      bios_sprlist[slot].pos_x = 128 + left;
      bios_sprlist[slot].pos_y = visible ? 128 + y + row * 32 : 0;
      bios_sprlist[slot].width = w / 8 - 1;
      bios_sprlist[slot].height = h / 8 - 1;
      bios_sprlist[slot].tile = tile;
      bios_sprlist[slot].palette = palette;
      bios_sprlist[slot].priority = 1;
      bios_sprlist[slot].h_flip = flip;
      bios_sprlist[slot].v_flip = 0;
      bios_sprlist[slot].next = slot == last_slot ? 0 : slot + 1;
      tile += (w / 8) * (h / 8);
    }
  }
}

#endif
