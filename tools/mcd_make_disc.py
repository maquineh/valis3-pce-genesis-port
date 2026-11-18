#!/usr/bin/env python3
"""Assemble a Mega CD ISO, multi-file CUE, and original CD-DA soundtrack.

Inputs are validated before publishing. Existing WAVs are reused only when
their SHA-256 matches the source. Changed files are staged alongside the
destination, with copies of old files retained for recovery. Publishing is
not a single atomic operation across files: a failure triggers best-effort
rollback, and the staging directory is kept for inspection or recovery.

Usage: python tools/mcd_make_disc.py <data.iso> <out_prefix> [all|1,3,5,...]
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import wave

AUDIO_SRC = Path('build/extracted/audio')
PREGAP_SEC = 2
SECTOR_BYTES = 2048


def msf(frames):
    return int(frames // 75 // 60), int(frames // 75 % 60), int(frames % 75)


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def wav_info(path):
    with wave.open(str(path), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (2, 2, 44100, 'NONE'):
            raise ValueError('CD audio must be stereo, 16-bit PCM at 44100 Hz: %s' % path)
        frames = wav.getnframes()
        if not frames or frames % 588:
            raise ValueError('CD audio must contain whole 1/75-second sectors: %s' % path)
        wav.setpos(frames - 1)
        if len(wav.readframes(1)) != 4:
            raise ValueError('truncated CD audio: %s' % path)
        return frames, frames / 44100.0


def select_tracks(spec):
    if spec == 'all':
        nums = sorted(int(match.group(1)) for path in AUDIO_SRC.iterdir()
                      if (match := re.fullmatch(r'track_(\d{2})\.wav', path.name)))
    else:
        nums = [int(value) for value in spec.split(',')]
    if not nums or len(nums) > 98 or len(set(nums)) != len(nums) or any(n < 1 or n > 99 for n in nums):
        raise ValueError('select 1 to 98 distinct audio track numbers in the range 1..99')
    return nums


def replace_file(src, dst):
    """Single-file atomic replace; isolated for failure-injection tests."""
    os.replace(src, dst)


def build_disc(iso, out, track_spec='all'):
    iso = Path(iso)
    dest = Path(out)
    parent = dest.parent
    if not iso.is_file() or not iso.stat().st_size or iso.stat().st_size % SECTOR_BYTES:
        raise ValueError('data ISO must exist and contain complete 2048-byte sectors: %s' % iso)
    nums = select_tracks(track_spec)
    plans = []
    data_frames = iso.stat().st_size // SECTOR_BYTES
    cursor = data_frames + PREGAP_SEC * 75
    cue = ['FILE "%s.iso" BINARY' % dest.name,
           '  TRACK 01 MODE1/2048', '    INDEX 01 00:00:00']
    manifest = {'data_tracks': 1, 'audio_tracks': [], 'source_iso': str(iso)}

    # Validate every source and inspect every destination before replacing any.
    for i, n in enumerate(nums):
        source = AUDIO_SRC / ('track_%02d.wav' % n)
        # Genesis Plus GX resolves each FILE relative to the preceding FILE.
        # Sibling filenames work both there and in CUE-relative players.
        target = parent / (dest.name + '_' + source.name)
        frames, duration = wav_info(source)
        source_hash = file_hash(source)
        old_hash = file_hash(target) if target.is_file() else None
        plans.append((source, target, source_hash, old_hash))
        m, s, f = msf(cursor)
        cue.extend(['FILE "%s" WAVE' % target.name,
                    '  TRACK %02d AUDIO' % (i + 2),
                    '    PREGAP 00:02:00', '    INDEX 01 00:00:00'])
        manifest['audio_tracks'].append({
            'disc_track': i + 2, 'pce_track': n, 'seconds': round(duration, 1),
            'index01': '%02d:%02d:%02d' % (m, s, f), 'wav': str(target)})
        cursor += frames // 588 + PREGAP_SEC * 75

    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + dest.name + '-staging-', dir=str(parent)))
    entries = []
    try:
        def stage_bytes(target, data):
            staged = stage / ('new-%03d' % len(entries))
            staged.write_bytes(data)
            entries.append((target, staged))

        for source, target, source_hash, old_hash in plans:
            if source_hash == old_hash:
                print('reuse %s (SHA-256 matches)' % target)
                continue
            staged = stage / ('new-%03d.wav' % len(entries))
            # Upgrade existing discs without duplicating their PCM data.
            legacy = Path(str(dest) + '_audio') / source.name
            if legacy.is_file() and file_hash(legacy) == source_hash:
                try:
                    os.link(legacy, staged)
                except OSError:
                    shutil.copyfile(source, staged)
            else:
                shutil.copyfile(source, staged)
            if file_hash(staged) != source_hash:
                raise OSError('source changed or staged copy failed verification: %s' % source)
            entries.append((target, staged))

        staged_iso = stage / 'new.iso'
        iso_hash = file_hash(iso)
        shutil.copyfile(iso, staged_iso)
        if file_hash(staged_iso) != iso_hash:
            raise OSError('source ISO changed or staged copy failed verification')
        entries.append((Path(str(dest) + '.iso'), staged_iso))
        stage_bytes(Path(str(dest) + '.json'), json.dumps(manifest, indent=2).encode('utf-8'))
        stage_bytes(Path(str(dest) + '.cue'), ('\r\n'.join(cue) + '\r\n').encode('ascii'))

        # Backups are copied before commit and kept in the staging directory.
        commits = []
        for index, (target, staged) in enumerate(entries):
            old_hash = file_hash(target) if target.is_file() else None
            backup = None
            if old_hash is not None:
                backup = stage / ('old-%03d' % index)
                shutil.copyfile(target, backup)
                if file_hash(backup) != old_hash:
                    raise OSError('destination changed while backing up: %s' % target)
            commits.append((target, staged, backup, old_hash))
        for target, _, _, old_hash in commits:
            actual = file_hash(target) if target.is_file() else None
            if actual != old_hash:
                raise OSError('destination changed before publishing: %s' % target)
        for _, target, source_hash, old_hash in plans:
            if source_hash == old_hash and (not target.is_file() or file_hash(target) != source_hash):
                raise OSError('reused audio changed before publishing: %s' % target)

        published = []
        try:
            for target, staged, backup, old_hash in commits:
                replace_file(staged, target)
                published.append((target, backup))
        except Exception as exc:
            problems = []
            for target, backup in reversed(published):
                if backup is not None:
                    try:
                        replace_file(backup, target)
                    except OSError as error:
                        problems.append('%s: %s' % (target, error))
                else:
                    problems.append('%s was newly created and was left in place' % target)
            detail = '; rollback issues: ' + '; '.join(problems) if problems else ''
            raise OSError('publishing failed: %s%s; recovery files: %s' % (exc, detail, stage)) from exc
    except Exception:
        print('Staged files preserved for inspection: %s' % stage, file=sys.stderr)
        raise
    print('wrote %s .cue/.json/.iso + %d audio WAVs; backups: %s' % (dest, len(nums), stage))
    return stage


def main():
    if not 3 <= len(sys.argv) <= 4:
        raise SystemExit('Usage: mcd_make_disc.py <data.iso> <out_prefix> [all|1,3,5,...]')
    build_disc(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'all')


if __name__ == '__main__':
    main()
