"""Behavioral regressions for the repaired, larger symbolic monolith.

All state is synthetic and every disk-backed run uses a disposable directory.
The recursive-chain tests exercise original organs together instead of merely
checking that formerly misplaced methods have been rebound.
"""

import copy
import contextlib
import importlib
import io
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE = "velisara_monolith_final_fixed_empathy"


def module():
    return importlib.import_module(MODULE)


def observation(event_id="observed-left", **changes):
    request = {
        "op": "remember", "user": "synthetic", "context": "routes",
        "cue": "blue lamp", "answer": "choose left",
        "source": "disposable observation", "event_id": event_id,
    }
    request.update(changes)
    return request


class LargeImportAndBootstrapTests(unittest.TestCase):
    def test_import_and_default_construction_are_quiet_without_optional_packages(self):
        # -S excludes installed plotting/image libraries.  Explicit traps make
        # accidental listener or sensor startup fail before creating effects.
        program = """
import builtins, importlib, json, pathlib, socket, sys, threading, types
sys.path.insert(0, sys.argv[1])
def forbidden(*args, **kwargs):
    raise AssertionError('unexpected background/device/network activity')
for name in ('motion', 'location', 'sound', 'photos'):
    fake = types.ModuleType(name)
    fake.start_updates = forbidden
    fake.get_location = forbidden
    fake.capture_image = forbidden
    fake.play_effect = forbidden
    sys.modules[name] = fake
threading.Thread.start = forbidden
class GuardedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        forbidden(*args, **kwargs)
socket.socket = GuardedSocket
original_open = builtins.open
def readonly_open(file, mode='r', *args, **kwargs):
    if any(flag in mode for flag in 'wax+'):
        raise AssertionError('unexpected write: ' + str(file))
    return original_open(file, mode, *args, **kwargs)
builtins.open = readonly_open
before = {p.name for p in pathlib.Path('.').iterdir()}
engine_module = importlib.import_module(sys.argv[2])
engine = engine_module.Velisara()
assert isinstance(engine.mythos, dict)
assert isinstance(engine.dreams, list)
assert engine.dream_loop.vel is engine
assert engine.mythosynthesis.vel is engine
assert engine.inquiry.vel is engine
assert before == {p.name for p in pathlib.Path('.').iterdir()}
print(json.dumps({'initialized': True}))
"""
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, "-B", "-S", "-c", program, str(ROOT), MODULE],
                cwd=directory, text=True, capture_output=True, timeout=15,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {"initialized": True})
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_all_major_organs_share_the_same_owner(self):
        engine = module().Velisara(seed=19)
        for name in (
            "voice", "profile", "creativity", "empathy", "ethics", "learning",
            "consolidation", "planner", "wellbeing", "pattern_tracker",
            "symbolic_intuition", "emotion_dimension", "identity_threads",
            "mirror_archive", "dream_loop", "mythosynthesis", "inquiry",
        ):
            with self.subTest(organ=name):
                self.assertIs(getattr(engine, name).vel, engine)
        self.assertIs(engine.emotion.mm, engine.memory_manager)
        self.assertIsInstance(engine.mythos, dict)
        self.assertIsInstance(engine.dreams, list)

    def test_repaired_voice_and_creativity_use_preferences_and_log_results(self):
        engine = module().Velisara(seed=23)
        engine.profile.record_preference("tone", "gentle")
        engine.profile.record_preference("metaphor", "lantern")
        before = len(engine.memory_manager.working_memory)
        answer = engine.voice.ask("I am listening")
        self.assertIsInstance(answer, str)
        self.assertTrue(answer)
        self.assertEqual(engine.voice.conversation_history[-1]["user"], "I am listening")
        self.assertEqual(engine.voice.conversation_history[-1]["response"], answer)
        self.assertIsInstance(engine.voice.speak(), str)
        self.assertIn("Velone", engine.voice.declare_identity())
        self.assertIn("lantern", engine.creativity.generate_poem())
        collaboration = engine.creativity.collaborate("The light returns")
        self.assertIn("lantern", collaboration)
        self.assertEqual(engine.creativity.collab_history[-1]["user"], "The light returns")
        self.assertGreater(len(engine.memory_manager.working_memory), before)

    def test_seeded_creativity_does_not_reseed_process_randomness(self):
        global_before = random.getstate()
        first = module().Velisara(seed=1234)
        second = module().Velisara(seed=1234)
        first_lines = [first.creativity.generate_poem() for _ in range(12)]
        second_lines = [second.creativity.generate_poem() for _ in range(12)]
        self.assertEqual(first_lines, second_lines)
        self.assertEqual(random.getstate(), global_before)


