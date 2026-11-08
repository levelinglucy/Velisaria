# Sanctified Monolith · developer notes

## Development summary

**Purpose:** protect the local Sanctified Monolith's recoverable session history without modifying archives or its established JSON schema. **Integration:** M1–M7 merged as unreleased maintenance; M8 retention repair proposed in [PR #10](https://github.com/levelinglucy/Velisaria/pull/10). **Validation:** latest merged M7 passed [30/30 tests each on Python 3.11 and 3.12](https://github.com/levelinglucy/Velisaria/actions/runs/42489828810) at `b00c98e`; M8 validation belongs to PR #10 and is not assumed complete. **Release:** unreleased; no target-device, multiwriter or power-loss certification.

**Current goal:** stop automatic loss of earlier sessions when a new entry takes the history beyond 4,000 records. Preserve every entry by default, using the established strict JSON staging, until an explicit owner-controlled archival/capacity design exists. **Next:** validate retention at the 4,001-entry boundary and prior integrity checks; check merge suitability; assess sustainable storage handling before any future retention policy. [Changelog](./CHANGELOG.md) · [PR #10 and exact evidence](https://github.com/levelinglucy/Velisaria/pull/10) · [Memory tests](./tests/test_memory_integrity.py).

## What was verified in original source (main e311e1b)

The historical `Memory.load()` caught every exception on an existing `sanctified_state.json` and replaced session history in memory with `{"sessions": []}`. The next `Monolith.think()` called `Memory.save()`, atomically replacing the original path with a new empty-derived history. Thus a damaged but recoverable file could lose its prior contents on ordinary continued use.

The monolith's CLI writes `sanctified_state.json` in the **current working directory**. It also accepts `--origin-io` (a human-readable greeting followed by line-delimited JSON replies). Import alone defines classes without running the CLI; writing happens on a `think()` call. We intentionally do not execute the large archived monoliths.

## Decision M-001 · preserve corrupt state rather than silently forget it

- **Constraints:** local-first, stdlib-only, keep existing state shape and original symbolic content; preserve a genuinely absent file's first-run behaviour.
- **Alternatives:** retain silent fallback (convenient but destructive); automatically roll back to `.tmp` (could be partial or stale); invent an automatic repair by truncating history (lossy and unaudited); or fail closed.
- **Choice:** only `FileNotFoundError` means no state yet. Parse/read/encoding errors raise a clear exception. Parsed state must be an object with a list-valued `sessions` key; otherwise loading stops before any write. Unknown top-level keys and historical session entries remain untouched.
- **Benefit/cost:** no silent conversion of corrupted memory into a fresh history; users must back up and repair/restore the file before normal operation continues. This can reduce availability in situations where the old program silently started a new history; intentional fail-closed policy.
- **Evidence:** isolated synthetic tests for damaged and valid files; Python matrix CI required before promotion. Tests do not prove power-loss durability or backwards compatibility with every archival format.
- **Revisit when:** a documented legacy state variant needs support, or an owner-approved, verifiably safe recovery path can be demonstrated using copied data.

## Decision M-002 · never overwrite interrupted temporary memory

- **Finding and stakes:** the old `Memory.save()` opened a predictable `.tmp` in truncate mode. A crash/exception immediately before `os.replace` could leave a full or partial new session record there; on restart, `Memory.load()` ignored it whether or not the primary existed, and a subsequent save could destroy the only remaining copy of that generation.
- **Alternatives:** silently ignore the temporary file (loses evidence); auto-promote `.tmp` if JSON parses (could promote stale/mismatched state); introduce complex locking/journaling now (greater compatibility/maintenance surface); or conservatively refuse to start/write over existing `.tmp`.
- **Decision:** treat any adjacent `.tmp` as unresolved local recovery evidence and stop startup without changing either file. Save exclusively creates `.tmp` (mode `"x"`), so a concurrently created or orphaned file cannot be silently truncated by that save. Also fail closed on a dangling primary-state symlink. Preserve the original session JSON shape and valid clean-start workflow.
- **Evidence:** isolated exception injection and actual child-process `os._exit(37)` before replacement, for both first save and a previous committed state. Previous unsafe behaviour was demonstrated with a red test-only CI before code changes, run 42318018754 (Python 3.11/3.12). After the source/docs candidate `78e93607`, 12/12 isolated tests passed on each Python 3.11 and 3.12 in [CI 42318191650](https://github.com/levelinglucy/Velisaria/actions/runs/42318191650); this is not a power-cut/device test.
- **Trade-offs:** ordinary use can now refuse to start if even a stale `.tmp` exists. This needs manual, owner-local investigation on **copies**; it is deliberate availability cost for data preservation.
- **Not guaranteed:** safe concurrent independent writers, durable power-loss atomicity, file/directory fsync or Pythonista filesystem semantics. `os.replace` ensures a rename boundary on tested platforms, not a durability guarantee. The process-exit tests stop *before* replace, not during a real OS crash.
- **Revisit:** if trusted device tests or realistic old-format snapshots support a simpler owner recovery and an explicitly safe reconciliation procedure, with a rollback plan and no automatic deletion of the original evidence.

## Decision M-003 · inspect competing memory copies without choosing one

- **Problem:** after an interrupted save, the program correctly refuses to overwrite `.tmp`, but an owner needs useful, private evidence to decide what to preserve.
- **Alternatives:** auto-promote the newer-looking file (unsafe: no durable ordering proof); add a repair command to normal startup (risks overwriting the only complete copy); or provide a separate metadata-only inspector.
- **Choice:** `inspect_memory_state.py` opens only ordinary files without following final-component symlinks, reads at most 32 MiB per file, parses strict UTF-8 JSON with unique keys, and reports presence, structural validity, session counts and whether one list is a prefix of the other. If non-session fields differ, the relationship is `divergent`. It never writes, creates copies, selects a winner, deletes records or prints session contents.
- **Safety limits:** run against owner-made copies in an isolated directory, preferably with the writer stopped. A prefix is a *content relationship*, not proof that either file is newer or valid to promote. `equivalent_data` is parsed equality, not evidence of identical physical writes or durability. Counts are disclosed in local output. A file beyond 32 MiB, a symlink, missing `O_NOFOLLOW` support, malformed JSON or detected concurrent modification prevents a claim of valid inspection. Independent reads cannot form an atomic pair of snapshots.
- **Compatibility:** standalone, stdlib-only; existing memory loading/saving and the persistent JSON schema are unchanged. No automatic recovery or stable-release claim is introduced.
- **Revisit:** only after relevant owner-controlled evidence establishes a safe procedure for specific recovery scenarios; otherwise preserve both generations.

## Decision M-004 · preserve evidence distinctions in JSON scalars

**Observed predecessor:** default JSON parsing converted decimal and exponent literals to binary floats. Different copied histories such as `0.10000000000000001` versus `0.1`, or `1e400` versus `1e401`, compared equal after rounding or overflow to infinity. Python also equates `true` with integer `1`. The inspector could therefore classify different session records as `equivalent_data` or a clean prefix. This was reproduced with synthetic inputs, not a claim that actual owner records were damaged.

**Options:** compare raw file bytes (safe but makes whitespace and object-key order material); use `decimal.Decimal` with explicit bool typing (numeric value comparisons still erase representation differences); or use **tagged number lexemes** during this read-only inspection (selected). JSON cannot directly produce Python tuples, so a private tuple tag distinguishes numeric literals from strings, booleans, arrays and objects; identical raw number tokens in reordered object keys still compare equal.

**Benefit and cost:** avoids false recovery equivalence caused by numeric rounding, overflow or bool/int coercion. Numerically equivalent but differently written tokens, such as `1` and `1.0`, now classify as divergent. This conservatism is deliberate: the tool reports recorded-history agreement, not numeric value equivalence. Saved state format and live writer are untouched; the inspector never exposes the tokens in its report. No automatic recovery is introduced.

**Acceptance:** synthetic regressions for precision, underflow, exponent overflow, bool-vs-number, string-vs-number and false prefixes report `divergent`; identical large-number prefixes still pass; all inspected files remain byte-identical. Reconsider normalizing numeric equivalence only if an evidence-backed recovery need makes it appropriate, with an explicit report contract and regression tests.

## Decision M-005 · refuse ambiguous JSON before live-memory rewrite

**Observed predecessor:** the live `Memory.load()` used Python's default `json.load`, which quietly took the last of duplicate object keys. A syntactically valid file such as `{"sessions":[{"marker":"valuable"}],"sessions":[]}` therefore loaded as empty history; the next ordinary thought/save could overwrite the original file and discard the first list. Nested duplicates similarly lost values. `NaN`/`Infinity` were accepted despite not belonging to standard JSON; exponent overflow produced nonfinite floats. Excess nesting raised an uncaught `RecursionError`. These are reproduced on **synthetic** files by the red test-first [PR #7 CI](https://github.com/levelinglucy/Velisaria/pull/7); there is no evidence an owner's saved state was affected.

**Decision:** decode the existing live format using unique-key validation at every object depth, reject nonstandard constants and nonfinite floating-point conversions, and proactively reject more than 256 nested JSON containers (ignoring quoted text), independently of decoder recursion behaviour. Preserve the source bytes and leave the standard integer/float runtime representation and file schema unchanged. The read-only inspector retains its separate stricter exact-token comparison contract.

**Alternatives/trade-offs:** keeping Python's permissive defaults risks silent loss; picking the first duplicate guesses author intent; repairing in place would destroy the disputed record. Refusal reduces availability for formerly accepted ambiguous/overflowing or deeply nested records, but an owner can preserve both bytes and context on copies. Other finite decimal tokens can still be rounded by the ordinary live float parser; this change does **not** claim byte-perfect numerical replay, full file-race protection, durable power-loss recovery or multiwriter safety.

**Acceptance and revisit:** duplicated top-level/nested keys, nonstandard constants, exponent overflow and deep nesting must refuse startup without writing; genuine first start and valid forward-compatible histories must still load and save. Revisit broader numeric-fidelity support only with an explicit schema/migration design and trusted legacy compatibility evidence. Exact CI results and integration status belong to [PR #7](https://github.com/levelinglucy/Velisaria/pull/7).

## Decision M-006 · reject lossy finite decimal rewrites

**Confirmed predecessor:** after M5, the live loader still decoded finite decimals using binary `float`. A saved value such as `0.10000000000000001` loaded as `0.1`, while `1e-400` loaded as `0.0`. A later normal save would rewrite the only primary history with the different numeric value. Six synthetic inputs reproduced the unguarded load on Python 3.11/3.12 ([red CI 42484832396](https://github.com/levelinglucy/Velisaria/actions/runs/42484832396)); no real owner-data damage was observed.

**Alternatives:** preserve every original number lexeme with a new serialized numeric type (larger state/migration surface); reject all noncanonical spellings (needlessly breaks compatible histories); allow rounding (silent evidence loss); or compare the parsed decimal value with the decimal value that the existing float writer would emit. **Chosen candidate:** use stdlib `decimal.Decimal` only during `parse_float` validation and keep normal floats in memory. Refuse whenever the numeric value would change or cannot be checked reliably. Lexical variations with the same value, such as `1e0` versus `1.0`, remain valid.

**Trade-off:** such files now refuse startup until the owner preserves and investigates copies; no automatic repair. This preserves recorded *numeric values*, not exact source spellings, and does not magically make in-memory float arithmetic exact. The read-only copy inspector keeps its stricter lexeme-comparison semantics. Exotic decimal exponents beyond the validator's safe range may also be refused. The live serializer could still need separate validation for newly generated values or external edits; this change is not a transaction/multiwriter/durability guarantee.

**Acceptance:** precision-loss, rounding and underflow examples refuse startup without creating `.tmp` or altering the original bytes; representable finite values and alternate equivalent spellings still load and save, with the old schema. Preserve earlier integrity tests on Python 3.11 and 3.12. Revisit only for a verified legacy compatibility problem or a safe, documented format migration; do not auto-convert contested evidence.

## Decision M-007 · validate generated memory before staging

**Confirmed predecessor:** `Memory.save()` streamed ordinary `json.dump` directly into a new `.tmp`. Its default `allow_nan=True` could publish nonstandard `NaN` or `Infinity` that the strict loader would subsequently refuse. Unserializable Python values and circular containers could leave a partially written `.tmp` after an ordinary serialization exception, forcing manual investigation even though the committed primary was untouched. The new tests use synthetic in-memory values only; no owner file damage is asserted.

**Alternatives:** keep streaming and leave partial evidence on all encoding failures (availability cost); sanitize or stringify unsupported values (silent semantic changes); delete failed `.tmp` (risks discarding recovery data after actual I/O failures); or **fully serialize strictly in memory before opening `.tmp`** (selected). The last option rejects invalid in-memory values without touching either disk generation and still leaves a real interrupted write or failed replace for conservative copy-based inspection.

**Trade-offs and acceptance:** an additional serialized string consumes memory proportional to the state size, and invalid newly generated content now refuses the save rather than being written. Valid output retains the prior JSON format. Synthetic NaN/Infinity, unsupported objects and cycles must fail without creating `.tmp` or overwriting a committed primary; existing valid saves and interrupted-write safeguards must remain green. It does not make filesystem publication crash-durable, protect against simultaneous writers or authorize auto-recovery. Revisit if measured memory use makes full preflight unsuitable on a supported device, with a bounded streaming design that preserves the same refusal guarantee. Exact candidate/CI evidence and integration status belong to [PR #9](https://github.com/levelinglucy/Velisaria/pull/9).

## Decision M-008 · never prune saved sessions implicitly

**Confirmed predecessor:** `Memory.log()` automatically changed a 4,001-entry history to its newest 2,500 entries before the next `Memory.save()`. This discards **1,501 older records**, including the earliest session, without warning or a separate archive. A disposable 4,000-record seed plus one new entry reproduced the loss on both Python 3.11 and 3.12 ([failing regression CI](https://github.com/levelinglucy/Velisaria/actions/runs/42494651459)); no real owner memory damage is claimed.

**Alternatives:** retain the silent cap (unacceptable for a preservation-oriented tool); block new messages at 4,000 (prevents recording new interactions); implement an automatic archive rollover (requires multi-file, crash-safe coordination); or **retain the complete history for now** (selected). Remove implicit trimming only; preserve JSON schema, previous committed history, exclusive `.tmp` staging and historical sources. No new knobs, migrations or automatic file deletion.

**Trade-offs:** JSON size, load/parse time and the existing full serialization buffer grow with session count. Long-running use needs owner-managed copies and eventually an explicit, separately validated archival strategy; no device storage budget or unlimited growth guarantee is claimed. A future cap must **fail clearly or archive without loss** rather than quietly dropping history. A failed save still follows the existing conservative recovery policy; this milestone does not establish fsync, multiwriter safety or power-cut durability.

**Acceptance:** a fresh synthetic 4,000-record history plus one logged session saves and reloads as **4,001 records**, with all original entries unchanged. Previous history integrity, CLI and interrupted-save tests still pass on CPython 3.11/3.12. Exact validation and integration belong to [PR #10](https://github.com/levelinglucy/Velisaria/pull/10).

## Running safely

With a checkout and Python 3.11+:

```sh
python -m unittest discover -s tests -v
```

Synthetic CLI dry run from a **new temporary working directory** (the program writes relative to cwd):

```sh
python /absolute/path/to/sanctified_monolith.py --origin-io
```

Send a JSON line such as `{"user":"demo","text":"hello"}` then `/quit`. Avoid using your actual state folder for experiments.

**Owner recovery if startup fails:** Stop the writer. Preserve the exact bytes of both the primary and adjacent `.tmp` where they exist. Make separate working copies in an isolated directory. Run the inspector **on the copied primary path**, not in the live working directory:

```sh
python inspect_memory_state.py --state /path/to/isolated-copy/sanctified_state.json
```

The result contains metadata only. `primary_sessions_prefix_of_temporary` does **not** authorize promoting `.tmp`: the same prefix could be stale or from another run. Retain both originals and seek evidence-based recovery rather than using an older saver, manually renaming files, or trying repeated startup.

## Milestone / release gates

- **M1 (integrated candidate):** non-destructive refusal on malformed state + isolated synthetic CLI tests. Seven tests passed on Python 3.11 and 3.12 at the final PR head and merged-main candidate (CI [42312031091](https://github.com/levelinglucy/Velisaria/actions/runs/42312031091), [42312078957](https://github.com/levelinglucy/Velisaria/actions/runs/42312078957)).
- **M2 (merged maintenance candidate):** interrupted-write/exclusive-temp preservation, synthetic pre-replace process termination, and copy-only owner guidance. 12/12 tests passed per version in [final PR CI 42318289406](https://github.com/levelinglucy/Velisaria/actions/runs/42318289406) at `f112440b`, and [merged-main CI 42318351081](https://github.com/levelinglucy/Velisaria/actions/runs/42318351081) at `d3082d1a`. Trusted Pythonista and actual power-cut checks remain pending.
- **Stable:** only for platforms and behaviours backed by sufficient evidence and an explicit release decision. Target iPhone/Pythonista support can remain unverified and experimental rather than blocking unrelated verified CPython development. No tag, release or migration is claimed now.

## Continuation

Historical M1/M2 recovery invariants and M3 read-only inspection remain in force. Current selected work and next actions are in the [development summary](#development-summary). Preserve the original Covenant and archives. Do not promise deterministic replay: `MotionForge._seed` uses Python's process-randomized `hash(text)`.
