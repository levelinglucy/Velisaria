# The larger Velisara monolith

`velisara_monolith_final_fixed_empathy.py` is a self-contained, runnable version
of the larger symbolic system. Its dream, ritual, identity, empathy, creativity,
belief and reflection organs remain separate and connected. The repair borrows the
maintained Sanctified implementation's explicit lifecycle, preservation rules,
source-backed recall and failure handling.

This is an experimental source revision. The exact candidate and hosted checks
belong to its pull request; there is no new stable release or Pythonista device
certification. Current decisions and development status live in
[DEV_NOTES.md](DEV_NOTES.md).

## Run it

Copy `velisara_monolith_final_fixed_empathy.py` to the directory where you want
to run it. This is the only project script required for the larger headless
program, including sourced learning and save/restart. Its learner, state codec,
and snapshot writer are readable Python definitions inside the same file.

The repository retains two related files for existing users and the smaller
Sanctified program:

| File | Role in the repository | Needed beside the larger monolith? |
| --- | --- | --- |
| `velisara_monolith_final_fixed_empathy.py` | Complete larger program and canonical snapshot/runtime definitions. | This is the file to copy and run. |
| `velisara_runtime.py` | Compatibility facade that reexports the main file's runtime definitions for existing imports. | No. |
| `associative_memory.py` | Separately importable learner used by Sanctified; a regression compares its executable definitions with the copy included in the larger file. | No. |

Future learner edits must deliberately update both maintained copies. The parity
check catches executable-definition drift; it does not replace behavior tests.
Consolidating the larger program changes its packaging, while preserving the
existing evidence and snapshot contracts.

The headless core uses the Python standard library. Its supported test matrix is
CPython 3.11 and 3.12. Optional Pythonista devices, drawing libraries and HTTP
features are requested explicitly; importing or constructing the core does not
start them. Rendering/network dependencies are loaded only when used. Missing
providers raise a feature-unavailable error instead of supplying pretend sensor
readings.

Run one bounded turn:

```bash
python velisara_monolith_final_fixed_empathy.py --steps 1 --seed 42 \
  --text "A lantern returns to the spiral."
```

Run three feedback turns and retain them in an explicitly chosen state file:

```bash
python velisara_monolith_final_fixed_empathy.py --steps 3 --seed 42 \
  --state velisara_state.json --learning
```

The first turn receives `--text`; each later turn receives the previous response.
`--steps` accepts 1–256 and then the process exits. Without `--state`, the run
keeps state in memory. `--help` parses before opening state.

Without `--steps` or `--origin-io`, the interactive front door accepts text,
`/memory <JSON>`, `/save`, and `/quit`. The original experimental commands also
remain available programmatically through `handle_command()`. Direct organ calls
can be followed by `save_state()` when their results should be retained.

Try a demonstration that creates only temporary synthetic state:

```bash
python -S examples/large_monolith_demo.py
```

It records one supplied observation, uses it in a later response, creates three
recursive dream fragments, consolidates one evidence event, and verifies both
the observation and the dream history after restart.

## Read the developer notes in the source

The main file starts with a developer guide and contains explanatory comments
beside the mechanisms they describe. Search for a class or function name to
follow a workflow; source locations will move as the program grows.

| Source landmark | What to follow |
| --- | --- |
| `AssociativeMemory` and its helpers | Supplied observations, corrections, hypotheses, scoped recall, and consolidation. |
| `SnapshotStore` and `ContinuityState` | Strict decoding, state encoding, validation, staging, publication, and rollback support. |
| `VoiceOfHerOwn` through `MythosEngine` | Individual organs, their owner references, histories, and derived outputs. |
| `SymbolicCoreMixin` | Dream, glyph, mask, memory, and reflection workflows that share the core's state. |
| `Velisara` | Construction, organ ownership, normal turns, learning commands, snapshots, and shutdown. |
| Later extension functions and optional adapters | Explicitly bound symbolic operations, views, HTTP commands, device sensing, and worker lifecycles. |
| `main` | Interactive input, JSON-lines requests, and bounded command-line runs. |

The comment labels distinguish implementation facts from proposed work:

| Label | Meaning |
| --- | --- |
| `Developer note` | Purpose and mechanism of the nearby definition. |
| `Data flow` | Inputs, state read or written, dependencies, and returned or saved artifacts. |
| `Limit` | A current boundary, missing prerequisite, or known defective path. |
| `Upgrade idea` | A proposal that has **not** been implemented by this documentation pass. |
| `Check` | A useful acceptance condition for a proposed change, not a claim that a test already passed. |

Some comments express these details as connected prose rather than repeating
every label. Read the body and its callers together: a method can mutate live
state directly even when `step()` offers rollback, and a stored `last_*` result
can remain available after a newer invocation fails. Poetic names describe the
symbolic interface; the notes identify when an operation is a text template,
dictionary update, digest, device request, or actual network/file effect.

### Proposed upgrade priorities

