/* Valis III Mega CD - shared definitions */

#ifndef VALIS3_SHARED_H
#define VALIS3_SHARED_H

#define FILE_IPX_MMD 0
#define FILE_GAME_MMD 1
#define FILE_STAGE1_MMD 2
#define FILE_STAGE2_MMD 3
#define FILE_STAGE2B_MMD 4
#define FILE_STAGE3A_MMD 5
#define FILE_STAGE2C_MMD 6
#define FILE_STAGE2A2_MMD 7
#define FILE_STAGE2C_GREEN_MMD 8
#define FILE_STAGE2C_B_MMD 9
#define FILE_STAGE4A_MMD 10
#define FILE_STAGE1A_MMD 11
#define FILE_STAGE4A_ALT_MMD 12
#define FILE_STAGE2_BOSS_MMD 20

/* Story modules follow the existing save IDs. Only gameplay scenes go in BRAM. */
#define FILE_STORY_FIRST 13
#define FILE_STORY_LAST 19
#define STORY_OFFSET 0x2000

/* Stage 1 cinematic ticks stored in the existing v2 position fields. */
#define CITY_MOVIE_MEETING 12288
#define CITY_MOVIE_FALL 14336

/* Sub CPU commands */
#define CMD_LOAD_FILE 1
#define CMD_PLAY_CDDA 2
#define CMD_STOP_CDDA 3
#define CMD_READ_SCENE 4
#define CMD_WRITE_SCENE 5
#define CMD_WRITE_POSITION 6
#define CMD_REPEAT_CDDA 7
#define CMD_CHAM_VOICE 8
#define CMD_PLAY_ONCE 9
#define CMD_STORY_REFILL 10
#define CMD_PLAY_SFX 11

#define CITY_SFX_SWORD 0
#define CITY_SFX_JUMP 1
#define CITY_SFX_HIT 2
#define CITY_SFX_MAGIC 3
#define CITY_SFX_ITEM CITY_SFX_MAGIC

/* Main CPU's otherwise unused command words carry transient module state. */
#define SCENE_RESUME_MARKER 0x5633
#define SCENE_SAVE_ERROR_MARKER 0x5345

#endif
