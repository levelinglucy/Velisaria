"""File-sync ordering and pre-publication failures on disposable synthetic state.

These checks observe real temporary-file bytes and inject ordinary exceptions.
They do not establish power-loss durability, directory-entry persistence,
multiwriter safety, or iPhone/Pythonista filesystem behavior.
"""

import builtins
import copy
from contextlib import contextmanager
import errno
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from associative_memory import AssociativeMemory
import sanctified_monolith as mono


class _TrackedTemporaryFile:
    """Wrap only the exclusive staging handle; its underlying writes are real."""

    def __init__(self, handle, events, fail_flush):
        self.handle = handle
        self.events = events
        self.fail_flush = fail_flush

    def __enter__(self):
        self.handle.__enter__()
        return self

    def __exit__(self, *args):
        try:
            return self.handle.__exit__(*args)
        finally:
            self.events.append("close")

    def flush(self):
        if self.fail_flush:
            raise OSError(errno.EIO, "synthetic flush failure")
        self.handle.flush()
        self.events.append("flush")

    def __getattr__(self, name):
        return getattr(self.handle, name)


@contextmanager
def _track_temporary_file(path, fail_flush=False):
    events, handles = [], []

    def tracked_open(filename, mode="r", *args, **kwargs):
        handle = builtins.open(filename, mode, *args, **kwargs)
        if str(filename) == str(path) and mode == "x":
            wrapped = _TrackedTemporaryFile(handle, events, fail_flush)
            handles.append(wrapped)
            return wrapped
        return handle

    with patch.object(mono, "open", tracked_open, create=True):
        yield events, handles


class MemoryFileSyncTests(unittest.TestCase):
    def test_full_temporary_contents_are_flushed_and_synced_before_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            temporary = Path(str(path) + ".tmp")
            original = b'{"sessions":[{"marker":"already committed"}]}'
            path.write_bytes(original)
            memory = mono.Memory(str(path))
            memory.state["sessions"].append({"text": "new synthetic record \u2603"})
            expected = json.dumps(memory.state, indent=2, allow_nan=False).encode("utf-8")
            real_fsync, real_replace = mono.os.fsync, mono.os.replace

            with _track_temporary_file(temporary) as (events, handles):
                def synced(fd):
                    self.assertEqual(events, ["flush"])
                    self.assertEqual(fd, handles[0].handle.fileno())
                    self.assertFalse(handles[0].handle.closed)
                    self.assertEqual(temporary.read_bytes(), expected)
                    self.assertEqual(path.read_bytes(), original)
                    real_fsync(fd)
                    events.append("fsync")

                def replaced(source, destination):
                    self.assertEqual(events, ["flush", "fsync", "close"])
                    self.assertTrue(handles[0].handle.closed)
                    self.assertEqual(str(source), str(temporary))
                    self.assertEqual(str(destination), str(path))
                    self.assertEqual(temporary.read_bytes(), expected)
                    self.assertEqual(path.read_bytes(), original)
                    real_replace(source, destination)
                    events.append("replace")

                with patch.object(mono.os, "fsync", side_effect=synced) as sync_call:
                    with patch.object(mono.os, "replace", side_effect=replaced) as replace_call:
                        memory.save()
                sync_call.assert_called_once()
                replace_call.assert_called_once()
                self.assertEqual(events, ["flush", "fsync", "close", "replace"])

            self.assertEqual(path.read_bytes(), expected)
            self.assertFalse(temporary.exists())
            self.assertEqual(memory._loaded_digest, hashlib.sha256(expected).digest())

    def test_new_digest_failure_cannot_follow_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            original = b'{"sessions":[{"marker":"already committed"}]}'
            path.write_bytes(original)
            memory = mono.Memory(str(path))
            old_digest = memory._loaded_digest
            memory.state["sessions"].append({"marker": "candidate"})
            candidate = json.dumps(memory.state, indent=2, allow_nan=False).encode("utf-8")
            real_hash = mono.hashlib.sha256

            def digest(data=b""):
                if data == candidate:
                    raise MemoryError("synthetic candidate digest failure")
                return real_hash(data)

            with patch.object(mono.hashlib, "sha256", side_effect=digest):
                with patch.object(mono.os, "replace", wraps=mono.os.replace) as replace_call:
                    with self.assertRaisesRegex(MemoryError, "candidate digest failure"):
                        memory.save()
                    replace_call.assert_not_called()
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(memory._loaded_digest, old_digest)

    def _check_failure(self, failure):
        for operation in ("think", "remember", "sleep"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "state.json"
                temporary = Path(str(path) + ".tmp")
                learner = AssociativeMemory()
                learner.observe("synthetic", "routes", "blue", "left", "fixture",
                                event_id="already-committed")
                original_state = {
                    "sessions": [{"marker": "already committed"}],
                    "associative_memory": learner.state,
                    "legacy": {"preserve": True},
                }
                original = json.dumps(original_state).encode("utf-8")
                path.write_bytes(original)
                engine = mono.Monolith(str(path), learning=True)
                old_state = engine.mem.state
                old_learner = engine.learner
                old_learning_state = copy.deepcopy(old_learner.state)
                old_digest = engine.mem._loaded_digest

                def invoke():
                    if operation == "think":
                        return engine.think("synthetic", "unpublished request")
                    if operation == "sleep":
                        return engine.learning_command({"op": "sleep", "max_events": 1})
                    return engine.learning_command({
                        "op": "remember", "user": "synthetic", "context": "routes",
                        "cue": "red", "answer": "right", "source": "fixture",
                        "event_id": "unpublished-observation",
                    })

                real_fsync = mono.os.fsync

                def synced(fd):
                    if failure == "fsync":
                        raise OSError(errno.EIO, "synthetic fsync failure")
                    return real_fsync(fd)

                with _track_temporary_file(temporary, fail_flush=failure == "flush"):
                    with patch.object(mono.os, "fsync", side_effect=synced) as sync_call:
                        with patch.object(mono.os, "replace", wraps=mono.os.replace) as replace_call:
                            with self.assertRaisesRegex(OSError, "synthetic " + failure + " failure"):
                                invoke()
                            replace_call.assert_not_called()
                            if failure == "flush":
                                sync_call.assert_not_called()
                            else:
                                sync_call.assert_called_once()

                self.assertEqual(path.read_bytes(), original)
                self.assertIs(engine.mem.state, old_state)
                self.assertEqual(engine.mem.state, original_state)
                self.assertIs(engine.learner, old_learner)
                self.assertEqual(engine.learner.state, old_learning_state)
                self.assertEqual(engine.mem._loaded_digest, old_digest)
                self.assertTrue(temporary.exists())
                evidence = temporary.read_bytes()
                # A failed explicit flush may leave partial or complete bytes;
                # either remains evidence rather than authorizing promotion.
                with self.assertRaisesRegex(RuntimeError, "temporary memory"):
                    mono.Monolith(str(path), learning=True)
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(temporary.read_bytes(), evidence)

    def test_flush_failure_preserves_evidence_and_rolls_back_unpublished_state(self):
        self._check_failure("flush")

    def test_file_fsync_failure_preserves_evidence_and_rolls_back_unpublished_state(self):
        self._check_failure("fsync")


if __name__ == "__main__":
    unittest.main()
