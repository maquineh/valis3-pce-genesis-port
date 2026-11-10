## Addendum: the stage loader code (found this pass)

### The 4-sector streaming reads

`tools/find_stage_reads.py` enumerates all 49 `cd_read` sites.  Eight of them
(`$22529E`, `$2252C4`, `$2252EA`, `$225310`, `$225336`, `$22535C`, `$22537F`,
`$2256A7`) read **4 sectors each into local RAM `$8000`** (`dh=$01`), from
sectors:

    988, 1000, 1020, 1040, 1060, 1080, 1120, 1128

Each of those frames carries a 4-byte chunk header `01 SS SS 01` and then
either a **stage title card** or **6502 code**:

| sector | file | header | payload |
|---|---|---|---|
| 988 | `$237540` | `01 03 03 01` | text `VALIS III ACT ...` |
| 1000 | `$23E380` | `01 03 15 01` | **code** |
| 1020 | `$249B40` | `01 03 35 01` | **code** |
| 1040 | `$255300` | `01 03 55 01` | text `VALIS III ACT ...` |
| 1060 | `$260AC0` | `01 04 00 01` | **code** |
| 1080 | `$26C280` | `01 04 20 01` | text `VALIS III ACT ...` |
| 1120 | `$283200` | `01 04 60 01` | **code** |
| 1128 | `$287B80` | `01 04 68 01` | text `VALIS III OMAKE` |

### The stage entry point (verified code)

The code chunk at sector 1000 is loaded to logical `$8000`; its entry is at
file `$23E394` (logical `$8004`) and is fully coherent:

```
$23E394  STA $F5
$23E396  JSR $E087        ex_irqoff
$23E399  JSR $E081        ex_rcroff
$23E39C  TSX ; STX $DE
$23E39F  LDA $FFF5 ; CLC ; ADC #$03 ; TAM #$20     MPR5 = $FFF5+3
$23E3A7  INC A ; TAM #$40                          MPR6 = $FFF5+4
$23E3AA  LDA #$04 ; LDX #$14 ; LDY #$85 ; JSR $E05D  ex_setvec
$23E3B3  JSR $E084        ex_irqon
$23E3B6  CLA ; JSR $E02D  cd_fade
$23E3BA  JSR $847C
$23E3BD  JSR $E099        ex_dspoff
$23E3C0  JSR $E07B        ex_vsync
$23E3C4  JSR $E06C        ex_dotmod
$23E3C7  STZ $2214 ; LDA #$7F ; STA $2215
$23E3CF  JSR $E0A2        ex_satclr
$23E3D2  JSR $E09F        ex_sprdma
$23E3D5  JSR $E030        ad_reset
$23E3D8  TMA #$20 ; PHA
$23E3DB  LDA $FFF5 ; CLC ; ADC #$06 ; TAM #$20    MPR5 = $FFF5+6
$23E3E3  CLA ; LDX #$08 ; JSR $E0AE              ex_setwrt -> MAWR $0800
$23E3E9  TIA $00A0, $0200, $0010                tile upload
$23E3F0  PLA ; TAM #$20
$23E3F3  JSR $8790
$23E3F6  JSR $959B
...
```

`tools/verify_chunk.py` re-derives this.  So the stage data is *streamed*:
the master loader reads a 4-sector chunk to `$8000`, the chunk's code uploads
tiles/palette through the VDC ports, and the next chunk is read.

### The multi-read setup routine `$847C` (verified, file `$23E80C`)

This is the routine the stage entry calls right after `cd_fade`, and it is
completely coherent:

```
$23E80C  LDA $F5 ; AND #$01 ; STA $F5
$23E812  LDA #$18 ; JSR $895D
$23E817  LDA #$00 ; STA $FC          cl = 0
         LDA #$00 ; STA $FD          ch = 0
         LDA #$00 ; STA $FE          dl = 0    -> sector 0
         LDA #$1D ; STA $F8          al = 29
         STZ $FF                     dh = 0
         LDA #$00 ; STA $FB ; STZ $FA           dest $0000
         JSR $E033                   ad_trans (ADPCM load)
$23E836  LDA #$00 ; STA $FC/$FD
         LDA #$20 ; STA $FE          dl = $20  -> sector 32
         LDA #$FF ; STA $FF          dh = $FF
         STZ $FA ; LDA #$10 ; STA $FB           dest $1000
         STZ $F9 ; LDA #$18 ; STA $F8           al = 24 sectors
         JSR $E009                   cd_read
$23E85C  LDA #$00 ; STA $FC/$FD
         LDA #$38 ; STA $FE          dl = $38  -> sector 56
         LDA #$05 ; STA $FF          dh = $05
         LDA $FFF5 ; CLC ; ADC #$05 ; STA $FA   bl = $FFF5+5
         LDA #$08 ; STA $F8          al = 8 sectors
         JSR $E009                   cd_read
```

So the stage data is streamed in three passes: an ADPCM transfer, a 24-sector
read from sector 32, and an 8-sector read from sector 56.  `cd_read` with
`dh=$FF` uses `al` as the **sector count** and `bx` as a local-RAM address,
while `dh=$FE` (used by the tile blocks decoded in
`tools/list_vram_reads.py`) uses `ah:al` as a **byte count** into VRAM.

The chunk code uploads tiles with `TIA ..., $0200, ...` and palettes through
the resident overlay's `$8CD9` routine, but the *map* (BAT) upload happens
inside routines at `$847C`/`$8790`/`$8839`/`$88E2` whose full bodies have not
been traced yet.  Until those are traced, the only verified stage screen
remains the one in `game/res/gfx/stage1_all_*`.
