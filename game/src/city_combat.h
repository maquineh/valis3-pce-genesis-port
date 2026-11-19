/* Japanese cartridge SAT sequences captured in pack_city_combat.py. */
extern const u16 city_combat[];
static const u16 *combat_poses, *charge_cells;
static s16 wave_x, wave_feet;
static s8 recoil;
static u8 hurt, charge, last_charge, wave_life, wave_left, wave_damage;
static void draw_pose_table(const u16 *table, u8 pose, s16 x, s16 y, u8 flip);

static void load_combat(void)
{
  const u16 *bank = city_combat;
  u16 base = *bank++, count = *bank++;
  const u16 *patterns = bank;
  bank += count*16;
  u16 table_words = *bank++;
  combat_poses = bank;
  charge_cells = bank + table_words;
  charge = 42;
  last_charge = 255;
  hurt = wave_life = 0;
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(base-2)),charge_cells+43*22,32);
  __asm__ volatile ("" ::: "d0","d1","d2","a0","a1","memory");
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(base)),(const u8 *)patterns,count*16);
  /* The BIOS advances its DMA source in D1. Megadev declares D1 input-only. */
  __asm__ volatile ("" ::: "d0","d1","d2","a0","a1","memory");
}

static u16 combat_hp_tile(u8 units)
{
  if (units >= 2) return hud_map[4];
  return 0x8000 | (city_combat[0]-1-units);
}

static void hit_player(s16 enemy_x)
{
  if (invincible || !hp) return;
  hp=hp>2 ? hp-2 : 0;
  hurt = 24;
  invincible = 90;
  recoil = enemy_x < (s16)xpos ? 2 : -2;
  facing = recoil < 0;
  attack = attack_buffer = jump_buffer = 0;
  engine_audio_command(CMD_PLAY_SFX,CITY_SFX_HIT);
}

static void start_wave(u8 life, u8 damage)
{
  wave_left = !facing;
  wave_x = (s16)xpos + (wave_left ? 2 : -2);
  wave_feet = feet;
  wave_life = life;
  wave_damage = damage;
}

static void cast_city_magic(void)
{
  start_wave(16,3+strength);
  engine_audio_command(CMD_PLAY_SFX,CITY_SFX_MAGIC);
}

static void step_sword(void)
{
  if (wave_life) {
    --wave_life;
    wave_x += wave_left ? -6 : 6;
  }
  if (attack == 8) {
    start_wave(1+charge/5,1+strength);
    charge = 0;
  } else if (charge < 42) {
    ++charge;
  }
}

static u8 remaining_hp(u8 health, u8 damage)
{
  return health > damage ? health-damage : 0;
}

static u8 sword_damage(s16 enemy_x, s16 enemy_feet)
{
  s16 dx = enemy_x-(s16)xpos, dy = enemy_feet-(s16)feet;
  s16 ahead = facing ? dx : -dx;
  if (attack && attack <= 12 && ahead >= -8 && ahead <= 32 && dy >= -39 && dy <= 26)
    return 1+strength;
  if (!wave_life) return 0;
  ahead = wave_left ? wave_x-enemy_x : enemy_x-wave_x;
  dy = enemy_feet-wave_feet;
  return ahead >= -8 && ahead <= 22 && dy >= -40 && dy <= 22 ? wave_damage : 0;
}

static void draw_fighter(u8 normal_pose, s16 x)
{
  if (hurt) {
    if (hurt & 1)
      draw_pose_table(combat_poses, hurt>19 ? 8 : hurt>9 ? 9 : 10,x,feet,!facing);
  } else if (attack) {
    u8 pose = attack>12 ? 0 : attack>8 ? 1 : attack>4 ? 2 : 3;
    draw_pose_table(combat_poses,pose+(aerial_attack ? 4 : 0),x,feet,!facing);
  } else {
    draw_pose_table(poses,normal_pose,x,feet,!facing);
  }
  if (wave_life) draw_pose_table(combat_poses,11,wave_x-camera,wave_feet,wave_left);
}

static void draw_hit(s16 screen_x, s16 enemy_feet, u8 flash)
{
  if (flash) {
    u8 frame = flash >= 20 ? 0 : (20-flash)>>2;
    draw_pose_table(combat_poses,12+frame,screen_x,enemy_feet,0);
  }
}

static void draw_charge(void)
{
  if (last_charge == charge) return;
  const u16 *cells = charge_cells + 22*charge;
  for (u8 row=2;row<=3;++row) {
    for (u8 col=5;col<=15;++col) {
      u16 value = *cells++;
      u8 index = row*32 + col;
      if (hud[index] != value) {
        hud[index] = value;
        vdp_ctrl_32 = to_vdp_addr(BIOS_VDP_DEFAULT_WINDOW + index*2) | VRAM_W;
        vdp_data_16 = value;
      }
    }
  }
  last_charge = charge;
}
