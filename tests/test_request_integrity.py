"""Request refusal must precede live changes and synthetic state-file writes."""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import sanctified_monolith as mono


SOURCE = Path(mono.__file__).resolve()
OBSERVATION = {
    "op": "remember", "user": "synthetic", "context": "routes",
    "cue": "blue lamp", "answer": "left", "source": "fixture",
    "event_id": "request-fixture",
}


def malformed_json_lines():
    base = json.dumps(OBSERVATION)[:-1]
    cases = [
        ("duplicate root", base + ', "answer":"right"}'),
        ("duplicate nested", base + ', "extra":{"x":1,"x":2}}'),
        ("duplicate in array", base + ', "extra":[{"x":1,"x":2}]}'),
        ("deep containers", base + ', "extra":' + '[' * 300 + '0' + ']' * 300 + '}'),
        ("syntax", '{"op":}'),
    ]
    for number in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999",
                   "1e-999", "0.1234567890123456789012345"):
        cases.append((number, base + ', "extra":{"number":' + number + '}}'))
    cases.extend(("nonobject " + raw, raw) for raw in ("[]", "null", "1", '"request"'))
    return cases


def origin_exchange(engine, lines):
    output = io.StringIO()
    incoming = io.StringIO("\n".join(lines) + "\n/quit\n")
    with mock.patch.object(mono.sys, "stdin", incoming), redirect_stdout(output):
        mono.OriginEngineAdapter(engine).loop_stdio()
    printed = output.getvalue().splitlines()
    responses = [json.loads(line) for line in printed if line.startswith("{")]
    return printed, responses


def live_state(engine):
    return copy.deepcopy({
        "memory": engine.mem.state,
        "mesh": engine.mesh.nodes,
        "governance": (vars(engine.gov.super), vars(engine.gov.apn)),
        "empathy": vars(engine.empathy),
        "refiner": vars(engine.rte),
        "profile": vars(engine.profile),
        "applied_profile_stamp": engine._applied_profile_stamp,
        "learning": None if engine.learner is None else engine.learner.state,
    })