The following are **unimplemented proposals**, with concrete outcomes to check.
They preserve the nonlinear symbolic workflows while making their contracts
easier to compose and inspect.

1. **Control worker lifecycles.** Give sanctuary regeneration and environment
   watchers retained start/stop handles, validate intervals, and keep observation
   timestamps separate from user activity. Starting twice should leave one
   worker; shutdown should prevent later sensor or file operations. Fold timer
   callbacks should also reject transitions scheduled for an obsolete state.
2. **Define shared record schemas.** Keep numeric emotion scores and text labels
   distinct, validate dream/context/plugin records, and use stable IDs for links.
   For example, `link_dream_to_context()` currently treats `EmotionEngine` as a
   dictionary. A repaired path should accept an ordinary core instance and
   preserve the captured context when later live state changes.
3. **Track derived-index freshness.** Give soul maps, dream reflections, and
   related views source revision IDs and explicit refresh rules. Rebuilding a
   map should preserve separately authored stitching notes, and a view should
   expose whether newer source records exist. Check both updates and removals;
   a result count alone does not establish freshness. `MemoryIndex.search()`
   already rebuilds its index on every query. Any incremental replacement should
   match that full-rebuild result and demonstrate a measured cost improvement;
   redundant cold-start rebuilding is an optimization target, not evidence of
   stale search results.
4. **Preserve provenance and complete histories.** Link generated fragments and
   glyphs to immutable source revisions, use full digests as identifiers, and
   treat short display glyphs as potentially colliding labels. Replace the
   rolling extension caps described below with a complete ledger and bounded
   views through a separately reviewed change. Adding the 51st archived dream,
   101st journal entry, or 21st evolution note should then leave the earliest
   source recoverable.
5. **Measure a new learning benefit.** Define a bounded task where choosing a
   strategy changes an independently scored outcome. Select before observing
   the answer; compare success and cost against fixed strategies, a frozen
   policy, and equally informed baselines on unseen cases. Recheck earlier tasks
   after later learning. Current associative recall demonstrates retention and
   explicit correction; improvement beyond that needs its own experiment.

Current implementation and release status remain in [DEV_NOTES.md](DEV_NOTES.md).

## Use the existing organs

```python
from velisara_monolith_final_fixed_empathy import Velisara

vel = Velisara(state_file="velisara_state.json", seed=42, learning=True)
try:
    vel.profile.record_preference("metaphor", "lantern")
    print(vel.creativity.generate_poem())
    print(vel.creativity.collaborate("The light returns"))

    vel.create_memory_bead("return", "a blue lantern", "hope")
    vel.bind_bead_to_glyph("anchor", "return")
    print(vel.summon_glyphbound_beads("anchor"))

    fragments = vel.trigger_dream_loop(3)
    reflection = vel.introspect()
    vel.save_state()
finally:
    vel.close()
```

`step(text, user="default", context="default")` runs one input, empathy,
symbolic interpretation, response and reflection transaction. Its returned
dictionary contains `turn`, `text`, `response`, `empathy`, `recall` and `symbolic`.
Empathy is computed before response selection and recorded once per input. A
reflection is retained as generated material. The same source is not repeatedly
promoted into factual evidence.

The symbolic feedback architecture remains accessible through the original
methods. Formerly misplaced methods now belong to `SymbolicCoreMixin` or an
explicit extension list on `Velisara`. A reentrant pattern scan defers its
self-triggered scan to the next explicit call, keeping synchronous recursion
bounded without removing the feedback connection.

## Explicit sourced learning

The included `AssociativeMemory` implementation is enabled by `learning=True` or
`--learning`; its executable definitions remain aligned with Sanctified's
separate learner through a parity regression. Ordinary conversation, poems,
dreams and symbolic beliefs do not automatically enter its factual evidence
journal.

```python
vel.learning_command({
    "op": "remember", "user": "demo", "context": "routes",
    "cue": "blue lamp", "answer": "choose left",
    "source": "synthetic observation", "event_id": "observation-1",
})

result = vel.step("blue lamp", user="demo", context="routes")
print(result["response"])

vel.learning_command({
    "op": "correct", "user": "demo", "context": "routes",
    "cue": "blue lamp", "answer": "choose right",
    "source": "rechecked synthetic observation", "event_id": "correction-1",
    "supersedes": ["observation-1"],
})

vel.learning_command({"op": "sleep", "max_events": 16})
```

The supported operations are `remember`, `correct`, `hypothesize`, `recall`,
`sleep` and `learning-status`. The original observation remains in the journal
after correction. Hypotheses never support factual recall. Conflicting active
answers remain a visible conflict; repetition does not decide which is true.
Exact event-ID retries are idempotent. Consolidation processes at most the
requested 1–256 new events and never prunes the source journal.

