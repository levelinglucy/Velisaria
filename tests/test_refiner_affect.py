"""Synthetic end-to-end checks that refinement uses current empathy, not fallbacks.

All runs use disposable files. See DEV_NOTES.md, decision M-013.
"""
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_refiner_affect_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class RefinerAffectTests(unittest.TestCase):
    def _check_one_thought(self, mono, text):
        tier_before = mono.mem.au_tier()
        expected = mono.empathy.affect(text, attention_tier=tier_before)
        result = mono.think("synthetic", text)
        refiner_marker = "refine w:{:.2f} s:{:.2f} c:{:.2f}".format(
            expected["warmth"], expected["tension"], expected["curiosity"]
        )
        self.assertIn(refiner_marker, result)
        # The final logged weight must use the RTE's actual stability-derived
        # score, not the provisional pre-RTE base (0.6).
        recorded = mono.mem.state["sessions"][-1]["metrics"]
        expected_weight = mono.empathy.weight(
            0.55 + 0.45 * recorded["stability"], text, attention_tier=tier_before
        )["weight"]
        self.assertAlmostEqual(recorded["empathy"], expected_weight)

    def test_default_affect_drives_live_refiner(self):
        with tempfile.TemporaryDirectory() as d:
            mono = mod.Monolith(state_path=str(pathlib.Path(d) / "state.json"))
            self._check_one_thought(mono, "Eternal Spiral")
            self._check_one_thought(mono, "angry but I love you")

    def test_valid_custom_profile_affects_refined_text(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            profile = root / "profile.json"
            profile.write_text(json.dumps({
                "priors": {"compassion_bias": 0.9, "curiosity_bias": 0.8},
                "terms": {"resonance": ["Moonlit Harbor"]},
            }), encoding="utf-8")
            mono = mod.Monolith(
                state_path=str(root / "state.json"), profile_path=str(profile)
            )
            self._check_one_thought(mono, "Moonlit Harbor")


if __name__ == "__main__":
    unittest.main()
