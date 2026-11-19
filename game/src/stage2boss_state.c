/* STG2C dungeon boss: the captured blue-knight pair and its fireballs.
 *
 * The arena is the one-screen STG2C corridor capture (palettes 0..2), so the
 * captured STG2A player frames and the extracted boss can share line 3.  The
 * boss keeps the source sprite shape; its colours are quantised to that line.
 * Timing and attack patterns are port gameplay, like the city boss. */
#include "shared.h"
#include "stage_physics.h"
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
extern u8 res_stage2c_b_state_tiles[];
extern u8 res_stage2c_b_state_pal[];
extern u8 res_stage2c_b_state_maps[];
extern u8 res_stage2_actors[];
extern u8 res_stage2_state_pal[];
extern u8 stage2_boss_tiles[];
extern u8 stage2_boss_fire_tiles[];

#define BG_TILES 80
#define PLAYER_TILE 80
#define PLAYER_FRAME_TILES 48
#define BOSS_TILE 272
#define FIRE_TILE 288
#define SOLID_TILE 292
#define BOSS_HP_MAX 16
#define PLAYER_HP 3
#define BOSS_VOICE_TICKS 1022
#define SCENE_ID FILE_STAGE2_BOSS_MMD

static StagePhysics stage_player;
static s16 boss_x, boss_feet, boss_bob;
static u8 boss_hp, boss_flash, boss_tick, boss_shoot, boss_clear, boss_clear_timer;
static u8 player_hp, invulnerable, hurt, attack, attack_cd, facing, walk_tick, jumped;
static u16 intro_tick;
static u8 displayed_player_hp, displayed_boss_hp;
static u16 hud[64];
static struct { s16 x, y; s8 dx; u8 life; } fire[4];

static const StageSurface floor_surface[] = { {0,255,176,176} };
static const StageSolid no_solids[] = { {0,0,0,0} };

static vdp_reg const stage_vdp_regs[] = {
    (VDP_REG_PL_SIZE & 0xFF00) | (VDP_PL_W64 | VDP_PL_H32),
    VDP_REG_MODE4,
    VDP_REG_MODE3 | 2,
    VDP_REG_WIN_HPOS,
    VDP_REG_WIN_VPOS | 2,
    0
};

static void reset_boss(void)
{
  boss_x = 176;
  boss_feet = 176;
  boss_bob = 0;
  boss_hp = BOSS_HP_MAX;
  boss_flash = boss_tick = boss_shoot = boss_clear = boss_clear_timer = 0;
  for (u8 i=0;i<4;++i) fire[i].life=0;
}

static void reset_player(void)
{
  stage_player = (StagePhysics){48, 160, 0, 0};
  player_hp = PLAYER_HP;
  invulnerable = 60;
  hurt = attack = attack_cd = 0;
  facing = 1;
  walk_tick = 0;
  for (u8 i=0;i<4;++i) fire[i].life=0;
}

static void make_solid_tiles(void)
{
  u8 tiles[64];
  for (u8 i=0;i<32;++i) tiles[i]=0xcc;      /* red health cell */
  for (u8 i=32;i<64;++i) tiles[i]=0x00;     /* empty cell */
  bios_dma_xfer(to_vdp_addr(vram_addr_from_tileidx(SOLID_TILE)), tiles, 32);
}

static void draw_hud(void)
{
  if (displayed_player_hp == player_hp && displayed_boss_hp == boss_hp) return;
  for (u8 i=0;i<64;++i) hud[i]= (u16)(0x8000 | (3<<13) | (SOLID_TILE+1));
  for (u8 i=0;i<PLAYER_HP;++i)
    if (i < player_hp) hud[i]=(u16)(0x8000|(3<<13)|SOLID_TILE);
  for (u8 i=0;i<BOSS_HP_MAX;++i)
    if (i < boss_hp) hud[16+i]=(u16)(0x8000|(3<<13)|SOLID_TILE);
  bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_WINDOW), (const u8 *)hud, 64);
  displayed_player_hp = player_hp;
  displayed_boss_hp = boss_hp;
}

static void hit_player(void)
{
  if (invulnerable || !player_hp) return;
  --player_hp;
  invulnerable = 60;
  hurt = 18;
  engine_audio_command(CMD_PLAY_SFX, CITY_SFX_HIT);
}

static void shoot_fire(void)
{
  for (u8 i=0;i<4;++i) if (!fire[i].life) {
    fire[i].x = boss_x + 8;
    fire[i].y = boss_feet - 40;
    fire[i].dx = boss_x > (s16)stage_player.x ? -2 : 2;
    fire[i].life = 100;
    engine_audio_command(CMD_PLAY_SFX, CITY_SFX_MAGIC);
    return;
  }
}

