#ifndef VALIS3_CAPTURED_WINDOW_H
#define VALIS3_CAPTURED_WINDOW_H

#include "scene_save.h"
#include <main/bios.h>
#include <main/io.def.h>
#include <main/memmap.h>
#include <main/vdp.h>

extern u8 next_module;
extern u8 res_player_spr[];

/* Each imported capture has two 32x24 maps. Both fit side by side on a
 * 64-cell plane, so movement only needs to update the horizontal scroll. */
static void captured_window(u8 scene, u8 screens, u16 tile_count,
                            u8 *tiles, u8 *palette, u8 *maps)
{
  static vdp_reg const registers[] = {
    (VDP_REG_PL_SIZE & 0xFF00) | (VDP_PL_W64 | VDP_PL_H32), VDP_REG_MODE4, 0
  };
  u16 blank_tile[16] = {0};
  u16 x = 0, y = 96;
  u16 width = screens * 256;
  bios_load_vdp_regs_default();
  bios_load_vdp_regs(registers);
  bios_vdp_disp_disable();
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(0)), tiles, tile_count * 16);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(tile_count)), res_player_spr, 4 * 16);
  bios_dma_xfer(to_vdp_addr(vram_addr_from_tileidx(tile_count + 4)), (u8 *)blank_tile, 16);
  bios_load_pal_update((Palette *)palette);
  bios_palette[56] = 0x0eee;
  bios_palette[57] = 0x0ccc;
  bios_palette[63] = 0x0aaa;
  bios_vdp_update_flags |= BIOS_MASK_COPY_PALETTE;
  bios_plane_fill(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W, 63, 31, tile_count + 4);
  bios_plane_fill(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W, 63, 31, tile_count + 4);
  bios_vdp_disp_enable();
  for (u8 i = 0; i < screens; ++i)
    bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA + VDP_PLANE_POS(i * 32, 0, Width64)) | VRAM_W,
                  31, 23, maps + i * 32 * 24 * 2);

  engine_resume_position(scene, &x, &y);
  for (;;)
  {
    bios_vblank_wait_default();
    u16 pad = bios_joy1_hold & (PAD_LEFT | PAD_RIGHT);
    if (pad == PAD_LEFT) x = x >= 2 ? x - 2 : 0;
    if (pad == PAD_RIGHT) x = x <= width - 18 ? x + 2 : width - 16;
    u16 camera = x > 120 ? x - 120 : 0;
    if (camera > width - 256) camera = width - 256;
    u16 scroll[2] = { (u16)-camera, (u16)-camera };
    bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_HSCROLL), (u8 *)scroll, 2);
    bios_sprlist[0].pos_x = 128 + x - camera;
    bios_sprlist[0].pos_y = 128 + y;
    bios_sprlist[0].tile = tile_count;
    bios_sprlist[0].width = bios_sprlist[0].height = 1;
    bios_sprlist[0].palette = 3;
    bios_sprlist[0].priority = 1;
    bios_sprlist[0].next = 0;
    bios_copy_sprlist();
    if (bios_joy1_hit & PAD_START) {
      engine_save_position(scene, x, y);
      next_module = FILE_GAME_MMD;
      return;
    }
  }
}
#endif
