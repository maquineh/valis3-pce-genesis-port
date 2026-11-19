/* Native cartridge graphics; encounter timing, hit boxes and AI are approximated.
 * Positions here are local to the continuation (source roof x=512) or arena. */
static void draw_pose(u8 pose, s16 x, s16 y, u8 flip);
static void draw_fire_thrower(u8 pose, s16 x, s16 y, u8 flip);
static u16 ground_at(s16 x);
typedef struct {
  s16 x, foot, left, right, speed;
  u8 kind, hp, tick, flash;
} CityFoe;
typedef struct {s16 x,y,dx,dy;u8 life;} CityShot;
static CityFoe late_foes[7];
static CityShot late_shots[4];
static s16 boss_x,boss_feet;
static u16 boss_tick,boss_clear;
static u8 boss_hp,boss_flash,boss_meter,boss_phase;

extern const u16 city_boss_dialogue[];
/* Seventeen seconds of Japanese dialogue on the full-disc encounter track. */
#define BOSS_VOICE_TICKS 1022
static u16 boss_intro_tick;
static u8 boss_page;

static void load_boss_dialogue(void)
{
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(700)),
                         (const u8 *)(city_boss_dialogue+1),city_boss_dialogue[0]*16);
  __asm__ volatile ("" ::: "d0","d1","d2","a0","a1","memory");
}

/* Yuko crosses the billboard and turns towards the cloaked figure. */
static void boss_introduction(void)
{
  ++boss_intro_tick;
  if (xpos<236 && boss_intro_tick<=205) {
    ++xpos; facing=1;
    if (++walking>48) walking=1;
  } else {
    walking=0; facing=0;
  }
  u8 page=boss_intro_tick<196 ? 0 : boss_intro_tick<510 ? 1 : boss_intro_tick<720 ? 2 : boss_intro_tick<BOSS_VOICE_TICKS ? 3 : 0;
  if (boss_intro_tick==BOSS_VOICE_TICKS) engine_repeat_cdda(27); /* PCE 43 */
  if (page!=boss_page) {
    if (page) {
      const u16 *cells=city_boss_dialogue+1+16*city_boss_dialogue[0]+320*(page-1);
      bios_dma_xfer_word_ram(to_vdp_addr(BIOS_VDP_DEFAULT_WINDOW+256),(const u8 *)cells,320);
      __asm__ volatile ("" ::: "d0","d1","d2","a0","a1","memory");
    }
    vdp_ctrl_16=VDP_REG_WIN_VPOS|(page ? 14 : 4);
    boss_page=page;
  }
}

static void late_reset(void)
{
  late_foes[0]=(CityFoe){164,160,138,207,-1,0,2,0,0};
  late_foes[1]=(CityFoe){239,192,239,239,1,1,4,20,0};
  late_foes[2]=(CityFoe){452,116,390,505,-1,2,2,40,0};
  late_foes[3]=(CityFoe){640,160,605,700,-1,0,2,12,0};
  late_foes[4]=(CityFoe){808,176,808,808,1,1,4,35,0};
  late_foes[5]=(CityFoe){960,128,906,1030,-1,2,2,55,0};
  late_foes[6]=(CityFoe){1032,192,1032,1032,-1,1,4,0,0};
  for(u8 i=0;i<4;++i) late_shots[i].life=0;
  boss_x=184;boss_feet=176;boss_tick=boss_clear=0;
  boss_hp=16;boss_flash=0;boss_meter=255;boss_intro_tick=0;boss_page=0;boss_phase=0;
}

static void late_shoot(s16 x,s16 y,s16 dx,s16 dy)
{
  for(u8 i=0;i<4;++i) if(!late_shots[i].life) {
    late_shots[i]=(CityShot){x,y,dx,dy,100};
    return;
  }
}

static void late_projectiles(void)
{
  for(u8 i=0;i<4;++i) {
    CityShot *p=&late_shots[i];
    if(!p->life)continue;
    --p->life;p->x+=p->dx;p->y+=p->dy;
    s16 dx=p->x-(s16)xpos,dy=p->y-(s16)feet;
    if(dx>-13 && dx<13 && dy>-38 && dy<5) {hit_player(p->x);p->life=0;}
  }
}

