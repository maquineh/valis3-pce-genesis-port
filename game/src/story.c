#include "engine.h"
#include <main/bios.h>
#include <main/io.def.h>
#include <main/vdp.h>

extern u8 next_module;

/* The packer uses a rolling LZ4 dictionary shared by successive updates. */
static u16 history_words[48128 / 2];
static u16 used;
static u16 last_timer;
static u32 elapsed;

static void update_time(void)
{
  u16 now = *ga_reg_stopwatch;
  elapsed += (now - last_timer) & 0xfff;
  last_timer = now;
}

static u16 run_length(u16 nibble, const u8 **src)
{
  u16 length = nibble;
  if (length == 15) {
    u8 n;
    do { n = *(*src)++; length += n; } while (n == 255);
  }
  return length;
}

static const u16 *unpack(const u8 *src, u16 size)
{
  u8 *history = (u8 *)history_words;
  if ((u32)used + size > sizeof(history_words)) {
    /* The regions are disjoint whenever a block (at most 4096 bytes) wraps. */
    const u16 *tail = history_words + (used - 16384) / 2;
    for (u16 i = 0; i < 8192; ++i) history_words[i] = tail[i];
    used = 16384;
  }
  u8 *start = history + used, *out = start;
  used += size;
  while (out < history + used) {
    u8 token = *src++;
    u16 literals = run_length(token >> 4, &src);
    while (literals--) *out++ = *src++;
    if (out == history + used) break;
    u16 distance = src[0] | ((u16)src[1] << 8);
    src += 2;
    u16 matches = 4 + run_length(token & 15, &src);
    const u8 *copy = out - distance;
    while (matches--) *out++ = *copy++;
  }
  return (const u16 *)start;
}

static void upload(const u16 *data, u16 words)
{
  const u16 *end = data + words;
  disable_interrupts();
  while (data < end) {
    u16 address = *data++, count = *data++;
    if (address == 0xffff) {
      vdp_ctrl_32 = CRAM_W;
      for (u16 i = 0; i < count; ++i) vdp_data_16 = data[i];
    } else if (count < 16) {
      vdp_ctrl_32 = to_vdp_addr(address) | VRAM_W;
      for (u16 i = 0; i < count; ++i) vdp_data_16 = data[i];
    } else {
      bios_dma_xfer(to_vdp_addr(address), (const u8 *)data, count);
      asm volatile("" ::: "d0","d1","d2","a0","a1","memory");
    }
    data += count;
  }
  enable_interrupts();
}

void main(void)
{
  static const vdp_reg regs[] = {
    VDP_REG_MODE4, VDP_REG_PL_SIZE | VDP_PL_W32 | VDP_PL_H32,
    VDP_REG_WIN_HPOS, VDP_REG_WIN_VPOS, 0
  };
  const u16 *page = (const u16 *)(WORD_RAM + STORY_OFFSET);
  const u16 track = page[0];
  const u16 *record = page + 3;
  bios_load_vdp_regs_default();
  bios_load_vdp_regs(regs);
  bios_vdp_disp_disable();
  bios_clear_vram();
  bios_sprlist[0].pos_y = 0;
  bios_sprlist[0].next = 0;
  bios_vdp_disp_enable();
  bios_vblank_wait_default();
  engine_audio_command(CMD_PLAY_ONCE, track);
  last_timer = *ga_reg_stopwatch;
  u8 skip = 0;
  for (;;) {
    u16 tick = *record++, blocks = *record++;
    /* The PCE frame lasts about 544 stopwatch ticks (59.83 Hz). */
    u32 deadline = (u32)tick * 544;
    while (elapsed < deadline) {
      bios_vblank_wait_default();
      update_time();
      if (bios_joy1_hit & PAD_START) { skip = 1; break; }
    }
    if (skip || !blocks) break;
    if (blocks == 0xffff) {
      grant_2m();
      engine_audio_command(CMD_STORY_REFILL, 0);
      wait_2m();
      record = page;
      update_time();
      continue;
    }
    while (blocks--) {
      u16 compressed = *record++, size = *record++;
      const u16 *data = unpack((const u8 *)record, size);
      update_time();
      upload(data, size / 2);
      update_time();
      record += (compressed + 1) / 2;
    }
  }
  engine_stop_cdda();
  bios_vdp_disp_disable();
  if (next_module == FILE_STORY_LAST) next_module = FILE_STAGE2_MMD;
  else if (skip || next_module == FILE_STORY_LAST - 1) next_module = FILE_STAGE1_MMD;
  else ++next_module;
}
