#!/usr/bin/env python3
"""Deterministic toy evaluation of explicit associative memory.

Train 12 A records, then 12 B records with the same cues in another context.
Evaluation inputs differ only in case and whitespace; they are never observed
as training events. This checks scoped retention and normalization, not neural
learning or semantic/conceptual generalization. Full archive lookup is the
baseline and should be just as accurate as the consolidated lookup.

Only a temporary JSON state file is written. No owner history is accessed.
Run from any directory: python /path/to/examples/associative_memory_demo.py
"""

import copy
import json
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from associative_memory import AssociativeMemory


USER = "synthetic-demo"
BATCH_SIZE = 5
WORKING_LIMIT = 4
FULL_MODES = ("archive", "combined", "consolidated")


def _rows(label, context):
    return [
        {
            "user": USER,
            "context": context,
            "cue": "signal {:02d}".format(index),
            "answer": "{} answer {:02d}".format(label, index),
            "source": "synthetic:{}:{:02d}".format(label, index),
            "event_id": "{}-{:02d}".format(label.lower(), index),
        }
        for index in range(12)
    ]


def _queries(rows):
    return [dict(row, query="  " + row["cue"].upper().replace(" ", " \t ") + "  ")
            for row in rows]


def _serialized(memory):
    return json.dumps(memory.state, sort_keys=True, allow_nan=False)


def _evaluate(memory, cases, mode):
    before = _serialized(memory)
    correct = 0
    statuses = {}
    failures = []
    for case in cases:
        result = memory.recall(case["user"], case["context"], case["query"],
                               mode=mode, working_limit=WORKING_LIMIT)
        status = result["status"]
        statuses[status] = statuses.get(status, 0) + 1
        if status == "recalled" and result["answer"] == case["answer"]:
            correct += 1
        else:
            failures.append({"query": case["query"], "status": status,
                             "expected": case["answer"], "answer": result["answer"]})
    if _serialized(memory) != before:
        raise AssertionError("Evaluation recall mutated the training state")
    report = {"correct": correct, "total": len(cases),
              "accuracy": correct / len(cases), "status_counts": statuses}
    if failures:
        report["unmatched_queries"] = failures
    return report


def _compare(memory, cases, modes=FULL_MODES):
    return {mode: _evaluate(memory, cases, mode) for mode in modes}


def _drain(memory):
    """Bound each consolidation pass; refuse a stalled or unbounded schedule."""
    trace = []
    previous_pending = len(memory.state["events"]) - memory.state["cursor"]
    for _ in range(previous_pending + 1):
        result = memory.consolidate(max_events=BATCH_SIZE)
        processed, pending = result["processed"], result["pending"]
        if not (type(processed) is int and 0 <= processed <= BATCH_SIZE and
                type(pending) is int and pending == previous_pending - processed):
            raise AssertionError("Consolidation violated its event budget or cursor")
        trace.append(dict(result))
        if pending == 0:
            return trace
        if processed == 0:
            raise AssertionError("Consolidation stalled with pending events")
        previous_pending = pending
    raise AssertionError("Consolidation did not drain within a finite schedule")


def _recall(memory, row, mode="combined"):
    return memory.recall(row["user"], row["context"], row["cue"], mode=mode)


