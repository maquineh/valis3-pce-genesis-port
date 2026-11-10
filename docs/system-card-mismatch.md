# Blocker: the provided System Card does not match this disc

## What the boot requires

`cd_boot` loads the disc's boot block (2 x 2048 bytes from sector 0) to
logical `$2800` and verifies **1237 bytes** against the ROM at physical
`$3FAE1`.  That check **passes** with `syscard1.pce`:

```
syscard1.pce[0x3FAE1:0x40006] == track_02.bin[0x0010:0x04E5]   1237/1237 bytes
```

Then it calls the disc's entry point `JSR $2B26`, which performs a **second**
integrity check of its own:

```
$2B26  CLY
$2B27  LDX #$4A                ; 74 bytes
$2B29  LDA #$20 ; STA $FA      ; bl = $20
$2B2D  LDA #$30 ; STA $FB      ; bh = $30   -> pointer $3020
$2B31  LDA #$B6 ; STA $FC
$2B35  LDA #$DF ; STA $FD      ; pointer $DFB6
$2B39  LDA ($FA),Y
$2B3B  CMP ($FC),Y
$2B3D  BEQ $2B40
$2B3F  RTS                     ; mismatch -> abort
```

So the disc expects **74 bytes at logical `$3020` to equal 74 bytes at logical
`$DFB6`**.  With `MPR6 = $1F` (set by `cd_boot`), `$DFB6` resolves to physical
`$3FFB6`.

## Why it fails

| side | bytes |
|---|---|
| disc, boot block `$3020` (file `$0830`) | `36dd36872ba48a23674a7de71e939a98…` |
| ROM, physical `$3FFB6` | `504320456e67696e652043442d524f4d20…` = `"PC Engine CD-ROM SYSTEM\0Copyright HUDSON SOFT / NEC Home Electronics,Ltd.\0"` |

Match: **1 / 74**.  The disc's pattern does not occur anywhere in
`syscard1.pce` (`bytes.find` returns -1), and the reference the game compares
against is the System Card's own volume-descriptor string.

## Conclusion

`syscard1.pce` is **System Card v1.0**, but Valis III's boot block carries an
integrity reference that only matches a **later System Card (v2.0 / v3.0)**.
With v1.0 the boot aborts at `$2B3F` (`RTS`) and `cd_boot` returns an error,
which is exactly what the emulator shows:

```
step     14  2B3F  RTS -> 0001        <- 74-byte check failed
```

The 256-candidate sweep of the `$2007` pointer (`tools/sweep_pointer.py`)
confirms the pointer is irrelevant while this check fails: every candidate
produces the identical result (1525 distinct PCs, then a loop in unloaded
`$FF` memory at `$BFE2-$C037`).

## What is needed

A **System Card v2.0 or v3.0** image (`syscard2.pce` / `syscard3.pce`).  With
the matching card the `$3020`/`$DFB6` comparison passes, the boot continues
into the game, and `tools/emu_game.py` can then capture real VRAM/CRAM for
each of the ten stage segments.

Everything up to this point is verified and committed; no further progress on
stages 2-10 is possible without the matching System Card (or a very long
manual trace of the still-compressed stage tile stream).
