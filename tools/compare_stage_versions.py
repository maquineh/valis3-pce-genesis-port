"""Compare detailed 8x8 patterns in PCE stage BATs and native Genesis captures.

Usage: py -3 tools/compare_stage_versions.py GENESIS_REFERENCE_DIR OUTPUT.csv
The reference directory contains mapN/frame_NNNN.png images from the cartridge.
"""
import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image

from extract_state import find_var, load
from pack_stage_state import ROOT, STEM
import render_pce_state as render


def patterns(image, search_offsets):
    rgb = np.asarray(image.convert('RGB'), dtype=np.int32)
    pixels = (rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]
    result = set()
    positions = range(8 if search_offsets else 1)
    for dy in positions:
        for dx in positions:
            region = pixels[dy:, dx:]
            h, w = (n // 8 * 8 for n in region.shape)
            tiles = region[:h, :w].reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 8)
            vertical = (tiles[:, 1:] != tiles[:, :-1]).sum((1, 2))
            horizontal = (tiles[:, :, 1:] != tiles[:, :, :-1]).sum((1, 2))
            for tile in np.unique(tiles[(vertical >= 10) & (horizontal >= 10)].reshape(-1, 64), axis=0):
                colors, first, indices = np.unique(tile, return_index=True, return_inverse=True)
                if len(colors) >= 4:
                    result.add(first[indices].astype('uint8').tobytes())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('genesis', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = {}
    render.WIDTH = render.HEIGHT = 512
    states = sorted([*ROOT.glob(STEM + '.mc?'), *(ROOT / 'states').glob('*.mc?')])
    for path in states:
        raw = load(path)
        cram = find_var(raw, b'color_table')
        if path.name.endswith('.stg1a.mc1'):
            cram = (ROOT / 'build/stg_extract/STG1A_pal.bin').read_bytes()[0x64:0x264]
        block = find_var(raw, b'CDRAM')[0xa000:0xa005].decode('ascii')
        bg, _ = render.render_background(find_var(raw, b'VRAM'), render.palette_colors(cram), 0, 0)
        source[(block, path.relative_to(ROOT).as_posix())] = patterns(bg, False)
    rows = []
    folders = sorted((p for p in args.genesis.glob('map*') if p.name[3:].isdigit()),
                     key=lambda p: int(p.name[3:]))
    if not folders:
        parser.error('no numbered cartridge map captures found')
    for folder in folders:
        # Use the same elapsed gameplay frame for each batch of original captures.
        captures = sorted(folder.glob('frame_*.png'))
        path = captures[-2] if len(captures) > 1 else captures[0]
        with Image.open(path) as im:
            if im.size != (256, 224):
                raise ValueError('expected native 256x224 image: ' + str(path))
            target = patterns(im.crop((0, 40, 256, 224)), True)
        for (block, state), tiles in source.items():
            rows.append([block, state, folder.name, path.name, len(tiles), len(tiles & target)])
    with args.output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['pce_block', 'pce_state', 'genesis_map', 'genesis_frame',
                         'distinct_detailed_pce_tiles', 'matched_tile_shapes'])
        writer.writerows(rows)


if __name__ == '__main__':
    main()
