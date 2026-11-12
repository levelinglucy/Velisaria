"""Small persistence primitives shared by the repaired large Velisara monolith.

Snapshots are complete JSON objects. The caller owns their schema, preserves
unknown fields, and publishes live changes only after ``save`` succeeds. This
module never prunes, repairs, merges or selects between competing histories.

Like the maintained sanctified monolith, disk saves detect sequential stale
writers and synchronize the staged file before atomic replacement. This is not
a filesystem lock: simultaneous writers or path swaps can still race, parent
directory aliases are not checked, and the containing directory is not fsynced.
"""

import hashlib
import inspect
import json
import math
import os
import random
import stat
from datetime import datetime
from decimal import Decimal, InvalidOperation


class SnapshotError(RuntimeError):
    """A snapshot could not be loaded or committed without risking its history."""


class SnapshotLoadError(SnapshotError):
    """Existing snapshot evidence could not be loaded safely."""


class SnapshotSaveError(SnapshotError):
    """The candidate was not published; preserve any remaining staging file."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate snapshot JSON key: {!r}".format(key))
        result[key] = value
    return result


def _reject_constant(token):
    raise ValueError("nonstandard snapshot JSON number: " + token)


def _finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("snapshot JSON number exceeds finite float range")
    try:
        if Decimal(token) != Decimal(repr(value)):
            raise ValueError("snapshot JSON decimal loses numeric precision")
    except InvalidOperation as exc:
        raise ValueError("snapshot JSON decimal cannot be checked") from exc
    return value


def _check_nesting(raw, maximum=256):
    depth = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > maximum:
                raise ValueError("snapshot JSON nesting exceeds 256 containers")
        elif char in "]}":
            depth -= 1


def strict_json_loads(raw):
    """Decode JSON without ambiguous keys, nonfinite or lossy decimal values.

    Accept UTF-8 bytes or text. Root/schema validation belongs to the caller;
    ``SnapshotStore`` additionally requires an object at the root.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        raise ValueError("snapshot JSON must be text or UTF-8 bytes")
    _check_nesting(raw)
    return json.loads(raw, object_pairs_hook=_unique_object,
                      parse_constant=_reject_constant, parse_float=_finite_float)


def _check_keys(value, active=None):
    """Refuse implicit stringification of JSON object keys before encoding."""
    if not isinstance(value, (dict, list, tuple)):
        return
    if active is None:
        active = set()
    identity = id(value)
    if identity in active:
        raise ValueError("snapshot contains a circular reference")
    active.add(identity)
    try:
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ValueError("snapshot object keys must be strings")
                _check_keys(child, active)
        else:
            for child in value:
                _check_keys(child, active)
    finally:
        active.remove(identity)


def _serialize(candidate):
    if not isinstance(candidate, dict):
        raise ValueError("snapshot root must be a JSON object")
    _check_keys(candidate)
    raw = json.dumps(candidate, ensure_ascii=True, indent=2, allow_nan=False)
    # Validate depth and the exact representation which the next loader sees.
    # Standard JSON array normalization of tuple values is intentional; tuple
    # object keys must instead use an explicit schema such as encode_pairs.
    normalized = strict_json_loads(raw)
    return raw.encode("utf-8"), normalized


