#ifndef VALIS3_STAGE4A_ENEMY_LOGIC_H
#define VALIS3_STAGE4A_ENEMY_LOGIC_H

/* PCE coordinates and velocities use four fractional bits.  Angles are derived
 * from the original $7A34 thresholds and $7B54 velocity coefficient table. */
typedef struct { short x, y, vx, vy; unsigned char awake, pause, timer; } SkullMotion;
typedef struct { short x, y, vx; unsigned char active; } ColumnShot;
#define STG4A_SHOTS 6

static unsigned char stg4a_direction(short dx, short dy)
{
  static const unsigned char thresholds[7] = {3,6,10,16,23,38,80};
  unsigned long ax = dx < 0 ? -(long)dx : dx;
  unsigned long ay = dy < 0 ? -(long)dy : dy;
  unsigned long remainder = ay << 4;
  unsigned char ratio = 0;
  unsigned char i=0, a;
  if (!ax) ratio=80;
  else while (remainder >= ax && ratio < 80) { remainder -= ax; ++ratio; }
  while (i < 7 && ratio >= thresholds[i]) ++i;
  if (dx >= 0) a = dy >= 0 ? 8+i : 7-i;
  else a = dy >= 0 ? 23-i : 24+i;
  if ((a & 7) == 0) ++a;
  else if ((a & 7) == 7) --a;
  return ((a+1) >> 1) & 15;
}

static void stg4a_skull_step(SkullMotion *s, short px, short py)
{
  static const signed char vx[16] = {0,3,5,7,8,7,5,3,0,-3,-5,-7,-8,-7,-5,-3};
  static const signed char vy[16] = {-8,-7,-5,-3,0,3,5,7,8,7,5,3,0,-3,-5,-7};
  short dx=px*16-s->x, dy=py*16-s->y;
  if (!s->awake) {
    if (dx < -1280 || dx >= 1280) return;
    s->awake=1; s->pause=29; s->timer=0;
  } else if (s->pause) {
    --s->pause;
    if (s->timer) --s->timer;
    return;
  }
  if (!s->timer) {
    unsigned char dir=stg4a_direction(dx,dy);
    s->vx=vx[dir]; s->vy=vy[dir]; s->timer=30;
  }
  --s->timer;
  s->x+=s->vx; s->y+=s->vy;
}

static void stg4a_column_step(ColumnShot *shots, unsigned char *phase,
                              unsigned char *timer, short x, short y,
                              unsigned char enabled)
{
  static const signed char ox[3]={18,-18,18}, oy[3]={-36,-20,-4};
  unsigned char i;
  if (enabled && *timer) --*timer;
  if (enabled && !*timer) {
    for (i=0; i<STG4A_SHOTS; ++i) if (!shots[i].active) {
      shots[i].x=(x+ox[*phase])*16;
      shots[i].y=(y+oy[*phase])*16;
      shots[i].vx=(*phase == 1 ? -32 : 32);
      shots[i].active=1;
      break;
    }
    if (++*phase == 3) *phase=0;
    *timer=120;
  }
  for (i=0; i<STG4A_SHOTS; ++i) if (shots[i].active) {
    shots[i].x+=shots[i].vx;
    if (shots[i].x < -256 || shots[i].x > 4352) shots[i].active=0;
  }
}
#endif
