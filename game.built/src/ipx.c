/* Valis III Mega CD - IPX: the kernel loaded from the boot sector.
 *
 * Responsibilities:
 *   - hook the VBLANK handler (BIOS sprite/palette update)
 *   - load the first user module (the title screen) from the CD
 *   - run the game loop / module scheduler
 */
#include "shared.h"
#include <main/bios.h>
#include <main/gate_arr.h>
#include <main/io.h>
#include <main/memmap.h>
#include <main/mmd.h>
#include <system.h>
#include <types.h>

u8 next_module;

void vblank_user(void)
{
  bios_copy_sprlist();
}

void main(void)
{
  *bios_vblank_user = vblank_user;

  /* font is used for debug text only; draw via our own engine */
  bios_load_font_defaults();
  bios_palette[1] = 0xEEE;
  bios_vdp_update_flags |= BIOS_MASK_COPY_PALETTE;

  next_module = FILE_GAME_MMD;
  enable_interrupts();

  for (;;)
  {
    /* give the Sub CPU Word RAM so it can read our module */
    grant_2m();

    *ga_reg_comcmd1 = next_module;
    *ga_reg_comcmd0 = CMD_LOAD_FILE;

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

    /* the module is now in 2M Word RAM; run its main() */
    void (*mmd_main)() = init_mmd();
    asm("call_mmd:");
    mmd_main();

    bios_clear_tables();
  }
}
