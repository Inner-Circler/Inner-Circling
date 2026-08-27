# CIRCLE_STATE(1)

## NAME

circle_state.py — is a circle open right now? A conservative test for whether a transcript in `circles/` might still be mid-write.

## SYNOPSIS

    python coordinator/circle_state.py
    from circle_state import is_circle_in_progress

## DESCRIPTION

A circle's transcript is written statement by statement as the circle happens, which is what makes it crash-safe — but it also means a transcript file on disk carries no marker distinguishing "still being written" from "finished." Reading a transcript mid-circle can silently return a partial: the module's own docstring records that on 2026-08-03, a transcript was read in flight and reported as a 12-statement finished circle when it actually closed at 33 statements. The fix that followed was a standing caution in `CLAUDE.md` telling a reader to remember not to read `circles/` while a circle might be open — a rule that depends on someone remembering it every time. This module replaces that caution with a test: rather than asking a reader to remember, it asks the filesystem.

The test is deliberately conservative, and both of its two conditions are required together. A transcript is considered OPEN unless (a) a close report exists for it, confirming the coordinator itself said it finished, or (b) it has gone quiet long enough that no live circle could plausibly still be writing it. Relying on the close report alone would treat an aborted circle (one that crashed or was killed before writing a close report) as open forever. Relying on quiet time alone would risk treating a part's long thinking pause as a finished circle. The quiet threshold used, 45 minutes, is deliberately generous, since a part may take a long time to answer and a Self prompt waits on a human — the cost of waiting an extra cycle is small, while the cost of misjudging a still-open circle as closed is a false record.

The module fails closed: anything it cannot determine — an unreadable directory, a transcript filename that doesn't parse, a file it cannot stat, an unexpected exception of any kind — is treated as "a circle may be open," never as "safe to read." The docstring states this directly: the safe answer to "may I read this?" is no.

