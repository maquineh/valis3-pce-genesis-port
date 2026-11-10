## Boot chain findings (this pass)

The goal was to boot the game in an emulator to dump each stage's real VRAM.
The CPU/VDC/VCE/CD-BIOS layer is now in place and unit-tested
(`tools/test_cpu.py`, ALL PASS).  What the emulator established about the
boot chain:

### The IPL structure (verified from the disc)

* Data track 2 sector frames are `16-byte header + 2048-byte user data +
  288-byte ECC`.  `track_02.bin` is the **continuous frame stream**, so
  `sector N` starts at byte offset `N*2352` and its payload at `N*2352+16`.
* Sector 1 (offset 2352+16) is the volume descriptor: it contains a track
  table and the strings `PC Engine CD-ROM SYSTEM` /
  `Copyright HUDSON SOFT / NEC Home Electronics,Ltd.`.
  Decoding the first 5-byte entries gives:
  `track 1: ctrl=$40 m=00 s=40 f=00 no=01` → MSF `00:40:00`.
* Sectors 0-7 are the **boot block** (16 KiB).  Its code spans only
  `$03E0-$04E4`; the rest is tile/dither data.  The boot block is loaded into
  work RAM (`$F8000` page, logical `$2000-$3FFF`) and entered at `$23E0`.
* The boot code's `JMP ($2007)` reads the pointer stored in the boot block at
  offset 7 → `$838D`.  With the MPR values the block itself specifies
  (`$3008=0, $300A=$38, $300C=$38`), `$838D` resolves to physical `$7038D`,
  which contains tile dither (`$E5E5…`), not code.

### Conclusion

The **game's main program is not inside the first 16 KiB of the data track**.
The System Card IPL must load it (via the `cd_exec` path that the loader code
decoded earlier in `tools/decode_cd_calls.py`: `cd_exec` sector `$20` → RAM
`$4000`, `cd_exec` sector `$3D0` → RAM `$4000`) before the boot's final jump
reaches real code.  Emulating that faithfully needs the copyrighted System
Card BIOS, which is not in this repository, so the emulator can be brought
only as far as the boot block.

### What is verified and usable now

* `tools/pce_cpu.py` - HuC6280 core (all 65C02 opcodes + HuC6280 extensions,
  7-byte block transfers TII/TDD/TIN/TIA/TAI, TAM/MPR banking, ST0/1/2 to the
  hardwired VDC ports, branches with correct 3-byte BBR/BBS operands).
* `tools/pce_system.py` - VDC (register select, MAWR auto-increment, VRAM
  write log), VCE (colour index/data, CRAM), the CD BIOS work area mirror
  (`$F8-$FF`), a shim for the 60+ System Card entry points the game calls,
  and a stack page that stays RAM when MPR0 is switched to the I/O page.
* `tools/trace_boot.py`, `tools/emulate_boot.py`, `tools/trace_boot.py` -
  bootstrap drivers used to reach the conclusions above.
* `tools/test_cpu.py` - 14 assertions covering the parts above.

### The two ways forward (documented for the next turn)

1. Decode the stage tracks' 4-byte records (period 86) - still the cheapest
   fully-local path.
2. Supply the System Card BIOS (copyrighted) so the emulator can complete
   `cd_exec` and dump the real stage VRAM/BAT.

