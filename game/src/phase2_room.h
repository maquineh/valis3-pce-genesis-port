/* A fixed PCE viewport for the two encounters after the opening. Each module
 * supplies its original world coordinates so existing BRAM checkpoints work. */
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
extern u8 room_tiles[], room_palette[], room_actors[];
extern u16 room_map[];
StagePhysics stage_player;
static StageCombat stage_combat;
static StageEnemy stage_enemies[STAGE_ENEMY_MAX];
static u16 room_left, original_floor;
static u8 walk_tick, enemy_tick, displayed_hp, screen_no, displayed_screen;
static u16 plane_map[32 * 28];

static const u16 *screen_map(void)
{
  return room_map + (u16)screen_no * 32 * 28;
}

static void encounter_init(void)
{
  room_left = stage_player.x & 0xff00;
  original_floor = ROOM_FLOOR;
#if LEGACY_COAST
  /* Older builds let the player save on higher cliff slices. Retain their
   * x/y and project that slice onto the recovered coastal arena. */
  if (room_left == 256) original_floor = 124;
  if (room_left == 512) original_floor = 60;
  if (room_left == 768) original_floor = stage_player.x >= 848 ? 172 : 140;
#endif
  stage_combat_init(&stage_combat, stage_enemies, room_left + ENEMY_X, original_floor - 16,
                    room_left + PATROL_LEFT, room_left + PATROL_RIGHT, 0, 0, 0, 0);
  stage_enemies[0].direction = 0;
  stage_enemies[1].alive = stage_enemies[1].hp = 0;
  enemy_tick = walk_tick = 0;
}

static void room_input(void)
{
  if (stage_combat.game_over) {
    if (stage_combat.death_timer) { --stage_combat.death_timer; return; }
    stage_player = (StagePhysics){SPAWN_X, SPAWN_Y, 0, 0};
    encounter_init();
    screen_no = (u8)(room_left >> 8);
    stage_combat.invulnerable = 60;
  }
  StageSurface floor = {FLOOR_LEFT, WORLD_WIDTH - 1, original_floor, original_floor};
  StageSolid ground = {floor.x1, original_floor, WORLD_WIDTH, original_floor + 48};
  u16 pad = bios_joy1_hold;
  u8 attack = bios_joy1_hit & (PAD_A | PAD_C);
  u8 old_hp = stage_combat.hp;
  stage_combat_face(&stage_combat, pad & PAD_LEFT, pad & PAD_RIGHT);
  u8 slide_started = 0;
  if (!stage_player.slide_timer && (pad & PAD_DOWN) &&
      (bios_joy1_hit & PAD_B) && stage_player.grounded) {
    stage_slide_start(&stage_player, stage_combat.facing);
    slide_started = 1;
    engine_audio_command(CMD_PLAY_SFX, CITY_SFX_JUMP);
  }
  u8 jumped = !slide_started && (bios_joy1_hit & PAD_B) && stage_player.grounded;
  stage_physics_step(&stage_player, &floor, 1, &ground, 1, WORLD_WIDTH,
                     (pad & PAD_LEFT) && stage_player.x > 0, pad & PAD_RIGHT,
                     bios_joy1_hit & PAD_B, SPAWN_X, SPAWN_Y);
  if (jumped) engine_audio_command(CMD_PLAY_SFX, CITY_SFX_JUMP);
  if ((stage_player.x & 0xff00) != room_left) {
    encounter_init();
    screen_no = (u8)(room_left >> 8);
  }
  if (pad & (PAD_LEFT | PAD_RIGHT)) ++walk_tick;
  else walk_tick = 0;
  ++enemy_tick;
  u8 hit = stage_combat_step_pose(&stage_combat, stage_enemies,
                                attack && !stage_player.slide_timer,
                                stage_player.x, stage_player.y, SPAWN_X, SPAWN_Y,
                                (enemy_tick & PATROL_MASK) == 0,
                                stage_player.slide_timer != 0);
  if (stage_player.slide_timer && stage_combat_slide_damage(
        &stage_combat, stage_enemies, stage_player.x, stage_player.y,
        &stage_player.slide_hit)) hit = 1;
  if (attack && !stage_player.slide_timer)
    engine_audio_command(CMD_PLAY_SFX, CITY_SFX_SWORD);
  if (hit || stage_combat.hp < old_hp)
    engine_audio_command(CMD_PLAY_SFX, CITY_SFX_HIT);
}

