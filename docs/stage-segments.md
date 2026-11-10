# The ten stage segments (decoded from the disc)

**The disc enumerates the stages explicitly.**  Every 40-sector block of data
track 2 starts with a 16-byte CD frame header, a short parameter area and an
ASCII stage label, followed by a VCE palette block and the stage's tile/map
data.  The first parameter byte after the label is a sequence number `00..09`:

| seq | label | sector | file offset | palette | palette words |
|---|---|---|---|---|---|
| 00 | `STG1A` | 304 | `$0AE900` | `$0AEB50` | 610 |
| 01 | `STG2A` | 344 | `$0C5880` | `$0C5A4C` | 676 |
| 02 | `STG2B` | 384 | `$0DC800` | `$0DC9F2` | 657 |
| 03 | `STG2C` | 424 | `$0F3780` | `$0F3972` | 673 |
| 04 | `STG3A` | 464 | `$10A700` | `$10A8CC` | 676 |
| 05 | `STG3B` | 504 | `$121680` | `$12184C` | 676 |
| 06 | `STG4A` | 544 | `$138600` | `$1387CC` | 676 |
| 07 | `STG4B` | 584 | `$14F580` | `$14F6EA` | 725 |
| 08 | `STG4C` | 624 | `$166500` | `$1666CC` | 692 |
| 09 | `STG5A` | 664 | `$17D480` | `$17D654` | 688 |

So the PCE version's ten stages are stored as ten segments grouped into five
`STG` worlds (`STG1A`, `STG2A/B/C`, `STG3A/B`, `STG4A/B/C`, `STG5A`), which is
what the port has to reproduce.

## Header format (verified bytes)

```
$0C5880: 00 FF FF FF FF FF FF FF FF FF FF 00 00   <- 12-byte sync + 4 bytes
$0C5890: 54 34 01                              <- frame address continuation
$0C5893: 53 54 47 32 41                         <- "STG2A"
$0C5898: 00 x10                                 <- reserved
$0C58A2: 01 03 00 04 00 00 b0 10 06 1c be 00 00 20 00   <- parameters
```

`tools/analyze_stages.py` prints the header parameters for every segment.

## Overlay relocation model (verified)

The System Card's `cd_exec` sites decode to:

| site | sector | dest | sectors | file range |
|---|---|---|---|---|
| `$4CA0` | 32 | `$4000` | 8 | `$012600-$016F80` |
| `$4CC8` | 976 | `$4000` | 12 | `$230700-$237540` |
| `$22CBF5` | 956 | `$4000` | 4 | `$224F40-$227400` |
| `$232D60` | 968 | `$4000` | 8 | `$22BD80-$230700` |
| `$232D7F` | 1172 | `$4000` | 8 | `$2A0FC0-$2A5940` |

The resident overlay (sector 32, logical `$4000` <- file `$12600`) holds the
engine's core routines, which is proven by three independent call sites that
only resolve to coherent code through this mapping:

| logical | file | routine | evidence |
|---|---|---|---|
| `$8660` | `$16C60` | decompressor | `BSR $6C39; STA ($FA); INC $FA` 32x256 loop |
| `$6C39` | `$15239` | entity update | indexed table reads `$2A16,X`, `$2D46,X` |
| `$8CD9` | `$2353D9` | **palette upload** | `TIA $5093, $0404, $2000` / `TIA $9092, $0404, $2000` |

`$8CD9` is the routine the stage loader calls right before it clears VRAM, and
it is the palette uploader: it writes the VCE colour index at `$0402/$0403`
and streams whole palettes into the colour data port `$0404`.  `tools/logical_to_file.py`
resolves any logical address with the verified formula.

## What is still missing for stages 2-10

The stage segments' **tile data is compressed** - the routine at logical `$8660`
is an 8 KiB decompressor driven by `BSR $6C39`.  Rendering the raw block bytes
as tiles produces dithered noise (`build/gfx/stg2a/contact.png`,
`build/gfx/stages2/contact.png`), while the stage *maps* inside the blocks are
plain `0x600`-sized BATs.  So the remaining work is:

1. implement the decompressor at logical `$8660`/`$6C39` in Python,
2. decompress each stage segment's tile block,
3. render/verify each segment's map with its own palette,
4. pack with `tools/pack_stage_all.py` and add `game/src/stageN.c` modules.
