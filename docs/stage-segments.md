# The ten stage segments (decoded from the disc)

**The disc enumerates the stages explicitly.** Every 40-sector block of data
track 2 starts with a 16-byte CD frame header, a short parameter area and an
ASCII stage label, followed by a VCE palette region and stage data. The first
parameter byte after the label is a sequence number `00..09`:

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

## CD reads and logical address mapping

The System Card's `cd_exec` sites decode to:

| site | sector | dest | sectors | file range |
|---|---|---|---|---|
| `$4CA0` | 32 | `$4000` | 8 | `$012600-$016F80` |
| `$4CC8` | 976 | `$4000` | 12 | `$230700-$237540` |
| `$22CBF5` | 956 | `$4000` | 4 | `$224F40-$227400` |
| `$232D60` | 968 | `$4000` | 8 | `$22BD80-$230700` |
| `$232D7F` | 1172 | `$4000` | 8 | `$2A0FC0-$2A5940` |

Raw data-track files retain 2352-byte sectors. A CD read exposes only the
2048-byte user payload, so logical addresses cannot be mapped by adding the
address delta to the first sector's file offset. For a read starting at sector
`S`, logical base `B`, and address `A`, the raw file offset is:

```
delta = A - B
file  = (S + delta // 2048) * 2352 + 16 + delta % 2048
```

Use `tools/logical_to_file.py --range SECTOR COUNT LOGICAL_BASE` to strip those
sector headers before disassembling. The old `$8660`/`$6C39`/`$8CD9` file
offsets in this document came from extrapolating one read linearly across raw
sectors; those routine labels are not supported by that mapping.

## Stage-chunk graphics decoder

The chunk loaded from sector 1000 has four sectors of user data at logical
`$8000-$9FFF`. Its routine at logical `$9366` (raw file `$23F956`, sector 1002
payload offset `$366`) is called by `$87E9` before the stage code uploads an
8 KiB window from `$A000` to VRAM. The routine:

* reads an 8-byte header from its CD stream;
* uses header bytes 0-1 to advance the next stream offset by that value plus 8;
* uses bytes 4-5 as the decoded byte count;
* expands literal and back-reference tokens through a 4 KiB history buffer at
  `$D000-$DFFF`, keeping the current 8 KiB output window at `$A000-$BFFF`;
* returns to `$87E9`, which uploads `$2000` bytes from `$A000` to VRAM at the
  word address held in `$3E07`.

This identifies a tile-data decoder. It does not write the BAT, and its input
has not yet been tied to the `+0x800` region of an `STG` block.

## What is still missing for stages 2-10

The BAT for stages 2-10 is still not located. The decoder above is called
before an 8 KiB tile upload; it is not evidence that raw BATs live inside the
`STG` blocks. The `+0x800` region and object records remain candidates for
further tracing, not decoded map data. The reliable porting path remains
captured gameplay BAT/VRAM/CRAM until the BAT-generation routine is found.
