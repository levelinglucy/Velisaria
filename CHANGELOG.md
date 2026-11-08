# Sanctified Monolith · change history

## Unreleased · M9 stale-memory save protection

- Reject an ordinary save if the on-disk primary changed since this instance last loaded or successfully saved it; prevent sequential stale writers from silently replacing more recent sessions.
- Detect a new primary appearing after first-start, as well as externally edited existing files. Reject *before* opening staging files; preserve the disk state on refusal.
- Retain normal successive saves from the same process and accept CRLF-originated histories, with LF UTF-8 staging so checksums match emitted bytes across platforms.
- Synthetic test-first failures reproduced the original three overwrite paths on both Python 3.11/3.12. The guarded candidate passed 35/35 per version plus compilation; exact integration proof and final revision belong to [PR #11](https://github.com/levelinglucy/Velisaria/pull/11).
- This is not an atomic multiwriter transaction: simultaneous writers can still race between the check and replace. No iPhone or power-loss durability claim. See [decision M-009](./DEV_NOTES.md#decision-m-009--reject-stale-memory-snapshots-before-staging).


## Unreleased · M8 complete-history retention

- Stop silently dropping older saved sessions once a new entry crosses 4,000 records. Previously 4,001 became only the latest 2,500; the new behavior preserves all existing records without changing the JSON schema.
- Add a disposable 4,000→4,001 history round-trip regression. Exact test-first failure on Python 3.11/3.12: [CI 42494651459](https://github.com/levelinglucy/Velisaria/actions/runs/42494651459). Final validation and integration evidence belong to [PR #10](https://github.com/levelinglucy/Velisaria/pull/10).
- History, file size and memory required for full serialization now grow without automatic pruning. Owner-controlled archival is a future, separately validated decision; no target-device storage, concurrency or power-loss guarantee. See [decision M-008](./DEV_NOTES.md#decision-m-008--never-prune-saved-sessions-implicitly).

## Unreleased · M7 strict generated-memory save preflight

- Validate and serialize the complete in-memory state with standard JSON numbers before creating `.tmp`, refusing generated NaN/Infinity instead of publishing a state the next strict loader cannot read.
- Reject unserializable records and circular structures before filesystem writes, avoiding partially written staging files on ordinary JSON encoding failures. Actual failed staging/rename operations continue to retain recovery evidence; previously committed memory remains untouched.
- Preserve the existing JSON shape and output formatting, with a proportional in-memory serialization buffer cost. Disposable regression coverage and trade-offs are in [decision M-007](./DEV_NOTES.md#decision-m-007--validate-generated-memory-before-staging) and [PR #9](https://github.com/levelinglucy/Velisaria/pull/9). Unreleased; no device or power-loss claim.

## Unreleased · M6 finite numeric history fidelity

- Reject saved finite JSON decimals whose numeric value would be rounded or underflowed by the live float loader and next standard JSON save; do not overwrite contested original history.
- Preserve ordinary float runtime types, the existing file schema and numerically equivalent spellings such as `1e0` and `1.0`; this is numeric-value protection, **not** original number-token preservation or automatic repair.
- Added disposable loss/compatibility regressions. See [decision M-006](./DEV_NOTES.md#decision-m-006--reject-lossy-finite-decimal-rewrites) and [PR #8](https://github.com/levelinglucy/Velisaria/pull/8) for evidence. No stable or target-device release claimed.

## Unreleased · M5 strict live-memory JSON load

- Refuse ambiguous primary memory state containing duplicate object keys (including nested session fields) instead of silently accepting the last value and potentially overwriting lost history on the next save.
- Reject nonstandard JSON constants, nonfinite float overflows and excessive parser nesting with a clear startup error; preserve original bytes and adjacent temporary evidence for owner investigation.
- Added isolated, byte-preservation regressions and documented availability/compatibility trade-offs in [decision M-005](./DEV_NOTES.md#decision-m-005--refuse-ambiguous-json-before-live-memory-rewrite); exact validation and integration belong to [PR #7](https://github.com/levelinglucy/Velisaria/pull/7). Valid JSON state schema and archived originals remain unchanged.

## Unreleased · M4 conservative memory-generation comparison

- Fixed false equivalence/prefix reports in copied JSON state when binary float parsing rounded or overflowed distinct recorded numbers, or Python equated JSON booleans with numbers.
- Inspector comparisons preserve exact numeric tokens behind an internal type tag. Equal-value spellings (e.g. `1` versus `1.0`) may now conservatively report divergence; primary and temporary files, live memory formats and historical sources remain unchanged.
- Added disposable type/precision/prefix regressions; recovery remains manual and inspection-only. See [decision M-004](./DEV_NOTES.md#decision-m-004--preserve-evidence-distinctions-in-json-scalars) and PR #6 for exact validation.

## Unreleased · M3 read-only state inspection

- Added standalone stdlib `inspect_memory_state.py --state PATH` to inspect copied primary and adjacent `.tmp` histories. It does not change memory files, promote either generation, or print session contents.
- Reports strict JSON/schema validity, private session counts and conservative equality/prefix/divergence relationships; rejects symlinks, special files, oversized files and detected file-change races.
- Added disposable synthetic tests for missing, damaged, divergent and prefix-related generations, CLI privacy, links and byte-for-byte preservation. Validation evidence belongs to the associated pull request's checks.
- Recovery implication: **no automatic repair**. A prefix relationship is not a trustworthy chronology or proof of crash durability. Inspect only owner-made copies with writers stopped; retain original evidence. See [decision M-003](./DEV_NOTES.md#decision-m-003--inspect-competing-memory-copies-without-choosing-one).

## 2026-11-07 · interrupted-save preservation merged candidate (PR #3; not released)

**Affected:** `sanctified_monolith.py` (Memory.load/save + developer header), `tests/test_memory_integrity.py`, project developer documentation. The Covenant and all archived monoliths are unchanged.

**Verified previous behaviour:** writing state through a fixed `state.json.tmp` in `"w"` mode silently truncated any existing temporary record. Loading a valid primary with an orphan `.tmp` ignored that recovery evidence; loading a missing primary with a potentially recoverable `.tmp` treated it as a new installation. A subsequent save could erase an interrupted generation. Regression tests first demonstrated this against baseline commit `61b8d3f` (red CI [42318018754](https://github.com/levelinglucy/Velisaria/actions/runs/42318018754): six failing assertions/variants in each Python version; these are expected failures on the old behaviour, not a production crash report).

**Change and why:** startup now refuses any existing `.tmp` rather than selecting a generation automatically; saving creates that path exclusively (`"x"`) rather than truncating it. A dangling primary-state symlink also cannot masquerade as a genuinely absent first launch. Valid first installs and existing valid history without leftover temporaries continue with the same JSON shape. Intentional extra caution preserves copies of recoverable local memory at the cost of manually inspecting orphan files.

**Validation:** five new bounded synthetic test methods cover existing/missing primary, injected rename failure, an already-running saver encountering a pre-existing temp, and real subprocess termination via `os._exit(37)` immediately before replacement. All use disposable state. After the code and developer documentation changes, **12/12 tests passed independently on Python 3.11 and 3.12** at candidate `78e93607` in [CI run 42318191650](https://github.com/levelinglucy/Velisaria/actions/runs/42318191650). The exact final PR head `f112440b` passed [CI 42318289406](https://github.com/levelinglucy/Velisaria/actions/runs/42318289406) in both versions; merged main `d3082d1a` then passed [CI 42318351081](https://github.com/levelinglucy/Velisaria/actions/runs/42318351081). This is an integrated, untagged candidate; neither a stable release nor power-cut durability is established.

**Limitations and rollback:** `os.replace` is not a claim of power-loss durability (no directory/file fsync). Concurrent independent writers can still lose updates; `.tmp` may be partial, stale or newer and is never auto-promoted. On intentional rollback, copy both primary and temporary files first; reverting to the old saver could destroy the temporary evidence. No device validation, tagged version or released artifact yet. See [decision M-002](./DEV_NOTES.md#decision-m-002--never-overwrite-interrupted-temporary-memory).

## 2026-11-06 · memory-integrity maintenance candidate integrated (untagged, unreleased)

**Affected:** `sanctified_monolith.py` `Memory.load`, `tests/test_memory_integrity.py`, developer documentation and Python CI.

**Previously:** an existing unreadable or malformed `sanctified_state.json` silently reset `sessions` to an empty list in memory; the next valid input could overwrite recoverable history.

**Now:** the loader treats a truly missing file as first launch, while refusing to continue on invalid JSON, unreadable text/files or missing/non-list `sessions`. Unknown extra top-level fields are preserved. No change to the standard JSON record shape for valid files.

**Why:** preserving owner history is more important than silently treating damaged history as new.

**Compatibility:** invalid pre-existing files now prevent startup until repaired; callers that assumed silent fallback must handle the exception. No automatic migration/recovery, auto-clearing or modification to archived monoliths.

**Validation:** seven isolated synthetic tests, including real subprocess CLI and byte-identical malformed-state preservation, passed on BOTH Python 3.11 and 3.12 in [CI run 42311924735](https://github.com/levelinglucy/Velisaria/actions/runs/42311924735) at candidate commit `5306bcd9`. The exact final PR head `d773fdb7` passed [CI 42312031091](https://github.com/levelinglucy/Velisaria/actions/runs/42312031091), and merged main `fdbe2494` passed [CI 42312078957](https://github.com/levelinglucy/Velisaria/actions/runs/42312078957), each on Python 3.11 and 3.12. PR #1 was merged as a candidate; this entry is a documentation-only status correction. Power-cut and actual Pythonista/iPhone semantics not yet tested.

**Rollback:** preserve the complete damaged file and possible `.tmp` evidence. Reverting the loader without repairing corrupted data can trigger the original silent data-loss behaviour. Merged through [PR #1](https://github.com/levelinglucy/Velisaria/pull/1); no stable tag or published release.

See [decision M-001](./DEV_NOTES.md#decision-m-001--preserve-corrupt-state-rather-than-silently-forget-it).

## Historical originals

The `README.md` Covenant v1.0 and archived Velisara monoliths predate this workshop. Their past design rationale is not reconstructed or retroactively attributed to this change. This changelog begins with verified workshop changes only.
