/* The city uses the Genesis cartridge's planes, palette lines and SAT pieces.
 * World ranges stay disjoint so a normal x/y checkpoint identifies the room. */
#include <system.h>
#include "scene_save.h"
#include "engine.h"
#include <main/bios.h>
#include <main/io.def.h>
#include <main/memmap.h>
#include <main/vdp.h>

extern u8 next_module;
extern const u16 city_street[], city_meeting[], city_fall[], city_roof[], city_late[], city_boss[];
enum Room { STREET, MEETING, FALL, ROOF, LATE, BOSS };
static const u16 *const packs[] = {city_street, city_meeting, city_fall, city_roof, city_late, city_boss};
static const u16 origins[] = {0,768,1024,1280,2048,8192};
static const u16 *front, *floor_map, *poses, *hud_map;
static u16 columns, map_columns, rows, camera_cell, hud[128], cloud_tick;
static s16 camera;
static u8 arena_arrival;
static u16 resume_movie_tick;
static u16 initial_plane[64 * 32];
static u16 room, scene_tick, xpos, feet;
static s16 velocity; /* quarter pixels per tick; the cartridge floors signed steps */
static u8 jump_buffer, attack_buffer;
static u8 facing, walking, attack, aerial_attack, hp, invincible, displayed_hp, slot;
#include "city_items.h"
typedef struct {
  s16 x, feet, speed, velocity, left, right;
  u8 hp, timer, flash;
} Leaper;
static Leaper enemies[2];
#include "city_combat.h"
#include "city_late.h"
#include "city_cinema.h"

static u16 column_offset(u16 x)
{
  return rows==32 ? x*32 : x*28;
}

static void column(u16 x)
{
  if (x >= map_columns) return;
  bios_load_map(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA + VDP_PLANE_POS(x & 63, 0, Width64))
                | VRAM_W, 0, 27, front + column_offset(x));
}

static s16 camera_for_player(void)
{
  /* The cartridge follows the leading edge at x=160 to the right and
   * x=48 to the left. Turning inside this interval leaves both planes still. */
  s16 target = camera;
  if ((s16)xpos - target > 160) target = xpos - 160;
  if ((s16)xpos - target < 48) target = (s16)xpos - 48;
  s16 origin=room==LATE ? 512 : 0;
  s16 limit=(map_columns*8-256)-origin;
  if (arena_arrival) target=camera+2;
  if (target < -origin) return -origin;
  return target > limit ? limit : target;
}

static u16 ground_at(s16 x)
{
  if (x < 0 || x >= columns * 8) return 0;
  if (room == STREET) return 192;
  if (room == MEETING) return x < 128 ? 168 : 0;
  return floor_map[(u16)x >> 3];
}

/* The sprite can land on either side of its centre. This keeps the 32px
 * gap traversable with the cartridge's 1px stride and 45-frame jump. */
static u16 support_at(s16 x)
{
  u16 left=ground_at(x-7), right=ground_at(x+7);
  if (!left) return right;
  if (!right) return left;
  return left<right ? left : right;
}

static void reset_scroll(void)
{
  vdp_ctrl_16=VDP_REG_AUTOINC|2;
  vdp_ctrl_32=VSRAM_W;
  for (u8 i=0;i<16;++i) vdp_data_32=0;
  vdp_ctrl_32=to_vdp_addr(BIOS_VDP_DEFAULT_HSCROLL)|VRAM_W;
  vdp_data_32=0;
}

