"""CLI syntax regressions using disposable working directories and no owner data."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"


def invoke(root, *args, stdin="/quit\n"):
    return subprocess.run(
        [sys.executable, str(SOURCE), *map(str, args)],
        cwd=root, input=stdin, text=True, capture_output=True,
        check=False, timeout=10,
    )


class CLIOptionTests(unittest.TestCase):
    def test_malformed_options_refuse_before_initializing_memory(self):
        cases = (
            ("--not-a-real-option",),
            ("--profile",),
            ("--profile", "--origin-io"),
            ("--origin-io", "--profile"),
            ("--origin-io", "--extra"),
        )
        for args in cases:
            with self.subTest(args=args), tempfile.TemporaryDirectory() as d:
                proc = invoke(d, *args)
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertIn("usage:", proc.stderr.lower())
                self.assertNotIn("traceback", proc.stderr.lower())
                self.assertNotIn("Sanctified Monolith", proc.stdout)
                self.assertEqual(list(pathlib.Path(d).iterdir()), [])

    def test_help_does_not_initialize_memory(self):
        with tempfile.TemporaryDirectory() as d:
            proc = invoke(d, "--help")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("--profile", proc.stdout)
            self.assertIn("--origin-io", proc.stdout)
            self.assertEqual(list(pathlib.Path(d).iterdir()), [])

    def test_valid_combined_flags_still_process_a_synthetic_request(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            profile = root / "profile.json"
            profile.write_text(
                json.dumps({"priors": {"compassion_bias": 0.8}}),
                encoding="utf-8",
            )
            proc = invoke(
                d, "--profile", profile, "--origin-io",
                stdin='{"user":"synthetic","text":"hello"}\n/quit\n',
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = proc.stdout.splitlines()
            self.assertTrue(lines[0].startswith("[origin-io] ready"), proc.stdout)
            response = json.loads(lines[1])
            self.assertTrue(response["ok"], response)
            self.assertEqual(response["snapshot"]["memory"]["sessions"], 1)
            stored = json.loads((root / "sanctified_state.json").read_text(encoding="utf-8"))
            self.assertEqual(len(stored["sessions"]), 1)


if __name__ == "__main__":
    unittest.main()
