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
extern u8 res_title_tiles[];
extern u8 res_title_pal[];
extern u8 res_title_map[];
/* Music: the original PC Engine soundtrack, burned as CD-DA tracks.
 * Disc track 2 = PCE track 1 (the title screen music). */
#define CDDA_TITLE 2

#define TITLE_TILES 353
#define TITLE_W 32
#define TITLE_H 28

#define CURSOR_X 8
#define CURSOR_START_Y 18
#define CURSOR_CONTINUE_Y 21
#define UI_TEXT_X 21
#define UI_GLYPHS 24

/* Each glyph uses the existing brightest color of title palette 0. */
static char const ui_chars[] = "SCEN OAV1234567890<>RITY";
static u8 const ui_font[UI_GLYPHS][7] = {
  {15,16,16,14,1,1,30},  /* S */
  {14,17,16,16,16,17,14}, /* C */
  {31,16,16,30,16,16,31}, /* E */
  {17,25,25,21,19,19,17}, /* N */
  {0,0,0,0,0,0,0},        /* space */
  {14,17,17,17,17,17,14}, /* O */
  {14,17,17,31,17,17,17}, /* A */
  {17,17,17,17,17,10,4},  /* V */
  {4,12,4,4,4,4,14},      /* 1 */
  {14,17,1,2,4,8,31},     /* 2 */
  {30,1,1,14,1,1,30},     /* 3 */
  {2,6,10,18,31,2,2},     /* 4 */
  {31,16,16,30,1,1,30},   /* 5 */
  {14,16,16,30,17,17,14}, /* 6 */
  {31,1,2,4,8,8,8},       /* 7 */
  {14,17,17,14,17,17,14}, /* 8 */
  {14,17,17,15,1,2,12},  /* 9 */
  {14,17,19,21,25,17,14}, /* 0 */
  {2,4,8,16,8,4,2},       /* < */
  {8,4,2,1,2,4,8},        /* > */
  {30,17,17,30,20,18,17}, /* R */
  {14,4,4,4,4,4,14}, /* I */
  {31,4,4,4,4,4,4}, /* T */
  {17,17,10,4,4,4,4} /* Y */
};

static u16 cursor_map[4];
static u8 glyph_tiles[UI_GLYPHS * 32];
static u8 const scene_modules[] = {
  FILE_STAGE2_MMD, FILE_STAGE2A2_MMD, FILE_STAGE2B_MMD,
  FILE_STAGE2C_MMD, FILE_STAGE3A_MMD, FILE_STAGE2C_GREEN_MMD,
  FILE_STAGE2C_B_MMD, FILE_STAGE4A_MMD, FILE_STAGE1A_MMD, FILE_STAGE4A_ALT_MMD,
  FILE_STAGE1_MMD
};

static u16 scene_command(u16 command, u16 value)
{
  u16 result;
  *ga_reg_comcmd1 = value;
  *ga_reg_comcmd0 = command;
  while (*ga_reg_comstat0 == 0) asm("nop");
  result = *ga_reg_comstat1;
  *ga_reg_comcmd0 = 0;
  while (*ga_reg_comstat0 != 0) asm("nop");
  return result;
}

static void make_ui_font(void)
{
  u16 const *palette = (u16 const *)(res_title_pal + 2);
  u16 brightest = 0;
  u8 ink = 1;
  for (u8 i = 1; i < 16; ++i)
  {
    u16 color = palette[i];
    u16 brightness = ((color >> 1) & 7) + ((color >> 5) & 7) + ((color >> 9) & 7);
    if (brightness > brightest) { brightest = brightness; ink = i; }
  }
  for (u8 glyph = 0; glyph < UI_GLYPHS; ++glyph)
    for (u8 y = 0; y < 8; ++y)
      for (u8 x = 0; x < 8; x += 2)
      {
        u8 bits = y < 7 ? ui_font[glyph][y] : 0;
        u8 a = (x >= 1 && x <= 5 && (bits & (1 << (5 - x)))) ? ink : 0;
        u8 b = (x + 1 >= 1 && x + 1 <= 5 && (bits & (1 << (4 - x)))) ? ink : 0;
        glyph_tiles[glyph * 32 + y * 4 + x / 2] = (a << 4) | b;
      }
  /* glyph_tiles is in Main CPU work RAM, not Word RAM. */
  bios_dma_xfer(to_vdp_addr(vram_addr_from_tileidx(TITLE_TILES)),
                glyph_tiles, sizeof(glyph_tiles) / 2);
}

static void draw_ui_text(u8 x, u8 y, char const *text)
{
  u16 entries[9];
  u8 n = 0;
  while (text[n] && n < 9)
  {
    u8 glyph = 0;
    while (glyph < UI_GLYPHS && ui_chars[glyph] != text[n]) ++glyph;
    entries[n] = (glyph == UI_GLYPHS || text[n] == ' ') ? 0 : TITLE_TILES + glyph;
    ++n;
  }
  if (n)
    bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA + VDP_PLANE_POS(x, y, Width64)) | VRAM_W,
                  n - 1, 0, entries);
}

static void draw_cursor(u8 selection)
{
  for (u8 option = 0; option < 2; ++option)
    bios_plane_fill(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA +
                    VDP_PLANE_POS(CURSOR_X, option ? CURSOR_CONTINUE_Y : CURSOR_START_Y, Width64)) | VRAM_W,
                    1, 1, 0);
  bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA +
                VDP_PLANE_POS(CURSOR_X, selection ? CURSOR_CONTINUE_Y : CURSOR_START_Y, Width64)) | VRAM_W,
                1, 1, cursor_map);
}

/* The D-pad bits of the Mega Drive joypad 1 register: bit3 = UP, bit2 = DOWN.
 * The engine headers already provide PAD_UP/PAD_DOWN; these fallbacks only
 * kick in if a header version does not. */
