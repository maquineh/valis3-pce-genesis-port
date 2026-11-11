#include "shared.h"
#include <sub/bios.h>
#include <sub/cdrom.h>
#include <sub/gate_arr.h>
#include <sub/memmap.h>
#include <system.h>

void load_ipx();

extern void sp_fatal();

u16 cd_track_number;

char const * const filenames[] = {
  "IPX.MMD;1", "GAME.MMD;1", "STAGE1.MMD;1", "STAGE2.MMD;1"};

// It's a good idea to put SPX's main in .init to ensure it's at the very start
// of the code, since we jump to where we expect it to be in memory
void main()
{
  enable_interrupts();
  register u16 command, param1;
  do
  {

    do
    {
      command = *ga_reg_comcmd0;
    } while (command == 0);

    if (command != *ga_reg_comcmd0)
      continue;

    param1 = *ga_reg_comcmd1;

    switch (command)
    {

      // load MMD
      case CMD_LOAD_FILE:
        load_file(CDROM_LOAD_CDC, filenames[param1], (u8 *) WORD_RAM_2M);
        grant_2m();
        break;

      // play CD audio track (0 = stop)
      case CMD_PLAY_CDDA:
        cd_track_number = param1;
        if (cd_track_number == 0)
          bios_msc_stop();
        else
          bios_msc_play(&cd_track_number);
        break;

      case CMD_STOP_CDDA:
        bios_msc_stop();
        break;

      default:
        break;
    }

    *ga_reg_comstat0 = 0xFFFFFFFF;

  } while (1);
}