static void late_step(void)
{
  late_projectiles();
  if(room==LATE) {
    for(u8 i=0;i<7;++i) {
      CityFoe *e=&late_foes[i];
      if(e->flash)--e->flash;
      if(!e->hp || e->x>(s16)xpos+152 || e->x<(s16)xpos-180)continue;
      ++e->tick;
      if(e->kind==1) {
        if(e->tick==78)e->speed=e->x>(s16)xpos ? -1 : 1;
        if(e->tick==80)late_shoot(e->x+12*e->speed,e->foot-36,2*e->speed,0);
        if(e->tick>=120)e->tick=0;
      } else {
        s16 next=e->x+e->speed;
        if(e->kind==0 && (ground_at(next-6)!=e->foot || ground_at(next+6)!=e->foot)) {
          e->speed=-e->speed;
        } else {
          e->x=next;
          if(e->x<=e->left)e->speed=1;
          if(e->x>=e->right)e->speed=-1;
        }
      }
      s16 foot=e->foot;
      if(e->kind==2)foot+=(e->tick&32)?(e->tick&31)/2:15-(e->tick&31)/2;
      u8 damage=sword_damage(e->x,foot);
      if(!e->flash && damage) {
        e->hp=remaining_hp(e->hp,damage); e->flash=20;
        engine_audio_command(CMD_PLAY_SFX,CITY_SFX_HIT);
      }
      s16 dx=e->x-(s16)xpos,dy=foot-(s16)feet;
      if(e->hp && !e->flash && dx>-19 && dx<19 && dy>-36 && dy<22)hit_player(e->x);
    }
    return;
  }
  if(boss_flash)--boss_flash;
  if(!boss_hp) {if(boss_clear<180)++boss_clear;return;}
  if(boss_tick<90) {++boss_tick;return;}
  u16 phase=boss_phase;
  if(++boss_phase>=240)boss_phase=0;
  if(phase<72) {
    boss_feet=176-(phase<36?phase:72-phase);
    boss_x+=(phase<36?-1:1);
    if(phase==36) {
      late_shoot(boss_x,boss_feet-30,-2,1);
      late_shoot(boss_x,boss_feet-30,2,1);
    }
  } else if(phase<144) {
    boss_feet=176;
    if(phase==80 || phase==110)late_shoot(boss_x,150,boss_x>(s16)xpos?-3:3,0);
  } else if(phase<192) {
    boss_feet=176;
    boss_x+=phase<168?-2:2;
    if(boss_x<40)boss_x=40;
    if(boss_x>216)boss_x=216;
  } else {
    boss_feet=176;
    if(phase==210)late_shoot(boss_x,140,boss_x>(s16)xpos?-2:2,1);
  }
  u8 damage=sword_damage(boss_x,boss_feet);
  if(!boss_flash && damage) {
    boss_hp=remaining_hp(boss_hp,damage); boss_flash=24;
    engine_audio_command(CMD_PLAY_SFX,CITY_SFX_HIT);
  }
  s16 dx=boss_x-(s16)xpos,dy=boss_feet-(s16)feet;
  if(!boss_flash && dx>-27 && dx<27 && dy>-52 && dy<26)hit_player(boss_x);
}

static void late_draw(void)
{
  if(room==LATE) {
    draw_pose(23,1096-camera,192,0);
    for(u8 i=0;i<7;++i) {
      CityFoe *e=&late_foes[i];
      s16 foot=e->foot;
      if(e->kind==2)foot+=(e->tick&32)?(e->tick&31)/2:15-(e->tick&31)/2;
      if(e->hp && !(e->flash&2)) {
        if (e->kind==1) draw_fire_thrower(e->tick>=78 && e->tick<100 ? 20 : 19,
                                         e->x-camera,foot,e->speed>0);
        else draw_pose(e->kind==2 ? 22 : 12,e->x-camera,foot,e->speed>0);
      }
      if(e->flash)draw_hit(e->x-camera,foot,e->flash);
    }
  } else {
    if(boss_hp && !(boss_flash&2)) {
      u16 phase=boss_tick<90?200:boss_phase;
      draw_pose(phase<72?25:phase>=144&&phase<192?27:24,boss_x,boss_feet,boss_x<(s16)xpos);
    }
    if(boss_flash)draw_hit(boss_x,boss_feet,boss_flash>20 ? 20 : boss_flash);
    if(boss_meter!=boss_hp) {
      /* Retail HP cells, repeated in the unused right part of the fourth HUD row. */
      for(u8 i=0;i<16;++i)hud[3*32+16+i]=i<boss_hp?hud_map[4]:0;
      bios_dma_xfer(to_vdp_addr(BIOS_VDP_DEFAULT_WINDOW),(const u8 *)hud,128);
      boss_meter=boss_hp;
    }
  }
  for(u8 i=0;i<4;++i) {
    CityShot *p=&late_shots[i];
    if(p->life)draw_pose(room==BOSS?28:21,p->x-camera,
                         p->y+(room==BOSS ? 0 : 12),p->dx>0);
  }
}
