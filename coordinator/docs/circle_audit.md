# CIRCLE_AUDIT(1)

## NAME

circle_audit.py — the circle-record audit (renamed from nightly.py 2026-08-19): preflight checks, a survey of circles inter_circle.py has not processed, reconcile-and-backfill safety net, invariant validation against a snapshot baseline, and a write-ahead commit of any staged repairs.

## SYNOPSIS

    python coordinator/circle_audit.py
    python coordinator/circle_audit.py --selfcheck
    python coordinator/circle_audit.py --snapshot [DIR]
    python coordinator/circle_audit.py --baseline DIR|last [--prune-baselines]
    python coordinator/circle_audit.py --git-setup [--git-name NAME] [--git-email EMAIL]
    python coordinator/circle_audit.py --backfill [--all-circles] [--dry-run] [--commit] [--no-git]
    python coordinator/circle_audit.py --stage-synthetic [--commit] [--no-git]
    python coordinator/circle_audit.py --commit [--no-git]
    python coordinator/circle_audit.py --transaction-status
    python coordinator/circle_audit.py --transaction-finish
    python coordinator/circle_audit.py --transaction-rollback
    (any of the above, plus --log to mirror output to a log file)

## DESCRIPTION

This script audits the per-circle records that `/close` and `coordinator/inter_circle.py` produce (its design history, under its old name, is `docs/NIGHTLY_DESIGN.md`). Nine phases are named in the module docstring: 0 preflight, 1 survey, 2 reconcile, 3 backfill, 6 validate, 7 commit, 8 verify, 9 record. Phases 4 (dream) and 5 (synthesise) are deliberately elsewhere — they are `coordinator/inter_circle.py`, run synchronously as `/close`'s second phase; this module is the independent check on that engine's records and stays independent of it. Without `--commit`, this script writes only under `work/circle_audit/` (its lock, snapshots and run log) and `work/nightly/` (the transaction module's staging root, shared with inter_circle.py and not renamed with this file); with `--backfill --commit` specifically, it writes short-term files and nothing else, a scope enforced by three independent layers — the staging directory (nothing reaches the live tree except through a commit), the invariant gate (phase 6 validation must pass first), and the transaction module's atomic swap-and-verify machinery.

"Processed" has exactly one definition here, and it is inter_circle.py's: the `dream/<OT>` git tag its phase-2 commit writes. The survey's scope EPOCH is the oldest such tag — circles older than it belong to the retired batch-nightly era and are out of audit scope by ruling (2026-08-19); the old dreaming manifests under `work/manifests/` are dead records this script no longer reads. Previously the only assurance over these records was a model's own self-report inside the retired dreaming skill's instructions ("Confirm all files were written in this run"); this audit exists to be the independent verification of them.

Two mechanisms recur throughout the script and are worth naming up front. First, a `Run` object accumulates every failure found across a whole invocation rather than stopping at the first one, so one bad check never hides the next — every phase function takes a shared `Run` and reports into it. Second, a commit-time TRANSACTION file (from the sibling `TRANSACTION_CLASS` module) records an in-progress file swap so that if the process is interrupted mid-write, a later run can detect the leftover transaction file and refuses to do anything else until a human resolves it via `--transaction-status`/`--transaction-finish`/`--transaction-rollback` — this script's preflight phase (0) checks for exactly this condition first, before anything else.

## MAIN

`main()` is structured as an argument parser (see COMMAND-LINE ARGUMENTS for every flag) followed by a long dispatch chain based on which flags were given. It is dispatch-style in the sense described below: several early branches are pure routing to a self-contained handler function and return immediately, while a later, larger branch runs a full preflight-through-result sequence inline.

    Parse all arguments into `args`.
    Create a fresh `Run` tracker and record the start time.
    if (`--log` was given) then {
        wrap stdout in a `Tee` that mirrors everything printed to a
        timestamped file under work/logs/, in addition to the console,
        so a run's detailed findings survive somewhere durable.
    }
    Print a banner naming the phases covered and the project root.

    if (`--transaction-status`, `--transaction-finish`, or `--transaction-rollback` was
        given) then {
        dispatch immediately to circle_audit_transaction_command_read() with the corresponding
        action and return its result. (Only the first matching flag in
        this fixed check order is honored if more than one were somehow
        given.)
    } else if (`--git-setup` was given) then {
        dispatch immediately to circle_audit_git_setup() and return its result.
    } else if (`--selfcheck` was given) then {
        run phase 6 with no baseline (a pure self-check of the live tree)
        and return 1 if any failures were recorded, else 0 -- this path
        skips locking, git checks, and reconcile entirely, as its help
        text states.
    } else {
        Run phase 0 (preflight: transaction file check, lock, circle-in-progress
        check, git preconditions, external record_verify.py).
        if (phase 0 reports failure) then {
            release the lock and return 2 if any failure is a "leftover
            commit" (a TRANSACTION file, or a JOURNAL a crash left before
            the 2026-09-04 rename), else return 1.
        } else {
            try {
                if (`--snapshot` was given) then {
                    Resolve the destination directory (a timestamped
                    default, or the given path). Take the snapshot, report
                    the file count, log the run, print a follow-up hint
                    for validating against it later, and return 0
                    immediately -- no further phases run in this branch.
                } else {
                    Run phase 1 (survey unprocessed circles) and phase 2
                    (reconcile + transcript safety net) unconditionally.

                    if (`--backfill` was given) then {
                        Build a Transaction. Determine scope: unprocessed
                        circles by default, or every circle on disk if
                        `--all-circles` was also given (with a warning
                        that backfilling an already-processed circle
                        repairs the record without re-triggering its
                        dreaming).
                        Run phase 3 (backfill) into the transaction.
                        if (anything was staged) then {
                            Run phase 6 validation of the staged
                            candidate against the live tree, print
                            non-OK findings, tally FAIL/WARN/OK, and
                            record any FAIL into `run.failures`.
                            if (`--commit` was given) then {
                                run phases 7-9 (commit/verify/record).
                            } else {
                                report the staged count and that
                                --commit is needed to write it.
                            }
                        }
                    } else if (`--stage-synthetic` OR `--commit` was
                        given) then {
                        Build a Transaction (nothing real to stage on
                        this path — backfill has its own branch, and
                        dream/synthesise live in inter_circle.py — so
                        this is the stand-in path for exercising the
                        transaction machinery).
                        if (`--stage-synthetic` was given) then {
                            stage a synthetic, legal change via
                            circle_audit_synthetic_stage().
                        }
                        if (nothing ended up staged) then {
                            fail: use --stage-synthetic to exercise the
                            transaction, or --backfill for a real repair.
                        } else {
                            Run phase 6 validation, print findings, tally,
                            record FAILs.
                            if (`--commit` was given) then {
                                run phases 7-9.
                            } else {
                                report validation-only completion.
                            }
                        }
                    } else {
                        Resolve the baseline directory from `--baseline`
                        (see circle_audit_baseline_resolve()).
                        if (`--baseline` was given but no matching
                            snapshot directory could be resolved) then {
                            fail: no such baseline snapshot exists.
                        } else if (a baseline path was resolved but is not
                            an existing directory) then {
                            fail: baseline directory not found; treat as
                            no baseline.
                        }
                        Run phase 6 (validate against the resolved
                        baseline, or self-check if none).
                    }
                    if (`--prune-baselines` was given) then {
                        delete old snapshot directories beyond the
                        newest KEEP_BASELINES (14) and report the count.
                    }
                }
            } finally {
                release the lock unconditionally.
            }
            Log this run's outcome (mode "validate" if --baseline was
            given, else "check"; result FAIL or ok; a summary of
            unprocessed-circle count and failure count).
            if (`run.failures` is non-empty) then {
                print every failure, note that nothing was written to the
                live tree (phases 7-9 run only behind --commit, and a
                phase-6 FAIL refuses them), and return 1.
            } else {
                print "all checks passed" and the elapsed time, and
                return 0.
            }
        }
    }

