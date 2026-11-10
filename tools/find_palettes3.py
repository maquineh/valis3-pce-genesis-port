"""Locate VCE palette blocks on the disc.

A VCE colour word is 9 bits, so a palette block is a long run of 16-bit words
whose high byte is 0 or 1 and which uses many distinct values.  The palette
upload routine found at logical $8CD9 (file $2353D9) transfers exactly this
kind of block into the VCE colour port, so these offsets are the real
palettes - including the ones the stages need.
"""
import sys

TRACK = 'build/extracted/data/track_02.bin'
MIN_WORDS = 256


def main():
    b = open(TRACK, 'rb').read()
    print('scanning %s for VCE palette blocks (>= %d words)...'
          % (TRACK, MIN_WORDS))
    blocks = []
    off = 0
    n = len(b) - 2
    while off < n:
        # extend a run of valid VCE words
        end = off
        distinct = set()
        while end < n:
            hi = b[end + 1]
            if hi not in (0, 1):
                break
            distinct.add(b[end] | (hi << 8))
            end += 2
        words = (end - off) // 2
        if words >= MIN_WORDS and len(distinct) >= 32:
            blocks.append((off, words, len(distinct)))
            off = end
        else:
            off += 2

    # merge adjacent blocks separated by a small gap
    print('%d palette blocks found:' % len(blocks))
    for off, words, d in blocks:
        print('   $%06X  %5d words (%d bytes)  %d distinct colours  sector %d'
              % (off, words, words * 2, d, off // 2352))


if __name__ == '__main__':
    main()
