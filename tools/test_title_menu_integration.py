#!/usr/bin/env python3
"""Exercise title selections and persistent CONTINUE using an isolated BRAM.

Requires a built disc, a compatible libretro core, and a system directory
with the user's BIOS. No BIOS, game disc, or savedata is distributed here.
The output directory must not already exist; screenshots and isolated BRAM
are left there for inspection.
"""
import argparse
import shutil
import subprocess
import sys
import wave
from array import array
from pathlib import Path

from compare_title_capture import read_rgb_png


HARNESS = Path(__file__).resolve().with_name('test_megacd_libretro.py')


def crc16_ccitt(data):
    """CRC-16/CCITT-FALSE, used to verify the on-disc save record."""
    crc = 0xffff
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    return crc


def save_records(data):
    """Locate valid legacy and current payloads without changing backup RAM."""
    result = []
    for i in range(len(data) - 13):
        if data[i:i + 3] != b'V3S':
            continue
        if data[i + 3] == 1 and data[i + 5] == (data[i + 4] ^ 0xa5):
            result.append((i, 1))
        elif data[i + 3] == 2 and crc16_ccitt(data[i:i + 12]) == int.from_bytes(data[i + 12:i + 14], 'big'):
            result.append((i, 2))
    return result


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print('PASS:', label, flush=True)


def image(path):
    width, height, pixels = read_rgb_png(path)
    check((width, height) == (256, 224), '%s dimensions' % path.name)
    return pixels


def crop(pixels, x0, y0, x1, y1):
    return b''.join(pixels[(y * 256 + x0) * 3:(y * 256 + x1) * 3]
                    for y in range(y0, y1))


def scene_anchors(pixels):
    """Stable map bands; exclude moving enemies/player and live HP icons."""
    return (crop(pixels, 0, 0, 208, 24) +
            crop(pixels, 0, 200, 256, 224))


def same_scene_background(actual, reference, label):
    check(scene_anchors(actual) == scene_anchors(reference), label)


def audio_peak(path, first_second, seconds=1):
    with wave.open(str(path), 'rb') as wav:
        check(wav.getnchannels() == 2 and wav.getsampwidth() == 2,
              'captured audio is stereo 16-bit PCM')
        wav.setpos(first_second * wav.getframerate())
        samples = array('h')
        samples.frombytes(wav.readframes(seconds * wav.getframerate()))
        return max((abs(x) for x in samples), default=0)