static void load_room(enum Room next, u16 x, u16 foot)
{
  room = next;
  const u16 *data = room==ROOF ? city_late : packs[room];
  map_columns = data[0];
  columns = room==ROOF ? 74 : room==LATE ? map_columns-64 : map_columns;
  arena_arrival=0;
  if (room==STREET || room==ROOF) cloud_tick=0;
  rows = room==FALL ? 32 : 28;
  u16 tiles = data[1];
  const u8 *patterns = (const u8 *)(data + 67);
  hud_map = (const u16 *)(patterns + tiles * 32);
  const u16 *back = hud_map + 128;
  front = back + 64 * rows;
  floor_map = front + column_offset(map_columns);
  poses = floor_map + map_columns;
  if (room==LATE) floor_map+=64;
  xpos = x; feet = foot;
  velocity = 0;
  jump_buffer = attack_buffer = 0;
  walking = attack = aerial_attack = 0;
  scene_tick = 0;
  camera = 0;
  camera = camera_for_player();
  camera_cell = (camera+(room==LATE ? 512 : 0)) >> 3;
  displayed_hp = 255;
  displayed_mana = 255;
  if (room >= LATE) late_reset();
  if (room == ROOF) {
    enemies[0] = (Leaper){224,192,-1,0,142,246,2,18,0};
    enemies[1] = (Leaper){394,176,-1,0,304,451,2,30,0};
  }
  for (u16 i=0; i<128; ++i) hud[i]=hud_map[i];
  /* Assemble the 64-cell ring before touching the VDP. Long CPU map writes
   * can cross a VBlank, whose BIOS handler changes the VDP destination. */
  for (u16 row=0; row<rows; ++row) {
    for (u16 col=0; col<64; ++col) {
      u16 world=camera_cell+col;
      initial_plane[row*64+(world&63)]=world<map_columns ? front[column_offset(world)+row] : 0;
    }
  }
  bios_vblank_wait_default();
  disable_interrupts();
  bios_vdp_disp_disable();
  reset_scroll();
  vdp_ctrl_16=VDP_REG_WIN_VPOS|4;
  vdp_ctrl_16=VDP_REG_MODE3|(room==FALL ? 4 : 2);
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(0)),patterns,tiles*16);
  if (room==MEETING || room==FALL) {load_movie(resume_movie_tick); resume_movie_tick=0;}
  if (room==BOSS) load_boss_dialogue();
  if (room >= ROOF) load_combat();
  bios_dma_xfer_word_ram(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEB),(const u8 *)back,64*rows);
  bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_PLANEA),(const u8 *)initial_plane,64*rows);
  bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_WINDOW),(const u8 *)hud,128);
  bios_load_pal_update((Palette *)(packs[room]+2));
  if (room >= ROOF) load_city_items();
  bios_vdp_disp_enable();
  enable_interrupts();
  bios_vblank_wait_default();
}

static void draw_pose_parts(const s16 *p, u16 count, s16 x, s16 y, u8 flip)
{
  for (u16 i=0;i<count;++i) {
    s16 left=*p++, top=*p++;
    u16 tile=*p++, shape=*p++;
    s16 width=((shape>>2)+1)*8;
    left=x+(flip ? -left-width : left);
    top+=y;
    if (left<=-width || left>=256 || top>=224 || top+(s16)((shape&3)+1)*8<=32) continue;
    bios_sprlist[slot].pos_x=128+left;
    bios_sprlist[slot].pos_y=128+top;
    bios_sprlist[slot].tile=tile&2047;
    bios_sprlist[slot].h_flip=((tile>>11)&1)^flip;
    bios_sprlist[slot].v_flip=(tile>>12)&1;
    bios_sprlist[slot].palette=(tile>>13)&3;
    bios_sprlist[slot].priority=(room==MEETING || room==FALL) ? tile>>15 : 1;
    bios_sprlist[slot].width=shape>>2;
    bios_sprlist[slot].height=shape&3;
    bios_sprlist[slot].next=slot+1;
    ++slot;
  }
}

static void draw_pose_table(const u16 *table, u8 pose, s16 x, s16 y, u8 flip)
{
  const s16 *p=(const s16 *)((const u8 *)table+table[pose]);
  draw_pose_parts(p+1,*p,x,y,flip);
}

static void draw_fire_thrower(u8 pose, s16 x, s16 y, u8 flip)
{
  const s16 *p=(const s16 *)((const u8 *)poses+poses[pose]);
  /* The first two pieces are the body. Align their 32px width to the
   * encounter position and leave the detached capture piece out. */
  s16 offset=p[1]+16;
  draw_pose_parts(p+1,2,x+(flip ? offset : -offset),y,flip);
}

