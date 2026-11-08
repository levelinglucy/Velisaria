"""Synthetic profile-shape regressions; only disposable paths are written.

The hot-reload contract keeps the last validated profile, never a partially
applied malformed replacement. See DEV_NOTES.md for known scope limits.
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_profile_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class ProfileValidationTests(unittest.TestCase):
    def test_invalid_profiles_leave_default_core_usable(self):
        cases = (
            ["not an object"],
            {"priors": "invalid"},
            {"priors": {"compassion_bias": "warm"}},
            {"priors": {"safety_bias": True}},
            {"priors": {"curiosity_bias": None}},
            {"terms": {"positive": [17]}},
            {"terms": {"negative": "fear"}},
            {"terms": {"resonance": [None]}},
            {"gains": {"compassion_gain": float("inf")}},
            {"gains": {"curiosity_gain": "fast"}},
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as d:
                root = pathlib.Path(d)
                profile = root / "profile.json"
                profile.write_text(json.dumps(case), encoding="utf-8")
                mono = mod.Monolith(
                    state_path=str(root / "state.json"), profile_path=str(profile)
                )
                self.assertEqual(mono.profile.profile, {})
                self.assertEqual(mono.empathy.compassion_bias, 0.58)
                self.assertEqual(mono.empathy.safety_bias, 0.62)
                self.assertEqual(mono.empathy.neg_terms[0], "angry")
                result = mono.think("synthetic", "hello")
                self.assertIn("stab:", result)
                self.assertEqual(mono.mem.snapshot()["sessions"], 1)

    def test_failed_reload_retains_last_complete_profile(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            path = root / "profile.json"
            path.write_text(
                json.dumps({
                    "priors": {"compassion_bias": 0.84},
                    "terms": {"positive": ["lantern"]},
                    "gains": {"curiosity_gain": 0.4},
                }), encoding="utf-8"
            )
            mono = mod.Monolith(
                state_path=str(root / "state.json"), profile_path=str(path)
            )
            self.assertEqual(mono.empathy.pos_terms, ["lantern"])
            self.assertEqual(mono.empathy.compassion_bias, 0.84)
            self.assertEqual(mono.empathy._curi_gain, 0.4)
            old = path.stat().st_mtime_ns
            path.write_text(
                json.dumps({
                    "priors": {"compassion_bias": 0.2},
                    "terms": {"positive": [None]},
                    "gains": {"curiosity_gain": 0.8},
                }), encoding="utf-8"
            )
            os.utime(path, ns=(old + 2_000_000_000, old + 2_000_000_000))
            mono.think("synthetic", "lantern")
            self.assertEqual(mono.empathy.pos_terms, ["lantern"])
            self.assertEqual(mono.empathy.compassion_bias, 0.84)
            self.assertEqual(mono.empathy._curi_gain, 0.4)

    def test_valid_profile_reload_applies_whole_new_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            path = root / "profile.json"
            path.write_text(
                json.dumps({"priors": {"safety_bias": 0.7}}), encoding="utf-8"
            )
            mono = mod.Monolith(
                state_path=str(root / "state.json"), profile_path=str(path)
            )
            self.assertEqual(mono.empathy.safety_bias, 0.7)
            old = path.stat().st_mtime_ns
            path.write_text(
                json.dumps({
                    "priors": {"safety_bias": 0.3},
                    "terms": {"negative": ["storm"]},
                    "gains": {"compassion_gain": 0.25},
                }), encoding="utf-8"
            )
            os.utime(path, ns=(old + 2_000_000_000, old + 2_000_000_000))
            mono.think("synthetic", "storm")
            self.assertEqual(mono.empathy.safety_bias, 0.3)
            self.assertEqual(mono.empathy.neg_terms, ["storm"])
            self.assertEqual(mono.empathy._comp_gain, 0.25)


if __name__ == "__main__":
    unittest.main()
