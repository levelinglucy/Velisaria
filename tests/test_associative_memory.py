"""Synthetic behavioural contracts for optional associative consolidation.

These cases exercise evidence, corrections, bounded work and process restart.
They do not imply semantic generalization or reproduce a neural learning model.
The production memory writer is covered by separate integration tests.
"""
import copy
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from associative_memory import AssociativeMemory


class AssociativeMemoryTests(unittest.TestCase):
    def observe(self, memory, event_id, answer="amber", cue="beacon",
                user="Dylan", context="woods", kind="observation",
                supersedes=None):
        return memory.observe(
            user=user, context=context, cue=cue, answer=answer,
            source="synthetic:" + event_id, event_id=event_id,
            kind=kind, supersedes=supersedes,
        )

    def recall(self, memory, cue="beacon", user="Dylan", context="woods",
               **kwargs):
        return memory.recall(user=user, context=context, cue=cue, **kwargs)

    def assert_answer(self, result, answer, evidence):
        self.assertEqual(result["status"], "recalled")
        self.assertEqual(result["answer"], answer)
        self.assertEqual(set(result["evidence_ids"]), set(evidence))
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["answer"], answer)
        self.assertEqual(set(result["candidates"][0]["evidence_ids"]), set(evidence))
        self.assertEqual(set(result["sources"]), {"synthetic:" + i for i in evidence})

    def test_source_linked_recall_normalizes_only_cue_and_preserves_scope(self):
        memory = AssociativeMemory()
        self.observe(memory, "one", cue="  ＢＥＡＣＯＮ\u3000Ａ  ")
        memory.consolidate()

        result = self.recall(memory, cue="beacon\t a", mode="consolidated")
        self.assert_answer(result, "amber", ["one"])
        for query in (
            {"cue": "beacon a", "user": "dylan"},
            {"cue": "beacon a", "context": "Woods"},
            {"cue": "beacon a", "user": "someone-else"},
            {"cue": "beacon a?"},
        ):
            with self.subTest(query=query):
                result = self.recall(memory, **query)
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["answer"])
                self.assertEqual(result["evidence_ids"], [])

    def test_repetition_cannot_turn_conflicting_observations_into_truth(self):
        memory = AssociativeMemory()
        for index in range(5):
            self.observe(memory, "old-" + str(index), answer="amber")
        self.observe(memory, "disagreement", answer="violet")
        memory.consolidate()

        for mode in ("archive", "working", "consolidated", "combined"):
            with self.subTest(mode=mode):
                result = self.recall(memory, mode=mode)
                self.assertEqual(result["status"], "conflict")
                self.assertIsNone(result["answer"])
                candidates = {entry["answer"]: entry for entry in result["candidates"]}
                self.assertEqual(set(candidates), {"amber", "violet"})
                self.assertEqual(set(candidates["amber"]["evidence_ids"]),
                                 {"old-" + str(i) for i in range(5)})
                self.assertEqual(candidates["violet"]["evidence_ids"], ["disagreement"])

    def test_explicit_correction_supersedes_all_named_evidence_without_erasure(self):
        memory = AssociativeMemory()
        self.observe(memory, "old-a")
        self.observe(memory, "old-b")
        memory.consolidate()
        original_events = copy.deepcopy(memory.state["events"])
        self.observe(memory, "correct", answer="violet", kind="correction",
                     supersedes=["old-a", "old-b"])

        self.assert_answer(self.recall(memory, mode="consolidated"),
                           "amber", ["old-a", "old-b"])
        for mode in ("archive", "combined"):
            self.assert_answer(self.recall(memory, mode=mode), "violet", ["correct"])
        memory.consolidate()
        restored = AssociativeMemory(json.loads(json.dumps(memory.state)))
        self.assert_answer(self.recall(restored, mode="consolidated"),
                           "violet", ["correct"])
        self.assertEqual(restored.state["events"][:2], original_events)
        self.assertEqual(len(restored.state["events"]), 3)
        before = copy.deepcopy(restored.state)
        restored.consolidate()
        self.assertEqual(restored.state, before)

    def test_partial_correction_leaves_unnamed_conflicting_evidence_visible(self):
        memory = AssociativeMemory()
        self.observe(memory, "old-a")
        self.observe(memory, "old-b")
        self.observe(memory, "correct-one", answer="violet", kind="correction",
                     supersedes=["old-a"])
        memory.consolidate()
        result = self.recall(memory)
        self.assertEqual(result["status"], "conflict")
        candidates = {entry["answer"]: entry for entry in result["candidates"]}
        self.assertEqual(candidates["amber"]["evidence_ids"], ["old-b"])
        self.assertEqual(candidates["violet"]["evidence_ids"], ["correct-one"])

    def test_pending_correction_survives_a_backlog_larger_than_working_window(self):
        memory = AssociativeMemory()
        self.observe(memory, "old")
        memory.consolidate()
        self.observe(memory, "correct", answer="violet", kind="correction",
                     supersedes=["old"])
        for index in range(36):
            self.observe(memory, "noise-" + str(index), cue="unrelated-" + str(index),
                         kind="hypothesis")

        self.assertEqual(self.recall(memory, mode="working")["status"], "unknown")
        self.assert_answer(self.recall(memory, mode="consolidated"), "amber", ["old"])
        for mode in ("combined", "archive"):
            result = self.recall(memory, mode=mode, working_limit=2)
            self.assert_answer(result, "violet", ["correct"])
            self.assertEqual(result["pending"], 37)
        memory.consolidate(max_events=2)
        self.assert_answer(self.recall(memory), "violet", ["correct"])

    def test_invalid_correction_targets_do_not_append_an_event(self):
        memory = AssociativeMemory()
        self.observe(memory, "old")
        self.observe(memory, "other-user", user="another-user")
        self.observe(memory, "other-context", context="shore")
        self.observe(memory, "other-cue", cue="another cue")
        self.observe(memory, "imagined", kind="hypothesis")
        self.observe(memory, "correct", answer="violet", kind="correction",
                     supersedes=["old"])
        invalid_targets = (
            [], ["missing"], ["old"], ["other-user"], ["other-context"],
            ["other-cue"], ["imagined"], ["correct", "correct"],
        )
        for index, targets in enumerate(invalid_targets):
            with self.subTest(targets=targets):
                before = copy.deepcopy(memory.state)
                with self.assertRaises(ValueError):
                    self.observe(memory, "invalid-" + str(index), answer="green",
                                 kind="correction", supersedes=targets)
                self.assertEqual(memory.state, before)

    def test_identical_event_retry_is_idempotent_but_conflicting_reuse_fails(self):
        memory = AssociativeMemory()
        first = self.observe(memory, "retry")
        self.assertTrue(first["created"])
        self.assertEqual(first["event_id"], "retry")
        memory.consolidate()
        before = copy.deepcopy(memory.state)
        retry = self.observe(memory, "retry")
        self.assertFalse(retry["created"])
        self.assertEqual(memory.state, before)
        self.assert_answer(self.recall(memory), "amber", ["retry"])
        with self.assertRaises(ValueError):
            self.observe(memory, "retry", answer="different")
        self.assertEqual(memory.state, before)

    def test_consolidation_budget_counts_skipped_hypotheses(self):
        memory = AssociativeMemory()
        for event_id in ("dream-a", "dream-b"):
            self.observe(memory, event_id, kind="hypothesis")
        self.observe(memory, "observed-a", cue="first")
        self.observe(memory, "dream-c", kind="hypothesis")
        self.observe(memory, "observed-b", cue="second")

        first = memory.consolidate(max_events=2)
        self.assertEqual((first["processed"], first["cursor"], first["pending"]), (2, 2, 3))
        self.assertEqual(self.recall(memory, cue="first", mode="consolidated")["status"],
                         "unknown")
        second = memory.consolidate(max_events=2)
        self.assertEqual((second["processed"], second["cursor"], second["pending"]), (2, 4, 1))
        self.assert_answer(self.recall(memory, cue="first", mode="consolidated"),
                           "amber", ["observed-a"])
        self.assertEqual(self.recall(memory, cue="second", mode="consolidated")["status"],
                         "unknown")
        last = memory.consolidate(max_events=2)
        self.assertEqual((last["processed"], last["cursor"], last["pending"]), (1, 5, 0))
        self.assert_answer(self.recall(memory, cue="second", mode="consolidated"),
                           "amber", ["observed-b"])

    def test_hypotheses_never_become_evidence_or_conflict_with_observations(self):
        memory = AssociativeMemory()
        self.observe(memory, "dream-only", cue="imagined key", kind="hypothesis")
        self.observe(memory, "fact")
        self.observe(memory, "contradictory-dream", answer="violet", kind="hypothesis")
        memory.consolidate()
        for mode in ("archive", "working", "consolidated", "combined"):
            with self.subTest(mode=mode):
                self.assertEqual(self.recall(memory, cue="imagined key", mode=mode)["status"],
                                 "unknown")
                self.assert_answer(self.recall(memory, mode=mode), "amber", ["fact"])

    def test_no_pending_events_is_an_exact_noop_and_invalid_budgets_refuse(self):
        memory = AssociativeMemory()
        self.observe(memory, "one")
        for budget in (0, -1, 257, True, 1.5):
            with self.subTest(budget=budget):
                before = copy.deepcopy(memory.state)
                with self.assertRaises(ValueError):
                    memory.consolidate(max_events=budget)
                self.assertEqual(memory.state, before)
        memory.consolidate()
        before = copy.deepcopy(memory.state)
        outcome = memory.consolidate()
        self.assertEqual(outcome["processed"], 0)
        self.assertEqual(outcome["pending"], 0)
        self.assertEqual(memory.state, before)

    def test_sequential_retention_matches_honest_archive_control_after_restart(self):
        # These held-out forms test declared normalization, not semantic reasoning.
        memory = AssociativeMemory()
        for context in ("woods", "shore"):
            for index in range(4):
                self.observe(memory, context + "-" + str(index),
                             cue="Beacon " + str(index), context=context,
                             answer=context + ":" + str(index))
            memory.consolidate(max_events=4)
        memory = AssociativeMemory(json.loads(json.dumps(memory.state)))
        for context in ("woods", "shore"):
            for index in range(4):
                query = {"context": context, "cue": "  BEACON\t" + str(index) + " "}
                with self.subTest(**query):
                    consolidated = self.recall(memory, mode="consolidated", **query)
                    archive = self.recall(memory, mode="archive", **query)
                    self.assert_answer(consolidated, context + ":" + str(index),
                                       [context + "-" + str(index)])
                    self.assertEqual(consolidated["answer"], archive["answer"])
                    self.assertEqual(consolidated["evidence_ids"], archive["evidence_ids"])
        self.assertEqual(self.recall(memory, cue="BEACON 0", context="woods",
                                     mode="working", working_limit=4)["status"], "unknown")

    def test_constructor_stages_a_deep_copy_of_supplied_state(self):
        memory = AssociativeMemory()
        self.observe(memory, "one")
        memory.consolidate()
        supplied = copy.deepcopy(memory.state)
        restored = AssociativeMemory(supplied)
        supplied["events"][0]["answer"] = "external mutation"
        self.assert_answer(self.recall(restored), "amber", ["one"])
        self.observe(restored, "two", cue="second")
        self.assertEqual(len(memory.state["events"]), 1)
        self.assertEqual(len(supplied["events"]), 1)

    def test_corrupted_cursor_digest_or_derived_evidence_is_refused(self):
        memory = AssociativeMemory()
        self.observe(memory, "one")
        memory.consolidate()
        pristine = copy.deepcopy(memory.state)
        corruptions = []
        for cursor in (-1, True, len(pristine["events"]) + 1):
            corrupt = copy.deepcopy(pristine)
            corrupt["cursor"] = cursor
            corruptions.append(("cursor-" + str(cursor), corrupt))
        corrupt = copy.deepcopy(pristine)
        corrupt["prefix_digest"] = "0" * 64
        corruptions.append(("digest", corrupt))
        corrupt = copy.deepcopy(pristine)
        next(iter(corrupt["associations"].values()))[0]["answer"] = "invented answer"
        corruptions.append(("derived-answer", corrupt))
        corrupt = copy.deepcopy(pristine)
        corrupt["events"][0]["source"] = "changed source"
        corruptions.append(("processed-source", corrupt))
        for label, corrupt in corruptions:
            with self.subTest(label=label):
                before = copy.deepcopy(corrupt)
                with self.assertRaises(ValueError):
                    AssociativeMemory(corrupt)
                self.assertEqual(corrupt, before)

    def test_fresh_interpreter_retains_pending_correction_and_consolidated_sources(self):
        memory = AssociativeMemory()
        self.observe(memory, "old")
        memory.consolidate()
        self.observe(memory, "correct", answer="violet", kind="correction",
                     supersedes=["old"])
        code = (
            "import json, sys\n"
            "from associative_memory import AssociativeMemory\n"
            "memory = AssociativeMemory(json.load(sys.stdin))\n"
            "result = {mode: memory.recall('Dylan', 'woods', 'BEACON', mode=mode) "
            "for mode in ('consolidated', 'combined', 'archive')}\n"
            "print(json.dumps(result, sort_keys=True))\n"
        )
        process = subprocess.run(
            [sys.executable, "-c", code], input=json.dumps(memory.state),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=str(ROOT), timeout=15, check=True,
        )
        result = json.loads(process.stdout)
        self.assert_answer(result["consolidated"], "amber", ["old"])
        for mode in ("combined", "archive"):
            self.assert_answer(result[mode], "violet", ["correct"])


if __name__ == "__main__":
    unittest.main()
