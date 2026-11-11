"""Explicit, scoped associations with a replayable consolidation cursor.

This is symbolic learning from supplied observations, not neural training.
Raw events are preserved. Hypotheses never support factual recall. Loading and
serializing a state are O(history); a consolidation budget limits raw events
processed by that call, not total disk I/O. Treat ``state`` as read-only outside
this class and persist it through the parent memory's guarded save operation.
"""

import copy
import hashlib
import json
import unicodedata
import uuid


_EVENT_FIELDS = {
    "event_id", "user", "context", "cue", "answer", "source", "kind",
    "supersedes",
}
_STATE_FIELDS = {"version", "events", "cursor", "associations", "prefix_digest"}
_EVIDENCE_FIELDS = {"event_id", "answer", "source"}
_KINDS = {"observation", "correction", "hypothesis"}
_MODES = {"combined", "consolidated", "archive", "working"}


def _text(value, field, limit):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ValueError("invalid associative memory " + field)
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("invalid associative memory " + field) from None
    return value


def _budget(value, field):
    if type(value) is not int or not 1 <= value <= 256:
        raise ValueError(field + " must be an integer from 1 to 256")
    return value


def _normalized(cue):
    return " ".join(unicodedata.normalize("NFKC", cue).casefold().split())


def _scope(user, context, cue):
    return json.dumps([user, context, _normalized(cue)], ensure_ascii=True,
                      separators=(",", ":"))


def _digest(events):
    data = json.dumps(events, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("ascii")).hexdigest()


def _check_event(event):
    if type(event) is not dict or set(event) != _EVENT_FIELDS:
        raise ValueError("invalid associative memory event structure")
    for field in ("user", "context", "cue", "source"):
        _text(event[field], field, 512)
    _text(event["answer"], "answer", 2048)
    _text(event["event_id"], "event_id", 128)
    if not _normalized(event["cue"]):
        raise ValueError("invalid associative memory normalized cue")
    if type(event["kind"]) is not str or event["kind"] not in _KINDS:
        raise ValueError("invalid associative memory event kind")
    targets = event["supersedes"]
    if type(targets) is not list:
        raise ValueError("supersedes must be a list of event IDs")
    for target in targets:
        _text(target, "superseded event_id", 128)
    if len(targets) != len(set(targets)):
        raise ValueError("supersedes contains duplicate event IDs")
    if event["kind"] == "correction":
        if not targets:
            raise ValueError("a correction requires superseded event IDs")
    elif targets:
        raise ValueError("only a correction may supersede evidence")


def _check_targets(event, prior, associations):
    if event["kind"] != "correction":
        return
    key = _scope(event["user"], event["context"], event["cue"])
    active = {item["event_id"] for item in associations.get(key, [])}
    for target_id in event["supersedes"]:
        target = prior.get(target_id)
        if target is None or target["kind"] == "hypothesis":
            raise ValueError("correction target is not earlier factual evidence")
        if _scope(target["user"], target["context"], target["cue"]) != key:
            raise ValueError("correction target belongs to a different scope")
        if target_id not in active:
            raise ValueError("correction target is already superseded")


def _apply(associations, event):
    """Fold a validated event; a truncated working view may omit its targets."""
    if event["kind"] == "hypothesis":
        return
    key = _scope(event["user"], event["context"], event["cue"])
    targets = set(event["supersedes"])
    evidence = [item for item in associations.get(key, [])
                if item["event_id"] not in targets]
    evidence.append({field: event[field] for field in _EVIDENCE_FIELDS})
    associations[key] = evidence


def _check_associations(associations):
    if type(associations) is not dict:
        raise ValueError("invalid associative memory associations")
    for key, evidence in associations.items():
        if type(key) is not str or type(evidence) is not list:
            raise ValueError("invalid associative memory association structure")
        for item in evidence:
            if type(item) is not dict or set(item) != _EVIDENCE_FIELDS:
                raise ValueError("invalid associative memory evidence structure")
            _text(item["event_id"], "evidence event_id", 128)
            _text(item["answer"], "evidence answer", 2048)
            _text(item["source"], "evidence source", 512)


