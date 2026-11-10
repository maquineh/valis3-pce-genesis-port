## Traced upload routines (this pass)

All offsets below are file offsets in `build/extracted/data/track_02.bin`,
with the chunk base **logical `$8000` <- file `$23E390`** (the 4-sector chunk
read by `cd_read` at `$2252C4`, sector 1000, `dh=$01`).

### `$847C` (file `$23E80C`) - the multi-read setup

Traced in `docs/stage-loader.md`.  Performs, in order:

| step | BIOS call | sector | count | dest |
|---|---|---|---|---|
| 1 | `ad_trans` `$E033` | 0 | 29 | `$0000`, `dh=$00` |
| 2 | `cd_read` `$E009` | 32 | 24 sectors | `$1000`, `dh=$FF` |
| 3 | `cd_read` `$E009` | 56 | 8 sectors | `Mpr5 + $FFF5+5`, `dh=$05` |

`dh=$FF` takes `al` as a **sector count** and `bx` as the address, while
`dh=$FE` (the tile blocks in `tools/list_vram_reads.py`) takes `ah:al` as a
**byte count** into VRAM.

### `$8790` (file `$23EB20`) - buffer shift + palette command

Coherent routine, ends in `RTS`:

```
$23EB20  STZ $A000
$23EB23  TII $00A0, $01A0, $FF1F     ; 65279-byte copy, +$100 shift
$23EB2A  STZ $3A00
$23EB2D  TII $003A, $013A, $FF03     ; 65279-byte copy, +$100 shift
$23EB34  LDA #$00 ; STA $2220
         LDA #$3A ; STA $2221
         LDA #$10 ; STA $2222
         LDA #$00 ; STA $2223
         LDA #$3C ; STA $2224
         LDA #$08 ; STA $2225
         LDA #$02 ; STA $221F
$23EB57  JSR $E0E4                   ; ex_colorcmd
$23EB5A  RTS
```

**Finding:** the playfield is kept as a **~64 KiB RAM buffer** that is shifted
by `$100` bytes (8 tiles) - i.e. the game scrolls a RAM copy of the stage and
uploads the visible part to VRAM.  That is why no plain 32x24 BAT exists on
the disc for stages 2-10: the BAT is *generated* from this buffer.

### `$9366` region (file `$23EB79`) - tile upload

```
$23EB79  JSR $9366
$23EB7C  JSR $E07B                   ; ex_vsync
$23EB7F  LDX $3E07
$23EB82  CLA
$23EB83  JSR $E0AE                   ; ex_setwrt -> MAWR = $3E07
$23EB86  TIA $00A0, $0200, $0020     ; 32-byte transfer
$23EB8D  LDA $3E07                   ; <-- data table starts here
```

So the tile upload writes 32 bytes (one tile) per call to the VDC, with the
address taken from the variable at `$3E07`, and the source data is the table
that begins at file `$23EB90`.  **That table is the compressed tile stream**
that has to be decoded.

### `$8839`, `$88E2`, `$959B`

These do **not** resolve inside the sector-1000 chunk (file `$23EBC9` onwards
is not code), so they belong to a different overlay.  They are the remaining
references to trace.
