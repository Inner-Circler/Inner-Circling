# ISSUE_SCHEMA.PY(1)

## NAME
issue_schema.py — the one reader and writer for an issue node: TOML load/save, prose wrap/unwrap, Markdown rendering, and schema-shape checks.

## SYNOPSIS
    python memory/issue_schema.py                  load every node, report parse/shape failures
    python memory/issue_schema.py --render nNNNN   print one node as Markdown, to stdout

## DESCRIPTION
`issue_schema.py` is the sole reader and writer of `issues/*.toml`, the files that make up the project's issue graph. The module's docstring frames why the format is TOML rather than the Markdown it replaced (ruled 2026-08-03): every parsing defect the project had recorded was Markdown ambiguity that failed *silently* — an indentation error hid an evidence entry, an edge type with an underscore fell outside a regex, a `## ` line inside a code fence ended a section early, and a markdown-aware editor once "normalised" a file and made most of its entries unparseable while it still looked fine to a human. TOML has a real grammar, so a malformed file now fails loudly at parse time instead. JSON was rejected because it has no multi-line strings, and hand-editable prose is half the point of the format.

Three things explicitly do NOT change with the move: the file prefix (`L_`, `S_`, `D_`, `X_`, `R_`, or none) remains presentation — the id is identity, and the gate cross-checks prefix against the `status` field; prose fields (`description`, `memo`, `description_history`, evidence `why`) remain Markdown text, just now living inside TOML strings, so what changed is the surrounding shape, not the writing; and prose is stored hard-wrapped with a single newline treated as soft (a paragraph break is a blank line) — exactly Markdown's own convention, decided once in this module's `issue_wrap()`/`issue_unwrap()` pair rather than scattered across every consumer.

**ROOT IS A FLAG, NOT A STATUS (R429, 2026-09-01, correcting R089/B23 of 2026-08-05).** `STATUSES` holds five values (`live`, `settled`, `declined`, `retired`, `lead`) — `"root"` is no longer one of them. A root node's own `status` is `"live"`; a separate OPTIONAL boolean field, `root`, marks it permanent (never retired or demoted — enforced by `issue_status.py`, not here) and always shown in full at circle open (`issue_prompt_projection.py`). Its filename still carries `R_`, but that prefix is now derived from the `root` flag rather than from `status` — see `prefix_for(doc)`.

The module also renders a node back to the old Markdown view on demand (`issue_render()`, `render()` before the B99 re-homing, 2026-09-03), partly for a reader who wants it and partly because rendering every migrated node and diffing against the original bytes is how the TOML migration proved it lost nothing.

## MAIN
This script has no `main()` naming convention deviation — its entry point is `main()`, called from `if __name__ == "__main__"`.

    if "--render" appears anywhere in argv then {
        take the argument immediately following "--render" as a node id;
        find the first node file (via issue_nodes_read()) whose bare id matches it;
        load and issue_render() it to Markdown; print it; return 0
    } else {
        for every node file (issue_nodes_read(), sorted) {
            try to issue_read() it as TOML;
            if loading raises any exception then {
                record "<file>: will not parse — <error>" as a failure and
                continue to the next file
            } else {
                count it as parsed, and append any failures from check(doc, p)
                to the failure list
            }
        }
        print the count of nodes parsed;
        print every failure, prefixed "FAIL";
        print "SCHEMA PASS" if there were no failures, else the failure count;
        return 1 if there were failures, else 0
    }

## COMMAND-LINE ARGUMENTS
- (no arguments): validates every node file under `issues/` and reports parse/shape failures.
- `--render nNNNN`: required following argument is a node id (any of the accepted spellings `issue_id_read()` handles via the caller, though here it is matched via `issue_id_read(nid)` against `issue_id_read(q.stem)`). Prints that one node rendered to Markdown and exits 0. If the argument is missing, or no node file matches it, prints one line naming the problem and exits 2 (see BUGS).

## DEPENDENCIES
Standard library: `pathlib`, `re`, `sys`, `textwrap`, `__future__.annotations`. TOML: `tomllib` (Python 3.11+) with a fallback import of `tomli` (identical parser) for older interpreters; `tomli_w` for writing. No sibling coordinator modules are imported — this module sits at the base of the issue-graph dependency chain, and other `issue_*.py` files import it, not the reverse.

## EXTERNAL FILES
Read: every `issues/*nNNNN.toml` node file, via `issue_nodes_read()` (all statuses) or `issue_live_read()` (files with no status prefix, UNION files prefixed `R_` — a root is live too, since 2026-09-01). `issue_locate()` computes a node's expected path from its id, status and (optionally) its root flag, but is not itself invoked by anything in this file's `main()`.