## COMMAND-LINE ARGUMENTS

`--snapshot [DIR]`
    Copy the current `parts/` and `self/` memory files to `DIR` (default: `work/circle_audit/baseline_<timestamp>`) and exit immediately, without running phases 1/2/6. Used as the before-side of a later `--baseline` comparison.

`--baseline DIR`
    Validate the live tree against this snapshot directory instead of self-checking it. The special value `last`/`latest`/`auto` (case-insensitive) resolves to the newest `work/circle_audit/baseline_*` directory, so a caller need not know the exact timestamp a prior snapshot run chose.

`--validate`
    Run phases 0, 1, 2, 6 — the default sequence — and nothing else. Given alongside a flag that selects another path (`--snapshot`, `--backfill`, `--stage-synthetic`, `--commit`) it REFUSES, naming the clash, and returns 1 rather than letting the other flag win silently. Honoured 2026-08-27; it was accepted and never read until then, so `--validate --backfill` ran the backfill without a word. (See BUGS.)

`--selfcheck`
    Run phase 6 only, against no baseline, with no lock, no git checks, and no reconcile.

`--git-setup`
    Idempotent git bootstrap: init, config, `.gitattributes`, `.gitignore`, un-tracking already-ignored paths. Never adds a remote, never rewrites history, never stages the whole tree.

`--git-name NAME`, `--git-email EMAIL`
    Identity to use with `--git-setup`. No default is set at the argparse level deliberately — the underlying `gitrepo.system_git_identity_resolve()` falls back through `$IFS_GIT_NAME`/`$IFS_GIT_EMAIL` (shell or `.env`), then git's own existing `user.name`/`user.email` config, then unset.

`--dry-run`
    With `--backfill`: report what would be generated (and an estimated cost) without calling the model.

`--prune-baselines`
    Delete all but the newest 14 (`KEEP_BASELINES`) snapshot directories under `work/circle_audit/`.

`--all-circles`
    With `--backfill`: scan every circle on disk, not only unprocessed ones — needed because a short-term record lost after its circle was already dreamed is otherwise invisible to the normal (unprocessed-only) scope.

`--backfill`
    Run phase 3: reconstruct any short-term record that is missing or malformed for a part that actually spoke in an unprocessed circle. Stages only; requires `--commit` to actually write.

`--stage-synthetic`
    Stage one legal synthetic change, so phases 6-9 (validate/commit/verify/record) can be exercised end-to-end with no model calls and no cost.

`--commit`
    Run phases 7-9 (commit, verify, record) against whatever was staged by `--backfill` or `--stage-synthetic`. Without this flag, a run that staged something stops after validation and writes nothing to the live tree.

`--no-git`
    With `--commit`: write the staged changes to disk but skip the `git commit` step.

`--transaction-status`, `--transaction-finish`, `--transaction-rollback`
    Inspect, complete, or undo an interrupted commit (a leftover transaction file from a process that died mid-file-swap). Each dispatches immediately and independently of every other flag. Default: off. The pre-B100 spellings `--journal-status` / `--journal-finish` / `--journal-rollback` (until 2026-09-04, R446/R448) are still accepted, hidden from `--help`, for one release: each prints a one-line note and does what its `--transaction-*` twin does. A leftover file named JOURNAL (left by a crash before the rename) is found and repaired exactly like a TRANSACTION; the report names whichever it found.

