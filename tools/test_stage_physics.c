/* Exercise the production movement code with synthetic, precisely known geometry. */
#include "../game/src/stage_physics.h"
static const StageSurface platform[] = {{0, 255, 120, 120}};
static const StageSolid blocks[] = {{80, 0, 96, 160}, {0, 40, 80, 48}};
int main(void)
{
  StagePhysics p = {40, 80, 0, 0};
  int i;
  for (i = 0; i < 40; ++i) stage_physics_step(&p, platform, 1, blocks, 2, 256, 0, 0, 0, 40, 80);
  if (p.y != 104 || !p.grounded) return 1;
  for (i = 0; i < 40; ++i) stage_physics_step(&p, platform, 1, blocks, 2, 256, 0, 1, 0, 40, 80);
  if (p.x != 64) return 2;
  p.x = 40; p.y = 48; p.vy = -20; p.grounded = 0;
  stage_physics_step(&p, platform, 1, blocks, 2, 256, 0, 0, 0, 40, 80);
  if (p.y != 48 || p.vy != 0) return 3;
  p.x = 40; p.y = 104; p.vy = 0; p.grounded = 1;
  stage_physics_step(&p, platform, 1, blocks, 2, 256, 0, 0, 1, 40, 80);
  if (p.y >= 104 || p.vy >= 0) return 4;
  p.x = 0; p.y = 80; p.vy = 0; p.grounded = 0;
  stage_physics_step(&p, platform, 1, blocks, 2, 256, 1, 0, 0, 40, 80);
  if (p.x != 0) return 5;
  {
    static const StageSurface slopes[] = {{0, 127, 176, 112}, {128, 255, 112, 176}};
    static const StageSurface seam[] = {{0, 255, 120, 120}, {256, 511, 120, 120}};
    p.x = 0; p.y = 150; p.vy = 0; p.grounded = 0;
    for (i = 0; i < 20; ++i) stage_physics_step(&p, slopes, 2, blocks, 0, 512, 0, 0, 0, 0, 150);
    if (p.y != 156) return 6; /* x=8 samples y=172 */
    p.x = 32; p.y = 140; p.vy = 0; p.grounded = 0;
    for (i = 0; i < 40; ++i)
      stage_physics_step(&p, slopes, 2, blocks, 0, 512, 0, 1, 0, 32, 140);
    if (p.x != 112 || p.y != 100 || !p.grounded) return 9;
    p.x = 119; p.y = 90; p.vy = 0; p.grounded = 0;
    for (i = 0; i < 20; ++i) stage_physics_step(&p, slopes, 2, blocks, 0, 512, 0, 0, 0, 119, 90);
    if (p.y != 96) return 7; /* final x=127 samples y=112 */
    p.x = 240; p.y = 104; p.vy = 0; p.grounded = 1;
    for (i = 0; i < 16; ++i) stage_physics_step(&p, seam, 2, blocks, 0, 512, 0, 1, 0, 240, 104);
    if (p.x != 272 || p.y != 104 || !p.grounded) return 8;
  }
  /* DOWN + B slide: 18 frames, 3 px each, no jump, then grounded control. */
  p.x = 120; p.y = 104; p.vy = 0; p.grounded = 1;
  p.slide_timer = p.slide_dir = p.slide_hit = 0;
  stage_slide_start(&p, 1);
  if (p.slide_timer != 18 || p.slide_dir != 1) return 10;
  for (i = 0; i < 6; ++i)
    stage_physics_step(&p, platform, 1, blocks, 2, 256, 0, 0, 0, 120, 104);
  if (p.x != 138 || p.y != 104 || !p.grounded) return 11;
  stage_physics_step(&p, platform, 1, blocks, 2, 256, 0, 0, 1, 120, 104);
  if (p.y != 104 || p.vy != 0) return 12; /* jump is ignored mid-slide */
  for (i = 0; i < 12; ++i)
    stage_physics_step(&p, platform, 1, blocks, 2, 256, 0, 0, 0, 120, 104);
  if (p.slide_timer != 0 || p.x != 174 || p.y != 104 || !p.grounded) return 13;
  return 0;
}

