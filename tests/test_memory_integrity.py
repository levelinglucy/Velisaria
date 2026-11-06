"""Synthetic, isolated regression coverage for the small Sanctified Monolith.

Development summary (2026-11-06): detect and prevent silent loss of session
history during startup after a truncated, unreadable, or malformed state file.
Runs with Python stdlib only; does not access a user's actual history.
Next: verify on Pythonista and test interruption around state-file replacement.
See DEV_NOTES.md and CHANGELOG.md.
"""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_sanctified_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class MemoryIntegrityTests(unittest.TestCase):
    def test_fresh_start_and_reload_genuine_history(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            m = mod.Monolith(state_path=str(path))
            self.assertFalse(path.exists())
            result = m.think("test-user", "hello")
            self.assertIn("stab:", result)
            self.assertEqual(mod.Monolith(state_path=str(path)).snapshot()["memory"]["sessions"], 1)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["sessions"][0]["user"], "test-user")

    def test_truncated_json_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            original = b'{"sessions": [{"t": 123, "text": "important"}'
            path.write_bytes(original)
            with self.assertRaisesRegex(RuntimeError, "left unchanged"):
                mod.Monolith(state_path=str(path))
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse((pathlib.Path(d) / "state.json.tmp").exists())

    def test_unreadable_utf8_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            original = b'{"sessions": "\xff"}'
            path.write_bytes(original)
            with self.assertRaises(RuntimeError):
                mod.Memory(str(path))
            self.assertEqual(path.read_bytes(), original)

    def test_invalid_top_level_schema_is_not_overwritten(self):
        for raw in (b"[]", b"{}", b'{"sessions": null}', b'{"sessions": "history"}'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as d:
                path = pathlib.Path(d) / "state.json"
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "Invalid Velisaria memory format"):
                    mod.Monolith(state_path=str(path))
                self.assertEqual(path.read_bytes(), raw)

    def test_forward_compatible_top_level_fields_survive(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            original = {"sessions": [{"marker": "legacy"}], "other": {"retain": True}}
            path.write_text(json.dumps(original), encoding="utf-8")
            m = mod.Monolith(state_path=str(path))
            self.assertEqual(m.snapshot()["memory"]["sessions"], 1)
            m.think("test", "hello")
            actual = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(actual["other"], original["other"])
            self.assertEqual(actual["sessions"][0], original["sessions"][0])

    def test_stdio_cli_declines_corrupt_memory_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "sanctified_state.json"
            original = b'{"sessions": ['
            path.write_bytes(original)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            p = subprocess.run(
                [sys.executable, str(SOURCE), "--origin-io"],
                input='{"user":"synthetic","text":"hello"}\n/quit\n',
                text=True, capture_output=True, cwd=d, timeout=10, check=False,
            )
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("file left unchanged", p.stderr)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
            self.assertFalse((pathlib.Path(d) / "sanctified_state.json.tmp").exists())

    def test_stdio_cli_valid_synthetic_request(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run(
                [sys.executable, str(SOURCE), "--origin-io"],
                input='{"user":"synthetic","text":"hello"}\n/quit\n',
                text=True, capture_output=True, cwd=d, timeout=10, check=False,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            lines = p.stdout.splitlines()
            self.assertTrue(lines[0].startswith("[origin-io] ready"))
            response = json.loads(lines[1])
            self.assertTrue(response["ok"])
            self.assertEqual(response["snapshot"]["memory"]["sessions"], 1)
            self.assertEqual(len(json.loads((pathlib.Path(d) / "sanctified_state.json").read_text())["sessions"]), 1)


if __name__ == "__main__":
    unittest.main()
