#!/usr/bin/env python3
"""Split the Valis III raw CD image into data tracks and audio WAVs.

IMPORTANT: this image has NO per-sector CD metadata (no sync pattern, no
4-byte header anywhere in the 555 MB file). It is a continuous stream where the
.cue MSF positions are simply multiplied by 2352 bytes. Therefore:

  * a data track's payload is the CONTINUOUS byte range
    [index01_frame*2352 .. next_index01_frame*2352)
  * a CD-DA track is the CONTINUOUS range of 2352 bytes per frame of
    16-bit stereo 44.1 kHz PCM
"""
import json
import os
import re
import sys
import wave

SECTOR = 2352


def msf_to_frames(s):
    m = s.split(":")
    return (int(m[0]) * 60 + int(m[1])) * 75 + int(m[2])


def frames_to_str(n):
    return "%02d:%02d:%02d" % (n // 75 // 60, (n // 75) % 60, n % 75)


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
                cur = {"file": file_name, "number": int(line.split()[1]),
                       "type": line.split()[2].upper(), "index01": None,
                       "pregap": 0}
                tracks.append(cur)
            elif up.startswith("INDEX 01") and cur is not None:
                cur["index01"] = msf_to_frames(line.split()[2])
            elif up.startswith("PREGAP") and cur is not None:
                cur["pregap"] = msf_to_frames(line.split()[1])
    return tracks


def split(cue_path, iso_path, out_dir):
    tracks = parse_cue(cue_path)
    total = os.path.getsize(iso_path)
    nsec = total // SECTOR
    print("image: %d bytes = %d frames (%s)" % (total, nsec, frames_to_str(nsec)))

    data_dir = os.path.join(out_dir, "data")
    audio_dir = os.path.join(out_dir, "audio")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)

    for i, t in enumerate(tracks):
        start = t["index01"]
        end = tracks[i + 1]["index01"] if i + 1 < len(tracks) else nsec
        t["start_frame"], t["end_frame"] = start, end
        t["frames"] = end - start

    manifest = {"source": os.path.basename(iso_path), "tracks": tracks}
    with open(os.path.join(out_dir, "tracks.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    with open(iso_path, "rb") as fh:
        for t in tracks:
            name = "track_%02d" % t["number"]
            fh.seek(t["start_frame"] * SECTOR)
            nbytes = t["frames"] * SECTOR
            if t["type"].startswith("MODE1"):
                payload = fh.read(nbytes)
                # data tracks: whole continuous range is the payload
                path = os.path.join(data_dir, name + ".bin")
                with open(path, "wb") as out:
                    out.write(payload)
                print("TRACK %02d MODE1 data  %s..%s  %d bytes -> %s"
                      % (t["number"], frames_to_str(t["start_frame"]),
                         frames_to_str(t["end_frame"]), len(payload), path))
            elif t["type"] == "AUDIO":
                payload = fh.read(nbytes)
                path = os.path.join(audio_dir, name + ".wav")
                with wave.open(path, "wb") as w:
                    w.setnchannels(2)
                    w.setsampwidth(2)
                    w.setframerate(44100)
                    w.writeframesraw(payload)
                t["audio"] = name + ".wav"
                print("TRACK %02d CD-DA audio  %s..%s  %d frames -> %s"
                      % (t["number"], frames_to_str(t["start_frame"]),
                         frames_to_str(t["end_frame"]), t["frames"], path))
            else:
                print("TRACK %02d %s (skipped)" % (t["number"], t["type"]))
    return manifest


if __name__ == "__main__":
    cue = sys.argv[1] if len(sys.argv) > 1 else "Valis_3_(NTSC-J)_[TJCD0009].cue"
    iso = cue[:-4] + ".iso"
    out = sys.argv[2] if len(sys.argv) > 2 else "build/extracted"
    split(cue, iso, out)
