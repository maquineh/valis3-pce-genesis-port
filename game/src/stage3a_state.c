/* Valis III Mega CD - Stage 3A module (ice castle, captured Mednafen BAT/VRAM/CRAM).
 *
 * Source: states/stg3a_additional.mc4, a later STG3A gameplay capture.
 *   maps  : BAT row 32, columns 0-63, packed as two horizontal 32x24 screens
 *   tiles : 176 distinct BAT tile/palette pairs from the live VRAM
 *   pal   : captured CRAM repacked by exact color; line 3 reserves sprite colors
 *   packed by tools/pack_state_window.py
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
#include "stage_physics.h"
#include "stage_combat.h"
#include "scene_save.h"
#include "resource.h"
#include "engine.h"
#include <main/bios.h>
#include <main/io.def.h>
#include <main/memmap.h>
#include <main/vdp.h>
#include <system.h>
#include <types.h>

extern u8 next_module;
extern u8 res_stage3a_state_tiles[];
extern u8 res_stage3a_state_pal[];
extern u8 res_stage3a_state_maps[];
extern u8 res_player_spr[];

#define STAGE_SCREENS 2
#define STAGE_TILES 176
#define SCREEN_COLS 32
#define SCREEN_ROWS 24
#define PLAYER_TILE 176  /* after the stage art */
#define HSCROLL_ADDR 0xBC00

static u8 screen_no;
static u16 camera_x;
StagePhysics stage_player;
static StageCombat stage_combat;
static StageEnemy stage_enemies[STAGE_ENEMY_MAX];
static const StageSurface stage_surfaces[] = { {0,511,176,176} };
#define SPAWN_X 32
#define SPAWN_Y 160
#define SCENE_ID FILE_STAGE3A_MMD
#define STAGE_EXIT_X 496

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
  return res_stage3a_state_maps + (idx << 1);
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
  bios_dma_xfer_word_ram(
    to_vdp_addr(vram_addr_from_tileidx(0)),
    &res_stage3a_state_tiles[0],
    (STAGE_TILES * 32) >> 1);
  bios_load_pal_update((Palette *)&res_stage3a_state_pal[0]);

  /* Player, heart and prototype enemy tiles; colors use reserved line 3 slots. */
  bios_dma_xfer_word_ram(
    to_vdp_addr(vram_addr_from_tileidx(PLAYER_TILE)),
    &res_player_spr[0],
    (9 * 32) >> 1);
  /* Line 3 indices 8, 9 and 15 are unused by this captured background. */
  bios_palette[56] = 0x0EEE;
  bios_palette[57] = 0x0CCC;
  bios_palette[63] = 0x0AAA;
  bios_vdp_update_flags |= BIOS_MASK_COPY_PALETTE;

  /* plane A: clear, then draw the first two screens */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    63, 31, 0);
  screen_no = 0;
  camera_x = 0;
  stage_player.x = SPAWN_X;
  stage_player.y = SPAWN_Y;
  stage_player.vy = 0;
  stage_player.grounded = 0;
  engine_resume_position(SCENE_ID, &stage_player.x, &stage_player.y);
  /* A torn or stale CONTINUE coordinate must not place the player outside this capture. */
  if (stage_player.x > STAGE_SCREENS * 256 - 16 || stage_player.y > 176) {
    stage_player.x = SPAWN_X; stage_player.y = SPAWN_Y;
    stage_player.vy = 0; stage_player.grounded = 0;
  }
  stage_combat_init(&stage_combat, stage_enemies,
                    150,160,140,180, 400,160,390,430);

  /* plane B stays clear behind the stage */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W,
    63, 31, 0);
}

static void stage_input(void)
{
  u8 previous_screen = screen_no;
  if (stage_combat.game_over) {
    if (stage_combat.death_timer) { --stage_combat.death_timer; return; }
    stage_player.x=SPAWN_X; stage_player.y=SPAWN_Y;
    stage_player.vy=0; stage_player.grounded=0;
    stage_player.slide_timer=0; stage_player.slide_hit=0;
    stage_combat_respawn(&stage_combat, stage_enemies, SPAWN_X, SPAWN_Y);
  }
  stage_combat_face(&stage_combat, bios_joy1_hold & PAD_LEFT,
                    bios_joy1_hold & PAD_RIGHT);
  if (!stage_player.slide_timer && (bios_joy1_hold & PAD_DOWN) &&
      (bios_joy1_hit & PAD_B) && stage_player.grounded) {
    stage_slide_start(&stage_player, stage_combat.facing);
    engine_audio_command(CMD_PLAY_SFX, CITY_SFX_JUMP);
  }
  stage_physics_step(&stage_player, stage_surfaces,
                     sizeof(stage_surfaces) / sizeof(stage_surfaces[0]),
                     0, 0,
                     STAGE_SCREENS * 256, bios_joy1_hold & PAD_LEFT,
                     bios_joy1_hold & PAD_RIGHT, bios_joy1_hit & PAD_B,
                     SPAWN_X, SPAWN_Y);
  stage_combat_step_pose(&stage_combat, stage_enemies,
                    (bios_joy1_hit & (PAD_A | PAD_C)) != 0 && !stage_player.slide_timer,
                    stage_player.x, stage_player.y, SPAWN_X, SPAWN_Y,
                    1, stage_player.slide_timer != 0);
  if (stage_player.slide_timer)
    stage_combat_slide_damage(&stage_combat, stage_enemies,
                              stage_player.x, stage_player.y,
                              &stage_player.slide_hit);
  camera_x = stage_player.x > 120 ? stage_player.x - 120 : 0;
  if (camera_x > (STAGE_SCREENS - 1) * 256)
    camera_x = (STAGE_SCREENS - 1) * 256;
  screen_no = camera_x >> 8;
  if (screen_no != previous_screen) {
    draw_screen(0, screen_no);
    draw_screen(SCREEN_COLS, next_screen(screen_no));
  }
}

