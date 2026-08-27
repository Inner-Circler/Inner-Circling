# TRANSACTION.PY(1)

## NAME
transaction.py — journaled, crash-detectable commit/verify/record machinery for the nightly run's file writes (phases 7-9 of NIGHTLY_DESIGN.md), plus post-crash journal repair

## SYNOPSIS
This file defines no `__main__` block and is not run directly; it is a library imported by the nightly orchestrator (referenced elsewhere as implementing "phases 7-9" of `NIGHTLY_DESIGN.md`). It is used via its `Transaction` class and the three module-level recovery functions (`find_journals`, `journal_finish`, `journal_rollback`).

## DESCRIPTION
The module's own docstring states its guarantee precisely: `os.replace()` is atomic per file on NTFS, but there is no multi-file atomic commit on any filesystem, so a true all-or-nothing swap across many files is not achievable. What this module implements instead is a swap that is always *detectable* and *completable* even if interrupted mid-way (process kill, power loss, etc.):

1. Write a JOURNAL file recording every intended replacement (source/dest relative path, sha256 of both the new and any existing old bytes, byte counts), then fsync it.
2. Copy every live file about to be overwritten into a `rollback/` directory, fsyncing each copy.
3. `os.replace()` each staged file over its live path.
4. fsync.
5. Delete the JOURNAL.

A crash at any point between steps 1 and 5 leaves the JOURNAL on disk. The module's contract (enforced by the caller, per `commit()`'s own refusal — see MAIN/OPERATION) is that no later run may proceed while a JOURNAL exists; instead the operator (or an automated recovery step) must run either `journal_finish()` (complete the interrupted swap) or `journal_rollback()` (undo it), both of which are pure, deterministic file operations driven entirely by comparing on-disk sha256 hashes against the two hashes recorded in the JOURNAL — no judgement calls, no re-running application logic. The worst case under this design is a tree that is *known* to be half-swapped and mechanically repairable, rather than one that is silently half-written.

Two further design notes from the header comments: only files whose staged bytes actually differ from the live file are staged into a commit at all (`changed()`), because an unchanged file entering a commit would be pure noise in every future diff of the journal/rollback history. And every path used throughout the class is derived from the `root` constructor argument rather than any hardcoded location, specifically so the whole commit/rollback/verify path can be exercised against a disposable copy of the tree in tests, rather than only ever having been exercised against real project data.

## MAIN
This module defines no `main()` function and no top-level executable script body outside function/class/constant definitions — it is a pure library module. There is therefore no single execution order to describe; each of its public entry points (`Transaction.commit`, `Transaction.verify`, `Transaction.record_committed`, `find_journals`, `journal_finish`, `journal_rollback`) is invoked independently by the calling orchestrator, and each one's own internal branching is documented under OPERATION below.

## COMMAND-LINE ARGUMENTS
None — this is a library module with no CLI surface of its own.

## DEPENDENCIES
Standard library: `datetime`, `json`, `os`, `pathlib`, `shutil`.
Local/sibling module: `ifs_model` (imported as `M`). This module supplies: `M.sha(data)` (sha256 hex digest of bytes), `M._tree_files(root)` (the fixed list of per-part `long_term.md`/`part_relationships.toml` paths plus self-directory files that make up the tracked tree), `M.compare_trees(baseline, candidate, today=...)` (returns a list of `M.Finding` objects — each with `level`, `code`, `path`, `message` — checking every invariant in NIGHTLY_DESIGN §4 between a baseline and candidate tree).

## EXTERNAL FILES
Read:
- Every path under `<root>/staging/` inside `staged()`, `changed()`, `candidate_tree()`, and `commit()` — the files this run intends to write.
- Every corresponding live path under `<root>/<rel>` inside `changed()` and `commit()`, to compare current bytes / build rollback copies.
- Every file listed by `M._tree_files(root)` plus every `<root>/self/narrative_*.md` file, inside `candidate_tree()`, to build the full overlay tree passed to the invariant checker.
- `<dir>/committed.json`, inside `verify()`, if present (if absent, `verify()` logs a warning and passes trivially — see BUGS/behavior note below).
- The JOURNAL file itself, inside `journal_report()` (called by both `journal_finish()` and `journal_rollback()`), plus every path it names under both the run's `staging/` and `rollback/` directories, and the live tree paths themselves (to compute current sha256 for state classification).

Written:
- `<staging>/<rel>`, whenever `stage(rel, data)` is called (unconditional — this is the staging API itself).
- `<dir>/JOURNAL`, at the start of `commit()`, whenever there is at least one changed file and no JOURNAL already exists.
- `<rollback>/<rel>`, for every changed file that currently exists live, during `commit()` step 2 (copy-before-overwrite).
- The live tree paths `<root>/<rel>`, replaced via `os.replace()` during `commit()` step 3, for every changed entry.
- `<dir>/committed.json`, whenever `record_committed()` is called, unconditionally overwriting any prior content.
- During `journal_finish()`: live tree paths that are not already in the "new" state are replaced with their staged copy; the JOURNAL is deleted on full success.
- During `journal_rollback()`: live tree paths that are not already in the "old" state are overwritten with their rollback copy — except paths the transaction CREATED (sha_old null), which are deleted instead, that being their pre-swap state; the JOURNAL is deleted on full success.
- The `<dir>/candidate/` tree is rebuilt from scratch (deleted if present, then repopulated) every time `candidate_tree()` runs.

