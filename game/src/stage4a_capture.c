/* STG4A captured window: prototype gameplay and collision. */
#include "shared.h"
#include "stage_physics.h"
#include "stage_combat.h"
#include "stage4a_enemy_logic.h"
#include "stage4a_combat.h"
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
extern u8 res_stage4a_capture_tiles[];
extern u8 res_stage4a_capture_pal[];
extern u8 res_stage4a_capture_maps[];
extern u8 res_stage4a_sprites[];
extern u8 res_stage4a_player_anim[];
extern u8 res_stage4a_skull_anim[];
extern u8 res_stage4a_column_anim[];
extern u8 res_stage4a_projectile[];
extern u8 res_stage4a_sprite_pal[];

#define STAGE_SCREENS 1
#define STAGE_TILES 286
#define SCREEN_COLS 32
#define SCREEN_ROWS 24
#define PLAYER_TILE 286   /* after the stage art */
#define ANIM_TILE (PLAYER_TILE + 50)
#define SKULL_ANIM_TILE (ANIM_TILE + 72)
#define COLUMN_ANIM_TILE (SKULL_ANIM_TILE + 32)
#define PROJECTILE_TILE (COLUMN_ANIM_TILE + 80)
#define BLANK_TILE (PROJECTILE_TILE + 4)
#define HSCROLL_ADDR 0xBC00

static u8 screen_no;
static u16 camera_x;
static u8 anim_tick, player_moving;
static u8 skull_anim_tick[STAGE_ENEMY_MAX];
static u8 column_anim_tick;
static SkullMotion skull_motion;
static ColumnShot column_shots[STG4A_SHOTS];
static Stage4aSword swords[STG4A_SWORDS];
static u8 column_phase, column_timer, column_recovery;
static const u8 blank_tile[32] = {0};
StagePhysics stage_player;
static StageCombat stage_combat;
static StageEnemy stage_enemies[STAGE_ENEMY_MAX];
static const StageSurface stage_surfaces[] = { {0,255,144,144} };
static const StageSolid stage_solids[] = { {512,0,528,192} };
#define SPAWN_X 32
#define SPAWN_Y 128
#define SCENE_ID FILE_STAGE4A_MMD
#define STAGE_EXIT_X 224

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
  return res_stage4a_capture_maps + (idx << 1);
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
    &res_stage4a_capture_tiles[0],
    (STAGE_TILES * 32) >> 1);
  bios_load_pal_update((Palette *)&res_stage4a_capture_pal[0]);

  /* Captured 32x48 PCE frames, two hardware sprites each, plus HUD tiles. */
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(PLAYER_TILE)),
                         res_stage4a_sprites, (50 * 32) >> 1);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(ANIM_TILE)),
                         res_stage4a_player_anim, (72 * 32) >> 1);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(SKULL_ANIM_TILE)),
                         res_stage4a_skull_anim, (32 * 32) >> 1);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(COLUMN_ANIM_TILE)),
                         res_stage4a_column_anim, (80 * 32) >> 1);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(PROJECTILE_TILE)),
                         res_stage4a_projectile, (4 * 32) >> 1);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(BLANK_TILE)),
                         blank_tile, sizeof(blank_tile) / 2);
  {
    const u16 *sprite_pal = (const u16 *)res_stage4a_sprite_pal;
    u8 i;
    for (i=1; i<16; ++i) bios_palette[48+i] = sprite_pal[i];
  }
  bios_vdp_update_flags |= BIOS_MASK_COPY_PALETTE;

  /* Clear the 64-cell plane; main repeats this captured screen across it. */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W,
    63, 31, BLANK_TILE);
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
                    72,128,0,240, 160,128,160,160);
  stage_combat.hp=STG4A_PLAYER_HP;
  stage_enemies[0].hp=8; stage_enemies[1].hp=212;
  skull_anim_tick[0] = skull_anim_tick[1] = 9;
  column_anim_tick = 11;
  skull_motion.x=(72+8)*16; skull_motion.y=(128+16)*16;
  skull_motion.vx=skull_motion.vy=0;
  skull_motion.awake=skull_motion.pause=skull_motion.timer=0;
  column_phase=column_timer=column_recovery=0;
  { u8 i; for (i=0; i<STG4A_SHOTS; ++i) column_shots[i].active=0; }
  { u8 i; for (i=0; i<STG4A_SWORDS; ++i) swords[i].life=0; }

  /* plane B stays clear behind the stage */
  bios_plane_fill(
    to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W,
    63, 31, BLANK_TILE);
}