static void player_step(void)
{
  u16 pad = bios_joy1_hold;
  u16 hit = bios_joy1_hit;
  s16 dir = ((pad & PAD_RIGHT)!=0)-((pad & PAD_LEFT)!=0);
  u8 old_hp = player_hp;
  jumped = 0;
  if (hurt) {
    --hurt;
    dir = 0;
    attack_cd = 0;
  } else {
    if (!stage_player.slide_timer && (pad & PAD_DOWN) && (hit & PAD_B) &&
        stage_player.grounded) {
      stage_slide_start(&stage_player, facing);
      jumped = 2; /* Slide SFX, not a jump. */
    }
    if ((hit & PAD_B) && stage_player.grounded && jumped != 2) jumped = 1;
    if ((hit & (PAD_A|PAD_C)) && !attack_cd && !attack && !stage_player.slide_timer) {
      attack = 12;
      attack_cd = 18;
      engine_audio_command(CMD_PLAY_SFX, CITY_SFX_SWORD);
    }
  }
  if (dir) facing = dir > 0;
  stage_physics_step(&stage_player, floor_surface, 1, no_solids, 0, 256,
                     pad & PAD_LEFT, pad & PAD_RIGHT, hit & PAD_B, 48, 160);
  if (jumped == 1) engine_audio_command(CMD_PLAY_SFX, CITY_SFX_JUMP);
  if (jumped == 2) engine_audio_command(CMD_PLAY_SFX, CITY_SFX_JUMP);
  if (stage_player.slide_timer && !(stage_player.slide_hit & 1) && !boss_flash) {
    s16 dx = (boss_x + 16) - (s16)stage_player.x;
    s16 dy = (boss_feet - 16) - (s16)stage_player.y;
    if (dx > -30 && dx < 30 && dy > -40 && dy < 40) {
      if (boss_hp) --boss_hp;
      boss_flash = 20;
      stage_player.slide_hit |= 1;
      engine_audio_command(CMD_PLAY_SFX, CITY_SFX_HIT);
    }
  }
  if (pad & (PAD_LEFT|PAD_RIGHT)) ++walk_tick; else walk_tick = 0;
  if (attack) {
    if (attack >= 7 && attack <= 10 && !boss_flash) {
      s16 dx = (boss_x + 16) - (s16)stage_player.x;
      s16 dy = (boss_feet - 16) - (s16)stage_player.y;
      if ((facing ? dx : -dx) >= 0 && (facing ? dx : -dx) < 46 && dy > -36 && dy < 36) {
        if (boss_hp) --boss_hp;
        boss_flash = 20;
        engine_audio_command(CMD_PLAY_SFX, CITY_SFX_HIT);
      }
    }
    --attack;
  }
  if (attack_cd) --attack_cd;
  if (player_hp < old_hp) engine_audio_command(CMD_PLAY_SFX, CITY_SFX_HIT);
}

static void boss_step(void)
{
  ++boss_tick;
  if (boss_tick & 1) {
    s16 next = boss_x + (boss_x > 188 ? -1 : 1);
    if (next < 160 || next > 208) next = boss_x;
    boss_x = next;
  }
  boss_bob = (boss_tick & 31) < 16 ? (boss_tick & 15) : 15 - (boss_tick & 15);
  if (boss_flash) --boss_flash;
  if (--boss_shoot == 0) {
    shoot_fire();
    boss_shoot = 100;
  }
  s16 dx = (boss_x + 16) - (s16)stage_player.x;
  s16 dy = (boss_feet - 16) - (s16)stage_player.y;
  if (!invulnerable && !stage_player.slide_timer &&
      dx > -28 && dx < 28 && dy > -40 && dy < 40) hit_player();
}

static void fire_step(void)
{
  for (u8 i=0;i<4;++i) {
    if (!fire[i].life) continue;
    fire[i].x += fire[i].dx;
    --fire[i].life;
    s16 dx = fire[i].x - (s16)stage_player.x;
    s16 dy = fire[i].y - (s16)stage_player.y;
    if (!invulnerable && !stage_player.slide_timer &&
        dx > -14 && dx < 14 && dy > -14 && dy < 20) {
      hit_player();
      fire[i].life = 0;
    }
  }
}