static void draw_pose(u8 pose, s16 x, s16 y, u8 flip)
{
  draw_pose_table(poses,pose,x,y,flip);
}

static void update_leaper_height(Leaper *e)
{
  s16 ground=ground_at(e->x);
  e->feet+=e->velocity;
  ++e->velocity;
  if (e->feet>=ground) {
    e->feet=ground; e->velocity=0; e->timer=20;
  }
}

static void update_enemies(void)
{
  for (u8 i=0;i<2;++i) {
    Leaper *e=&enemies[i];
    if (e->flash) {
      --e->flash;
      if (e->feet<(s16)ground_at(e->x)) update_leaper_height(e);
      continue;
    }
    if (!e->hp || e->x > (s16)xpos+152) continue;
    if (e->timer) --e->timer;
    else {
      if (!e->velocity && e->feet==ground_at(e->x)) e->velocity=-12;
      e->x+=e->speed;
      if (e->x<=e->left) e->speed=1;
      if (e->x>=e->right) e->speed=-1;
      update_leaper_height(e);
    }
    s16 dx=e->x-(s16)xpos, dy=e->feet-(s16)feet;
    u8 damage=sword_damage(e->x,e->feet);
    if (damage) {
      e->hp=remaining_hp(e->hp,damage); e->flash=20;
      engine_audio_command(CMD_PLAY_SFX,CITY_SFX_HIT);
    } else if (!invincible && !e->flash && dx>-16 && dx<16 && dy>-34 && dy<21) {
      hit_player(e->x);
    }
  }
}

static void player_step(void)
{
  u16 pad=bios_joy1_hold;
  s16 dir=((pad&PAD_RIGHT)!=0)-((pad&PAD_LEFT)!=0);
  u16 floor=support_at(xpos);
  u8 standing=floor && feet==floor && velocity>=0;
  u8 recoiling=hurt!=0;
  if (recoiling) {
    --hurt; dir=recoil; attack_buffer=jump_buffer=0;
  } else if (bios_joy1_hit&PAD_B) jump_buffer=4;
  if (room>=ROOF && !recoiling && (bios_joy1_hit&(PAD_A|PAD_C))) {
    if ((pad&PAD_UP) && (bios_joy1_hit&PAD_C) && has_magic && mana && !attack) {
      --mana;
      cast_city_magic();
    } else attack_buffer=4;
  }
  if (standing && jump_buffer) {
    velocity=-20; jump_buffer=0;
    engine_audio_command(CMD_PLAY_SFX,CITY_SFX_JUMP);
  }
  else if (jump_buffer) --jump_buffer;
  if (!recoiling && standing && (attack_buffer || (attack>1 && !aerial_attack))) dir=0;
  s16 nx=(s16)xpos+dir;
  if (dir && !recoiling) facing=dir>0;
  if (dir && nx>=8 && nx<=columns*8-8 &&
      (!support_at(nx) || feet<=support_at(nx))) {
    xpos=nx;
    if (++walking>48) walking=1;
  } else walking=0;
  if (attack) --attack;
  if (attack_buffer && !attack) {
    attack=15; aerial_attack=!standing || velocity<0; attack_buffer=0;
    engine_audio_command(CMD_PLAY_SFX,CITY_SFX_SWORD);
  } else if (attack_buffer) --attack_buffer;
  floor=support_at(xpos);
  s16 next=(s16)feet+(velocity>>2);
  if (velocity<16) ++velocity;
  if (velocity>=0 && floor && feet<=floor && next>=floor) {
    feet=floor; velocity=0;
  } else feet=next<48 ? 48 : next;
  if (room >= ROOF) step_sword();
}

