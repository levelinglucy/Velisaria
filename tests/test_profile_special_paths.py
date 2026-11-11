"""Non-regular optional profiles must not block or replace last-good settings.

Use disposable files only. The FIFO startup regression runs in a child process
with a timeout so an unsafe predecessor cannot hang the test runner.
"""
import importlib.util
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_profile_special_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class ProfileSpecialPathTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO creation is unavailable")
    def test_fifo_profile_startup_returns_defaults_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            profile = root / "profile.json"
            state = root / "state.json"
            os.mkfifo(profile)
            code = (
                "import json, sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "from sanctified_monolith import Monolith, EmpathyCore\n"
                "engine = Monolith(state_path=sys.argv[2], profile_path=sys.argv[3])\n"
                "print(json.dumps({'profile': engine.profile.profile, "
                "'stamp': engine.profile._stamp, "
                "'default_bias': engine.empathy.compassion_bias == EmpathyCore().compassion_bias}))\n"
            )
            try:
                process = subprocess.run(
                    [sys.executable, "-c", code, str(ROOT), str(state), str(profile)],
                    cwd=directory, capture_output=True, text=True, timeout=3,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                self.fail("Optional FIFO profile blocked startup beyond three seconds")
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result, {"profile": {}, "stamp": None, "default_bias": True})
            self.assertFalse(state.exists())
            self.assertFalse(pathlib.Path(str(state) + ".tmp").exists())
            self.assertTrue(stat.S_ISFIFO(profile.stat().st_mode))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO creation is unavailable")
    def test_fifo_replacement_retains_last_good_profile_without_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = pathlib.Path(directory) / "profile.json"
            original = {"priors": {"compassion_bias": 0.73}}
            profile.write_text(json.dumps(original), encoding="utf-8")
            loader = mod.ProfileLoader(str(profile))
            self.assertEqual(loader.load(), original)
            previous_stamp = loader._stamp
            profile.unlink()
            os.mkfifo(profile)

            # The mock both observes forbidden reads and contains the old code:
            # a direct FIFO read here would otherwise block this process.
            with patch.object(loader, "_read", side_effect=AssertionError("must not read FIFO")) as read:
                self.assertEqual(loader.load(), original)
                read.assert_not_called()
            self.assertEqual(loader.profile, original)
            self.assertEqual(loader._stamp, previous_stamp)
            self.assertTrue(stat.S_ISFIFO(profile.stat().st_mode))

    def test_directory_replacement_preserves_cache_then_regular_reload_resets_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            profile = root / "profile.json"
            original = {
                "priors": {"compassion_bias": 0.73},
                "gains": {"curiosity_gain": 0.07},
            }
            profile.write_text(json.dumps(original), encoding="utf-8")
            engine = mod.Monolith(state_path=str(root / "state.json"), profile_path=str(profile))
            previous_stamp = engine.profile._stamp
            self.assertEqual(engine.empathy.compassion_bias, 0.73)
            self.assertEqual(engine.empathy._curi_gain, 0.07)
            profile.unlink()
            profile.mkdir()

            with patch.object(engine.profile, "_read", side_effect=AssertionError("must not read directory")) as read:
                self.assertEqual(engine.profile.load(), original)
                engine.think("synthetic", "directory replacement")
                read.assert_not_called()
            self.assertEqual(engine.profile.profile, original)
            self.assertEqual(engine.profile._stamp, previous_stamp)
            self.assertEqual(engine._applied_profile_stamp, previous_stamp)
            self.assertEqual(engine.empathy.compassion_bias, 0.73)
            self.assertEqual(engine.empathy._curi_gain, 0.07)

            # Returning to a valid regular profile must resume normal reload.
            # An accepted empty replacement removes old overrides under M14.
            profile.rmdir()
            profile.write_text("{}", encoding="utf-8")
            engine.think("synthetic", "regular profile restored")
            defaults = mod.EmpathyCore()
            self.assertEqual(engine.profile.profile, {})
            self.assertNotEqual(engine.profile._stamp, previous_stamp)
            self.assertEqual(engine._applied_profile_stamp, engine.profile._stamp)
            self.assertEqual(engine.empathy.compassion_bias, defaults.compassion_bias)
            self.assertEqual(engine.empathy._curi_gain, defaults._curi_gain)


if __name__ == "__main__":
    unittest.main()
