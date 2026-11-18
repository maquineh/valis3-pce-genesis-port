/* Tests the port's captured-Yuko combat values and collision boundaries. */
#include "../game/src/stage_combat.h"
#include "../game/src/stage4a_enemy_logic.h"
#include "../game/src/stage4a_combat.h"
#include <stdio.h>

int main(void)
{
  StageCombat c; StageEnemy e[2]; SkullMotion s={0};
  ColumnShot shots[STG4A_SHOTS]={{0}};
  Stage4aSword swords[STG4A_SWORDS]={{0}};
  int i;
  stage_combat_init(&c,e,47,120,0,240,160,128,160,160);
  c.hp=24; e[0].hp=8; e[1].alive=0; s.awake=1;
  stg4a_combat_step(&c,e,&s,shots,swords,32,128,0,0);
  if (c.hp!=22 || c.invulnerable!=90) return 1; /* x separation 15 */
  for (i=0;i<89;i++) stg4a_combat_step(&c,e,&s,shots,swords,32,128,0,0);
  if (c.hp!=22 || c.invulnerable!=1) return 2;
  stg4a_combat_step(&c,e,&s,shots,swords,32,128,0,0);
  if (c.hp!=20 || c.invulnerable!=90) return 3;
  c.hp=24;c.invulnerable=0;e[0].x=48; /* separation 16 misses */
  stg4a_combat_step(&c,e,&s,shots,swords,32,128,0,0);
  if (c.hp!=24) return 4;
  e[0].alive=0; shots[0].active=1;shots[0].x=40*16;shots[0].y=120*16;
  stg4a_combat_step(&c,e,&s,shots,swords,32,128,0,0);
  if (c.hp!=21 || c.invulnerable!=90 || !shots[0].active) return 5;
  shots[0].active=0;c.invulnerable=0;c.hp=24;
  e[0].alive=1;e[0].x=48;e[0].y=120;e[0].hp=8;e[0].hit_flash=0;
  stg4a_combat_step(&c,e,&s,shots,swords,32,128,1,0);
  if (e[0].hp!=4 || e[0].hit_flash!=10) return 6;
  for (i=0;i<10;i++) stg4a_combat_step(&c,e,&s,shots,swords,32,128,0,0);
  if (e[0].hp!=4) return 7; /* same projectile cannot hit twice */
  for (i=0;i<STG4A_SWORDS;i++) swords[i].life=0;
  e[0].alive=0;e[1].alive=1;e[1].hp=212;e[1].x=32;e[1].y=128;
  e[1].hit_flash=0;c.hp=24;c.invulnerable=0;c.attack_cooldown=0;
  stg4a_combat_step(&c,e,&s,shots,swords,32,128,0,1);
  if (c.hp!=24 || e[1].hp!=212) return 8; /* first recovery phase masked */
  stg4a_combat_step(&c,e,&s,shots,swords,32,128,0,2);
  if (c.hp!=21 || c.invulnerable!=90) return 9;
  stg4a_combat_step(&c,e,&s,shots,swords,32,128,1,2);
  if (e[1].hp!=208 || e[1].hit_flash!=10) return 10;
  puts("PASS: PCE-derived contact damage, invulnerability and weapon protection");
  return 0;
}
