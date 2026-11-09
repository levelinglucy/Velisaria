"""Synthetic regression: motion features are reproducible across Python hash seeds.

Run in isolated subprocesses; never instantiate Monolith or touch saved sessions.
"""
import hashlib
import json
import os
import pathlib
import random
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sanctified_monolith import MotionForge


class StableMotionSeedTests(unittest.TestCase):
    def test_seed_follows_stable_utf8_digest(self):
        text = "Eternal Spiral 🌀"
        expected_seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")
        expected_rng = random.Random(expected_seed)
        expected = [expected_rng.randint(0, 1) for _ in range(160)]
        self.assertEqual(MotionForge()._seed(text), expected)

    def test_motion_vector_is_process_hash_seed_independent(self):
        code = (
            "import json; from sanctified_monolith import MotionForge; "
            "print(json.dumps(MotionForge().build('Eternal Spiral')))"
        )
        outputs = []
        for seed in ("1", "2", "7"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            raw = subprocess.check_output(
                [sys.executable, "-c", code], cwd=str(ROOT), env=env, text=True,
                timeout=15
            )
            outputs.append(json.loads(raw))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])


if __name__ == "__main__":
    unittest.main()