## MAIN

    try {
        Call open_circles() to get the list of transcripts that may still
        be mid-write.
    }
    if (open_circles() raised any exception) then {
        print "COULD NOT TELL -- <the exception>" and a instruction to
        treat this as a circle in progress and ask Self.
        return exit code 1.
    } else if (the returned list is empty) then {
        Count every circle_*.md transcript file under both the live
        circles/ directory and the sandbox circles/ directory (regardless
        of open/closed state, purely for the reported count).
        print "NO CIRCLE IN PROGRESS -- <n> transcript(s), all with a
        close report or long quiet. Safe to read."
        return exit code 0.
    } else {
        print "<count> CIRCLE(S) MAY BE OPEN -- do not read, ask Self:"
        for each open transcript found, print its path relative to the
        project root and the specific reason it was judged open (either
        "cannot stat -- failing closed", or "no close report and last
        written <n> min ago").
        return exit code 1.
    }

## COMMAND-LINE ARGUMENTS

None. The script takes no arguments; it is invoked bare either as a shell command (to get a pass/fail exit code and a human-readable report) or imported as a module (to call `is_circle_in_progress()` directly from other Python code).

## DEPENDENCIES

Python standard library only: `pathlib`, `sys`, `time`, plus `from __future__ import annotations`. No sibling/local project modules, no third-party packages, and no external programs are invoked.

## EXTERNAL FILES

    Read
        Every file matching `circle_*.md` directly under two directories:
        the live circles directory (`<project root>/circles/`) and the
        sandbox circles directory (`work/sandbox/circles/`) — read
        only for their filesystem metadata (modification time via
        `stat()`), never their contents. Each candidate file's
        modification time is read unconditionally when that directory
        exists and is scanned.

        `work/logs/close_<OT>.json` — for each transcript found, checked
        only for existence (`is_file()`), once per transcript, to
        determine whether a close report exists for that circle's OT
        (open-time) id. The file's contents are never read, only whether
        it is present.

    Written
        None. The script performs no file writes anywhere in its source.

## NETWORK ACCESS

None. The script makes no network calls of any kind.

## HUMAN I/O

No input is read from stdin; the script's only external input is the filesystem state described above. When run as a script, a report is printed to stdout: either a "safe to read" message with a transcript count, a per-transcript list of reasons a circle may still be open, or (on an unhandled error) a "COULD NOT TELL" message instructing the reader to treat the situation as a circle in progress and ask Self. Exit code is `0` only when no circle appears to be open; `1` both when one or more circles may be open and when the check itself failed and could not determine an answer — the module's fail-closed design means an inconclusive result and a positive result produce the same "do not proceed" signal to a caller checking the exit code alone.

## OPERATION

### Module setup

    {
        If standard output supports it, reconfigure it to UTF-8 with
        character replacement on error, so that a Windows console
        (defaulting to cp1252) degrades instead of crashing when this
        script's em-dashes and arrows are printed -- a crash while
        formatting a status message would itself misreport as a failure
        that isn't real.

        Resolve this file's own directory (HERE) and its parent (ROOT).
        Define LIVE as ROOT/circles, SANDBOX as HERE/sandbox/circles, and
        LOGS as ROOT/work/logs -- the three filesystem locations the rest
        of the module reads. Define QUIET_SECONDS as 45 minutes (45 * 60),
        the threshold past which an unclosed transcript is judged
        abandoned rather than actively being written.
    }

### `_closed(ot)`

    { Return whether a close-report file named `close_<ot>.json` exists
      under LOGS. This is treated as the coordinator's own statement that
      the circle with that open-time id finished -- existence alone is
      checked, not the report's contents. }

### `open_circles(now=None)`

Returns every transcript that may still be being written; an empty list is the "safe to proceed" answer.

    Resolve `now` to the current time if none was given (allows a caller
    to test against a fixed point in time).
    For each of the two candidate directories, LIVE and SANDBOX, in order:
        if (the directory does not exist) then {
            skip it entirely -- no transcripts to consider from it.
        } else {
            for each file matching circle_*.md under it, sorted by name:
                Derive the transcript's OT (open-time) id by stripping the
                "circle_" prefix from the filename's stem.
                if (statting the file to get its modification time raises
                    an OSError) then {
                    add it to the open-list with quiet = -1 and reason
                    "cannot stat -- failing closed" -- an unreadable file
                    is never assumed safe.
                    continue to the next file.
                }
                Compute quiet = now minus the file's modification time.
                if (a close report exists for this OT, per _closed()) then {
                    skip this transcript -- the coordinator itself said
                    it finished, so it is not added to the open list.
                } else if (quiet is at least QUIET_SECONDS, i.e. the file
                    has been untouched for 45 minutes or more) then {
                    skip this transcript -- treated as abandoned, or
                    predating the close-report convention, rather than
                    actively open.
                } else {
                    add it to the open list with its computed quiet time
                    and a reason string: "no close report and last written
                    <n> min ago" (minutes computed as max(0, quiet) / 60,
                    formatted to zero decimal places).
                }
        }
    Return the accumulated list of dicts, each carrying path, ot, quiet,
    and why.

### `is_circle_in_progress()`

    { Public entry point for other modules. Attempt to call open_circles()
      and return True if the resulting list is non-empty (some transcript
      may still be open), False if it is empty. }
    if (calling open_circles() raises any exception at all) then {
        return True unconditionally -- this is the module's fail-closed
        guarantee: any failure to determine the answer is reported as "a
        circle may be open," never as "safe."
    }

## BUGS

- `main()`'s "safe to read" branch reports a transcript count computed independently of `open_circles()`'s own directory-existence checks: it calls `LIVE.glob(...)` and `SANDBOX.glob(...)` directly without first checking `is_dir()` on either. `pathlib.Path.glob()` on a non-existent directory simply yields nothing rather than raising, so this doesn't crash, but if one of the two directories doesn't exist, `open_circles()` silently skips it (per its own `if not d.is_dir(): continue`) while `main()`'s count line still reports as if both were considered — in practice harmless since the count is used only for the printed "safe to read" message, not for any decision.

- `is_circle_in_progress()`'s fail-closed guarantee is easy to lose silently in a caller that only checks the return value and doesn't distinguish it from a genuine "no circle open" case, since both are `False`/`True` with no way to tell an inconclusive check from a confident one from the boolean alone. `main()` avoids this by handling its own `try`/`except` separately with a distinct message, but any other caller of `is_circle_in_progress()` directly gets no such distinction — a caller who logs or acts on the boolean alone cannot tell "confirmed open" from "could not tell, so treated as open."
