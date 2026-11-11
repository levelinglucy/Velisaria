"""Disposable end-to-end learning, persistence, and refusal regressions."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import sanctified_monolith as mono


SOURCE = Path(mono.__file__).resolve()


def observation(event_id="a1", **changes):
    payload = {
        "op": "remember", "user": "synthetic", "context": "routes",
        "cue": "blue lamp", "answer": "choose left",
        "source": "fixture observation", "event_id": event_id,
    }
    payload.update(changes)
    return payload


def run_cli(root, requests, *options):
    proc = subprocess.run(
        [sys.executable, str(SOURCE), "--learning", "--origin-io", *options],
        cwd=root, input="\n".join(json.dumps(item) for item in requests) + "\n/quit\n",
        text=True, capture_output=True, timeout=15, check=False,
    )
    if proc.returncode:
        raise AssertionError(proc.stdout + proc.stderr)
    return [json.loads(line) for line in proc.stdout.splitlines()
            if line.startswith("{")]


class LearningIntegrationTests(unittest.TestCase):
    def test_opt_in_and_read_only_operations_do_not_create_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            disabled = mono.Monolith(str(path))
            with self.assertRaisesRegex(ValueError, "disabled"):
                disabled.learning_command(observation())
            enabled = mono.Monolith(str(path), learning=True)
            self.assertEqual(enabled.learning_command({"op": "sleep"})["processed"], 0)
            result = enabled.learning_command({
                "op": "recall", "user": "synthetic", "cue": "unknown",
            })
            self.assertEqual(result["status"], "unknown")
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_actual_response_uses_scoped_evidence_and_explicit_correction(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = mono.Monolith(str(Path(directory) / "state.json"), learning=True)
            before = engine.think("synthetic", "blue lamp", context="routes")
            self.assertNotIn("Recall:", before)
            engine.learning_command(observation())
            reply = engine.think("synthetic", " BLUE  LAMP ", context="routes")
            self.assertTrue(reply.startswith("Recall: choose left [evidence: a1]"), reply)
            self.assertNotIn("Recall:", engine.think("another", "blue lamp", "routes"))
            self.assertNotIn("Recall:", engine.think("synthetic", "blue lamp", "elsewhere"))
            engine.learning_command(observation("a2", answer="choose right"))
            disputed = engine.think("synthetic", "blue lamp", "routes")
            self.assertTrue(disputed.startswith("Recall conflict:"), disputed)
            engine.learning_command(observation(
                "a3", op="correct", answer="choose right", supersedes=["a1", "a2"],
            ))
            resolved = engine.think("synthetic", "blue lamp", "routes")
            self.assertTrue(resolved.startswith("Recall: choose right [evidence: a3]"))

    def test_existing_sessions_and_unknown_fields_survive_learning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            original = {"sessions": [{"text": "prior synthetic history", "extra": [1, True]}],
                        "legacy": {"symbols": ["spiral"], "custom": "preserve"}}
            path.write_text(json.dumps(original), encoding="utf-8")
            engine = mono.Monolith(str(path), learning=True)
            engine.learning_command(observation())
            engine.learning_command({"op": "sleep", "max_events": 1})
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored["sessions"], original["sessions"])
            self.assertEqual(stored["legacy"], original["legacy"])
            raw = copy.deepcopy(stored["associative_memory"]["events"])
            before = path.read_bytes()
            with mock.patch.object(engine.mem, "save", side_effect=AssertionError("unexpected save")):
                retry = engine.learning_command(observation())
                slept = engine.learning_command({"op": "sleep"})
            self.assertFalse(retry["created"])
            self.assertEqual(slept["processed"], 0)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(engine.learner.state["events"], raw)

    def test_failed_learning_save_restores_live_state_and_keeps_staging_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            engine = mono.Monolith(str(path), learning=True)
            engine.learning_command(observation())
            before = path.read_bytes()
            live = copy.deepcopy(engine.learner.state)
            with mock.patch.object(mono.os, "replace", side_effect=OSError("synthetic interruption")):
                with self.assertRaises(OSError):
                    engine.learning_command({"op": "sleep", "max_events": 1})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(engine.learner.state, live)
            self.assertEqual(engine.mem.state["associative_memory"], live)
            staged = Path(str(path) + ".tmp")
            self.assertTrue(staged.exists())
            self.assertEqual(json.loads(staged.read_text())["associative_memory"]["cursor"], 1)
            with self.assertRaises(RuntimeError):
                mono.Monolith(str(path), learning=True)
            self.assertTrue(staged.exists())

    def test_stale_learning_writer_is_refused_without_live_or_disk_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            first = mono.Monolith(str(path), learning=True)
            stale = mono.Monolith(str(path), learning=True)
            first.learning_command(observation())
            before = path.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "changed since"):
                stale.learning_command(observation("b1", cue="red lamp"))
            self.assertEqual(stale.learner.snapshot()["events"], 0)
            self.assertNotIn("associative_memory", stale.mem.state)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_invalid_learning_state_is_preserved_and_never_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            for invalid in (None, {"version": 99}, {"events": []}):
                with self.subTest(invalid=invalid):
                    path.write_text(json.dumps({"sessions": [], "associative_memory": invalid}))
                    before = path.read_bytes()
                    with self.assertRaises(ValueError):
                        mono.Monolith(str(path), learning=True)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_cli_learning_survives_a_fresh_process_and_changes_think_output(self):
        with tempfile.TemporaryDirectory() as directory:
            first = run_cli(directory, [observation(), {"op": "sleep", "max_events": 1}],
                            "--state", "experiment.json")
            self.assertTrue(all(item["ok"] for item in first), first)
            self.assertEqual(first[1]["result"]["processed"], 1)
            second = run_cli(directory, [
                observation("b1", context="other", answer="unrelated"),
                {"op": "sleep", "max_events": 1},
                {"op": "think", "user": "synthetic", "context": "routes", "text": "BLUE LAMP"},
                {"op": "recall", "user": "synthetic", "context": "other", "cue": "blue lamp"},
            ], "--state", "experiment.json")
            self.assertTrue(all(item["ok"] for item in second), second)
            self.assertTrue(second[2]["output"].startswith("Recall: choose left [evidence: a1]"))
            self.assertEqual(second[3]["result"]["answer"], "unrelated")
            self.assertEqual(second[3]["snapshot"]["learning"]["consolidated"], 2)
            self.assertFalse((Path(directory) / "sanctified_state.json").exists())

    def test_enabled_long_and_empty_thoughts_remain_ordinary_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = mono.Monolith(str(Path(directory) / "state.json"), learning=True)
            for text in ("", "word " * 200):
                reply = engine.think("synthetic", text)
                self.assertIn("refine w:", reply)
                self.assertNotIn("Recall:", reply)

    def test_invalid_json_operations_report_errors_without_learning_or_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            replies = run_cli(directory, [
                {"op": ["sleep"]}, {"op": "slepe"}, {"op": "sleep", "max_events": True},
                observation(source=""), {"op": "recall", "cue": ""},
            ])
            self.assertEqual(len(replies), 5)
            self.assertTrue(all(item["ok"] is False for item in replies), replies)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