## NETWORK ACCESS
None. Every operation in this module is local filesystem I/O.

## HUMAN I/O
No stdin reads. All human-facing output goes through a caller-supplied `log(level, message)` callback passed into `commit()`, `verify()`, `journal_finish()`, and `journal_rollback()` — this module does not print directly. Log levels used: `"ok"`, `"fail"`, `"did"`, `"warn"`, `"note"`. `commit()` and `verify()` return `bool` (success/failure); `journal_finish()` and `journal_rollback()` likewise return `bool`. There is no process-level exit code since this is a library, not a script.

## OPERATION

### _fsync_file(p)
    {
        Opens the path read-only and calls os.fsync() on its file
        descriptor, always closing the descriptor afterward via
        try/finally.
    }
    if (any OSError occurs, e.g. the path does not support fsync) then {
        silently swallow it — the comment marks this explicitly as
        best-effort, "not available for all paths"
    }

### _fsync_dir(p)
    if (running on Windows, i.e. os.name == "nt") then {
        return immediately without attempting anything — the comment notes
        directory fsync is POSIX-only and opening a directory handle fails
        on Windows; per-file fsync is what carries the durability guarantee
        on that platform instead
    } else {
        attempt the same open/fsync/close sequence as _fsync_file, silently
        swallowing any OSError
    }

### Transaction.__init__(root, run_id)
    { Resolves `root` to an absolute path and derives every working
      directory from it: dir = root/work/nightly/<run_id>, and staging/,
      rollback/, candidate/, and the JOURNAL path underneath that. }

