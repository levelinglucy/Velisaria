"""Failed-save regressions use only synthetic, disposable local memory files.

A request that reports an error must not be silently included in a later
successful session history. No owner memory or archived monolith is touched.
"""
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_failed_commit_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class FailedSessionCommitTests(unittest.TestCase):
    def test_failed_first_save_does_not_leak_into_later_success(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            monolith = mod.Monolith(state_path=str(path))
            with patch.object(monolith.mem, "save", side_effect=OSError("synthetic refusal")):
                with self.assertRaisesRegex(OSError, "synthetic refusal"):
                    monolith.think("synthetic", "failed first")
            self.assertEqual(monolith.mem.state["sessions"], [])
            self.assertFalse(path.exists())
            self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())

            monolith.think("synthetic", "successful second")
            saved = json.loads(path.read_text(encoding="utf-8"))["sessions"]
            self.assertEqual([item["text"] for item in saved], ["successful second"])
            self.assertEqual(monolith.mem.state["sessions"], saved)

    def test_stale_writer_refusal_does_not_leave_phantom_session(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            first = mod.Monolith(state_path=str(path))
            stale = mod.Monolith(state_path=str(path))
            first.think("writer-a", "committed")
            committed = path.read_bytes()

            with self.assertRaisesRegex(RuntimeError, "changed since load"):
                stale.think("writer-b", "refused")
            self.assertEqual(stale.mem.state["sessions"], [])
            self.assertEqual(path.read_bytes(), committed)
            self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())

    def test_failed_replace_preserves_recovery_evidence_but_not_live_phantom(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            original = b'{"sessions":[{"marker":"already committed"}]}'
            path.write_bytes(original)
            monolith = mod.Monolith(state_path=str(path))

            with patch.object(mod.os, "replace", side_effect=OSError("synthetic rename error")):
                with self.assertRaisesRegex(OSError, "synthetic rename error"):
                    monolith.think("synthetic", "uncommitted")
            self.assertEqual(
                monolith.mem.state["sessions"], [{"marker": "already committed"}]
            )
            self.assertEqual(path.read_bytes(), original)
            # The complete staging file is preserved for manual recovery.
            self.assertTrue(pathlib.Path(str(path) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
