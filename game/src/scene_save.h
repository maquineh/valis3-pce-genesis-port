/* Checkpoint commands used by independently linked scene modules. */
#ifndef SCENE_SAVE_H
#define SCENE_SAVE_H

#include "shared.h"
#include <main/gate_arr.h>
#include <types.h>

/* The title marks CONTINUE in command word 4; START clears it. Consume the
 * marker once so future module loads cannot accidentally resume an old save. */
static int engine_resume_position(u16 scene, u16 *x, u16 *y)
{
  u16 marker = *ga_reg_comcmd4;
  u16 saved_scene, flags, saved_x, saved_y;
  *ga_reg_comcmd4 = 0;
  if (marker != SCENE_RESUME_MARKER) return 0;
  *ga_reg_comcmd1 = 0;
  *ga_reg_comcmd0 = CMD_READ_SCENE;
  while (*ga_reg_comstat0 == 0) asm("nop");
  saved_scene = *ga_reg_comstat1;
  saved_x = *ga_reg_comstat2;
  saved_y = *ga_reg_comstat3;
  flags = *ga_reg_comstat4;
  *ga_reg_comcmd0 = 0;
  while (*ga_reg_comstat0 != 0) asm("nop");
  if (saved_scene != scene || flags != 1) return 0;
  *x = saved_x;
  *y = saved_y;
  return 1;
}

/* Save the world-space top-left immediately before leaving a scene. Failed
 * writes are reported once to the title without overwriting the active slot. */
static int engine_save_position(u16 scene, u16 x, u16 y)
{
  u16 result;
  *ga_reg_comcmd1 = scene;
  *ga_reg_comcmd2 = x;
  *ga_reg_comcmd3 = y;
  *ga_reg_comcmd0 = CMD_WRITE_POSITION;
  while (*ga_reg_comstat0 == 0) asm("nop");
  result = *ga_reg_comstat1;
  *ga_reg_comcmd0 = 0;
  while (*ga_reg_comstat0 != 0) asm("nop");
  *ga_reg_comcmd5 = result ? 0 : SCENE_SAVE_ERROR_MARKER;
  return result != 0;
}

/* Move directly to the next prototype scene, making its spawn the CONTINUE
 * checkpoint before the module loader changes scenes. */
static int engine_transition_scene(u16 scene, u8 module, u16 x, u16 y,
                                  u8 *next_module)
{
  int saved;
  *ga_reg_comcmd4 = 0;
  saved = engine_save_position(scene, x, y);
  if (saved) *ga_reg_comcmd4 = SCENE_RESUME_MARKER;
  *next_module = module;
  return saved;
}

#endif
