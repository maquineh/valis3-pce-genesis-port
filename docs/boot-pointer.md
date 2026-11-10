## Correction: the `$2007` pointer is built by the boot block itself

The previous note said the pointer at work RAM `$2007` comes from the System
Card's IPL.  That is wrong - the boot block **computes it**:

```
file $049C (logical $2C8C):
        CLC
        LDA $07
        ADC #$00
        STA $07          ; low  byte
        LDA $08
        ADC #$30
        STA $08          ; high byte += $30, i.e. pointer += $3000
        BRA $04DE        ; -> LDX #$FF / TXS / JMP ($2007)
```

`tools/trace_2007.py` finds exactly two work-RAM stores in the whole boot
block:

| file | logical | instruction |
|---|---|---|
| `$035B` | `$2B4B` | `STA $00` |
| `$04A1` | `$2C91` | `STA $07` |

**The key to reading this correctly is MPR0.**  The boot block is written to
run with **MPR0 = `$F8`**, which aliases work RAM at logical `$0000-$1FFF`:

| logical | physical | |
|---|---|---|
| `$0007` | `$1F0007` | = work RAM `$2007` (the low byte of the jump pointer) |
| `$0008` | `$1F0008` | = work RAM `$2008` (the high byte) |
| `$0004` | `$1F0004` | = work RAM `$2004` (the "second boot" flag) |

So `STA $07` / `STA $08` really writes `$2007`/`$2008`, and the boot block
raises the pointer by `$3000` before the final `JMP ($2007)`.

With `MPR0 = $F8` the emulator (`tools/emu_game.py`) now runs the boot block
far past the entry: **200 000 steps, 1525 distinct program counters**, versus
11 PCs before.  It still ends by jumping into an unloaded region
(`$BFE2-$C037`, all `$FF`), because the pointer's initial value plus `$3000`
lands outside the boot block - the initial value is what the System Card's
CD-boot leaves in work RAM, and that was not yet identified.

## `cd_boot`'s own read and the signature check (verified)

Unchanged and confirmed: `cd_boot` reads 2 x 2048 bytes from disc sector 0 to
logical `$2800` (`dh=1`, `al=2`), then compares 1237 bytes against the ROM
reference at physical `$3FAE1`.  `syscard1.pce[0x3FAE1:]` matches
`track_02.bin[0x0010:]` **1237/1237 bytes**, which pins the boot block exactly.
