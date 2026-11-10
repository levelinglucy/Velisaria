"""Refuse special primary-state files before opening them.

Synthetic named pipes and directories only. Subprocess timeouts ensure a
regression cannot hang the test runner or open any real owner memory.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"


class MemorySpecialPathTests(unittest.TestCase):
    def _run(self, script, path):
        try:
            proc = subprocess.run(
                [sys.executable, "-c", script, str(SOURCE), str(path)],
                capture_output=True, text=True, timeout=3, check=False,
            )
        except subprocess.TimeoutExpired:
            self.fail("memory operation blocked on a non-regular state path")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_fifo_cannot_block_initial_load(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("named pipes unavailable")
        with tempfile.TemporaryDirectory() as root:
            fifo = pathlib.Path(root) / "state.json"
            os.mkfifo(fifo)
            self._run(
                """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("m", sys.argv[1])
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
try:
    m.Memory(sys.argv[2])
except RuntimeError as exc:
    assert "regular file" in str(exc), str(exc)
else:
    raise AssertionError("named pipe accepted")
""", fifo)
            self.assertTrue(fifo.exists())
            self.assertFalse(pathlib.Path(str(fifo) + ".tmp").exists())

    def test_fifo_substituted_after_load_cannot_block_save(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("named pipes unavailable")
        with tempfile.TemporaryDirectory() as root:
            state = pathlib.Path(root) / "state.json"
            state.write_text('{"sessions":[]}', encoding="utf-8")
            self._run(
                """
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("m", sys.argv[1])
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
p = sys.argv[2]
mem = m.Memory(p)
os.unlink(p)
os.mkfifo(p)
try:
    mem.save()
except RuntimeError as exc:
    assert "regular file" in str(exc), str(exc)
else:
    raise AssertionError("named pipe accepted for saving")
""", state)
            self.assertTrue(state.exists())
            self.assertFalse(pathlib.Path(str(state) + ".tmp").exists())

    def test_directory_primary_is_rejected_explicitly(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "state.json"
            path.mkdir()
            self._run(
                """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("m", sys.argv[1])
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
try:
    m.Memory(sys.argv[2])
except RuntimeError as exc:
    assert "regular file" in str(exc), str(exc)
else:
    raise AssertionError("directory accepted")
""", path)
            self.assertTrue(path.is_dir())
            self.assertFalse(pathlib.Path(str(path) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