class AssociativeMemory:
    """A staged, JSON-compatible observation ledger and derived lookup table."""

    def __init__(self, state=None):
        if state is None:
            state = {"version": 1, "events": [], "cursor": 0,
                     "associations": {}, "prefix_digest": _digest([])}
        if type(state) is not dict or set(state) != _STATE_FIELDS:
            raise ValueError("invalid associative memory state structure")
        self.state = copy.deepcopy(state)
        data = self.state
        if type(data["version"]) is not int or data["version"] != 1:
            raise ValueError("unsupported associative memory state version")
        if type(data["events"]) is not list:
            raise ValueError("invalid associative memory event ledger")
        cursor = data["cursor"]
        if type(cursor) is not int or not 0 <= cursor <= len(data["events"]):
            raise ValueError("invalid associative memory cursor")
        self._events_by_id = {}
        self._all_associations = {}
        expected = {}
        for position, event in enumerate(data["events"]):
            _check_event(event)
            if event["event_id"] in self._events_by_id:
                raise ValueError("duplicate associative memory event ID")
            _check_targets(event, self._events_by_id, self._all_associations)
            _apply(self._all_associations, event)
            self._events_by_id[event["event_id"]] = event
            if position < cursor:
                _apply(expected, event)
        _check_associations(data["associations"])
        if data["associations"] != expected:
            raise ValueError("associative memory derived evidence mismatch")
        if (type(data["prefix_digest"]) is not str or
                data["prefix_digest"] != _digest(data["events"][:cursor])):
            raise ValueError("associative memory processed-prefix digest mismatch")

    def observe(self, user, context, cue, answer, source, event_id=None,
                kind="observation", supersedes=None):
        """Append explicit evidence; an identical explicit-ID retry is a no-op."""
        event = {"event_id": uuid.uuid4().hex if event_id is None else event_id,
                 "user": user, "context": context, "cue": cue, "answer": answer,
                 "source": source, "kind": kind,
                 "supersedes": [] if supersedes is None else copy.deepcopy(supersedes)}
        _check_event(event)
        previous = self._events_by_id.get(event["event_id"])
        if previous is not None:
            if previous != event:
                raise ValueError("event ID was already used for a different payload")
            return {"created": False, "event_id": event["event_id"]}
        _check_targets(event, self._events_by_id, self._all_associations)
        self.state["events"].append(event)
        self._events_by_id[event["event_id"]] = event
        _apply(self._all_associations, event)
        return {"created": True, "event_id": event["event_id"]}

    def consolidate(self, max_events=32):
        """Process at most max_events raw records, including hypotheses."""
        _budget(max_events, "max_events")
        start = self.state["cursor"]
        end = min(start + max_events, len(self.state["events"]))
        if end > start:
            associations = copy.deepcopy(self.state["associations"])
            for event in self.state["events"][start:end]:
                _apply(associations, event)
            digest = _digest(self.state["events"][:end])
            # Publish the derived table and its cursor together within this stage.
            self.state = dict(self.state, associations=associations, cursor=end,
                              prefix_digest=digest)
        return {"processed": end - start,
                "pending": len(self.state["events"]) - end, "cursor": end}

    def recall(self, user, context, cue, mode="combined", working_limit=32):
        """Return evidence or abstain; conflicting answers never become votes."""
        for field, value in (("user", user), ("context", context), ("cue", cue)):
            _text(value, field, 512)
        if not _normalized(cue):
            raise ValueError("invalid associative memory normalized cue")
        if type(mode) is not str or mode not in _MODES:
            raise ValueError("invalid associative memory recall mode")
        _budget(working_limit, "working_limit")
        key = _scope(user, context, cue)
        events = self.state["events"]
        cursor = self.state["cursor"]
        if mode in ("combined", "consolidated"):
            view = {key: copy.deepcopy(self.state["associations"].get(key, []))}
            remaining = events[cursor:] if mode == "combined" else ()
        else:
            view = {}
            remaining = events if mode == "archive" else events[-working_limit:]
        for event in remaining:
            if _scope(event["user"], event["context"], event["cue"]) == key:
                _apply(view, event)
        evidence = view.get(key, [])
        candidates = {}
        sources = []
        for item in evidence:
            candidate = candidates.setdefault(item["answer"],
                {"answer": item["answer"], "evidence_ids": [], "sources": []})
            candidate["evidence_ids"].append(item["event_id"])
            if item["source"] not in candidate["sources"]:
                candidate["sources"].append(item["source"])
            if item["source"] not in sources:
                sources.append(item["source"])
        choices = list(candidates.values())
        status = "unknown" if not choices else "recalled" if len(choices) == 1 else "conflict"
        return {"status": status,
                "answer": choices[0]["answer"] if status == "recalled" else None,
                "candidates": choices,
                "evidence_ids": [item["event_id"] for item in evidence],
                "sources": sources, "mode": mode, "pending": len(events) - cursor}

    def snapshot(self):
        """Compact counts; no source text is included."""
        data = self.state
        return {"version": data["version"], "events": len(data["events"]),
                "consolidated": data["cursor"],
                "pending": len(data["events"]) - data["cursor"],
                "scopes": len(data["associations"]),
                "active_evidence": sum(len(items) for items in data["associations"].values())}