static void room_draw(void)
{
  u8 sliding = stage_player.slide_timer != 0;
  u8 frame = sliding ? 3 : stage_combat.attack_flash ? 3 : walk_tick ? 1 + ((walk_tick >> 3) & 1) : 0;
  u8 flip = !stage_combat.facing;
  if (screen_no != displayed_screen) {
    const u16 *source = screen_map();
    for (u16 i = 0; i < 32 * 28; ++i) plane_map[i] = source[i];
    bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W, 31, 27, plane_map);
    displayed_screen = screen_no;
    displayed_hp = 255;
  }
  s16 dy = DISPLAY_FLOOR - (s16)original_floor;
  draw_actor(0, STAGE_TILES + 48 * frame, (s16)(stage_player.x - room_left) - (flip ? 40 : 8),
             stage_player.y + dy - (sliding ? 24 : 32), 64, 48, 3, flip,
             !stage_combat.game_over && !(stage_combat.invulnerable & 4), 7);
  StageEnemy *e = &stage_enemies[0];
#if LEGACY_COAST
  /* The three lance poses have holds of 10, 8 and 12 ticks. */
  u8 t = enemy_tick & 63;
  u8 pose = t < 34 ? 0 : t < 44 ? 1 : t < 52 ? 2 : 3;
#else
  static const u8 strides[] = {0, 1, 2, 1};
  u8 pose = strides[(enemy_tick >> 3) & 3];
#endif
  draw_actor(4, STAGE_TILES + 48 * (4 + pose), e->x - (s16)room_left - 16,
             DISPLAY_FLOOR - 64, 48, 64, 2, e->direction, e->alive && !(e->hit_flash & 1), 7);
  bios_copy_sprlist();
  if (displayed_hp != stage_combat.hp) {
    for (u8 i = 0; i < 12; ++i)
      plane_map[32 + 4 + i] = i < 4 * stage_combat.hp ? screen_map()[32 + 4 + i] : 0;
    bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA + VDP_PLANE_POS(0, 1, Width64)) | VRAM_W,
                  31, 0, &plane_map[32]);
    displayed_hp = stage_combat.hp;
  }
}

void main(void)
{
  static const vdp_reg regs[] = {
    (VDP_REG_PL_SIZE & 0xff00) | (VDP_PL_W64 | VDP_PL_H32), VDP_REG_MODE4, 0
  };
  bios_load_vdp_regs_default();
  bios_load_vdp_regs(regs);
  bios_vdp_disp_disable();
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(0)), room_tiles, STAGE_TILES * 16);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(STAGE_TILES)),
                         room_actors, (4 + ENEMY_FRAMES) * 48 * 16);
  bios_load_pal_update((Palette *)room_palette);
  bios_plane_fill(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W, 63, 31, 0);
  bios_plane_fill(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W, 63, 31, 0);
  screen_no = displayed_screen = 0;
  for (u16 i = 0; i < 32 * 28; ++i) plane_map[i] = room_map[i];
  u16 scroll[2] = {0, 0};
  bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_HSCROLL), (u8 *)scroll, 2);
  stage_player = (StagePhysics){SPAWN_X, SPAWN_Y, 0, 0};
  engine_repeat_cdda(24); /* Coast, original PCE track 40. */
  engine_resume_position(SCENE_ID, &stage_player.x, &stage_player.y);
  if (stage_player.x > WORLD_WIDTH - 16 || stage_player.y > 176)
    stage_player = (StagePhysics){SPAWN_X, SPAWN_Y, 0, 0};
  encounter_init();
  screen_no = displayed_screen = (u8)(room_left >> 8);
  for (u16 i = 0; i < 32 * 28; ++i) plane_map[i] = screen_map()[i];
  displayed_hp = 255;
  bios_vdp_disp_enable();
  bios_vblank_wait_default();
  bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W, 31, 27, plane_map);
  for (;;) {
    bios_vblank_wait_default();
    room_input();
    room_draw();
    if (stage_combat_exit_ready(stage_enemies, stage_player.x, WORLD_WIDTH - 24)) {
      engine_transition_scene(NEXT_SCENE, NEXT_SCENE, NEXT_X, NEXT_Y, &next_module);
      return;
    }
    if (bios_joy1_hit & PAD_START) {
      engine_save_position(SCENE_ID, stage_player.x, stage_player.y);
      next_module = FILE_GAME_MMD;
      return;
    }
  }
}