static void draw(void)
{
  camera=camera_for_player();
  u16 world_camera=camera+(room==LATE ? 512 : 0);
  u16 cell=world_camera>>3;
  if (cell>camera_cell) column(cell+32);
  if (cell<camera_cell) column(cell);
  camera_cell=cell;
  if (room==FALL) {
    /* In the original VDP mode each pair of columns has its own vertical
     * origin. Seven pairs show the near wall, nine the more distant tower. */
    const s16 *v=movie_record+3;
    vdp_ctrl_32=VSRAM_W;
    for (u8 col=0;col<16;++col) {
      vdp_data_16=col<7 ? v[0] : v[2];
      vdp_data_16=v[1];
    }
  } else {
    /* Cell scroll entries are 32 bytes apart. Only rows 4..6 are clouds;
     * at scanline 56 the entire skyline switches to quarter camera speed. */
    u16 near_scroll=(u16)-world_camera;
    u16 far_camera=room==BOSS ? 1784 : world_camera;
    u16 far_scroll=(u16)-((far_camera+3)>>2);
    vdp_ctrl_16=VDP_REG_AUTOINC|32;
    vdp_ctrl_32=to_vdp_addr(BIOS_VDP_DEFAULT_HSCROLL+4*32)|VRAM_W;
    for (u8 row=4;row<28;++row) vdp_data_16=near_scroll;
    vdp_ctrl_32=to_vdp_addr(BIOS_VDP_DEFAULT_HSCROLL+4*32+2)|VRAM_W;
    for (u8 row=4;row<7;++row) vdp_data_16=cloud_tick>>1;
    for (u8 row=7;row<28;++row) vdp_data_16=far_scroll;
    vdp_ctrl_16=VDP_REG_AUTOINC|2;
  }
  slot=0;
  s16 screen_x=(s16)xpos-camera;
  if (room==MEETING || room==FALL) {
    draw_movie();
  } else {
    static const u8 street_strides[]={1,15,2,1,16,3};
    /* Pose 15 in the rooftop and arena banks still wears the street outfit. */
    static const u8 rooftop_strides[]={1,16,2,1,16,3};
    const u8 *strides=room==STREET ? street_strides : rooftop_strides;
    u8 pose=walking ? strides[(walking-1)>>3] : 0;
    if (feet!=support_at(xpos)) pose=velocity<=0 ? 17 : 18;
    if (room>=ROOF) draw_fighter(pose,screen_x);
    else draw_pose(pose,screen_x,feet,!facing);
    if (room==ROOF) {
      for (u8 i=0;i<2;++i) {
        Leaper *e=&enemies[i];
        draw_hit(e->x-camera,e->feet,e->flash);
        if (e->hp || e->flash)
          draw_pose(e->timer ? (e->timer>13?11:e->timer>6?12:13) : 14,e->x-camera,e->feet,e->speed>0);
      }
    }
  }
  if (room>=LATE) late_draw();
  if (room==ROOF || room==LATE) draw_city_items();
  if (!slot) {bios_sprlist[0].pos_y=0;slot=1;}
  bios_sprlist[slot-1].next=0;
  bios_copy_sprlist();
  if (room >= ROOF) draw_charge();
  if (displayed_hp!=hp || displayed_mana!=mana) {
    if (room>=ROOF) for (u8 i=0;i<12;++i) {
      s16 units=(s16)hp-2*i;
      hud[4+i]=combat_hp_tile(units>=2 ? 2 : units>0);
      hud[36+i]=i<4*mana ? hud_map[36+i] : 0x8000;
    }
    bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_WINDOW),(const u8 *)hud,128);
    displayed_hp=hp;
    displayed_mana=mana;
  }
}

