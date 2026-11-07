# Sanctified Monolith · developer notes

## Development summary

**Status:** historical Velisara Covenant v1.0 remains unchanged. The smaller `sanctified_monolith.py` now has an **integrated, untagged memory-integrity maintenance candidate** on main via [PR #1](https://github.com/levelinglucy/Velisaria/pull/1), merge `fdbe2494`; it is not a versioned stable release.

**Current goal:** protect existing local history across interrupted saves. **Current stage:** M2 maintenance candidate merged through PR #3 at main `d3082d1a`, not tagged or released; M1 fail-closed loader remains part of the integrated main baseline. **Latest changes:** refuse leftover `.tmp` at startup and exclusively create the temporary file when saving, preserving possible interrupted generations; simulate real pre-replace process exit on synthetic data. **Next priorities:** (1) investigate copy-only owner inspection for competing state generations; (2) obtain trusted Pythonista/iPhone and real power-loss evidence before stable promotion; (3) revisit multi-writer coordination only with a concrete use case. **Limitations:** no automatic repair, cross-process write coordination or proven power-cut durability. [Changelog](./CHANGELOG.md) · [Tests](./tests/test_memory_integrity.py).

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

**Owner recovery if startup fails:** Do not rerun an older version against the damaged state. Preserve the exact file bytes and any adjacent `.tmp` file before investigating. Work on copies; do not rename `.tmp` to the live state without checking which generation it contains. This branch does not include a repair command.

## Milestone / release gates

- **M1 (integrated candidate):** non-destructive refusal on malformed state + isolated synthetic CLI tests. Seven tests passed on Python 3.11 and 3.12 at the final PR head and merged-main candidate (CI [42312031091](https://github.com/levelinglucy/Velisaria/actions/runs/42312031091), [42312078957](https://github.com/levelinglucy/Velisaria/actions/runs/42312078957)).
- **M2 (merged maintenance candidate):** interrupted-write/exclusive-temp preservation, synthetic pre-replace process termination, and copy-only owner guidance. 12/12 tests passed per version in [final PR CI 42318289406](https://github.com/levelinglucy/Velisaria/actions/runs/42318289406) at `f112440b`, and [merged-main CI 42318351081](https://github.com/levelinglucy/Velisaria/actions/runs/42318351081) at `d3082d1a`. Trusted Pythonista and actual power-cut checks remain pending.
- **Stable:** only after actual target-device checks and an explicit release decision. No tag, release or migration is claimed now.

## Continuation

First inspect merged main `d3082d1a`, preserved CI, and new issues; M2 is integrated. Next investigate copy-based inspection for an orphan `.tmp` without auto-promotion or deleting the originals. Keep the original Covenant and large archives intact. Do not promise deterministic replay: `MotionForge._seed` uses Python's process-randomized `hash(text)` and requires an independent decision.
