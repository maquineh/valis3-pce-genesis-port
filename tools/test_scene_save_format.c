/* Host checks for the exact checkpoint format used on the Mega CD. */
#include "../game/src/scene_save_format.h"

int main(void)
{
  unsigned char data[64], legacy[64] = { 'V', '3', 'S', 1, FILE_STAGE2_MMD,
                                        FILE_STAGE2_MMD ^ 0xa5 };
  static const unsigned char crc_sample[] = "123456789";
  SceneCheckpoint input = { FILE_STAGE2B_MMD, 1, 280, 128, 42, 2 };
  SceneCheckpoint decoded;
  unsigned char i;
  if (checkpoint_crc(crc_sample, 9) != 0x29b1) return 1;
  checkpoint_encode(data, &input);
  if (!checkpoint_decode(data, &decoded) || decoded.scene != input.scene ||
      decoded.x != input.x || decoded.y != input.y ||
      decoded.sequence != input.sequence || !decoded.has_position) return 2;
  /* Any single-bit corruption of the protected payload must be rejected. */
  for (i = 0; i < 14; ++i) {
    data[i] ^= 1;
    if (checkpoint_decode(data, &decoded)) return 3;
    data[i] ^= 1;
  }
  if (!checkpoint_decode(legacy, &decoded) || decoded.version != 1 ||
      decoded.has_position || decoded.scene != FILE_STAGE2_MMD) return 4;
  legacy[5] ^= 1;
  if (checkpoint_decode(legacy, &decoded)) return 5;
  input.x = 497; /* two screens: rightmost valid top-left is 496 */
  checkpoint_encode(data, &input);
  if (checkpoint_decode(data, &decoded)) return 6;
  input.x = 496; input.y = 177;
  checkpoint_encode(data, &input);
  if (checkpoint_decode(data, &decoded)) return 7;
  input.has_position = 0; input.x = input.y = 0;
  checkpoint_encode(data, &input);
  if (!checkpoint_decode(data, &decoded) || decoded.has_position) return 8;
  if (!checkpoint_newer(0, 65535) || checkpoint_newer(65535, 0) ||
      checkpoint_newer(2, 2)) return 9;
  return 0;
}
