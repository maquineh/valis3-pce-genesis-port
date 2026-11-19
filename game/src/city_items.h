enum CityItemKind { CITY_POWER, CITY_HEALTH, CITY_MAGIC, CITY_MANA };
enum { CITY_ITEM_TILE = 1280, CITY_ITEM_LINE = 1, CITY_MAX_MANA = 3 };

/* Prototype item locations, in each room's local coordinates. */
static const struct {
  u16 x, y;
  u8 room, kind;
} city_items[] = {
  {112,137,ROOF,CITY_POWER}, {318,122,ROOF,CITY_HEALTH},
  {48,106,LATE,CITY_MAGIC}, {168,106,LATE,CITY_MANA},
  {332,122,LATE,CITY_HEALTH}, {698,137,LATE,CITY_MANA},
  {930,106,LATE,CITY_MANA}, {1080,137,LATE,CITY_HEALTH}
};

static u8 taken_items, strength, has_magic, mana, displayed_mana;

/* Original PCE HUD icons packed by tools/pack_pce_icons.py: four 2x2 sprite
 * tiles mapped to the captured line-1 colours, so CRAM is not modified. */
extern const u8 city_item_bin[];

static void reset_city_items(void)
{
  taken_items=strength=has_magic=mana=0;
}

static void load_city_items(void)
{
  bios_dma_xfer(to_vdp_addr(vram_addr_from_tileidx(CITY_ITEM_TILE)),
                city_item_bin,16*16);
}

static void collect_city_items(void)
{
  for (u8 i=0; i<sizeof(city_items)/sizeof(city_items[0]); ++i) {
    u8 flag=1u<<i;
    s16 dx=(s16)city_items[i].x-(s16)xpos;
    s16 dy=(s16)city_items[i].y-(s16)feet;
    if (city_items[i].room!=room || (taken_items&flag) ||
        dx<=-14 || dx>=14 || dy<=-45 || dy>=0) continue;
    u8 picked=1;
    switch (city_items[i].kind) {
      case CITY_POWER: strength=1; break;
      case CITY_HEALTH:
        if (hp>=24) picked=0; else hp=hp<=16 ? hp+8 : 24;
        break;
      case CITY_MAGIC: has_magic=1; break;
      case CITY_MANA:
        if (mana>=CITY_MAX_MANA) picked=0; else ++mana;
        break;
    }
    if (picked) {
      taken_items|=flag;
      engine_audio_command(CMD_PLAY_SFX,CITY_SFX_ITEM);
    }
  }
}

static void draw_pose_parts(const s16 *pieces, u16 count, s16 x, s16 y, u8 flip);

static void draw_city_items(void)
{
  for (u8 i=0; i<sizeof(city_items)/sizeof(city_items[0]); ++i) {
    if (city_items[i].room!=room || (taken_items&(1u<<i))) continue;
    s16 piece[]={-8,-16,
                 (s16)((CITY_ITEM_LINE<<13)|(CITY_ITEM_TILE+city_items[i].kind*4)),
                 5};
    draw_pose_parts(piece,1,city_items[i].x-camera,city_items[i].y,0);
  }
}
