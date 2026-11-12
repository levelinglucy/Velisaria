"""Regression tests for the large monolith's history-preserving snapshot store."""

import copy
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone
import random
from types import SimpleNamespace
import unittest
from unittest import mock

from velisara_runtime import (
    SnapshotStore, SnapshotLoadError, SnapshotSaveError,
    decode_pairs, encode_pairs, strict_json_loads,
    ContinuityState, decode_state, encode_state,
)


class SnapshotStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "state.json"
        self.staging = Path(str(self.path) + ".tmp")

    def committed(self, state=None):
        store = SnapshotStore(self.path)
        store.load()
        store.save({"history": ["original"]} if state is None else state)
        return store

    def test_default_is_detached_and_absent_file_not_created(self):
        default = {"working_memory": [], "future_extension": {"keep": [1]}}
        store = SnapshotStore(self.path)
        loaded = store.load(default)
        loaded["future_extension"]["keep"].append(2)
        self.assertEqual(default["future_extension"]["keep"], [1])
        self.assertFalse(self.path.exists())
        store.save(loaded)
        self.assertEqual(SnapshotStore(self.path).load(), loaded)

    def test_round_trip_unknown_fields_pairs_and_long_history(self):
        history = [{"content": str(i), "intensity": 0.1} for i in range(300)]
        pairs = {("Fire", "Root"): 2, ("a::b", "c"): 0}
        state = {"working_memory": history, "co_occurrence": encode_pairs(pairs),
                 "future_extension": {"untouched": [False, None, {"x": "∞"}]}}
        store = self.committed(state)
        loaded = SnapshotStore(self.path).load()
        self.assertEqual(loaded, state)
        self.assertEqual(decode_pairs(loaded["co_occurrence"]), pairs)
        # Consecutive writes update the writer's own byte fingerprint.
        loaded["working_memory"].append({"content": "new", "intensity": 1.0})
        store.save(loaded)
        self.assertEqual(len(SnapshotStore(self.path).load()["working_memory"]), 301)

    def test_in_memory_has_the_same_validation_and_no_aliases(self):
        store = SnapshotStore(None)
        result = store.load({"history": ["original"]})
        result["history"].append("unsaved")
        self.assertEqual(store.load(), {"history": ["original"]})
        candidate = {"history": ["next"]}
        returned = store.save(candidate)
        returned["history"].append("mutated result")
        candidate["history"].append("mutated input")
        self.assertEqual(store.load(), {"history": ["next"]})
        with self.assertRaises(SnapshotSaveError):
            store.save({"invalid": float("nan")})
        self.assertEqual(store.load(), {"history": ["next"]})

    def test_existing_state_cannot_be_saved_without_loading(self):
        self.committed()
        before = self.path.read_bytes()
        with self.assertRaises(SnapshotSaveError):
            SnapshotStore(self.path).save({"history": []})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.staging.exists())

    def test_corrupt_ambiguous_and_lossy_json_never_becomes_empty_history(self):
        bad = [b'{"history":', b'[]', b'{"history": [], "history": [1]}',
               b'{"other": {"x": 1, "x": 2}}', b'{"x": NaN}',
               b'{"x": Infinity}', b'{"x": -Infinity}', b'{"x": 1e999}',
               b'{"x": 1e-999}', b'{"x": 1.0000000000000001}', b'\xff']
        for raw in bad:
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaises(SnapshotLoadError):
                    SnapshotStore(self.path).load({"history": []})
                self.assertEqual(self.path.read_bytes(), raw)
                self.assertFalse(self.staging.exists())

    def test_deep_json_refused_but_quoted_brackets_allowed(self):
        raw = '{"x":' + '[' * 256 + '0' + ']' * 256 + '}'
        self.path.write_text(raw, encoding="utf-8")
        with self.assertRaises(SnapshotLoadError):
            SnapshotStore(self.path).load()
        quoted = {"x": "[" * 1000 + '\\"' + "]" * 1000}
        self.assertEqual(strict_json_loads(json.dumps(quoted)), quoted)

    def test_failed_serialization_does_not_create_staging_or_modify_primary(self):
        store = self.committed()
        before = self.path.read_bytes()
        cyclic = {}
        cyclic["self"] = cyclic
        candidates = [[], {"nan": float("nan")}, {"object": object()},
                      {"keys": {1: "numeric", "1": "text"}},
                      {"pairs": {("a", "b"): 1}}, cyclic]
        for candidate in candidates:
            with self.subTest(candidate_type=type(candidate).__name__):
                with self.assertRaises(SnapshotSaveError):
                    store.save(candidate)
                self.assertEqual(self.path.read_bytes(), before)
                self.assertFalse(self.staging.exists())
        store.save({"history": ["original", "valid retry"]})

    def test_existing_and_missing_primary_stale_writers_are_refused(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if self.path.exists():
                    self.path.unlink()
                if existing:
                    self.committed()
                first, stale = SnapshotStore(self.path), SnapshotStore(self.path)
                first.load()
                stale.load()
                first.save({"history": ["first writer"]})
                before = self.path.read_bytes()
                with self.assertRaises(SnapshotSaveError):
                    stale.save({"history": ["stale writer"]})
                self.assertEqual(self.path.read_bytes(), before)
                self.assertFalse(self.staging.exists())

    def test_external_byte_changes_and_deletion_are_refused(self):
        for changed in (b'{"history": ["external"]}', None):
            with self.subTest(changed=changed):
                store = self.committed()
                if changed is None:
                    self.path.unlink()
                else:
                    self.path.write_bytes(changed)
                with self.assertRaises(SnapshotSaveError):
                    store.save({"history": ["local"]})
                self.assertEqual(self.path.read_bytes() if self.path.exists() else None,
                                 changed)
                self.assertFalse(self.staging.exists())

    def test_crlf_source_can_be_saved_and_saved_again(self):
        self.path.write_bytes(b'{\r\n  "history": []\r\n}\r\n')
        store = SnapshotStore(self.path)
        loaded = store.load()
        store.save(loaded)
        store.save({"history": ["next"]})

    def test_orphan_temporary_blocks_load_and_save_without_overwrite(self):
        store = self.committed()
        before = self.path.read_bytes()
        self.staging.write_bytes(b'partial recovery evidence')
        with self.assertRaises(SnapshotLoadError):
            SnapshotStore(self.path).load()
        with self.assertRaises(SnapshotSaveError):
            store.save({"history": ["next"]})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.staging.read_bytes(), b'partial recovery evidence')
        self.path.unlink()
        with self.assertRaises(SnapshotLoadError):
            SnapshotStore(self.path).load()
        self.assertFalse(self.path.exists())

    def test_sync_and_replace_failures_keep_primary_and_staging(self):
        for operation in ("fsync", "replace"):
            with self.subTest(operation=operation):
                if self.staging.exists():
                    self.staging.unlink()  # Disposable previous test fixture only.
                store = self.committed()
                before = self.path.read_bytes()
                with mock.patch("velisara_runtime.os." + operation,
                                side_effect=OSError("injected failure")):
                    with self.assertRaises(SnapshotSaveError):
                        store.save({"history": ["original", "candidate"]})
                self.assertEqual(self.path.read_bytes(), before)
                self.assertTrue(self.staging.exists())
                self.assertEqual(strict_json_loads(self.staging.read_bytes()),
                                 {"history": ["original", "candidate"]})

    def test_primary_and_staging_symlinks_are_refused(self):
        target = self.path.with_name("real.json")
        target.write_bytes(b'{"history": ["original"]}')
        self.path.symlink_to(target)
        with self.assertRaises(SnapshotLoadError):
            SnapshotStore(self.path).load()
        self.assertTrue(self.path.is_symlink())
        self.path.unlink()
        store = SnapshotStore(self.path)
        store.load()
        self.staging.symlink_to(target)
        with self.assertRaises(SnapshotSaveError):
            store.save({"history": []})
        self.assertTrue(self.staging.is_symlink())
        self.assertEqual(target.read_bytes(), b'{"history": ["original"]}')

    def test_symlink_substitution_after_load_is_refused(self):
        store = self.committed()
        target = self.path.with_name("real.json")
        self.path.rename(target)
        self.path.symlink_to(target)
        with self.assertRaises(SnapshotSaveError):
            store.save({"history": ["next"]})
        self.assertTrue(self.path.is_symlink())
        self.assertFalse(self.staging.exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixture requires os.mkfifo")
    def test_fifo_refused_before_open(self):
        os.mkfifo(self.path)
        # An accidental open would block; explicitly ensure it is never reached.
        with mock.patch("builtins.open", side_effect=AssertionError("opened FIFO")):
            with self.assertRaises(SnapshotLoadError):
                SnapshotStore(self.path).load()

    def test_directory_refused_without_changes(self):
        self.path.mkdir()
        with self.assertRaises(SnapshotLoadError):
            SnapshotStore(self.path).load()
        self.assertTrue(self.path.is_dir())


class MythosPairSchemaTests(unittest.TestCase):
    def test_pair_records_are_explicit_and_do_not_alias_input(self):
        source = {("Fire", "Root"): 3}
        records = encode_pairs(source)
        self.assertEqual(records, [{"symbols": ["Fire", "Root"], "count": 3}])
        self.assertEqual(decode_pairs(records), source)
        self.assertEqual(encode_pairs({}), [])
        self.assertEqual(decode_pairs([]), {})

    def test_ambiguous_or_invalid_records_are_rejected(self):
        valid = {"symbols": ["a", "b"], "count": 1}
        invalid = [{}, [valid, copy.deepcopy(valid)],
                   [{"symbols": ["a"], "count": 1}],
                   [{"symbols": ["a", "b"], "count": True}],
                   [{"symbols": ["a", "b"], "count": -1}],
                   [{"symbols": ["a", 1], "count": 1}],
                   [dict(valid, extra="unknown")]]
        for records in invalid:
            with self.subTest(records=records), self.assertRaises(ValueError):
                decode_pairs(records)
        for pairs in ({"a,b": 1}, {("a", "b"): True}, {("a",): 1}):
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                encode_pairs(pairs)


class SymbolicContinuityTests(unittest.TestCase):
    def owner_and_state(self, path=None):
        owner = SimpleNamespace(rng=random.Random(7), turn=0,
                                learning_enabled=False, learner=None,
                                _dormant_learning=None, tags={"spiral"})
        owner.organ = SimpleNamespace(vel=owner, history=[], relations={})
        state = ContinuityState(owner, path, ["organ"], transient_names=(
            "rng", "learning_enabled", "learner", "_dormant_learning"))
        return owner, state

    def test_codec_preserves_tuple_keys_sets_datetime_and_tag_shaped_user_data(self):
        original = {("left", "right"): {"symbols": {"∞", "spiral"}},
                    "timestamp": datetime(2026, 1, 2, tzinfo=timezone.utc, fold=1),
                    "ordinary": {"kind": "tuple", "items": [1, 2]},
                    "tuple": (1, False, None)}
        encoded = json.loads(json.dumps(encode_state(original)))
        decoded = decode_state(encoded)
        self.assertEqual(decoded, original)
        self.assertEqual(decoded["timestamp"].fold, 1)
        for bad in (object(), float("nan"), b"unsupported"):
            with self.assertRaises(ValueError):
                encode_state(bad)
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(ValueError):
            encode_state(cycle)

    def test_malformed_tagged_state_is_rejected(self):
        invalid = [[], {"kind": "execute", "items": []},
                   {"kind": "dict", "items": [["a", 1], ["a", 2]]},
                   {"kind": "set", "items": [1, 1]},
                   {"kind": "list", "items": [], "unknown": True},
                   {"kind": "datetime", "value": "bad", "fold": 0}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_state(value)

    def test_restore_preserves_organs_and_rolls_back_new_dynamic_state(self):
        owner, state = self.owner_and_state()
        state.load()
        organ = owner.organ
        before = state.snapshot()
        old_rng = owner.rng.getstate()
        owner.organ.history.append("uncommitted")
        owner.organ.added_by_turn = {"new": True}
        owner.dynamic_symbolic_data = {("left", "right"): ["uncommitted"]}
        owner.turn += 1
        owner.rng.random()
        state.restore(before)
        self.assertIs(owner.organ, organ)
        self.assertIs(owner.organ.vel, owner)
        self.assertEqual(owner.organ.history, [])
        self.assertFalse(hasattr(owner, "dynamic_symbolic_data"))
        self.assertFalse(hasattr(owner.organ, "added_by_turn"))
        self.assertEqual(owner.rng.getstate(), old_rng)
        self.assertEqual(owner.turn, 0)

    def test_invalid_organ_shape_refuses_before_any_live_change(self):
        owner, state = self.owner_and_state()
        state.load()
        before = state.snapshot()
        malformed = copy.deepcopy(before)
        data = decode_state(malformed["organs"]["organ"])
        data["history"] = "not a list"
        malformed["organs"]["organ"] = encode_state(data)
        symbolic = decode_state(malformed["symbolic_state"])
        symbolic["turn"] = 999
        malformed["symbolic_state"] = encode_state(symbolic)
        with self.assertRaises(ValueError):
            state.restore(malformed)
        self.assertEqual(state.snapshot(), before)

    def test_unknown_extensions_and_dormant_evidence_survive_reload(self):
        from associative_memory import AssociativeMemory
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "continuity.json"
            owner, state = self.owner_and_state(path)
            state.load()
            learner = AssociativeMemory()
            learner.observe("fixture", "scope", "blue lamp", "left", "fixture", event_id="one")
            incoming = state.snapshot()
            incoming["future_extension"] = {"retain": True}
            incoming["organs"]["future_organ"] = encode_state({"items": [1]})
            incoming["associative_memory"] = learner.state
            state.restore(incoming)
            state.save()
            restarted, loaded = self.owner_and_state(path)
            restored = loaded.load()
            self.assertEqual(restored["future_extension"], {"retain": True})
            self.assertEqual(decode_state(restored["organs"]["future_organ"]), {"items": [1]})
            self.assertEqual(restarted._dormant_learning, learner.state)
            self.assertIsNone(restarted.learner)

    def test_bad_saved_schema_cannot_be_overwritten_after_refused_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "continuity.json"
            owner, state = self.owner_and_state(path)
            state.load()
            invalid = state.snapshot()
            invalid["schema_version"] = 999
            path.write_text(json.dumps(invalid), encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaises(SnapshotLoadError):
                state.load()
            with self.assertRaises(SnapshotSaveError):
                state.save()
            self.assertEqual(path.read_bytes(), before)


class LargeCoreStateValidationTests(unittest.TestCase):
    def test_malformed_saved_profile_keeps_live_state_and_disk_evidence(self):
        from velisara_monolith_final_fixed_empathy import Velisara
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            engine = Velisara(state_file=path)
            engine.profile.record_preference("tone", "gentle")
            engine.save_state()
            before = engine._continuity.snapshot()
            invalid = copy.deepcopy(before)
            profile = decode_state(invalid["organs"]["profile"])
            profile["preferences"]["tone"] = 42
            invalid["organs"]["profile"] = encode_state(profile)
            path.write_text(json.dumps(invalid), encoding="utf-8")
            evidence = path.read_bytes()
            with self.assertRaises(SnapshotLoadError):
                engine.load_state()
            self.assertEqual(engine._continuity.snapshot(), before)
            self.assertEqual(path.read_bytes(), evidence)
            with self.assertRaises(SnapshotSaveError):
                engine.save_state()
            self.assertEqual(path.read_bytes(), evidence)
            self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_invalid_core_records_are_refused_before_any_live_restore(self):
        from velisara_monolith_final_fixed_empathy import Velisara
        invalid_fields = [
            ("profile", "preferences", {"ethics_priority": ["care", "care"]}),
            ("conversation", "max_history", 2.5),
            ("empathy", "sentiment_dict", {"positive": {1}, "negative": {"sad"}}),
            ("empathy", "history", ["not a sentiment"]),
            ("empathy", "mode", "unrecognized"),
            ("empathy", "last_score", "high"),
            ("emotion", "current_emotion", True),
            ("emotion", "last_label", []),
            ("mythos_engine", "co_occurrence", {("Fire", "Root"): 1.5}),
            ("memory_manager", "log", "cannot replace the property"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            engine = Velisara(state_file=path)
            engine.save_state()
            before = engine._continuity.snapshot()
            before_bytes = path.read_bytes()
            for organ, field, value in invalid_fields:
                with self.subTest(organ=organ, field=field):
                    candidate = copy.deepcopy(before)
                    data = decode_state(candidate["organs"][organ])
                    data[field] = value
                    candidate["organs"][organ] = encode_state(data)
                    with self.assertRaises(ValueError):
                        engine._continuity.restore(candidate)
                    self.assertEqual(engine._continuity.snapshot(), before)
                    self.assertEqual(path.read_bytes(), before_bytes)
                    self.assertFalse(Path(str(path) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
