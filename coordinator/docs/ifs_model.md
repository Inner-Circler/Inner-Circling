# IFS_MODEL(1)

## NAME
ifs_model.py — read-only structural model and invariant gate for the IFS memory tree (`long_term.md`, `part_relationships.toml`, and the `self/` files)

## SYNOPSIS
    from ifs_model import compare_trees, selfcheck_tree
    findings = compare_trees(baseline_dir, candidate_dir)
    findings = selfcheck_tree(root_dir)

This is a pure library module — it defines no CLI and has no `main()` or `if __name__ == "__main__":` block. It is imported and driven by other coordinator scripts (documented elsewhere) that run nightly dreaming and its self-checks.

## DESCRIPTION
This is Phase 6 of `NIGHTLY_DESIGN.md`, and the docstring explains it was built *first*, deliberately, ahead of the transactional plumbing it eventually guards. It parses `long_term.md`, `part_relationships.toml`, and the `self/` register files for every part into a structured model, and compares a candidate tree (the output of a nightly run) against a baseline tree (the state before that run), reporting every structural change and flagging the ones that violate a fixed set of invariants.

The stated motivation is that a transaction only guarantees a *consistent* set of files, not a *correct* one — a nightly run that silently drops three sections from `long_term.md` would pass every atomicity check ever written, because atomicity says nothing about content. This module is the part that notices content-level regressions: sections that vanish, dream-entry bodies that get edited after the fact, history that gets reordered, weight numbers that move, and so on.

Invariants are derived from the baseline tree itself rather than hardcoded, because the files are not structurally uniform in practice — a part's `part_relationships.toml` can carry a section another part's doesn't, `self.md` grows one new "Dream synthesis <date>" heading per night, and "settled" markers appear in two different textual shapes. A fixed schema would be wrong the moment it met a real file; comparing candidate against baseline is both stricter (it catches drift a fixed schema would miss) and more honest about what the files actually look like.

The module writes nothing anywhere — every function it exposes only reads bytes and returns `Finding` objects.

## MAIN
This module has no `main()`/entry-point function; it is a pure library. The two public "top-level" operations a caller drives are `compare_trees()` (baseline vs. candidate) and `selfcheck_tree()` (a single tree, no baseline). Both are described in OPERATION below in the same if/then/else style used elsewhere for `main()`, since together they represent the module's execution order when invoked by an external driver.

## COMMAND-LINE ARGUMENTS
None — this module exposes no CLI of its own.

## DEPENDENCIES
Standard library: `datetime`, `hashlib`, `pathlib`, `re`, `sys`, `unicodedata`, `__future__`. Sibling module: `roster` (as `R`), for `R.ALPHA_DIR_NAMES` — the list of part directory names this module iterates over (aliased locally as `PARTS`), replacing what was previously a hand-typed alphabetical copy.

## EXTERNAL FILES
Read (all read-only; nothing here is ever written back):
- For every part in `PARTS`: `<tree_root>/parts/<part>/long_term.md` and `<tree_root>/parts/<part>/part_relationships.toml`.
- `<tree_root>/self/self.md` (the `SELF_FILES` set — ONE member today), tagged with how it is expected to change: "structured" (heading-set contract, `Dream synthesis <date>` sections may be added). `narrative_arc.md` was a member, "append_only" (prior content must be a byte-prefix of new content), until 2026-08-24: nothing has written it since R165 moved its phase bullet into `self/circle_history.toml` (2026-08-15), nothing reads it, it reaches no prompt block, and R256 had already recorded that it does not ship — so the entry was the only thing still asserting the file must exist, and `selfcheck_tree()` FAILED `MISSING` on every fresh install because of it. `self_observation_log.md` left the set on 2026-08-19: it is `self/self_observation_log.toml` now and is judged by the `REGISTERS` arm instead (`SO-` ids, `per_run_max` 1, no cap). `circle_briefing.md` had been in the set before either, tagged "rewritten," until it was removed 2026-08-11 alongside `self/circle_briefing.md`'s own retirement (see `docs/BNF.md` BLOCK 2) — no "rewritten" kind exists in `SELF_FILES` any more, and the "append_only" arm is now unreached (kept as the rule, not as a live path).
- `<tree_root>/self/narrative_<today>.md`, checked separately for baseline/candidate presence to enforce "one narrative per day, never overwritten."
- In `compare_trees()`, all of the above are read from *both* the given baseline and candidate roots; in `selfcheck_tree()`, from a single given root.

