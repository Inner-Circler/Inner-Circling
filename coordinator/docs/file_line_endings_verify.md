# FILE_LINE_ENDINGS_VERIFY.PY(1)

## NAME
file_line_endings_verify.py — asserts no carriage return survives in any file this project hashes, parses, or ships.

## SYNOPSIS
    python coordinator/file_line_endings_verify.py
    python coordinator/file_line_endings_verify.py <path> [<path> ...]
    python coordinator/file_line_endings_verify.py --staged
    python coordinator/file_line_endings_verify.py --fix <path> [<path> ...]

## DESCRIPTION
The project's `.gitattributes` sets `* -text`, which tells git to store every byte exactly as given — no line-ending normalization on checkout or commit. That is what makes a sha256 hash or a byte-identical comparison elsewhere in this project (e.g. `quote_verify.py`'s provenance check) mean anything, but it also means nothing ever cleans up a stray CRLF once it lands in the tree. The script's own docstring recounts the incident that motivated it: on 2026-08-07, three files were converted wholesale to CRLF because `pathlib.Path.write_text(..., encoding="utf-8")` silently translates `\n` to `\r\n` on Windows unless `newline=""` is passed — and because the resulting content was otherwise correct, every other probe passed, while the CRLF noise buried a genuine one-line fix under 1,193 lines of diff a reviewer could not usefully read.

The scope is deliberately not "everything in the repository": `SCOPE_DIRS`/`SCOPE_ROOT_SUFFIX`/`SCOPE_SELF_SUFFIX`
name exactly the directories and file kinds this project writes, hashes, parses, or ships. `SCOPE_DIRS` derives
its first four legs from `record_paths.CODE_DIRS` rather than hand-copying them, and resolves to
`coordinator/`, `memory/`, `ui/`, `packaging/`, `docs/`, `groups/ifs/issues/`, `groups/ifs/parts/`,
`rulings/`, `groups/ifs/circles/`, `work/logs/` and `work/prompts/`. Root-level `.md`/`.toml`/`.py`/`.json`
files are in scope as well, and inside `groups/ifs/self/` only the generated `.md`/`.toml`/`.json` kinds —
that directory also holds Self's own hand-authored `.txt` notes, which are explicitly not this project's to
police. `OUT_OF_SCOPE` explicitly excludes vendored/third-party material and sandbox output. (It named `archive/`
too until 2026-08-19; that entry was always redundant, since `archive/` is not in `SCOPE_DIRS` and
`system_line_endings_is_in_scope()`s final leg rejects any path with a `/` in it.) The docstring is blunt about
why this matters: "a check that fires on someone's hand-authored notes is a check that gets switched off, and a
switched-off check is worse than no check."

A small number of files carry LOAD-BEARING CRLF — for example, a close report hashes a circle's `short_terms` bytes, and if those bytes are CRLF then the recorded sha256 *is* the hash of the CRLF bytes; "fixing" the line endings would silently break a record that no longer verifies against its own stored hash. Such files are exempted individually, by exact path, in `line_endings_grandfathered.toml` beside this script — never by directory or date, since a blanket exemption would let the next stray CRLF transcript through unnoticed, exactly the failure this script exists to catch. The docstring insists any such entry must be *measured* (its recorded sha256 checked against the file's actual current bytes), not merely assumed correct.

## MAIN
    do_fix = "--fix" in argv
    args = every argv entry not starting with "--"
    if ("--staged" in argv) then {
        args = system_line_endings_staged_read()   # files this commit's index actually touches
        if (args is empty) then { print "OK nothing staged"; return 0 }
    }
    bad, nul = scan(args or None)   # None means: scan the whole tree
    if (do_fix) then {
        if (bad is empty) then { print "nothing to fix"; return 0 }
        fix() every offending path; re-scan to confirm
    }
    if (bad is still non-empty) then {
        print a FAIL header and, for each offending file, whether it is
        wholly CRLF or a mix of CRLF/LF line counts, plus repair
        instructions
        return 1
    }
    if (any grandfather entry failed its re-measurement — printed as
    FAIL lines before the scan, see system_line_endings_grandfather_verify() below) then {
        return 1 even when no CR was found
    }
    print an OK summary (scope description, grandfathered-file count,
    "every measurement re-verified")
    return 0

## COMMAND-LINE ARGUMENTS
- (no arguments): scans the entire project tree within scope.
- `<path> [<path> ...]`: check only these specific paths (still filtered through `system_line_endings_is_in_scope()` and the grandfather list).
- `--staged`: scan only files staged in the current git commit (via `git diff --cached --name-only --diff-filter=d -z`, excluding deletions), rather than a path list or the whole tree.
- `--fix <path> [<path> ...]`: in addition to any of the above, strip `\r\n` down to `\n` via raw byte replacement (never a text-mode rewrite, which is what caused the problem in the first place) for every currently-offending path, then re-check and report.

