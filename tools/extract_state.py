"""Extract a Mednafen PCE state (VRAM/CRAM/BAT/CDRAM/BaseRAM) by name.

The automatic sequential parser can misalign on some states; this tool finds
each section by its ASCII name and uses the known record layout:
    [len][name][type][size:u24 LE][data]
Size is in 256-byte blocks for arrays; scalars use type bytes.
"""
import gzip
import json
import os
import sys
from collections import Counter

OUT_DEFAULT = 'build/state_extract'
STG_NAMES = [b'STG1A', b'STG2A', b'STG2B', b'STG2C', b'STG3A',
             b'STG3B', b'STG4A', b'STG4B', b'STG4C', b'STG5A']


def load(path):
    raw = open(path, 'rb').read()
    return gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw


def find_var(d, name, occ=0):
    pos = -1
    for _ in range(occ + 1):
        pos = d.find(name, pos + 1)
        if pos < 0:
            return None
    ln = d[pos - 1]
    if ln != len(name):
        # fall back to the first occurrence with the right length
        pos2 = d.find(bytes([len(name)]) + name)
        if pos2 >= 0:
            pos = pos2 + 1
            ln = len(name)
    typ = d[pos + ln]
    s = d[pos + ln + 1:pos + ln + 4]
    size = s[0] | (s[1] << 8) | (s[2] << 16)
    n = size * 256 if typ == 0 else typ
    return d[pos + ln + 4:pos + ln + 4 + n]


def main():
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else OUT_DEFAULT
    os.makedirs(out, exist_ok=True)
    d = load(path)
    vram = find_var(d, b'VRAM')
    cram = find_var(d, b'color_table')
    cdr = find_var(d, b'CDRAM')
    base = find_var(d, b'BaseRAM')
    mpr = find_var(d, b'MPR')
    bgx = find_var(d, b'BG_XOffset')
    bgy = find_var(d, b'BG_YOffset')
    assert vram and cram and cdr, 'missing core sections'
    open(os.path.join(out, 'vram.bin'), 'wb').write(vram)
    open(os.path.join(out, 'cram.bin'), 'wb').write(cram)
    open(os.path.join(out, 'cdram.bin'), 'wb').write(cdr)
    if base:
        open(os.path.join(out, 'baseram.bin'), 'wb').write(base)
    open(os.path.join(out, 'bat.bin'), 'wb').write(vram[:0x2000])
    words = [vram[2 * i] | (vram[2 * i + 1] << 8) for i in range(0x1000)]
    bot = words[2048:4096]
    c = Counter(bot)
    stage = None
    for n in STG_NAMES:
        if cdr.find(n) >= 0:
            stage = n.decode()
            break
    info = {
        'source': path, 'stage_in_cdram_d': stage,
        'cdram_stg_offset': cdr.find(stage.encode()) if stage else None,
        'mpr': mpr.hex(' ') if mpr else None,
        'bg_x': int.from_bytes(bgx, 'little') if bgx else None,
        'bg_y': int.from_bytes(bgy, 'little') if bgy else None,
        'bat_unique_bottom': len(c),
        'bat_palettes': sorted({x >> 12 for x in bot}),
        'bat_top': [(hex(k), n) for k, n in c.most_common(12)],
    }
    json.dump(info, open(os.path.join(out, 'summary.json'), 'w'), indent=2)
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
