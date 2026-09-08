# ROSTER.PY(1)

## NAME
part_roster.py — the single canonical list of parts (directory / display tag pairs, canonical and alphabetical orderings, and lookup dicts in both directions), replacing what the docstring describes as thirteen-plus hardcoded copies scattered across the codebase.

## SYNOPSIS
    python coordinator/part_roster.py

(Also imported as a module by other scripts for `ROSTER`, `DIR_NAMES`, `ALPHA_DIR_NAMES`, `TAGS`, `TAG_BY_DIR`, `DIR_BY_TAG`, `DIR_BY_TAG_ALL`, and `IDENTITY_TAILS`.)

## DESCRIPTION
The docstring frames this file as consolidation work: before it existed, the ordered list of parts was typed out by hand in roughly thirteen places across eight files (with `coordinator/circle_close_verify.py` alone contributing two more copies, `TAG_TO_DIR` and `MAX_MEMBERS`), and each copy was a place a part could go silently missing — adding a part meant finding and editing every one of ten copies, and a missed one would not raise an error, it would simply leave that reader blind to the new part. `part_roster.py` is now the one place that changes.

That consolidation has since gone further than the docstring's original scope: `ROSTER`, `ALT_TAGS`, `IDENTITY_TAILS`, and `PROBLEMS` are no longer a hand-typed table at all. `part_scan()` reads `parts/` directly — every immediate subdirectory containing a `part.toml` is a part, its `tag` field supplies the display Tag, its optional `alt_tags` list supplies any historical spellings, and its optional `identity_tail` string supplies that part's own speaking rules, appended in BLOCK 3 every circle (R303; arrived R246 as `--minimal`'s block-4 suffix, moved out of `prompt_build.py` where it had been keyed by a part name — the mode itself retired R360). A directory with no `part.toml`, or one that fails validation (missing/invalid tag, a tag containing transcript-grammar characters, a tag colliding with another part's Tag/alt_tag or with Self's own name), is excluded from the roster and reported in `PROBLEMS` rather than silently skipped.

The docstring also explains why ordering is alphabetical rather than a separately maintained canonical order: most readers in the codebase once used one canonical circle ordering, while two others (`record_model.PARTS` and `practice_manager.PART_ADDRESSEES` after its "All parts" entry) used an alphabetical-by-directory ordering instead (a third, `recency.PARTS`, existed too until that module was deleted 2026-09-01 as unreachable dead code, D-d). A canonical order cannot survive a scan — there is nothing in a directory to derive it from — so alphabetical-by-directory-name is now the only order there is; `ALPHA_DIR_NAMES` is kept as an alias of `DIR_NAMES`, not a second distinct ordering, so the readers that historically expected that name do not need to change.

A separate note documents a historical rename: the seventh part's display tag was changed from its earlier two-word form to its current shorter form ("Part#" in both cases, per this project's redaction convention) on 2026-08-07. Fifty-six existing lines across the corpus still carry the earlier two-word form and constitute the historical record, so any reader that walks past older transcripts (`circle_close_verify.py`, `issue_gate.py`) must still be able to resolve it; a reader that only ever sees newly generated output does not need the older form.

## MAIN
The module has no `main()` function. Its top-level module body always executes, defining the roster data and derived lookup structures unconditionally; the only conditional logic is in the `if __name__ == "__main__":` guard.

    if (the module is run as a script, not imported) then {
        call verify() to get the list of problems (empty if clean);
        print how many parts are in ROSTER and their directory
            designations;
        if (any problems were found) then {
            print each one, prefixed "FAIL"; exit with status 1
        } else {
            print "PASS — ROSTER matches parts/"
        }
    } else {
        (imported as a module) only the top-level data definitions run;
        nothing is printed and no exit code is produced.
    }

## COMMAND-LINE ARGUMENTS
None. The script takes no flags or positional arguments; running it directly performs the verification described above and prints its result.

## DEPENDENCIES
Standard library only: `pathlib`, `__future__.annotations`. No sibling-module imports, no third-party packages, no external programs invoked.

## EXTERNAL FILES
Read: `<repo root>/parts/` — every immediate subdirectory, and each one's `part.toml` if present. Read once at import time to build `ROSTER`/`ALT_TAGS`/`PROBLEMS`, and again on every `verify()` call, which re-scans rather than trusting the import-time snapshot so a tree edited since import is read as it is now. If `parts/` does not exist, this is treated as an empty set rather than an error.

Written: none. The script performs no writes of any kind.

## NETWORK ACCESS
None. The script makes no network calls.

## HUMAN I/O
No stdin. When run as a script: prints the count and designations of the parts in `ROSTER`, then either a "PASS" line or one "FAIL" line per discrepancy between `ROSTER` and the `parts/` directory tree. Exit code 1 if any discrepancy is found, 0 (implicit) otherwise; when imported as a module, no output is produced and no exit code is set.

## OPERATION