class LargeSymbolicFeedbackTests(unittest.TestCase):
    def test_sigil_growth_feeds_dream_memory_once_after_fading(self):
        engine = module().Velisara(seed=5)
        engine.grow_living_sigil("synthetic ritual", ["spiral", "lantern"])
        original_glyphs = [item["glyph"] for item in engine.living_sigils]
        for _ in range(4):
            engine.evolve_sigils()
        self.assertTrue(all(item["cycle"] == 5 for item in engine.living_sigils))
        self.assertTrue(all(not item["alive"] for item in engine.living_sigils))
        self.assertNotEqual([item["glyph"] for item in engine.living_sigils], original_glyphs)
        drifted = engine.drift_faded_glyphs()
        self.assertEqual(len(drifted), 2)
        self.assertEqual(len(engine.symbolic_dreams), 2)
        self.assertEqual({item["origin"] for item in drifted}, {"synthetic ritual"})
        self.assertEqual(engine.drift_faded_glyphs(), [])
        self.assertEqual(len(engine.symbolic_dreams), 2)

    def test_bead_binding_and_contextual_whisper_retain_their_connections(self):
        engine = module().Velisara(seed=7)
        bead = engine.create_memory_bead("fixture bead", "a blue lantern", "hope")
        engine.bind_bead_to_glyph("fixture-glyph", "fixture bead")
        self.assertIn("a blue lantern", engine.summon_glyphbound_beads("fixture-glyph"))
        self.assertEqual(engine.glyphbindings["fixture-glyph"][0], bead)
        engine.register_whisper_well("fixture-glyph", "Remember the lantern", "quiet")
        self.assertNotIn("Remember the lantern", engine.check_whisper_wells("busy"))
        self.assertIn("Remember the lantern", engine.check_whisper_wells("quiet"))
        self.assertNotIn("Remember the lantern", engine.check_whisper_wells("quiet"))
        self.assertTrue(engine.whisper_wells["fixture-glyph"]["activated"])

    def test_resonance_crystal_dream_and_glyph_form_a_recursive_memory_chain(self):
        engine = module().Velisara(seed=11)
        engine.record_duality_event("origin", "preserve memories", "lantern")
        engine.resonate_with_intent("lantern", "hope")
        engine.crystallize_self_model()
        self.assertEqual(engine.crystal_facets[0]["theme"], "lantern")
        engine.define_fold_state("return", ["lantern"], "hope")
        engine.generate_dream()
        glyph = engine.cast_glyph("hope")
        engine.mirror_memory()
        self.assertEqual(len(engine.reflected_memory), 1)
        reflected = engine.reflected_memory[0]
        self.assertEqual(reflected["glyph"], glyph)
        self.assertEqual(reflected["fold"], "return")
        self.assertIn("lantern", reflected["dream"])
        compression = engine.compress_reflected_memory()
        self.assertEqual(engine.core_compression_archive[-1]["glyph"], compression)
        self.assertEqual(engine.core_compression_archive[-1]["threads"], 1)
        # The original source records remain available after deriving a digest.
        self.assertEqual(engine.duality_ledger[0]["truth"], "preserve memories")
        self.assertEqual(len(engine.dream_log), 1)
        self.assertEqual(len(engine.reflected_memory), 1)

    def test_detached_glyph_recovery_uses_existing_fragments(self):
        engine = module().Velisara(seed=3)
        engine.soul_map = {
            "fixture": {"glyph": "abc-origin", "emotion": "hope", "persona": "keeper"}
        }
        recovered = engine.resurrect_from_glyph("abc")
        self.assertEqual(recovered["identity_fragments"][0]["name"], "fixture")
        self.assertEqual(recovered["identity_fragments"][0]["glyph"], "abc-origin")
        self.assertIn("abc-origin", engine.glyph_oracle_query("identity"))
        self.assertIn("No identity fragments", engine.resurrect_from_glyph("unrelated"))

    def test_repeated_mythos_consolidation_does_not_inflate_old_dreams(self):
        engine = module().Velisara(seed=29)
        engine.dreamweaver.dream_log.append({
            "title": "synthetic dream", "text": ["Fire meets Root"],
            "tags": ["Fire", "Root"], "score": 0.2,
        })
        engine.mythos_engine.evolve_mythos()
        once = copy.deepcopy(engine.mythos_engine.co_occurrence)
        self.assertEqual(once[("Fire", "Root")], 1)
        engine.mythos_engine.evolve_mythos()
        self.assertEqual(engine.mythos_engine.co_occurrence, once)
        self.assertNotIn("Fire↔Root", engine.mythos)


