#!/usr/bin/env python3
"""Assemble the final Sega Mega CD disc image.

Takes the data ISO produced by the Mega CD build and appends the original
PC Engine CD-DA soundtrack tracks as audio tracks, then writes a .cue in the
format emulators expect:

    FILE "valis3_mcd.iso" BINARY
      TRACK 01 MODE1/2048
        INDEX 01 00:00:00
    FILE "valis3_mcd_audio/track_01.wav" WAVE
      TRACK 02 AUDIO
        INDEX 00 mm:ss
        INDEX 01 mm:ss

and a JSON manifest mapping disc track numbers to the original PC Engine
track numbers (so the game code can play the right music).

Usage:
    python3 tools/mcd_make_disc.py <data.iso> <out_prefix> [all|1,3,5,...]
"""
import json
import os
import shutil
import sys
import wave

AUDIO_SRC = "build/extracted/audio"
PREGAP_SEC = 2


def msf(frames):
    f = int(frames % 75)
    s = int((frames // 75) % 60)
    m = int((frames // 75) // 60)
    return m, s, f


def wav_info(path):
    w = wave.open(path, "rb")
    frames = w.getnframes()
    w.close()
    return frames, frames / 44100.0


def main():
    iso = sys.argv[1]
    out = sys.argv[2]
    tracks = sys.argv[3].split(",") if len(sys.argv) > 3 else ["all"]
    dest = out
    destdir = os.path.dirname(dest)
    if destdir:
        os.makedirs(destdir, exist_ok=True)
    shutil.copy(iso, dest + ".iso")
    os.makedirs(dest + "_audio", exist_ok=True)

    if tracks == ["all"]:
        nums = sorted(int(f[6:8]) for f in os.listdir(AUDIO_SRC)
                      if f.endswith(".wav"))
    else:
        nums = [int(t) for t in tracks]

    data_frames = os.path.getsize(iso) // 2048
    cursor = data_frames + PREGAP_SEC * 75   # first audio track index 01
    cue = ['FILE "%s.iso" BINARY' % os.path.basename(dest),
           "  TRACK 01 MODE1/2048",
           "    INDEX 01 00:00:00"]
    manifest = {"data_tracks": 1, "audio_tracks": [], "source_iso": iso}
    for i, n in enumerate(nums):
        src = os.path.join(AUDIO_SRC, "track_%02d.wav" % n)
        dst = os.path.join(dest + "_audio", "track_%02d.wav" % n)
        shutil.copy(src, dst)
        frames, dur = wav_info(src)
        cd_frames = int(round(dur * 75))   # CD frames = seconds * 75
        m, s, f = msf(cursor)
        cue.append('FILE "%s_audio/track_%02d.wav" WAVE' %
                   (os.path.basename(dest), n))
        cue.append("  TRACK %02d AUDIO" % (i + 2))
        mm, ss, ff = msf(cursor - PREGAP_SEC * 75)
        cue.append("    INDEX 00 %02d:%02d:%02d" % (mm, ss, ff))
        cue.append("    INDEX 01 %02d:%02d:%02d" % (m, s, f))
        manifest["audio_tracks"].append({
            "disc_track": i + 2, "pce_track": n, "seconds": round(dur, 1),
            "index01": "%02d:%02d:%02d" % (m, s, f), "wav": dst})
        cursor += cd_frames + PREGAP_SEC * 75
        print("disc track %02d <- PCE track %02d (%5.1fs) index01 %02d:%02d:%02d"
              % (i + 2, n, dur, m, s, f))

    with open(dest + ".cue", "w", encoding="ascii", newline="\r\n") as fh:
        fh.write("\n".join(cue) + "\n")
    with open(dest + ".json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print("wrote %s .cue/.json/.iso + %d audio WAVs"
          % (dest, len(nums)))


if __name__ == "__main__":
    main()
