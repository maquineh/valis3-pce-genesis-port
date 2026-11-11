"""Build the real absolute TOC for the retail Valis III disc.

The retail cue is a per-track-file cue: every track lives in its own .bin and
tracks 2, 6, 8, ... carry an INDEX 00 pregap at the start of the file.  The
absolute position of a track file is the sum of all previous track lengths;
disc file sector 0 is MSF 00:00:00, i.e. absolute LBA -150.
"""

import os
import re

RETAIL = os.path.join('build', 'retail')
CUE = os.path.join(RETAIL, 'Valis III (Japan).cue')


def msf_bcd(lba):
    """Absolute LBA -> BCD min/sec/frame (LBA 0 == 00:02:00)."""
    f = lba + 150
    m, f = divmod(f, 75 * 60)
    s, f = divmod(f, 75)
    bcd = lambda v: ((v // 10) << 4) | (v % 10)
    return bytes([bcd(m), bcd(s), bcd(f)])


def parse_cue(path=CUE):
    tracks = []
    cur = None
    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.strip()
            m = re.match(r'FILE\s+"(.+)"\s+BINARY', line, re.I)
            if m:
                cur = {'file': m.group(1), 'index0': None, 'index1': None,
                       'mode': None}
                tracks.append(cur)
                continue
            m = re.match(r'TRACK\s+(\d+)\s+(\S+)', line, re.I)
            if m and cur is not None:
                cur['track'] = int(m.group(1))
                cur['mode'] = m.group(2).upper()
                continue
            m = re.match(r'INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)', line, re.I)
            if m and cur is not None:
                frames = int(m.group(2)) * 75 * 60 + int(m.group(3)) * 75 + int(m.group(4))
                if int(m.group(1)) == 0:
                    cur['index0'] = frames
                elif int(m.group(1)) == 1:
                    cur['index1'] = frames
    # absolute LBA of each track file start
    pos = 0
    for t in tracks:
        t['file_sector'] = pos
        t['lba0'] = pos - 150
        idx1 = t['index1'] if t['index1'] is not None else 0
        t['lba1'] = t['lba0'] + idx1
        path = os.path.join(RETAIL, t['file'])
        t['sectors'] = os.path.getsize(path) // 2352
        t['control'] = 0x04 if t['mode'] and t['mode'].startswith('MODE') else 0x00
        t['msf_bcd'] = msf_bcd(t['lba1'])
        pos += t['sectors']
    return tracks


TOC = parse_cue()
BY_TRACK = {t['track']: t for t in TOC}


def info(track):
    t = BY_TRACK[track]
    return bytes(list(t['msf_bcd']) + [t['control']])


if __name__ == '__main__':
    print('tracks:', len(TOC))
    for t in TOC:
        print('  %2d %-10s file=%-38s lba0=%6d lba1=%6d msf=%02X:%02X:%02X ctl=%02X' %
              (t['track'], t['mode'], t['file'][-34:], t['lba0'], t['lba1'],
               t['msf_bcd'][0], t['msf_bcd'][1], t['msf_bcd'][2], t['control']))
