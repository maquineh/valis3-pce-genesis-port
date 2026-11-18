"""Boot the mixed-mode disc and identify the city music before and after a loop."""
import argparse
import json
from pathlib import Path
import sys
import wave

import numpy as np
from scipy.signal import correlate

import test_megacd_libretro as harness


def mono(path):
    with wave.open(str(path), "rb") as source:
        assert (source.getframerate(), source.getsampwidth(), source.getnchannels()) == (44100, 2, 2)
        pcm = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").reshape(-1, 2)
    # Low-pass before downsampling. The CD and emulator sample phases can differ.
    length = len(pcm) // 8 * 8
    return pcm[:length].reshape(-1, 16).mean(axis=1).astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "system", "cue", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.cue.with_suffix(".json").read_text())
    track = next(track for track in manifest["audio_tracks"] if track["pce_track"] == 38)
    source = mono(args.cue.parent / Path(track["wav"]).name)
    rate = 44100 / 8
    duration = len(source) / rate
    # Walk to the meeting and then wait at the rooftop entrance. Include a
    # sample after the original track's 142 s period to exercise the repeat.
    times = (48, 83, round(48 + duration))
    sys.argv = ["city-audio", "--core", str(args.core), "--system", str(args.system),
                "--cue", str(args.cue), "--output", str(args.output), "--script-only",
                "--event", "600:start:4", "--event", "2250:start:4",
                "--event", "2410:right:880",
                "--frames", str((times[-1] + 2) * 60)]
    harness.main()
    output = mono(args.output / "audio.wav")
    positions = []
    for second in times:
        start = round(second * rate)
        sample = output[start:start + round(rate)]
        scores = correlate(source, sample, mode="valid", method="fft")
        index = int(scores.argmax())
        norm = np.linalg.norm(source[index:index+len(sample)]) * np.linalg.norm(sample)
        assert norm, f"silent at {second} s"
        match = scores[index] / norm
        assert match > 0.85, (second, "wrong recording", match)
        positions.append(index / rate)
        print(f"{second}s of emulation matches PCE track 38 at {positions[-1]:.2f}s ({match:.3f})")
    assert abs(positions[1] - positions[0] - (times[1] - times[0])) < 0.20
    # Allow the physical seek at the track boundary.
    assert abs(positions[2] - positions[0] - (times[2] - times[0] - duration)) < 3

    # Match several syllables to the PCE actor's recording, using the actual
    # mixed output: the drive must continue playing underneath the PCM channel.
    voice_track = next(track for track in manifest["audio_tracks"] if track["pce_track"] == 19)
    voice = mono(args.cue.parent / Path(voice_track["wav"]).name)
    search_start = 48
    speech_window = output[round(search_start * rate):round(65 * rate)]
    starts = []
    for offset in (0.35, 1.53, 2.15):
        start = round((7.98 + offset) * rate)
        sample = voice[start:start + round(0.38 * rate)]
        scores = correlate(speech_window, sample, mode="valid", method="fft")
        index = int(scores.argmax())
        norm = np.linalg.norm(sample) * np.linalg.norm(speech_window[index:index+len(sample)])
        assert norm and scores[index] / norm > 0.45, ("missing Cham voice", offset)
        starts.append(search_start + index / rate - offset)
    assert max(starts) - min(starts) < 0.04, ("voice timing", starts)
    print(f"Cham's track 19 line begins at {starts[0]:.2f}s of emulation")
    during = round((starts[0] + 1.5) * rate)
    sample = output[during:during+round(rate)]
    scores = correlate(source, sample, mode="valid", method="fft")
    index = int(scores.argmax())
    expected = positions[0] + during/rate - times[0]
    assert abs(index/rate - expected) < 0.2, "background track interrupted by speech"


if __name__ == "__main__":
    main()
