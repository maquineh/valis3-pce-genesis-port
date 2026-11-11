"""Full multi-track disc reader for the retail Valis III cue/bin set.

Absolute LBAs are the drive's 24-bit sector addresses: disc file sector 0 is
MSF 00:00:00, i.e. LBA -150.  Each retail track file keeps its own INDEX 00
pregap, so a track's absolute base is the running sum of previous track
lengths minus 150.
"""

import os

from valis_toc import TOC, BY_TRACK, msf_bcd

RETAIL = os.path.join('build', 'retail')


class ValisDisc(object):
    def __init__(self, retail=RETAIL, tracks=TOC):
        self.retail = retail
        self.tracks = tracks
        self.reads = []
        self._fh = {}
        self.total_sectors = sum(t['sectors'] for t in tracks)

    def _file(self, name):
        path = os.path.join(self.retail, name)
        fh = self._fh.get(path)
        if fh is None:
            fh = open(path, 'rb')
            self._fh[path] = fh
        return fh

    def track_for(self, lba):
        for t in self.tracks:
            if t['lba0'] <= lba < t['lba0'] + t['sectors']:
                return t
        return None

    def read_sector(self, n):
        self.reads.append(n)
        if n > 0x7FFFFF:                # 24-bit negative LBA
            n -= 0x1000000
        t = self.track_for(n)
        if t is None:
            return b"\x00" * 2048
        header = 0 if t['control'] == 0 else 16
        off = (n - t['lba0']) * 2352 + header
        fh = self._file(t['file'])
        fh.seek(off)
        data = fh.read(2048)
        if len(data) < 2048:
            data += b"\x00" * (2048 - len(data))
        return data

    def read_frame(self, n):
        if n > 0x7FFFFF:
            n -= 0x1000000
        t = self.track_for(n)
        if t is None:
            return b"\x00" * 2352
        fh = self._file(t['file'])
        fh.seek((n - t['lba0']) * 2352)
        return fh.read(2352)

    def read_sectors(self, n, count):
        return b"".join(self.read_sector(n + i) for i in range(count))

    def toc_info(self, track):
        if track in BY_TRACK:
            return BY_TRACK[track]['msf_bcd'] + bytes([BY_TRACK[track]['control']])
        return b"\x00\x00\x00\x00"

    def leadout_msf(self):
        return msf_bcd(self.total_sectors - 150 + 150)  # absolute lead-out


if __name__ == '__main__':
    d = ValisDisc()
    print('tracks', len(d.tracks), 'total sectors', d.total_sectors)
    for track in (1, 2, 6, 8, 72):
        t = BY_TRACK[track]
        print('track %2d lba1=%6d info=%s' % (track, t['lba1'], d.toc_info(track).hex(' ')))
    print('track2 first 16:', d.read_sector(3440)[:16].hex(' '))
    print('track6 first 16:', d.read_sector(BY_TRACK[6]['lba1'])[:16].hex(' '))
