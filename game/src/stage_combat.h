#ifndef VALIS3_STAGE_COMBAT_H
#define VALIS3_STAGE_COMBAT_H

/* Small combat loop for the captured-scene prototypes. Enemy placement and
 * patrol limits are authored placeholders until original gameplay data is
 * available; this is not a reconstruction of the PCE enemy tables. */
#define STAGE_ENEMY_MAX 2
#define STAGE_PLAYER_HP 3

typedef struct {
  short x, y, left, right;
  unsigned char hp, alive, direction, hit_flash;
} StageEnemy;

typedef struct {
  unsigned char hp, invulnerable, attack_cooldown, facing;
  unsigned char attack_flash, game_over, death_timer;
} StageCombat;

static void stage_combat_init(StageCombat *c, StageEnemy *e,
                              short x1, short y1, short l1, short r1,
                              short x2, short y2, short l2, short r2)
{
  c->hp = STAGE_PLAYER_HP; c->invulnerable = 0; c->attack_cooldown = 0;
  c->facing = 1; c->attack_flash = 0; c->game_over = 0; c->death_timer = 0;
  e[0].x=x1; e[0].y=y1; e[0].left=l1; e[0].right=r1;
  e[0].hp=2; e[0].alive=1; e[0].direction=1; e[0].hit_flash=0;
  e[1].x=x2; e[1].y=y2; e[1].left=l2; e[1].right=r2;
  e[1].hp=2; e[1].alive=1; e[1].direction=1; e[1].hit_flash=0;
}

static unsigned char stage_combat_step_pose(StageCombat *c, StageEnemy *e,
                                        unsigned char attack,
                                        unsigned short px, unsigned short py,
                                        unsigned short spawn_x, unsigned short spawn_y,
                                        unsigned char move_enemies,
                                        unsigned char crouch)
{
  unsigned char i, hit = 0;
  if (c->game_over) return 0;
  if (c->invulnerable) --c->invulnerable;
  if (c->attack_cooldown) --c->attack_cooldown;
  if (c->attack_flash) --c->attack_flash;
  if (attack && !crouch && !c->attack_cooldown && !c->game_over) {
    short edge = (short)px + (c->facing ? 30 : -18);
    c->attack_cooldown=18; c->attack_flash=7;
    for (i=0; i<STAGE_ENEMY_MAX; ++i) {
      short ex;
      if (!e[i].alive || e[i].y + 16 < py || e[i].y > py + 16) continue;
      ex=e[i].x;
      if ((c->facing && ex >= (short)px && ex <= edge) ||
          (!c->facing && ex + 16 >= edge && ex <= (short)px)) {
        if (e[i].hp) --e[i].hp;
        e[i].hit_flash=6;
        if (!e[i].hp) e[i].alive=0;
        hit=1;
      }
    }
  }
  for (i=0; i<STAGE_ENEMY_MAX; ++i) {
    short ex;
    if (!e[i].alive) continue;
    if (e[i].hit_flash) --e[i].hit_flash;
    if (move_enemies) {
      e[i].x += e[i].direction ? 1 : -1;
      if (e[i].x <= e[i].left) { e[i].x=e[i].left; e[i].direction=1; }
      if (e[i].x >= e[i].right) { e[i].x=e[i].right; e[i].direction=0; }
    }
    ex=e[i].x;
    if (!crouch && !c->invulnerable && py < e[i].y+16 && py+16 > e[i].y &&
        (short)px < ex+16 && (short)px+16 > ex) {
      if (c->hp) --c->hp;
      c->invulnerable=60;
      if (!c->hp) { c->game_over=1; c->death_timer=45; return 0; }
    }
  }
  (void)spawn_x; (void)spawn_y;
  return hit;
}

static unsigned char stage_combat_step_ex(StageCombat *c, StageEnemy *e,
                                        unsigned char attack,
                                        unsigned short px, unsigned short py,
                                        unsigned short spawn_x, unsigned short spawn_y,
                                        unsigned char move_enemies)
{
  return stage_combat_step_pose(c, e, attack, px, py, spawn_x, spawn_y,
                                move_enemies, 0);
}

/* A sliding body hits each enemy at most once per slide. */
static unsigned char stage_combat_slide_damage(StageCombat *c, StageEnemy *e,
                                               unsigned short px, unsigned short py,
                                               unsigned char *hit_mask)
{
  unsigned char i, hit = 0;
  for (i=0; i<STAGE_ENEMY_MAX; ++i) {
    if (!e[i].alive || (*hit_mask & (1u << i))) continue;
    if (py + 8 < e[i].y + 16 && py + 16 > e[i].y &&
        (short)px - 4 < e[i].x + 16 && (short)px + 20 > e[i].x) {
      if (e[i].hp) --e[i].hp;
      e[i].hit_flash=6;
      if (!e[i].hp) e[i].alive=0;
      *hit_mask |= (unsigned char)(1u << i);
      hit=1;
    }
  }
  (void)c;
  return hit;
}

static unsigned char stage_combat_step(StageCombat *c, StageEnemy *e,
                                        unsigned char attack,
                                        unsigned short px, unsigned short py,
                                        unsigned short spawn_x, unsigned short spawn_y)
{
  return stage_combat_step_ex(c, e, attack, px, py, spawn_x, spawn_y, 1);
}

static void stage_combat_respawn(StageCombat *c, StageEnemy *e,
                                 unsigned short spawn_x, unsigned short spawn_y)
{
  unsigned char i;
  c->hp=STAGE_PLAYER_HP; c->invulnerable=60; c->game_over=0; c->death_timer=0;
  for (i=0; i<STAGE_ENEMY_MAX; ++i) {
    e[i].alive=1; e[i].hp=2; e[i].hit_flash=0;
    if (e[i].x < spawn_x) e[i].direction=1;
    else e[i].direction=0;
  }
  (void)spawn_y;
}

static void stage_combat_face(StageCombat *c, int left, int right)
{
  if (left && !right) c->facing=0;
  else if (right && !left) c->facing=1;
}

static int stage_combat_cleared(const StageEnemy *e)
{
  unsigned char i;
  for (i=0; i<STAGE_ENEMY_MAX; ++i) if (e[i].alive) return 0;
  return 1;
}

static int stage_combat_exit_ready(const StageEnemy *e, unsigned short x,
                                   unsigned short exit_x)
{
  return stage_combat_cleared(e) && x >= exit_x;
}
#endif