class RequestIntegrityTests(unittest.TestCase):
    def assert_invalid_response(self, response):
        self.assertIs(response["ok"], False, response)
        self.assertEqual(response.get("error_code"), "invalid_request", response)
        self.assertIsInstance(response.get("error"), str)
        self.assertTrue(response["error"])

    def test_origin_strict_json_refuses_before_changes_and_recovers(self):
        cases = malformed_json_lines()
        with tempfile.TemporaryDirectory() as directory:
            engine = mono.Monolith(str(Path(directory) / "state.json"), learning=True)
            before = live_state(engine)
            # Brackets and escaped quotes inside a string are not nesting.
            valid = json.dumps({"op": "learning-status", "extra": '\\"' + '[' * 300})
            printed, responses = origin_exchange(engine, [raw for _, raw in cases] + [valid])
            self.assertTrue(printed[0].startswith("[origin-io] ready;"))
            self.assertEqual(printed[-1], "[origin-io] bye")
            self.assertEqual(len(responses), len(cases) + 1)
            for (label, _), response in zip(cases, responses):
                with self.subTest(case=label):
                    self.assert_invalid_response(response)
            self.assertIs(responses[-1]["ok"], True)
            self.assertEqual(responses[-1]["result"]["events"], 0)
            self.assertEqual(live_state(engine), before)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_interactive_memory_uses_same_strict_json_and_recovers(self):
        cases = malformed_json_lines()
        incoming = "\n".join("/memory " + raw for _, raw in cases)
        incoming += '\n/memory {"op":"learning-status"}\n/quit\n'
        with tempfile.TemporaryDirectory() as directory:
            proc = subprocess.run(
                [sys.executable, str(SOURCE), "--learning", "--state", "state.json"],
                cwd=directory, input=incoming, text=True, capture_output=True,
                timeout=15, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(proc.stdout.startswith("Sanctified Monolith"))
            self.assertTrue(proc.stdout.rstrip().endswith("bye."))
            self.assertEqual(proc.stdout.count("memory error:"), len(cases), proc.stdout)
            self.assertIn('"events": 0', proc.stdout)
            self.assertIn('"pending": 0', proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_origin_classifies_bad_operations_and_learning_arguments(self):
        requests = [{"op": value} for value in (None, [], {}, 1, True, "unknown")]
        requests += [
            {"op": "sleep", "max_events": True},
            {"op": "sleep", "max_events": 257},
            {"op": "recall", "cue": ""},
            {"op": "recall", "cue": "blue lamp", "mode": "unknown"},
            dict(OBSERVATION, source=""),
            dict(OBSERVATION, answer=[]),
            dict(OBSERVATION, event_id=""),
            dict(OBSERVATION, op="correct", supersedes=[]),
            dict(OBSERVATION, op="correct", supersedes=["absent"]),
        ]
        with tempfile.TemporaryDirectory() as directory:
            engine = mono.Monolith(str(Path(directory) / "state.json"), learning=True)
            before = live_state(engine)
            _, responses = origin_exchange(
                engine, [json.dumps(item) for item in requests] + ['{"op":"learning-status"}'])
            self.assertEqual(len(responses), len(requests) + 1)
            for index, response in enumerate(responses[:-1]):
                with self.subTest(request=index):
                    self.assert_invalid_response(response)
            self.assertIs(responses[-1]["ok"], True)
            self.assertEqual(live_state(engine), before)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_think_validates_scope_and_text_before_all_side_effects(self):
        self.assertTrue(issubclass(mono.InvalidRequest, ValueError))
        invalid_scope = (None, [], {}, 7, True, b"bytes", "", " \t\n", "x" * 513, "\ud800")
        invalid_text = (None, [], {}, 7, True, b"bytes", "\ud800")
        cases = []
        for field in ("user", "context"):
            for value in invalid_scope:
                for text in ("ordinary", "", "long " * 150):
                    payload = {"user": "synthetic", "context": "routes", "text": text}
                    payload[field] = value
                    cases.append((field, payload))
        cases += [("text", {"user": "synthetic", "context": "routes", "text": value})
                  for value in invalid_text]
        for learning in (False, True):
            with self.subTest(learning=learning), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = root / "profile.json"
                profile.write_text('{"priors":{"compassion_bias":0.4}}', encoding="utf-8")
                engine = mono.Monolith(str(root / "state.json"), str(profile), learning=learning)
                before = live_state(engine)
                # An invalid request must not trigger even a valid pending reload.
                profile.write_text('{"priors":{"compassion_bias":0.876}}', encoding="utf-8")
                profile_bytes = profile.read_bytes()
                adapter = mono.OriginEngineAdapter(engine)
                with mock.patch.object(engine.profile, "load", wraps=engine.profile.load) as reload_, \
                     mock.patch.object(engine.mesh, "step", wraps=engine.mesh.step) as mesh_step, \
                     mock.patch.object(engine.mem, "save", wraps=engine.mem.save) as save:
                    for entrypoint in ("direct", "adapter"):
                        for index, (field, payload) in enumerate(cases):
                            with self.subTest(entrypoint=entrypoint, field=field, case=index):
                                with self.assertRaises(mono.InvalidRequest):
                                    if entrypoint == "direct":
                                        engine.think(**payload)
                                    else:
                                        adapter.handle(payload)
                    reload_.assert_not_called()
                    mesh_step.assert_not_called()
                    save.assert_not_called()
                self.assertEqual(live_state(engine), before)
                self.assertEqual(profile.read_bytes(), profile_bytes)
                self.assertEqual(sorted(p.name for p in root.iterdir()), ["profile.json"])

    def test_origin_think_validation_has_error_code_in_both_modes(self):
        for learning in (False, True):
            with self.subTest(learning=learning), tempfile.TemporaryDirectory() as directory:
                engine = mono.Monolith(str(Path(directory) / "state.json"), learning=learning)
                requests = [
                    {"user": [], "text": ""},
                    {"user": "synthetic", "context": "", "text": "long " * 150},
                    {"user": "synthetic", "text": "\ud800"},
                ]
                _, responses = origin_exchange(engine, [json.dumps(item) for item in requests]
                                               + ['{"user":"synthetic","text":"valid next line"}'])
                for response in responses[:-1]:
                    self.assert_invalid_response(response)
                self.assertIs(responses[-1]["ok"], True)
                sessions = json.loads((Path(directory) / "state.json").read_text())["sessions"]
                self.assertEqual([entry["text"] for entry in sessions], ["valid next line"])
                self.assertFalse((Path(directory) / "state.json.tmp").exists())

    def test_valid_empty_long_and_utf8_thoughts_remain_accepted(self):
        for learning in (False, True):
            with self.subTest(learning=learning), tempfile.TemporaryDirectory() as directory:
                engine = mono.Monolith(str(Path(directory) / "state.json"), learning=learning)
                adapter = mono.OriginEngineAdapter(engine)
                for text in ("", "long thought " * 400):
                    self.assertIsInstance(engine.think("u" * 512, text, "c" * 512), str)
                    self.assertIs(adapter.handle({"user": "Zoë", "context": "森", "text": text})["ok"], True)
                self.assertEqual(len(engine.mem.state["sessions"]), 4)

    def test_storage_refusals_are_not_classified_as_invalid_requests(self):
        for failure in (ValueError, RuntimeError, OSError):
            for request in ({"user": "synthetic", "text": "valid thought"}, OBSERVATION):
                with self.subTest(error=failure.__name__, op=request.get("op", "think")), \
                     tempfile.TemporaryDirectory() as directory:
                    engine = mono.Monolith(str(Path(directory) / "state.json"), learning=True)
                    with mock.patch.object(engine.mem, "save", side_effect=failure("synthetic storage refusal")):
                        _, responses = origin_exchange(engine, [json.dumps(request), '{"op":"learning-status"}'])
                    self.assertIs(responses[0]["ok"], False)
                    self.assertEqual(responses[0]["error"], "synthetic storage refusal")
                    self.assertNotEqual(responses[0].get("error_code"), "invalid_request")
                    self.assertIs(responses[1]["ok"], True)
                    self.assertEqual(engine.mem.state["sessions"], [])
                    self.assertEqual(engine.learner.snapshot()["events"], 0)
                    self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
