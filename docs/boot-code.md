## PCE boot code located (foundation for the emulator)

The game's boot routine is at `track_02` offset `$0400-$04E4`, and it confirms
the CPU address mapping used by the rest of the game.

### Entry sequence (disassembled, `tools/disasm6280.py`)

```
0403  JSR $E009        ; cd_read (load the disc's first block)
0406  CMP #$00         ; retry on error
040A  ...
041F  STA $F8 / STZ $FA..$FF   ; CD BIOS work area: al/ah/bl/bh = 0
0427  JSR $E033        ; ad_trans
0437  LDA $3017 .. ASL A x3      ; align a pointer
043F  LDA #$FF; STA $F8; STA $F9
0445  LDA $3018; STA $FF
044A  LDA $00; AND #$80; STA $FE
0450  JSR $E03C        ; ad_play
0459  JSR $E08A        ; ex_bgon
---------- memory map setup ----------
045C  LDA #$FF; TAM #$01   ; MPR0 = $FF  -> $0000-$1FFF = I/O page
0460  LDA #$F8; TAM #$02   ; MPR1 = $F8  -> $2000-$3FFF = 8 KiB work RAM
0464  LDA $3008; ADC $FFF5; TAM #$04   ; MPR2 = $3008 + $FFF5
046D  LDA $3009; ADC $FFF5; TAM #$08   ; MPR3
0476  LDA $300A; ADC $FFF5; TAM #$10   ; MPR4
047F  LDA $300B; ADC $FFF5; TAM #$20   ; MPR5
0488  LDA $300C; ADC $FFF5; TAM #$40   ; MPR6
0491  TII $0030, $0120, $0800           ; copy $800 bytes $0030 -> $0120
04DE  LDX #$FF; TXS
04E1  JMP ($2007)                       ; jump to the entry point in work RAM
```

So the game's real entry point is the 16-bit pointer stored at **work RAM
`$2007`**, and the work RAM page is filled by the preceding `cd_read`/`ad_trans`
calls (the BIOS work area `$F8-$FF` = al/ah/bl/bh/cl/ch/dl/dh, i.e. destination
address + sector number + count).

### What this means for the emulator
1. The HuC6280 core needs MPR banking and the 7-byte block transfers - done in
   `tools/pce_cpu.py` (verified: `LDA #$05; STA $10; LDA #$04; ADC #$02`
   returns 6 in A and stores it at `$11`).
2. The BIOS shim only has to answer nine calls the game actually makes
   (`tools/find_bios_calls.py`): `cd_read`, `cd_exec`, `cd_play`, `cd_search`,
   `cd_base`, `cd_stat`, `cd_pause`, `cd_fade`, `ad_reset` (plus `ad_trans`,
   `ad_play`, `ex_bgon` used by this boot block).
3. The stage tile blocks that must then be loaded into VRAM are the nine known
   from `tools/list_vram_reads.py` (sectors `$2C,$2F,$30,$34,$44,$4A4,$4D4,$4F4,$514`).