Written: none.

## NETWORK ACCESS
None.

## HUMAN I/O
None directly — this module returns `list[Finding]` objects for a caller to print or act on; it performs no printing, prompting, or logging itself, and defines no exit code (it is a library, not a process).

## OPERATION

### `Finding` / `_f(level, code, path, message)`
    {
        A lightweight record (`level` in "OK"/"WARN"/"FAIL", a short `code`, the relative path, and a human message), with `_f()` as a terse constructor that stringifies the path.
    }

### `sha(data)`, `read_bytes(p)`, `decode(data)`
    {
        sha() hashes bytes with SHA-256. read_bytes() returns file bytes or None on any OSError. decode() is deliberately strict: a stray NUL byte is reported as an error rather than silently decoded, and a UTF-8 decode failure is reported by exception message rather than swallowed with `errors="replace"` — the docstring is explicit that permissive decoding is exactly how corruption becomes invisible.
    }

### `line_endings(data)`
    {
        Classify a byte string's line endings as "lf", "crlf", "mixed", or "none", by counting CRLF pairs against total LF count. This matters because the pipeline's byte-identical / sha256 checks all assume untouched files never change line-ending style; a style change signals something rewrote the file even if the visible text is unchanged.
    }

### `suspicious_chars(text)`
    {
        Scan the distinct characters in a text for ones that are valid UTF-8 (so invisible to encoding checks) but belong to a non-Latin script (CJK, Hiragana/Katakana, Hangul, Arabic, Hebrew, Cyrillic, Devanagari, Thai), excluding a short allow-list of typographic punctuation. Motivated by a real observed defect: a stray Chinese character appearing mid-sentence in an English short_term entry, which an encoding-only check would have passed.
    }

### `headings(text, level=2)` / `split_sections(text, level=2)` / `preamble(text, marker)`
    {
        headings() lists the text of every heading line at the given `#` depth. split_sections() maps each such heading to the body text between it and the next heading at that depth (later duplicate headings win, and are reported separately by callers). preamble() returns everything before a literal marker string, or None if the marker is absent.
    }

### `Entry` (long_term.md dream/settled entries) and `parse_entries(section_body, section)`
    {
        Entry models one `### [markers] Dream <date> — <title>` block: its bracket markers (parsed via `_MARKER_RE`), date, title, field dict (from `*Name:* value` or `*Name: value*` lines — both spellings are accepted since the dreaming skill's own template specifies the second form verbatim), and body. Derived properties: `is_review` (a "review" marker present), `is_tombstone` (a header with an empty body — a known real case where an entry's content was lost but its marker line survived), `recency` (the effective date used for staleness computation: the *Last mentioned:* field's date if present, else the entry's own dream date, per a 2026-07-26 ruling that self-report entries with no circle reference must still anchor to something), and `weight` (a digit-only marker, the frozen historic weight, if any).

        parse_entries() walks a section body, finds every `### ...` line matching the strict entry template, and for each collects consecutive `*field:* value` lines immediately following it into the entry's fields dict, stopping at the first non-matching, non-blank line and treating the rest as body text.
    }

### `LongTerm` (class)
    {
        Wraps a full long_term.md text: extracts the level-2 headings, the preamble (everything above "## Dream entries"), and parses the "Dream entries" and "Settled" sections into Entry lists via parse_entries(). Critically, it also scans every `### ` line in those two sections and records any that do NOT match the entry regex as `unparsed` — this is the module's answer to a real, previously undetected failure mode: a markdown auto-formatter once escaped `### [review] Dream ...` into `### \[review] Dream ...` across a real file, silently dropping 14 of 22 entries from every downstream count while a self-check kept reporting zero failures, because it only ever examined what it had successfully parsed. `by_id` and `total` are convenience views over the combined dream+settled entries.
    }

### `check_file(path, data)`
    if (data is None) then { return (None, [FAIL MISSING]). }
    else if (the bytes are entirely blank/whitespace) then { return (None, [FAIL EMPTY]). }
    else {
        decode the bytes.
        if (decoding failed) then { return (None, [FAIL ENCODING]). }
        else {
            {
                check trailing newline (FAIL if absent, WARN if multiple trailing blank lines) and scan for suspicious_chars (FAIL per character class found).
            }
            return (text, findings-so-far).
        }
    }

