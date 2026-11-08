"""Disposable, read-only checks for the standalone Velisaria inspector.

No historical memory or user records are used; tests write only synthetic
fixtures in temporary directories. See DEV_NOTES.md for the recovery boundary.
"""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "inspect_memory_state.py"
SPEC = importlib.util.spec_from_file_location("velisaria_state_inspector", SOURCE)
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)


class ReadOnlyInspectorTests(unittest.TestCase):
    def _snapshot(self, root):
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.iterdir() if p.is_file() and not p.is_symlink()
        }

    def _write(self, path, sessions, **extra):
        path.write_text(json.dumps(dict(sessions=sessions, **extra)), encoding="utf-8")

    def test_missing_or_primary_only_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            state = root / "state.json"
            self.assertEqual(inspector.inspect(str(state))["relationship"], "nothing_found")
            self.assertEqual(list(root.iterdir()), [])
            self._write(state, [{"private": "DO_NOT_PRINT"}], retained="yes")
            before = self._snapshot(root)
            result = inspector.inspect(str(state))
            self.assertEqual(result["relationship"], "primary_only")
            self.assertEqual(result["primary"]["sessions"], 1)
            self.assertNotIn("DO_NOT_PRINT", json.dumps(result))
            self.assertEqual(before, self._snapshot(root))

    def test_temporary_only_and_both_generations_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            state = root / "state.json"
            temp = root / "state.json.tmp"
            original = [{"text": "SECRET_A"}]
            self._write(temp, original + [{"text": "SECRET_B"}])
            self.assertEqual(inspector.inspect(str(state))["relationship"], "temporary_only")
            self._write(state, original)
            before = self._snapshot(root)
            report = inspector.inspect(str(state))
            self.assertEqual(report["relationship"], "primary_sessions_prefix_of_temporary")
            self.assertEqual(report["temporary"]["sessions"], 2)
            self.assertNotIn("SECRET_A", json.dumps(report))
            self.assertNotIn("SECRET_B", json.dumps(report))
            self.assertEqual(before, self._snapshot(root))

    def test_equivalent_primary_prefix_and_divergent_cases(self):
        with tempfile.TemporaryDirectory() as d:
            state = pathlib.Path(d) / "state.json"
            temp = pathlib.Path(str(state) + ".tmp")
            self._write(state, [{"a": 1}], kept=True)
            self._write(temp, [{"a": 1}], kept=True)
            self.assertEqual(inspector.inspect(str(state))["relationship"], "equivalent_data")
            self._write(state, [{"a": 1}, {"b": 2}], kept=True)
            self.assertEqual(inspector.inspect(str(state))["relationship"],
                             "temporary_sessions_prefix_of_primary")
            self._write(temp, [{"a": 1}], kept=False)
            self.assertEqual(inspector.inspect(str(state))["relationship"], "divergent")
            self._write(temp, [{"a": 3}], kept=True)
            self.assertEqual(inspector.inspect(str(state))["relationship"], "divergent")

    def test_distinct_json_scalar_types_and_numbers_never_look_equivalent(self):
        # Real precision/type losses in json.loads + Python equality formerly
        # made distinct copied generations appear equivalent.
        cases = [
            ('{"sessions":[{"score":0.10000000000000001}]}',
             '{"sessions":[{"score":0.1}]}'),
            ('{"sessions":[{"score":1e-400}]}',
             '{"sessions":[{"score":0.0}]}'),
            ('{"sessions":[{"score":1e400}]}',
             '{"sessions":[{"score":1e401}]}'),
            ('{"sessions":[{"flag":true}]}',
             '{"sessions":[{"flag":1}]}'),
            ('{"sessions":[{"flag":"1"}]}',
             '{"sessions":[{"flag":1}]}'),
            ('{"sessions":[],"flag":true}',
             '{"sessions":[],"flag":1}'),
        ]
        with tempfile.TemporaryDirectory() as d:
            state = pathlib.Path(d) / "state.json"
            temp = pathlib.Path(str(state) + ".tmp")
            for left, right in cases:
                with self.subTest(left=left, right=right):
                    state.write_text(left, encoding="utf-8")
                    temp.write_text(right, encoding="utf-8")
                    before = (state.read_bytes(), temp.read_bytes())
                    result = inspector.inspect(str(state))
                    self.assertEqual(result["primary"]["status"], "valid")
                    self.assertEqual(result["temporary"]["status"], "valid")
                    self.assertEqual(result["relationship"], "divergent")
                    self.assertEqual((state.read_bytes(), temp.read_bytes()), before)
                    self.assertNotIn("score", json.dumps(result))

    def test_session_prefix_requires_exact_numeric_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            state = pathlib.Path(d) / "state.json"
            temp = pathlib.Path(str(state) + ".tmp")
            state.write_text('{"sessions":[{"n":1e400}]}', encoding="utf-8")
            temp.write_text('{"sessions":[{"n":1e401},{"n":2}]}', encoding="utf-8")
            self.assertEqual(inspector.inspect(str(state))["relationship"], "divergent")
            # A genuine prefix remains recognized, even with large numbers.
            temp.write_text('{"sessions":[{"n":1e400},{"n":2}]}', encoding="utf-8")
            self.assertEqual(inspector.inspect(str(state))["relationship"],
                             "primary_sessions_prefix_of_temporary")

    def test_partial_malformed_and_duplicate_records_are_not_promoted(self):
        with tempfile.TemporaryDirectory() as d:
            state = pathlib.Path(d) / "state.json"
            temp = pathlib.Path(str(state) + ".tmp")
            self._write(state, [{"x": 1}])
            for broken in (b'{"sessions":[', b"\xff", b'{"sessions":[],"sessions":[]}',
                           b'{"sessions":NaN}', b'{"sessions":{}}'):
                with self.subTest(broken=broken):
                    temp.write_bytes(broken)
                    before = (state.read_bytes(), temp.read_bytes())
                    result = inspector.inspect(str(state))
                    self.assertEqual(result["relationship"], "undetermined")
                    self.assertIn(result["temporary"]["status"],
                                  ("invalid_json", "invalid_shape"))
                    self.assertEqual((state.read_bytes(), temp.read_bytes()), before)

    def test_non_regular_paths_not_opened(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            state = root / "state.json"
            target = root / "protected.json"
            target.write_bytes(b'{"sessions":[{"private":"KEEP"}]}')
            try:
                state.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks not supported on this platform")
            before = target.read_bytes()
            self.assertEqual(inspector.inspect(str(state))["primary"]["status"], "not_regular_file")
            self.assertEqual(target.read_bytes(), before)
            state.unlink()
            state.mkdir()
            self.assertEqual(inspector.inspect(str(state))["primary"]["status"], "not_regular_file")

    def test_oversized_file_is_not_loaded_or_modified(self):
        with tempfile.TemporaryDirectory() as d:
            state = pathlib.Path(d) / "state.json"
            with state.open("wb") as f:
                f.seek(inspector.MAX_BYTES)
                f.write(b"x")
            before = state.stat().st_size
            self.assertEqual(inspector.inspect(str(state))["primary"]["status"], "too_large")
            self.assertEqual(state.stat().st_size, before)

    def test_cli_emits_metadata_only_with_no_side_effects(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            state = root / "state.json"
            temp = root / "state.json.tmp"
            self._write(state, [{"user": "SECRET_USER"}])
            self._write(temp, [{"user": "SECRET_USER"}, {"text": "SECRET_TEXT"}])
            before = self._snapshot(root)
            proc = subprocess.run(
                [sys.executable, str(SOURCE), "--state", str(state)],
                cwd=d, capture_output=True, text=True, timeout=10, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["relationship"], "primary_sessions_prefix_of_temporary")
            self.assertNotIn("SECRET", proc.stdout + proc.stderr)
            self.assertEqual(before, self._snapshot(root))


if __name__ == "__main__":
    unittest.main()