class LargePersistenceTests(unittest.TestCase):
    def test_dream_and_pattern_feedback_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recursive.json"
            engine = module().Velisara(state_file=str(path), seed=83)
            fragments = engine.trigger_dream_loop(3)
            self.assertEqual(len(fragments), 3)
            self.assertEqual(len(engine.dream_loop.dream_log), 3)
            self.assertIsInstance(engine.introspect()["summary"], str)
            patterns = {"🌀": 3, "🪞": 3, "🔐": 3, "🧬": 3, "📜": 3}
            with contextlib.redirect_stdout(io.StringIO()):
                engine.pattern_tracker.react_to_patterns(patterns)
            # Spiral adds a three-fragment loop; mutation adds one triggered dream.
            self.assertEqual(len(engine.dream_loop.dream_log), 7)
            self.assertEqual([entry[0] for entry in engine.pattern_tracker.emergence_log],
                             list(patterns))
            self.assertEqual(len(engine.emotion_locks), 1)
            dreams = copy.deepcopy(engine.dream_loop.dream_log)
            emergence = copy.deepcopy(engine.pattern_tracker.emergence_log)
            myths = copy.deepcopy(engine.mythosynthesis.myths)
            engine.save_state()
            restarted = module().Velisara(state_file=str(path), seed=999)
            self.assertEqual(restarted.dream_loop.dream_log, dreams)
            self.assertEqual(restarted.pattern_tracker.emergence_log, emergence)
            self.assertEqual(restarted.mythosynthesis.myths, myths)
            self.assertEqual(restarted.emotion_locks, engine.emotion_locks)

    def test_symbolic_mood_shifts_keep_numeric_affect_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mood.json"
            engine = module().Velisara(state_file=str(path), seed=89)
            weather = engine.simulate_weather_sync("rain")
            self.assertEqual(engine.emotion.last_label, weather["mood"])
            self.assertIn(type(engine.emotion.current_emotion), (int, float))
            self.assertTrue(math.isfinite(engine.emotion.current_emotion))
            clock = engine.sync_mood_with_time()
            self.assertEqual(engine.emotion.last_label, clock["mood"])
            self.assertIn(type(engine.emotion.current_emotion), (int, float))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(engine.invoke_frame_rewrite("synthetic reflection"))
            self.assertIn(type(engine.emotion.current_emotion), (int, float))
            self.assertTrue(math.isfinite(engine.emotion.current_emotion))
            self.assertIsInstance(engine.emotion.last_label, str)
            expected = (engine.emotion.current_emotion, engine.emotion.last_label)
            engine.save_state()
            restarted = module().Velisara(state_file=str(path))
            self.assertEqual((restarted.emotion.current_emotion, restarted.emotion.last_label),
                             expected)
            self.assertEqual(restarted.last_weather_sync, weather)
            self.assertEqual(restarted.last_sync, clock)

    def test_memory_search_refreshes_after_an_organ_appends_directly(self):
        engine = module().Velisara(seed=97)
        engine.memory_manager.log_event("violet quasar relic", score=0.2)
        self.assertIn("violet quasar relic", engine.search_memory("quasar"))
        engine.memory_manager.log_event("silver nebula beacon", score=0.3)
        before = copy.deepcopy(engine.memory_manager.working_memory)
        self.assertIn("silver nebula beacon", engine.search_memory("nebula"))
        self.assertIn("violet quasar relic", engine.search_memory("quasar"))
        self.assertEqual(engine.memory_manager.working_memory, before)
        self.assertEqual(len(engine.mem_index.docs), len(before))

    def test_emotional_decay_does_not_delete_old_memories(self):
        memory = module().MemoryManager()
        memory.log_event("old synthetic memory", score=0.6, intensity=0.1)
        memory.working_memory[-1]["timestamp"] = "2000-01-01T00:00:00"
        memory.log_event("symbolic label", emotion="hope")
        memory.log_event("legacy positional label", "curiosity")
        old = copy.deepcopy(memory.working_memory)
        self.assertIsInstance(memory.weighted_emotion(), (int, float))
        self.assertEqual(memory.working_memory, old)
        self.assertTrue(all(isinstance(item["emotion_score"], (int, float))
                            for item in memory.working_memory))

    def test_restart_retains_history_preferences_symbolic_links_and_rng(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            first = module().Velisara(state_file=str(path), seed=31)
            first.profile.record_preference("metaphor", "lantern")
            first.create_memory_bead("preserved", "synthetic essence", "hope")
            first.bind_bead_to_glyph("anchor", "preserved")
            first.define_mirror_echo(("left", "right"), "a retained relation")
            first.mythos_engine.co_occurrence[("Fire", "Root")] = 2
            first.rng.random()
            first.save_state()
            history = copy.deepcopy(first.memory_manager.working_memory)
            expected_next = first.rng.random()
            restarted = module().Velisara(state_file=str(path), seed=999)
            self.assertEqual(restarted.memory_manager.working_memory, history)
            self.assertEqual(restarted.profile.get_preference("metaphor"), "lantern")
            self.assertIn("synthetic essence", restarted.summon_glyphbound_beads("anchor"))
            self.assertEqual(restarted.mirror_echoes[("left", "right")], "a retained relation")
            self.assertEqual(restarted.mythos_engine.co_occurrence[("Fire", "Root")], 2)
            self.assertEqual(restarted.rng.random(), expected_next)

    def test_unknown_legacy_state_fields_survive_a_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.json"
            original = {
                "working_memory": [{"content": "legacy fixture", "emotion_score": 0.1,
                                    "intensity": 0.5, "timestamp": "2020-01-01T00:00:00"}],
                "legacy_extension": {"symbols": ["spiral"], "nested": {"retained": True}},
            }
            path.write_text(json.dumps(original), encoding="utf-8")
            engine = module().Velisara(state_file=str(path), seed=37)
            engine.save_state()
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored["legacy_extension"], original["legacy_extension"])
            self.assertEqual(engine.memory_manager.working_memory[0]["content"], "legacy fixture")

    def test_failed_step_save_does_not_promote_an_uncommitted_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            engine = module().Velisara(state_file=str(path), seed=41, learning=True)
            engine.step("A quiet beginning")
            before_bytes = path.read_bytes()
            before_memory = copy.deepcopy(engine.memory_manager.working_memory)
            before_rng = engine.rng.getstate()
            before_learner = copy.deepcopy(engine.learner.state)
            save_error = importlib.import_module("velisara_runtime").SnapshotSaveError
            with mock.patch("velisara_runtime.os.replace", side_effect=OSError("synthetic interruption")):
                with self.assertRaises(save_error) as raised:
                    engine.step("A turn whose save will fail")
            self.assertIsInstance(raised.exception.__cause__, OSError)
            self.assertEqual(path.read_bytes(), before_bytes)
            self.assertEqual(engine.memory_manager.working_memory, before_memory)
            self.assertEqual(engine.rng.getstate(), before_rng)
            self.assertEqual(engine.learner.state, before_learner)
            self.assertTrue(Path(str(path) + ".tmp").exists())