class SnapshotStore:
    """A guarded complete-snapshot store; ``None`` selects in-memory storage.

    Call ``load(default)`` before the first disk save. Loading an absent file
    returns a detached copy of the default (or ``{}``) without writing it.
    ``save(candidate)`` returns a detached, JSON-normalized committed value.
    Unknown fields are retained when the caller carries them into candidates.
    """

    def __init__(self, path):
        self.path = None if path is None else os.fspath(path)
        if self.path is not None and not isinstance(self.path, str):
            raise ValueError("snapshot path must be a text path or None")
        self._loaded = False
        self._digest = None
        self._memory = None

    def _inspect(self):
        try:
            mode = os.lstat(self.path).st_mode
        except FileNotFoundError:
            return
        if stat.S_ISLNK(mode):
            raise ValueError("snapshot path is a symbolic link; use a direct regular file")
        if not stat.S_ISREG(mode):
            raise ValueError("snapshot path is not a regular file")

    def _current_bytes(self):
        self._inspect()
        try:
            with open(self.path, "rb") as stream:
                return stream.read()
        except FileNotFoundError:
            if os.path.lexists(self.path):
                raise ValueError("snapshot path is unresolved")
            return None

    def _refuse_temporary(self):
        if os.path.lexists(self.path + ".tmp"):
            raise ValueError("snapshot .tmp already exists; preserve and inspect both copies")

    def load(self, default=None):
        try:
            if self.path is None:
                source = self._memory if self._memory is not None else default
                _, loaded = _serialize({} if source is None else source)
                self._memory = loaded
                # A returned value must never expose the store's live object.
                _, result = _serialize(loaded)
                self._loaded = True
                return result
            self._refuse_temporary()
            raw = self._current_bytes()
            if raw is None:
                _, loaded = _serialize({} if default is None else default)
                digest = None
            else:
                loaded = strict_json_loads(raw)
                if not isinstance(loaded, dict):
                    raise ValueError("snapshot root must be a JSON object")
                digest = hashlib.sha256(raw).digest()
            # Adopt the generation only after the complete read has succeeded.
            self._digest = digest
            self._loaded = True
            return loaded
        except (OSError, UnicodeError, ValueError, TypeError,
                OverflowError, RecursionError) as exc:
            raise SnapshotLoadError("Cannot load snapshot; all files left unchanged: "
                                    + str(exc)) from exc

    def save(self, candidate):
        try:
            raw, normalized = _serialize(candidate)
            if self.path is None:
                self._memory = normalized
                self._loaded = True
                # Serialize again for detachment; no disk side effect occurred.
                return strict_json_loads(raw)
            if not self._loaded:
                raise ValueError("load the snapshot before saving a candidate")
            self._refuse_temporary()
            current = self._current_bytes()
            digest = None if current is None else hashlib.sha256(current).digest()
            if digest != self._digest:
                raise ValueError("snapshot changed since load or last save")
            published_digest = hashlib.sha256(raw).digest()
            with open(self.path + ".tmp", "xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(self.path + ".tmp", self.path)
            # No fallible work follows publication. In particular, directory
            # fsync would need its own committed-but-durability-uncertain result.
            self._digest = published_digest
            return normalized
        except (OSError, UnicodeError, ValueError, TypeError,
                OverflowError, RecursionError) as exc:
            raise SnapshotSaveError("Snapshot was not committed; preserve all files: "
                                    + str(exc)) from exc


def encode_pairs(pairs):
    """Encode a mythos pair-count mapping as explicit JSON pair records.

    Schema: ``[{"symbols": ["first", "second"], "count": nonnegative_int}]``.
    Pair order and map insertion order are preserved; no string-key guessing.
    """
    if not isinstance(pairs, dict):
        raise ValueError("mythos pairs must be a mapping")
    result = []
    for pair, count in pairs.items():
        if (type(pair) is not tuple or len(pair) != 2
                or any(type(symbol) is not str for symbol in pair)):
            raise ValueError("mythos pair keys must be two-string tuples")
        if type(count) is not int or count < 0:
            raise ValueError("mythos pair counts must be nonnegative integers")
        result.append({"symbols": list(pair), "count": count})
    return result


def decode_pairs(records):
    """Decode only the documented pair-record schema, refusing duplicates."""
    if not isinstance(records, list):
        raise ValueError("mythos pair records must be a list")
    pairs = {}
    for record in records:
        if (type(record) is not dict or set(record) != {"symbols", "count"}
                or type(record["symbols"]) is not list
                or len(record["symbols"]) != 2
                or any(type(symbol) is not str for symbol in record["symbols"])):
            raise ValueError("invalid mythos pair record")
        pair, count = tuple(record["symbols"]), record["count"]
        if type(count) is not int or count < 0 or pair in pairs:
            raise ValueError("invalid or duplicate mythos pair count")
        pairs[pair] = count
    return pairs


def encode_state(value, _active=None):
    """Encode supported symbolic data with unambiguous tagged containers.

    Every container is tagged, including ordinary dictionaries, so user keys
    cannot accidentally become control tags. Owner/organ references and runtime
    handles must be excluded explicitly by the coordinator. Cyclic containers
    and arbitrary objects are refused; this is data encoding, never pickle.
    """
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("symbolic state contains a nonfinite float")
        return value
    if type(value) is datetime:
        return {"kind": "datetime", "value": value.isoformat(), "fold": value.fold}
    if type(value) not in (dict, list, tuple, set):
        raise ValueError("unsupported symbolic state type: " + type(value).__name__)
    active = set() if _active is None else _active
    identity = id(value)
    if identity in active:
        raise ValueError("symbolic state contains a cyclic data container")
    active.add(identity)
    try:
        if type(value) is dict:
            items = [[encode_state(key, active), encode_state(item, active)]
                     for key, item in value.items()]
            kind = "dict"
        else:
            items = [encode_state(item, active) for item in value]
            kind = type(value).__name__
            if kind == "set":
                items.sort(key=lambda item: json.dumps(item, sort_keys=True,
                                                      ensure_ascii=True))
        return {"kind": kind, "items": items}
    finally:
        active.remove(identity)


def decode_state(value, _depth=0):
    """Decode and validate the tagged data schema without constructing code."""
    if _depth > 128:
        raise ValueError("symbolic state nesting exceeds safe limit")
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("symbolic state contains a nonfinite float")
        return value
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise ValueError("symbolic state container requires an explicit kind")
    kind = value["kind"]
    if kind == "datetime":
        if (set(value) != {"kind", "value", "fold"}
                or type(value["value"]) is not str
                or type(value["fold"]) is not int or value["fold"] not in (0, 1)):
            raise ValueError("invalid symbolic datetime")
        return datetime.fromisoformat(value["value"]).replace(fold=value["fold"])
    if (kind not in {"dict", "list", "tuple", "set"}
            or set(value) != {"kind", "items"} or type(value["items"]) is not list):
        raise ValueError("invalid symbolic container schema")
    items = value["items"]
    if kind == "dict":
        result = {}
        for pair in items:
            if type(pair) is not list or len(pair) != 2:
                raise ValueError("symbolic dictionary entries must be key/value pairs")
            key = decode_state(pair[0], _depth + 1)
            item = decode_state(pair[1], _depth + 1)
            try:
                if key in result:
                    raise ValueError("duplicate symbolic dictionary key")
                result[key] = item
            except TypeError as exc:
                raise ValueError("unhashable symbolic dictionary key") from exc
        return result
    decoded = [decode_state(item, _depth + 1) for item in items]
    if kind == "tuple":
        return tuple(decoded)
    if kind == "set":
        try:
            result = set(decoded)
        except TypeError as exc:
            raise ValueError("unhashable symbolic set member") from exc
        if len(result) != len(decoded):
            raise ValueError("duplicate symbolic set member")
        return result
    return decoded


class ContinuityState:
    """Capture and restore registered organs without replacing their identity.

    ``transient_names`` contains owner attribute names or ``organ.attribute``
    names. Organ owner references named vel/mm/memory_manager/rng are always
    excluded. Every other value must have a supported data representation.

    A restore validates the complete candidate before touching any live state.
    Callers serialize operations on the owner and use snapshot/restore around
    mutations whose save may fail; this coordinator is not a thread lock.
    """

    _FIELDS = {"schema_version", "organs", "symbolic_state", "rng_state",
               "associative_memory"}
    _REFERENCES = {"vel", "mm", "memory_manager", "rng"}
    _LEGACY = {"working_memory", "dream_log", "mythos", "mythos_keywords",
               "symbol_weights", "symbol_logs", "symbols", "co_occurrence"}

    def __init__(self, owner, path, organ_names, transient_names=()):
        self.owner = owner
        self.store = SnapshotStore(path)
        self.organ_names = tuple(organ_names)
        if len(set(self.organ_names)) != len(self.organ_names):
            raise ValueError("continuity organ names must be unique")
        self.transient_names = frozenset(transient_names)
        self._extra = {}
        self._unknown_organs = {}
        self._dormant = None
        self._schemas = {}
        seen = set()
        for name in self.organ_names:
            organ = getattr(owner, name)
            if id(organ) in seen:
                raise ValueError("register each organ once, excluding aliases: " + name)
            seen.add(id(organ))
            self._schemas[name] = {
                key: type(value) for key, value in vars(organ).items()
                if not self._excluded(name, key)
            }
        self._owner_schema = {key: type(value) for key, value in vars(owner).items()
                              if not self._excluded(None, key)}

    def _excluded(self, organ, attribute):
        if organ is None:
            return attribute in self.organ_names or attribute in self.transient_names
        return (attribute in self._REFERENCES
                or organ + "." + attribute in self.transient_names)

    def _capture(self, target, name=None):
        return {key: value for key, value in vars(target).items()
                if not self._excluded(name, key)}

    def snapshot(self):
        organs = dict(self._unknown_organs)
        for name in self.organ_names:
            organs[name] = encode_state(self._capture(getattr(self.owner, name), name))
        learner = getattr(self.owner, "learner", None)
        evidence = (learner.state if learner is not None else
                    getattr(self.owner, "_dormant_learning", self._dormant))
        result = dict(self._extra)
        result.update(schema_version=1, organs=organs,
                      symbolic_state=encode_state(self._capture(self.owner)),
                      rng_state=encode_state(self.owner.rng.getstate()),
                      associative_memory=evidence)
        # Deep detachment also verifies the complete JSON representation.
        _, result = _serialize(result)
        return result

    @staticmethod
    def _matches_type(expected, value):
        if expected is type(None):
            return True  # Optional/dynamically initialized field.
        if expected is float:
            return type(value) in (int, float)
        return type(value) is expected

    def _validate_attributes(self, name, values, expected, target):
        if type(values) is not dict or any(type(key) is not str for key in values):
            raise ValueError("continuity attributes must be a string-keyed dictionary")
        if not set(expected).issubset(values):
            raise ValueError("missing initialized attributes in " + (name or "owner"))
        for key, value in values.items():
            # Inspect without invoking a descriptor's __get__ while checking
            # untrusted attribute names. Data cannot replace methods/properties.
            descriptor = inspect.getattr_static(type(target), key, None)
            if (self._excluded(name, key) or key.startswith("__")
                    or callable(descriptor)
                    or any(hasattr(type(descriptor), method)
                           for method in ("__get__", "__set__", "__delete__"))):
                raise ValueError("snapshot cannot replace runtime attribute: " + key)
            if key in expected and not self._matches_type(expected[key], value):
                raise ValueError("invalid state type for {}.{}".format(name or "owner", key))

    @staticmethod
    def _validate_memories(organs):
        memory = organs.get("memory_manager", {})
        for entry in memory.get("working_memory", []):
            if (type(entry) is not dict
                    or not {"content", "emotion_score", "intensity", "timestamp"}.issubset(entry)
                    or type(entry["content"]) is not str
                    or type(entry["timestamp"]) is not str):
                raise ValueError("invalid working memory entry")
            datetime.fromisoformat(entry["timestamp"])
            for key in ("emotion_score", "intensity"):
                value = entry[key]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError("invalid working memory numeric field")
            if entry["intensity"] < 0:
                raise ValueError("working memory intensity cannot be negative")
            if "emotion" in entry and type(entry["emotion"]) is not str:
                raise ValueError("invalid working memory emotion label")

    def _validate_core_organs(self, organs):
        """Check the maintained core's contracts without guessing older schemas."""
        if "profile" in organs:
            self.owner.profile.validate(organs["profile"]["preferences"])

        if "empathy" in organs:
            empathy = organs["empathy"]
            lexicons = empathy["sentiment_dict"]
            for name in ("positive", "negative"):
                entries = lexicons.get(name)
                if (type(entries) is not set
                        or any(type(word) is not str or not word.strip() for word in entries)):
                    raise ValueError("invalid empathy " + name + " lexicon")
            if any(type(item) is not str or item not in {"positive", "negative", "neutral"}
                   for item in empathy["history"]):
                raise ValueError("invalid empathy sentiment history")
            if empathy["mode"] not in {"neutral", "soothing", "cheerful"}:
                raise ValueError("invalid empathy response mode")
            self._require_finite(empathy["last_score"], "empathy.last_score")

        if "emotion" in organs:
            emotion = organs["emotion"]
            for name in ("current_emotion", "fatigue"):
                self._require_finite(emotion[name], "emotion." + name)
            if type(emotion["last_label"]) is not str:
                raise ValueError("emotion.last_label must be text")

        if "mythos_engine" in organs:
            encode_pairs(organs["mythos_engine"]["co_occurrence"])

    @staticmethod
    def _require_finite(value, name):
        try:
            valid = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(name + " must be a finite number")

    def _prepare(self, snapshot):
        # The encoded form must itself be valid JSON, even on an in-memory
        # rollback path. Reject duplicate tagged keys before any assignments.
        _, data = _serialize(snapshot)
        if (type(data.get("schema_version")) is not int
                or data["schema_version"] != 1 or not self._FIELDS.issubset(data)):
            raise ValueError("invalid or unsupported continuity snapshot schema")
        encoded_organs = data["organs"]
        if type(encoded_organs) is not dict or not set(self.organ_names).issubset(encoded_organs):
            raise ValueError("continuity snapshot is missing registered organs")
        organs = {name: decode_state(value) for name, value in encoded_organs.items()}
        for name, values in organs.items():
            if type(values) is not dict or any(type(key) is not str for key in values):
                raise ValueError("invalid organ state: " + name)
            if name in self._schemas:
                self._validate_attributes(name, values, self._schemas[name],
                                          getattr(self.owner, name))
        symbolic = decode_state(data["symbolic_state"])
        self._validate_attributes(None, symbolic, self._owner_schema, self.owner)
        self._validate_memories(organs)
        self._validate_core_organs(organs)
        if "turn" in symbolic and (type(symbolic["turn"]) is not int or symbolic["turn"] < 0):
            raise ValueError("continuity turn must be a nonnegative integer")
        rng_state = decode_state(data["rng_state"])
        candidate_rng = random.Random()
        try:
            candidate_rng.setstate(rng_state)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid continuity random state") from exc
        evidence = data["associative_memory"]
        learner = None
        if evidence is not None or getattr(self.owner, "learning_enabled", False):
            from associative_memory import AssociativeMemory
            learner = AssociativeMemory(evidence)
        return data, organs, symbolic, candidate_rng.getstate(), learner

    def _legacy_snapshot(self, legacy):
        if (any(key in legacy for key in ("organs", "symbolic_state", "rng_state"))
                or not (set(legacy) & self._LEGACY)):
            raise ValueError("unrecognized legacy continuity state")
        result = self.snapshot()
        organs = {name: decode_state(value) for name, value in result["organs"].items()}
        symbolic = decode_state(result["symbolic_state"])
        mappings = {"working_memory": ("memory_manager", "working_memory"),
                    "dream_log": ("dreamweaver", "dream_log"),
                    "symbol_weights": ("binder", "symbol_weights"),
                    "symbol_logs": ("symbols", "logs"),
                    "symbols": ("symbols", "symbols")}
        for key, (organ, attribute) in mappings.items():
            if key in legacy:
                if organ not in organs:
                    raise ValueError("legacy state requires organ: " + organ)
                organs[organ][attribute] = legacy[key]
        for key in ("mythos", "mythos_keywords"):
            if key in legacy:
                symbolic[key] = legacy[key]
        if "co_occurrence" in legacy:
            pairs = legacy["co_occurrence"]
            if type(pairs) is dict and not pairs:
                pairs = {}
            else:
                pairs = decode_pairs(pairs)
            organs["mythos_engine"]["co_occurrence"] = pairs
        result["organs"] = {name: encode_state(value) for name, value in organs.items()}
        result["symbolic_state"] = encode_state(symbolic)
        for key, value in legacy.items():
            if key not in self._LEGACY:
                result[key] = value
        return result

    def load(self):
        raw = self.store.load(default=self.snapshot())
        try:
            if "schema_version" not in raw:
                raw = self._legacy_snapshot(raw)
            self.restore(raw)
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            # A structurally readable but semantically invalid file must not
            # become an accepted baseline for overwriting it with defaults.
            self.store._loaded = False
            raise SnapshotLoadError("Cannot restore continuity; state left unchanged: "
                                    + str(exc)) from exc
        return self.snapshot()

    def save(self):
        candidate = self.snapshot()
        self._prepare(candidate)  # All semantic validation precedes disk writes.
        return self.store.save(candidate)

    def restore(self, snapshot):
        data, organs, symbolic, rng_state, candidate_learner = self._prepare(snapshot)
        # All validation has completed. Mutate only data dictionaries of the
        # existing objects; references, locks, aliases and handles stay intact.
        for name in self.organ_names:
            target = vars(getattr(self.owner, name))
            for key in tuple(target):
                if not self._excluded(name, key) and key not in organs[name]:
                    del target[key]
            target.update(organs[name])
        target = vars(self.owner)
        for key in tuple(target):
            if not self._excluded(None, key) and key not in symbolic:
                del target[key]
        target.update(symbolic)
        self.owner.rng.setstate(rng_state)
        if getattr(self.owner, "learning_enabled", False):
            existing = getattr(self.owner, "learner", None)
            if existing is None:
                self.owner.learner = candidate_learner
            else:
                vars(existing).clear()
                vars(existing).update(vars(candidate_learner))
            self.owner._dormant_learning = None
        else:
            self.owner._dormant_learning = data["associative_memory"]
        self._dormant = data["associative_memory"]
        self._extra = {key: value for key, value in data.items() if key not in self._FIELDS}
        self._unknown_organs = {name: data["organs"][name] for name in data["organs"]
                                if name not in self.organ_names}
        return data
