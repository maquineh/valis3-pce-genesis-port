#ifndef STAGE_PHYSICS_H
#define STAGE_PHYSICS_H
/* One-way tops and solid rectangles approximate captured art. Slopes use a
 * 1:2 gradient; the final pixel is clamped to the specified endpoint. */
typedef struct { unsigned short x1, x2, y1, y2; } StageSurface;
typedef struct { unsigned short x1, y1, x2, y2; } StageSolid; /* half-open */
typedef struct { unsigned short x, y; short vy; unsigned short grounded;
                 unsigned char slide_timer, slide_dir, slide_hit; } StagePhysics;

/* Down + B starts the PCE slide: 18 frames at three pixels per frame. The
 * lowered body ignores enemy contact and damages each enemy once per slide. */
static void stage_slide_start(StagePhysics *p, unsigned char direction)
{
  if (p->slide_timer || !p->grounded) return;
  p->slide_timer = 18;
  p->slide_dir = direction != 0;
  p->slide_hit = 0;
  p->vy = 0;
}

static int stage_blocked(short x, short y, const StageSolid *solids, unsigned short count)
{
  unsigned short i;
  for (i = 0; i < count; ++i)
    if (x < solids[i].x2 && x + 16 > solids[i].x1 &&
        y < solids[i].y2 && y + 16 > solids[i].y1) return 1;
  return 0;
}
static void stage_physics_step(StagePhysics *p, const StageSurface *surfaces,
                               unsigned short count, const StageSolid *solids,
                               unsigned short solid_count, unsigned short width,
                               int left, int right, int jump,
                               unsigned short spawn_x, unsigned short spawn_y)
{
  short dx = (right && !left) ? 1 : ((left && !right) ? -1 : 0);
  short dy, direction, next_y;
  unsigned short i, step, oldfoot, floor, sample, move_steps;
  unsigned char sliding = p->slide_timer != 0;
  if (sliding) {
    --p->slide_timer;
    dx = p->slide_dir ? 1 : -1;
    move_steps = 3;
    jump = 0; /* A slide cannot be interrupted by a jump. */
  } else {
    move_steps = 2;
  }
  for (step = 0; step < move_steps && dx; ++step) {
    short nx = (short)p->x + dx;
    if (nx >= 0 && nx <= width - 16 && !stage_blocked(nx, p->y, solids, solid_count)) p->x = nx;
    else break;
  }
  if (jump && p->grounded) { p->vy = -20; p->grounded = 0; }
  if (p->vy < 24) p->vy += 2;
  dy = p->vy / 4;
  direction = dy < 0 ? -1 : 1;
  if (!dy) dy = 1; /* Probe support even at zero vertical velocity. */
  else if (dy < 0) dy = -dy;
  for (step = 0; step < dy; ++step) {
    next_y = (short)p->y + direction;
    if (next_y < 0 || stage_blocked(p->x, next_y, solids, solid_count)) {
      p->vy = 0; p->grounded = direction > 0; break;
    }
    if (direction > 0) {
      oldfoot = p->y + 16;
      for (i = 0; i < count; ++i) {
        const StageSurface *s = &surfaces[i];
        if (p->x + 15 < s->x1 || p->x > s->x2) continue;
        sample = p->x + 8;
        if (sample < s->x1) sample = s->x1;
        if (sample > s->x2) sample = s->x2;
        floor = s->y1;
        if (sample == s->x2) floor = s->y2;
        else if (s->y2 > s->y1) floor += (sample - s->x1) >> 1;
        else if (s->y2 < s->y1) floor -= (sample - s->x1) >> 1;
        /* Six pixels of support tolerance keep a player attached to the
         * captured slopes after attack recoil, landing and CONTINUE. */
        if (oldfoot <= floor + 6 && oldfoot + 1 >= floor) {
          p->y = floor - 16; p->vy = 0; p->grounded = 1; break;
        }
      }
      if (i < count) break;
    }
    p->y = next_y; p->grounded = 0;
  }
  if (p->y > 176) { p->x = spawn_x; p->y = spawn_y; p->vy = 0; p->grounded = 0; }
}
#endif

