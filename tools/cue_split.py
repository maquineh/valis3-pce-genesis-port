#!/usr/bin/env python3
"""Split a raw 2352-byte-sector CD image (.cue/.iso, MODE1/2352) into tracks.

PC Engine / TurboGrafx-16 CD-ROM games are CD-ROM XA style discs:
  * one or more MODE1/2352 data tracks holding game code + data
  * many CD-DA (audio) tracks holding the soundtrack

This script parses the .cue, walks the raw image and writes:
  out_dir/data/track_XX.bin      2048-byte payload of each MODE1 data track
  out_dir/audio/track_XX.wav     16-bit stereo 44.1 kHz WAV of each AUDIO track
  out_dir/tracks.json            full parsed track table (also used by later tools)
"""
import json
import os
import re
import struct
import sys
import wave

SECTOR = 2352
DATA_PAYLOAD = 2048
AUDIO_BYTES = 2352


def msf_to_frames(s):
    m = s.split(":")
    return (int(m[0]) * 60 + int(m[1])) * 75 + int(m[2])


def parse_cue(cue_path):
    tracks = []
    cur = None
    file_name = None
    with open(cue_path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            up = line.upper()
            if up.startswith("FILE"):
                m = re.search(r'"([^"]+)"', line)
                file_name = m.group(1) if m else None
                cur = None
            elif up.startswith("TRACK"):
                cur = {
                    "file": file_name,
                    "number": int(line.split()[1]),
                    "type": line.split()[2].upper(),
                    "index01": None,
                    "pregap": 0,
                }
                tracks.append(cur)
            elif up.startswith("INDEX 01") and cur is not None:
                cur["index01"] = msf_to_frames(line.split()[2])
            elif up.startswith("PREGAP") and cur is not None:
                cur["pregap"] = msf_to_frames(line.split()[1])
    return tracks


def sector_time(nframes):
    return frames_to_str(nframes)


def frames_to_str(n):
    f = n % 75
    s = (n // 75) % 60
    m = n // 75 // 60
    return "%02d:%02d:%02d" % (m, s, f)


def split(cue_path, iso_path, out_dir):
    tracks = parse_cue(cue_path)
    total = os.path.getsize(iso_path)
    nsec = total // SECTOR
    print("image: %d bytes = %d sectors (%s)" % (total, nsec, frames_to_str(nsec)))

    data_dir = os.path.join(out_dir, "data")
    audio_dir = os.path.join(out_dir, "audio")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)

    # assign start/end frames per track (pregap fills the gap before index01)
    starts = []
    for t in tracks:
        if t["index01"] is None:
            raise SystemExit("track %d has no INDEX 01" % t["number"])
        start = t["index01"] - t["pregap"]
        starts.append((t, start))
    for i, (t, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else nsec
        t["start_frame"] = start
        t["index01_frame"] = t["index01"]
        t["end_frame"] = end
        t["frames"] = end - start
        t["sectors_payload"] = (end - start) - t["pregap"]

    manifest = {"source": os.path.basename(iso_path), "tracks": tracks}
    with open(os.path.join(out_dir, "tracks.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    with open(iso_path, "rb") as fh:
        for t in tracks:
            name = "track_%02d" % t["number"]
            if t["type"].startswith("MODE1"):
                path = os.path.join(data_dir, name + ".bin")
                fh.seek(t["start_frame"] * SECTOR)
                with open(path, "wb") as out:
                    # payload starts at offset 16 of the raw sector (12 sync + 4 header)
                    written = 0
                    for s in range(t["start_frame"], t["end_frame"]):
                        fh.seek(s * SECTOR)
                        sec = fh.read(SECTOR)
                        out.write(sec[16:16 + DATA_PAYLOAD])
                        written += 2048
                print("TRACK %02d MODE1 data  %s..%s  %d sectors -> %s (%d bytes)"
                      % (t["number"], frames_to_str(t["start_frame"]),
                         frames_to_str(t["end_frame"]), t["frames"], path, written))
            elif t["type"] == "AUDIO":
                path = os.path.join(audio_dir, name + ".wav")
                with wave.open(path, "wb") as w:
                    w.setnchannels(2)
                    w.setsampwidth(2)
                    w.setframerate(44100)
                    for s in range(t["start_frame"], t["end_frame"]):
                        fh.seek(s * SECTOR + 16)
                        w.writeframesraw(fh.read(AUDIO_BYTES - 16))
                t["audio"] = name + ".wav"
                print("TRACK %02d CD-DA audio  %s..%s  %d frames -> %s (%s)"
                      % (t["number"], frames_to_str(t["start_frame"]),
                         frames_to_str(t["end_frame"]), t["frames"], path,
                         frames_to_str(t["frames"])))
            else:
                print("TRACK %02d %s (skipped)" % (t["number"], t["type"]))
    return manifest


if __name__ == "__main__":
    cue = sys.argv[1] if len(sys.argv) > 1 else "Valis_3_(NTSC-J)_[TJCD0009].cue"
    iso = cue[:-4] + ".iso"
    out = sys.argv[2] if len(sys.argv) > 2 else "build/extracted"
    split(cue, iso, out)
