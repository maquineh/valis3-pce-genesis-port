/* Valis III Mega CD - Stage 1 module.
 *
 * Loads the real PC Engine stage-1 screen (tiles/map/palette packed by
 * tools/pack_stage.py from track 2 map $17FF90 + tiles at $19440) into
 * Mega Drive VRAM, then runs the stage: plane A horizontal scrolling with the
 * player sprite.
 */

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
extern u8 res_stage1_tiles;
extern u8 res_stage1_pal;
extern u8 res_stage1_map;
extern u8 res_player_spr;

#define STAGE1_TILES 451
#define PLAYER_TILE 700    /* sprite tiles come after the stage art */
#define HSCROLL_ADDR 0xBC00 /* BIOS default horizontal scroll table */
#define SCREEN_W 32
#define SCREEN_H 28
#define MAX_SCROLL_X 96    /* the decoded screen is 320px wide (40 cells) */

typedef struct
{
  s16 x, y;
  s16 vx;
  u8 frame;
} Player;

static Player player;
static s16 scroll_x;

static vdp_reg const stage_vdp_regs[] = {
    VDP_REG_MODE4,                    /* 32-cell screen, no interlace */
    0};

static void stage_load(void)
{
  /* stage art at tile 0 */
  bios_dma_xfer(
    to_vdp_addr(vram_addr_from_tileidx(0)),
    &res_stage1_tiles,
    (STAGE1_TILES * 32) >> 1);

  /* palette: 64 colours (4 palette lines) */
  bios_load_pal_update((Palette *)&res_stage1_pal);

  /* plane A: clear then write the 32x28 PC Engine map */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    Width32, SCREEN_H, 0);
  bios_load_map(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    SCREEN_W - 1, SCREEN_H - 1, &res_stage1_map);

  /* plane B behind the stage */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W,
    Width32, SCREEN_H, 0);

  /* player sprite tiles */
  bios_dma_xfer(
    to_vdp_addr(vram_addr_from_tileidx(PLAYER_TILE)),
    &res_player_spr,
    (4 * 32) >> 1);

  /* white player palette line */
  bios_palette[48] = 0x0EEE;
  bios_palette[49] = 0x0EEE;
  bios_palette[50] = 0x0EEE;
  bios_vdp_update_flags |= BIOS_MASK_COPY_PALETTE;
}

static void player_init(void)
{
  player.x = 64;
  player.y = 128;
  player.vx = 0;
  player.frame = 0;
  scroll_x = 0;
}

static void stage_input(void)
{
  bios_read_joypad();
  player.vx = 0;
  if (bios_joy1_hold & PAD_LEFT)  player.vx = -2;
  if (bios_joy1_hold & PAD_RIGHT) player.vx = 2;

  player.x += player.vx;
  if (player.x < 8) player.x = 8;
  if (player.x > 248) player.x = 248;

  /* camera follows the player, clamped to the decoded screen width */
  scroll_x = player.x - 64;
  if (scroll_x < 0) scroll_x = 0;
  if (scroll_x > MAX_SCROLL_X) scroll_x = MAX_SCROLL_X;

  if (player.vx != 0) player.frame = (player.frame + 1) & 3;
  else player.frame = 0;
}

static void player_draw(void)
{
  bios_sprlist[0].pos_x = 128 + player.x;
  bios_sprlist[0].pos_y = 128 + player.y;
  bios_sprlist[0].tile = PLAYER_TILE;
  bios_sprlist[0].width = 1;     /* 2 cells wide */
  bios_sprlist[0].height = 1;    /* 2 cells high */
  bios_sprlist[0].palette = 3;
  bios_sprlist[0].priority = 1;
  bios_sprlist[0].h_flip = 0;
  bios_sprlist[0].v_flip = 0;
  bios_sprlist[0].next = 1;
  bios_copy_sprlist();
}

static void stage_scroll(void)
{
  /* the VDP horizontal scroll table: one longword per line, full-screen mode
   * reads the first entry, so writing one word scrolls plane A everywhere */
  u16 hscroll[2];
  hscroll[0] = (u16)scroll_x;
  hscroll[1] = (u16)scroll_x;
  bios_dma_xfer(to_vdp_addr(HSCROLL_ADDR), (const u8 *)hscroll, 2);
}

void main(void)
{
  bios_load_vdp_regs_default();
  bios_load_vdp_regs(stage_vdp_regs);
  bios_vdp_disp_disable();
  stage_load();
  player_init();
  bios_vdp_disp_enable();

  for (;;)
  {
    bios_vblank_wait_default();
    stage_input();
    player_draw();
    stage_scroll();

    if (bios_joy1_hit & PAD_START)
    {
      next_module = FILE_GAME_MMD;
      return;
    }
  }
}