`--log`
    Mirror all printed output to a timestamped file under `work/logs/` (`circle_audit_<timestamp>.log`), in addition to stdout.

## DEPENDENCIES

Python standard library: `argparse`, `atexit`, `datetime`, `json`, `os`, `pathlib`, `re`, `shutil`, `subprocess`, `sys`, plus `from __future__ import annotations`.

Local/sibling modules: `ifs_model` (as `M`) — the file model: `record_file_verify`, `record_sha`, `record_bytes_read`, `SHORT_TERM_SECTIONS`, `PARTS`, and the `Finding` result type (`level`/`code`/`path`/`message`); `register_gate` (as `RG`, since 2026-09-03) — the gate: `_tree_files`, `record_tree_compare`, `record_tree_verify`, `register_summarise`; `gitrepo` (as `G`) — all git-repository bootstrap and safety operations (`system_git_is_available`, `system_git_run`, `system_git_repo_ensure`, `system_git_remote_refuse`, `system_git_config_ensure`, `system_git_attributes_ensure`, `system_git_hooks_ensure`, `system_git_ignore_ensure`, `system_git_ignored_untrack`, `system_git_is_dirty`, `system_git_paths_commit`, `system_git_identity_resolve`, `ENV_GIT_NAME`, `ENV_GIT_EMAIL`); `TRANSACTION_CLASS` (as `T`) — the staged-write/transaction file/commit machinery: the `Transaction` class (`stage`, `staged`, `changed`, `validate`, `commit`, `verify`, `record_committed`, `run_id`, `staging`) and the module-level `transaction_read`, `transaction_report`, `transaction_finish`, `transaction_rollback`; `roster` (as `R`) — `TAGS` and `DIR_BY_TAG` (current-spelling part tag/directory mappings, deliberately not `DIR_BY_TAG_ALL`, since this reader only ever sees circles the audit itself processes, all postdating a 2026-08-07 tag rename); `circle_state` (as `CS`, imported locally inside circle_audit_open_verify() and circle_audit_snapshot()) — `circle_is_in_progress()`, the fails-closed open-circle probe.

Inside `circle_audit_phase3_run()` only, two further dependencies are imported locally rather than at module load: `prompt_build` (as `C`, for the same identity/prompt assembly a live circle uses — `group_shared_read`, `circle_briefing_build`, `prompt_part_assemble`, `PART_TAGS`; it was `circle` until phase 2 stage 2, and `load_shared`/`shared_block`/`system_blocks` retired into `prompt_part_assemble` 2026-09-02) and `llm_client` (as `LC`, for `stream_client_build` and `stream_call_once` — the transport, which owns the `anthropic` client and the `.env` key resolution since 2026-08-28; this file built its own `Anthropic()` client until then).

