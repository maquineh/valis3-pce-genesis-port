import hashlib
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import wave

SCRIPT = Path(__file__).resolve().with_name("mcd_make_disc.py")
spec = importlib.util.spec_from_file_location("mcd_make_disc", SCRIPT)
disc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(disc)


def write_wav(path, frames=588):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(bytes(frames * 4))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DiscPublicationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audio = self.root / "build/extracted/audio"
        self.out = self.root / "dist/test"
        self.iso = self.root / "input.iso"
        self.iso.parent.mkdir(parents=True, exist_ok=True)
        self.iso.write_bytes(b"I" * 2048)
        self.audio.mkdir(parents=True)
        self.wav = self.audio / "track_01.wav"
        write_wav(self.wav)
        self.old_cwd = Path.cwd()
        import os
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.old_cwd)

    def test_each_wav_uses_its_own_time_base(self):
        second_wav = self.audio / "track_03.wav"
        write_wav(second_wav, frames=44100 * 4)
        disc.build_disc(self.iso, self.out, "1,3")
        cue = Path(str(self.out) + ".cue").read_text()
        files = re.findall(r'^FILE "([^"]+)" (?:BINARY|WAVE)$', cue, re.M)
        self.assertEqual(len(files), 3)
        self.assertTrue(all(Path(name).name == name for name in files))
        self.assertTrue(all((self.root / "dist" / name).is_file() for name in files))
        self.assertEqual(re.findall(r'^\s*INDEX 01 (\S+)$', cue, re.M),
                         ["00:00:00"] * 3)
        self.assertEqual(re.findall(r'^\s*PREGAP (\S+)$', cue, re.M),
                         ["00:02:00"] * 2)
        self.assertNotIn("INDEX 00", cue)
        manifest = json.loads(Path(str(self.out) + ".json").read_text())
        self.assertEqual([track["pce_track"] for track in manifest["audio_tracks"]], [1, 3])
    def test_matching_wav_is_reused_without_replacement(self):
        target = Path(str(self.out) + "_track_01.wav")
        target.parent.mkdir(parents=True)
        target.write_bytes(self.wav.read_bytes())
        original = disc.replace_file
        replaced = []
        def record(src, dst):
            replaced.append(Path(dst))
            original(src, dst)
        with mock.patch.object(disc, "replace_file", side_effect=record):
            stage = disc.build_disc(self.iso, self.out, "1")
        self.assertNotIn(target, replaced)
        self.assertEqual(digest(target), digest(self.wav))
        self.assertTrue((self.out.with_suffix(".cue")).is_file())
        self.assertTrue(stage.is_dir())

    def test_invalid_input_leaves_existing_outputs_untouched(self):
        outputs = [Path(str(self.out) + suffix) for suffix in (".iso", ".cue", ".json")]
        audio_target = Path(str(self.out) + "_track_01.wav")
        audio_target.parent.mkdir(parents=True)
        for path in outputs + [audio_target]:
            path.write_bytes(("prior:" + path.name).encode())
        before = {path: path.read_bytes() for path in outputs + [audio_target]}
        with self.assertRaises(ValueError):
            disc.build_disc(self.iso, self.out, "1,1")
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(list((self.root / "dist").glob(".test-staging-*")), [])

    def test_publish_failure_rolls_back_all_prior_artifacts(self):
        outputs = [Path(str(self.out) + suffix) for suffix in (".iso", ".cue", ".json")]
        audio_target = Path(str(self.out) + "_track_01.wav")
        audio_target.parent.mkdir(parents=True)
        for path in outputs + [audio_target]:
            path.write_bytes(("prior:" + path.name).encode())
        before = {path: path.read_bytes() for path in outputs + [audio_target]}
        real_replace = disc.replace_file
        calls = 0
        def fail_once(src, dst):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("injected publish failure")
            real_replace(src, dst)
        with mock.patch.object(disc, "replace_file", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "publishing failed: injected publish failure"):
                disc.build_disc(self.iso, self.out, "1")
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(calls, 5)  # two publishes, failed publish, and two rollbacks
        self.assertEqual(len(list((self.root / "dist").glob(".test-staging-*"))), 1)


if __name__ == "__main__":
    unittest.main()