static void draw(void)
{
  u8 sliding = stage_player.slide_timer != 0;
  u8 frame = sliding ? 3 : attack ? 3 : walk_tick ? 1 + ((walk_tick >> 3) & 1) : 0;
  u8 flip = !facing;
  draw_actor(0, PLAYER_TILE + frame * PLAYER_FRAME_TILES,
             (s16)stage_player.x - (flip ? 40 : 8),
             (s16)stage_player.y - (sliding ? 24 : 32),
             64, 48, 3, flip,
             !(invulnerable & 4) && !(hurt & 2), 8);
  /* The captured sprite holds both knights; one 32x32 hardware sprite. */
  bios_sprlist[4].pos_x = 128 + boss_x;
  bios_sprlist[4].pos_y = 128 + boss_feet - 32 - boss_bob;
  bios_sprlist[4].tile = BOSS_TILE;
  bios_sprlist[4].width = 3;
  bios_sprlist[4].height = 3;
  bios_sprlist[4].palette = 3;
  bios_sprlist[4].priority = 1;
  bios_sprlist[4].h_flip = boss_x > (s16)stage_player.x;
  bios_sprlist[4].v_flip = 0;
  bios_sprlist[4].next = 5;
  if (!boss_hp || (boss_flash & 2)) {
    bios_sprlist[4].pos_x = 0;
    bios_sprlist[4].pos_y = 0;
  }
  for (u8 i=0;i<4;++i) {
    u8 slot = 5 + i;
    bios_sprlist[slot].pos_x = 128 + fire[i].x;
    bios_sprlist[slot].pos_y = 128 + fire[i].y;
    bios_sprlist[slot].tile = FIRE_TILE;
    bios_sprlist[slot].width = 1;
    bios_sprlist[slot].height = 1;
    bios_sprlist[slot].palette = 3;
    bios_sprlist[slot].priority = 1;
    bios_sprlist[slot].h_flip = fire[i].dx > 0;
    bios_sprlist[slot].v_flip = 0;
    bios_sprlist[slot].next = slot + 1;
    if (!fire[i].life) { bios_sprlist[slot].pos_x = 0; bios_sprlist[slot].pos_y = 0; }
  }
  bios_sprlist[8].next = 0;
  bios_copy_sprlist();
  draw_hud();
}

void main(void)
{
  bios_load_vdp_regs_default();
  bios_load_vdp_regs(stage_vdp_regs);
  bios_vdp_disp_disable();
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(0)),
                         res_stage2c_b_state_tiles, BG_TILES * 16);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(PLAYER_TILE)),
                         res_stage2_actors, 4 * PLAYER_FRAME_TILES * 16);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(BOSS_TILE)),
                         stage2_boss_tiles, 16 * 16);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(FIRE_TILE)),
                         stage2_boss_fire_tiles, 4 * 16);
  make_solid_tiles();

  /* The corridor pack uses lines 0..2; line 3 comes from the captured player. */
  bios_load_pal_update((Palette *)res_stage2c_b_state_pal);
  for (u8 i=0;i<16;++i)
    bios_palette[48+i] = ((const u16 *)res_stage2_state_pal)[48+i];
  bios_vdp_update_flags |= BIOS_MASK_COPY_PALETTE;

  bios_plane_fill(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W, 63, 31, 0);
  bios_plane_fill(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB) | VRAM_W, 63, 31, 0);
  bios_plane_fill(to_vdp_addr(BIOS_VDP_DEFAULT_WINDOW) | VRAM_W, 31, 1, 0);
  bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA) | VRAM_W, 31, 23, res_stage2c_b_state_maps);
  u16 scroll[2] = {0,0};
  bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_HSCROLL), (u8 *)scroll, 2);

  reset_player();
  reset_boss();
  intro_tick = 0;
  displayed_player_hp = displayed_boss_hp = 255;
  engine_repeat_cdda(23); /* PCE 39, the encounter dialogue. */
  bios_vdp_disp_enable();
  bios_vblank_wait_default();

  for (;;) {
    bios_vblank_wait_default();
    if (intro_tick < BOSS_VOICE_TICKS) {
      ++intro_tick;
      if (intro_tick == BOSS_VOICE_TICKS) engine_repeat_cdda(27); /* PCE 43 */
      boss_bob = (intro_tick & 31) < 16 ? (intro_tick & 15) : 15 - (intro_tick & 15);
    } else if (boss_clear) {
      if (++boss_clear_timer == 120) {
        engine_transition_scene(FILE_STAGE3A_MMD, FILE_STAGE3A_MMD, 32, 160, &next_module);
        return;
      }
    } else {
      if (invulnerable) --invulnerable;
      if (player_hp) player_step(); else if (hurt) --hurt;
      /* The dungeon boss keeps its remaining hit points across player
       * retries; only the player and the projectiles reset. */
      if (!player_hp && !hurt) reset_player();
      boss_step();
      fire_step();
      if (!boss_hp && !boss_clear) {
        boss_clear = 1;
        boss_clear_timer = 0;
        engine_audio_command(CMD_PLAY_SFX, CITY_SFX_HIT);
      }
    }
    draw();
    if (bios_joy1_hit & PAD_START) {
      engine_save_position(SCENE_ID, stage_player.x, stage_player.y);
      next_module = FILE_GAME_MMD;
      return;
    }
  }
}
