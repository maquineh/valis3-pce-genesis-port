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
        self.cpu.mpr[0] = 0xFF
        self.cpu.mpr[1] = 0xF8
        self.cpu.pc = 0
        self.bios_calls = []
        self.steps = 0
        self.hook_bios = None         # fn(self, name, addr)
        self.cd_base = [0, 0]         # track-relative sector bases (code 1/2)

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
        if 0xE000 <= addr <= 0xE0FF and addr in BIOS:
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
            return self.vdc_reg
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
        if 0x1000 <= addr < 0x1400:      # joypad: nothing pressed
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
        if unit_bytes:
            size = self.wa16(0xF9, 0xF8)
            count = max(1, (size + 2351) // 2352)
        else:
            count = self.wa[0xF8] or 1
        if hasattr(self.disc, "read_sectors"):
            data = self.disc.read_sectors(sector, count)
        else:
            data = b"".join(self.disc.read_sector(sector + i) for i in range(count))

        # dh selects the destination bank:
        #   $01 / $FE / $FF -> local (MPR-mapped) RAM at logical address bx
        #   $02..$06        -> MPR page (2=MPR1 .. 6=MPR5), destination = bx
        #   $07/$08..       -> VRAM: bx is a VRAM *word* address
        if dh in (0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E):
            base = dest * 2
            for i, byte in enumerate(data):
                self.vram[(base + i) & 0xFFFF] = byte
            self.vram_writes.append((base, len(data)))
            return 0
        if dh in (1, 0xFE, 0xFF):
            self._write_phys_range(self.cpu.phys(dest), data)
            return 0
        # dh = $02..$06 -> MPR page (2=MPR1 .. 6=MPR5)
        page = max(1, min(5, dh - 1))
        self._write_phys_range((self.cpu.mpr[page] << 13) |
                               ((dest & 0x1FFF) if dest >= 0x2000 else dest),
                               data)
        return 0

    def bios_cd_read(self):
        return self._load_sectors(True)

    def bios_cd_exec(self):
        self._load_sectors(False)
        # cd_exec jumps to the loaded entry point
        self.cpu.pc = self.wa16(0xFB, 0xFA)
        raise StopIteration("cd_exec -> $%04X" % self.cpu.pc)

    def bios_cd_base(self):
        # ch selects the code (0/1); the track number is in al
        idx = self.wa[0xFD] & 1
        self.cd_base[idx] = self.wa[0xF8] & 3
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
        # We only need the call to succeed.
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
