"""Create checkpoints with the previous local disc, then load them on the integrated disc."""
import argparse
import struct
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageChops

from test_stage_physics_integration import run_case
from test_title_menu_integration import save_records


def checkpoints(directory):
    data = (directory / 'scd_U.brm').read_bytes()
    return {struct.unpack_from('>4H', data, offset + 4)
            for offset, version in save_records(data) if version == 2 and data[offset + 5] == 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('core', 'system', 'previous', 'cue', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    new = SimpleNamespace(**vars(args))
    old = SimpleNamespace(**vars(args))
    old.cue = args.previous
    for index, scene in enumerate((3, 7, 4, 6, 5, 8, 9, 10, 11, 12)):
        saves = args.output / ('save-%d' % scene)
        original = old if index < 8 else new
        start = ['600:start:4'] + ['%d:right:4' % (2050 + 20 * i) for i in range(index)]
        start += ['2300:start:4', '2480:right:12', '2540:start:4']
        first = run_case(original, 'write-%d' % scene, saves, start, [2479, 2539], 2660)
        records = checkpoints(saves)
        assert len(records) == 1, (scene, records)
        tag, x, y, seq = records.pop()
        assert tag == (scene << 8 | 1), (scene, tag)
        # Both new windows have a fixed path at y=96 and start at x=0.
        if index >= 8:
            assert (x, y) == (24, 96), (scene, x, y)
        resumed = run_case(new, 'resume-%d' % scene, saves,
                           ['600:start:4', '2210:down:4', '2250:start:4', '2495:start:4'],
                           [2494], 2620)
        assert (tag, x, y, (seq + 1) & 0xffff) in checkpoints(saves), (scene, x, y)
        # Verify the loaded module, independently of the BRAM record. Actors
        # can be at different patrol/animation frames while the map stays put.
        with Image.open(first / 'frame_2539.png') as a, Image.open(resumed / 'frame_2494.png') as b:
            difference = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
            same = sum(n for n, rgb in difference.getcolors(a.width * a.height) if rgb == (0, 0, 0))
            assert len(a.convert('RGB').getcolors(a.width * a.height)) > 8
            assert same >= 0.95 * a.width * a.height, (scene, same)
        print('PASS: scene %d reopened at (%d,%d) with valid BRAM' % (scene, x, y), flush=True)


if __name__ == '__main__':
    main()