static void player_draw(void)
{
  bios_sprlist[0].pos_x = 128 + stage_player.x - camera_x;
  bios_sprlist[0].pos_y = 128 + stage_player.y + (stage_player.slide_timer ? 8 : 0);
  if (stage_combat.game_over || (stage_combat.invulnerable & 4)) {
    bios_sprlist[0].pos_x=0; bios_sprlist[0].pos_y=0;
  }
  bios_sprlist[0].tile = PLAYER_TILE;
  bios_sprlist[0].width = 1;      /* 2x2 cells */
  bios_sprlist[0].height = 1;
  bios_sprlist[0].palette = 3;
  bios_sprlist[0].priority = 1;
  bios_sprlist[0].next = 1;
  {
    u8 i;
    for (i=0; i<STAGE_ENEMY_MAX; ++i) {
      u8 slot=i+1;
      if (stage_enemies[i].alive && stage_enemies[i].x + 16 > camera_x &&
          stage_enemies[i].x < camera_x + 256) {
        bios_sprlist[slot].pos_x=128 + stage_enemies[i].x - camera_x;
        bios_sprlist[slot].pos_y=128 + stage_enemies[i].y;
        if (stage_enemies[i].hit_flash & 1) {
          bios_sprlist[slot].pos_x=0; bios_sprlist[slot].pos_y=0;
        }
        bios_sprlist[slot].tile=PLAYER_TILE+5;
        bios_sprlist[slot].width=1; bios_sprlist[slot].height=1;
        bios_sprlist[slot].palette=3;
        bios_sprlist[slot].priority=1;
      } else {
        bios_sprlist[slot].pos_x=0; bios_sprlist[slot].pos_y=0;
        bios_sprlist[slot].tile=PLAYER_TILE+5;
        bios_sprlist[slot].width=1; bios_sprlist[slot].height=1;
        bios_sprlist[slot].palette=3;
        bios_sprlist[slot].priority=1;
      }
      bios_sprlist[slot].next=slot+1;
    }
    bios_sprlist[3].pos_x=0; bios_sprlist[3].pos_y=0;
    bios_sprlist[3].tile=PLAYER_TILE+3; bios_sprlist[3].width=0;
    bios_sprlist[3].height=0; bios_sprlist[3].palette=2;
    bios_sprlist[3].priority=1; bios_sprlist[3].next=4;
    if (stage_combat.attack_flash && !stage_combat.game_over) {
      bios_sprlist[3].pos_x=128 + stage_player.x - camera_x +
                            (stage_combat.facing ? 16 : -16);
      bios_sprlist[3].pos_y=128 + stage_player.y;
    }
    for (i=0; i<3; ++i) {
      u8 slot=i+4;
      bios_sprlist[slot].pos_x=0; bios_sprlist[slot].pos_y=0;
      bios_sprlist[slot].tile=PLAYER_TILE+4;
      bios_sprlist[slot].width=0; bios_sprlist[slot].height=0;
      bios_sprlist[slot].palette=3; bios_sprlist[slot].priority=1;
      bios_sprlist[slot].next=(i<2) ? slot+1 : 0;
      if (i < stage_combat.hp) {
        bios_sprlist[slot].pos_x=128 + 224 + i*8;
        bios_sprlist[slot].pos_y=136;
      }
    }
  }
  bios_copy_sprlist();
}

static void stage_scroll(void)
{
  u16 hscroll[2];
  hscroll[0] = -(camera_x & 255);
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
  camera_x = stage_player.x > 120 ? stage_player.x - 120 : 0;
  if (camera_x > (STAGE_SCREENS - 1) * 256) camera_x = (STAGE_SCREENS - 1) * 256;
  screen_no = camera_x >> 8;
  draw_screen(0, screen_no);
  draw_screen(SCREEN_COLS, next_screen(screen_no));

  for (;;)
  {
    bios_vblank_wait_default();
    stage_input();
    player_draw();
    stage_scroll();

    if (stage_combat_exit_ready(stage_enemies, stage_player.x, STAGE_EXIT_X)) {
      engine_transition_scene(FILE_STAGE2_MMD, FILE_STAGE2_MMD, 32, 160,
                              &next_module);
      return;
    }

    if (bios_joy1_hit & PAD_START)
    {
      engine_save_position(SCENE_ID, stage_player.x, stage_player.y);
      next_module = FILE_GAME_MMD;
      return;
    }
  }
}