### `ROSTER`, `ALT_TAGS`, and the derived lookup structures
    {
        ROSTER, ALT_TAGS, and PROBLEMS are built once at import time by
        part_scan(): every immediate subdirectory of parts/ (skipping
        __pycache__, .git, .venv, and dotdirs) that contains a
        part.toml is a part. Order is alphabetical by directory name —
        the only order there is, since nothing in a directory or its
        files can carry a canonical circle order.

        For each part directory, part.toml supplies the display Tag
        (the `tag` key — required, non-empty, and forbidden from
        containing "[", "]", or a newline, the transcript grammar's
        characters), optionally a list of historical spellings of
        that Tag (`alt_tags`), and optionally that part's BLOCK 4
        speaking-rules tail (`identity_tail`, a string — R246,
        2026-08-19). A directory with no part.toml, a part.toml that
        fails to load, a missing or invalid tag, or a tag that
        collides with another part's Tag or alt_tag is EXCLUDED from
        ROSTER and reported in PROBLEMS instead — a malformed part is
        absent and loud, not included and broken. A `identity_tail`
        that is not a string is reported but does NOT drop the part:
        the tag is what makes a part addressable, a tail is one
        identity suffix, and dropping a whole part over it
        would turn a cosmetic error into an absence that reads
        downstream as silence.

        ROSTER is `[(directory designation, Tag)]`. ALT_TAGS is
        `{historical Tag: directory designation}`, aggregated from
        every part's own `alt_tags` — there is no single global
        historical-spelling register; each part's own file carries
        its own. IDENTITY_TAILS is `{directory designation: text}`,
        holding only the parts that declare one, and read from the
        marker BEFORE `alt_tags` so a malformed historical-spelling
        list cannot cost a part its tail.

        From ROSTER and ALT_TAGS, six derived structures are built:
        DIR_NAMES (directory designations, alphabetical), ALPHA_DIR_NAMES
        (an alias of DIR_NAMES, kept so readers that once expected a
        separate alphabetical ordering do not need to change), TAGS
        (display tags, same order as DIR_NAMES), TAG_BY_DIR (directory
        to current display tag), DIR_BY_TAG (current display tag to
        directory, current spellings only), and DIR_BY_TAG_ALL (the
        same, plus every historical spelling from ALT_TAGS merged in).
    }

### `statement_re(tags)`
    {
        Compile THE transcript statement-line grammar for a tag set —
        exactly what transcript_store.statement_line writes: "[Tag]:" or
        "[Tag] [To: X]:", one space, [To: ...] the only legal second
        bracket. One builder since 2026-08-19 (review, tier 3 #35):
        circle_close_verify.py and nightly.py (circle_audit.py since
        2026-08-19) each hand-rolled a copy and the
        two had drifted (any-second-bracket vs loose spacing); measured
        across all 47 transcripts before converging — neither divergence
        matched a single real line. The tag set stays the caller's
        parameter (DIR_BY_TAG_ALL for historical walkers, TAGS for the
        nightly's own recent circles).
    }

### `verify()`
    {
        re-run part_scan() against base (default parts/), fresh — not the
        import-time ROSTER/PROBLEMS snapshot, so a tree edited since
        import (or a caller-supplied fixture directory) is read as it
        actually is right now;
    }
    start from every problem part_scan() itself already reports (no
    part.toml, a part.toml that fails to load, a missing/empty/
    non-string tag, a tag containing "[", "]", or a newline, a tag
    colliding with another part's Tag or alt_tag, alt_tags not a list
    of strings, identity_tail not a string, zero parts found);
    for each part in the fresh scan, additionally check its Tag against
    Self's own display name (case-insensitively) — a check part_scan() itself
    cannot make, since part_scan() does not know who Self is;
    record "parts/<dir>/part.toml: tag <Tag> is Self's name — a part
    cannot share the operator's tag" for any collision found;
    return the combined list of problems (empty means clean).
    since 2026-08-23 part_scan() also reports every [context] shape problem
    part_context_problems_read() finds (non-string purpose, a question without a
    non-empty key/ask, data_type not STRING|NUMERIC_STRING, data_max not a
    positive integer, a non-string render, a duplicate key, an answer that is
    not a string or answers no declared question) — REPORTED, the part KEPT,
    the identity_tail precedent.

### `part_context_problems_read(dir_name, doc)`, `part_context_read(dir_name, base=None)`,
### `part_context_write(dir_name, answers, base=None)`
    R331, 2026-08-23 (docs/Initialization.md stage 1). A part's
    part.toml MAY carry a [context] table: `purpose`, `[[context.questions]]`
    (key, ask, data_type, data_max, optional render — the ONLY path from an
    answer into BLOCK 3, so a question without one is recorded-only,
    R329) and a `[context.answers]` table between the
    markers CONTEXT_OPEN / CONTEXT_CLOSE.
    read_context: the table as declared RIGHT NOW — None for no table, an
        unreadable file, or any problem; answers is a key->string dict over
        every declared key ("" where unanswered). Reads the file every call
        (R332: a hand-tuned data_max is active at once).
    write_context: refuse a key answering no question or a non-string value;
        merge into the recorded answers; render the block (question order,
        TOML basic strings); replace exactly the bytes between the markers,
        appending the block if the file has none, refusing unpaired markers;
        the new text must load and verify BEFORE it lands; record_atomic_write()
        (LF); re-read, raising if it does not read back. Bytes outside the
        markers are never touched — the file is never re-serialised.

## BUGS
None found. The module's own comment on `DIR_BY_TAG` versus `DIR_BY_TAG_ALL` explicitly documents and justifies why two nearly-identical lookup dicts exist rather than one, so the apparent duplication is a deliberate, explained design choice rather than an oversight.
