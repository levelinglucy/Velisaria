"""Prove the delivered monolith runs with no repository companion scripts."""
import ast
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILENAME = 'velisara_monolith_final_fixed_empathy.py'


class SingleFileTests(unittest.TestCase):
    def test_copied_file_runs_and_restarts_under_isolated_standard_python(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / FILENAME
            shutil.copyfile(ROOT / FILENAME, main)
            state = Path(directory) / 'state.json'
            command = [sys.executable, '-I', '-B', '-S', str(main), '--learning',
                       '--state', str(state), '--steps', '2', '--seed', '67']
            first = subprocess.run(command, cwd=directory, text=True,
                                   capture_output=True, timeout=20)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            turns = [json.loads(line) for line in first.stdout.splitlines()]
            self.assertEqual([item['turn'] for item in turns], [1, 2])
            self.assertEqual(turns[1]['text'], turns[0]['response'])
            second = subprocess.run(command, cwd=directory, text=True,
                                    capture_output=True, timeout=20)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            resumed = [json.loads(line) for line in second.stdout.splitlines()]
            self.assertEqual([item['turn'] for item in resumed], [3, 4])
            self.assertEqual({p.name for p in Path(directory).iterdir()},
                             {FILENAME, 'state.json'})

    def test_learning_and_symbolic_routes_never_import_or_create_companions(self):
        program = r'''
import builtins, json, pathlib, runpy, sys
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name in {'associative_memory', 'velisara_runtime'}:
        raise AssertionError('unexpected companion import: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
namespace = runpy.run_path(sys.argv[1], run_name='portable_velisara')
Velisara = namespace['Velisara']
path = pathlib.Path('memory.json')
first = Velisara(state_file=path, seed=71, learning=True)
first.learning_command(dict(op='remember', cue='blue lamp', answer='left',
                            source='single-file fixture', event_id='first'))
first.learning_command(dict(op='correct', cue='blue lamp', answer='right',
                            source='rechecked fixture', event_id='second',
                            supersedes=['first']))
first.learning_command(dict(op='sleep', max_events=2))
first.trigger_dream_loop(3)
first.define_mirror_echo(('lantern', 'spiral'), 'retained link')
first.save_state()
second = Velisara(state_file=path, learning=False)
second.save_state()  # Disabled learning retains dormant evidence.
third = Velisara(state_file=path, learning=True)
answer = third.step('blue lamp')
assert answer['recall']['answer'] == 'right'
assert answer['recall']['evidence_ids'] == ['second']
assert len(third.learner.state['events']) == 2
assert len(third.dream_loop.dream_log) == 3
assert third.mirror_echoes[('lantern', 'spiral')] == 'retained link'
assert {p.name for p in pathlib.Path('.').iterdir()} == {path.name, pathlib.Path(sys.argv[1]).name}
print(json.dumps({'recalled': answer['recall']['answer'], 'dreams': 3}))
'''
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / FILENAME
            shutil.copyfile(ROOT / FILENAME, main)
            completed = subprocess.run(
                [sys.executable, '-I', '-B', '-S', '-c', program, str(main)],
                cwd=directory, text=True, capture_output=True, timeout=20)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {'recalled': 'right', 'dreams': 3})

    def test_included_learner_matches_the_shared_evidence_implementation(self):
        # The single-file copy deliberately shares semantics with Sanctified's
        # separately importable learner. Changes must update both, not drift.
        standalone = ast.parse((ROOT / FILENAME).read_text(encoding='utf-8'))
        shared = ast.parse((ROOT / 'associative_memory.py').read_text(encoding='utf-8'))
        def identity(node):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                return node.name
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                return node.targets[0].id
            return None
        actual = {identity(node): node for node in standalone.body if identity(node)}
        for expected in shared.body:
            key = identity(expected)
            if key:
                with self.subTest(definition=key):
                    self.assertIn(key, actual)
                    self.assertEqual(ast.dump(expected, include_attributes=False),
                                     ast.dump(actual[key], include_attributes=False))

    def test_previous_runtime_import_path_reexports_canonical_definitions(self):
        main = importlib.import_module(FILENAME[:-3])
        facade = importlib.import_module('velisara_runtime')
        for name in facade.__all__:
            with self.subTest(name=name):
                self.assertIs(getattr(facade, name), getattr(main, name))
        self.assertIs(facade.os, main.os)


if __name__ == '__main__':
    unittest.main()
