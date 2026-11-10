# CD drive protocol: what the real System Card v3.0 needs

## Bank mapping matters when reading the BIOS

`cd_boot` leaves `MPR6 = $01`, so logical `$C000-$DFFF` resolves to
**image offset `0x2000 + (logical & 0x1FFF)`**, not `logical - $E000`.
That is why `JSR $C860` (disc detection) lives at image `0x2860`.

## Disc detection (`$C860` → image `0x2860`)

```
$C860  LDA #$7B ; STA $F8
       LDA #$C9 ; STA $F9
       JSR $C950              ; send a command block from $C97B
       JSR $FE92              ; poll / check result
       BCS $C88C
       ...
$C874  LDA #$AA ; STA $18C0   ; <-- unlock sequence
       LDA #$55 ; STA $18C0
       LDA #$0C ; STA $F8
       LDA #$CA ; STA $F9
       JSR $C950
       ...
$C88C  LDA #$56 ; STA $F8
       LDA #$CA ; STA $F9
       JSR $C950
...
$C897  LDA $2241 ; AND #$3F ; CMP #$20
       BCS $C8AD               ; disc present?
```

So the drive is driven through:

| register | use |
|---|---|
| `$1800` | status / command |
| `$1801` | parameter byte / data byte |
| `$1802`, `$1803` | flags |
| `$180C`-`$180F` | control |
| **`$18C0`** | **unlock / mode register** (written `$AA` then `$55`) |
| `$18C1`-`$18C7` | result / status bytes |
| `$1403` | IRQ related |

and command blocks are sent with a helper at `$C950` from pointer tables at
`$C97B`, `$CA0C`, `$CA56`, `$CA84`, `$CA9C`, `$CAC0` ...

## What this means for the emulator

`tools/pce_system.py` already has a first `$1800`/`$1801` state machine and
answers `idle/param/data/done`.  What is still missing:

1. `$18C0` unlock handling (`$AA` then `$55`), returning a plausible
   "CD-ROM² unit present" acknowledgement;
2. the `$18C1`-`$18C7` result bytes the detection reads;
3. the command blocks at `$C97B`/`$CA0C`/`$CA56`/`$CA84` (each is a small
   parameter list, e.g. "get disc info", "read TOC", "set mode");
4. `$1403` acknowledgement.

Once the detection returns "CD-ROM² game disc, track 2 present", `cd_boot`
takes the `$E145` path (`LDA #$04; BSR $E156`) which installs
`MPR2-6 = $04..$08` and does `JMP $4000` - the game's boot block entry.

## Honest assessment

This is a bounded but non-trivial subsystem: four command handlers plus the
unlock/result registers, each of which has to be derived from the BIOS code
and validated step by step in the emulator.  It is the last obstacle between
the current state and real per-stage VRAM dumps; without it there is no way to
obtain the stage maps, because the game *generates* them in RAM
(`docs/upload-routines.md`) rather than storing ready-made BATs on the disc.


## Correction (important)

The flat image offset == physical address map **is** correct.  The earlier
conclusion that it failed came from confusing two files: the **US**
TurboGrafx CD Super System Card (USA) (v3.0).pce has NOP padding at
$E0F3, while **syscard3.pce (JPN)** has real code there:

`
syscard3.pce[0x0F3] =   (SEI)      <- cd_boot entry
syscard3.pce[0x106] =   (JSR )
syscard3.pce[0x14B] =   (RTS)
`

## The real v3.0 boot ($E0F3, verified by disassembly)

`
  SEI ; CSH ; CLD
  LDX # ; TXS
  TXA ; TAM #              MPR0 =  (I/O page)
  LDA # ; TAM #         MPR1 =  (work RAM)
  BSR 
  LDA # ; TAM #         MPR6 = 
  JSR                    drive/VDC init
  JSR                    disc check -> A
  TAX ; BEQ              A = 0 -> good disc
  BSR  ; LDA # ; TAM # ; JMP    (error)
  JSR 
  BSR 
  BCC 
  LDA # ; BSR         <- MPR bank table
  JMP                    <- GAME ENTRY
  LDA # ; BSR  ; JMP 
  LDA 
  TAM #                    MPR2 = A
  INC A ; TAM #            MPR3 = A+1
  INC A ; TAM #            MPR4 = A+2
...                                MPR5 = A+3, MPR6 = A+4
`

With syscard3.pce[0x1FF5] =  the bank table becomes **MPR2-6 =
$84..**, i.e. logical $4000 maps to physical **$108000**.  So in
v3.0 the game's boot block is loaded into Super CD RAM at $108000 and
entered at logical $4000.

## Still missing

JSR  (the disc check) loops waiting on the CD unit.  The emulator
currently ends the run in a $0000 loop after a few steps, so the drive
handshake ($1800 status/command, $1801 parameters/data, $18C0 unlock,
$18C1- results) still has to be completed before A = 0 is returned
and the boot reaches JMP .


## Progress: the disc boot code runs and issues a real cd_read

Bypassing the drive handshake and installing what the BIOS installs on a
successful check - boot block payload at physical \ (logical \,
MPR2-6 = \..\) - the disc's own boot code executes:

`
entry \ (file \):
  JSR \                 ex_dspoff
  LDA \ ; STA \     al = boot parameter
  LDA \ ; STA \     bl
  LDA \ ; STA \     bh
  JSR \                cd_read       <- REAL disc read (sector 0)
  LDA \ ; CLC ; ADC \ ; TAM #\   MPR2 =   ...
  JMP (\)
`

Evidence: disc reads: [0], and MPR becomes FF F8 80 05 06 07 08 00
(MPR2 = \, i.e. logical \ -> physical \, Super CD RAM).

So the boot code and its BIOS calls work; what fails afterwards is the
**entry pointer at work RAM \**, which ends in empty memory (\,
146k iterations of a no-op loop) because the parameters at logical
\-\ are only populated when the boot block is placed at logical
\ (the v1.0 layout), not at \ (the v3.0 layout).

To finish: run the real \ disc check so the BIOS itself loads the boot
block to the right place and fills those parameters, instead of installing
them heuristically.
