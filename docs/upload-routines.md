# Stage chunk graphics path

The addresses below come from the four-sector read at sector 1000, loaded at
logical `$8000`. Track files retain 2352-byte raw sectors; map logical
addresses with `tools/logical_to_file.py --range 1000 4 0x8000` so the 16-byte
header in each sector is skipped.

## `$847C` — select and read the stage data

At file `$23E80C`, this routine selects CD base track 24 through `$895D`, then:

| BIOS call | relative sector | count | destination |
|---|---:|---:|---|
| `ad_trans` `$E033` | 0 | 29 sectors | ADPCM transfer buffer |
| `cd_read` `$E009` | 32 | 24 sectors | local RAM `$1000` |
| `cd_read` `$E009` | 56 | 8 sectors | MPR5 bank `$FFF5+5` |

The later stream decoder calls `ad_read` `$E036`; its source address is kept in
the `$3E02/$3E03` byte offset, while the selected CD base and low sector byte
come from the loader's current CD state.

## `$8790` — initialize two RAM buffers

At file `$23EB20`, the routine contains these HuC6280 block transfers:

```text
$8790  STZ $A000
       TII $A000, $A001, $1FFF
       STZ $3A00
       TII $3A00, $3A01, $03FF
       ... set VCE color-command registers ...
       JSR $E0E4
       RTS
```

This is not a 64 KiB scrolling-buffer shift. The copies are `$1FFF` and
`$03FF` bytes, followed by VCE command setup.

## `$9366` — LZ-style tile decoder

The routine is in the same loaded chunk at file `$23F956` (sector 1002 payload
offset `$366`). The caller at `$87E9` is file `$23EB79`:

```text
$87E9  JSR $9366
       JSR $E07B
       LDX $3E07
       CLA
       JSR $E0AE                ; set VDC MAWR from $3E07
       TIA $A000, $0002, $2000  ; upload 8 KiB from RAM to VRAM
```

The decoder reads an 8-byte stream header. Header bytes 0-1 advance the next
stream offset by that value plus eight; bytes 4-5 set the decoded byte count.
It reads literal/back-reference tokens, stores history at `$D000-$DFFF`, and
keeps the current 8 KiB output window at `$A000-$BFFF`. The first stage call
sets `$3E07` to `$10`, so the upload begins at VDC word address `$1000` (tile
index `$100`).

This path accounts for tile graphics. No BAT write is present in `$9366` or
its `$87E9` upload call, and the decoder input has not yet been matched to the
`+0x800` area of an `STG` block. The stage BAT/object generation remains open.
