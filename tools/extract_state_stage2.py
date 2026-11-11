"""Extract the real Stage 2 snapshot (VRAM / CRAM / BAT) from the Mednafen state.

Layout decoded from the state:
    BaseRAM  @ 0x031029  8192 B   work RAM
    CDRAM    @ 0x045615 65536 B   CD-ROM2 code/data RAM (loaded at $100000)
    VRAM     @ 0x033B0C 65536 B   64 KiB video RAM (16-bit LE words)
    color_table @ 0x033260 1024 B  512 CRAM words (16-bit LE)
"""
import json
import os
import sys

sys.path.insert(0, 'tools')
from pce_state import decompress, parse

STATE = 'Valis III (Japan).dad575d3e6e26b145cc260e5858b8c48.mc0'
OUT = 'build/state_stage2'


def main():
    os.makedirs(OUT, exist_ok=True)
    v = parse(decompress(STATE))
    vram = v['VRAM'][2]
    cram = v['color_table'][2]
    bat = vram[:0x2000]          # 64x64 words at VRAM $0000
    cam = v['CDRAM'][2]
    open(os.path.join(OUT, 'vram.bin'), 'wb').write(vram)
    open(os.path.join(OUT, 'cram.bin'), 'wb').write(cram)
    open(os.path.join(OUT, 'bat.bin'), 'wb').write(bat)
    open(os.path.join(OUT, 'cdram.bin'), 'wb').write(cam)

    words = [bat[2 * i] | (bat[2 * i + 1] << 8) for i in range(len(bat) // 2)]
    used = sorted({w & 0xFFF for w in words})
    pals = sorted({(w >> 12) & 0xF for w in words})
    info = {
        'state': STATE,
        'vram_bytes': len(vram),
        'cram_words': len(cram) // 2,
        'bat_words': len(words),
        'bat_unique_tiles': len(used),
        'bat_tile_min': used[0] if used else None,
        'bat_tile_max': used[-1] if used else None,
        'bat_palettes': pals,
        'cdram_stg2a_offset': cam.find(b'STG2A'),
        'bg_x': int.from_bytes(v['BG_XOffset'][2], 'little'),
        'bg_y': int.from_bytes(v['BG_YOffset'][2], 'little'),
        'pc': v['PC'][2].hex(' '),
        'mpr': v['MPR'][2].hex(' '),
    }
    json.dump(info, open(os.path.join(OUT, 'summary.json'), 'w'), indent=2)
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
