# Sanctified Monolith · change history

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
