#!/usr/bin/env python3
"""Extract raw 2352-byte CUE tracks as continuous data and CD-DA WAV files.

INDEX 01 is relative to the current FILE. For tracks sharing a file, the next
INDEX 01 ends the preceding track (the historical behavior of this tool).
INDEX 00 and PREGAP are retained as metadata, not separately extracted.
An explicit image path preserves support for the original single-image dump.
MODE1 bytes are copied verbatim: a standard raw image retains sync, header and
ECC, while the original headerless dump remains headerless. These layouts are
not interchangeable for consumers that assume a particular sector layout.
"""
import json
import os
from pathlib import Path
import re
import sys
import wave

SECTOR = 2352


def msf_to_frames(s):
    parts = s.split(":")
    if len(parts) != 3 or not all(x.isdigit() for x in parts):
        raise ValueError("invalid MSF: " + s)
    minutes, seconds, frames = map(int, parts)
    if seconds >= 60 or frames >= 75:
        raise ValueError("invalid MSF: " + s)
    return (minutes * 60 + seconds) * 75 + frames


def frames_to_str(n):
    return "%02d:%02d:%02d" % (n // 75 // 60, (n // 75) % 60, n % 75)


def parse_cue(cue_path):
    tracks = []
    cur = None
    file_name = None
    with open(cue_path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            fields = line.split()
            command = fields[0].upper()
            if command == "FILE":
                match = re.fullmatch(r'FILE\s+(?:"([^"]+)"|(\S+))\s+(\S+)\s*', line, re.I)
                if not match or match.group(3).upper() != "BINARY":
                    raise ValueError("unsupported FILE declaration: " + line)
                file_name = match.group(1) or match.group(2)
                cur = None
            elif command == "TRACK":
                if file_name is None or len(fields) != 3:
                    raise ValueError("invalid TRACK declaration: " + line)
                cur = {"file": file_name, "number": int(fields[1]),
                       "type": fields[2].upper(), "index01": None, "pregap": 0}
                tracks.append(cur)
            elif command == "INDEX" and cur is not None and len(fields) == 3:
                if fields[1] == "01":
                    cur["index01"] = msf_to_frames(fields[2])
                elif fields[1] == "00":
                    cur["index00"] = msf_to_frames(fields[2])
            elif command == "PREGAP" and cur is not None:
                cur["pregap"] = msf_to_frames(fields[1])
    if not tracks:
        raise ValueError("CUE contains no tracks")
    return tracks


def split(cue_path, iso_path=None, out_dir="build/extracted"):
    tracks = parse_cue(cue_path)
    cue_dir = Path(cue_path).resolve().parent
    paths = [Path(iso_path).resolve() if iso_path else cue_dir / t["file"] for t in tracks]
    sizes = {}
    seen_numbers = set()
    for i, (t, path) in enumerate(zip(tracks, paths)):
        if t["number"] in seen_numbers:
            raise ValueError("duplicate track number: %s" % t["number"])
        seen_numbers.add(t["number"])
        if t["type"] not in ("MODE1/2352", "AUDIO"):
            raise ValueError("unsupported track type: " + t["type"])
        if path not in sizes:
            sizes[path] = path.stat().st_size
            if sizes[path] % SECTOR:
                raise ValueError("image is not sector-aligned: %s" % path)
        start = t["index01"]
        if start is None:
            raise ValueError("missing INDEX 01 for track %02d" % t["number"])
        end = (tracks[i + 1]["index01"] if i + 1 < len(tracks) and paths[i + 1] == path
               else sizes[path] // SECTOR)
        if end is None or not 0 <= start <= end <= sizes[path] // SECTOR:
            raise ValueError("invalid track range for track %02d" % t["number"])
        t.update(start_frame=start, end_frame=end, frames=end - start)
        if t["type"] == "AUDIO":
            t["audio"] = "track_%02d.wav" % t["number"]

    data_dir = Path(out_dir) / "data"
    audio_dir = Path(out_dir) / "audio"
    data_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"source": os.path.basename(iso_path) if iso_path else os.path.basename(cue_path),
                "tracks": tracks}
    for t, path in zip(tracks, paths):
        name = "track_%02d" % t["number"]
        target = data_dir / (name + ".bin") if t["type"] == "MODE1/2352" else audio_dir / (name + ".wav")
        with open(path, "rb") as src:
            src.seek(t["start_frame"] * SECTOR)
            if t["type"] == "AUDIO":
                out = wave.open(str(target), "wb")
                out.setnchannels(2)
                out.setsampwidth(2)
                out.setframerate(44100)
                write = out.writeframesraw
            else:
                out = open(target, "wb")
                write = out.write
            try:
                remaining = t["frames"] * SECTOR
                while remaining:
                    chunk = src.read(min(remaining, SECTOR * 1024))
                    if not chunk:
                        raise EOFError("unexpected end of " + str(path))
                    write(chunk)
                    remaining -= len(chunk)
            finally:
                out.close()
        print("TRACK %02d %s %s..%s -> %s" %
              (t["number"], t["type"], frames_to_str(t["start_frame"]),
               frames_to_str(t["end_frame"]), target))
    with open(Path(out_dir) / "tracks.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


if __name__ == "__main__":
    cue = sys.argv[1] if len(sys.argv) > 1 else "Valis_3_(NTSC-J)_[TJCD0009].cue"
    out = sys.argv[2] if len(sys.argv) > 2 else "build/extracted"
    # Historical dumps used a sibling .iso even when the CUE names another file.
    legacy_iso = Path(cue).with_suffix(".iso")
    parsed = parse_cue(cue)
    cue_files_exist = all((Path(cue).resolve().parent / t["file"]).is_file() for t in parsed)
    one_file = len({t["file"] for t in parsed}) == 1
    split(cue, str(legacy_iso) if one_file and not cue_files_exist and legacy_iso.is_file() else None, out)
