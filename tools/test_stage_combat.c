/* Deterministic checks for the prototype combat loop used by captured scenes. */
#include "../game/src/stage_combat.h"

int main(void)
{
  StageCombat c;
  StageEnemy e[STAGE_ENEMY_MAX];
  stage_combat_init(&c,e,40,40,32,60,120,40,110,140);
  if (stage_combat_exit_ready(e,100,100)) return 13; /* enemies still live */

  /* Facing right: a nearby target takes two separate hits, then dies. */
  if (!stage_combat_step(&c,e,1,20,40,8,40)) return 1;
  if (e[0].hp != 1 || !e[0].alive) return 2;
  if (stage_combat_step(&c,e,1,20,40,8,40)) return 3; /* cooldown */
  while (c.attack_cooldown) --c.attack_cooldown;
  if (!stage_combat_step(&c,e,1,20,40,8,40)) return 4;
  if (e[0].alive) return 5;
  e[1].alive=0;
  if (!stage_combat_exit_ready(e,100,100) || stage_combat_exit_ready(e,99,100)) return 14;

  /* Facing left keeps the same reach but cannot hit a target behind us. */
  stage_combat_init(&c,e,40,40,32,60,120,40,110,140);
  stage_combat_face(&c,1,0);
  if (stage_combat_step(&c,e,1,20,40,8,40)) return 6;
  while (c.attack_cooldown) --c.attack_cooldown;
  if (!stage_combat_step(&c,e,1,60,40,8,40)) return 7;

  /* Contact costs one HP, invulnerability prevents repeated damage. */
  stage_combat_init(&c,e,40,40,32,60,120,40,110,140);
  if (stage_combat_step(&c,e,0,35,40,8,40)) return 8;
  if (c.hp != 2 || c.invulnerable != 60) return 9;
  stage_combat_step(&c,e,0,35,40,8,40);
  if (c.hp != 2) return 10;

  /* Third hit requests a spawn reset; respawn restores enemies and HP. */
  c.invulnerable=0;
  stage_combat_step(&c,e,0,35,40,8,40);
  c.invulnerable=0;
  stage_combat_step(&c,e,0,35,40,8,40);
  if (!c.game_over || c.hp != 0) return 11;
  e[0].alive=0;
  stage_combat_respawn(&c,e,8,40);
  if (c.game_over || c.hp != STAGE_PLAYER_HP || !e[0].alive || e[0].hp != 2) return 12;

  /* A slide hits each enemy once, then a new slide can finish it. */
  stage_combat_init(&c,e,40,40,32,60,120,40,110,140);
  {
    unsigned char mask = 0;
    if (!stage_combat_slide_damage(&c,e,35,40,&mask)) return 15;
    if (e[0].hp != 1 || !e[0].alive || mask != 1) return 16;
    if (stage_combat_slide_damage(&c,e,35,40,&mask)) return 17;
    mask = 0;
    if (!stage_combat_slide_damage(&c,e,35,40,&mask)) return 18;
    if (e[0].alive) return 19;
  }

  /* The lowered slide body ignores contact damage for its duration. */
  stage_combat_init(&c,e,40,40,32,60,120,40,110,140);
  stage_combat_step_pose(&c,e,0,35,40,8,40,0,1);
  if (c.hp != STAGE_PLAYER_HP) return 20;
  stage_combat_step_pose(&c,e,0,35,40,8,40,0,0);
  if (c.hp != STAGE_PLAYER_HP - 1) return 21;
  return 0;
}
