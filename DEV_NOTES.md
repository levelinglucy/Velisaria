# Sanctified Monolith · developer notes

## Development summary

**Purpose:** preserve local session history in the smaller Sanctified Monolith without changing the historical Covenant or archived monoliths. **Integration:** M1 corrupt-state and M2 interrupted-save preservation are merged maintenance candidates; the M3 read-only inspector is documented under **Unreleased**. PR history records integration and CI; none of this is a tagged stable release.

**Current goal:** allow an owner to inspect *copies* of the primary and orphan `.tmp` files without overwriting either or showing session contents. **Latest implementation:** `inspect_memory_state.py` reports bounded validity and list-prefix relationships, and declines unsafe file types. **Next steps:** run isolated inspections against additional synthetic legacy shapes; seek relevant Pythonista/iPhone evidence; investigate manual recovery only if an evidence-backed procedure exists. **Limitations:** structural similarity does not prove chronology, completeness, power-cut durability or safe auto-restoration. [Changelog](./CHANGELOG.md) · [Inspector tests](./tests/test_memory_inspector.py) · [Memory tests](./tests/test_memory_integrity.py).

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
- **Stable:** only after actual target-device checks and an explicit release decision. No tag, release or migration is claimed now.

## Continuation

M1/M2 preserve damaged and orphaned state; M3 supplies a separate read-only, no-repair inspection aid. Review synthetic/legacy copied-format evidence and possible honest owner recovery guidance next. Preserve the original Covenant and archives. Do not promise deterministic replay: `MotionForge._seed` uses Python's process-randomized `hash(text)`.
