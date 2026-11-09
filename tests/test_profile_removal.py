"""Synthetic checks: a valid reduced profile must release removed overrides.

No owner state files are opened. All writes use disposable paths.
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_profile_removal_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class ProfileRemovalTests(unittest.TestCase):
    def _replace(self, path, value):
        previous = path.stat().st_mtime_ns
        path.write_text(json.dumps(value), encoding="utf-8")
        os.utime(path, ns=(previous + 2_000_000_000,) * 2)

    def test_valid_partial_reload_releases_omitted_prior_terms_and_gain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            profile = root / "profile.json"
            profile.write_text(json.dumps({
                "priors": {"compassion_bias": 0.93, "safety_bias": 0.91},
                "terms": {"positive": ["lantern"]},
                "gains": {"curiosity_gain": 0.44},
            }), encoding="utf-8")
            mono = mod.Monolith(str(root / "state.json"), str(profile))
            core = mono.empathy
            self.assertEqual(core.pos_terms, ["lantern"])
            self._replace(profile, {"priors": {"safety_bias": 0.27}})
            mono.think("synthetic", "lantern")
            self.assertIs(mono.empathy, core)
            self.assertEqual(core.compassion_bias, 0.58)
            self.assertEqual(core.safety_bias, 0.27)
            self.assertEqual(core._curi_gain, 0.18)
            self.assertEqual(core.pos_terms, mod.EmpathyCore().pos_terms)
            self.assertNotIn("lantern", core.pos_terms)

    def test_empty_valid_reload_clears_overrides_but_invalid_keeps_last_good(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            profile = root / "profile.json"
            profile.write_text(json.dumps({
                "priors": {"curiosity_bias": 0.91},
                "terms": {"resonance": ["moon lantern"]},
            }), encoding="utf-8")
            mono = mod.Monolith(str(root / "state.json"), str(profile))
            self.assertEqual(mono.empathy.curiosity_bias, 0.91)
            self._replace(profile, {"priors": {"curiosity_bias": "invalid"}})
            mono.think("synthetic", "moon lantern")
            self.assertEqual(mono.empathy.curiosity_bias, 0.91)
            self.assertEqual(mono.empathy.res_terms, ["moon lantern"])
            self._replace(profile, {})
            mono.think("synthetic", "moon lantern")
            self.assertEqual(mono.empathy.curiosity_bias, 0.52)
            self.assertEqual(mono.empathy.res_terms, mod.EmpathyCore().res_terms)


if __name__ == "__main__":
    unittest.main()
