"""Synthetic checks that memory state paths cannot silently split histories.

All fixtures are disposable. No owner files, real links or existing histories
are opened. A symlink to a valid file is different from a direct state path
because os.replace() replaces the *link*, not the referent.
"""
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "sanctified_monolith.py"
SPEC = importlib.util.spec_from_file_location("velisaria_link_integrity_test", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class MemoryPrimaryLinkTests(unittest.TestCase):
    def _link(self, link, target):
        try:
            link.symlink_to(target.name)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable on this host")

    def test_valid_primary_symlink_refused_before_loading(self):
        with tempfile.TemporaryDirectory() as root:
            directory = pathlib.Path(root)
            actual = directory / "historical.json"
            alias = directory / "state.json"
            original = b'{"sessions":[{"marker":"old-history"}]}'
            actual.write_bytes(original)
            self._link(alias, actual)

            with self.assertRaisesRegex(RuntimeError, "symbolic link"):
                mod.Memory(str(alias))

            self.assertTrue(alias.is_symlink())
            self.assertEqual(actual.read_bytes(), original)
            self.assertFalse((directory / "state.json.tmp").exists())

    def test_link_substituted_after_load_refused_before_save(self):
        with tempfile.TemporaryDirectory() as root:
            directory = pathlib.Path(root)
            primary = directory / "state.json"
            original = b'{"sessions":[{"marker":"old-history"}]}'
            primary.write_bytes(original)
            mem = mod.Memory(str(primary))
            real = directory / "historical.json"
            primary.rename(real)
            self._link(primary, real)
            mem.state["sessions"].append({"marker": "new-history"})

            with self.assertRaisesRegex(RuntimeError, "symbolic link"):
                mem.save()

            self.assertTrue(primary.is_symlink())
            self.assertEqual(real.read_bytes(), original)
            self.assertFalse((directory / "state.json.tmp").exists())

    def test_direct_regular_file_remains_writable(self):
        with tempfile.TemporaryDirectory() as root:
            primary = pathlib.Path(root) / "state.json"
            original = {"sessions": [{"marker": "old-history"}]}
            primary.write_text(json.dumps(original), encoding="utf-8")
            mem = mod.Memory(str(primary))
            mem.state["sessions"].append({"marker": "new-history"})
            mem.save()
            self.assertEqual(
                [item["marker"] for item in mod.Memory(str(primary)).state["sessions"]],
                ["old-history", "new-history"],
            )
            self.assertFalse(pathlib.Path(str(primary) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
