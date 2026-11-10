/* Valis III Mega CD - Stage 1 module (all decoded screens).
 *
 * Stage 1 is the first 10 screens of the PC Engine original:
 *   maps  : PC Engine track 2, $17FF90 + k*$600  (24 rows x 32 cells each)
 *   tiles : PC Engine track 2, $19440 (cd_read sector $2C -> VRAM $1000)
 *   packed by tools/pack_stage_all.py into stage1_all_{tiles,maps,pal}
 *
 * The Mega Drive plane A is only 64 cells wide, so the stage is streamed the
 * way the PC Engine original does it: the plane always holds the current
 * screen (columns 0-31) and the next screen (columns 32-63); when the player
 * has scrolled a full screen the pair is redrawn one screen further on.
 *
 * Note: the Mega CD links with -nostdlib, so avoid 32-bit division/modulo
 * (no __divsi3/__modsi3 in libgcc for this link).
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
extern u8 res_stage1_all_tiles[];
extern u8 res_stage1_all_pal[];
extern u8 res_stage1_all_maps[];
extern u8 res_player_spr[];

#define STAGE_SCREENS 10
#define STAGE_TILES 1297
#define SCREEN_COLS 32
#define SCREEN_ROWS 24
#define PLAYER_TILE 1300   /* after the stage art */
#define HSCROLL_ADDR 0xBC00

static u8 screen_no;      /* screen at plane columns 0-31 */
static u16 cell_scroll;   /* scrolled cells within the stage */
static s16 player_x;      /* 0..(SCREEN_COLS-1)*8 */

static vdp_reg const stage_vdp_regs[] = {
    (VDP_REG_PL_SIZE & 0xFF00) | (VDP_PL_W64 | VDP_PL_H32),
    VDP_REG_MODE4,                    /* 240p, 32-cell screen */
    0};

/* Screen index s -> pointer to its 32x24 plane A entries (the packed array is
 * STAGE_SCREENS blocks of 32*24 words). */
static u8 const * screen_map(u8 s)
{
  if (s >= STAGE_SCREENS) s = STAGE_SCREENS - 1;
  u16 idx = (u16)s * (SCREEN_COLS * SCREEN_ROWS);
  return res_stage1_all_maps + (idx << 1);
}

static u8 next_screen(u8 s)
{
  if (s + 1 >= STAGE_SCREENS) return STAGE_SCREENS - 1;
  return (u8)(s + 1);
}

static void draw_screen(u8 col, u8 s)
{
  bios_load_map(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA
                + VDP_PLANE_POS(col, 0, Width64)) | VRAM_W,
    SCREEN_COLS - 1, SCREEN_ROWS - 1, screen_map(s));
}

static void stage_load(void)
{
  /* stage art + palette */
  bios_dma_xfer(
    to_vdp_addr(vram_addr_from_tileidx(0)),
    &res_stage1_all_tiles[0],
    (STAGE_TILES * 32) >> 1);
  bios_load_pal_update((Palette *)&res_stage1_all_pal[0]);

  /* player sprite tiles + a white palette line */
  bios_dma_xfer(
    to_vdp_addr(vram_addr_from_tileidx(PLAYER_TILE)),
    &res_player_spr[0],
    (4 * 32) >> 1);
  bios_palette[48] = 0x0EEE;
  bios_palette[49] = 0x0EEE;
  bios_palette[50] = 0x0EEE;
  bios_vdp_update_flags |= BIOS_MASK_COPY_PALETTE;

  /* plane A: clear, then draw the first two screens */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    Width64, 32, 0);
  screen_no = 0;
  cell_scroll = 0;
  draw_screen(0, 0);
  draw_screen(SCREEN_COLS, 1);

  /* plane B stays clear behind the stage */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W,
    Width64, 32, 0);
}

static void stage_input(void)
{
  u16 prev = cell_scroll;

  bios_read_joypad();
  if (bios_joy1_hold & PAD_LEFT)  cell_scroll -= 1;
  if (bios_joy1_hold & PAD_RIGHT) cell_scroll += 1;

  /* the player walks the stage; the plane follows one screen behind */
  player_x = (cell_scroll & (SCREEN_COLS - 1)) * 8;

  if (cell_scroll != prev && (cell_scroll & (SCREEN_COLS - 1)) == 0)
  {
    /* crossed a screen boundary: advance the streamed pair */
    screen_no = next_screen(screen_no);
    draw_screen(0, screen_no);
    draw_screen(SCREEN_COLS, next_screen(screen_no));
  }
}

static void player_draw(void)
{
  bios_sprlist[0].pos_x = 128 + player_x;
  bios_sprlist[0].pos_y = 128 + 96;
  bios_sprlist[0].tile = PLAYER_TILE;
  bios_sprlist[0].width = 1;      /* 2x2 cells */
  bios_sprlist[0].height = 1;
  bios_sprlist[0].palette = 3;
  bios_sprlist[0].priority = 1;
  bios_sprlist[0].next = 1;
  bios_copy_sprlist();
}

static void stage_scroll(void)
{
  u16 hscroll[2];
  hscroll[0] = (cell_scroll & (SCREEN_COLS - 1)) * 8;
  hscroll[1] = hscroll[0];
  bios_dma_xfer(to_vdp_addr(HSCROLL_ADDR), (const u8 *)hscroll, 2);
}

void main(void)
{
  bios_load_vdp_regs_default();
  bios_load_vdp_regs(stage_vdp_regs);
  bios_vdp_disp_disable();
  stage_load();
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
