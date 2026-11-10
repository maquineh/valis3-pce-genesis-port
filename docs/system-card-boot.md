# System Card boot chain (verified against the real BIOS)

With `syscard1.pce` (256 KiB) in the repository root the whole boot path is
now decoded from the real System Card code instead of guessed.

## Memory image

`syscard1.pce` maps **1:1 to physical `$00000-$3FFFF`**:

| physical | contents | accessible as |
|---|---|---|
| `$00000-$01FFF` | System Card ROM (8 KiB) | logical `$E000-$FFFF`, MPR7 = `$00` |
| `$3E000-$3FFFF` | System Card data bank | logical `$C000-$DFFF`, MPR6 = `$1F` |

`syscard1.pce[0x0000]` = `4C E7 E0` = `JMP $E0E7` = `cd_boot`, and the whole
jump table matches the documented BIOS entry points:

| logical | target | logical | target |
|---|---|---|---|
| `$E000` cd_boot | `$E0E7` | `$E01E` cd_subq | `$F047` |
| `$E003` cd_reset | `$E95C` | `$E021` cd_dinfo | `$F081` |
| `$E006` cd_base | `$EC1C` | `$E024` cd_contnts | `$F13A` |
| `$E009` cd_read | `$DEF6` | `$E027` cd_subrd | `$F3B5` |
| `$E00C` cd_seek | `$EE49` | `$E02A` cd_pcmrd | `$F3C5` |
| `$E00F` cd_exec | `$EC57` | `$E02D` cd_fade | `$F3DA` |
| `$E012` cd_play | `$EE96` | `$E030` ad_reset | `$F3E0` |
| `$E015` cd_search | `$EFB1` | `$E033` ad_trans | `$F3F4` |
| `$E018` cd_pause | `$F01B` | `$E036` ad_read | `$F467` |
| `$E01B` cd_stat | `$F3A7` | `$E039` ad_write | `$F566` |
| | | `$E03C` ad_play | `$F662` |

Because image offset = physical address, `logical X` in `$E000-$FFFF` is at
image offset `X - 0xE000`.

## `cd_boot` (`$E0E7`)

```
SEI ; CSH ; CLD
LDX #$FF ; TXS
TXA ; TAM #$01          ; MPR0 = $FF  (I/O page)
LDA #$F8 ; TAM #$02     ; MPR1 = $F8  (work RAM)
JSR $E143
LDA #$01 ; TAM #$40     ; MPR6 = $01
JSR $DEA9
JSR $DB80               ; disc type -> A
...
(type 3, normal CD)     JSR $F13A ; BSR $0148 ; BCC $E13E
$E13E                   BSR $E143   -> LDA #$04 ; JMP $E295
$E140                   JMP $4000
```

`$E295` sets the bank table from `A`:

```
TAM #$04      ; MPR2 = A
INC A ; TAM #$08   ; MPR3 = A+1
INC A ; TAM #$10   ; MPR4 = A+2
INC A ; TAM #$20   ; MPR5 = A+3
INC A ; TAM #$40   ; MPR6 = A+4
```

With `A = $04` the banks are `$04,$05,$06,$07,$08`, i.e.

| logical | physical |
|---|---|
| `$4000-$5FFF` | `$08000` |
| `$6000-$7FFF` | `$0A000` |
| `$8000-$9FFF` | `$0C000` |
| `$A000-$BFFF` | `$0E000` |
| `$C000-$DFFF` | `$10000` |

## The boot block and its signature check

`$E186` issues the boot read:

```
STZ $FC ; STZ $FD ; STZ $FE      ; sector 0
LDA #$00 ; STA $FA ; LDA #$28 ; STA $FB   ; bx = $2800
LDA #$01 ; STA $FF               ; dh = 1  (local RAM)
INC A    ; STA $F8               ; al = 2 sectors
STZ $F9
JSR $EC6D                        ; cd_read
LDA #$1F ; TAM #$40              ; MPR6 = $1F
```

So the boot block is **2 sectors x 2048 bytes = 4096 bytes at logical `$2800`**,
which is work RAM offset `$800` (MPR1 = `$F8` -> physical `$1F0000`).

`$E1BC` then verifies it:

```
pointer $EC = $2800        (the loaded boot block)
pointer $EE = $DAE1        (physical $3FAE1, MPR6 = $1F)
compare $04D5 bytes, then $4A zero bytes
if equal -> JSR $2B26      (the disc's entry point)
else     -> SEC ; RTS      (boot fails)
```

**Verified:** `syscard1.pce[0x3FAE1:0x40006]` matches
`track_02.bin[0x0010:0x04E5]` **1237/1237 bytes (100 %)** (`tools/check_signature.py`).
That pins the mapping **logical `$2800` <- disc file `$0010`** exactly.

## The disc's own entry (`$2B26`)

`JSR $2B26` -> image `$2B26 - $E000` is *not* in the ROM; `$2B26` is inside
the boot block, so the file offset is `0x10 + ($2B26 - $2800) = 0x336`.

At file `$0336` the disc code does a *second* 74-byte check
(`$3020` vs `$DFB6` = image `$3FFB6`) and then either falls through or runs
the main boot at `$2BFC` (file `$040C`):

```
$2BFC  BBR1 $00, $2C43
$2BFF  TII $3014, $FC20, $0300      ; relocate $300 bytes
$2C06  LDA $3017 ; BEQ $2C43
$2C0F  STA $F8 ; STZ $FF ; STZ $FA ; STZ $FB
$2C17  JSR $E033                     ; ad_trans
...
$2C43  ...                           ; the MPR setup at file $045C
$2CD1  JMP ($2007)                   ; indirect jump through work RAM
```

`$2BFC` onwards is the same code that was previously disassembled at file
offsets `$040C-$04E4`; the correct logical base is `+ $27F0`
(`logical = file + 0x27F0`).

## `cd_read` destination semantics (from `$EC6D`)

The real implementation dispatches on `dh` (work area `$FF`):

```
CMP #$02 ; BCC dh<2      ; dh = 0 or 1
CMP #$FF ; BEQ $ECE5     ; dh = $FF
CMP #$FE ; BEQ $ED30     ; dh = $FE
JMP $ED85                ; dh = 2..6 (MPR banks)
```

For `dh = 1` and `dh = $FF` the count is converted with

```
LDA $F8 ; ASL A ; ASL A ; ASL A ; STA $F9 ; STZ $F8
```

i.e. **`al` sectors = `al * 2048` bytes**, so `al` is a count of *2048-byte
sectors*, not 2352-byte frames.  `dh = $FF` then uploads through
`TIA $FA20, $0200, $0200` with the VDC register selected on `$0000`.

## Running it

`tools/emu_game.py` installs exactly this state (System Card image at
physical `$00000`, boot block at logical `$2800`, MPR
`FF F8 04 05 06 07 1F 00`) and starts at `$2B26`.  The emulator reproduces
the signature check loop (74 iterations at `$2B39`) and reaches the MPR
setup, but the final `JMP ($2007)` needs the pointer that the System Card's
IPL leaves in work RAM; that value is written by the BIOS path that runs
before `cd_boot` in a real console (not by `cd_boot` itself, which is why
`tools/emu_game.py` currently stops there).
