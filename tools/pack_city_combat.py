"""Pack the original Japanese cartridge's sword, reactions and two HUD rows.

The roof reference starts at s12000 from capture_genesis_city.py. From that
state march right during frames [70,225). For slash press Genesis B (libretro
button 0) on frames 28 and 115; hurt uses no attack. Frame numbers below are
states saved immediately AFTER the frame. The aerial swing is from the main
reference capture. All sprite layouts, pattern bits and flips come from SAT.
"""
import argparse
import ctypes as ct
import struct
import sys
import zlib
from pathlib import Path

from pack_genesis_city import State, words
import test_megacd_libretro as harness

ROOT = Path(__file__).resolve().parents[1]


def capture(args, route):
    wanted = ({30, 33, 37, 41, 125, 128, 132, 136, 140, *range(38, 81)}
              if route == 'slash' else {124, 128, 138})
    args.captures.mkdir(parents=True, exist_ok=True)
    def before_frame(core, frame):
        if frame == 0:
            raw = zlib.decompress((args.roof/'s12000.z').read_bytes())
            core.retro_unserialize.argtypes = [ct.c_void_p, ct.c_size_t]
            core.retro_unserialize.restype = ct.c_bool
            if not core.retro_unserialize(ct.create_string_buffer(raw), len(raw)):
                raise ValueError('incompatible cartridge core or roof state')
            core.retro_serialize_size.restype = ct.c_size_t
            core.retro_serialize.argtypes = [ct.c_void_p, ct.c_size_t]
            core.retro_serialize.restype = ct.c_bool
        if frame-1 in wanted:
            size = core.retro_serialize_size()
            buf = ct.create_string_buffer(size)
            if not core.retro_serialize(buf, size):
                raise RuntimeError('cartridge state capture failed')
            (args.captures/f'{route}{frame-1}.z').write_bytes(zlib.compress(buf.raw, 1))
    sys.argv = ['capture', '--core', str(args.core), '--system', str(args.system),
                '--cue', str(args.rom), '--output', str(args.captures/route),
                '--frames', str(max(wanted)+2), '--script-only', '--no-audio-file',
                '--event', f'70:right:{max(wanted)-68}']
    if route == 'slash':
        sys.argv += ['--event', '28:b:1', '--event', '115:b:1']
    harness.main(before_frame)


def build(captures, roof):
    atlas = bytearray()
    tiles = {}
    packets = []

    def pattern(state, value, count):
        src = (value & 2047) * 32
        block = state.vram[src:src + count * 32]
        if block not in tiles:
            tiles[block] = len(atlas) // 32
            atlas.extend(block)
        return (value & 0xf800) | tiles[block]

    def frame(state, lo, hi, x, y):
        parts = [(px - x, py - y, pattern(state, attr, w*h), (w-1)*4+h-1)
                 for px, py, w, h, attr in state.sat if py > 30 and lo <= attr & 2047 <= hi]
        assert parts
        packets.append(parts)

    def replay(name, n):
        return State(captures / f'{name}{n}.z')

    for f in (30, 33, 37, 41):
        frame(replay('slash', f), 0, 0x17f, 56, 192)
    for f in (12201, 12204, 12210, 12213):
        s = State(roof / f's{f}.z')
        body = [p for p in s.sat if p[1] > 30 and p[4] & 2047 < 0x180]
        frame(s, 0, 0x17f, body[0][0] + 16, body[0][1] + 48)
    for f, x in ((124,104), (128,96), (138,76)):
        frame(replay('hurt', f), 0x130, 0x17f, x, 192)
    frame(replay('slash', 37), 0x1b4, 0x1bc, 54, 192)
    for f in (125, 128, 132, 136, 140):
        frame(replay('slash', f), 0x7ac, 0x7df, 117, 192)

    # The charge advances by two pixels per frame, including the tapered tip.
    # Pull the two rows for every charge state, keeping the original HUD tiles.
    bars = []
    for f in range(38, 81):
        s = replay('slash', f)
        window = s.reg[3] * 512
        cells = [pattern(s, s.words[window + 32*row + col], 1)
                 for row in (2, 3) for col in range(5, 16)]
        bars.append(cells)

    count = len(atlas) // 32
    base = 0xa000 // 32 - count
    meta = bytearray()
    offsets = []
    for parts in packets:
        offsets.append(2*len(packets)+len(meta))
        meta.extend(words([len(parts)]))
        for x, y, attr, shape in parts:
            meta.extend(struct.pack('>hhHH', x, y, attr+base, shape))
    # Leave every resident sprite/HUD index unchanged. These two HP patterns
    # are transferred to the two slots just below the shared bank.
    hp_source = replay('hurt', 124)
    hp_tiles = hp_source.vram[0x5c7*32:0x5c9*32]
    return (words([base,count]) + atlas + words([len(packets)+len(meta)//2]) + words(offsets) + meta +
            b''.join(words([a+base for a in row]) for row in bars) + hp_tiles)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures',type=Path)
    parser.add_argument('roof',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'game/res/gfx/city_combat.bin')
    for key in ('core','system','rom'):
        parser.add_argument('--'+key,type=Path,help='Replay the original roof state to regenerate captures')
    args = parser.parse_args()
    if any((args.core,args.system,args.rom)):
        if not all((args.core,args.system,args.rom)):
            parser.error('--core, --system and --rom are required together')
        for route in ('slash','hurt'):
            capture(args, route)
    blob = build(args.captures, args.roof)
    args.output.write_bytes(blob)
    base, count = struct.unpack_from('>HH', blob)
    print(f'{count} patterns at VRAM tile {base}, {len(blob)} bytes')
