# Sanctified Monolith · developer notes

## Development summary

**Purpose:** preserve local session history and keep computed/refined signals faithful to their stated inputs. **Current goal (M16):** make empathy profile decoding unambiguous before a hot reload can change live settings. A profile with duplicate JSON object keys or nonstandard JSON constants must be refused, preserving the last validated profile (or defaults). Keep normal partial profiles, live-object identity, session schema, archived monoliths and owner files unchanged.

**Integration:** M15 deterministic MotionForge seed was integrated in [PR #17](https://github.com/levelinglucy/Velisaria/pull/17). M16 is proposed in [PR #18](https://github.com/levelinglucy/Velisaria/pull/18), not yet merged. **Validation:** initial test-only head `b352084b` failed on seven expected subcases, while all previous 51 tests and one new valid-profile test passed on both Python 3.11 and 3.12 ([red CI](https://github.com/levelinglucy/Velisaria/actions/runs/42719546190)). Subsequent candidate validation belongs to PR #18 and must not be anticipated. **Release:** untagged/unreleased; iPhone/Pythonista, real owner-state recovery, concurrent writes and power-loss durability remain unverified.

**Acceptance:** malformed duplicate or nonstandard JSON is refused at all object depths, cached last-good settings survive invalid replacement, previously valid profiles still load, and the full suite and source compilation pass on Python 3.11/3.12. **Next:** validate the implementation candidate at its exact revision, merge only when checks and repository protections permit, then resume portfolio triage. No user-run device test is required for this source-only milestone.

## Decision M-016 · reject ambiguous JSON before profile activation

**Observed predecessor:** `ProfileLoader._read()` used default `json.load` semantics. Duplicate keys silently selected the final occurrence, allowing a replacement file with two `curiosity_bias` entries to change the live setting from its last good value. Nested duplicate keys and nonstandard `NaN`/`Infinity` values in unrecognized sections also passed the JSON reader. These are synthetic input defects, not evidence that an owner profile was corrupted. Test-only [CI 42719546190](https://github.com/levelinglucy/Velisaria/actions/runs/42719546190) reproduced seven subcase failures across three new tests per Python version, with previous tests still passing.

**Choice:** use `object_pairs_hook` to reject repeat JSON keys at every depth and `parse_constant` to refuse nonstandard numeric literals before existing profile field validation. Invalid files remain uncached; `load()` keeps the last successfully parsed profile and signature. No storage migration, profile schema redesign, default-value change or automatic repair of disputed files is involved.

**Alternatives and trade-offs:** last-key-wins silently discards evidence; first-key-wins merely reverses the arbitrary choice; accepting nonstandard constants only in unused sections makes profile validity depend on which fields happen to be recognized today. Strict refusal can leave a previously accepted malformed configuration inactive until an owner reviews a copy and makes its intended settings unambiguous. The live profile file is never rewritten by this change. Unknown *standard* JSON fields remain permitted for forward compatibility; last-good fallback may still be quiet, and metadata-invisible edits and concurrent replacement races remain outside this milestone.

**Revisit:** if users require precise error reporting or stronger change detection with a tested platform contract; do not infer profile authentication, iPhone portability or multiwriter safety. Revision-specific validation and decision outcomes belong to [PR #18](https://github.com/levelinglucy/Velisaria/pull/18).

## Decision M-015 · stable input-derived motion seed

**Observed predecessor:** `MotionForge._seed()` used `hash(text) & ((1<<32)-1)` to seed a local `random.Random`. Python salts string hashes per process by default. Consequently, the same prompt can produce distinct motion vectors on separate launches, making replays incomparable even before any other state changes. This concerns generated motion features rather than stored history corruption. A synthetic independent-process regression compares three explicit `PYTHONHASHSEED` values; no owner state is needed.

**Choice:** hash UTF-8 text using SHA-256, take the first four digest bytes as an unsigned big-endian integer, and feed that into the existing local 160-bit `random.Random` stream. Keep the vector transformation, API, downstream state schema and historical source untouched. **Compatibility:** vectors for a given prompt intentionally change relative to old runs; the pre-fix randomized mapping cannot be reconstructed without knowing its process hash seed. This is deterministic within the tested interpreter/algorithm versions, not a promise of identical `randint` output across every future Python implementation.

**Alternatives:** setting `PYTHONHASHSEED` globally would require a launch-time environment contract and could affect unrelated code; persisting random seeds would change stored formats; a local digest-derived seed is minimal and self-contained. **Revisit** only if cross-interpreter bitwise replay or independent-vector serialization becomes a requirement. Unrelated timestamps, UUIDs and the dynamic mesh still make full-session replay nondeterministic. See [PR #17](https://github.com/levelinglucy/Velisaria/pull/17) for revision-specific checks.

## Decision M-014 · removed profile overrides revert to defaults

**Observed predecessor:** `ProfileLoader.apply_to_empathy()` used currently active values as fallbacks for omitted fields, and `Monolith.think()` reapplied partial settings on every call. When a valid hot reload removed a configured prior, gain or term list, the previous custom value persisted indefinitely. A valid empty object was accepted but did not restore defaults. This could produce behaviour inconsistent with the file the owner had deliberately replaced. Two synthetic tests exposed these failures against the previous implementation on both CPython 3.11 and 3.12; [PR #16](https://github.com/levelinglucy/Velisaria/pull/16) holds exact revisions and logs.

**Decision:** retain the existing all-or-nothing validation and metadata change detection. Track the last successfully applied profile signature; on a *new validated* signature, restore dataclass-defined EmpathyCore defaults in place, then apply only keys in that profile. An invalid, unreadable or missing replacement leaves the previous successful signature unchanged and reapplies its cached profile; unchanged valid profile continues the established per-thought overlay. This retains object identity and session format and does not touch saved files.

**Alternatives:** leave removed fields active (misleading), replace `Monolith.empathy` on each reload (breaks external references), reset on every thought (discards independent live modifications), or always hash/read files (additional I/O, separate detection scope). In-place reset only after accepted reload is minimal and makes profile removal deliberate. Removal will intentionally change calculated values to defaults. No guarantee for metadata-invisible changes, simultaneous profile writes, power-loss durability or target iPhone filesystem semantics.

**Revisit when:** a supported runtime override outside the profile should persist across profile replacement, or a concrete platform requires stronger reload/detection semantics. Test on synthetic disposable files only.

## Decision M-013 · feed live empathy to refinement, then finalize weight

**Observed predecessor:** `Monolith.think()` ran `RTE.step()` before `EmpathyCore.step()`; `RTE.step()` therefore received an empty `ctx["affect"]` and used hard-coded `warmth=0.6, tension=0.6, curiosity=0.5` in its generated refinement text. Actual input, resonance phrases, configured profile priors and attention tier affected the later weight calculation but not the displayed refiner values. Direct M12 tests did not exercise this orchestration path.

**Decision:** perform one provisional empathy pass before RTE, then RTE with actual affect, then a second empathy pass to recompute the final weight using RTE's stability-derived `base_score`. The affect component depends on the text/profile/tier, not on the base score, so the refiner and final weight use the same effective affect. This is a bounded, pure extra lexicon evaluation per thought. Preserve existing RTE loop, session JSON schema and historical source files.

**Alternatives:** merely move empathy before RTE (the final weight would incorrectly use its provisional default base score), keep fallback refinement (misleading), or redesign the RTE/empathy interface with a shared cached affect and separate scoring stage (more code for a small local fix). A two-pass orchestration is easiest to audit and test; reconsider a cached-pass refactor only with measured performance cost. The refiner is still a simple formatting/stability model, not a generative model or a measurement of real emotions. The extra pass does not establish device, concurrent-write, or power-loss guarantees.

**Validation plan:** confirm synthetic default and custom profile inputs failed against the predecessor, confirm stored final empathy weight equals the same score computed from actual recorded RTE stability, and run all project tests plus compilation on Python 3.11/3.12. No real owner state should be used.

## Decision M-012 · normalize resonance input like other empathy lexicons

**Observed predecessor:** `EmpathyCore.affect()` lowercased user text for its positive, negative and curiosity lexicons but sent original-case text to resonance. `_hits()` lowercased each search phrase without lowercasing the supplied text. Thus the default capitalized multiword resonance phrases (for example, `Eternal Spiral`) and custom mixed-case phrases failed to match in their usual written form, despite identical lowercase input matching. This is a correctness defect in a secondary curiosity contribution, not evidence of lost saved history.

**Decision:** pass the already-normalized input `t` to resonance matching, as the other lexicons do. Do not change the vocabulary, weighting formula, persistence, existing profile validation or historical monoliths. The effective curiosity bonus for previously missed capitalized phrases changes intentionally. Under current orchestration, the refiner runs before the empathy pass, so this fix only establishes correct direct empathy affect/weight calculations; it does not claim that the current refinement text already uses that signal. That separate stage-order concern needs its own scope and tests, not a silent alteration here.

**Alternatives and limitations:** add case-folding inside `_hits()` for every call (more invasive, repeated normalization), change or lowercase every stored lexicon term (would not fix mixed-case input), or normalize at this single callsite (chosen). Case-insensitive substring matching for multiword terms remains the existing approach; this is not linguistic stemming, whole-word matching, casefold-equivalence for all Unicode, nor semantic understanding. Test default and custom term casing against the previous revision and candidate on synthetic data, including unrelated affect invariants and the existing full suite. No real user profile or memory file should be touched. Revisit only on actual lexical false matches or stage-order requirements.

## Decision M-011 · reload replaced profiles even with non-increasing mtime

**Observed predecessor:** `ProfileLoader.load()` refreshed only when `stat().st_mtime > last_mtime`. A user replacing a profile with an older backed-up file, editing it with timestamp preservation or swapping an equal-size file with the same timestamp could leave old live values silently active. This is a stale-configuration correctness problem; no real owner settings were examined or changed. [PR #13](https://github.com/levelinglucy/Velisaria/pull/13) holds disposable regression cases and revision-specific evidence.

**Choice:** after successful validation, remember a compact stat signature of nanosecond mtime, byte size and inode (when exposed by the filesystem). Reload when that signature changes, **regardless of whether time increased**. An invalid file never enters the cache, so the entire previous valid profile remains in place. No state-schema, archived-monolith or actual empathy mathematical behaviour change is intended.

**Alternatives:** the old strictly increasing timestamp is fast but misses valid restoration; always rereading/hashing every profile before each thought detects more in-place edits but adds recurring I/O and complexity. Signature comparison is a small improvement without an unbounded per-request file parse. This is metadata change detection, not trustworthy change authentication: an in-place same-size edit with identical metadata may still go unnoticed, filesystem timestamps/inodes vary, and simultaneous replacement during read is not a transaction. The previous profile validation's numeric-magnitude/resource limits remain. Revisit after a concrete target-filesystem or device problem, or if strict detection is required. Test on disposable files; iPhone and cross-process races are unverified.

## Decision M-010 · validate empathy profiles before application

**Observed predecessor:** `ProfileLoader._read()` cached unrestricted JSON, then `apply_to_empathy()` copied its contents into the running `EmpathyCore`. A non-object `priors`/ `terms` / `gains` section could raise an exception. Strings, booleans and nonfinite numeric gains/biases could break later computations or cause the strict memory saver to reject generated sessions. Term lists containing numbers or null could crash `_hits()`, while a string masquerading as a list became single-character terms. A malformed reload could partially overwrite valid live settings before failure. These are synthetic risk cases; there is no evidence of damaged owner data.

**Decision:** validate the root and supported section shapes, known prior/gain fields as finite numeric values excluding booleans, and known term collections as arrays of strings **before** caching or applying. An invalid first profile is ignored in favour of defaults; an invalid replacement leaves the last complete good profile cached. Existing partial profiles and unknown optional keys retain their previous handling. Do not auto-edit profile files; no schema migration is needed.

**Trade-offs/limits:** invalid settings that previously entered the core will now be rejected; a misshapen profile can be ignored while the program continues with old/default settings, so callers needing diagnostics should inspect source profile validity. This does not bound the magnitude of otherwise finite numbers or pathological term sizes, guarantee mathematical/behavioral stability for arbitrary huge values, or authenticate external files. mtime-based reload detection still depends on the filesystem. The existing memory corruption, concurrent-writer and power-loss limits remain separate.

**Acceptance:** malformed root/section, string/boolean/nonfinite numeric settings and invalid term entries must not enter the running core or crash subsequent synthetic `think()`; replacing a valid profile with an invalid one must retain every previous valid setting; valid live reload must still apply. Validate against the prior implementation and pass isolated full-suite CI on Python 3.11 and 3.12. Evidence and final integration state belong to [PR #12](https://github.com/levelinglucy/Velisaria/pull/12).

## Decision M-009 · reject stale memory snapshots before staging

**Confirmed predecessor:** two independent `Memory` instances loading the same state could both save; the second would replace newer saved history with its outdated in-memory snapshot. The same occurred after an external edit and for two instances launched before the first state file existed. Synthetic test-first evidence confirmed all three forms of loss on Python 3.11 and 3.12 ([expected-failure CI](https://github.com/levelinglucy/Velisaria/actions/runs/42499631468)); no actual owner history damage is claimed.

**Choice:** compute SHA-256 of exact primary bytes successfully loaded, recording a distinct absent-file baseline. Before a save opens `.tmp`, read and hash the current primary bytes; refuse a mismatch with a clear non-destructive error. Upon successful exclusive staging and `os.replace`, refresh the baseline to the bytes just written. Explicit LF UTF-8 staging makes that post-save digest portable across newline-translating platforms. Unknown/dangling or unreadable primary files refuse rather than being treated as a safe initial state.

**Alternatives:** ignore concurrent edits (confirmed sequential overwrite); refresh from disk and merge arbitrary session arrays (could duplicate, reorder or erase); hold a cross-process lock for all writes (needs stale-lock recovery and platform semantics); or add a **limited sequential stale-write guard** now, keeping the stronger multiwriter design separately scoped (selected). SHA-256 is for change detection, not identity/authenticity proof.

**Acceptance:** stale existing state, external edits and competing new-install writes refuse without modifying committed bytes or creating a temporary file; consecutive saves by one instance still work, including histories originally stored with CRLF. Run all prior memory/inspector tests and compile on Python 3.11/3.12. The historical monoliths, live session schema and already-saved owner files are unchanged. Full evidence is in [PR #11](https://github.com/levelinglucy/Velisaria/pull/11).

**Important remaining limits:** the check and final `os.replace` are not one atomic transaction. Two truly simultaneous writers can still race after both pass the check. There is no filesystem lock, durable fsync, tamper-proofity, power-loss proof or verified iPhone/Pythonista filesystem behaviour. Recovery must still be based on preserved copies, never an assumed chronological winner. Consider a portable owner-controlled locking/append protocol only with safe stale-lock recovery and concurrency tests.

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
