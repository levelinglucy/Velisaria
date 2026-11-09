"""Regression: resonance phrases must match user text regardless of case.

All inputs are synthetic and in memory; no persistent Monolith state is used.
"""
import importlib.util
import pathlib
import sys
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_resonance_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class ResonanceMatchingTests(unittest.TestCase):
    def test_default_resonance_phrase_is_case_insensitive(self):
        core = mod.EmpathyCore()
        neutral = core.affect("quiet harbour")["curiosity"]
        self.assertAlmostEqual(neutral, core.curiosity_bias)
        # One of eight default multiword resonances: 1 hit / 4.
        expected = core.curiosity_bias + 0.15 / 4
        for text in ("Eternal Spiral", "eternal spiral", "ETERNAL SPIRAL", "eTeRnAl SpIrAl"):
            with self.subTest(text=text):
                self.assertAlmostEqual(core.affect(text)["curiosity"], expected)

    def test_custom_profile_resonance_is_case_insensitive(self):
        core = mod.EmpathyCore()
        loader = mod.ProfileLoader()
        loader.profile = {"terms": {"resonance": ["Moonlit Harbor"]}}
        loader.apply_to_empathy(core)
        for text in ("Moonlit Harbor", "moonlit harbor", "MOONLIT HARBOR"):
            with self.subTest(text=text):
                self.assertAlmostEqual(
                    core.affect(text)["curiosity"], core.curiosity_bias + 0.15 / 4
                )
        self.assertAlmostEqual(core.affect("no motif")["curiosity"], core.curiosity_bias)

    def test_non_resonance_metrics_remain_unchanged(self):
        core = mod.EmpathyCore()
        before = core.affect("gentle curiosity")
        after = core.affect("Eternal Spiral")
        self.assertEqual(after["warmth"], core.compassion_bias)
        self.assertEqual(after["tension"], core.stability_bias)
        self.assertEqual(after["safety"], core.safety_bias)
        self.assertGreaterEqual(before["curiosity"], core.curiosity_bias)


if __name__ == "__main__":
    unittest.main()
