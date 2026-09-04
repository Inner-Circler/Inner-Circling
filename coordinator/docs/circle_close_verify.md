# CIRCLE_CLOSE_VERIFY(1)

## NAME

circle_close_verify.py (circle_close.py until 2026-09-03) — the close verifier: proof that every part that spoke left a record, and that the record is still there afterwards.

## SYNOPSIS

    python coordinator/circle_close_verify.py --reconcile --open-time YYYY-MM-DD_HHMM
    python coordinator/circle_close_verify.py --short-term-only --open-time YYYY-MM-DD_HHMM
                                       [--write-report]
    python coordinator/circle_close_verify.py
    python coordinator/circle_close_verify.py --prune
    python coordinator/circle_close_verify.py --claude-home /path/to/.claude

## DESCRIPTION

At the end of a circle, every part that spoke writes a short note about what the circle was for it. That note is the part's own account, and it is the thing a later stage reads when the part dreams. **A part that spoke but lost its note is invisible, not noisy** — the dreaming stage reads a missing file as a part that had nothing to say, which is a legal outcome, so nothing fails and that part's sense of itself simply does not move. This module is what makes that loss visible.

It runs in two live modes, both invoked for you rather than by hand in the ordinary course of things:

    --short-term-only --write-report   at every live close. Checks each speaking
                                       part's note and writes work/logs/close_<OT>.json
                                       recording its size and sha256 — the durable
                                       manifest of what existed at close.
    --reconcile --open-time <OT>       the audit's guard, run BEFORE dreaming. Re-reads
                                       those notes from disk and compares them to the
                                       manifest.
    --postcondition [--open-time <OT>] the report read as a POSTCONDITION (R368).
                                       Re-derives who spoke from the transcript the
                                       report names and holds the report to what it
                                       claimed. Read-only, no --open-time needed.

The second exists because of a specific failure shape: a write that succeeds at close and is gone by the time anything reads it, because the store it landed on had not flushed. Without a manifest that is indistinguishable from a part that never wrote. With one, it is caught as a **named absence against a known expectation** and the part is backfilled from the transcript instead of being read as disengaged. That is the exact "clean close, empty aftermath" contradiction this closes.

**By hand, the one you would type is the reconcile:**

    python coordinator/circle_close_verify.py --reconcile --open-time 2026-08-09_1520

**`--reconcile` and `--postcondition` ask different questions of the same file, and both are worth asking.** The reconcile asks whether what the report recorded is STILL on disk — a durability question about the time since the close. The postcondition asks the prior one: **was the report a true statement about the close when it was written?** It re-derives who spoke through `parts_that_spoke()` — the one reader of a transcript's speaker tags, never a second regex — and checks the report against that: every count agreeing, every speaking part having a row at all, `result` agreeing with `missing`, `missing` agreeing with the `present` flags, and every present row carrying the digest the reconcile will later need. The rules and their prose live in `coordinator/close_contract.toml`; `coordinator/tests/test_close_postcondition.py` breaks one thing at a time and asserts each still refuses.

**Three dispositions, all derived, none of them an exemption.** A transcript older than the OLDEST close report predates close reporting and is out of scope — the same rule `circle_audit.py` uses for `dream/<OT>` tags. A SANDBOX report is a different artefact in a different shape and is noted. And a `parts/` directory RENAMED since the close (`injured_soul` became `soul`; eight reports carry the older name and were true when written) is paired back to its speaker by statement count and noted — pairing only suspends the two NAME-based rules, and a row whose count matches nothing still fails.

**It refuses to read `circles/` while a circle may be open.** `circle_state` fails closed and a partial transcript is well-formed, so a mid-circle sweep would report disagreements that are only an in-flight circle.

**A note counts as present only if it is well formed.** Present, non-empty, and carrying all four of its sections. A file that exists but is half-written is a failure, not a pass.

**The short-term check fails closed.** If the transcript cannot be resolved at all, it fails rather than passing with nothing verified — a stale mount making a transcript unreadable used to produce a vacuous success, which is the false clean close in its purest form.

**Silent parts are exempt.** A part that never spoke is not expected to write anything.

**Some of this file is vestigial, and is kept deliberately.** The team-state checks and `--prune` belong to a retired runtime in which parts were separate processes that had to be torn down. Circles are now one local process making direct calls, so there are no teammates to shut down and no leftover state to orphan. Those checks are self-skipping when their subject is absent, and a tree archived from that era still verifies against them, so they were kept rather than deleted. Nothing schedules them and no live path runs them.