#ifndef PAD_UP
#define PAD_UP 0x08
#endif
#ifndef PAD_DOWN
#define PAD_DOWN 0x04
#endif

/**
 * The PC Engine renders 240p as a 32x28 tile screen (256x224), which is the
 * Mega Drive's H32 cell mode. Set that explicitly (40-cell is the BIOS
 * default) so every PCE tile maps 1:1 onto the plane A grid.
 */
static vdp_reg const title_vdp_regs[] = {
    VDP_REG_MODE4,                             /* 32-cell mode, no interlace */
    0};

/* Load the captured PC Engine title/menu assets into Mega Drive VRAM/CRAM. */
static void title_load(void)
{
  u16 hscroll[2] = { 0, 0 };
  /* palette: 64 colours (4 MD palette lines), CRAM line 0 */
  bios_load_pal_update((Palette *)res_title_pal);

  /* Upload the generated tiles at index 0; tile 0 is transparent. */
  bios_dma_xfer_word_ram(
    to_vdp_addr(vram_addr_from_tileidx(0)),
    res_title_tiles,
    (TITLE_TILES * 32) >> 1);
  make_ui_font();

  /* Clear both planes. Tile 0 is transparent in the generated resources. */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    31, 27, 0);
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W,
    31, 27, 0);

  /* Stages update the scroll table; reset it when returning to the title. */
  bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_HSCROLL),
                (const u8 *) hscroll, 2);

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
  u16 const *title_map = (u16 const *)res_title_map;
  u16 saved_scene;
  u8 selection = 0;
  u8 scene_index = sizeof(scene_modules) - 1;
  u8 save_error = 0;
  u8 previous_save_error = *ga_reg_comcmd5 == SCENE_SAVE_ERROR_MARKER;
  char scene_label[] = "<SCENE1> ";

  *ga_reg_comcmd5 = 0;

  bios_load_vdp_regs_default();
  bios_load_vdp_regs(title_vdp_regs);
  bios_vdp_disp_disable();
  title_load();
  bios_vdp_disp_enable();

  /* The BIOS map upload is performed after enabling the display, as in the
   * scene modules: loading it while display is disabled left a blank plane. */
  bios_load_map(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    TITLE_W - 1, TITLE_H - 1, res_title_map);

  /* Preserve the original sword cursor; redraw it on the selected option. */
  cursor_map[0] = title_map[CURSOR_START_Y * TITLE_W + CURSOR_X];
  cursor_map[1] = title_map[CURSOR_START_Y * TITLE_W + CURSOR_X + 1];
  cursor_map[2] = title_map[(CURSOR_START_Y + 1) * TITLE_W + CURSOR_X];
  cursor_map[3] = title_map[(CURSOR_START_Y + 1) * TITLE_W + CURSOR_X + 1];
  saved_scene = scene_command(CMD_READ_SCENE, 0);
  draw_cursor(selection);
  draw_ui_text(UI_TEXT_X, 19, scene_modules[scene_index] == FILE_STAGE1_MMD ? "<CITY>   " : scene_label);
  if (previous_save_error) draw_ui_text(UI_TEXT_X, 22, "SAVE ERR");
  else if (!saved_scene) draw_ui_text(UI_TEXT_X, 22, "NO SAVE ");

  /* play the original soundtrack (PC Engine track 1) */
  engine_play_cdda(CDDA_TITLE);

  for (;;)
  {
    /* The BIOS VBlank handler reads the pad; a second read clears hits. */
    bios_vblank_wait_default();
    u8 hit = bios_joy1_hit;
    if (hit & (PAD_UP | PAD_DOWN))
    {
      selection ^= 1;
      draw_cursor(selection);
      if (save_error || previous_save_error)
      {
        save_error = 0;
        previous_save_error = 0;
        draw_ui_text(UI_TEXT_X, 22, saved_scene ? "        " : "NO SAVE ");
      }
    }
    if (!selection && (hit & (PAD_LEFT | PAD_RIGHT)))
    {
      if ((hit & PAD_LEFT) && !(hit & PAD_RIGHT))
        scene_index = scene_index == 0 ? sizeof(scene_modules) - 1 : scene_index - 1;
      if ((hit & PAD_RIGHT) && !(hit & PAD_LEFT))
        scene_index = scene_index + 1 == sizeof(scene_modules) ? 0 : scene_index + 1;
      if (scene_index == 9) {
        scene_label[6] = '1'; scene_label[7] = '0'; scene_label[8] = '>';
      } else {
        scene_label[6] = '1' + scene_index; scene_label[7] = '>'; scene_label[8] = ' ';
      }
      draw_ui_text(UI_TEXT_X, 19, scene_modules[scene_index] == FILE_STAGE1_MMD ? "<CITY>   " : scene_label);
      if (save_error || previous_save_error)
      {
        save_error = 0;
        previous_save_error = 0;
        draw_ui_text(UI_TEXT_X, 22, saved_scene ? "        " : "NO SAVE ");
      }
    }
    if (hit & (PAD_START | PAD_A | PAD_B | PAD_C))
    {
      u16 target = selection ? saved_scene : scene_modules[scene_index];
      if (!target) continue; /* NO SAVE is displayed until a valid save exists. */
      if (!selection && !save_error && !scene_command(CMD_WRITE_SCENE, target))
      {
        /* Do not hide a failed save; a second confirmation starts without it. */
        draw_ui_text(UI_TEXT_X, 22, "SAVE ERR");
        save_error = 1;
        continue;
      }
      *ga_reg_comcmd4 = selection ? SCENE_RESUME_MARKER : 0;
      engine_stop_cdda();
      next_module = (u8)target;
      return;
    }
  }
}
