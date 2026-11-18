# Sega CD port checkpoint — 2026-11-15

The port is still in progress. This checkpoint records the current real-System-Card
boot investigation and the files needed to continue it.

## Current state

- The unshimmed Japanese System Card v3.0 runs through `ValisDisc()` with the
  complete TOC and the approximate NTSC frame clock.
- A no-extra-input run and a timed-input run take different paths. With no
  timed input, the game reaches the opening program and then follows an audio
  path; it does not enter the ACT0 overlay.
- One timed RUN at post-run step `9000000` reads track-2 ranges beginning at
  LBA 4740. At the end of that capture, `$2208/$2209` is `$4DBA` and MPR2 is
  `$80`; this run does not reach ACT0.
- An earlier four-pulse run reached the track-20 `ACT0` visual module. It read
  LBA 52450–52473, 52478–52493 and 52494–52513, then started CD-DA track 8.
  That extended capture stopped at `$20D8` on illegal opcode `$0B`, after
  1,127 VBlank interrupts, without reading an `STG` block.
- In that ACT0 capture, the BIOS VBlank path called `$E86A`, which jumps through
  `$2208/$2209 = $4D3A`. With MPR2 `$82`, `$4D3A` resolves to data in the ACT0
  bank; `$4D41` contains `JSR $0000`. The same logical address resolves to
  different bytes with MPR2 `$80`. The illegal opcode is a downstream symptom;
  do not add `$0B` as an instruction.
- The ACT0 trace also showed MPR2 changing from `$80` to `$82` at `$7D41`, where
  the program restores the saved mapping from `$310F`. The precise input pulse
  and vector update that lead to `$4D3A` still need to be captured together.

## Reproduction artifacts

- The runner is [run_full_disc.py](../tools/run_full_disc.py). It accepts timed
  inputs as `STEP[:ACTIVE_LOW_MASK]` and logs writes to the BIOS callback vector.
- The no-extra-input run is in
  `build/bios-continue-20261115/vector-writes/`.
- The single-RUN run (`5000000 17000000 9000000:0x07`) is in
  `build/bios-continue-20261115/first-input/`.
- The earlier four-pulse ACT0 run and its crash-time trace are in
  `build/bios-continue-20261115/act0-exit-final/`.
- Related progress notes are in [bios-boot-progress.md](bios-boot-progress.md),
  [cd-protocol.md](cd-protocol.md), and [stage-status.md](stage-status.md).

## Next step

Repeat the timed-input path with vector-write instrumentation and narrow down
which pulse installs `$4D3A` and which transition leaves MPR2 at `$82`. Compare
the vector target and the physical bytes it resolves to at each VBlank. Keep
the current capture directories intact; each emulator run should use a fresh
output prefix. Do not change the BIOS callback or opcode table based only on
the current crash trace.

No stage loader has been reached, and no test suite was run during this
checkpoint.
