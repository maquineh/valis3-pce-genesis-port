"""Pack captured PCE RGB565 frames into timed H32 palette, tile and map updates.

Input records are zlib-compressed <width,height,pitch,format> (four little-endian
words) followed by the libretro framebuffer. Requires NumPy and python-lz4.
"""
import argparse
from pathlib import Path
import struct
import zlib

import lz4.block
import numpy as np

# RGB565 samples from Beetle PCE Fast, rounded to the nearest MD DAC level.
RGB = np.arange(65536, dtype=np.int32)
DAC = ((RGB >> 11) * 7 + 15) // 31 | (((RGB >> 5 & 63) * 7 + 31) // 63 << 3) | (((RGB & 31) * 7 + 15) // 31 << 6)
BLACK = bytes(32)
BLOCK = 4096
SLOTS = 1280


def source_cells(path):
    data = zlib.decompress(path.read_bytes())
    width, height, pitch, fmt = struct.unpack_from('<4H', data)
    if (width, height, fmt) != (256, 243, 2):
        raise ValueError(f'{path}: expected the 256x243 RGB565 PCE viewport')
    raw = np.frombuffer(data, '<u2', offset=8).reshape(height, pitch // 2)
    # Align to the original artwork's 8-pixel grid (the active raster starts at 3).
    screen = DAC[raw[11:235, :256]]
    return screen.reshape(28, 8, 32, 8).transpose(0, 2, 1, 3).reshape(896, 64)


def palettes(cells):
    colors = np.unique(cells)
    groups = [set(colors) - {0}]
    if len(groups[0]) > 15:
        # A mask identifies all colours used by one hardware tile.
        powers = np.zeros(512, dtype=np.uint64)
        if len(colors) > 63:
            raise ValueError('unexpected cinematic palette')
        powers[colors] = np.left_shift(np.uint64(1), np.arange(len(colors), dtype=np.uint64))
        powers[0] = 0
        masks = np.unique(np.bitwise_or.reduce(powers[cells], axis=1))
        groups = []
        for mask in sorted(map(int, masks), key=lambda m: (-m.bit_count(), m)):
            used = {color for i, color in enumerate(colors) if mask & (1 << i)}
            fits = [g for g in groups if len(g | used) <= 15]
            if fits:
                min(fits, key=lambda g: len(used - g)).update(used)
            elif len(groups) < 4:
                groups.append(used)
            # Rare composite tiles can span several PCE palettes. Keep common
            # colours and select the nearest DAC colour per pixel below.
    palette = np.zeros((4, 16), dtype=np.int32)
    for line, group in enumerate(groups):
        ordered = sorted(group)
        if len(ordered) > 15:
            counts = np.bincount(cells.ravel(), minlength=512)
            ordered = sorted(sorted(ordered, key=lambda c: -counts[c])[:15])
        palette[line, 1:1+len(ordered)] = ordered
    return palette


def convert(cells, palette):
    colors = np.arange(512)
    diff = np.zeros((4, 512, 16), dtype=np.int32)
    for shift, weight in ((0, 2), (3, 3), (6, 1)):
        diff += weight * (((colors >> shift & 7)[None, :, None] -
                           (palette >> shift & 7)[:, None, :]) ** 2)
    nearest = diff.argmin(axis=2)
    cost = diff.min(axis=2)
    lines = cost[:, cells].sum(axis=2).argmin(axis=0)
    idx = nearest[lines[:, None], cells]
    tiles = (idx[:, ::2] * 16 + idx[:, 1::2]).astype('u1')
    return lines, tiles, np.count_nonzero(cost[lines[:, None], cells])


def spans(indices):
    if not len(indices):
        return
    start = prev = int(indices[0])
    for i in indices[1:]:
        i = int(i)
        if i != prev + 1:
            yield start, prev + 1
            start = i
        prev = i
    yield start, prev + 1


def blocks(commands, history):
    raw = bytearray()
    result = []
    def flush():
        if len(history) + len(raw) > 48128:
            del history[:-16384]
        compressed = lz4.block.compress(raw, mode='high_compression', compression=10, store_size=False, dict=bytes(history))
        history.extend(raw)
        result.append(struct.pack('>HH', len(compressed), len(raw)) + compressed + bytes(len(compressed) % 2))
        raw.clear()
    for address, payload in commands:
        while payload:
            if len(raw) >= BLOCK - 4:
                flush()
            take = min(len(payload), BLOCK - len(raw) - 4)
            raw.extend(struct.pack('>HH', address, take // 2))
            raw.extend(payload[:take])
            payload = payload[take:]
            if address == 0xffff and payload:
                raise ValueError('palette must be first in its block')
            address += take
    if raw:
        flush()
    return result


def pack(directory, start, stop, step, disc_track, output):
    slot_data = [None] * SLOTS
    slot_data[0] = BLACK
    slots = {BLACK: 0}
    cursor = 1
    prev_map = np.zeros(896, dtype=np.uint16)
    prev_palette = prev_cells = None
    events = []
    history = bytearray()
    worst_error = 0
    for tick in range(start, stop, step):
        cells = source_cells(directory / f'{tick:05}.z')
        if np.array_equal(cells, prev_cells):
            continue
        prev_cells = cells
        palette = palettes(cells)
        lines, tiles, error = convert(cells, palette)
        worst_error = max(worst_error, error)
        commands = []
        if not np.array_equal(palette, prev_palette):
            cram = (palette & 7) * 2 + (palette >> 3 & 7) * 32 + (palette >> 6) * 512
            commands.append((0xffff, cram.astype('>u2').tobytes()))
            prev_palette = palette
        patterns = [tile.tobytes() for tile in tiles]
        needed = dict.fromkeys(patterns)
        dirty = []
        for pattern in needed:
            if pattern in slots:
                continue
            while slot_data[cursor] in needed:
                cursor = 1 + cursor % (SLOTS - 1)
            old = slot_data[cursor]
            if old is not None:
                del slots[old]
            slot_data[cursor] = pattern
            slots[pattern] = cursor
            dirty.append(cursor)
            cursor = 1 + cursor % (SLOTS - 1)
        for a, b in spans(sorted(dirty)):
            commands.append((a * 32, b''.join(slot_data[a:b])))
        tilemap = (lines << 13) | [slots[tile] for tile in patterns]
        for a, b in spans(np.flatnonzero(tilemap != prev_map)):
            commands.append((0xc000 + 2*a, tilemap[a:b].astype('>u2').tobytes()))
        prev_map = tilemap
        if commands:
            chunks = blocks(commands, history)
            events.append(struct.pack('>HH', tick - start, len(chunks)) + b''.join(chunks))
    events.append(struct.pack('>HH', stop - start, 0))
    # The first page follows the player in Word RAM. Prefetch all further pages
    # in the Sub CPU's three free program RAM banks before starting the CD-DA.
    # Between pages only RAM changes hands. The drive keeps playing the voices.
    pages = [bytearray()]
    for record in events:
        if len(pages[-1]) + len(record) + 10 > (0x3e000 if len(pages) == 1 else 60000):
            pages[-1].extend(struct.pack('>HH', 0, 0xffff))
            pages.append(bytearray())
        pages[-1].extend(record)
    primary = struct.pack('>HHH', disc_track, stop - start, len(pages)-1) + pages[0]
    extra = b''.join(struct.pack('>H', len(page)//2) + page for page in pages[1:])
    if len(primary) > 0x3e000 or len(extra) > 0x60000:
        raise ValueError('clip exceeds the reserved Mega CD RAM')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(primary)
    tail = output.with_suffix('.ext')
    if extra:
        tail.write_bytes(extra)
    elif tail.exists():
        tail.unlink()
    print(f'{output.name}: {len(events)-1} updates, {len(primary)+len(extra)} bytes, '
          f'max {worst_error} remapped pixels/frame', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path)
    ap.add_argument('start', type=int)
    ap.add_argument('stop', type=int)
    ap.add_argument('disc_track', type=int)
    ap.add_argument('output', type=Path)
    ap.add_argument('--step', type=int, default=6)
    args = ap.parse_args()
    pack(args.directory, args.start, args.stop, args.step, args.disc_track, args.output)
