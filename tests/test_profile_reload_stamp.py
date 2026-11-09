"""Synthetic timestamp-replacement profile reload regressions.

All profile files are disposable. We never start the persistent Monolith or
open a user's state, and do not depend on wall-clock delays for filesystem time.
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_reload_stamp_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class ProfileReloadStampTests(unittest.TestCase):
    def _create_loader(self, path, content):
        path.write_text(json.dumps(content), encoding="utf-8")
        old_ns = path.stat().st_mtime_ns
        loader = mod.ProfileLoader(str(path))
        self.assertEqual(loader.load(), content)
        return loader, old_ns

    def test_valid_older_timestamp_replacement_is_applied(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "profile.json"
            loader, old_ns = self._create_loader(
                path, {"priors": {"safety_bias": 0.72}}
            )
            updated = {"priors": {"safety_bias": 0.24}}
            path.write_text(json.dumps(updated), encoding="utf-8")
            os.utime(path, ns=(old_ns - 5_000_000_000,) * 2)
            self.assertEqual(loader.load(), updated)
            core = mod.EmpathyCore()
            loader.apply_to_empathy(core)
            self.assertEqual(core.safety_bias, 0.24)

    def test_same_timestamp_changed_size_triggers_reload(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "profile.json"
            loader, old_ns = self._create_loader(
                path, {"terms": {"positive": ["hope"]}}
            )
            updated = {"terms": {"positive": ["hope", "longer lantern"]}}
            path.write_text(json.dumps(updated), encoding="utf-8")
            os.utime(path, ns=(old_ns,) * 2)
            self.assertEqual(loader.load(), updated)

    def test_older_invalid_replacement_preserves_last_good_profile(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "profile.json"
            original = {"gains": {"compassion_gain": 0.2}}
            loader, old_ns = self._create_loader(path, original)
            path.write_text('{"gains":{"compassion_gain":"invalid"}}', encoding="utf-8")
            os.utime(path, ns=(old_ns - 5_000_000_000,) * 2)
            self.assertEqual(loader.load(), original)
            repaired = {"gains": {"compassion_gain": 0.4}}
            path.write_text(json.dumps(repaired), encoding="utf-8")
            os.utime(path, ns=(old_ns - 4_000_000_000,) * 2)
            self.assertEqual(loader.load(), repaired)

    def test_same_stat_metadata_replacement_inode_triggers_reload(self):
        with tempfile.TemporaryDirectory() as d:
            directory = pathlib.Path(d)
            path = directory / "profile.json"
            first = {"priors": {"safety_bias": 0.72}}
            loader, old_ns = self._create_loader(path, first)
            replacement = directory / "next.json"
            next_value = {"priors": {"safety_bias": 0.24}}
            replacement.write_text(json.dumps(next_value), encoding="utf-8")
            self.assertEqual(replacement.stat().st_size, path.stat().st_size)
            os.utime(replacement, ns=(old_ns,) * 2)
            os.replace(replacement, path)
            self.assertEqual(loader.load(), next_value)


if __name__ == "__main__":
    unittest.main()