def run_demo():
    """Return JSON-safe measurements and acceptance checks, without owner data."""
    memory = AssociativeMemory()
    rows_a, rows_b = _rows("A", "context-a"), _rows("B", "context-b")
    cases_a, cases_b = _queries(rows_a), _queries(rows_b)
    checks = {}
    phases = {}
    sleep_passes = {}

    for row in rows_a:
        memory.observe(**row)
    sleep_passes["after_a"] = _drain(memory)
    phases["after_a_consolidation"] = {"set_a": _compare(memory, cases_a)}
    checks["a_learned"] = all(
        metric["correct"] == 12
        for metric in phases["after_a_consolidation"]["set_a"].values())

    for row in rows_b:
        memory.observe(**row)
    phases["before_b_consolidation"] = {"set_b": _compare(memory, cases_b)}
    before_b = phases["before_b_consolidation"]["set_b"]
    checks["new_events_available_before_consolidation"] = (
        before_b["archive"]["correct"] == before_b["combined"]["correct"] == 12 and
        before_b["consolidated"]["status_counts"] == {"unknown": 12})

    sleep_passes["after_b"] = _drain(memory)
    phases["after_b_consolidation"] = {
        "set_a": _compare(memory, cases_a, FULL_MODES + ("working",)),
        "set_b": _compare(memory, cases_b, FULL_MODES + ("working",)),
    }
    retained = phases["after_b_consolidation"]
    checks["a_retained_after_b"] = all(retained["set_a"][m]["correct"] == 12
                                               for m in FULL_MODES)
    checks["b_learned_without_context_collision"] = all(
        retained["set_b"][m]["correct"] == 12 for m in FULL_MODES)
    checks["archive_and_consolidated_accuracy_equal"] = all(
        retained[s]["archive"]["correct"] == retained[s]["consolidated"]["correct"]
        for s in ("set_a", "set_b"))
    checks["bounded_working_ablation"] = (
        retained["set_a"]["working"]["correct"] == 0 and
        retained["set_b"]["working"]["correct"] == WORKING_LIMIT)
    original_events = copy.deepcopy(memory.state["events"])

    provenance = _recall(memory, rows_a[0], mode="consolidated")
    checks["original_source_retained"] = (
        provenance["evidence_ids"] == [rows_a[0]["event_id"]] and
        provenance["sources"] == [rows_a[0]["source"]])

    duplicate = dict(rows_a[0], event_id="a-00-duplicate", source="synthetic:duplicate")
    memory.observe(**duplicate)
    retry = memory.observe(**duplicate)
    sleep_passes["after_duplicate"] = _drain(memory)
    duplicate_result = _recall(memory, rows_a[0], mode="consolidated")
    empty_sleep_state = _serialized(memory)
    empty_sleeps = [memory.consolidate(max_events=BATCH_SIZE) for _ in range(3)]
    checks["no_repeated_support_from_retry_or_sleep"] = (
        retry["created"] is False and
        duplicate_result["evidence_ids"] == ["a-00", "a-00-duplicate"] and
        all(r["processed"] == r["pending"] == 0 for r in empty_sleeps) and
        _serialized(memory) == empty_sleep_state and
        _recall(memory, rows_a[0], mode="consolidated") == duplicate_result)

    contradiction = dict(rows_a[0], event_id="a-00-conflict",
                         source="synthetic:contradiction", answer="contradictory answer")
    memory.observe(**contradiction)
    sleep_passes["after_conflict"] = _drain(memory)
    conflict = _recall(memory, rows_a[0], mode="consolidated")
    checks["conflict_abstains_even_against_duplicate_evidence"] = (
        conflict["status"] == "conflict" and conflict["answer"] is None and
        len(conflict["candidates"]) == 2 and len(conflict["evidence_ids"]) == 3)

    superseded = ["a-00", "a-00-duplicate", "a-00-conflict"]
    correction = dict(rows_a[0], event_id="a-00-correction", answer="corrected A answer 00",
                      source="synthetic:explicit-correction", kind="correction",
                      supersedes=superseded)
    memory.observe(**correction)
    correction_pending = _recall(memory, rows_a[0])
    sleep_passes["after_correction"] = _drain(memory)
    corrected = _recall(memory, rows_a[0], mode="consolidated")
    checks["explicit_correction_supersedes_all_old_duplicates"] = all(
        result["status"] == "recalled" and result["answer"] == correction["answer"] and
        result["evidence_ids"] == [correction["event_id"]] and
        result["sources"] == [correction["source"]]
        for result in (correction_pending, corrected))

    hypothesis_existing = dict(rows_a[1], event_id="hypothesis-existing",
                               source="synthetic:generated-hypothesis", kind="hypothesis")
    hypothesis_only = dict(rows_a[1], cue="unverified signal", answer="imagined answer",
                           event_id="hypothesis-only", source="synthetic:generated-hypothesis",
                           kind="hypothesis")
    memory.observe(**hypothesis_existing)
    memory.observe(**hypothesis_only)
    sleep_passes["after_hypotheses"] = _drain(memory)
    checks["hypotheses_do_not_supply_factual_evidence"] = all(
        _recall(memory, hypothesis_only, mode=m)["status"] == "unknown" and
        _recall(memory, rows_a[1], mode=m)["evidence_ids"] == [rows_a[1]["event_id"]]
        for m in FULL_MODES)

    abstentions = {
        "unknown_cue": memory.recall(USER, "context-a", "never observed"),
        "other_user": memory.recall("another-user", "context-a", rows_a[1]["cue"]),
        "other_context": memory.recall(USER, "context-c", rows_a[1]["cue"]),
        "hypothesis_only": _recall(memory, hypothesis_only),
    }
    checks["unknown_and_other_scopes_abstain"] = all(
        r["status"] == "unknown" and r["answer"] is None and not r["evidence_ids"]
        for r in abstentions.values())
    checks["raw_training_events_preserved"] = memory.state["events"][:24] == original_events
    held_out_forms = {case["query"] for case in cases_a + cases_b}
    checks["evaluation_forms_never_observed"] = all(
        event["cue"] not in held_out_forms for event in memory.state["events"])

    # Restore only synthetic association state; this is not a durability test
    # or a test of the surrounding Monolith's guarded publication path.
    state_before_restart = _serialized(memory)
    with tempfile.TemporaryDirectory(prefix="velisaria-association-demo-") as directory:
        path = Path(directory) / "synthetic_state.json"
        path.write_text(state_before_restart, encoding="utf-8")
        restored = AssociativeMemory(json.loads(path.read_text(encoding="utf-8")))
    updated_a = copy.deepcopy(cases_a)
    updated_a[0]["answer"] = correction["answer"]
    phases["after_restart"] = {
        "set_a_with_explicit_correction": _compare(restored, updated_a),
        "set_b": _compare(restored, cases_b),
    }
    checks["restart_preserves_state_and_answers"] = (
        _serialized(restored) == state_before_restart and
        all(metric["correct"] == 12 for group in phases["after_restart"].values()
            for metric in group.values()) and
        _recall(restored, rows_a[0], mode="consolidated") == corrected)

    return {
        "experiment": "Toy scoped associative retention and consolidation",
        "setup": {"base_training_observations": 24, "set_a": 12, "set_b": 12,
                  "shared_cues_in_distinct_contexts": True,
                  "held_out_forms": "Case and whitespace changes only",
                  "evaluation_records_added_as_training": 0,
                  "consolidation_batch_limit": BATCH_SIZE, "working_window": WORKING_LIMIT,
                  "total_events_including_explicit_checks": len(memory.state["events"])},
        "limitations": [
            "Explicit supplied cue-answer associations; no neural weights are trained.",
            "Normalization is tested, not semantic or conceptual generalization.",
            "Full archive lookup has the same information and should match consolidation accuracy.",
            "No latency, speedup, memory-efficiency, or broad continual-learning claim is measured.",
            "Temporary JSON round trip only; no Monolith, device, or crash-durability claim.",
        ],
        "phases": phases, "consolidation_passes": sleep_passes,
        "provenance_example": provenance,
        "duplicate_evidence_before_conflict": duplicate_result,
        "conflict": conflict,
        "correction": {"superseded_event_ids": superseded, "result": corrected},
        "abstentions": abstentions, "empty_consolidation_passes": empty_sleeps,
        "checks": checks, "acceptance_passed": all(checks.values()),
    }


def main():
    try:
        report = run_demo()
    except (AssertionError, ValueError) as exc:
        print(json.dumps({"acceptance_passed": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
