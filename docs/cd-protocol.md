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