static void stage_input(void)
{
  u8 previous_screen = screen_no;
  u16 previous_x = stage_player.x;
  if (stage_combat.game_over) {
    if (stage_combat.death_timer) { --stage_combat.death_timer; return; }
    stage_player.x=SPAWN_X; stage_player.y=SPAWN_Y;
    stage_player.vy=0; stage_player.grounded=0;
    stage_combat_respawn(&stage_combat, stage_enemies, SPAWN_X, SPAWN_Y);
    stage_combat.hp=STG4A_PLAYER_HP; stage_combat.invulnerable=90;
    stage_enemies[0].hp=8; stage_enemies[1].hp=212;
    skull_anim_tick[0] = skull_anim_tick[1] = 9;
    column_anim_tick = 11;
    skull_motion.x=(stage_enemies[0].x+8)*16; skull_motion.y=(stage_enemies[0].y+16)*16;
    skull_motion.vx=skull_motion.vy=0;
    skull_motion.awake=skull_motion.pause=skull_motion.timer=0;
    column_phase=column_timer=column_recovery=0;
    { u8 i; for (i=0; i<STG4A_SHOTS; ++i) column_shots[i].active=0; }
    { u8 i; for (i=0; i<STG4A_SWORDS; ++i) swords[i].life=0; }
  }
  stage_combat_face(&stage_combat, bios_joy1_hold & PAD_LEFT,
                    bios_joy1_hold & PAD_RIGHT);
  stage_physics_step(&stage_player, stage_surfaces,
                     sizeof(stage_surfaces) / sizeof(stage_surfaces[0]),
                     stage_solids, sizeof(stage_solids) / sizeof(stage_solids[0]),
                     STAGE_SCREENS * 256, bios_joy1_hold & PAD_LEFT,
                     bios_joy1_hold & PAD_RIGHT, bios_joy1_hit & PAD_B,
                     SPAWN_X, SPAWN_Y);
  player_moving = stage_player.x != previous_x;
  if (player_moving) ++anim_tick;
  {
    if (stage_enemies[0].alive && !stage_enemies[0].hit_flash)
      stg4a_skull_step(&skull_motion, stage_player.x+8, stage_player.y+16);
    else if (skull_motion.pause) --skull_motion.pause;
    stage_enemies[0].x=skull_motion.x/16-8;
    stage_enemies[0].y=skull_motion.y/16-16;
    if (skull_motion.vx) stage_enemies[0].direction=skull_motion.vx>0;
    if (stage_enemies[1].alive && !stage_enemies[1].hit_flash) {
      if (!column_recovery && stage_enemies[1].hp < 200) {
        stage_enemies[1].hp=212; column_recovery=1; column_timer=120;
      } else if (column_recovery && column_timer && !--column_timer) {
        if (column_recovery==1) { column_recovery=2; column_timer=60; }
        else { column_recovery=0; column_phase=0; }
      }
    }
    if (!stage_combat.game_over) {
      stg4a_column_step(column_shots, &column_phase, &column_timer,
                        stage_enemies[1].x+8, stage_enemies[1].y+16,
                        stage_enemies[1].alive && !column_recovery &&
                        !stage_enemies[1].hit_flash);
    }
    stg4a_combat_step(&stage_combat, stage_enemies, &skull_motion, column_shots,
                      swords, stage_player.x, stage_player.y,
                      (bios_joy1_hit & (PAD_A | PAD_C)) != 0, column_recovery);
  }
  {
    u8 i;
    for (i=0; i<STAGE_ENEMY_MAX; ++i) {
      if (stage_enemies[i].alive && (i != 0 || skull_motion.awake) && ++skull_anim_tick[i] >= 10)
        skull_anim_tick[i] = 0;
    }
  }
  if (stage_enemies[1].alive && ++column_anim_tick >= 12)
    column_anim_tick = 0;
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
  u8 i;
  u16 player_frame = PLAYER_TILE;
  if (stage_combat.attack_flash) player_frame = ANIM_TILE + 48;
  else if (player_moving) player_frame = ANIM_TILE + ((anim_tick & 8) ? 24 : 0);
  /* The collision body stays 16x16; place the 32x48 art around its feet. */
  for (i=0; i<10+STG4A_SHOTS; ++i) {
    bios_sprlist[i].pos_x=0; bios_sprlist[i].pos_y=0;
    bios_sprlist[i].palette=3; bios_sprlist[i].priority=1;
    bios_sprlist[i].h_flip=0;
    bios_sprlist[i].next=(i==9+STG4A_SHOTS) ? 0 : i+1;
  }
  for (i=0; i<2; ++i) {
    bios_sprlist[i].tile=player_frame+(i ? 16 : 0);
    bios_sprlist[i].h_flip = !stage_combat.facing;
    bios_sprlist[i].width=3; bios_sprlist[i].height=i ? 1 : 3;
    if (!stage_combat.game_over && !(stage_combat.invulnerable & 4)) {
      bios_sprlist[i].pos_x=128 + stage_player.x - camera_x - 8;
      bios_sprlist[i].pos_y=128 + stage_player.y - 32 + (i ? 32 : 0);
    }
  }
  {
    u8 slot=2;
    /* STG4A animation 0x1F: frame 33 then 34, five updates each. */
    bios_sprlist[slot].tile=SKULL_ANIM_TILE + (skull_anim_tick[0] < 5 ? 0 : 16);
    bios_sprlist[slot].palette=2;
    bios_sprlist[slot].h_flip = !stage_enemies[0].direction;
    bios_sprlist[slot].width=3; bios_sprlist[slot].height=3;
    if (stage_enemies[0].alive && skull_motion.awake && !(stage_enemies[0].hit_flash & 1)) {
      bios_sprlist[slot].pos_x=128 + stage_enemies[0].x - camera_x - 8;
      bios_sprlist[slot].pos_y=128 + stage_enemies[0].y - 16;
    }
  }
  for (i=0; i<3; ++i) {
    u8 slot=3+i;
    bios_sprlist[slot].tile=COLUMN_ANIM_TILE + (column_anim_tick < 6 ? 0 : 40)
                           + (i==0 ? 0 : i==1 ? 16 : 32);
    bios_sprlist[slot].palette=2;
    bios_sprlist[slot].width=3; bios_sprlist[slot].height=i==2 ? 1 : 3;
    if (stage_enemies[1].alive && !(stage_enemies[1].hit_flash & 1)) {
      bios_sprlist[slot].pos_x=128 + stage_enemies[1].x - camera_x - 8;
      bios_sprlist[slot].pos_y=128 + stage_enemies[1].y - 64 + i*32;
    }
  }
  for (i=0; i<STG4A_SHOTS; ++i) {
    u8 slot=10+i;
    bios_sprlist[slot].tile=PROJECTILE_TILE;
    bios_sprlist[slot].palette=2;
    bios_sprlist[slot].width=1; bios_sprlist[slot].height=1;
    if (column_shots[i].active) {
      bios_sprlist[slot].pos_x=128 + column_shots[i].x/16 - camera_x - 8;
      bios_sprlist[slot].pos_y=128 + column_shots[i].y/16 - 8;
    }
  }
  bios_sprlist[6].tile=PLAYER_TILE+49;
  bios_sprlist[6].width=0; bios_sprlist[6].height=0;
  if (stage_combat.attack_flash && !stage_combat.game_over) {
    bios_sprlist[6].pos_x=128 + stage_player.x - camera_x +
                          (stage_combat.facing ? 16 : -16);
    bios_sprlist[6].pos_y=128 + stage_player.y;
  }
  for (i=0; i<3; ++i) {
    u8 slot=7+i;
    bios_sprlist[slot].tile=PLAYER_TILE+48;
    bios_sprlist[slot].width=0; bios_sprlist[slot].height=0;
    if (i*8 < stage_combat.hp) {
      bios_sprlist[slot].pos_x=128+224+i*8;
      bios_sprlist[slot].pos_y=136;
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

    /* The original column recovers instead of being a mandatory kill. */
    if (!stage_enemies[0].alive && stage_player.x >= STAGE_EXIT_X) {
      engine_transition_scene(FILE_STAGE3A_MMD, FILE_STAGE3A_MMD, 32, 160,
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
