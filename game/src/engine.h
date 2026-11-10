/* Valis III Mega CD - engine services for game modules.
 *
 * Modules are linked independently from the IPX kernel, so each module needs
 * its own Gate Array / Sub CPU command code. This is the shared implementation.
 */
#ifndef VALIS3_ENGINE_H
#define VALIS3_ENGINE_H

#include "shared.h"
#include <main/gate_arr.h>
#include <main/memmap.h>
#include <system.h>
#include <types.h>

/* Ask the Sub CPU to start CD-DA playback at a disc track (1 = no playback).
 * Disc tracks are indexed on the built disc: track 1 = data, 2.. = the
 * original PC Engine soundtrack tracks (see docs/findings.md). */
static inline void engine_play_cdda(u8 disc_track)
{
  grant_2m();
  *ga_reg_comcmd1 = disc_track;
  *ga_reg_comcmd0 = CMD_PLAY_CDDA;
  do
  {
    asm("nop");
  } while (*ga_reg_comstat0 == 0);
  *ga_reg_comcmd0 = 0;
  do
  {
    asm("nop");
  } while (*ga_reg_comstat0 != 0);
  wait_2m();
}

static inline void engine_stop_cdda(void)
{
  engine_play_cdda(0);
}

#endif