def run_case(args, name, save_dir, events, captures, frames, cue=None):
    out = args.output / name
    command = [sys.executable, str(HARNESS), '--core', str(args.core),
               '--system', str(args.system), '--cue', str(cue or args.cue),
               '--output', str(out), '--save-dir', str(save_dir),
               '--frames', str(frames), '--script-only']
    for event in events:
        command.extend(('--event', event))
    for frame in captures:
        command.extend(('--capture', str(frame)))
    result = subprocess.run(command, text=True, capture_output=True)
    (args.output / (name + '.log')).write_text(
        result.stdout + '\n' + result.stderr, encoding='utf-8')
    check(result.returncode == 0, '%s ran successfully' % name)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--system', required=True, type=Path)
    parser.add_argument('--cue', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--all-scenes', action='store_true',
                        help='independently select and compare all eleven scenes')
    parser.add_argument('--scene-reference-dir', type=Path,
                        help='optional previous build/test-title directory for scene comparison')
    parser.add_argument('--title-reference', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'game/res/gfx/title_reference.png',
                        help='quantized RGB title reference for logo and copyright checks')
    parser.add_argument('--legacy-cue', type=Path,
                        help='optional previous v1-save ISO for an actual migration test')
    args = parser.parse_args()
    for name in ('core', 'system', 'cue', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    if args.output.exists():
        parser.error('output directory must not already exist: %s' % args.output)
    args.output.mkdir(parents=True)
    save = args.output / 'isolated-save'
    first = run_case(args, 'first', save,
        ['600:start:4', '2250:down:4', '2320:start:4', '2450:up:4', '2470:right:4',
         '2500:right:4', '2520:right:4', '2550:left:4', '2570:right:4', '2600:start:4',
         '3100:start:4', '3450:down:4', '3500:start:4'],
        [2200, 2299, 2399, 2540, 2560, 2590, 2899, 3399, 3499, 3799], 3900)
    frames = {frame: image(first / ('frame_%04d.png' % frame))
              for frame in (2200, 2299, 2399, 2540, 2560, 2590, 2899, 3399, 3499, 3799)}
    logo = lambda pixels: crop(pixels, 0, 32, 256, 140)
    cursor = lambda pixels: crop(pixels, 56, 144, 88, 192)
    check(logo(frames[2200]) == logo(frames[2299]) == logo(frames[2399]),
          'no-save confirmation remains on the logo screen')
    check(cursor(frames[2200]) != cursor(frames[2299]),
          'DOWN changes the menu cursor')
    check(frames[2299] == frames[2399], 'CONTINUE without save leaves the menu unchanged')
    check(frames[2200] != frames[2540], 'RIGHT changes the scene selection')
    check(frames[2540] != frames[2560] and frames[2540] == frames[2590],
          'LEFT and RIGHT select and restore the previous scene choice')
    check(frames[2899] != frames[2540], 'START enters the selected scene')
    check(logo(frames[3399]) == logo(frames[2200]), 'START returns from scene to title')
    same_scene_background(frames[3799], frames[2899],
                          'CONTINUE restores the selected scene background in session')
    check(audio_peak(first / 'audio.wav', 25) > 0, 'title audio is present')
    check(audio_peak(first / 'audio.wav', 48) > 0,
          'selected scene plays its original CD-DA music')

    second = run_case(args, 'reboot', save,
        ['600:start:4', '2250:down:4', '2320:start:4',
         '2700:start:4', '3100:start:4', '3150:start:4'],
        [2200, 2299, 2600, 2999, 3399, 4000], 4200)
    reboot_menu = image(second / 'frame_2200.png')
    check(crop(frames[2200], 160, 176, 240, 184) !=
          crop(reboot_menu, 160, 176, 240, 184),
          'NO SAVE indicator disappears when a valid save exists')
    same_scene_background(image(second / 'frame_2600.png'), frames[2899],
                          'CONTINUE restores the selected scene after core reload')
    first_scene = image(second / 'frame_4000.png')
    check(first_scene != frames[2899], 'START can choose a different scene after reload')
    rewritten = run_case(args, 'rewritten', save,
        ['600:start:4', '2250:down:4', '2320:start:4'], [2600], 2700)
    # CITY deliberately starts with the PCE prologue on START but CONTINUE
    # returns the saved street spawn.  Verify that CONTINUE follows the newly
    # selected scene instead of comparing two different CITY entry points.
    check(image(rewritten / 'frame_2600.png') != image(second / 'frame_2600.png'),
          'CONTINUE leaves the previously restored scene')
    rewritten_bram = (save / 'scd_U.brm').read_bytes()
    check(any(version == 2 and rewritten_bram[o + 4] == 2 and
              not rewritten_bram[o + 5] & 1
              for o, version in save_records(rewritten_bram)),
          'CONTINUE follows the updated CITY selection')

    bram = save / 'scd_U.brm'
    check(bram.is_file(), 'isolated Sega CD backup RAM was saved')
    data = bytearray(bram.read_bytes())
    records = save_records(data)
    check(1 <= len(records) <= 2, 'one or two valid project save payloads were found')
    check(any(version == 2 for _, version in records), 'new saves use the position-aware format')
    positioned = [(o, v) for o, v in records
                  if v == 2 and data[o + 5] & 1]
    check(bool(positioned), 'BRAM has a CRC-valid scene position checkpoint')
    if positioned:
        newest = positioned[0]
        for candidate in positioned[1:]:
            old_seq = int.from_bytes(data[newest[0] + 10:newest[0] + 12], 'big')
            new_seq = int.from_bytes(data[candidate[0] + 10:candidate[0] + 12], 'big')
            delta = (new_seq - old_seq) & 0xffff
            if 0 < delta < 0x8000:
                newest = candidate
        offset = newest[0]
        check(data[offset + 4] == 4 and
              int.from_bytes(data[offset + 6:offset + 8], 'big') == 32 and
              int.from_bytes(data[offset + 8:offset + 10], 'big') == 128,
              'CONTINUE checkpoint stores Stage 2B spawn and position')
    current = [offset for offset, version in records if version == 2]
    if len(current) == 2:
        # Sequence numbers wrap modulo 65536. Here the records result from a
        # few consecutive writes, so their signed modular difference decides
        # which is newer without relying on filesystem ordering.
        a, b = current
        seq_a = int.from_bytes(data[a + 10:a + 12], 'big')
        seq_b = int.from_bytes(data[b + 10:b + 12], 'big')
        delta = (seq_a - seq_b) & 0xffff
        newer, older = (a, b) if 0 < delta < 0x8000 else (b, a)
        check(data[older + 4] != data[newer + 4],
              'fallback fixture contains two different saved scenes')
        fallback_data = bytearray(data)
        fallback_data[newer + 12] ^= 1
        fallback = args.output / 'fallback-save'
        fallback.mkdir()
        (fallback / 'scd_U.brm').write_bytes(fallback_data)
        cart = save / '4Mbit_cart.brm'
        if cart.exists():
            shutil.copyfile(cart, fallback / cart.name)
        old = run_case(args, 'fallback', fallback,
                       ['600:start:4', '2250:down:4', '2320:start:4'], [2600], 2700)
        same_scene_background(image(old / 'frame_2600.png'), frames[2899],
                              'CONTINUE falls back after checksum corruption')
        check((fallback / 'scd_U.brm').read_bytes() == fallback_data,
              'reading the fallback does not rewrite the damaged slot')
    # Both slots must be corrupt to exercise the no-valid-save path. Mutate
    # only checksums, leaving filesystem metadata and record bodies intact.
    for offset, version in records:
        data[offset + (5 if version == 1 else 12)] ^= 1
    corrupted_bytes = bytes(data)
    corrupt = args.output / 'corrupt-save'
    corrupt.mkdir()
    (corrupt / 'scd_U.brm').write_bytes(data)
    cart = save / '4Mbit_cart.brm'
    if cart.exists():
        shutil.copyfile(cart, corrupt / cart.name)
    third = run_case(args, 'corrupt', corrupt,
        ['600:start:4', '2250:down:4', '2320:start:4', '2450:up:4',
         '2480:right:4', '2500:start:4', '2600:start:4', '3100:start:4'],
        [2200, 2299, 2399, 2550, 2899, 3399], 3500)
    corrupt_menu = image(third / 'frame_2299.png')
    corrupt_result = image(third / 'frame_2399.png')
    check(logo(corrupt_result) == logo(frames[2200]), 'corrupt save stays on title')
    check(corrupt_menu == corrupt_result, 'corrupt save cannot enter a scene')
    check(crop(corrupt_result, 160, 176, 240, 184) ==
          crop(frames[2399], 160, 176, 240, 184),
          'corrupt save displays the no-save indicator')
    error = image(third / 'frame_2550.png')
    check(logo(error) == logo(frames[2200]) and
          crop(error, 160, 176, 240, 184) != crop(frames[2200], 160, 176, 240, 184),
          'failed save shows feedback and remains at title')
    check(image(third / 'frame_2899.png') != frames[2200],
          'a second START allows playing without replacing a corrupt save')
    after = image(third / 'frame_3399.png')
    check(crop(after, 160, 176, 240, 184) == crop(error, 160, 176, 240, 184),
          'returning after failed position save still shows SAVE ERR')
    actual_bram = (corrupt / 'scd_U.brm').read_bytes()
    # The libretro core normalizes the 16-byte BRAM header on exit; the record
    # area (the part the game could write) must stay byte-for-byte intact.
    check(actual_bram[16:] == corrupted_bytes[16:],
          'failed write preserved the incompatible BRAM record area')

    reference = image(args.title_reference)
    core_reference = bytearray(len(reference))
    for i, value in enumerate(reference):
        level = (value * 7 + 127) // 255
        core_reference[i] = (((level * 34) >> 2) * 255 // 63 if i % 3 == 1
                             else ((level * 34) >> 3) * 255 // 31)
    check(crop(frames[2200], 0, 32, 256, 144) == crop(core_reference, 0, 32, 256, 144),
          'emulated logo matches the quantized original pixel-for-pixel')
    check(crop(frames[2200], 0, 190, 256, 211) == crop(core_reference, 0, 190, 256, 211),
          'emulated copyright matches the quantized original pixel-for-pixel')

    if args.all_scenes:
        reference_names = (None, 'none', 'up', 'left', 'down', 'right', None, None, None, None, None)
        results = []
        for index, reference_name in enumerate(reference_names):
            events = ['600:start:4']
            events.extend('%d:right:4' % (2300 + 20 * i) for i in range(index))
            events.append('2520:start:4')
            case = run_case(args, 'scene%d' % (index + 1),
                            args.output / ('scene%d-save' % (index + 1)),
                            events, [2659], 2700)
            scene = image(case / 'frame_2659.png')
            results.append(scene)
            if args.scene_reference_dir and reference_name:
                old = args.scene_reference_dir / reference_name / 'frame_2699.png'
                same_scene_background(scene, image(old),
                                      'scene %d background matches the prior reference' % (index + 1))
        check(len(set(results)) == len(reference_names), 'all eleven scene selectors show distinct scenes')

    if args.legacy_cue:
        # Produce v1 with the previous program itself instead of fabricating
        # BIOS directory entries. Then reboot into the new disc and save a
        # real checkpoint, checking that migration uses the other slot.
        old_cue = args.legacy_cue.resolve()
        if not old_cue.is_file():
            raise ValueError('legacy CUE not found: %s' % old_cue)
        legacy_save = args.output / 'legacy-save'
        run_case(args, 'legacy-create', legacy_save,
                 ['600:start:4', '2250:start:4'], [2450], 2500, cue=old_cue)
        legacy_bram = legacy_save / 'scd_U.brm'
        before = legacy_bram.read_bytes()
        old_records = [(o, v) for o, v in save_records(before) if v == 1]
        check(len(old_records) == 1, 'previous ISO created one valid legacy v1 record')
        original_offset = old_records[0][0]
        legacy_scene = before[original_offset + 4]
        legacy = run_case(args, 'legacy-migrate', legacy_save,
                          ['600:start:4', '2200:down:4', '2240:start:4', '2600:start:4'],
                          [2499, 2799], 2850)
        check(image(legacy / 'frame_2499.png') != image(legacy / 'frame_2799.png'),
              'CONTINUE opens legacy scene and START returns to menu')
        after = legacy_bram.read_bytes()
        new_records = save_records(after)
        check(after[original_offset:original_offset + 64] ==
              before[original_offset:original_offset + 64],
              'legacy record was preserved byte-for-byte during migration')
        check(any(v == 2 and after[o + 4] == legacy_scene and after[o + 5] & 1
                  for o, v in new_records),
              'exiting legacy scene created a valid position-aware record in another slot')
    print('All menu integration checks passed; evidence:', args.output)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError) as exc:
        print('FAIL:', exc, file=sys.stderr)
        raise SystemExit(1)