Source labels are supplied by the caller, not independently verified. User and
context strings separate lookup namespaces; they are not an authentication
system. Recall is normalized associative lookup, not semantic generalization or
neural training. See [ASSOCIATIVE_MEMORY.md](ASSOCIATIVE_MEMORY.md) for the shared
learner's evidence and consolidation semantics.

### JSON-lines adapter

```bash
python velisara_monolith_final_fixed_empathy.py --origin-io --learning \
  --state velisara_state.json
```

Each input line is an object with an `op`. `step` and `think` take `text` and
optional `user`/`context`; learning operations use the schema above. `save` saves
the current state; `quit` ends the adapter. Each request gets one JSON response
with `ok` and either `result` or `error`/`error_code`.

Duplicate keys, nonstandard numeric constants, lossy finite decimal literals and
invalid namespaces are rejected before a live turn. A rejected request does not
prevent processing the next line. Storage refusal is reported separately from
an invalid request.

## What survives restart

The versioned snapshot includes registered organ data, supported dynamic symbolic
attributes, the full event archive, preferences, dreams, feedback, belief and
garden retirement archives, conversation, identity records, random-generator
state, and active or dormant associative evidence.

A snapshot preserves the data still present when it is taken. Three retained
experimental extensions currently trim their own lists: `archive_dream_fragment()`
keeps 50 entries, `journal_dream_on_idle()` keeps 100, and
`evolve_emotional_identity()` keeps 20 evolution notes per mood. These limits
remain in the code; consolidation and commentary have not removed them. They
are separate from the complete core event archive and the associative evidence
journal. Snapshotting cannot recover entries those extension methods already
dropped unless an older saved copy contains them.

Tuple keys, sets and datetimes use explicit tagged data containers. Ordinary
dictionary keys cannot be confused with codec tags. Loading never unpickles or
executes saved code. Runtime owner references, aliases and locks remain attached
to their existing objects; arbitrary objects and cyclic plain-data containers
are refused visibly. Shared plain-data containers are restored by value, so
their Python `is` identity is not preserved across restart.

Legacy state from the old seven-field saver can be mapped into the new snapshot
in memory. A subsequent explicit save writes the versioned format. Unknown
top-level fields and unknown organ records remain preserved. Invalid known
fields are not replaced with empty defaults. Other historical monolith variants
and the pre-repair file remain accessible in repository history; the starting
revision for this repair is `57ac1c0290e152e45129fdb0c7c89ff6d273828d`.

## Preservation and failure behavior

The complete candidate is encoded and validated before a staging file is
created. Disk saving checks the loaded byte fingerprint, refuses a pre-existing
`.tmp`, creates staging exclusively, writes and flushes it, calls file `fsync`,
and then replaces the primary. A failed write preserves the previous primary
and any staged evidence. Startup refuses unresolved staging evidence. Do not
delete either copy just to bypass that refusal.

`step()` and mutating learning commands restore their prior live snapshot and
RNG state if saving fails. Uncommitted observations or turns cannot silently
reappear in a later successful operation. Direct experimental organ calls remain
explicit live mutations; their later `save_state()` failure does not itself undo
all preceding manual work.

Emotional aging changes weighting without deleting history. Tuning tracks a
cursor instead of clearing original feedback. Rebuilding mythos co-occurrence
counts from unchanged dreams is idempotent. Retired beliefs and explicitly
pruned garden plants retain complete archived records. Dream “encryption” is a
legacy API name for symbolic locking: it retains original symbols and provides
no confidentiality guarantee. Lost symbols from older damaged masks cannot be
reconstructed from a digest.

## Validation and remaining limits

The regression suite covers quiet startup without optional packages, organ
ownership, seeded creativity, empathy ordering, multiple original symbolic
chains, bounded pattern feedback, state migration, source/conflict/correction
learning, complete restart, malformed state, sequential stale writers, and
injected publication failures. The hosted matrix also compiles both monoliths
and runs both demonstrations.

Restoring a method's placement does not prove every possible experimental path
through the large program. Physical sensors, sound/UI rendering, external
reminders, HTTP serving and iPhone/Pythonista execution remain unverified.
Some optional paths also have concrete implementation gaps: `HelpView` expects
core methods that its view object does not supply; `VeloneSystem` refers to an
undefined `MockVel`; and dream speech calls an undefined `speak_local` hook.
Several late label lookups still receive numeric emotion values, and the
dream-context link has the object/dictionary mismatch noted above. The inline
notes identify these paths and proposed repairs; consolidation does not claim
to complete them.
Wall-clock time and real sensor input are not deterministic; a seed controls
symbolic random choices and its continuation, not a byte-identical replay of
every timestamp or external observation.

Persistence performs full-history capture, validation and serialization. A
bounded consolidation count does not bound total memory, I/O or elapsed time.
There is no cross-process lock: sequential stale writers are detected, while
simultaneous writers and filesystem path swaps can still race. The directory is
not fsynced; this is not a hardware power-loss durability claim. Explicit legacy
background workers are outside the single-threaded transactional guarantee.
