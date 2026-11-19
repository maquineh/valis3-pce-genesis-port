/* STG2A opening assembled from its PCE raster split, VRAM and actor frames. */

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
extern u8 res_stage2_state_tiles[];
extern u8 res_stage2_state_pal[];
extern u8 res_stage2_state_maps[];
extern u8 res_stage2_actors[];
extern u16 res_stage2_hud[];

#define STAGE_SCREENS 4
#define STAGE_TILES 83
#define SCREEN_COLS 32
#define SCREEN_ROWS 28
#define PLAYER_TILE STAGE_TILES
#define PLAYER_FRAME_TILES 48
#define ENEMY_TILE (PLAYER_TILE + 4 * PLAYER_FRAME_TILES)
#define HSCROLL_ADDR 0xBC00

static u8 screen_no, walk_tick, encounter_started, displayed_hp, room_no;
static u16 camera_x;
StagePhysics stage_player;
static StageCombat stage_combat;
static StageEnemy stage_enemies[STAGE_ENEMY_MAX];
/* A continuous floor lets the normal route visit all four captured screens. */
static const StageSurface stage_surfaces[] = { {0,1023,176,176} };
static const StageSolid stage_solids[] = { {0,176,1024,192} };
#define SPAWN_X 32
#define SPAWN_Y 160
#define SCENE_ID FILE_STAGE2_MMD
#define STAGE_EXIT_X 992

static void room_enemies(u8 room)
{
  u16 base = (u16)room << 8;
  stage_enemies[0] = (StageEnemy){base+140,160,base+100,base+235,2,1,1,0};
  stage_enemies[1] = (StageEnemy){base+210,160,base+180,base+235,2,1,1,0};
}

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
  return res_stage2_state_maps + (idx << 1);
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
    &res_stage2_state_tiles[0],
    (STAGE_TILES * 32) >> 1);
  bios_load_pal_update((Palette *)&res_stage2_state_pal[0]);

  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(PLAYER_TILE)),
                         res_stage2_actors, (4 * PLAYER_FRAME_TILES + 48) * 16);
  walk_tick = encounter_started = 0;
  displayed_hp = 255;

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
                    140,160,100,170, 210,160,180,235);
  room_no = (u8)(stage_player.x >> 8);
  room_enemies(room_no);

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
  u8 attack = (bios_joy1_hit & (PAD_A | PAD_C)) != 0;
  u8 old_hp = stage_combat.hp;
  stage_combat_face(&stage_combat, bios_joy1_hold & PAD_LEFT,
                    bios_joy1_hold & PAD_RIGHT);
  u8 slide_started = 0;
  if (!stage_player.slide_timer && (bios_joy1_hold & PAD_DOWN) &&
      (bios_joy1_hit & PAD_B) && stage_player.grounded) {
    stage_slide_start(&stage_player, stage_combat.facing);
    slide_started = 1;
    engine_audio_command(CMD_PLAY_SFX, CITY_SFX_JUMP);
  }
  u8 jumped = !slide_started && (bios_joy1_hit & PAD_B) && stage_player.grounded;
  stage_physics_step(&stage_player, stage_surfaces,
                     sizeof(stage_surfaces) / sizeof(stage_surfaces[0]),
                     stage_solids, sizeof(stage_solids) / sizeof(stage_solids[0]),
                     STAGE_SCREENS * 256, bios_joy1_hold & PAD_LEFT,
                     bios_joy1_hold & PAD_RIGHT, bios_joy1_hit & PAD_B,
                     SPAWN_X, SPAWN_Y);
  if (jumped) engine_audio_command(CMD_PLAY_SFX, CITY_SFX_JUMP);
  if (stage_player.x >= 64) encounter_started = 1;
  u8 room = (u8)(stage_player.x >> 8);
  if (room != room_no) {
    room_no = room;
    room_enemies(room);
  }
  if (bios_joy1_hold & (PAD_LEFT | PAD_RIGHT)) ++walk_tick;
  else walk_tick = 0;
  u8 hit = stage_combat_step_pose(&stage_combat, stage_enemies,
                             attack && !stage_player.slide_timer,
                             stage_player.x, stage_player.y, SPAWN_X, SPAWN_Y,
                             1, stage_player.slide_timer != 0);
  if (stage_player.slide_timer && stage_combat_slide_damage(
        &stage_combat, stage_enemies, stage_player.x, stage_player.y,
        &stage_player.slide_hit)) hit = 1;
  if (attack && !stage_player.slide_timer)
    engine_audio_command(CMD_PLAY_SFX, CITY_SFX_SWORD);
  if (hit || stage_combat.hp < old_hp)
    engine_audio_command(CMD_PLAY_SFX, CITY_SFX_HIT);
  camera_x = stage_player.x > 120 ? stage_player.x - 120 : 0;
  if (camera_x > (STAGE_SCREENS - 1) * 256)
    camera_x = (STAGE_SCREENS - 1) * 256;
  screen_no = camera_x >> 8;
  if (screen_no != previous_screen) {
    draw_screen(0, screen_no);
    draw_screen(SCREEN_COLS, next_screen(screen_no));
  }
}

#include "phase2_actor.h"

static void player_draw(void)
{
  u8 sliding = stage_player.slide_timer != 0;
  u8 frame = sliding ? 3 : stage_combat.attack_flash ? 3 : walk_tick ? 1 + ((walk_tick >> 3) & 1) : 0;
  u8 flip = !stage_combat.facing;
  draw_actor(0, PLAYER_TILE + frame * PLAYER_FRAME_TILES,
             (s16)stage_player.x - camera_x - (flip ? 40 : 8),
             (s16)stage_player.y - (sliding ? 24 : 32),
             64, 48, 3, flip, !stage_combat.game_over && !(stage_combat.invulnerable & 4), 11);
  for (u8 i = 0; i < STAGE_ENEMY_MAX; ++i) {
    StageEnemy *e = &stage_enemies[i];
    s16 x = e->x - (s16)camera_x - 16;
    draw_actor(4 + i * 4, ENEMY_TILE, x, e->y - 48, 48, 64, 2,
               e->direction, encounter_started && e->alive && !(e->hit_flash & 1)
                             && x > -48 && x < 256, 11);
  }
  bios_copy_sprlist();
  if (displayed_hp != stage_combat.hp) {
    u16 hud[32 * 5];
    for (u16 i = 0; i < 32 * 5; ++i) hud[i] = res_stage2_hud[i];
    for (u8 i = 4 * stage_combat.hp; i < 12; ++i) hud[32 + 4 + i] = 0;
    bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W, 31, 4, hud);
    displayed_hp = stage_combat.hp;
  }
}

static void stage_scroll(void)
{
  u16 hscroll[2];
  hscroll[0] = -(camera_x & 255);
  hscroll[1] = 0; /* Fixed HUD on plane B. */
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
  engine_repeat_cdda(24); /* Coast, original PCE track 40. */

  for (;;)
  {
    bios_vblank_wait_default();
    stage_input();
    player_draw();
    stage_scroll();

    if (stage_combat_exit_ready(stage_enemies, stage_player.x, STAGE_EXIT_X)) {
      engine_transition_scene(FILE_STAGE2A2_MMD, FILE_STAGE2A2_MMD, 80, 172,
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
