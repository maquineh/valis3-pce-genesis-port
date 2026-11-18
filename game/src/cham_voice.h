#include <sub/pcm.h>

extern const u8 city_cham_voice[], city_cham_voice_end[];

static void prepare_city_voice(void)
{
  static u8 uploaded;
  if (uploaded) return;
  const u8 *p = city_cham_voice;
  u16 bank = 0;
  while (p < city_cham_voice_end) {
    *PCM_CTRL = WAVEBANK(bank++);
    volatile u8 *dest = (volatile u8 *)(_PCM_RAM + 1);
    for (u16 i=0; i<4096 && p<city_cham_voice_end; ++i) {
      *dest = *p++;
      dest += 2;
    }
  }
  uploaded=1;
}

static void play_city_voice(void)
{
  /* 32,552 Hz PCM clock, 11 fractional pitch bits, 11,025 Hz recording. */
  const u16 pitch=694;
  const u16 silence=(u16)(city_cham_voice_end-city_cham_voice-2);
  *PCM_CDISABLE=0xff;
  *PCM_CTRL=CHANNEL(1);
  *PCM_ENV=0xff;
  *PCM_PAN=0xff;
  *PCM_FDL=(u8)pitch;
  *PCM_FDH=pitch>>8;
  *PCM_LSL=(u8)silence;
  *PCM_LSH=silence>>8;
  *PCM_ST=0;
  *PCM_CDISABLE=0xfe;
}
