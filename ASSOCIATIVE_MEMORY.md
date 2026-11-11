# Explicit associative memory

Velisaria can record a sourced association, use it in a later response, and
consolidate it into a persistent lookup table. This is an opt-in symbolic
learning experiment built around the maintained `sanctified_monolith.py`.

## Try the isolated demonstration

From the repository directory:

```sh
python examples/associative_memory_demo.py
```

The demonstration writes only temporary synthetic data. It learns 12 associations
in context A, then 12 in context B, consolidates in batches of at most five events,
and checks both contexts after saving and loading the state. It also exercises
conflict, correction, provenance, hypotheses, duplicate retries and empty sleep
passes. A nonzero exit indicates an unmet acceptance check.

The test questions vary capitalization and spacing. They do not demonstrate
semantic generalization. Full-archive recall has the same evidence and is expected
to achieve the same accuracy as consolidated recall. The deliberately limited
last-four-event working view is reported separately as an ablation; it is not the
full-archive baseline. No speed or memory-efficiency improvement is measured.

## Use the learning console

Keep `associative_memory.py` beside `sanctified_monolith.py`. Both use only the
Python standard library. Start an explicit experiment file:

```sh
python sanctified_monolith.py --learning --state learning_experiment.json
```

Then enter:

```text
/memory {"op":"remember","context":"default","cue":"blue lamp","answer":"choose left","source":"synthetic example","event_id":"lamp-1"}
/sleep
blue lamp
```

The ordinary response starts with `Recall: choose left [evidence: lamp-1]` and
retains the existing refinement diagnostics. Interactive memory commands default
to user `dylan`, the same user as the ordinary console. End with `/quit` and run
the same command again: `blue lamp` still retrieves the recorded association.

`/sleep` processes at most 32 new raw events. Use `/memory` with an explicit
`max_events` to choose a budget from 1 through 256. There is no unattended
background process: consolidation runs only when requested by the caller.

## JSON-lines interface

```sh
python sanctified_monolith.py --learning --origin-io --state learning_experiment.json
```

The adapter retains its existing human-readable ready/bye lines. Other responses
are JSON objects. Example requests, one per line:

```json
{"op":"remember","user":"demo","context":"routes","cue":"blue lamp","answer":"choose left","source":"observed example","event_id":"route-1"}
{"op":"sleep","max_events":1}
{"op":"think","user":"demo","context":"routes","text":" BLUE  LAMP "}
{"op":"recall","user":"demo","context":"routes","cue":"blue lamp"}
{"op":"learning-status"}
```

`think` returns an `output`; learning operations return a `result`. All successful
requests include a compact `snapshot`. Failed requests return `ok: false` and an
error. A normal thought is logged as a session; learning events are stored in a
separate `associative_memory` section of the same guarded state file.

| Operation | Fields and effect |
|---|---|
| `remember` | `cue`, `answer`, `source`; appends an explicit observation. |
| `correct` | The same fields plus `supersedes`, a nonempty list of active evidence IDs in the same scope. |
| `hypothesize` | The same fields as `remember`; preserves a proposal without using it as factual evidence. |
| `sleep` | Optional `max_events` (default 32, maximum 256); advances the persistent consolidation cursor. |
| `recall` | `cue`; returns the answer and supporting evidence, `unknown`, or `conflict`. |
| `learning-status` | Returns event, cursor, pending and association counts without source text. |

Learning records and recall are scoped by exact `user` and `context` strings.
JSON requests default to `user: "anon"` and `context: "default"`; provide both
explicitly when sharing a file across namespaces. These labels are not an
authentication or access-control system.

Cues match after Unicode NFKC normalization, case folding and whitespace
normalization. Punctuation, word order and synonyms are not automatically
equivalent. User/context/cue/source fields are nonempty strings up to 512
characters; answers up to 2048; event IDs up to 128. Ordinary long or empty
`think` inputs continue through the existing refiner without a cue lookup.

## Correct evidence without erasing its history

If another observation disagrees, recall exposes a conflict even when the first
answer has been repeated more often. To replace the earlier evidence explicitly:

```json
{"op":"correct","user":"demo","context":"routes","cue":"blue lamp","answer":"choose right","source":"verified correction","event_id":"route-2","supersedes":["route-1"]}
```

The new answer is available immediately through combined recall, including before
the next sleep pass. The original record remains in the event journal, with the
correction linking to it. If several active records represent the old claim,
name every record you intend to supersede. Unnamed conflicting evidence remains
visible. A correction cannot target another user/context/cue, an already
superseded record, or a hypothesis.

Supply an `event_id` to make retries idempotent: resending the identical request
does not add evidence or write another generation. Reusing the ID with a
different payload is an error. If omitted, an ID is generated and returned.
Source labels record the caller's stated provenance; the program does not verify
the source's truth or independence.

## What consolidation changes

The raw journal records experience. The derived table retains active evidence for
each scoped cue. A persistent cursor tracks how much of the journal has been
folded into that table. Each sleep pass consumes a bounded number of raw records,
including hypotheses that do not become evidence. Repeating sleep without new
records makes no changes and never adds support.

Recall modes are explicit:

- `combined` (default): the consolidated table plus all pending events for the
  queried scope. Pending corrections cannot disappear behind a working-window
  cutoff.
- `consolidated`: only the processed prefix. The returned `pending` count warns
  that later records may exist; this mode can omit a pending correction.
- `archive`: folds every raw event, for the full-information comparison.
- `working`: folds only the last `working_limit` global raw events, default 32.
  This intentionally restricted diagnostic view can omit older evidence.

Only `combined` is used by ordinary `think`. Recalled answers and conflict notices
change the visible response. This feature does not infer neural confidence from
the monolith's stability/empathy diagnostics or retrain an external model.

## Persistence and practical limits

The event journal, derived table and cursor are saved in one generation through
the existing guarded `Memory.save()`. The live learner changes only after save
succeeds. A stale writer or interrupted replacement does not publish the candidate
learner in memory. An interrupted `.tmp` is preserved for the existing recovery
procedure; it is never automatically deleted or promoted.

Existing sessions and unrelated state fields are preserved. Original learning
events are never silently pruned. On activation, malformed learning state,
inconsistent derived evidence, unsupported versions and mismatched processed
prefixes are refused. The digest checks internal consistency, not authenticity.

The event budget bounds new learning updates. Loading, integrity replay, copying,
hashing and saving still scale with total history, and storage grows with retained
events. Concurrent-writer race and power-loss limits of the existing saver still
apply. Pythonista/iPhone operation is not yet verified.

The current milestone demonstrates explicit associative retention and correction.
Autonomous discovery, semantic concept learning, generated-practice evaluation and
adaptive mycelium routing remain separate development work. See
[DEV_NOTES.md](./DEV_NOTES.md) for the next step and validation policy.

## Research connection

The design borrows the separation between fast experience and slower consolidation
from [Google Research's Nested Learning overview](https://research.google/blog/introducing-nested-learning-a-new-ml-paradigm-for-continual-learning/)
and [the sleep framework](https://research.google/blog/the-sleep-framework-a-new-way-for-llms-to-retain-knowledge-in-continual-learning/).
This symbolic prototype is not an implementation or benchmark replication of
HOPE or the neural sleep framework.
