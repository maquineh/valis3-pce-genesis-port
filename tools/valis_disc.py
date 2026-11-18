"""Full multi-track disc reader for the retail Valis III cue/bin set.

Absolute LBAs are the drive's 24-bit sector addresses: disc file sector 0 is
MSF 00:00:00, i.e. LBA -150.  Each retail track file keeps its own INDEX 00
pregap, so a track's absolute base is the running sum of previous track
lengths minus 150.
"""

import os
import wave

from valis_toc import TOC, BY_TRACK, msf_bcd

RETAIL = os.path.join('build', 'retail')
EXTRACTED_DATA = os.path.join('build', 'extracted', 'data')
EXTRACTED_AUDIO = os.path.join('build', 'extracted', 'audio')


class ValisDisc(object):
    def __init__(self, retail=RETAIL, tracks=TOC):
        self.retail = retail
        self.tracks = tracks
        self.reads = []
        self._fh = {}
        self._waves = {}
        self._kind = {}
        self.total_sectors = sum(t['sectors'] for t in tracks)

    def _track_path(self, track):
        path = os.path.join(self.retail, track['file'])
        if os.path.isfile(path):
            return path, 'raw'
        number = track['track']
        if track['control']:
            path = os.path.join(EXTRACTED_DATA, 'track_%02d.bin' % number)
            if os.path.isfile(path):
                return path, 'data'
        else:
            path = os.path.join(EXTRACTED_AUDIO, 'track_%02d.wav' % number)
            if os.path.isfile(path):
                return path, 'audio'
        raise FileNotFoundError(os.path.join(self.retail, track['file']))

    def _file(self, track):
        path, kind = self._track_path(track)
        fh = self._fh.get(path)
        if fh is None:
            fh = open(path, 'rb')
            self._fh[path] = fh
            self._kind[path] = kind
        return path, fh, kind

    def _wave_file(self, path):
        reader = self._waves.get(path)
        if reader is None:
            reader = wave.open(path, 'rb')
            self._waves[path] = reader
        return reader

    @staticmethod
    def _normalize_lba(n):
        return n - 0x1000000 if n > 0x7FFFFF else n

    def _read_extracted_audio(self, path, sector):
        reader = self._wave_file(path)
        reader.setpos(sector * 588)
        return reader.readframes(588).ljust(2352, b'\x00')

    def track_for(self, lba):
        for t in self.tracks:
            if t['lba0'] <= lba < t['lba0'] + t['sectors']:
                return t
        return None

    def read_sector(self, n):
        n = self._normalize_lba(n)
        self.reads.append(n)
        t = self.track_for(n)
        if t is None:
            return b"\x00" * 2048
        path, fh, kind = self._file(t)
        if kind == 'audio':
            if n < t['lba1']:
                return b"\x00" * 2048
            return self._read_extracted_audio(path, n - t['lba1'])[:2048]
        if kind == 'data':
            if n < t['lba1']:
                return b"\x00" * 2048
            off = (n - t['lba1']) * 2352 + 16
        else:
            header = 0 if t['control'] == 0 else 16
            off = (n - t['lba0']) * 2352 + header
        fh.seek(off)
        data = fh.read(2048)
        if len(data) < 2048:
            data += b"\x00" * (2048 - len(data))
        return data

    def read_frame(self, n):
        n = self._normalize_lba(n)
        t = self.track_for(n)
        if t is None:
            return b"\x00" * 2352
        path, fh, kind = self._file(t)
        if kind == 'audio':
            if n < t['lba1']:
                return b"\x00" * 2352
            return self._read_extracted_audio(path, n - t['lba1'])
        if kind == 'data':
            if n < t['lba1']:
                return b"\x00" * 2352
            off = (n - t['lba1']) * 2352
        else:
            off = (n - t['lba0']) * 2352
        fh.seek(off)
        return fh.read(2352)

    def read_sectors(self, n, count):
        return b"".join(self.read_sector(n + i) for i in range(count))

    def toc_info(self, track):
        if track in BY_TRACK:
            return BY_TRACK[track]['msf_bcd'] + bytes([BY_TRACK[track]['control']])
        return b"\x00\x00\x00\x00"

    def leadout_msf(self):
        # total_sectors is a file-frame count; subtract the 150-frame lead-in
        # before converting the absolute LBA back to MSF.
        return msf_bcd(self.total_sectors - 150)


if __name__ == '__main__':
    d = ValisDisc()
    print('tracks', len(d.tracks), 'total sectors', d.total_sectors)
    for track in (1, 2, 6, 8, 72):
        t = BY_TRACK[track]
        print('track %2d lba1=%6d info=%s' % (track, t['lba1'], d.toc_info(track).hex(' ')))
    print('track2 first 16:', d.read_sector(3440)[:16].hex(' '))
    print('track6 first 16:', d.read_sector(BY_TRACK[6]['lba1'])[:16].hex(' '))
