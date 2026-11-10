# Boot status with the Super System Card v3.0

Both System Cards are now in the repository:

| file | size | cd_boot entry |
|---|---|---|
| `syscard1.pce` | 262144 | `$E0E7` |
| `[BIOS] TurboGrafx CD Super Card (USA) (v3.0).pce` | 262144 | `$E0F3` |

Both carry the disc's **1237-byte boot signature at image `$3FAE1`**
(`tools/match_signatures.py`), so the System Card's own boot-block check is
satisfied by either card.

## What still fails

The disc's entry at logical `$2B26` does its own 74-byte comparison:

```
$2B26  LDX #$4A
$2B29  pointer $3020      (boot block, file $0830)
$2B31  pointer $DFB6      (MPR6-relative)
$2B39  LDA ($FA),Y ; CMP ($FC),Y ; BEQ ok
$2B3F  RTS                                    ; mismatch -> abort
```

`tools/find_signature_bank.py` scans **all 256 MPR6 banks of both cards** for
those 74 bytes: no bank reaches even 8/74.  So `$DFB6` is not a static ROM
reference - it is either work RAM that a *running* BIOS fills in, or the
comparison is a decryption-key check on data the real boot prepares first.

Consequence, reproduced with both cards (`tools/run_v3.py`):

```
step     14  2B3F  RTS -> 0001        <- the 74-byte check aborts
```

## Why the synthetic bootstrap cannot get past this

Starting the emulator at the disc entry (`$2B26`) with a hand-built state
cannot work, because the boot code depends on state the real BIOS creates:

* with `MPR0 = $FF` (which the boot's own MPR setup installs) the zero-page
  accesses `LDA $04`, `LDA $07`, `STA $08` hit the I/O page, not work RAM;
* with `MPR0 = $F8` those same accesses hit work RAM, but then the boot's
  `TAM #$01` immediately overwrites MPR0 with `$FF`.

So the real IPL must establish `$2004/$2007/$2008` **before** the boot block
runs, and the value of `$DFB6` must be produced by the real CD boot
(`cd_boot`'s own read/verify path) - neither of which the synthetic
bootstrap reproduces.

## What is needed to go further

Run the **real** System Card from its reset vector (`$E10C` in v3.0) and
emulate the CD-ROM² drive interface (`$1800`-range command/status plus the
data port), so the BIOS performs its own boot exactly as on hardware.  That is
the remaining engineering task; the CPU, VDC, VCE, work RAM and the disc
sector source are all already implemented and unit-tested
(`tools/test_cpu.py`, 14/14 PASS).