## MAIN

    Parse the arguments.

    if (--reconcile) then {
        if (no --open-time was given) then { FAIL — it is required; return 1. }
        if (there is no close report for that open time) then {
            WARN that the circle predates close-report logging, and return 0 —
            there is nothing to reconcile against.
        }
        if (the report cannot be read or parsed) then { FAIL; return 1. }
        FOR EACH part the report recorded as present at close:
            Re-read the note from disk and take its size and sha256.
            if (it is absent now) then { print MISSING and record drift. }
            else if (either size or hash differs) then { print DRIFT with both
                the recorded and the current values, and record drift. }
            else { print OK. }
        if (anything drifted) then {
            print "RECONCILE-DRIFT: <parts>" — a line built to be parsed —
            then a failure line saying to backfill the named parts from the
            transcript BEFORE dreaming; return 1.
        }
        print RECONCILE PASS and return 0.
    }

    if (--short-term-only) then {
        Resolve the transcript: by --open-time exactly if given, otherwise by
            today's date — which warns and refuses if today has more than one.
        if (no transcript could be resolved) then {
            FAIL rather than pass; return 1.
        }
        FOR EACH part that spoke in the transcript:
            Check its note; record size and sha256; collect any that are missing
            or malformed.
        if (--write-report) then { write work/logs/close_<open time>.json. }
        Report, and return 1 if any speaking part's note is missing or malformed.
    }

    otherwise run the legacy teardown checks against whatever remains after any
    --prune, and delete every parts/*/statement_temp.md unconditionally.

## COMMAND-LINE ARGUMENTS

    --reconcile         re-read the notes and compare to the close report. Requires
                        --open-time. Default: off.
    --short-term-only   run only the note check, skipping every teardown check,
                        --prune and the temp-file deletion. Default: off.
    --write-report      with --short-term-only, also write work/logs/close_<OT>.json.
                        Default: off.
    --open-time         the circle's open time, YYYY-MM-DD_HHMM. Without it the
                        transcript is guessed from today's calendar date, which is
                        wrong for a circle that opens before midnight and closes
                        after it. Default: unset.
    --prune             delete leftover team directories and their matching task
                        directories before checking. Vestigial. Default: off.
    --claude-home       override the location of ~/.claude, for testing.
                        Default: the real one.
    --root              the project root. Default: this checkout.
    --max-members       the bloat threshold for the vestigial team check.

## EXIT CODES

    0   clean — every part that spoke wrote a well-formed note, and (in reconcile)
        every note recorded at close is still intact on disk.
    1   action needed — a speaking part's note is missing or malformed, the
        transcript could not be resolved, or the durable store has diverged from
        what close recorded.

## DEPENDENCIES

`roster` for the mapping from a transcript tag to a part's directory. `argparse`, `hashlib`, `json`, `os`, `shutil`, `sys`, `collections`, `datetime`, `pathlib`.

## EXTERNAL FILES

    circles/circle_<OT>.md            READ — who spoke, and how many times
    parts/<name>/short_term_<OT>.toml READ — the note being verified (.md before 2026-09-04,
                                      R434; found by short_term_manager.short_term_locate,
                                      either suffix). The report row records the REAL name
                                      hashed as `file`; --reconcile re-hashes by it and falls
                                      back to the .md for a report written before the key
    work/logs/close_<OT>.json         WRITTEN by --write-report; READ by --reconcile
    parts/*/statement_temp.md         DELETED unconditionally in the legacy path
    ~/.claude/teams, ~/.claude/tasks  READ, and deleted under --prune. Vestigial.

The close report is written with explicit newlines rather than the platform default, because it is a durability record under version control and should not change shape depending on which machine wrote it.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout; reads no input. Standard output is reconfigured to UTF-8 with replacement on import — a check that dies formatting its own PASS message reports a failure that is not there, which is how three suites once read as broken for a week.

## OPERATION

### parts_that_spoke(transcript)
Reads the transcript and counts statements per part by matching each line's speaker tag. An unreadable transcript yields nothing rather than raising.

### short_term_status(path)
    if (path is None or the file does not exist) then { return (false, "missing"). }
    if (it cannot be read) then { return (false, the error). }
    if (it is blank) then { return (false, "empty"). }
    if (it does not parse through short_term_manager — a broken .toml) then {
        return (false, "malformed (does not parse ...)").
    }
    if (any of the four required sections is absent OR EMPTY) then {
        return (false, "malformed", naming which. )
    }
    otherwise return (true, "").
Empty counts since B96: a heading with nothing under it is the record B54 exists for.

### record_file_digest(path)
(`file_digest()` before the B99 re-homing, 2026-09-03.)
Size and sha256, or nothing at all if the file is absent or unreadable.

### circle_close_report_write(root, ot, transcript, records, missing)
(`write_close_report()` before the B99 re-homing, 2026-09-03.)
Writes the manifest: the open time, when it was checked, the transcript it verified against, pass or fail, the parts that were missing, one record per speaking part, and a note stating plainly that the hashes are the close-time on-disk view and that the later reconcile re-reads the durable store.

### circle_transcript_resolve(circles, open_time) (`resolve_transcript()` before the B99 re-homing, 2026-09-03)
    if (an open time was given) then { return that transcript if it exists. }
    otherwise look for today's transcripts.
    if (there is exactly one) then { use it. }
    if (there are several) then { return a warning asking for --open-time. }
    if (there are none) then { return nothing. }

## BUGS

None found. The mode split is unusual enough to note: `--reconcile` and `--short-term-only` return before the legacy teardown path is reached, so those two modes never touch team state, never prune, and never delete a temp file.

## HISTORY

Moved from `scripts/` to `coordinator/` on 2026-08-18. It had sat there since a retired runtime, read as leftover tooling, and was twice assessed as a candidate for archiving — but it is not leftover: it is the close step itself, with two live callers in this same directory. The genuinely general sweep that had been beside it, the corruption check, moved the same day to `check_integrity.py` (`record_verify.py` since 2026-09-03, R435) and became a gate at circle open.
