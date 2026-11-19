/* Valis III Mega CD - Stage 2C module (blue brick dungeon, real Mednafen .mc2 BAT/VRAM/CRAM).
 *
 * Source: the user's Mednafen PCE save state with the Stage 2C room loaded
 *   (states/Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc2).
 *   maps  : captured 64x64 BAT, the dungeon rows split into 32x24 plane A screens
 *   tiles : 159 tile/palette variants used by the captured BAT
 *   pal   : exact-color packing for the palettes used by the captured BAT
 *   packed by tools/pack_state_window.py --pack-all-palettes (rows 0,8,16,24)
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
#include "phase2_actor.h"

extern u8 next_module;
extern u8 res_stage2c_state_tiles[];
extern u8 res_stage2c_state_pal[];
extern u8 res_stage2c_state_maps[];
extern u8 res_stage2c_state_actors[];

#define STAGE_SCREENS 4
#define STAGE_TILES 159
#define SCREEN_COLS 32
#define SCREEN_ROWS 24
#define PLAYER_TILE 159   /* after the repacked stage art */
#define PLAYER_FRAME_TILES 48
#define PLAYER_FRAMES 4
#define ENEMY_TILE (PLAYER_TILE + PLAYER_FRAMES * PLAYER_FRAME_TILES)
#define ENEMY_FRAMES 2
#define HEART_TILE (ENEMY_TILE + ENEMY_FRAMES * PLAYER_FRAME_TILES)
#define ACTOR_TILES (PLAYER_FRAMES * PLAYER_FRAME_TILES + \
                     ENEMY_FRAMES * PLAYER_FRAME_TILES + 1)
#define HSCROLL_ADDR 0xBC00

static u8 screen_no, room_no, enemy_tick, walk_tick;
static u16 camera_x;
StagePhysics stage_player;
static StageCombat stage_combat;
static StageEnemy stage_enemies[STAGE_ENEMY_MAX];
/* A continuous floor lets the normal route visit all four captured screens. */
static const StageSurface stage_surfaces[] = { {0,1023,66,66} };
static const StageSolid stage_solids[] = { {0,66,1024,192} };
#define SPAWN_X 100
#define SPAWN_Y 50
#define SCENE_ID FILE_STAGE2C_MMD
#define STAGE_EXIT_X 992

static void room_enemies(u8 room)
{
  u16 base = (u16)room << 8;
  stage_enemies[0] = (StageEnemy){base+145,50,base+120,base+170,2,1,1,0};
  stage_enemies[1] = (StageEnemy){base+205,50,base+180,base+230,2,1,1,0};
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
  return res_stage2c_state_maps + (idx << 1);
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
    &res_stage2c_state_tiles[0],
    (STAGE_TILES * 32) >> 1);
  bios_load_pal_update((Palette *)&res_stage2c_state_pal[0]);

  /* Captured STG2C actor frames: four player poses, two fire frames and the
   * HUD heart. Palette line 3 is the exact PCE player palette; the fire uses
   * line 2 with two added warm colors. */
  bios_dma_xfer_word_ram(
    to_vdp_addr(vram_addr_from_tileidx(PLAYER_TILE)),
    &res_stage2c_state_actors[0],
    (ACTOR_TILES * 32) >> 1);
  enemy_tick = 0;
  walk_tick = 0;

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
                    145,50,120,170, 205,50,180,230);
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
  u8 room = (u8)(stage_player.x >> 8);
  if (room != room_no) {
    room_no = room;
    room_enemies(room);
  }
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
  if (bios_joy1_hold & (PAD_LEFT | PAD_RIGHT)) ++walk_tick;
  else walk_tick = 0;
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
  u8 sliding = stage_player.slide_timer != 0;
  u8 frame = sliding ? 3 : stage_combat.attack_flash ? 3 :
             walk_tick ? 1 + ((walk_tick >> 3) & 1) : 0;
  u8 flip = !stage_combat.facing;
  u8 visible = !stage_combat.game_over && !(stage_combat.invulnerable & 4);
  u8 eframe = (enemy_tick >> 3) & 1;
  u8 i;

  ++enemy_tick;
  draw_actor(0, PLAYER_TILE + frame * PLAYER_FRAME_TILES,
             (s16)stage_player.x - camera_x - (flip ? 40 : 8),
             (s16)stage_player.y - (sliding ? 24 : 32),
             64, 48, 3, flip, visible, 14);
  for (i = 0; i < STAGE_ENEMY_MAX; ++i) {
    StageEnemy *e = &stage_enemies[i];
    s16 x = e->x - (s16)camera_x - 16;
    draw_actor(4 + i * 4, ENEMY_TILE + eframe * PLAYER_FRAME_TILES,
               x, e->y - 48, 48, 64, 2, e->direction,
               e->alive && !(e->hit_flash & 1) && x > -48 && x < 256, 14);
  }
  for (i = 0; i < 3; ++i) {
    u8 slot = 12 + i;
    bios_sprlist[slot].pos_x = 0;
    bios_sprlist[slot].pos_y = 0;
    bios_sprlist[slot].tile = HEART_TILE;
    bios_sprlist[slot].width = 0;
    bios_sprlist[slot].height = 0;
    bios_sprlist[slot].palette = 3;
    bios_sprlist[slot].priority = 1;
    bios_sprlist[slot].h_flip = 0;
    bios_sprlist[slot].v_flip = 0;
    bios_sprlist[slot].next = (i < 2) ? slot + 1 : 0;
    if (i < stage_combat.hp) {
      bios_sprlist[slot].pos_x = 128 + 224 + i * 8;
      bios_sprlist[slot].pos_y = 136;
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
  engine_repeat_cdda(24); /* Coast, original PCE track 40. */

  for (;;)
  {
    bios_vblank_wait_default();
    stage_input();
    player_draw();
    stage_scroll();

    if (stage_combat_exit_ready(stage_enemies, stage_player.x, STAGE_EXIT_X)) {
      engine_transition_scene(FILE_STAGE2_BOSS_MMD, FILE_STAGE2_BOSS_MMD, 48, 160,
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
