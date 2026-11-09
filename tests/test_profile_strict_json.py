"""Strict profile JSON checks using only disposable synthetic files.

Profile hot reload must not turn duplicate JSON keys or nonstandard constants
into accepted replacement settings. The last valid profile must remain active.
"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_profile_strict_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class StrictProfileJsonTests(unittest.TestCase):
    def test_replacement_with_duplicate_prior_keeps_last_good_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "profile.json"
            state = Path(temp) / "state.json"
            valid = {"priors": {"curiosity_bias": 0.71}}
            path.write_text(json.dumps(valid), encoding="utf-8")
            monolith = mod.Monolith(state_path=str(state), profile_path=str(path))
            self.assertEqual(monolith.empathy.curiosity_bias, 0.71)

            # The default JSON parser picks the LAST occurrence silently.
            path.write_text(
                '{"priors":{"curiosity_bias":0.82,"curiosity_bias":0.19}}',
                encoding="utf-8",
            )
            monolith.think("synthetic", "hello")
            self.assertEqual(monolith.empathy.curiosity_bias, 0.71)
            self.assertEqual(monolith.profile.profile, valid)
            self.assertEqual(len(monolith.mem.state["sessions"]), 1)

    def test_duplicate_keys_at_any_depth_are_not_valid_profile_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "profile.json"
            loader = mod.ProfileLoader(str(path))
            for raw in (
                '{"priors":{"curiosity_bias":0.7},"priors":{"curiosity_bias":0.2}}',
                '{"terms":{"curiosity":["why"],"curiosity":["never"]}}',
                '{"unknown":{"nested":1,"nested":2}}',
            ):
                with self.subTest(raw=raw):
                    path.write_text(raw, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "duplicate profile JSON key"):
                        loader._read(str(path))

    def test_nonstandard_json_constants_cannot_hide_in_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "profile.json"
            loader = mod.ProfileLoader(str(path))
            for literal in ("NaN", "Infinity", "-Infinity"):
                with self.subTest(literal=literal):
                    path.write_text(
                        '{"metadata":{"unrecognized":' + literal + '}}',
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(ValueError, "nonstandard profile JSON"):
                        loader._read(str(path))

    def test_unambiguous_valid_profile_still_loads(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "profile.json"
            valid = {"priors":{"curiosity_bias":0.71}, "terms":{"positive":["care"]}}
            path.write_text(json.dumps(valid), encoding="utf-8")
            loader = mod.ProfileLoader(str(path))
            self.assertEqual(loader._read(str(path)), valid)


if __name__ == "__main__":
    unittest.main()
