# SELF_SCHEMA.PY(1)

## NAME
self_schema.py — shared TOML reader/writer for the hand-authored `self/` registers (best practices, better options, per-circle marks, proposals, mark proposals), replacing separate regex-based Markdown parsers with one loader that either parses cleanly or refuses to load at all.

## SYNOPSIS
This module exposes no command-line interface of its own; it defines no `if __name__ == "__main__":` block and is imported by other scripts (e.g. `check_best_practices.py`, `check_better_options.py`, a marks reader) as a library.

## DESCRIPTION
The docstring identifies the registers this module reads and writes: `self/best_practices.toml` (how the circle behaves), `self/better_options.toml` (how Self moves), `self/marks/<tag>.toml` (Self's own ratifications, written at a circle's close), and the later PROPOSE-class registers (`self/proposals.toml`, `self/mark_proposals.toml`). `self/proposals.toml` (R202, 2026-08-16) replaced two earlier, separate files at once — `self/requests.toml` and `self/relation_proposals.toml` — when `request` and `relation` folded into one PROPOSE marker; neither predecessor ever held a real row, so there was nothing to migrate. Until a 2026-08-05 ruling, four of these (including the now-retired `self/open_concerns.toml`) were the last hand-edited structured records outside the `parts/` tree, and each had its own bespoke regex parser matching a heading pattern specific to that file. The open-concerns register itself was retired outright, 2026-08-13 — vestigial — along with `concerns.py`; `self_schema.py`'s own `CONCERNS` path constant went with it.

The docstring gives a concrete measurement of what those four regex parsers cost in reliability: a separate stats script re-derived two of the same counts these registers track and got 23 and 0 where the registers' own owners recorded 17 and 11, and the (now-retired) concerns parser silently swallowed a "## Resolved" heading, turning every resolved concern back into an apparently-open one. The docstring's point is that both classes of defect are structurally impossible in TOML: an array of tables either parses as present or the file fails to load at all, so a heading-matching mistake cannot silently misclassify data the way a regex could.

The docstring is explicit about what the format change does *not* fix: everything these registers claim about the world — that a quote is verbatim, that a projection reached the briefing, that a tally matches — is still checked by the same downstream verifiers; those verifiers now read already-parsed data instead of re-parsing prose, but the substance of what they check is unchanged.

A design note explains why each file's introductory prose (`[doc] preamble`) is preserved rather than dropped: it is real prose — what a place in the register costs, what synthesis may and may not do with an entry — belonging to Self and to the author to read, not decoration, and stripping it during a format migration would repeat a failure this project has found before: bursting structured content out of its prose loses the reasoning that gave it meaning.

## MAIN
This module has no `main()` function and no top-level executable entry point at all; it is purely a library of functions and module-level path constants, imported by other scripts. Its top-level code, executed unconditionally on import, is linear (no branching):

    {
        resolve ROOT (the repository root, two parents above this file)
        and SELF (the self/ subdirectory); BETTER and MARKS
        resolve beneath SELF, BEST beneath ROOT/coordinator instead —
        best practices are circle-scoped, not self-scoped;
        set WRAP, the default word-wrap width for rendered prose, to 76;
        import tomllib from the standard library, falling back to the
        third-party tomli backport if tomllib is unavailable (Python
        3.10 and earlier).
    }

## COMMAND-LINE ARGUMENTS
None — this module defines no argument parser and is never invoked directly from the command line.

## DEPENDENCIES
Standard library: `pathlib`, `textwrap` (imported lazily inside `wrap()`), `__future__.annotations`, and `tomllib` (Python 3.11+). Third-party fallback: `tomli`, imported only when `tomllib` is unavailable, to provide equivalent TOML parsing on older Python versions. No sibling-module imports and no external programs invoked.

## EXTERNAL FILES
Read: whatever path is passed to `load(p)` — in practice, one of the register paths (`BEST`, `BETTER`, `PROPOSALS`, `MARK_PROPOSALS`, or a file under `MARKS`) as chosen by the calling script; this module does not choose which file to read on its own.

