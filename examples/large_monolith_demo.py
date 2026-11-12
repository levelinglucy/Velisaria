"""A disposable demonstration of the restored larger recursive core.

Run from any directory with Python 3.11+; no device packages or owner data are
used. The evidence ledger, generated dreams and restart all use a temporary path.
"""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from velisara_monolith_final_fixed_empathy import Velisara


def main():
    with tempfile.TemporaryDirectory() as directory:
        state = Path(directory) / "demonstration.json"
        core = Velisara(state_file=state, seed=42, learning=True)
        before = core.step("blue lamp", user="demo", context="route")
        core.learning_command({
            "op": "remember", "user": "demo", "context": "route",
            "cue": "blue lamp", "answer": "choose the left path",
            "source": "synthetic observed route", "event_id": "demo-observation",
        })
        after = core.step("blue lamp", user="demo", context="route")
        dreams = core.trigger_dream_loop(3)
        consolidated = core.learning_command({"op": "sleep", "max_events": 1})
        core.save_state()
        core.close()

        restarted = Velisara(state_file=state, seed=999, learning=True)
        recalled = restarted.learning_command({
            "op": "recall", "user": "demo", "context": "route", "cue": "blue lamp",
        })
        if before["recall"]["status"] != "unknown":
            raise RuntimeError("unexpected evidence before the observation")
        if after["recall"]["answer"] != "choose the left path" or recalled != after["recall"] | {"pending": 0}:
            raise RuntimeError("sourced evidence did not survive consolidation/restart")
        if len(restarted.dream_loop.dream_log) != 3:
            raise RuntimeError("recursive dream fragments were not preserved")
        if len(restarted.learner.state["events"]) != 1:
            raise RuntimeError("generated dreams were incorrectly promoted to evidence")
        print(json.dumps({
            "before": before["recall"]["status"],
            "after": after["response"],
            "dream_fragments": len(dreams),
            "consolidated": consolidated["processed"],
            "restart_recall": recalled["answer"],
            "retained_observations": len(restarted.learner.state["events"]),
        }, indent=2))
        restarted.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
