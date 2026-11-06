# Sanctified Monolith · developer notes

## Development summary

**Status:** historical Velisara Covenant v1.0 remains unchanged. The smaller `sanctified_monolith.py` now has an **integrated, untagged memory-integrity maintenance candidate** on main via [PR #1](https://github.com/levelinglucy/Velisaria/pull/1), merge `fdbe2494`; it is not a versioned stable release.

**Current goal:** protect existing local session history when a state file is truncated, malformed or unreadable at startup. **Latest change:** fail closed with an explicit recovery message instead of quietly resetting sessions. **Next priorities:** (1) verify merged-main CI; (2) test on a trusted Pythonista/iPhone; (3) consider separate, non-destructive crash recovery for `.tmp` after evidence. **Blocker:** no trusted target-device or real-user recovery evidence. [Changelog](./CHANGELOG.md) · [Tests](./tests/test_memory_integrity.py).

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
- **M2 (verification):** trusted Pythonista device and interrupted-write exercises on disposable files, preserving prior state and showing a recoverable failure.
- **Stable:** only after actual target-device checks and an explicit release decision. No tag, release or migration is claimed now.

## Continuation

First inspect merged-main head and CI. M1 is merged; leave it alone absent a new regression, preserving the original covenant and large archive files. If a later test fails, repair that exact regression before expanding scope. Then investigate `.tmp` retention and safe snapshot recovery using synthetic data. Do not promise deterministic replay: `MotionForge._seed` uses Python's process-randomized `hash(text)` and requires an independent decision.