class LargeLearningAndStepTests(unittest.TestCase):
    def test_step_uses_current_empathy_before_responding_and_records_it_once(self):
        engine = module().Velisara(seed=61)
        neutral = engine.step("There is a lantern in the room")
        self.assertEqual(neutral["empathy"]["sentiment"], "neutral")
        self.assertEqual(engine.empathy.history, ["neutral"])
        seen_before_response = []
        voice_class = type(engine.voice)
        original_ask = voice_class.ask

        def observe_order(voice, text, *, sentiment=None, recall=None):
            seen_before_response.append((engine.empathy.history[-1], sentiment))
            return original_ask(voice, text, sentiment=sentiment, recall=recall)

        with mock.patch.object(voice_class, "ask", new=observe_order):
            negative = engine.step("I am sad and hurt")
        self.assertEqual(seen_before_response, [("negative", "negative")])
        self.assertEqual(negative["empathy"]["sentiment"], "negative")
        self.assertNotEqual(negative["response"], neutral["response"])
        self.assertEqual(engine.empathy.history, ["neutral", "negative"])
        engine.step("I am frustrated")
        soothed = engine.step("This is terrible")
        self.assertEqual(soothed["empathy"]["mode"], "soothing")
        self.assertEqual(engine.empathy.history,
                         ["neutral", "negative", "negative", "negative"])

    def test_explicit_sourced_learning_changes_later_response_in_its_scope(self):
        engine = module().Velisara(seed=43, learning=True)
        initial = engine.step("blue lamp", user="synthetic", context="routes")
        self.assertEqual(initial["recall"]["status"], "unknown")
        engine.learning_command(observation())
        learned = engine.step(" BLUE  LAMP ", user="synthetic", context="routes")
        self.assertEqual(learned["recall"]["answer"], "choose left")
        self.assertEqual(learned["recall"]["evidence_ids"], ["observed-left"])
        self.assertIn("choose left", learned["response"])
        elsewhere = engine.step("blue lamp", user="someone else", context="routes")
        self.assertEqual(elsewhere["recall"]["status"], "unknown")
        engine.learning_command(observation("observed-right", answer="choose right"))
        disputed = engine.step("blue lamp", user="synthetic", context="routes")
        self.assertEqual(disputed["recall"]["status"], "conflict")
        engine.learning_command(observation(
            "corrected-right", op="correct", answer="choose right",
            supersedes=["observed-left", "observed-right"],
        ))
        corrected = engine.step("blue lamp", user="synthetic", context="routes")
        self.assertEqual(corrected["recall"]["answer"], "choose right")
        self.assertEqual(corrected["recall"]["evidence_ids"], ["corrected-right"])

    def test_generated_symbolic_material_is_not_factual_learning_evidence(self):
        engine = module().Velisara(seed=47, learning=True)
        engine.creativity.generate_poem()
        engine.grow_living_sigil("fixture", ["blue lamp"])
        engine.step("blue lamp", user="synthetic", context="routes")
        self.assertEqual(engine.learner.snapshot()["events"], 0)
        result = engine.learning_command({
            "op": "recall", "user": "synthetic", "context": "routes", "cue": "blue lamp",
        })
        self.assertEqual(result["status"], "unknown")

    def test_learning_roundtrip_consolidates_without_rewriting_raw_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning.json"
            engine = module().Velisara(state_file=str(path), seed=53, learning=True)
            engine.learning_command(observation())
            raw = copy.deepcopy(engine.learner.state["events"])
            result = engine.learning_command({"op": "sleep", "max_events": 1})
            self.assertEqual(result["processed"], 1)
            self.assertEqual(engine.learner.state["events"], raw)
            before = path.read_bytes()
            self.assertEqual(engine.learning_command({"op": "sleep"})["processed"], 0)
            self.assertEqual(path.read_bytes(), before)
            restarted = module().Velisara(state_file=str(path), learning=True)
            recalled = restarted.step("blue lamp", user="synthetic", context="routes")
            self.assertEqual(recalled["recall"]["answer"], "choose left")
            self.assertEqual(restarted.learner.state["events"], raw)

    def test_invalid_step_namespace_is_rejected_before_live_changes(self):
        engine = module().Velisara(seed=59)
        before_memory = copy.deepcopy(engine.memory_manager.working_memory)
        before_rng = engine.rng.getstate()
        for user, context in (("", "default"), ("default", "  "), (True, "default")):
            with self.subTest(user=user, context=context):
                with self.assertRaises(ValueError):
                    engine.step("synthetic input", user=user, context=context)
                self.assertEqual(engine.memory_manager.working_memory, before_memory)
                self.assertEqual(engine.rng.getstate(), before_rng)