Written: whatever path is passed to `save(p, doc, table, order)` — again chosen by the caller — but only after the freshly rendered text is re-parsed and compared back against the in-memory document; if the two do not match exactly, the write is refused and no file is touched.

## NETWORK ACCESS
None. The module makes no network calls of any kind.

## HUMAN I/O
None directly — this module has no stdin/stdout interaction of its own and raises exceptions (rather than printing) when something is wrong; calling scripts are responsible for any user-facing output.

## OPERATION

### `load(p)`
    { read the file at path p as UTF-8 text and parse it as TOML,
      returning the resulting dict; parse failures propagate as
      whatever exception tomllib/tomli raises. }

### `unwrap(s)`
    {
        given hard-wrapped prose, rejoin each blank-line-separated
        paragraph into a single line (a single newline is treated as a
        soft wrap point, a blank line as a genuine paragraph break —
        the same convention used by the sibling issue-schema module),
        and return the paragraphs rejoined by blank lines. This is the
        form prose is compared and emitted in.
    }

### `wrap(s, width=WRAP)`
    {
        take the unwrapped (one-line-per-paragraph) form of s and
        re-wrap each paragraph to the given column width using
        textwrap, preserving blank paragraphs as empty lines, and
        prefix the whole result with a leading newline. This is the
        form prose is stored in on disk, so that diffs stay readable.
    }

### `_lit(s)`
    if (s contains no newline AND is under 90 characters AND does not
        itself contain a triple-quote) then {
        render it as a single-line TOML basic string, escaping
            backslashes and double quotes
    } else {
        render it as a TOML triple-quoted multi-line string, escaping
            backslashes and any triple-quote sequences, with any
            trailing newline stripped before the closing quotes
    }
    The docstring stresses this function never re-wraps or normalizes
    whitespace, because several of the stored records hold verbatim
    quotes, and at least four quotes in the project deliberately carry
    a double space that an automatic tidy-up would otherwise remove.

### `dumps(doc, table, order)`
    {
        emit every top-level scalar field of doc (skipping the main
        table key and the "doc" key) as a bare TOML assignment, booleans
        lowercased, strings rendered via _lit, everything else via
        str().
    }
    if (doc has a non-empty "doc" sub-dict) then {
        emit a "[doc]" table header, then each of its key/value pairs
            as a bare assignment via _lit — deliberately with NO
            wrapping or reformatting applied here; the docstring notes
            an earlier version called wrap() at this point, which made
            the text written back differ from the text just loaded, so
            save()'s round-trip guard refused every write — correctly,
            but wrapping belongs to a one-time converter step, not to
            every write, if the writer is to be idempotent
    }
    if (doc has no entries under the main table key) then {
        emit an explicit "<table> = []" line — the docstring explains
            this guards a case found 2026-08-07: with zero entries, the
            "[[table]]" array-of-tables syntax would otherwise emit
            nothing at all, so reloading the file would show no table
            key present, and save()'s round-trip guard would refuse the
            write for a register that has legitimately emptied out
            (e.g. the last pending request was resolved)
    }
    for each entry in the main table, in its existing order {
        emit a "[[table]]" header;
        for each key in the caller-supplied canonical order, if present
            in the entry {
            emit it: a list as a bracketed, comma-separated block of
                literals; a bool lowercased; an int as-is; otherwise via
                _lit
        }
        for each key actually present in the entry that is NOT in the
            canonical order {
            raise ValueError — an entry may not carry an undeclared key
        }
    }
    return the assembled text, trailing-whitespace-stripped, with
        exactly one trailing newline.

### `save(p, doc, table, order)`
    {
        render doc via dumps(), then immediately re-parse that rendered
        text with tomllib;
    }
    if (the re-parsed document does not exactly equal the original doc
        passed in) then {
        raise ValueError refusing to write — the round-trip guard the
            docstring credits with catching both classes of defect the
            old regex parsers were prone to
    } else {
        write the rendered text to p as UTF-8 with Unix line endings
    }

## BUGS
None found. `dumps()`'s handling of an empty main table and `save()`'s round-trip guard both include their own comments explaining a specific historical failure each was added to fix, and the code as written matches what those comments describe.
