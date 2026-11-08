"""Synthetic, isolated regression coverage for the small Sanctified Monolith.

Tests fail closed on unreadable/corrupt history and interrupted saves.
Stdlib only; use disposable state. See DEV_NOTES.md and CHANGELOG.md.
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

    def test_duplicate_state_keys_cannot_erase_history(self):
        # Both positions are significant; Python's default json.load silently
        # keeps the last value and the next normal save would erase evidence.
        examples = (
            b'{"sessions":[{"marker":"valuable"}],"sessions":[]}',
            b'{"sessions":[{"marker":"valuable","marker":"replacement"}]}',
            b'{"sessions":[{"other":{"important":1,"important":2}}]}',
        )
        for original in examples:
            with self.subTest(original=original), tempfile.TemporaryDirectory() as d:
                path = pathlib.Path(d) / "state.json"
                path.write_bytes(original)
                with self.assertRaisesRegex(RuntimeError, "left unchanged"):
                    mod.Monolith(state_path=str(path))
                self.assertEqual(path.read_bytes(), original)
                self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())

    def test_nonfinite_json_numbers_cannot_enter_live_history(self):
        for constant in ("NaN", "Infinity", "-Infinity", "1e400", "-1e400"):
            original = ('{"sessions":[{"metrics":{"score":' + constant + '}}]}').encode()
            with self.subTest(constant=constant), tempfile.TemporaryDirectory() as d:
                path = pathlib.Path(d) / "state.json"
                path.write_bytes(original)
                with self.assertRaisesRegex(RuntimeError, "left unchanged"):
                    mod.Memory(str(path))
                self.assertEqual(path.read_bytes(), original)
                self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())

    def test_precision_losing_finite_decimals_refuse_before_save(self):
        # Ordinary finite float decoding can round a legitimate JSON number;
        # a subsequent normal save would permanently erase that distinction.
        samples = (
            "0.10000000000000001",
            "1.0000000000000001",
            "-1.0000000000000001",
            "1e-400",
            "-1e-400",
            "1.234567890123456789",
        )
        for literal in samples:
            with self.subTest(literal=literal), tempfile.TemporaryDirectory() as d:
                path = pathlib.Path(d) / "state.json"
                original = ('{"sessions":[{"metrics":{"score":' + literal + '}}]}').encode()
                path.write_bytes(original)
                with self.assertRaisesRegex(RuntimeError, "left unchanged"):
                    mod.Memory(str(path))
                self.assertEqual(path.read_bytes(), original)
                self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())

    def test_exactly_roundtrippable_finite_decimals_still_save(self):
        # Alternate exponent/zero spellings are fine if their numeric value
        # survives the live float representation and future JSON serialization.
        from decimal import Decimal
        for literal in ("0.1", "1.0", "1e0", "1e-320", "-0.0", "1.0000000000000002"):
            with self.subTest(literal=literal), tempfile.TemporaryDirectory() as d:
                path = pathlib.Path(d) / "state.json"
                original = ('{"sessions":[{"metrics":{"score":' + literal + '}}]}').encode()
                path.write_bytes(original)
                m = mod.Memory(str(path))
                m.state["sessions"].append({"marker": "new"})
                m.save()
                actual = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
                self.assertEqual(actual["sessions"][0]["metrics"]["score"], Decimal(literal))
                self.assertEqual(actual["sessions"][1], {"marker": "new"})
                self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())

    def test_excessive_json_nesting_fails_closed_without_rewrite(self):
        # Reader exhaustion should be a controlled startup refusal, not an
        # unhandled RecursionError followed by a risky user workaround.
        original = (b'{"sessions":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}')
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            path.write_bytes(original)
            with self.assertRaisesRegex(RuntimeError, "left unchanged"):
                mod.Memory(str(path))
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())

    def test_brackets_and_escaped_quotes_inside_strings_remain_valid(self):
        # The depth bound must count JSON containers, never syntax-like text.
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            value = {"sessions": [{"text": 'quoted "[{" ' + "[" * 600 + "}" * 600}]}
            original = json.dumps(value, ensure_ascii=False).encode("utf-8")
            path.write_bytes(original)
            memory = mod.Memory(str(path))
            self.assertEqual(memory.state, value)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())

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



class InterruptedSaveTests(unittest.TestCase):
    """Disposable state only: test exceptions and actual process termination before rename."""

    def test_existing_primary_with_orphan_temp_preserves_both(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            old = b'{"sessions": [{"marker": "committed"}]}'
            recovery = b'{"sessions": [{"marker": "uncommitted"}]}'
            path.write_bytes(old)
            pathlib.Path(str(path) + ".tmp").write_bytes(recovery)
            with self.assertRaisesRegex(RuntimeError, "temporary"):
                mod.Memory(str(path))
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(pathlib.Path(str(path) + ".tmp").read_bytes(), recovery)

    def test_missing_primary_with_orphan_temp_is_not_treated_as_new(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            recovery = b'{"sessions": [{"marker": "uncommitted"}]}'
            pathlib.Path(str(path) + ".tmp").write_bytes(recovery)
            with self.assertRaisesRegex(RuntimeError, "temporary"):
                mod.Memory(str(path))
            self.assertFalse(path.exists())
            self.assertEqual(pathlib.Path(str(path) + ".tmp").read_bytes(), recovery)

    def test_replace_failure_keeps_primary_and_temp_for_owner(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            old = b'{"sessions": [{"marker": "previous"}]}'
            path.write_bytes(old)
            memory = mod.Memory(str(path))
            memory.state["sessions"].append({"marker": "new"})
            with mock.patch.object(mod.os, "replace", side_effect=OSError("synthetic replace failure")):
                with self.assertRaisesRegex(OSError, "synthetic replace failure"):
                    memory.save()
            tmp = pathlib.Path(str(path) + ".tmp")
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(len(json.loads(tmp.read_text(encoding="utf-8"))["sessions"]), 2)
            with self.assertRaisesRegex(RuntimeError, "temporary"):
                mod.Memory(str(path))

    def test_save_refuses_to_overwrite_preexisting_temp(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            old = b'{"sessions": [{"marker": "committed"}]}'
            path.write_bytes(old)
            memory = mod.Memory(str(path))
            recovery = b'{"sessions": [{"marker": "recoverable"}]}'
            pathlib.Path(str(path) + ".tmp").write_bytes(recovery)
            memory.state["sessions"].append({"marker": "new"})
            with self.assertRaisesRegex(RuntimeError, "temporary"):
                memory.save()
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(pathlib.Path(str(path) + ".tmp").read_bytes(), recovery)

    def test_real_process_exit_before_replace_preserves_recovery_evidence(self):
        crash_script = (
            "import os, runpy, sys\n"
            "module = runpy.run_path(sys.argv[1])\n"
            "def crash_before_replace(*args): os._exit(37)\n"
            "os.replace = crash_before_replace\n"
            "module['Monolith'](state_path=sys.argv[2]).think('synthetic', 'hello')\n"
        )
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as d:
                path = pathlib.Path(d) / "state.json"
                old = b'{"sessions": [{"marker": "committed"}]}'
                if existing:
                    path.write_bytes(old)
                proc = subprocess.run(
                    [sys.executable, "-c", crash_script, str(SOURCE), str(path)],
                    cwd=d, text=True, capture_output=True, timeout=10, check=False,
                )
                self.assertEqual(proc.returncode, 37, proc.stderr)
                self.assertEqual(path.exists(), existing)
                if existing:
                    self.assertEqual(path.read_bytes(), old)
                tmp = pathlib.Path(str(path) + ".tmp")
                self.assertTrue(tmp.is_file())
                self.assertEqual(len(json.loads(tmp.read_text(encoding="utf-8"))["sessions"]),
                                 2 if existing else 1)
                before = tmp.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "temporary"):
                    mod.Memory(str(path))
                self.assertEqual(tmp.read_bytes(), before)



if __name__ == "__main__":
    unittest.main()