Written: nothing by `main()` in either mode described above. `issue_write(p, doc)` is provided as a library function (writes `issue_dumps(doc)` to `p` with LF newlines) but is only called by other modules that import this one (e.g. a migration or edit tool), not by this script's own CLI paths.

## NETWORK ACCESS
None.

## HUMAN I/O
Stdout only, no stdin. `--render` mode prints the rendered Markdown for one node. Default mode prints a parse count, one `FAIL` line per failure, and a final PASS/failure-count line. Exit codes: 0 when `--render` succeeds or when default-mode validation finds no failures; 1 when default-mode validation finds any failures. (`--render` on an unmatched id, or with no id after it, prints a one-line message and returns **2** — a code this script uses for nothing else, so a caller can tell a broken node from a mistyped argument. Guarded 2026-08-27; it raised an uncaught exception until then. See BUGS.)

## OPERATION

### `issue_prefix_read(doc)` (`prefix_for()` before the B99 re-homing, 2026-09-03)
    {
        return "R_" if doc's root flag is set; otherwise PREFIX[doc's status].
        The one place status and the root flag combine into a filename
        prefix — issue_verify() and issue_locate() both call it rather than
        re-deriving the same rule twice.
    }

### `issue_locate(nid, status, root=False)`
    {
        build issues/<prefix><nid>.toml, where prefix is "R_" if root is
        True, else PREFIX[status].
    }

