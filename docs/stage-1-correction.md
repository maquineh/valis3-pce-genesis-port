# Correction: the stage-1 tile base was wrong

## The evidence

The title screen proves the convention.  `tools/list_vram_reads.py` shows:

```
$0049CD  cd_read  sector $0C  VRAM word $1000 (= tile 256)  size $A000
```

and `tools/render_bat.py` with `--tiles 0x6E40 --base 0x100` reproduces the
title screen exactly (START / CONTINUE legible).  So **a block read to VRAM
word `$W` starts at tile index `W/16`**, i.e. base = VRAM word / 16.

Applying the same rule to the stage tile block:

```
$237605  cd_read  sector $2C  VRAM word $1000 (= tile 256)  size $C000
```

gives tiles at file `$19440` with **base `$100`** (1536 tiles, `$100-$700`).

The stage-1 packer (`tools/pack_stage.py` / `tools/pack_stage_all.py`) used
**base `$200`**, which shifts every tile by 256 tiles (8 KiB).  The renders in
`build/gfx/v_base_100_mask_7FF.png` (correct base, 737/768 cells resolved) and
`build/gfx/v_base_200_mask_7FF.png` (old base) are both dithered noise, which
means the map at `$17FF90` does **not** describe a screen drawn from the
sector-`$2C` block alone.

## What that implies

A stage screen is not drawn from a single tile block.  The loader's multi-read
routine at logical `$847C` (file `$23E80C`, traced in `docs/stage-loader.md`)
loads, in order:

1. `ad_trans` sector 0 (29 sectors),
2. `cd_read` sector 32, **24 sectors**, dest `$1000`,
3. `cd_read` sector 56, 8 sectors, `dh=$05`.

Read 2 alone covers 56448 bytes = 1764 tiles, and the block at sector 32
(file `$12600`) is also where the **resident overlay** is loaded from
(`cd_exec` at `$4CA0`: sector 32 → logical `$4000`).  So the stage tileset
overlaps the resident code region, and the map tile indices are VRAM tile
indices that only make sense with the *complete* VRAM state the loader builds.

Rendering the map at `$17FF90` against that 24-sector block
(`build/gfx/sec32_75264_2047.png`) is still noise, so the correct per-screen
VRAM state is not yet known.

## Consequence for the port

`game/res/gfx/stage1_all_*` was packed with the wrong base and is therefore
**not verified content**.  It should be treated as a placeholder until the
stage loader's tile/BAT upload sequence is traced in full (or the game is run
in an emulator with the System Card BIOS).

`tools/test_stage_logic.py` still passes because it only checks the *layout*
of the packed files (sizes, index ranges, streaming order), not their visual
correctness.