### `check_short_term(path, data, part, open_time)`
    {
        Validate a short_term file: run check_file() first; if that fails to produce text, return its findings.
    }
    for each of the four SHORT_TERM_SECTIONS headings: if (missing) then { FAIL MISSING-SECTION. }
    if (any section was missing) then { return early with what's collected. }
    else {
        if (the found section positions are out of the canonical order) then { FAIL SECTION-ORDER. }
        for each section's body (bounded by section positions): if (fewer than 8 words) then { FAIL EMPTY-SECTION. }
        if (the first line does not start with "# Short-term") then { FAIL BAD-HEADER. }
        else if (the part's title-cased name is not found anywhere in that header line) then { WARN HEADER-PART. }
        if (an open_time was given and its date portion does not appear in the file's opening text) then { WARN HEADER-DATE. }
    }

### `check_size(path, base, cand, allow_shrink)`
    if (the baseline is empty) then { no findings (nothing to compare against). }
    else if (the candidate shrank by more than SHRINK_TOLERANCE (2%) and shrinkage is not explicitly allowed) then { FAIL SHRANK. }
    else if (the size changed at all beyond a negligible epsilon) then { OK SIZE, reporting the delta. }
    else { no findings. }

### `compare_long_term(path, base_text, cand_text)`
    {
        Parse both texts as LongTerm. If either lacks a "## Dream entries" heading, fail immediately (cannot verify further).
    }
    for each unparsed line in the candidate: FAIL UNPARSED-ENTRY.
    {
        compare heading sets: any lost heading is FAIL SECTION-LOST; any newly gained heading is OK if it is exactly "Settled", else FAIL SECTION-ADDED.
    }
    if (the preamble — everything above "## Dream entries" — changed) then { FAIL PREAMBLE-CHANGED (foundational identity content is not the nightly's to touch). }
    if (the candidate has fewer total entries than the baseline) then { FAIL ENTRIES-LOST (dream history is append-only). }
    for each baseline entry, matched to a candidate entry by (date|title) id:
        if (no matching candidate entry exists) then { FAIL ENTRY-VANISHED. }
        else {
            if (the entry body text changed) then { FAIL ENTRY-BODY-EDITED (bodies are immutable once written). }
            if (a frozen weight marker changed) then { FAIL WEIGHT-CHANGED. }
            for each field name present in either version whose value changed: if (the field is in MUTABLE_FIELDS — "last mentioned", "review flagged", "settled") then { OK FIELD-CHANGED. } else { FAIL FIELD-CHANGED. }
            if (the entry moved between the dream and settled sections) then {
                if (it moved dream -> settled) then { OK SETTLED. }
                else { FAIL UNSETTLED (any other transition is disallowed). }
            }
            if (a "review" marker was present in baseline and is now cleared, and the entry is still in the dream section) then {
                if (the *Last mentioned:* field actually changed, evidencing engagement) then { OK REVIEW-CLEARED. }
                else { FAIL REVIEW-CLEARED — a review flag may only clear on engagement or by settling, and neither happened. }
            }
        }
    for each candidate entry with no baseline counterpart (a genuinely new entry):
        {
            OK ENTRY-NEW.
        }
        if (it was written straight into the Settled section) then { FAIL NEW-IN-SETTLED. }
        if (it carries a weight marker) then { FAIL NEW-HAS-WEIGHT — new entries never carry historic weight numbers. }
        if (it has no *Last mentioned:* field) then { FAIL NEW-NO-FIELD. }
        if (its word count falls outside 60-320) then { WARN NEW-LENGTH (template guidance is 100-200). }
    if (there is a genuinely new entry and it is not the first entry listed in the candidate's Dream entries section) then { WARN NEW-NOT-FIRST. }

### `compare_headed(path, base_text, cand_text, allow_new=None)`
    {
        Used for part_relationships.toml and self.md: the level-2 heading set is treated as the contract.
    }
    for each baseline heading absent from the candidate: FAIL SECTION-LOST.
    for each candidate heading absent from the baseline: if (an `allow_new` pattern was given and matches "## <heading>") then { OK SECTION-ADDED. } else { FAIL SECTION-ADDED. }
    for each heading present in both, whose body text differs: OK SECTION-REWRITTEN.

### `compare_append_only(path, base_text, cand_text)`
    if (the candidate text starts with the exact baseline text as a byte prefix) then {
        if (anything was actually appended) then { OK APPENDED. } else { no findings. }
    } else {
        find the first differing character position and FAIL NOT-APPEND-ONLY, reporting where the divergence starts.
    }

### `_tree_files(root)`
    {
        Build the fixed list of paths this module cares about under a given root: every part's long_term.md and part_relationships.toml, plus the SELF_FILES set.
    }

### `compare_trees(baseline, candidate, today=None)`
    {
        The primary entry point. today defaults to the real current date.
    }
    for each tracked file:
        if (it is absent from the baseline) then { WARN NO-BASELINE, skip. }
        else if (it is absent from the candidate) then { FAIL MISSING, skip. }
        else {
            run check_file() on the candidate bytes (collecting its findings) and separately on the baseline bytes (findings discarded, just for the decoded text); if either failed to decode, skip further comparison.
            if (line-ending style differs between baseline and candidate) then { FAIL LINE-ENDINGS, with a note this is usually git core.autocrlf converting on checkout. }
            else if (the candidate's line endings are "mixed") then { WARN LINE-ENDINGS. }
            if (the bytes are byte-identical) then { OK UNCHANGED, and move to the next file. }
            else {
                if (this is a long_term.md file) then {
                    determine whether any entry SETTLED in this diff (to decide whether shrinkage is allowed), run check_size() accordingly, then run compare_long_term() and append its findings.
                } else if (this is a part_relationships.toml file) then {
                    run check_size() (shrinkage never allowed) then compare_headed().
                } else {
                    look up its SELF_FILES kind ("structured" or "append_only" — "rewritten" was a third kind, circle_briefing.md's own, removed 2026-08-11 with the file itself); run check_size() (shrinkage never allowed, now that no "rewritten" kind remains);
                    if (kind == "append_only") then { compare_append_only(). }
                    else { compare_headed(allow_new=a pattern matching "## Dream synthesis <today>"). }
                }
            }
        }
    {
        separately, check self/narrative_<today>.md.
    }
    if (the candidate does not write this narrative at all) then { no findings — a run that writes no narrative is unaffected by whether one already exists. }
    else if (the baseline had no such file) then { treat it as a new file via check_file(), defaulting to OK NARRATIVE-NEW if check_file() itself found nothing wrong. }
    else if (baseline and candidate narrative bytes differ) then { FAIL NARRATIVE-OVERWRITE — one narrative per day; a second nightly run for the same date must not clobber the first. }
    return the accumulated findings list.

### `selfcheck_tree(root)`
    {
        No baseline comparison — proves the parser understands a single real tree and checks invariants that don't require a diff. Meant to run before compare_trees() as a sanity gate.
    }
    for each tracked file:
        {
            run check_file(); collect its findings.
        }
        if (text failed to decode) then { skip further checks on this file. }
        else {
            if (line endings are "mixed") then { WARN. } else if ("crlf") then { WARN, "rest of tree is LF". }
            if (this is long_term.md) then {
                parse as LongTerm.
                if (no "## Dream entries" heading) then { FAIL NO-DREAM-SECTION, skip rest. }
                else {
                    for each unparsed line: FAIL UNPARSED-ENTRY.
                    for each duplicate entry id (same date|title appearing more than once across dreams+settled): FAIL DUPLICATE-ENTRY.
                    for each dream entry: if (it is a tombstone — header with empty body) then { WARN TOMBSTONE, skip its other checks. } else { if (its recency came from the entry-date fallback rather than an explicit field) then { OK RECENCY-DERIVED. } if (it is flagged "review" but has no *Review flagged:* field) then { WARN NO-FIELD. } }
                    for each settled entry: if (it has no *Settled:* field) then { WARN NO-FIELD. }
                    OK PARSED, summarizing section/entry/review counts.
                }
            } else if (this is part_relationships.toml) then {
                if (it has any level-2 headings) then { OK PARSED. } else { FAIL PARSED, "no sections". }
            } else {
                OK PARSED with the section count (the generic case, for self.md — narrative_arc.md left this set 2026-08-24 as a phantom, self_observation_log.md left it 2026-08-19 for the register arm, and circle_briefing.md was also handled here, via a dedicated branch calling check_briefing(), before both were removed 2026-08-11).
            }
        }
    return the accumulated findings.

### `summarise(findings)`
    {
        Return (fail_count, warn_count, ok_count) tallied from a findings list — a convenience for a caller printing a final line.
    }

## BUGS
None found.
