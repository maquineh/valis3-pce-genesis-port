/* The two scripted scenes share the normal room planes. Each run-length record
 * holds the original actors, dialogue window and column scroll for that tick. */
extern const u16 city_cinema_meeting[], city_cinema_fall[];
static const u16 *movie, *movie_poses, *movie_actors, *movie_pages;
static const s16 *movie_record;
static u16 movie_left, movie_remaining, movie_page, movie_time;

static void load_movie(u16 start_tick)
{
  movie = room==MEETING ? city_cinema_meeting : city_cinema_fall;
  const u8 *data=(const u8 *)movie;
  bios_dma_xfer_word_ram(to_vdp_addr(vram_addr_from_tileidx(movie[0])),data+movie[5],movie[1]*16);
  movie_pages=(const u16 *)(data+movie[6]);
  movie_poses=(const u16 *)(data+movie[7]);
  movie_actors=(const u16 *)(data+movie[8]);
  movie_record=(const s16 *)(data+movie[9]);
  movie_remaining=movie[2];
  movie_time=start_tick<movie[3] ? start_tick : 0;
  u16 skip=movie_time;
  while (skip>=(u16)movie_record[0] && movie_remaining>1) {
    skip-=movie_record[0]; movie_record+=7; --movie_remaining;
  }
  movie_left=movie_record[0]-skip;
  movie_page=0;
}

static u8 advance_movie(void)
{
  ++movie_time;
  if (--movie_left) return 0;
  if (!--movie_remaining) return 1;
  movie_record+=7;
  movie_left=movie_record[0];
  return 0;
}

static void draw_movie(void)
{
  u16 page=movie_record[2];
  if (page!=movie_page) {
    if (page)
      bios_dma_xfer_word_ram(to_vdp_addr(BIOS_VDP_DEFAULT_WINDOW+256),
                            (const u8 *)(movie_pages+320*(page-1)),320);
    vdp_ctrl_16=VDP_REG_WIN_VPOS|(page ? 14 : 4);
    movie_page=page;
  }
  const s16 *actors=(const s16 *)(movie_actors+movie_record[1]);
  u16 count=*actors++;
  for (u16 i=0;i<count;++i,actors+=3)
    draw_pose_table(movie_poses,actors[0],actors[1],actors[2],0);
  if (movie_record[6]>0) feet=movie_record[6];
}