External programs: `git`, invoked throughout via `subprocess.run` (directly in this file's `circle_audit_git_run()` helper, and indirectly through every `gitrepo` function); the sibling script `coordinator/record_verify.py`, invoked as a subprocess during phase 0; the sibling script `coordinator/circle_close_verify.py --reconcile`, invoked as a subprocess during phase 2.

## EXTERNAL FILES

    Read
        `work/circle_audit/.lock` -- checked and parsed (if present) by
        circle_audit_lock_take() to detect a concurrent run.
        Every `*/TRANSACTION` file under `work/nightly/` (TRANSACTION_CLASS.py's
        staging root) -- checked by circle_audit_transaction_verify()/circle_audit_transaction_command_read() via
        T.transaction_read().
        The `dream/<OT>` git tags -- read (via `git tag -l`) by
        circle_audit_dream_tags_read(), the one definition of which circles inter_circle.py
        has processed.
        `circles/circle_*.md` -- every transcript file, read for its
        filename (phase 1 survey) and, per unprocessed circle, its full
        text (phase 2's backfill.part_spoke_read(), and phase 3's backfill prompt
        construction).
        `parts/<part>/short_term_<ot>.toml` (`.md` before 2026-09-04, R434)
        -- checked for well-formedness per speaking part per unprocessed
        circle, in phase 2 and phase 3.
        `parts/<part>/long_term.md` (`part_relationships.toml` too, until
        that register retired 2026-08-22) and the fixed set of `self/*.md`
        files (per ifs_model.SELF_FILES)
        -- read wholesale during a snapshot (circle_audit_snapshot()) and during
        invariant checking (record_tree_compare()/record_tree_verify(), called from
        phase 6).
        `<baseline>/SNAPSHOT.json` -- read by circle_audit_window_describe() when a
        `--baseline` was given, to determine whether inter_circle.py
        processed any circle in the window since the snapshot was taken.
        `.env` (project root) -- read opportunistically inside circle_audit_phase3_run()
        if `ANTHROPIC_API_KEY` is not already set in the environment.
        `work/circle_audit/baseline_*` directories -- listed (not read as
        files) by circle_audit_baseline_resolve() and circle_audit_baselines_prune().

    Written
        `work/circle_audit/.lock` -- written by circle_audit_lock_take() at the start
        of every non-selfcheck run, removed by circle_audit_lock_release() when the run
        ends (successfully or via the `finally` block).
        `<snapshot dest>/**` and `<snapshot dest>/SNAPSHOT.json` -- the
        full copied memory-file tree plus a manifest of the snapshot
        itself, written only when `--snapshot` is given.
        `work/circle_audit/baseline_*` (old ones) -- deleted by
        circle_audit_baselines_prune() when `--prune-baselines` is given.
        `work/nightly/<run_id>/staging/*` and associated transaction file/rollback
        bookkeeping under `work/nightly/<run_id>/` -- written by the
        Transaction object during --backfill/--stage-synthetic staging
        and, if --commit is given, during the phase 7 commit swap.
        The live tree's `parts/<part>/long_term.md` etc. -- written ONLY
        during phase 7 (inside circle_audit_phase7_9_run(), called only when --commit was
        given and phase 6 validation found no FAILures), via the
        Transaction's atomic swap.
        `work/nightly/<run_id>/committed.json` -- written by
        Transaction.record_committed() after a successful phase 7 commit.
        `work/logs/circle_audit.log` -- one summary line appended per
        run, via circle_audit_run_log(), near the very end of every non-early-return
        path through main().
        `work/logs/circle_audit_<timestamp>.log` -- the full mirrored
        output of the run, written incrementally by the Tee class, only
        when `--log` was given.
        `.gitattributes`, `.gitignore`, and git's own config/hooks/index
        -- modified idempotently by `gitrepo`'s ensure_* functions during
        `--git-setup` (and, for the config/attributes/hooks/ignore setup
        specifically, also as part of every phase 0 preflight's
        circle_audit_git_verify() call path when may_commit is relevant).

## NETWORK ACCESS

Only inside phase 3 (`--backfill`, without `--dry-run`): one API request per part-needing-backfill, via `llm_client.stream_call_once()`, using `llm_client.MODEL` and a 16,000-token ceiling (`BACKFILL_MAX_TOKENS`). No other phase, flag, or code path makes a network call; git operations are all local. It went through the transport on 2026-08-28 (stage 1 of the provider socket) — this file previously built its own `Anthropic()` client, so a backfill rode no retry ladder and reached no meter. It is also the one caller whose `system` is a LIST OF BLOCKS rather than a string, being the only one that assembles a real part prompt.

## HUMAN I/O

No input is read from stdin. Output is extensive and printed throughout every phase via `print()`, `Run.ok()/warn()/fail()`, and the `circle_audit_hr_render()` section-header helper; when `--log` is given, all of it is additionally mirrored to a timestamped log file via the `Tee` class. A one-line append to `work/logs/circle_audit.log` records the mode/result/detail of every run near the end of `main()`. Exit codes: `0` on a clean run (or an early, successful `--snapshot`/dry-run path); `1` if any check recorded a failure, if phase 0 preflight failed for any non-transaction file reason, or if most subcommand handlers (`circle_audit_git_setup`, `circle_audit_transaction_command_read`) themselves recorded a failure; `2` specifically when phase 0 failed because of a leftover commit transaction file, signaling that a human decision is required before anything else can safely run.

## OPERATION

### `circle_audit_hr_render(title)`

    { Print a title framed by a line of 72 dashes above and below, used
      throughout the script as a section header for each phase's output. }

### `class Run`

    { A simple accumulator: `.ok(msg)` and `.warn(msg)` print an "OK "/
      "WARN" line; `.fail(msg)` prints a "FAIL" line and additionally
      appends `msg` to `self.failures`, the list every phase function
      shares and appends to, so a single Run object tracks every failure
      across an entire invocation without any one phase needing to stop
      the others. }

### `git(*args)`

    { A thin shell over gitrepo.system_git_run(*args, read_only=True) since
      2026-08-19 (review, tier 5 #45) — the subprocess mechanics were a
      hand-rolled duplicate that had drifted (30s vs run()'s 120s
      timeout; raised GitError vs this module's rc-tuple contract). One
      owner now; only the contract is adapted here. }
    if (gitrepo.system_git_run raises GitError — git missing, or killed at run()'s
    120s timeout) then {
        return exit code 127 and the error text as output.
    } else {
        return the process's actual exit code and combined output.
    }

### `circle_audit_git_setup(run, name, email)`

Idempotent git bootstrap; the docstring states everything it does is routine and reversible, safe to re-run at any time since it only ever adds what's missing.

    if (git is not available on PATH) then {
        log a failure and return 1.
    }
    Log git's version.
    if (system_git_repo_ensure() fails, OR system_git_remote_refuse() reports a remote that
        could take this material off the machine) then {
        return 1 -- either the repo could not be initialized/verified
        isolated, or a remote is present that this material must not
        reach.
    }
    Log that no remote can take this material off the machine. A remote
    on a local fixed or removable volume -- a second-disk backup -- is
    permitted and system_git_remote_refuse() has already reported it by name with
    the reason it passed (R130, 2026-08-10).
    Run system_git_config_ensure(), system_git_attributes_ensure(), system_git_hooks_ensure(),
    system_git_ignore_ensure(), and system_git_ignored_untrack() in sequence -- each is
    independently idempotent per gitrepo.py's own contracts.

    Check the working tree's dirty status.
    if (nothing is dirty) then {
        log that the tree is clean, nothing to commit.
    } else {
        print up to 20 dirty paths (plus a remainder count), and print an
        explanation that staging the WHOLE tree is a deliberate human
        judgment this script will not make on its own -- only automated
        runs' own output paths are ever auto-committed -- along with the
        exact `git add -A && git commit` command to run by hand.
    }
    return 1 if any failures were logged, else 0.

### `circle_audit_git_verify(run, may_commit)`

Verifies git preconditions, but only enforces them as hard failures when the run could actually write to the live tree; a read-only run downgrades every check to a warning instead, since git is only needed here as the revert target for a write.

    Determine `level` as run.fail if may_commit else run.warn.
    if (git --version fails) then {
        level("git unavailable -- there is no revert target") and return.
    }
    Log the git version as OK.
    if (this is not a git repository) then {
        level(pointing at the NIGHTLY_DESIGN.md §6 bootstrap) and return.
    }
    Delegate to gitrepo.system_git_remote_refuse(), mapping its log kinds onto
    run.fail / run.ok. Each remote that stays on this machine is logged
    OK with the reason; each that could take the material off it is a
    run.fail, unconditionally, regardless of may_commit -- this
    repository holds private material.

    ONE CLASSIFIER, NOT TWO. This block held its own inline `git remote`
    check until 2026-08-10 and would have drifted from gitrepo.py's the
    moment either changed. If gitrepo.py is not importable that is
    itself a failure, never a pass.
    if (git status --porcelain fails) then {
        level(the failure) and return.
    }
    if (the working tree is clean) then {
        log OK and return.
    }
    Parse each dirty line's path (slicing past the two-character porcelain
    status column, correct for every status-column shape git produces).
    Split paths into `expected` (matching AUDIT_OUTPUT_RE -- exactly
    what an audit run is allowed to have left uncommitted: short_terms
    and the synthetic observation-log append) and `other`.
    if (there are expected paths and no other paths) then {
        log OK: the tree is dirty only in the audit's own output -- the
        expected state after an uncommitted backfill.
    } else {
        level(a message distinguishing "N path(s) outside the audit's
        output set" from any expected paths mixed in) and print up to 10
        of the unexplained paths.
    }

### `circle_audit_dream_tags_read()`

    { List the dream/<OT> git tags via the read-only git() helper. On a
      git failure, return ([], the error text) rather than a bare empty
      list -- an empty answer read as "nothing processed" would report
      every circle unprocessed because git hiccuped (the same lesson
      inter_circle.circle_is_processed() carries, pointed the other way).
      On success, return (the sorted OT list, None). }

### `circle_audit_open_verify(run, writing)`

Refuses to let a snapshot be taken while a circle may be open — /close's phase 2 (inter_circle.py) dreams and commits synchronously inside the close, so a snapshot taken mid-circle captures a tree that is neither cleanly before nor after — meaningless as a comparison baseline, but in a way that looks like real findings rather than an obviously broken result. Replaces the RETIRED `check_cowork_nightly` guard, the manifest-watching check for the scheduled task R228 removed.

    Ask circle_state.circle_is_in_progress() (which fails closed).
    if (no circle is in progress) then {
        log OK and return.
    } else if (`writing` is true) then {
        run.fail -- refuse outright; wait for /close to finish.
    } else {
        run.warn -- flag it, but do not block a read-only run.
    }

### `circle_audit_transaction_verify(run)`

    { Find every leftover commit transaction file via T.transaction_read(). }
    if (none found) then {
        return False (nothing to resolve).
    } else {
        for each transaction file found:
            run.fail, naming it as evidence a previous commit was
            interrupted mid-swap.
            try to read and tally its per-file states (old/new/other);
            if unreadable, print the error and continue to the next
            transaction file.
            print the tally and any file not in a clean "old"/"new"
            state.
        print instructions for the three transaction-repair commands
        (--transaction-status/--transaction-finish/--transaction-rollback).
        return True -- the caller (circle_audit_phase0_run) must stop here.
    }

### `_logger(run)`

    { Return a closure `log(kind, msg)` that prints a marked line (OK/
      DID/WARN/note/FAIL) and, if kind is "fail", also appends `msg` to
      `run.failures` -- a slightly differently-formatted twin of the
      marks used inline in circle_audit_git_setup(), reused by circle_audit_transaction_command_read() and
      circle_audit_phase7_9_run(). }

### `circle_audit_transaction_command_read(run, action)`

    Find every leftover transaction file.
    if (none found) then {
        log OK: nothing to resolve. Return 0.
    } else {
        for each transaction file:
            Parse and print its creation time and per-file states.
            if (the transaction file does not parse — T.transaction_report raises
            ValueError with repair guidance, 2026-08-19) then {
                run.fail with that message, continue to the next transaction file
                (still reporting the others), and the final return is 1 —
                never a raw traceback out of the diagnostic itself.
            }
            if (action == "status") then {
                continue to the next transaction file without acting.
            } else {
                if (action == "finish") then { call T.transaction_finish(). }
                else { call T.transaction_rollback(). }
                if (that call reports failure) then {
                    return 1 immediately.
                }
            }
        return 1 if any failures were logged, else 0.
    }

### `circle_audit_lock_take(run)`

    Ensure the work/circle_audit/ directory exists.
    if (a lock file already exists) then {
        try to parse it for the holding pid and start time; on any
        parse failure, treat its age as older than the staleness
        threshold (forcing a takeover).
        if (its age is under LOCK_STALE_SEC, 6 hours) then {
            run.fail naming the holding pid and age, and return False.
        } else {
            run.warn that the stale lock is being taken over.
        }
    }
    Write a fresh lock file recording this process's pid, start time,
    and argv. Return True.

### `circle_audit_lock_release()`

    { Delete the lock file ONLY if it records this process's own pid;
      a lock held by another pid is left untouched, and a lock that
      does not parse is left for circle_audit_lock_take()'s staleness takeover.
      Any OSError (e.g. it's already gone) is silently ignored.
      Ownership-checked since 2026-08-19: main()'s phase-0 failure
      path calls this, so a run that LOST the lock race used to delete
      the winning run's live lock on its way out. }

### `circle_audit_phase0_run(run, may_commit, writing=False)`

    Print the phase 0 header.
    if (circle_audit_transaction_verify() reports a leftover transaction file) then {
        return False immediately -- nothing else in phase 0 or beyond
        runs.
    }
    if (circle_audit_lock_take() fails to acquire the lock) then {
        return False immediately.
    }
    Run circle_audit_open_verify() and circle_audit_git_verify() (both accumulate into
    `run` rather than short-circuiting).
    if (coordinator/record_verify.py does not exist) then {
        run.fail.
    } else {
        Run it as a subprocess; log its last non-blank output line as
        OK or FAIL depending on its exit code, and if it failed, also
        print every line of its output containing "FAIL".
    }
    Return True if `run.failures` is still empty, else False.

### `circle_audit_phase1_run(run)`

Unprocessed = in scope and carrying no dream/<OT> tag. The scope epoch is the oldest dream tag: circles older than it are the retired batch nightly's era, out of audit scope by ruling (2026-08-19). Deleting the oldest tag — inter_circle's own "delete the tag first if you mean it" re-run path — therefore shifts the epoch backward and pulls legacy circles into scope.

    Get the processed OT set from circle_audit_dream_tags_read().
    if (circle_audit_dream_tags_read reported a git error) then {
        run.fail (survey refused -- guessing would report every circle
        unprocessed) and return an empty list.
    }
    List every circle_*.md transcript's open-time id, sorted.
    if (no dream tags exist at all) then {
        run.warn: inter_circle.py has processed nothing yet; every
        circle on disk predates it and is out of scope. Return [].
    }
    Split circles at the epoch (the oldest tag): `legacy` before it
    (reported as out of scope, with a count), `inscope` at or after it.
    Compute `unprocessed` as every in-scope circle whose id is not in
    the processed set.
    if (none are unprocessed) then {
        run.ok: every in-scope circle carries its dream/<OT> tag.
    } else {
        run.ok, reporting the in-scope and unprocessed counts, naming
        inter_circle.py's --ot re-run entry point, and printing each
        unprocessed circle's filename.
    }
    Return the list of unprocessed circle ids.

### `spoke_in` — MOVED to backfill.py as `part_spoke_read(transcript)` (B54, 2026-08-19)

    { Read the given transcript file as text (returning an empty dict on
      any OSError). For each line matching STATEMENT_RE (a bracketed
      part-tag, optionally followed by a "[To: ...]" addressee, then a
      colon), map the tag to its directory name via roster.DIR_BY_TAG and
      increment that part's count. Return the per-part statement-count
      dict. }

### `circle_audit_phase2_run(run, unprocessed)`

Reconciles each unprocessed circle against `circle_close_verify.py`, then applies what the docstring calls "the transcript safety net": any part that spoke in the transcript but has no well-formed short-term record must be backfilled before dreaming would otherwise read it as having said nothing at all. A part that stayed silent is correctly exempt -- absence for a part that never spoke is not a loss.

    if (there is nothing unprocessed) then {
        run.ok and return immediately.
    }
    for each unprocessed circle, in order:
        Run coordinator/circle_close_verify.py --reconcile --open-time <ot> as a
        subprocess; print its non-empty output lines (except lines
        starting with "Circle-close").
        if (it exited non-zero) then {
            run.fail: RECONCILE-DRIFT -- the short-terms recorded at
            close are absent or changed on disk; phase 3 must backfill
            them.
        }

        Determine which parts spoke in this circle's transcript via
        backfill.part_spoke_read().
        if (no parseable statements were found at all) then {
            run.fail and continue to the next circle.
        }
        for each part that spoke, sorted:
            Check its short_term_<ot>.toml (.md before 2026-09-04, R434) via
            ifs_model.record_file_verify().
            if (the file could not be read at all) then {
                record it as needing backfill, with the first finding's
                message (or "missing") as the reason.
            } else if (any of the four required section headings is
                absent from it) then {
                record it as needing backfill, reason "malformed (no
                '<first missing section>')".
            }
        if (anything needs backfill) then {
            run.fail once per part, naming how many times it spoke and
            why its record is unusable.
        } else {
            run.ok: every speaking part has a well-formed short_term.
        }
        Print, informationally, which known parts stayed silent this
        circle (correctly having no short_term).

### `circle_audit_snapshot(dest)`

    { Create `dest`. Copy every file returned by register_gate._tree_files()
      (each part's long_term.md — part_relationships.toml too, until that
      register retired 2026-08-22 — plus every fixed self/ file) into
      `dest`, preserving relative structure, counting
      files copied. Additionally copy every self/narrative_*.md file
      (not part of the fixed _tree_files() set). Record the snapshot's
      position in the circle stream (the latest dream/<OT> tag, or the
      git error that hid it, and whether a circle may be in progress)
      and write it, along with the file count, timestamp, and a sha256
      of every copied .md file, to dest/SNAPSHOT.json. Return dest. }

### `circle_audit_window_describe(run, baseline)`

States plainly whether inter_circle.py actually processed a circle between when a snapshot was taken and now — the docstring is explicit that "no differences" means two very different things depending on the answer, and only one of them is good news.

    if (baseline/SNAPSHOT.json does not exist) then {
        run.warn: cannot tell whether any circle was processed since
        this snapshot, and return.
    }
    if (it exists but fails to parse) then {
        run.warn with the parse error, and return.
    }
    Read the snapshot's recorded latest dream/<OT> tag (`then`) and get
    the CURRENT latest tag (`now`) via circle_audit_dream_tags_read(); a git error now is
    a run.warn ("the window below is unknown") and an early return.
    Print both, plus when the snapshot was taken.
    if (the snapshot recorded a dream_tag_error of its own) then {
        run.warn: the snapshot's baseline position is unknown.
    }
    if (the snapshot recorded a circle possibly in progress when it was
        taken) then {
        run.warn: this snapshot is neither a clean before nor after;
        take a fresh one.
    }
    if (`now` equals `then`) then {
        run.warn: inter_circle.py has processed NO circle since this
        snapshot, so any "unchanged" result below is trivially true and
        proves nothing.
    } else {
        run.ok: processing advanced in this window, so the comparison
        that follows is meaningful.
    }

### `circle_audit_phase6_run(run, baseline)`

    Print the phase 6 header, naming the baseline path if given, else
    "(self-check)".
    if (a baseline was given) then {
        call circle_audit_window_describe() and print a blank line.
    }
    if (a baseline was given) then {
        findings = register_gate.record_tree_compare(baseline, ROOT).
    } else {
        findings = register_gate.record_tree_verify(ROOT).
    }
    for each finding:
        if (its level is not OK, OR a baseline was given at all) then {
            print it -- i.e. in self-check mode, only non-OK findings
            are printed, but in baseline-compare mode every finding
            (including OK ones) is printed.
        }
    Tally FAIL/WARN/OK counts and print the summary line.
    Append every FAIL finding's path and code to `run.failures`.
    if (this was a self-check AND there were any WARNs) then {
        print two clarifying notes: a RECENCY-DERIVED warning is not
        itself a problem (an entry with no explicit "Last mentioned"
        anchors to its own dream date), and a TOMBSTONE warning means an
        entry's body was lost while its header survives.
    }

### `circle_audit_short_terms_missing_read(unprocessed)`

    { For each unprocessed circle, for each part that spoke in it (via
      backfill.part_spoke_read()), check its short_term_<ot>.toml (.md
      before 2026-09-04, R434) via
      backfill.short_term_verify(). If any FAIL-level finding resulted,
      add (ot, part, spoken-count) to the output list. A part that never
      spoke in that circle is never considered -- its absence is
      correct, not a loss. Return the accumulated list. }

### `circle_audit_phase3_run(run, tx, unprocessed, dry)`

Reconstructs lost short-term records directly from a circle's transcript, staging the result rather than writing it — mechanizing a procedure the docstring says was previously done by hand for four parts on 2026-07-26, under the same rule: only `short_term_*.toml` (`.md` before 2026-09-04, R434) is ever written here, never `long_term.md` (and never `part_relationships.toml`, while that register existed — retired 2026-08-22).

    Find everything needing backfill via circle_audit_short_terms_missing_read().
    if (nothing needs it) then {
        run.ok and return 0.
    }
    for each (ot, part, n) needing backfill:
        run.warn, naming the part, circle, and how many times it spoke
        with no usable record.
    if (`dry` is true) then {
        print the count that WOULD be generated and an estimated dollar
        cost, and return 0 without calling the model.
    }

    Import circle (as C) and the anthropic package locally.
    if (ANTHROPIC_API_KEY is not already set in the environment) then {
        try to load it from a project-root .env file via python-dotenv;
        tolerate the import failing if the package isn't installed.
    }
    Create an Anthropic client and load the shared prompt context once
    (C.group_shared_read()).

    for each (ot, part, n) needing backfill:
        Assemble that part's system prompt exactly as a live circle
        would (C.prompt_part_assemble(part, core, briefing) — the retired
        `shared_block`/`system_blocks` pair became that one call, 2026-09-02).
        Read the full transcript text for this circle.
        Send one message: the transcript plus the fixed BACKFILL_PROMPT
        (which asks for the four short-term sections, grounding "What I
        said"/"What I observed in others" in the actual transcript and
        leaving "Shifts"/"Current emotional state" to the model's own
        judgment), capped at BACKFILL_MAX_TOKENS (16,000) output tokens.
        Extract the response's text.
        if (the response was truncated at the token cap, OR the
            extracted text is empty) then {
            run.fail, naming the stop reason, output token count, and
            character count -- an inline comment explains this model
            can consume its whole token ceiling on internal "thinking"
            before producing any visible text, so a reply can come back
            completely EMPTY rather than visibly truncated; this was
            observed for real on 2026-07-27 with an 8,000-token ceiling.
            Nothing is staged for this part; continue to the next one.
        } else {
            Build the file's header (noting it was backfilled by
            circle_audit.py because the original close-write was lost)
            plus the model's body text.
            Check the assembled text via backfill.short_term_verify().
            if (any FAIL-level finding resulted) then {
                run.fail: the regenerated record is itself malformed;
                continue to the next part without staging.
            } else {
                stage the file into the transaction, run.ok with a word
                count, and count it as done.
            }
        }
    Return the count of parts successfully staged.

### `circle_audit_synthetic_stage(tx, run)`

One legal synthetic change, used to exercise the real tree, the real gate, and the phase 6-9 plumbing end-to-end with no model calls and no cost. ONE legal file since 2026-08-19 (review tier 2 #17): it used to also stage a fake [[dreams]] record, written before the register gate saw TOML — the gate then declared parts/*/dreams.toml FROZEN (R178), so the synthetic staging became a guaranteed phase-6 FAIL and --stage-synthetic could never reach phases 7-9 at all. The multi-file swap and both transaction file repairs are covered by coordinator/tests/test_TRANSACTION_CLASS.py against throwaway trees.

    {
        Read the self-observation log and stage it with one synthetic
        line appended.

        run.ok, reporting how many synthetic files were staged.
    }

### `circle_audit_phase7_9_run(run, tx, findings, do_git)`

Phases 7 (commit), 8 (verify), 9 (record) — the docstring notes explicitly that nothing here runs at all if phase 6 already found a FAILure.

    if (any finding is FAIL-level) then {
        run.fail: refusing to commit; the live tree is untouched and
        staging is kept for inspection. Return False.
    }
    Determine which staged files actually differ from the live tree
    (tx.changed()).
    if (nothing differs) then {
        run.ok: staged output is identical to what's already live --
        nothing to commit. Return True.
    }

    Print the phase 7 header and the list of files to be replaced.
    if (tx.commit() reports failure) then {
        return False.
    }
    Record which paths were committed (tx.record_committed()).

    Print the phase 8 header.
    if (tx.verify() -- a re-read-from-disk comparison against what was
        meant to be written -- reports failure) then {
        run.fail: post-commit verification failed, see the rollback
        copies. Return False.
    }

    Print the phase 9 header.
    if (`do_git` is true) then {
        commit exactly the changed paths to git (gitrepo.system_git_paths_commit()),
        tagged audit/<run_id>.
    } else {
        run.warn: committed to disk but not to git (--no-git was given).
    }
    Log the run as a successful commit. Return True.

### `circle_audit_baseline_resolve(arg)`

    if (`arg` is falsy) then {
        return None.
    } else if (`arg`, lowercased, is "last"/"latest"/"auto") then {
        find every work/circle_audit/baseline_* directory, sort by name
        (which sorts chronologically given the timestamp-based naming),
        and return the newest one, or None if none exist.
    } else {
        return `arg` treated directly as a path.
    }

### `circle_audit_baselines_prune(keep=KEEP_BASELINES)`

    { Sort every baseline_* directory by name, keep the newest `keep`
      (14 by default), and delete the rest (ignoring errors during
      deletion). Return the count deleted. }

### `class Tee`

    { On construction, open the given log file path for writing (LF
      newlines) and register self.close via atexit -- the comment notes
      main() has too many return paths to guard each one individually.
      `.write(s)` writes to both the original stdout and the log file;
      `.flush()` flushes both; `.close()` closes the log file. }

### `circle_audit_run_log(mode, result, detail)`

    { Append one fixed-width line (timestamp, mode, result, detail) to
      work/logs/circle_audit.log, creating its parent directory if
      needed -- one line per run, so a week of audit runs can be read
      at a glance. }

`install_tasks`/`uninstall_tasks`/`TASK_XML`/`TASKS`/`task_defs` — REMOVED WHOLESALE
2026-08-15, code included. They registered/removed the two Windows Task Scheduler jobs that
snapshotted before and validated after the separate, since-retired `ifs-nightly` Cowork task.
See `rulings/` and `docs/NIGHTLY_DESIGN.md`'s own §7 retirement note: nothing schedules
dreaming/synthesis any more (`docs/INTER_CIRCLE_DESIGN.md`'s Placement ruling — synchronous
at `/close`).

## BUGS

- **RESOLVED 2026-08-27.** Honoured rather than deleted, because the module ships: selecting the default path explicitly, and refusing a combination that would silently override it, makes the help text true without removing a documented flag from a shipped CLI. Verified both ways — `--validate` alone runs the default sequence to "all checks passed"; `--validate --backfill` and `--validate --commit` each refuse by name and return 1. The record of the defect follows.

  `--validate` was defined as a documented argparse flag ("run phases 0, 1, 2, 6 (the default)") but `main()` never read `args.validate` anywhere in its dispatch chain — `grep -n "args.validate" coordinator/circle_audit.py` returns nothing. Running with no flags at all already falls through to exactly that phase sequence, so `--validate` is a no-op that changes nothing whether given or not. The flag's own help text implies it selects a mode; every unhandled combination of flags reaches that same code path regardless.

  This one reaches users: `coordinator/circle_audit.py` is listed file-by-file in `packaging/required.toml`, so the dead flag ships in the export bundle and its help text is read by people who did not write it.

  Worse than decoration, and this is the part the original entry missed: `--validate --backfill` ran the BACKFILL. The flag did not merely do nothing — it LOST, silently, to whichever other flag was present.

- WITHDRAWN 2026-08-27 — the `NameError: unprocessed` reported here. **It cannot occur, and the mechanism it was reasoned from does not exist.** The block is `try:` / `finally: circle_audit_lock_release()` with *no* `except` clause, so an exception raised anywhere inside the `try` runs `finally` and then propagates out of `main()`; the failure-summary line sits *after* the whole construct and is never reached on that path. The claim also placed the `--transaction-*`/`--git-setup`/`--selfcheck` early returns inside the `try` — all three are above it. On every path that does reach the summary line, `unprocessed = circle_audit_phase1_run(run)` has run: the only branch between the `try` and that assignment is `--snapshot`, which returns 0.

- WITHDRAWN 2026-08-27 — "the distinction ... is not made anywhere in the message". The premise is right: `circle_audit_phase0_run()` does call `circle_audit_git_verify()` before phase 7, so a matched path can only be a prior run's leftover. The conclusion is wrong — `circle_audit_git_verify()` says exactly that. Its `expected and not other` branch prints *"working tree dirty in N path(s), all of them audit output — the expected state after an uncommitted backfill. Review, then commit."* Naming the leftover as a prior uncommitted backfill IS the distinction the entry reported missing.
