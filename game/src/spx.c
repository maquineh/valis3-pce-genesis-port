#include "shared.h"
#include "city_sfx_lengths.h"
#include "cham_voice.h"
#include "scene_save_format.h"
#include <sub/bios.h>
#include <sub/cdrom.h>
#include <sub/gate_arr.h>
#include <sub/memmap.h>
#include <sub/bram.h>
#include <system.h>

void load_ipx();

extern void sp_fatal();

u16 cd_track_number;

/* Alternate two project-owned BRAM blocks so a failed update leaves the
 * previously valid checkpoint intact. Slot 0 is the legacy v1 file. */
static BramFileInfo const scene_files[2] = {
  {"VALIS3MCD1", 0, 1}, {"VALIS3MCD2", 0, 1}
};
static u8 scene_data[64];

/* 0 = absent, 1 = valid checkpoint, 2 = occupied but not safe to overwrite. */
static int read_slot(u8 slot, SceneCheckpoint *record)
{
  BrmserchRes *found = bram_brmserch(scene_files[slot].filename);
  BrmreadRes *read;
  if (found == NULL) return 0;
  if (found->filesize != 1 || (u8)found->mode != 0) return 2;
  read = bram_brmread(scene_files[slot].filename, scene_data);
  /* The devkit wrapper omits A0/A1 and memory clobbers although BRMREAD
   * changes both address registers while copying the file. */
  asm volatile("" ::: "a0", "a1", "memory");
  if (!read->success || read->filesize != 1 || read->mode != 0) return 2;
  return checkpoint_decode(scene_data, record) ? 1 : 2;
}

static int init_bram(void)
{
  BrminitRes init;
  bram_brminit(&init);
  return init.status == SegaFormatted;
}

/* Caller initializes BRAM. A valid v2 record outranks v1, then sequence wins. */
static int active_slot(SceneCheckpoint records[2], int states[2])
{
  states[0] = read_slot(0, &records[0]);
  states[1] = read_slot(1, &records[1]);
  if (states[0] != 1) return states[1] == 1 ? 1 : -1;
  if (states[1] != 1) return 0;
  if (records[0].version != records[1].version)
    return records[1].version == 2 ? 1 : 0;
  return checkpoint_newer(records[1].sequence, records[0].sequence) ? 1 : 0;
}

static void read_scene(void)
{
  SceneCheckpoint records[2];
  int states[2], active;
  *ga_reg_comstat1 = *ga_reg_comstat2 = *ga_reg_comstat3 = *ga_reg_comstat4 = 0;
  if (!init_bram()) return;
  active = active_slot(records, states);
  if (active < 0) return;
  *ga_reg_comstat1 = records[active].scene;
  *ga_reg_comstat2 = records[active].x;
  *ga_reg_comstat3 = records[active].y;
  *ga_reg_comstat4 = records[active].has_position;
}

/* Never format BRAM or overwrite occupied slots we cannot authenticate. */
static u16 write_scene(u16 scene, u16 has_position, u16 x, u16 y)
{
  SceneCheckpoint records[2], value, verified;
  int states[2], active, target;
  if (scene > 255 || !checkpoint_screens((u8)scene) || has_position > 1 ||
      (has_position && !checkpoint_valid_position((u8)scene, x, y))) return 0;
  if (!init_bram()) return 0;
  active = active_slot(records, states);
  target = active < 0 ? (states[0] == 0 ? 0 : 1) : 1 - active;
  if (states[target] == 2) return 0;
  value.scene = (u8)scene;
  value.has_position = (u8)has_position;
  value.x = has_position ? x : 0;
  value.y = has_position ? y : 0;
  value.sequence = active < 0 ? 1 : (u16)(records[active].sequence + 1);
  value.version = 2;
  checkpoint_encode(scene_data, &value);
  asm volatile("" ::: "memory");
  if (!bram_brmwrite(&scene_files[target], scene_data)) return 0;
  asm volatile("" ::: "a0", "a1", "memory");
  return read_slot((u8)target, &verified) == 1 && verified.version == 2 &&
         verified.sequence == value.sequence && verified.scene == value.scene &&
         verified.has_position == value.has_position && verified.x == value.x && verified.y == value.y;
}

char const * const filenames[] = {
  "IPX.MMD;1", "GAME.MMD;1", "STAGE1.MMD;1", "STAGE2.MMD;1", "STAGE2B.MMD;1",
  "STAGE3A.MMD;1", "STAGE2C.MMD;1", "STAGE2A2.MMD;1", "STAGE2CG.MMD;1",
  "STAGE2CB.MMD;1", "STAGE4A.MMD;1", "STAGE1A.MMD;1", "STAGE4AX.MMD;1",
  "STORY06.MMD;1", "STORY07.MMD;1", "STORY08.MMD;1", "STORY09.MMD;1",
  "STORY10.MMD;1", "STORY11.MMD;1", "STORY12.MMD;1", "STG2BOSS.MMD;1"};

