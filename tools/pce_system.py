#!/usr/bin/env python3
"""PC Engine (CD-ROM^2) system emulator for asset dumping.

Layers on top of tools/pce_cpu.py:
  * 2 MiB physical memory (I/O page hardwired at $1FE000-$1FFFFF,
    8 KiB work RAM at $1F0000-$1F1FFF, ROM/loaded pages elsewhere)
  * HuC6270 VDC: register select ($0000), low/high byte ports ($0002/$0003),
    MAWR auto-increment into 64 KiB VRAM - every VRAM write is recorded so the
    real stage graphics can be dumped.
  * HuC6260 VCE: colour index ($0402) / colour data ($0404) -> 512-entry CRAM.
  * A CD-ROM^2 System Card BIOS shim answering the calls the game makes.

Usage (after a stage is loaded):
    sys = PCESystem(...); sys.run_until(...); sys.dump_vram(...)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pce_cpu import HuC6280  # noqa: E402

IO_BASE = 0x1FE000      # $0000-$1FFF logical
WRAM_BASE = 0x1F0000    # $2000-$3FFF logical (MPR1 = $F8)
PHYS_SIZE = 1 << 21

# CD BIOS jump table (from the System Card documentation)
BIOS = {
    0xE000: "cd_boot", 0xE003: "cd_reset", 0xE006: "cd_base",
    0xE009: "cd_read", 0xE00C: "cd_seek", 0xE00F: "cd_exec",
    0xE012: "cd_play", 0xE015: "cd_search", 0xE018: "cd_pause",
    0xE01B: "cd_stat", 0xE01E: "cd_subq", 0xE021: "cd_dinfo",
    0xE024: "cd_contnts", 0xE027: "cd_subrd", 0xE02A: "cd_pcmrd",
    0xE02D: "cd_fade", 0xE030: "ad_reset", 0xE033: "ad_trans",
    0xE036: "ad_read", 0xE039: "ad_write", 0xE03C: "ad_play",
    0xE03F: "ad_cplay", 0xE042: "ad_stop", 0xE045: "ad_stat",
    0xE048: "bm_format", 0xE04B: "bm_free", 0xE04E: "bm_read",
    0xE051: "bm_write", 0xE054: "bm_delete", 0xE057: "bm_files",
    0xE05A: "ex_getver", 0xE05D: "ex_setvec", 0xE060: "ex_getfnt",
    0xE063: "ex_joysns", 0xE066: "ex_joyrep", 0xE069: "ex_scrsiz",
    0xE06C: "ex_dotmod", 0xE06F: "ex_scrmod", 0xE072: "ex_imode",
    0xE075: "ex_vmode", 0xE078: "ex_hmode", 0xE07B: "ex_vsync",
    0xE07E: "ex_rcron", 0xE081: "ex_rcroff", 0xE084: "ex_irqon",
    0xE087: "ex_irqoff", 0xE08A: "ex_bgon", 0xE08D: "ex_bgoff",
    0xE090: "ex_spron", 0xE093: "ex_sproff", 0xE096: "ex_dspon",
    0xE099: "ex_dspoff", 0xE09C: "ex_dmamod", 0xE09F: "ex_sprdma",
    0xE0A2: "ex_satclr", 0xE0A5: "ex_sprput", 0xE0A8: "ex_setrcr",
    0xE0AB: "ex_setred", 0xE0AE: "ex_setwrt", 0xE0B1: "ex_setdma",
    0xE0B4: "ex_binbcd", 0xE0B7: "ex_bcdbin", 0xE0BA: "ex_rnd",
    0xE0D8: "psg_bios", 0xE0DB: "grp_bios", 0xE0DE: "key_bios",
    0xE0E1: "psg_driver", 0xE0E4: "ex_colorcmd",
}

# BIOS work area (in work RAM, mirrored at $F8 with MPR0=$F8 in some builds)
WA = {0xF8: "al", 0xF9: "ah", 0xFA: "bl", 0xFB: "bh",
      0xFC: "cl", 0xFD: "ch", 0xFE: "dl", 0xFF: "dh"}


class PCESystem(object):
    def __init__(self, disc, boot_pointer_phys=WRAM_BASE + 0x2007,
                 verbose=True):
        self.disc = disc              # object with read_sector(n) -> bytes
        self.verbose = verbose
        self.mem = bytearray(PHYS_SIZE)
        # ---- VDC state
        self.vdc_reg = 0
        self.vdc_status = 0        # read at $0000: bit5 = VBlank IRQ
        self.mawr = 0
        self.marr = 0
        self.vram = bytearray(0x10000)
        self.vram_writes = []         # (addr, value) log
        self.cram = [0] * 512
        self.cram_idx = 0
        self.vdc_latch = 0
        self.regs = [0] * 32
        # ---- CD BIOS work area (mirrored at $F8-$FF by the System Card)
        self.wa = {0xF8: 0, 0xF9: 0, 0xFA: 0, 0xFB: 0,
                   0xFC: 0, 0xFD: 0, 0xFE: 0, 0xFF: 0}
        # ---- CPU
        self.cpu = HuC6280(self.read, self.write, io_write=self._io_write)
        # Zero-page addressing always hits work RAM at $1F0000-$1F00FF, even
        # with MPR0=$FF.  Keep the BIOS work-area mirror ($F8-$FF) in sync.
        def _zp_read(addr):
            return self.mem[0x1F0000 + (addr & 0xFF)]

        def _zp_write(addr, val):
            addr &= 0xFF
            self.mem[0x1F0000 + addr] = val & 0xFF
            if 0xF8 <= addr <= 0xFF:
                self.wa[addr] = val & 0xFF

        self.cpu.zp_read = _zp_read
        self.cpu.zp_write = _zp_write
        self.cpu.mpr[0] = 0xFF
        self.cpu.mpr[1] = 0xF8
        self.cpu.pc = 0
        self.bios_calls = []
        self.steps = 0
        self.hook_bios = None         # fn(self, name, addr)
        self.cd_base = [0, 0]         # track-relative sector bases (code 1/2)
        self._bios_enabled = True     # False = run the real System Card code
        # ---- CD-ROM drive interface ($1800-$180F) --------------------
        self.cd_state = "idle"      # idle|param|data|result|final|done|error
        self.cd_params = bytearray()
        self.cd_buf = b""
        self.cd_pos = 0
        self.cd_ack = False         # $1802 bit7: clears status bit6
        self.cd_result = b""
        self.cd_result_pos = 0
        # PCE joypad is read as two active-low nibbles selected by $1000 bit0.
        self.joy_select = 0
        self.joy_low = 0x0F         # Up/Right/Down/Left
        self.joy_high = 0x0F        # II/I/Select/Run (Run = bit3)
        self.cd_flags = 0x00
        self.cd_cmd = 0x00
        self.cd_unlock = 0x0000     # $18C0 unlocks with $AA then $55
        self.cd_result = [0x00] * 8  # $18C1-$18C7 result bytes
        self.cd_ready = 0x01        # "CD-ROM2 unit present"
        self.cd_disc = 0x01         # "disc present"
        self.cd_track = 0x02        # first data track

    # ------------------------------------------------------------------ io
    def read(self, addr):
        """Logical read.

        * A fetch from a System Card BIOS entry point ($E000-$E0FF) runs the
          shim and returns RTS, so `JSR $E009` returns to its caller.  The
          interception is unconditional because the game maps the System Card
          ROM at logical $E000 regardless of what MPR7 happens to be.
        * The 6502 stack page ($0100-$01FF) is always RAM: the game switches
          MPR0 to the I/O page ($FF) after boot and still needs the stack.
        * The I/O page ($0000-$1FFF, minus the stack page) is active when
          MPR0 = $FF; otherwise that range is ordinary banked memory.
        """
        if self._bios_enabled and 0xE000 <= addr <= 0xE0FF and addr in BIOS:
            # The System Card ROM is a JMP table: the byte at the entry point
            # is not an opcode.  Run the shim, then return RTS so the CPU
            # pops the return address the JSR pushed and carries on.
            self.bios_call(addr)
            return 0x60                     # RTS
        if 0x100 <= addr <= 0x1FF:
            return self.mem[0x1F0000 + addr]
        if addr < 0x2000 and self.cpu.mpr[0] == 0xFF:
            return self.io_read(addr)
        return self.mem[self.cpu.phys(addr)]

    def write(self, addr, val):
        if 0x100 <= addr <= 0x1FF:
            self.mem[0x1F0000 + addr] = val & 0xFF
            return
        if addr < 0x2000 and self.cpu.mpr[0] == 0xFF:
            self._io_write(addr, val & 0xFF)
            return
        # mirror the CD BIOS work area ($F8-$FF) whatever page is mapped
        if 0xF8 <= addr <= 0xFF:
            self.wa[addr] = val & 0xFF
        self.mem[self.cpu.phys(addr)] = val & 0xFF

    # ----------------------------------------------------------------- VDC
    def io_read(self, addr):
        if addr == 0x0000:
            # Reading $0000 returns the VDC status byte, not the register
            # select.  The System Card's IRQ handler checks bit 5 (VBlank)
            # and only advances its frame counter at $2241 when it is set.
            status = self.vdc_status
            self.vdc_status &= ~0x20
            return status
        if addr == 0x0002:
            return 0                     # VRR not modelled (unused here)
        if addr == 0x0003:
            return 0x40                  # VSYNC bit set (status)
        if addr in (0x0004, 0x0005, 0x0006, 0x0007):
            return 0
        if addr in (0x0008, 0x000A):     # PSG data -> unused
            return 0
        if addr in (0x0C00, 0x0C01, 0x0C02):
            return 0
        if 0x18C0 <= addr <= 0x18C7:     # CD unit signature / unlock
            # $FE92 in the System Card validates the unit with the byte
            # pattern AA 55 at $18C1/$18C2 and $18C5/$18C6, then uses the
            # ID byte at $18C3/$18C7.  Bit 7 of the ID selects the Super CD
            # unlock path (AA/55 written to $18C0).
            sig = {0x18C1: 0xAA, 0x18C2: 0x55, 0x18C3: 0x00,
                   0x18C5: 0xAA, 0x18C6: 0x55, 0x18C7: 0x80}
            return sig.get(addr, 0x00)
        if addr == 0x1800:               # SCSI status
            return self._cd_status()
        if addr == 0x1801:               # SCSI data / result byte
            return self._cd_read_byte()
        if addr == 0x1802:
            return self.cd_flags
        if addr == 0x1803:
            return 0x10 if self.cd_state != "idle" else 0x00
        if addr == 0x1808:               # CD bulk data port (SCSI READ)
            # Bulk reads do not use the $1802 bit7 handshake; release any
            # ack left over from the command phase.
            self.cd_ack = False
            return self._cd_read_byte(bulk=True)
        if addr in (0x180A, 0x180C):
            return self.cd_flags
        if addr == 0x1806:
            return 0
        if addr == 0x1807:
            return 1
        if addr == 0x1000:               # joypad nibble (active low)
            return self.joy_low if self.joy_select == 0 else self.joy_high
        if 0x1000 < addr < 0x1400:
            return 0xFF
        if 0x1400 <= addr < 0x1800:      # CD-ROM data: not ready
            return 0
        if 0x1800 <= addr < 0x1C00:      # CD-ROM control
            return 0
        if addr == 0x1C02:               # BRAM on/off
            return 0
        return 0

    def _io_write(self, addr, val):
        if addr < 0x2000 and self.cpu.mpr[0] != 0xFF:
            # not the I/O page -> plain banked memory (game code/data)
            self.mem[self.cpu.phys(addr)] = val & 0xFF
            if 0xF8 <= addr <= 0xFF:
                self.wa[addr] = val
            return
        if addr == 0x18C0:               # unlock / mode
            self.cd_unlock = ((self.cd_unlock << 8) | (val & 0xFF)) & 0xFFFF
            if self.cd_unlock == 0xAA55:
                self.cd_ready = 0x01
                self.cd_state = "param"
                # The card's disc-type probe polls work RAM $222D for 4
                # (CD-ROM2) or 8 (Super CD).  A successful AA/55 unlock means
                # the Super CD RAM is present, so report 8.
                # Work RAM is at $1F0000 + (logical & $1FFF), so logical
                # $222D is physical $1F022D (not $1F222D).
                self.mem[0x1F0000 + (0x222D & 0x1FFF)] = 8
            return True
        if 0x18C1 <= addr <= 0x18C7:
            return True
        if addr == 0x1000:               # joypad select
            self.joy_select = val & 1
            return True
        if addr == 0x1801:               # SCSI parameter byte
            self._cd_write_param(val)
            return True
        if addr == 0x1800:               # SCSI command
            self._cd_write_command(val)
            return True
        if addr == 0x1802:               # SCSI control/ack
            self._cd_write_control(val)
            return True
        if addr in (0x1803, 0x1804, 0x1805, 0x1809, 0x180B, 0x180D,
                    0x180E, 0x180F):
            return True
        if addr == 0x0000:               # VDC register select
            self.vdc_reg = val & 0x1F
            return True
        if addr == 0x0002:               # VDC data low
            if self.vdc_reg == 0:        # MAWR low
                self.mawr = (self.mawr & 0xFF00) | val
            elif self.vdc_reg == 2:      # VRAM write low byte
                self.vdc_latch = val
                self.vram_write_pending = True
            elif self.vdc_reg == 1:
                self.marr = (self.marr & 0xFF00) | val
            else:
                self.regs[self.vdc_reg] = (self.regs[self.vdc_reg] & 0xFF00) | val
            return True
        if addr == 0x0003:               # VDC data high
            if self.vdc_reg == 0:
                self.mawr = (self.mawr & 0x00FF) | (val << 8)
            elif self.vdc_reg == 2:      # VRAM write high byte -> commit word
                word = (val << 8) | self.vdc_latch
                self._vram_store(word)
            elif self.vdc_reg == 1:
                self.marr = (self.marr & 0x00FF) | (val << 8)
            else:
                self.regs[self.vdc_reg] = (self.regs[self.vdc_reg] & 0x00FF) | (val << 8)
            return True
        # ---- CD BIOS work area mirror ($F8-$FF) -----------------------
        if 0xF8 <= addr <= 0xFF:
            self.wa[addr] = val
            return True
        if addr == 0x0400:
            return True
        if addr == 0x0402:               # VCE colour index low
            self.cram_idx = (self.cram_idx & 0xFF00) | val
            return True
        if addr == 0x0403:               # VCE colour index high
            self.cram_idx = (self.cram_idx & 0x00FF) | ((val & 1) << 8)
            return True
        if addr == 0x0404:               # VCE colour data low
            self.cram[self.cram_idx & 0x1FF] = \
                (self.cram[self.cram_idx & 0x1FF] & 0xFF00) | val
            return True
        if addr == 0x0405:               # VCE colour data high
            self.cram[self.cram_idx & 0x1FF] = \
                (self.cram[self.cram_idx & 0x1FF] & 0x00FF) | ((val & 1) << 8)
            self.cram_idx = (self.cram_idx + 1) & 0x1FF
            return True
        if addr in (0x0800, 0x0802, 0x0804, 0x0806):   # PSG
            return True
        if addr == 0x1C02:               # BRAM on/off
            return True
        if 0x1C00 <= addr < 0x2000:      # arcade card / BRAM - accept
            return True
        return False

    # ------------------------------------------------------- work area + BIOS
    def bios_call(self, addr):
        """Execute the System Card BIOS routine the game asked for."""
        name = BIOS.get(addr)
        if name is None:
            return 0
        self.bios_calls.append((self.steps, name))
        if self.hook_bios:
            self.hook_bios(self, name, addr)
        fn = getattr(self, "bios_" + name, None)
        return fn() if fn else 0

    def wa16(self, hi, lo):
        return (self.wa[hi] << 8) | self.wa[lo]

    def wa24(self):
        return (self.wa[0xFC] << 16) | (self.wa[0xFD] << 8) | self.wa[0xFE]

    def set_a(self, v):
        self.cpu.a = v & 0xFF

    def phys_of(self, logical):
        return self.cpu.phys(logical)

    def _write_phys_range(self, start, data):
        for i, byte in enumerate(data):
            self.mem[(start + i) & (PHYS_SIZE - 1)] = byte

    def _load_sectors(self, unit_bytes):
        """cd_read core: count sectors/user bytes into the destination.

        Work area: $F8=al $F9=ah $FA=bl $FB=bh $FC=cl $FD=ch $FE=dl $FF=dh.
        The sector number is the 24-bit cl:ch:dl and the destination is bx.
        """
        sector = self.wa24()
        dh = self.wa[0xFF]
        dest = self.wa16(0xFB, 0xFA)
        if dh == 0xFE:
            # $FE: ah:al is a *byte* count; sector payload is 2048 bytes.
            size = self.wa16(0xF9, 0xF8)
            count = max(1, (size + 2047) // 2048)
        else:
            # $FF and $01..$06: al is a sector count.
            count = self.wa[0xF8] or 1
        if hasattr(self.disc, "read_sectors"):
            data = self.disc.read_sectors(sector, count)
        else:
            data = b"".join(self.disc.read_sector(sector + i) for i in range(count))

        # dh selects the destination:
        #   $FE       -> VRAM; bx is a VRAM *word* address and ah:al a byte count
        #   $01 / $FF -> local (MPR-mapped) RAM at logical address bx, al sectors
        #   $02..$06  -> MPR page (2=MPR1 .. 6=MPR5), destination = bx
        if dh == 0xFE:
            base = dest * 2
            for i, byte in enumerate(data):
                self.vram[(base + i) & 0xFFFF] = byte
            self.vram_writes.append((base, len(data)))
            return 0
        if dh in (1, 0xFF):
            self._write_phys_range(self.cpu.phys(dest), data)
            return 0
        # dh = $02..$06 -> MPR page (2=MPR1 .. 6=MPR5)
        page = max(1, min(5, dh - 1))
        self._write_phys_range((self.cpu.mpr[page] << 13) |
                               ((dest & 0x1FFF) if dest >= 0x2000 else dest),
                               data)
        return 0

    def bios_cd_read(self):
        result = self._load_sectors(True)
        self.set_a(result)          # A=0 means success; the game retries otherwise
        return result

    def bios_cd_exec(self):
        self._load_sectors(False)
        # cd_exec jumps to the loaded entry point
        self.cpu.pc = self.wa16(0xFB, 0xFA)
        raise StopIteration("cd_exec -> $%04X" % self.cpu.pc)

    def bios_cd_base(self):
        # ch selects the code (0/1); the track number is in al
        idx = self.wa[0xFD] & 1
        self.cd_base[idx] = self.wa[0xF8] & 3
        self.set_a(0)
        return 0

    def bios_cd_seek(self):
        return 0

    def bios_cd_play(self):
        return 0

    def bios_cd_search(self):
        self.set_a(0)
        return 0

    def bios_cd_pause(self):
        return 0

    def bios_cd_stat(self):
        self.set_a(0x04)          # single speed, ready
        return 0

    def bios_cd_subq(self):
        self.set_a(0)
        return 0

    def bios_cd_dinfo(self):
        self.set_a(0)
        return 0

    def bios_cd_contnts(self):
        self.set_a(0)
        return 0

    def bios_cd_subrd(self):
        self.set_a(0)
        return 0

    def bios_cd_pcmrd(self):
        self.set_a(0)
        return 0

    def bios_cd_fade(self):
        return 0

    def bios_ad_reset(self):
        return 0

    def bios_ad_trans(self):
        # ADPCM transfer: al sectors from ah:bl into the ADPCM buffers.
        # We only need the call to succeed, but it must return A=0.
        self.set_a(0)
        return 0

    def bios_ad_read(self):
        self.set_a(0)
        return 0

    def bios_ad_write(self):
        return 0

    def bios_ad_play(self):
        return 0

    def bios_ad_cplay(self):
        return 0

    def bios_ad_stop(self):
        return 0

    def bios_ad_stat(self):
        self.set_a(0)
        return 0

    def bios_bm_format(self):
        return 0

    def bios_bm_free(self):
        return 0

    def bios_bm_read(self):
        self.set_a(0)
        return 0

    def bios_bm_write(self):
        return 0

    def bios_bm_delete(self):
        return 0

    def bios_bm_files(self):
        self.set_a(0)
        return 0

    def bios_ex_getver(self):
        self.set_a(2)             # system card version 2.x
        return 0

    def bios_ex_setvec(self):
        return 0

    def bios_ex_getfnt(self):
        return 0

    def bios_ex_joysns(self):
        # the game reads the pad ports itself at $2228/$222D; nothing pressed
        return 0

    def bios_ex_joyrep(self):
        return 0

    def bios_ex_scrsiz(self):
        self.regs[7] = 0x1F        # 32 cells - 1
        return 0

    def bios_ex_dotmod(self):
        return 0

    def bios_ex_scrmod(self):
        return 0

    def bios_ex_imode(self):
        return 0

    def bios_ex_vmode(self):
        return 0

    def bios_ex_hmode(self):
        return 0

    def bios_ex_vsync(self):
        return 0                  # returns immediately

    def bios_ex_rcron(self):
        return 0

    def bios_ex_rcroff(self):
        return 0

    def bios_ex_irqon(self):
        self.cpu.fI = 0
        return 0

    def bios_ex_irqoff(self):
        self.cpu.fI = 1
        return 0

    def bios_ex_bgon(self):
        return 0

    def bios_ex_bgoff(self):
        return 0

    def bios_ex_spron(self):
        return 0

    def bios_ex_sproff(self):
        return 0

    def bios_ex_dspon(self):
        return 0

    def bios_ex_dspoff(self):
        return 0

    def bios_ex_dmamod(self):
        return 0

    def bios_ex_sprdma(self):
        return 0

    def bios_ex_satclr(self):
        return 0

    def bios_ex_sprput(self):
        return 0

    def bios_ex_setrcr(self):
        return 0

    def bios_ex_setred(self):
        return 0

    def bios_ex_setwrt(self):
        # A = low byte, X = high byte -> VRAM write address
        self.mawr = ((self.cpu.x << 8) | self.cpu.a) & 0xFFFF
        return 0

    def bios_ex_setdma(self):
        return 0

    def bios_ex_binbcd(self):
        return 0

    def bios_ex_bcdbin(self):
        return 0

    def bios_ex_rnd(self):
        self.set_a(0)
        return 0

    def bios_psg_bios(self):
        return 0

    def bios_grp_bios(self):
        return 0

    def bios_key_bios(self):
        return 0

    def bios_psg_driver(self):
        return 0

    def bios_ex_colorcmd(self):
        return 0

    # ------------------------------------------------- CD-ROM drive
    # ---- SCSI command engine -------------------------------------------
    # The CD unit is a SCSI device.  The card sends: $81 on $1801, $81 on
    # $1800, then a 6-byte command descriptor block (CDB) through $1801.
    # Status codes read from $1800:
    #   $D0 parameter request, $C8 data byte ready, $D8 result byte ready,
    #   $F8 command complete, $98 done, $88 end/error.
    CD_STATUS = {"param": 0xD0, "data": 0xC8, "result": 0xD8,
                 "final": 0xF8, "done": 0xD8, "error": 0x88}

    def _cd_status(self):
        code = self.CD_STATUS.get(self.cd_state, 0x00)
        if self.cd_ack:
            # $1802 bit7 acknowledges the byte; the drive drops REQ/MSG
            # (bits 7 and 6) until the card releases the ack.
            code &= ~0xC0
        return code

    def _cd_read_byte(self, bulk=False):
        # $1808 is the bulk sector port: it only supplies the data phase and
        # must not consume the $D8 result / $F8 final bytes (those belong to
        # the $1801 control path).
        if bulk and self.cd_state != "data":
            return 0
        if self.cd_state == "data":
            if self.cd_pos < len(self.cd_buf):
                byte = self.cd_buf[self.cd_pos]
                self.cd_pos += 1
                if self.cd_pos >= len(self.cd_buf):
                    self.cd_state = "result"
                    self.cd_result = b"\x00"
                    self.cd_result_pos = 0
                return byte
            self.cd_state = "result"
            self.cd_result = b"\x00"
            self.cd_result_pos = 0
            return 0
        if self.cd_state == "result":
            if self.cd_result_pos < len(self.cd_result):
                byte = self.cd_result[self.cd_result_pos]
                self.cd_result_pos += 1
                if self.cd_result_pos >= len(self.cd_result):
                    self.cd_state = "final"
                    self.cd_result = b"\x00"
                    self.cd_result_pos = 0
                return byte
            self.cd_state = "final"
            self.cd_result = b"\x00"
            self.cd_result_pos = 0
            return 0
        if self.cd_state == "final":
            self.cd_state = "idle"
            return 0
        if self.cd_state == "done":
            # One completion byte ($D8 phase), then the $F8 final status.
            self.cd_state = "final"
            self.cd_result = b"\x00"
            self.cd_result_pos = 0
            return 0
        return 0

    def _cd_write_param(self, val):
        # The driver writes $81 to $1801 before selecting the drive.  That
        # byte is a prefix, not CDB data, and it also means "start a new
        # transaction" - clear any leftover final/result phase from the
        # previous command so the next $1800 read sees an idle unit.
        if val == 0x81:
            self.cd_state = "idle"
            self.cd_params.clear()
            self.cd_cmd = 0
            return
        if self.cd_state == "param" and self.cd_cmd == 0x81:
            self.cd_params.append(val)
            if len(self.cd_params) >= 6:
                self._scsi_exec()

    def _cd_write_command(self, val):
        self.cd_cmd = val
        if val == 0x81:
            self.cd_state = "param"
            self.cd_params.clear()
            return
        # A direct command (reset/pause etc.): acknowledge it.
        self.cd_state = "done"

    def _cd_write_control(self, val):
        self.cd_ack = bool(val & 0x80)
        self.cd_flags = val & 0x7F

    def _scsi_exec(self):
        p = self.cd_params
        op = p[0]
        self.cd_pos = 0
        self.cd_result_pos = 0
        if op == 0x08:                      # READ (6)
            lba = (p[1] << 16) | (p[2] << 8) | p[3]
            count = p[4] or 1
            if hasattr(self.disc, "read_sectors"):
                self.cd_buf = self.disc.read_sectors(lba, count)
            else:
                self.cd_buf = b"".join(self.disc.read_sector(lba + i)
                                       for i in range(count))
            self.cd_state = "data" if self.cd_buf else "result"
            if not self.cd_buf:
                self.cd_result = b"\x00"
        elif op == 0x00:                    # TEST UNIT READY
            self.cd_state = "done"
        elif op == 0x03:                    # REQUEST SENSE
            self.cd_result = bytes(4)
            self.cd_state = "result"
        elif op == 0xDE:                    # CD_DINFO (TOC)
            # AL=0: min/max track; AL=1: lead-out MSF; AL=2: track start+control.
            al = p[1]
            track = p[2]
            if al == 0x00:
                # 72 tracks on this disc; track 1 is audio, track 2 is data.
                data = bytes([0x01, 0x72, 0x00, 0x00])
            elif al == 0x01:
                # lead-out of the last track (52:30:28 BCD)
                data = bytes([0x52, 0x30, 0x28, 0x00])
            else:
                if track == 0x02:
                    # track 2 INDEX 01 = 00:44:65; control bit2 = data
                    data = bytes([0x00, 0x44, 0x65, 0x04])
                elif track == 0x01:
                    data = bytes([0x00, 0x00, 0x00, 0x00])
                else:
                    data = bytes([0x00, 0x00, 0x00, 0x00])
            self.cd_buf = data
            self.cd_state = "data"
        else:
            self.cd_state = "done"
        self.cd_params.clear()

    def _vram_store(self, word):
        a = self.mawr & 0xFFFF
        self.vram[a] = word & 0xFF
        self.vram[a + 1] = (word >> 8) & 0xFF
        self.vram_writes.append((a, word))
        self.mawr = (self.mawr + self.auto_inc()) & 0xFFFF

    def auto_inc(self):
        # reg 9 (MWR) selects the auto-increment amount
        return [1, 32, 64, 128][self.regs[9] & 3]

    # ------------------------------------------------------------------ CPU
    def install_page(self, page, data):
        for i in range(0x2000):
            self.mem[(page << 13) | i] = data[i % len(data)] if data else 0

    def run(self, max_steps=2_000_000):
        try:
            for _ in range(max_steps):
                self.steps += 1
                self.cpu.step()
        except RuntimeError as e:
            if self.verbose:
                print("stop after %d steps: %s" % (self.steps, e))
        return self.steps

    def dump_vram(self, path):
        with open(path, "wb") as fh:
            fh.write(bytes(self.vram))
        return path

    def dump_cram(self, path):
        out = bytearray()
        for c in self.cram:
            out.append(c & 0xFF)
            out.append((c >> 8) & 0xFF)
        with open(path, "wb") as fh:
            fh.write(bytes(out))
        return path


def load_disc(cue_path, track=2):
    """Open the disc image for sector reads relative to a track's index01."""
    base = os.path.dirname(os.path.abspath(cue_path))
    name = os.path.basename(cue_path)
    iso = os.path.join(base, name[:-4] + ".iso")
    fh = open(iso, "rb")
    manifest = json.load(open(os.path.join(base, "tracks.json"))) \
        if os.path.exists(os.path.join(base, "tracks.json")) else None
    tracks = manifest["tracks"] if manifest else []
    t = [x for x in tracks if x["number"] == track]
    first = t[0]["index01_frame"] if t else 3365

    class Disc(object):
        def read_sector(self, n):
            """Sectors are 2048 bytes of user data from the continuous stream."""
            fh.seek((first + n) * 2352)
            return fh.read(2048)

        def read_frame(self, n):
            fh.seek((first + n) * 2352)
            return fh.read(2352)

    return Disc()


if __name__ == "__main__":
    print(__doc__)