## DEPENDENCIES
Standard library: `pathlib`, `sys`, `subprocess` (inside `system_line_endings_staged_read()`, to invoke `git`), `tomllib` (or the `tomli` backport on Python <3.11, inside `_grandfathered()`). External program: `git` (`git diff --cached --name-only --diff-filter=d -z`), only when `--staged` is used.

## EXTERNAL FILES
Read: `coordinator/line_endings_grandfathered.toml` (the exemption register, read once at import time into the module-level `GRANDFATHERED` dict); every file under the project tree (or every path given on the command line, or every staged path) whose relative path is judged in-scope by `system_line_endings_is_in_scope()`.

Written: only the specific paths given to `--fix`, and only those actually found to contain `\r\n` — rewritten with raw byte replacement (`p.write_bytes(fixed)`), not a text-mode write.

## NETWORK ACCESS
None.

## HUMAN I/O
Stdout: a FAIL header and per-file CRLF/LF counts plus repair guidance, per-entry grandfather re-measurement failures, an OK summary line, or (with `--fix`) per-file "fixed ... (N CR removed)" lines. No stdin. Exit codes: 0 if nothing staged (with `--staged` and nothing to check), 0 if `--fix` found nothing to fix, 0 if the final scan is clean AND every grandfather measurement re-verified, 1 if any in-scope file still carries a CR after the requested action or any grandfather entry failed its re-measurement.

## OPERATION

### `_grandfathered()`
    if (coordinator/line_endings_grandfathered.toml does not exist) then {
        return {} — an absent register is the normal state, not a fault
    } else {
        parse it and return {path: full entry dict} for every listed file
        (each entry carries hashed_by, why, and — since 2026-08-19 — the
        measured sha256 itself)
    }

### `system_line_endings_grandfather_verify()`
    { (valid exempt paths, failure lines), computed once per run and
      cached. 2026-08-19 (review, tier 3 #33): the register's rule is
      "measured, not assumed", but the exemption used to be path-keyed
      and never re-measured — a file deleted and recreated with fresh
      CRLF stayed silently exempt, and a rename had already orphaned an
      entry once. Each entry now exempts its path only while the file
      exists AND its current sha256 equals the entry's recorded one; a
      missing file, a missing sha256 field, or a mismatch produces a
      loud FAIL naming the repair, and the file drops back into scope.
      The measurement lives IN the register because the close report
      hashes only the seven short_terms — the transcript entry was
      always exempted by association and had no recorded measurement
      anywhere until the field was added. }

### `system_line_endings_is_in_scope(rel)`
    if (rel is in the grandfathered set AND its measurement re-verifies
    per system_line_endings_grandfather_verify()) then { return False }
    else if (rel starts with any OUT_OF_SCOPE prefix) then { return False }
    else if (rel starts with "self/") then {
        return True only if its suffix is one of the generated kinds
        (.md/.toml/.json)
    } else if (rel starts with any SCOPE_DIRS prefix) then {
        return True unless its suffix is a known binary suffix
    } else {
        return True only if rel has no further "/" (i.e. it's a root-level
        file) and its suffix is .md/.toml/.py/.json
    }

### `system_line_endings_scan(paths=None)` — the CR half; the NUL half rides the same pass
(`scan()` before the B99 re-homing, 2026-09-03.)
    (`offenders(paths)`, a wrapper returning only the CR half, was retired
    2026-09-03: nothing called it)
    {
        iterate either every file under ROOT (paths is None) or the given
        path list; for each, compute its path relative to ROOT and skip it
        if that fails (outside the project) or it is not in scope; skip
        files that look binary by a null-byte probe of the first 8000
        bytes even if their suffix slipped through; for every remaining
        file whose raw bytes contain a "\r", record (relative path, CRLF
        line count, LF count); return them sorted
    }

### `system_line_endings_fix(rel_paths)` (`fix()` before the B99 re-homing, 2026-09-03)
    for each path {
        read its raw bytes; if it contains any "\r\n", replace every
        occurrence with "\n" and write the result back as raw bytes
        (never a text-mode write, since that is exactly what caused the
        damage this script exists to catch); print a confirmation with the
        byte-count difference
    }
    return the count of files actually changed

### `system_line_endings_staged_read()`
    {
        run `git diff --cached --name-only --diff-filter=d -z` in ROOT and
        return each resulting relative path, resolved to an absolute path
        under ROOT. The -z (NUL-separated) output format is used
        specifically so no shell-quoting edge case has to be handled by
        hand.
    }

## BUGS
None found.