### `circle_transcript(ref)`  (with the `CIRCLES`/`SANDBOX_CIRCLES` roots; added 2026-08-19)
    {
        circle_<OT> -> circles/<ref>.md; sandbox_<OT> ->
        work/sandbox/circles/circle_<OT>.md; anything else -> None. The
        ONE copy of the ref-to-transcript mapping (review, tier 5 #44):
        issue_gate.issue_source_read() wraps it (keeping its own self/ session
        arm), issue_prompt_projection._transcript() and quote_verify's
        constants derive from it — previously three lockstep clones the
        R176 sweep had to edit together.
    }

### `issue_id_read(stem)`
    {
        strip a two-character status prefix ("X_", "L_", etc.) from a
        filename stem if the second character is an underscore; otherwise
        the stem is already the bare id.
    }

### `issue_nodes_read()` / `issue_live_read()`
    {
        glob issues/ for every *nNNNN.toml file (issue_nodes_read(), any status
        prefix), or the unprefixed nNNNN.toml files UNION the R_-prefixed
        ones (issue_live_read() — a root is live too, since 2026-09-01), sorted.
        Two filename globs rather than a parse-and-filter of issue_nodes_read(): this
        stays the same fast, filename-only check every caller already
        relies on.
    }

### `issue_read(p)`
    {
        open the file in binary mode and parse it with tomllib/tomli.
    }

### `issue_unwrap(s)`
    {
        split the string on blank-line paragraph breaks, collapse all
        internal whitespace runs (including single newlines) to single
        spaces within each paragraph, and rejoin paragraphs with a blank
        line — turning hard-wrapped storage prose into one line per
        paragraph for consumption.
    }

### `issue_wrap(s, width=74)`
    for each paragraph (blocks split on blank lines) {
        collapse runs of spaces/tabs to one space;
        if (the collapsed block starts with a list marker "- ", "* ",
            blockquote "> ", a code fence "```", a table pipe "|", a
            heading "#", or still contains an embedded newline) then {
                leave the block exactly as it was, unwrapped — re-flowing a
                bullet, blockquote or code fence would change what the
                Markdown inside it means
        } else {
            hard-wrap the flattened text at `width` columns (74 by default),
            not breaking on hyphens or long words
        }
    }
    join the resulting blocks with blank lines between them.

### `issue_dumps(doc)`
    {
        copy the scalar (non-repeating-table) fields named in ORDER that
        are present in doc; issue_wrap() every prose field among them
        (description, absence, description_history, memo, memo_original,
        edges_note); emit them via tomli_w with multiline strings enabled.
        Then, for `proposals` (an array of tables, deliberately excluded
        from ORDER so it is not emitted twice), append each proposal's own
        TOML block. Then for `edges` and `evidence`, append each row's own
        TOML block, wrapping only the `why`/`basis` prose fields within a
        row and leaving `quote` byte-for-byte untouched — the comment
        explains this is because re-flowing a verbatim quote once
        collapsed double spaces that four real quotes carry, breaking the
        character-for-character verification issue_gate.py performs.
    }

### `issue_write(p, doc)`
    {
        write issue_dumps(doc) to path p as UTF-8 text with LF-only line endings.
    }

### `issue_render(doc)` (`render()` before the B99 re-homing, 2026-09-03)
    {
        build a Markdown document from a loaded node's dict: an H1 of its
        id; Description, Label, (optional) Label ruled, (optional)
        Aliases, (optional) Adopted, Status, Opened, Held by; a
        Description history section; What its absence looks like; an
        Edges section listing each edge's type/target/status/basis/why/
        notes/ask/quote/retired fields when present; an optional
        edges_note; an Evidence section grouped by part IN FIRST-APPEARANCE
        ORDER (not alphabetical — the comment notes alphabetising silently
        reordered three nodes during migration) with each entry's source,
        quote and why; a Proposals section; a Memo section; and, only if
        present, a "Memo — original" section for the one node that carries
        a rewritten memo alongside its original.
    }

### `check(doc, p)`
    for each key in REQUIRED {
        if (missing from doc) then { record a "missing required key" failure }
    }
    for each key present in doc {
        if (not in REQUIRED or OPTIONAL) then {
            record an "unknown key — the schema is closed" failure
        }
    }
    if (doc's status is not one of the known STATUSES) then {
        record a bad-status failure
    } else if (doc's root flag is set and status is not "live") then {
        record a "root but not live" failure — a root is always live,
        never any other status
    } else if (the filename does not match prefix_for(doc)+id+".toml") then {
        record a prefix mismatch failure (against status AND the root flag)
    }
    if (doc's id does not match issue_id_read(filename)) then {
        record an id/filename mismatch failure
    }
    for each proposal (on the node itself, or on any of its edges) {
        if (it has any key outside PROPOSAL_KEYS) then { record it }
        if (its status is not in PROPOSAL_STATUS) then { record it }
        for each of question/asked_by/source {
            if (missing or falsy) then { record it }
        }
        if (it names a "type" that is not a legal EDGE_TYPE) then { record it }
        if (exactly one of "type"/"target" is present, not both) then {
            record it — "half of one is a claim nobody can act on"
        }
    }
    for each edge on the node {
        if (its type is not a legal EDGE_TYPE) then { record it }
        if (its target equals the node's own id) then {
            record "edge points at itself"
        }
    }
    return the accumulated list of failure strings (empty means the node's
    shape is valid — NOT that its claims are true; that is issue_gate.py's
    job, as the function's own docstring states explicitly).

## BUGS
**RESOLVED 2026-08-27**, ranked first of the repairs that day because it is a shipped surface. Both failure shapes below now print one line and return **2**;
the record of what was wrong is kept because the exit-code reasoning is the part worth not
re-deriving.

---

**CONFIRMED 2026-08-27, reproduced, and worse than recorded.** `main()`'s `--render` branch was two
unguarded lines:

```
nid = sys.argv[sys.argv.index("--render") + 1]
p = next(q for q in issue_nodes_read() if issue_id_read(q.stem) == issue_id_read(nid))
```

Neither has a default or a surrounding try/except, so there are two failure shapes, not one:

```
--render n9999    StopIteration  — no node file matches that id
--render          IndexError     — the flag was given with nothing after it
```

Both print a Python traceback instead of a usage line. Every other error path in this file (parse
failures in default mode) is caught and reported cleanly; these two are not.

**CORRECTION.** This entry said the exit code "is not one of the script's own documented codes
(0/1)". Measured: it is **1** — Python's code for an uncaught exception — which is the script's
documented code for *validation failures found*. So a caller reading exit codes cannot tell "this
node is malformed" from "you typed the id wrong". Colliding with a documented code is worse than
falling outside the set, because the wrong reading is the plausible one.

**This ships.** `packaging/required.toml` includes `memory` as a whole directory, and
`packaging/additions.toml` ships this very man page with the justification *"the `--render <id>` a
person uses to read one as Markdown"* — so the advertised user-facing spelling of the command is
the one that tracebacks on a typo.

**The fix, as landed.** The argument is read with a bounds check and `next()` is given a `None`
default; either miss prints one line — the missing-argument usage, or the id with a pointer at
`ls issues/` — and returns `2`. `2` keeps `0`/`1` meaning what the OUTPUT section says they mean.
Nothing changes for a `--render` that succeeds. All four paths were exercised: unknown id, no
argument, a real node, and the bare validate run.
