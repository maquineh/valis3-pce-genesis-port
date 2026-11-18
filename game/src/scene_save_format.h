/* Portable on-disc representation of a scene checkpoint. */
#ifndef SCENE_SAVE_FORMAT_H
#define SCENE_SAVE_FORMAT_H

#include "shared.h"

typedef struct SceneCheckpoint {
  unsigned char scene;
  unsigned char has_position;
  unsigned short x, y, sequence;
  unsigned char version;
} SceneCheckpoint;

static unsigned short checkpoint_crc(const unsigned char *data, unsigned short length)
{
  unsigned short crc = 0xffff;
  while (length--) {
    unsigned char bit;
    crc ^= (unsigned short)*data++ << 8;
    for (bit = 0; bit < 8; ++bit)
      crc = (unsigned short)((crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1);
  }
  return crc;
}

static unsigned char checkpoint_screens(unsigned char scene)
{
  if (scene == FILE_STAGE1_MMD) return 8;
  if (scene == FILE_STAGE2_MMD || scene == FILE_STAGE2A2_MMD ||
      scene == FILE_STAGE2C_MMD) return 4;
  if (scene == FILE_STAGE2B_MMD || scene == FILE_STAGE3A_MMD ||
      scene == FILE_STAGE1A_MMD || scene == FILE_STAGE4A_ALT_MMD) return 2;
  if (scene == FILE_STAGE2C_GREEN_MMD || scene == FILE_STAGE2C_B_MMD || scene == FILE_STAGE4A_MMD) return 1;
  return 0;
}

static int checkpoint_valid_position(unsigned char scene, unsigned short x, unsigned short y)
{
  unsigned char screens = checkpoint_screens(scene);
  if (scene == FILE_STAGE1_MMD && y <= 223) {
    if ((x >= 2048 && x < 3576) || (x >= 8192 && x < 8448)) return 1;
    if (x >= CITY_MOVIE_MEETING && x < CITY_MOVIE_MEETING + 1551) return 1;
    if (x >= CITY_MOVIE_FALL && x < CITY_MOVIE_FALL + 581) return 1;
  }
  return screens && x <= (unsigned short)(screens * 256 - 16) && y <= (scene == FILE_STAGE1_MMD ? 223 : 176);
}

/* Buffer is one 64-byte, unprotected Sega BRAM block. v1 only saved scene. */
static int checkpoint_decode(const unsigned char *data, SceneCheckpoint *out)
{
  unsigned short crc;
  if (data[0] != 'V' || data[1] != '3' || data[2] != 'S' ||
      !checkpoint_screens(data[4])) return 0;
  out->scene = data[4];
  out->version = data[3];
  if (data[3] == 1) {
    if (data[5] != (unsigned char)(data[4] ^ 0xa5)) return 0;
    out->has_position = 0;
    out->x = out->y = out->sequence = 0;
    return 1;
  }
  if (data[3] != 2 || data[5] > 1) return 0;
  crc = checkpoint_crc(data, 12);
  if (data[12] != (unsigned char)(crc >> 8) || data[13] != (unsigned char)crc) return 0;
  out->has_position = data[5];
  out->x = (unsigned short)((data[6] << 8) | data[7]);
  out->y = (unsigned short)((data[8] << 8) | data[9]);
  out->sequence = (unsigned short)((data[10] << 8) | data[11]);
  if (out->has_position) return checkpoint_valid_position(out->scene, out->x, out->y);
  return out->x == 0 && out->y == 0;
}

static void checkpoint_encode(unsigned char *data, const SceneCheckpoint *record)
{
  unsigned short crc;
  unsigned char i;
  for (i = 0; i < 64; ++i) data[i] = 0;
  data[0] = 'V'; data[1] = '3'; data[2] = 'S'; data[3] = 2;
  data[4] = record->scene; data[5] = record->has_position;
  data[6] = (unsigned char)(record->x >> 8); data[7] = (unsigned char)record->x;
  data[8] = (unsigned char)(record->y >> 8); data[9] = (unsigned char)record->y;
  data[10] = (unsigned char)(record->sequence >> 8); data[11] = (unsigned char)record->sequence;
  crc = checkpoint_crc(data, 12);
  data[12] = (unsigned char)(crc >> 8); data[13] = (unsigned char)crc;
}

/* Sequence comparison remains correct across wrap, as adjacent writes differ by 1. */
static int checkpoint_newer(unsigned short a, unsigned short b)
{
  unsigned short delta = (unsigned short)(a - b);
  return delta != 0 && delta < 0x8000;
}

#endif
