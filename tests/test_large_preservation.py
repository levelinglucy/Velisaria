"""Regression tests for preserving source records through symbolic transformations."""
import contextlib
import copy
import io
import unittest
from unittest import mock

import velisara_monolith_final_fixed_empathy as monolith


class LargePreservationTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.core = monolith.Velisara(seed=53)
        self.addCleanup(self.redirect.__exit__, None, None, None)
        self.addCleanup(self.core.close)

    def test_symbolic_lock_retains_originals_and_refuses_lost_legacy_data(self):
        symbols = ["Spiral", "☾", "a nested thought"]
        dream = {"symbols": copy.deepcopy(symbols), "text": "source dream"}
        self.core.dream_vault.dreams["lantern"] = dream
        self.core.belief_engine.seed_belief("anchor", "The anchor remembers.")
        self.core.encrypt_dream("lantern", "anchor")
        self.assertEqual(dream["symbols"], symbols)
        self.assertTrue(dream["locked"])
        self.assertEqual(dream["lock_kind"], "symbolic")
        masked = copy.deepcopy(dream["symbols_encrypted"])
        rng = self.core.rng.getstate()
        self.core.encrypt_dream("lantern", "anchor")
        self.assertEqual(self.core.rng.getstate(), rng)
        self.assertEqual(dream["symbols_encrypted"], masked)
        self.assertIsNone(self.core.decrypt_dream("lantern", "unrelated"))
        self.assertTrue(dream["locked"])
        restored = self.core.decrypt_dream("lantern", "anchor")
        self.assertEqual(restored, symbols)
        self.assertFalse(dream["locked"])
        restored.append("caller mutation")
        self.assertEqual(dream["symbols"], symbols)
        legacy = {"locked": True, "symbols_encrypted": ["⊗∆"]}
        self.core.dream_vault.dreams["legacy"] = legacy
        with self.assertRaisesRegex(ValueError, "cannot reconstruct"):
            self.core.decrypt_dream("legacy", "anchor")
        self.assertEqual(legacy, {"locked": True, "symbols_encrypted": ["⊗∆"]})

    def test_belief_retirement_preserves_history_and_repeat_retirements(self):
        beliefs = self.core.belief_engine
        beliefs.seed_belief("echo", "first source", source="observation",
                            truth_likelihood=0.12, emotional_bond=0.11)
        original = copy.deepcopy(beliefs.beliefs["echo"])
        self.assertEqual(beliefs.decay_beliefs(0.04), ["echo"])
        self.assertNotIn("echo", beliefs.beliefs)
        archived = beliefs.retired_beliefs[0]
        self.assertEqual(archived["symbol"], "echo")
        self.assertEqual(archived["belief"]["text"], original["text"])
        self.assertEqual(archived["belief"]["source"], original["source"])
        self.assertEqual(archived["belief"]["history"][:-1], original["history"])
        self.assertEqual(beliefs.decay_beliefs(), [])
        self.assertEqual(len(beliefs.retired_beliefs), 1)
        beliefs.seed_belief("echo", "second source", truth_likelihood=0.05, emotional_bond=0.05)
        beliefs.decay_beliefs()
        self.assertEqual([r["belief"]["text"] for r in beliefs.retired_beliefs],
                         ["first source", "second source"])
        state = copy.deepcopy(beliefs.__dict__)
        with self.assertRaises(ValueError):
            beliefs.decay_beliefs(float("nan"))
        self.assertEqual(beliefs.__dict__, state)

    def test_explicit_garden_pruning_archives_every_removed_source(self):
        garden = self.core.garden
        garden.plant("river", tags=["nature"], resonance=0.7)
        garden.plant("lantern", tags=["light"], resonance=0.9)
        originals = copy.deepcopy(garden.plants)
        self.assertEqual(garden.prune(["nature"]), 1)
        self.assertEqual(garden.plants, [originals[1]])
        self.assertEqual(garden.pruned_plants[0]["plant"], originals[0])
        self.assertEqual(garden.prune(["nature"]), 0)
        self.assertEqual(len(garden.pruned_plants), 1)
        self.assertEqual(garden.prune(), 1)
        self.assertEqual(garden.plants, [])
        self.assertEqual([r["plant"] for r in garden.pruned_plants], originals)
        self.assertEqual(garden.prune(), 0)
        self.assertEqual(len(garden.pruned_plants), 2)

    def test_archetype_reseeding_preserves_trials_and_descriptive_myths(self):
        descriptions = copy.deepcopy(self.core.mythos)
        self.core.generate_mythos()
        self.core.invoke_mythic("The Wanderer")
        self.core.mythic_trial("crossing the river")
        archetypes = copy.deepcopy(self.core.mythic_archetypes)
        self.core.generate_mythos()
        self.assertEqual(self.core.mythic_archetypes, archetypes)
        self.assertEqual(self.core.mythos, descriptions)
        with mock.patch.object(self.core.mythos_engine, "evolve_mythos", return_value=[]) as evolve:
            self.core.handle_command("myth evolve")
            evolve.assert_called_once_with()
        with mock.patch.object(self.core.emotion, "aggregate", return_value=(0.0, "calm")) as aggregate:
            self.core.handle_command("mood")
            aggregate.assert_called_once_with()

    def test_council_reinitialization_preserves_votes_and_adds_shadow_member(self):
        self.core.initialize_council()
        self.core.council_vote("path", ["river", "garden"])
        self.core.summarize_council_opinion("path")
        original = copy.deepcopy(self.core.inner_council)
        self.core.thread_shadow("hesitation", "uncertainty", "The Hesitant One")
        self.core.initialize_council()
        for name, member in original.items():
            self.assertEqual(self.core.inner_council[name], member)
        self.assertIn("The Hesitant One", self.core.inner_council)
        member = self.core.inner_council["The Wanderer"]
        member["votes"] = [{"topic": "tie", "choice": "first"},
                           {"topic": "tie", "choice": "second"}]
        self.assertEqual(self.core.summarize_council_opinion("tie")["The Wanderer"], "first")
        prior = copy.deepcopy(self.core.inner_council)
        rng = self.core.rng.getstate()
        with self.assertRaises(ValueError):
            self.core.council_vote("invalid", [])
        self.assertEqual(self.core.inner_council, prior)
        self.assertEqual(self.core.rng.getstate(), rng)

    def test_myth_pattern_feedback_is_bounded_and_resumes_after_a_failed_callback(self):
        self.core.seed_self_identity_core()
        self.core.anchor_synapse_node("synthetic anchor")
        self.core.log_event("📜 📜 📜")
        myths_before = len(self.core.myth_archive)
        events_before = len(self.core.memory_manager.working_memory)
        result = self.core.generate_personal_myth("synthetic myth")
        self.assertIsInstance(result, str)
        self.assertGreater(len(self.core.myth_archive), myths_before)
        self.assertLessEqual(len(self.core.myth_archive) - myths_before, 2)
        self.assertLessEqual(len(self.core.memory_manager.working_memory) - events_before, 12)

        # A failed reaction must not leave the scanner permanently disabled.
        with mock.patch.object(self.core, "generate_personal_myth",
                               side_effect=RuntimeError("synthetic callback failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic callback failure"):
                self.core.pattern_tracker.scan_for_patterns()
        myths_before = len(self.core.myth_archive)
        self.core.pattern_tracker.scan_for_patterns()
        self.assertEqual(len(self.core.myth_archive) - myths_before, 1)


if __name__ == "__main__":
    unittest.main()
