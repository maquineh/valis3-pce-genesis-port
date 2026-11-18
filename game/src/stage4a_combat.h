#ifndef VALIS3_STAGE4A_COMBAT_H
#define VALIS3_STAGE4A_COMBAT_H

/* Captured Yuko, weapon level 2: 24 HP, uncharged type-0 shot, power 4.
 * Actor centers use the PCE feet origin; all distances below are pixels. */
#define STG4A_PLAYER_HP 24
#define STG4A_SWORDS 3
typedef struct { short x, y, vx; unsigned char life, overlap; } Stage4aSword;

static int stg4a_within(short a, short b, short radius)
{
  short d=a-b;
  if (d<0) d=-d;
  return d < (radius+1)*16; /* PCE compares floor(abs(delta)/16) <= radius. */
}

static void stg4a_player_damage(StageCombat *c, unsigned char damage)
{
  if (c->invulnerable || c->game_over || !damage) return;
  c->hp = c->hp > damage ? c->hp-damage : 0;
  c->invulnerable=90;
  if (!c->hp) { c->game_over=1; c->death_timer=45; }
}

static void stg4a_combat_step(StageCombat *c, StageEnemy *e, SkullMotion *skull,
                               ColumnShot *shots, Stage4aSword *swords,
                               unsigned short px, unsigned short py,
                               unsigned char attack, unsigned char column_recovery)
{
  unsigned char i,j;
  short playerx=(px+8)*16, playery=((short)py-8)*16;
  if (c->game_over) return;
  if (c->invulnerable) --c->invulnerable;
  if (c->attack_cooldown) --c->attack_cooldown;
  if (c->attack_flash) --c->attack_flash;
  for (i=0;i<STAGE_ENEMY_MAX;++i) if (e[i].hit_flash) --e[i].hit_flash;
  if (attack && !c->attack_cooldown) {
    for (i=0;i<STG4A_SWORDS;++i) if (!swords[i].life) {
      swords[i].x=playerx+(c->facing?256:-256);
      swords[i].y=((short)py-4)*16;
      swords[i].vx=c->facing?32:-32;
      swords[i].life=24;
      swords[i].overlap=0;
      break;
    }
    c->attack_cooldown=10; c->attack_flash=7;
  }
  for (i=0;i<STG4A_SWORDS;++i) if (swords[i].life) {
    swords[i].x+=swords[i].vx;
    --swords[i].life;
    for (j=0;j<STAGE_ENEMY_MAX;++j) {
      short ex=(e[j].x+8)*16;
      short ey=(e[j].y+16-(j?40:16))*16;
      int overlap=e[j].alive && !(j && column_recovery==1) &&
        stg4a_within(ex,swords[i].x,(j?16:12)+2) &&
        stg4a_within(ey,swords[i].y,(j?40:12)+22);
      unsigned char bit=1<<j;
      if (!overlap) { swords[i].overlap &= ~bit; continue; }
      if ((swords[i].overlap & bit) || e[j].hit_flash ||
          (!j && (!skull->awake || skull->pause))) continue;
      swords[i].overlap |= bit;
      e[j].hp = e[j].hp > 4 ? e[j].hp-4 : 0;
      e[j].hit_flash=10;
      if (!e[j].hp) e[j].alive=0;
    }
  }
  for (i=0;i<STAGE_ENEMY_MAX && !c->invulnerable;++i) {
    short ex=(e[i].x+8)*16;
    short ey=(e[i].y+16-(i?40:16))*16;
    if (e[i].alive && !e[i].hit_flash && !(i && column_recovery==1) &&
        (i || (skull->awake && !skull->pause)) &&
        stg4a_within(ex,playerx,(i?16:12)+3) &&
        stg4a_within(ey,playery,(i?40:12)+22))
      stg4a_player_damage(c,i?3:2);
  }
  for (i=0;i<STG4A_SHOTS && !c->invulnerable;++i)
    if (shots[i].active && stg4a_within(shots[i].x,playerx,4+3) &&
        stg4a_within(shots[i].y,playery,4+22))
      stg4a_player_damage(c,3);
}
#endif
