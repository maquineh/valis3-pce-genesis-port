/* Runtime-independent checks for the STG4A movement and projectile cycle. */
#include "../game/src/stage4a_enemy_logic.h"
#include <stdio.h>

int main(void)
{
  SkullMotion s={1280,2304,0,0,0,0,0};
  ColumnShot p[STG4A_SHOTS]={{0}};
  unsigned char phase=0,timer=0;
  int i;
  /* Target is above and to the left: both axes must move. */
  stg4a_skull_step(&s,40,110);
  if (!s.awake || s.vx >= 0 || s.vy >= 0 || s.x >= 1280 || s.y >= 2304) return 1;
  for (i=0;i<29;i++) stg4a_skull_step(&s,40,110);
  if (s.x != 1280+s.vx || s.y != 2304+s.vy) return 2;
  stg4a_skull_step(&s,40,110);
  if (s.x >= 1280+s.vx || s.y >= 2304+s.vy) return 3;
  stg4a_column_step(p,&phase,&timer,168,144,1);
  if (phase != 1 || timer != 120 || !p[0].active || p[0].vx != 32 ||
      p[0].x != (168+18)*16+32 || p[0].y != (144-36)*16) return 4;
  for (i=0;i<119;i++) stg4a_column_step(p,&phase,&timer,168,144,1);
  if (phase != 1 || timer != 1) return 5;
  stg4a_column_step(p,&phase,&timer,168,144,1);
  if (phase != 2 || timer != 120 || !p[0].active || p[0].vx != -32 ||
      p[0].y != (144-20)*16) return 6;
  for (i=0;i<120;i++) stg4a_column_step(p,&phase,&timer,168,144,1);
  if (phase != 0 || timer != 120 || !p[0].active || p[0].vx != 32 ||
      p[0].y != (144-4)*16) return 7;
  puts("PASS: 2D skull pursuit and three projectile origins, directions and cadence");
  return 0;
}
