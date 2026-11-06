# Sanctified Monolith · change history

## 2026-11-06 · memory-integrity maintenance candidate (unreleased)

**Affected:** `sanctified_monolith.py` `Memory.load`, `tests/test_memory_integrity.py`, developer documentation and Python CI.

**Previously:** an existing unreadable or malformed `sanctified_state.json` silently reset `sessions` to an empty list in memory; the next valid input could overwrite recoverable history.

**Now:** the loader treats a truly missing file as first launch, while refusing to continue on invalid JSON, unreadable text/files or missing/non-list `sessions`. Unknown extra top-level fields are preserved. No change to the standard JSON record shape for valid files.

**Why:** preserving owner history is more important than silently treating damaged history as new.

**Compatibility:** invalid pre-existing files now prevent startup until repaired; callers that assumed silent fallback must handle the exception. No automatic migration/recovery, auto-clearing or modification to archived monoliths.

**Validation:** seven isolated synthetic tests, including real subprocess CLI and byte-identical malformed-state preservation, passed on BOTH Python 3.11 and 3.12 in [CI run 42311924735](https://github.com/levelinglucy/Velisaria/actions/runs/42311924735) at candidate commit `5306bcd9`. Subsequent documentation-only updates require the latest head check before integration. Power-cut and actual Pythonista/iPhone semantics not yet tested.

**Rollback:** preserve the complete damaged file and possible `.tmp` evidence. Reverting the loader without repairing corrupted data can trigger the original silent data-loss behaviour. No stable tag or published release.

See [decision M-001](./DEV_NOTES.md#decision-m-001--preserve-corrupt-state-rather-than-silently-forget-it).

## Historical originals

The `README.md` Covenant v1.0 and archived Velisara monoliths predate this workshop. Their past design rationale is not reconstructed or retroactively attributed to this change. This changelog begins with verified workshop changes only.