extern const u8 city_sfx_data[];

/* One short effect occupies each 4 KiB PCM bank; the player voice follows at
 * bank CITY_SFX_COUNT.  Samples are sign-magnitude with an 0xFF loop marker
 * and a silent 0x80 byte at the loop address. */
static void prepare_city_sfx(void)
{
  static u8 uploaded;
  if (uploaded) return;
  const u8 *p = city_sfx_data;
  for (u8 bank = 0; bank < CITY_SFX_BANKS; ++bank) {
    *PCM_CTRL = WAVEBANK(bank);
    volatile u8 *dest = (volatile u8 *)(_PCM_RAM + 1);
    for (u16 i = 0; i < CITY_SFX_BANK_BYTES; ++i) {
      *dest = *p++;
      dest += 2;
    }
  }
  uploaded = 1;
}

static void play_city_sfx(u16 id)
{
  if (id >= CITY_SFX_COUNT) return;
  const u16 pitch = 694; /* 11,025 Hz at the 32,552 Hz PCM clock. */
  u16 start = city_sfx_offsets[id];
  u16 loop = (u16)(start + city_sfx_lengths[id]);
  prepare_city_sfx();
  *PCM_CDISABLE = 0xfc; /* channels 1 and 2 on; leave the rest disabled */
  *PCM_CTRL = CHANNEL(2);
  *PCM_ENV = 0xff;
  *PCM_PAN = 0xff;
  *PCM_FDL = (u8)pitch;
  *PCM_FDH = pitch >> 8;
  *PCM_LSL = (u8)loop;
  *PCM_LSH = loop >> 8;
  *PCM_ST = start >> 8;
  *PCM_CDISABLE = 0xfc;
}

static const u16 *story_tail;
static char tail_name[] = "STORY00.EXT;1";

/* Banks 1..3 are free above the SPX code and BRAM buffers. Read ahead while
 * the drive is in data mode, then serve later pages entirely from RAM. */
static void prepare_story(u16 module)
{
  const u16 *header = (const u16 *)(WORD_RAM_2M + STORY_OFFSET);
  if (!header[2]) return;
  const char *name = filenames[module];
  tail_name[5] = name[5];
  tail_name[6] = name[6];
  story_tail = (const u16 *)PRG_RAM_BANK2;
  if (!load_file(CDROM_LOAD_CDC, tail_name, (u8 *)story_tail)) sp_fatal();
}

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
        *PCM_CDISABLE = 0xff;
        if (!load_file(CDROM_LOAD_CDC, filenames[param1], (u8 *)WORD_RAM_2M)) sp_fatal();
        if (param1 >= FILE_STORY_FIRST && param1 <= FILE_STORY_LAST) prepare_story(param1);
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

      case CMD_STORY_REFILL: {
        u16 words = *story_tail++;
        u16 *dest = (u16 *)(WORD_RAM_2M + STORY_OFFSET);
        while (words--) *dest++ = *story_tail++;
        grant_2m();
        break;
      }

      case CMD_PLAY_ONCE:
        cd_track_number = param1;
        asm volatile("" ::: "memory");
        bios_msc_play1(&cd_track_number);
        break;

      case CMD_STOP_CDDA:
        bios_msc_stop();
        break;

      case CMD_REPEAT_CDDA:
        prepare_city_voice();
        cd_track_number = param1;
        asm volatile("" ::: "memory");
        bios_msc_playr(&cd_track_number);
        break;

      case CMD_CHAM_VOICE:
        play_city_voice();
        break;

      case CMD_PLAY_SFX:
        play_city_sfx(param1);
        break;

      case CMD_READ_SCENE:
        read_scene();
        break;

      case CMD_WRITE_SCENE:
        *ga_reg_comstat1 = write_scene(param1, 0, 0, 0);
        break;

      case CMD_WRITE_POSITION:
        *ga_reg_comstat1 = write_scene(param1, 1, *ga_reg_comcmd2, *ga_reg_comcmd3);
        break;

      default:
        break;
    }

    /* Signal completion, then wait until the main CPU acknowledges it.
     * Both ip.s and ipx.c wait for the status to return to zero before
     * taking Word RAM; leaving it set deadlocks the very first module load. */
    *ga_reg_comstat0 = command;
    while (*ga_reg_comcmd0 != 0)
      asm("nop");
    *ga_reg_comstat0 = 0;

  } while (1);
}