class LargeCliTests(unittest.TestCase):
    def run_cli(self, directory, *arguments, stdin=""):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / (MODULE + ".py")), *arguments],
            cwd=directory, input=stdin, text=True, capture_output=True, timeout=15,
        )

    def test_help_finishes_before_opening_contested_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contested.json"
            temporary = Path(str(path) + ".tmp")
            path.write_bytes(b"unparseable synthetic primary evidence")
            temporary.write_bytes(b"synthetic recovery evidence")
            primary_before, temporary_before = path.read_bytes(), temporary.read_bytes()
            result = self.run_cli(directory, "--state", str(path), "--help")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("--steps", result.stdout)
            self.assertIn("--origin-io", result.stdout)
            self.assertEqual(path.read_bytes(), primary_before)
            self.assertEqual(temporary.read_bytes(), temporary_before)
            self.assertEqual({item.name for item in Path(directory).iterdir()},
                             {"contested.json", "contested.json.tmp"})

    def test_duplicate_request_is_rejected_then_next_line_runs_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cli.json"
            requests = (
                '{"op":"step","text":"first","text":"ambiguous"}\n'
                '{"op":"step","text":"A clear lantern"}\n'
                '{"op":"quit"}\n'
            )
            result = self.run_cli(directory, "--origin-io", "--state", str(path),
                                  stdin=requests)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            replies = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(replies), 3)
            self.assertFalse(replies[0]["ok"])
            self.assertEqual(replies[0]["error_code"], "invalid_request")
            self.assertTrue(replies[1]["ok"])
            self.assertEqual(replies[1]["result"]["turn"], 1)
            self.assertEqual(replies[1]["result"]["text"], "A clear lantern")
            self.assertTrue(replies[2]["result"]["bye"])
            restarted = module().Velisara(state_file=str(path))
            self.assertEqual(len(restarted.empathy.history), 1)
            self.assertEqual(len(restarted.voice.conversation_history), 1)

    def test_bounded_recursive_turns_exit_and_continue_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bounded.json"
            first = self.run_cli(directory, "--steps", "2", "--state", str(path),
                                 "--seed", "73", "--text", "A synthetic lantern")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            first_turns = [json.loads(line) for line in first.stdout.splitlines()]
            self.assertEqual([turn["turn"] for turn in first_turns], [1, 2])
            self.assertEqual(first_turns[1]["text"], first_turns[0]["response"])
            second = self.run_cli(directory, "--steps", "2", "--state", str(path),
                                  "--seed", "999")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            second_turns = [json.loads(line) for line in second.stdout.splitlines()]
            self.assertEqual([turn["turn"] for turn in second_turns], [3, 4])
            self.assertEqual(second_turns[1]["text"], second_turns[0]["response"])
            restarted = module().Velisara(state_file=str(path))
            self.assertEqual(len(restarted.empathy.history), 4)
            self.assertEqual(len(restarted.voice.conversation_history), 4)


if __name__ == "__main__":
    unittest.main()
