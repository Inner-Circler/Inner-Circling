# CIRCLE_OPEN_VERIFY(1)

## NAME

circle_open_verify.py — the open step's verifier: what an open left behind, written down. It reports; it never refuses.

## SYNOPSIS

    (at every open, in-process)  circle_open.circle_open_verifier_run()
    python coordinator/circle_open_verify.py --open-time YYYY-MM-DD_HHMM [--write-report]
    python coordinator/circle_open_verify.py --open-time <OT> --dry-run
    python coordinator/circle_open_verify.py --open-time <OT> --parts judge,mourner
    python coordinator/circle_open_verify.py --open-time <OT> --capture <OT>_resume_1
    python coordinator/circle_open_verify.py --group band --open-time <OT>

`--open-time <OT>`: the circle to check, by its open time. Required.

`--dry-run`: check a sandbox circle — its transcript under `work/sandbox/circles/`, and its report under `work/sandbox/logs/`. Default: off (a live circle).

`--group <name>`: read `groups/<name>/`'s record. Default: unset — the default group.

`--parts <a,b,...>`: the roster the capture must cover. Default: unset — the roster an existing report for this circle recorded; with neither, that one check is not applicable.

`--capture <dir>`: the capture directory's name under `work/prompts/`, for a resumed circle, whose capture is `<OT>_resume_<k>`. Default: unset — `work/prompts/<OT>`.

`--write-report`: also write the report file. Default: off — the command line prints and writes nothing.

Exit 0 when every postcondition passes or does not apply; 1 when one fails. That exit code belongs to the command line alone: the in-process call at every open returns nothing the open acts on.

## DESCRIPTION

When a circle opens, it should leave four things behind: a transcript headed with its own open time, a record of which issues the room was shown, a verbatim capture of the program each part was sent, and that capture covering every part. This module checks all four and writes the answer to one file:

    work/logs/open_<OT>.json            a live circle
    work/sandbox/logs/open_<OT>.json    a dry run

**It reports and never refuses** (R535, 2026-09-10 — *"1 - report only."*). Nothing it finds stops a circle, and three things make that true rather than intended: the open acts on nothing it returns; the call is wrapped, the import included, so nothing it raises reaches the open; and it never calls `seam.fail()`, because `circle.py` turns a `fail()` into a non-zero exit — which would be refusing by another route.

**A live report is filed with its circle** (R537): the close's own commit carries `work/logs/open_<OT>.json` beside `work/logs/close_<OT>.json`, its twin, and `circle_audit.py` reads every one in its phase 2 — a failed postcondition is a warning there, never a failed audit. A circle opened before this verifier existed has none, and nothing is staged in its place. A dry run's report stays in `work/sandbox/logs/`, which nothing commits.

**It runs inside the open, not as a separate process.** Its twin, `circle_close_verify.py`, is shelled out to at every close, and a separate process has to be told which group's record to read — the first time one was not told (E33), the band's close looked in the wrong group's folder. Called from inside the open, the group is already bound. The price is that nothing on that path may print, because the Ticker window reads standard output as its own protocol; the open step says what it found through the seam, and only in developer mode.

## THE POSTCONDITIONS

`coordinator/open_contract.toml` holds them, each with a `says` sentence a reader can check and change. The list was proposed, not ruled — the ruling settled whether the check may refuse.

    transcript_names_its_open_time   the transcript exists, parses, and its header names this
                                     open time
    working_set_recorded             circles/working_sets.toml has exactly one entry for it
    capture_is_whole                 prompt_capture's own per-directory check finds nothing
                                     wrong with the capture
    capture_covers_every_part        the capture's manifest names exactly this circle's parts

The last three do not apply to a dry run, which records no working set and captures no prompt. A postcondition the contract names that the code does not evaluate — or the reverse — is itself written into the report, so the two cannot drift apart without it saying so.

## THE REPORT

    open_time, checked_at, live, group    which circle, when, and where its record is
    transcript, capture, parts            what was checked
    result                                pass, or fail if any postcondition failed or the
                                          contract and the code disagree
    failed, contract                      the failing ids; the disagreements, as sentences
    postconditions                        one row per check: id, result, detail

## SEE ALSO

`coordinator/docs/circle_open.md` (the open step, whose last act is calling this), `coordinator/docs/circle_close_verify.md` (the twin at the other end), `coordinator/open_contract.toml`, `coordinator/tests/test_circle_open_verify.py`, `coordinator/prompt_capture.py --verify`.