void main(void)
{
  static vdp_reg const regs[]={
    (VDP_REG_PL_SIZE & 0xff00)|(VDP_PL_W64|VDP_PL_H32),VDP_REG_MODE4,
    VDP_REG_MODE3|2,VDP_REG_WIN_HPOS,VDP_REG_WIN_VPOS|4,0};
  u16 x=32,y=160;
  enum Room start=STREET;
  engine_resume_position(FILE_STAGE1_MMD,&x,&y);
  if (x>=CITY_MOVIE_FALL) {
    resume_movie_tick=x-CITY_MOVIE_FALL; start=FALL; x=origins[FALL]+192;
  } else if (x>=CITY_MOVIE_MEETING) {
    resume_movie_tick=x-CITY_MOVIE_MEETING; start=MEETING; x=origins[MEETING]+24;
  } else if (x>=8192) start=BOSS;
  else if (x>=2048) start=LATE;
  else if (x>=1280) start=ROOF;
  else if (x>=1024) start=FALL;
  else if (x>=768) start=MEETING;
  x-=origins[start];
  if (x<8 || x>=(start==LATE ? (packs[start][0]-64)*8 : packs[start][0]*8) || y>223) {start=STREET;x=32;y=160;}
  bios_load_vdp_regs_default();
  bios_load_vdp_regs(regs);
  hp=24; invincible=0; facing=1;
  reset_city_items();
  load_room(start,x,y+32);
  if (start==BOSS) boss_intro_tick=BOSS_VOICE_TICKS;
  /* PCE city playback repeats LBA 112021..122668 (track 38).
   * The mixed-mode Mega CD image places that recording on track 22. */
  engine_repeat_cdda(start==BOSS ? 27 : 22);
  for (;;) {
    bios_vblank_wait_default();
    ++scene_tick; ++cloud_tick;
    if (invincible) --invincible;
    if (room==MEETING || room==FALL) {
      if (room==MEETING && movie_time==0) engine_audio_command(CMD_CHAM_VOICE,0);
      if (advance_movie()) {
        if (room==MEETING) load_room(FALL,192,30);
        else load_room(ROOF,32,192);
      }
    } else {
      u8 in_intro=room==BOSS && boss_intro_tick<BOSS_VOICE_TICKS;
      if (in_intro) boss_introduction();
      else if (arena_arrival) {
        if (xpos<1304) {++xpos; if (++walking>48) walking=1;}
        else walking=0;
      } else {
        player_step();
        if (room==ROOF || room==LATE) collect_city_items();
      }
      if (room==STREET && xpos>=744) load_room(MEETING,24,168);
      else if (room==ROOF) {
        update_enemies();
        if (!hp || feet>224) {hp=24; load_room(ROOF,32,192); invincible=75;}
        if (!enemies[0].hp && !enemies[1].hp && xpos>=columns*8-24) {
          /* Both halves use the same streamed planes. Keep the ring, camera,
           * stride, sword charge and cloud phase when the encounter set changes. */
          room=LATE;
          xpos-=512; camera-=512;
          floor_map+=64; columns=map_columns-64;
          late_reset();
          bios_load_pal_update((Palette *)(city_late+2));
        }
      } else if (room>=LATE) {
        if (!arena_arrival && !in_intro) late_step();
        if (!hp || feet>224) {
          hp=24; load_room((enum Room)room,32,room==BOSS?192:160); invincible=75;
          if (room==BOSS) boss_intro_tick=BOSS_VOICE_TICKS;
        }
        else if (room==LATE && xpos>=1248 && feet==192) {
          arena_arrival=1;
          facing=1;
          if (camera>=1272 && xpos>=1304) {
            load_room(BOSS,32,192);
            engine_audio_command(CMD_PLAY_ONCE,23); /* PCE 39: the encounter dialogue. */
          }
        }
        else if (room==BOSS && !boss_hp && boss_clear>=120) {
          reset_scroll();
          engine_transition_scene(FILE_STAGE2_MMD,FILE_STORY_LAST,32,160,&next_module);
          return;
        }
      }
    }
    draw();
    if (bios_joy1_hit&PAD_START) {
      reset_scroll();
      u16 checkpoint=origins[room]+xpos;
      if (room==MEETING) checkpoint=CITY_MOVIE_MEETING+movie_time;
      if (room==FALL) checkpoint=CITY_MOVIE_FALL+movie_time;
      engine_save_position(FILE_STAGE1_MMD,checkpoint,feet>32 && feet<256 ? feet-32 : 0);
      next_module=FILE_GAME_MMD; return;
    }
  }
}
