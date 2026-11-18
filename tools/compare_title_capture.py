#!/usr/bin/env python3
"""Compare a libretro screenshot with the quantized Mega Drive title reference.

Both inputs must be non-interlaced, 8-bit RGB PNGs. The screenshot written by
test_megacd_libretro.py has this format. Genesis Plus GX's RGB565 output maps
the hardware's 0..14 channel levels to a maximum of 238, whereas the quantized
reference expands its 3-bit levels to 0..255. The optional core-specific mode
models that conversion before comparing, without relaxing pixel positions.
"""
import argparse
import struct
import zlib
from pathlib import Path


def read_rgb_png(path):
    data = Path(path).read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG: %s' % path)
    offset, chunks, header, ended = 8, [], None, False
    while offset + 12 <= len(data):
        size = int.from_bytes(data[offset:offset + 4], 'big')
        tag = data[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(data):
            raise ValueError('truncated PNG chunk')
        content = data[offset + 8:offset + 8 + size]
        if zlib.crc32(tag + content) != int.from_bytes(data[end - 4:end], 'big'):
            raise ValueError('invalid PNG chunk CRC')
        if tag == b'IHDR':
            header = struct.unpack('>IIBBBBB', content)
        elif tag == b'IDAT':
            chunks.append(content)
        elif tag == b'IEND':
            ended = True
            break
        offset = end
    if not header or not chunks or not ended:
        raise ValueError('PNG missing IHDR, IDAT or IEND')
    width, height, depth, color, compression, filtering, interlace = header
    if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
        raise ValueError('expected non-interlaced 8-bit RGB PNG')
    raw = zlib.decompress(b''.join(chunks))
    stride = width * 3
    if len(raw) != height * (stride + 1):
        raise ValueError('unexpected decompressed PNG size')
    output = bytearray()
    previous = bytes(stride)
    for y in range(height):
        start = y * (stride + 1)
        mode = raw[start]
        if mode > 4:
            raise ValueError('unsupported PNG filter %d' % mode)
        row = bytearray(raw[start + 1:start + 1 + stride])
        for x in range(stride):
            left = row[x - 3] if x >= 3 else 0
            above = previous[x]
            upper_left = previous[x - 3] if x >= 3 else 0
            if mode == 1:
                predictor = left
            elif mode == 2:
                predictor = above
            elif mode == 3:
                predictor = (left + above) // 2
            elif mode == 4:
                p = left + above - upper_left
                distances = (abs(p - left), abs(p - above), abs(p - upper_left))
                predictor = (left, above, upper_left)[distances.index(min(distances))]
            else:
                predictor = 0
            row[x] = (row[x] + predictor) & 255
        output.extend(row)
        previous = row
    return width, height, bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('screenshot', type=Path)
    parser.add_argument('--tolerance', type=int, default=1,
                        help='maximum allowed per-channel difference (default: 1)')
    parser.add_argument('--genesis-plus-gx-rgb565', action='store_true',
                        help='model Genesis Plus GX RGB565 color expansion')
    args = parser.parse_args()
    if not 0 <= args.tolerance <= 255:
        parser.error('tolerance must be in 0..255')
    rw, rh, reference = read_rgb_png(args.reference)
    sw, sh, screenshot = read_rgb_png(args.screenshot)
    if (rw, rh) != (256, 224) or (sw, sh) != (rw, rh):
        print('FAIL: dimensions reference %dx%d, screenshot %dx%d; expected 256x224' %
              (rw, rh, sw, sh))
        return 1
    if args.genesis_plus_gx_rgb565:
        converted = bytearray(len(reference))
        for i, value in enumerate(reference):
            level = (value * 7 + 127) // 255
            converted[i] = (((level * 34) >> 2) * 255 // 63 if i % 3 == 1
                            else ((level * 34) >> 3) * 255 // 31)
        reference = converted
    differences = [abs(a - b) for a, b in zip(reference, screenshot)]
    mismatches = sum(any(v > args.tolerance for v in differences[i:i + 3])
                     for i in range(0, len(differences), 3))
    print('%s: %d/%d pixels exceed tolerance %d; maximum channel difference %d; mean %.6f' %
          ('PASS' if not mismatches else 'FAIL', mismatches, rw * rh, args.tolerance,
           max(differences), sum(differences) / len(differences)))
    return 1 if mismatches else 0


if __name__ == '__main__':
    raise SystemExit(main())