### Transaction.stage(rel, data)
    { Writes `data` to <staging>/<rel>, creating parent directories as
      needed, and returns the destination path. Unconditional — no
      dedup or diff check happens here (that is changed()'s job). }

### Transaction.staged()
    if (the staging directory does not exist) then {
        return an empty list
    } else {
        return the sorted list of every file's path, relative to staging,
        in POSIX form
    }

### Transaction.changed()
    for each staged relative path:
        if (the live file does not exist, OR its bytes differ from the
        staged bytes) then {
            include this path in the result
        } else {
            skip it — an identical staged file is not a real change and
            should not enter the commit, per the header's stated reasoning
            about diff noise
        }
    return the collected list

### Transaction.candidate_tree()
    if (a candidate directory from a previous run already exists) then {
        delete it entirely first
    }
    {
        Copy every file named by ifs_model._tree_files(root) that
        currently exists, into the candidate tree at the same relative
        path (preserving metadata via shutil.copy2).
    }
    {
        Additionally copy every root/self/narrative_*.md file into
        candidate/self/, by the same glob-then-copy2 pattern (these are
        evidently not part of the fixed _tree_files() list because they
        are dynamically named per day).
    }
    {
        Finally, overlay every staged file (not just changed ones — ALL
        currently staged files) onto the candidate tree, overwriting
        anything just copied from the live tree at the same relative path.
    }
    return the candidate directory path

### Transaction.validate(today=None)
    { Thin wrapper: builds the candidate tree via candidate_tree() and
      passes (root, candidate, today) to ifs_model.compare_trees(),
      returning its list of Finding objects unmodified. }

### Transaction.commit(log)
    if (changed() returns no paths) then {
        log "ok" that nothing differs and return True — a no-op commit is
        success, not a refusal
    } else if (a JOURNAL file already exists at self.journal) then {
        log "fail" naming the existing journal and return False WITHOUT
        touching anything else in the tree — this is the refusal gate that
        forces any prior interrupted swap to be resolved via
        journal_finish()/journal_rollback() before a new commit can run
    } else {
        {
            Build one entry per changed file recording its relative path,
            sha256 and byte-length of the new (staged) bytes, and sha256/
            byte-length of the old (live) bytes if a live file currently
            exists, else None for both old fields.
        }
        {
            Step 1: create the run directory if needed, write the JOURNAL
            as JSON (run_id, creation timestamp, resolved root, and the
            entries list), fsync the JOURNAL file, and log "did".
        }
        for each entry:
            if (no live file currently exists at that relative path) then {
                skip the rollback copy — there is nothing to back up
            } else {
                copy the live file into rollback/<rel>, creating parent
                directories as needed, and fsync the copy
            }
        { log "did" once after the rollback-copy loop completes. }
        for each entry:
            {
                os.replace() the staged file over the live path (creating
                parent directories first), then fsync the destination.
            }
        {
            fsync the root directory itself (a no-op on Windows per
            _fsync_dir), log "did" with the count replaced, delete the
            JOURNAL file (this is the point at which the swap is no
            longer "in progress" from a crash-recovery point of view),
            and return True.
        }
    }

### Transaction.verify(log)
    if (<dir>/committed.json does not exist as a file) then {
        log "warn" that there is nothing to verify and return True
    } else {
        {
            Load the entries list from committed.json.
        }
        for each entry:
            if (the live file is missing, OR its current sha256 does not
            match the recorded sha_new) then {
                add its relative path to the `bad` list — the comment
                notes this exists specifically to catch a write that
                silently did not land, which cannot be detected by
                checking the value held in memory at write time
            }
        if (bad is non-empty) then {
            log a "fail" line per bad path, log a "note" pointing at the
            rollback directory, and return False
        } else {
            log "ok" that every sha256 matched on re-read, and return True
        }
    }

### Transaction.record_committed()
    { Takes no argument since 2026-08-19. Writes <dir>/committed.json
      containing the run_id, a completion timestamp, and — for every entry
      commit() swapped — the sha_new commit() hashed FROM STAGING before
      the swap, carried on the instance (`_committed_entries`), never
      re-read from the live tree. Re-reading was the original behavior and
      made verify() compare the disk against itself: a replace that
      silently left wrong bytes hashed as "matching" on both sides.
      Raises RuntimeError if called before a successful commit(). }

### find_journals(root)
    if (<root>/work/nightly is not a directory) then {
        return an empty list
    } else {
        return the sorted list of every */JOURNAL path found one level
        down (i.e. one JOURNAL per run-id subdirectory, if present)
    }

### journal_report(jpath)
    {
        Parse the JOURNAL's JSON and resolve its recorded root. A JOURNAL
        that does not parse raises ValueError carrying the repair
        guidance (crash-during-write means deleting it is the whole
        repair; but the write is atomic since 2026-08-19 — atomic_write,
        temp-file + os.replace — so a torn journal can no longer be
        created here, and one damaged later deserves investigation), not
        a raw JSONDecodeError out of the diagnostic.
    }
    for each recorded entry:
        if (the live file at root/rel does not currently exist) then {
            classify its state as "absent"
        } else {
            compute its current sha256 and classify as "new" if it matches
            sha_new, "old" if it matches sha_old, or "other" if it matches
            neither — "other" meaning some third party touched the file
            after the crash, which the caller must be prepared to refuse to
            repair over (see journal_finish/journal_rollback below)
        }
    return (the parsed journal dict, the list of (rel, state) pairs)

### journal_finish(jpath, log)
    {
        Compute the per-file state via journal_report().
    }
    for each (rel, state):
        if (state is "new") then {
            skip — already fully applied, nothing to do
        } else if (the staged copy for this file no longer exists on
        disk) then {
            log "fail" naming the file's unexpected state and the missing
            staged copy, and return False immediately — finishing is not
            possible without the staged bytes, so the caller must roll
            back instead
        } else {
            os.replace() the staged file over the live path, fsync it, and
            log "did"
        }
    { On full success (loop completes without an early return), delete the
      JOURNAL file, log "ok", and return True. }

### journal_rollback(jpath, log)
    {
        Compute the per-file state via journal_report(), and the set of
        rels the transaction CREATED (JOURNAL entries with sha_old null).
    }
    for each (rel, state):
        if (state is "old") then {
            skip — already at the pre-swap value, nothing to restore
        } else if (the rel is in the created set) then {
            its rolled-back state is ABSENT — commit() rightly took no
            rollback copy, because there was nothing to copy. Delete the
            live file if it exists (unlink, missing_ok), log "did", and
            continue. (Until 2026-08-19 this case hit the missing-copy
            fail below, so a transaction that created any file could
            never be rolled back at all.)
        } else if (no rollback copy exists for this file) then {
            log "fail" naming the file's state and the missing rollback
            copy, and return False immediately
        } else {
            copy the rollback file over the live path (shutil.copy2),
            fsync it, and log "did"
        }
    { On full success, delete the JOURNAL file, log "ok", and return True. }

## BUGS
- `commit()`'s inline step comments are numbered 1, 2, 3, 5 — there is no comment numbered "4" even though the docstring's overview at the top of the file explicitly lists five steps (write journal, copy rollback, replace, fsync, delete journal). The `_fsync_dir(self.root)` call and its "replaced N file(s)" log line sit where step 4 (fsync) should be commented but are unlabeled, so the code and the header's own five-step description are very slightly out of sync — cosmetic, but worth flagging since the header treats the step numbering as meaningful.
- `verify()` treats a missing `committed.json` as automatic success (`log("warn", ...); return True`). Since `record_committed()` is presumably meant to be called by the orchestrator between `commit()` and `verify()`, this means if the orchestrator's own call sequence is ever broken (e.g. it skips calling `record_committed()`, or calls `verify()` before `record_committed()` finishes), `verify()` will not detect that anything is wrong — it will report success having actually verified nothing. This may be intentional (verify is opt-in / a defensive extra rather than a hard requirement), but it is worth confirming with whoever owns the orchestrator's call order that a silently-skipped verify can't mask a real problem.
