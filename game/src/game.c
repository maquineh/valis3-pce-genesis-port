/* Valis III Mega CD - game module: title screen */

#include "shared.h"
#include "resource.h"
#include "engine.h"
#include <main/bios.h>
#include <main/io.def.h>
#include <main/memmap.h>
#include <main/vdp.h>
#include <system.h>
#include <types.h>

extern u8 next_module;
extern u8 res_title_tiles;
extern u8 res_title_pal;
extern u8 res_title_map;
/* Music: the original PC Engine soundtrack, burned as CD-DA tracks.
 * Disc track 2 = PCE track 1 (the title screen music). */
#define CDDA_TITLE 2

#define TITLE_TILES 768
#define TITLE_W 32
#define TITLE_H 28

/**
 * The PC Engine renders 240p as a 32x28 tile screen (256x224), which is the
 * Mega Drive's H32 cell mode. Set that explicitly (40-cell is the BIOS
 * default) so every PCE tile maps 1:1 onto the plane A grid.
 */
static vdp_reg const title_vdp_regs[] = {
    VDP_REG_MODE4,                             /* 32-cell mode, no interlace */
    0};

/* Load the PC Engine title screen assets into Mega Drive VRAM/CRAM.
 * PCE tiles were converted to MD tile format by tools/pce2md.py. */
static void title_load(void)
{
  /* palette: 64 colours (4 MD palette lines), CRAM line 0 */
  bios_load_pal_update((Palette *)&res_title_pal);

  /* tiles: upload at tile index 0 (the plane map uses indices 0..767) */
  bios_dma_xfer(
    to_vdp_addr(vram_addr_from_tileidx(0)),
    &res_title_tiles,
    (TITLE_TILES * 32) >> 1);

  /* plane A: clear it, then write the 32x28 PC Engine map (padded) */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    Width32, 28, 0);

  bios_load_map(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    TITLE_W - 1, TITLE_H - 1, &res_title_map);

  /* clear plane B behind the title art */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W,
    Width32, 28, 0);

  /* sprites: hide them all (empty SAT) */
  for (u8 i = 0; i < 80; i++)
  {
    bios_sprlist[i].pos_y = 160;
    bios_sprlist[i].pos_x = 320;
    bios_sprlist[i].tile = 0;
    bios_sprlist[i].palette = 0;
    bios_sprlist[i].width = 0;
    bios_sprlist[i].height = 0;
    bios_sprlist[i].next = 0;
  }
  bios_copy_sprlist();
}

void main(void)
{
  bios_load_vdp_regs_default();
  bios_load_vdp_regs(title_vdp_regs);
  bios_vdp_disp_disable();
  title_load();
  bios_vdp_disp_enable();

  /* play the original soundtrack (PC Engine track 1) */
  engine_play_cdda(CDDA_TITLE);

  /* wait for a START press */
  do
  {
    bios_vblank_wait_default();
    bios_read_joypad();
  } while (!(bios_joy1_hit & PAD_START));

  engine_stop_cdda();

  /* proceed to stage 1 */
  next_module = FILE_STAGE2_MMD;
}
