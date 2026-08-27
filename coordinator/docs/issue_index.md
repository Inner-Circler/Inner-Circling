# ISSUE_INDEX.PY(1)

## NAME
issue_index.py — generate issues/INDEX.md, the one scannable document summarising the whole issue graph.

## SYNOPSIS
    python memory/issue_index.py
    python memory/issue_index.py --working-set nNNNN,nNNNN,...
    python memory/issue_index.py --live

## DESCRIPTION
`issue_index.py` writes `issues/INDEX.md`, a generated (never hand-edited) summary of the issue graph: counts by status, a table of live issues ranked by evidence depth, lists of leads and closed issues, an edge census, and a "gone quiet" section flagging live issues with no recent evidence (the headings say "issue", never "node" — R279, 2026-08-21). The module's docstring explains the "generated, never hand-edited" discipline by pointing at a real prior failure: `self/circle_briefing.md` drifted under hand maintenance until only 2 of 8 sampled quotes still traced back to source. The fix is to regenerate rather than correct.

It was rewritten for the 2026-07-31 "recognition pass," when the graph went from 35 unreviewed nodes to 9 live plus 26 recording a ruling already made — so the index now leads with the live nine and, deliberately, counts only *live* edges everywhere (a retired edge counted alongside a live one would report a graph making a claim it no longer makes).

It supports a `--working-set`/`--live` view that restricts which nodes are summarised without ever removing anything from `issues/` itself, and pulls in any node a chosen node has a live edge to (so the index never shows half an edge) — the same `--working-set`/`--live` design `issue_draw.py` had until its own `--live` was retired 2026-08-13 (see `issue_draw.md` NOTES); this script's `--live` is unaffected.

## MAIN
    parse any --working-set/--live arguments into a chosen id list (using a
    freshly loaded graph to resolve --live);
    load the graph again (fresh, second load);
    compute the live/leads/roots/closed id lists, and inbound live-edge
    counts, over the WHOLE graph;
    if (a working set was chosen) then {
        trim live/leads/roots/closed down to the working-set-plus-pulled-in
        node ids (working_set()); report unknown ids
    }
    compute total live/retired edge counts and the most recent circle any
    live node cites;
    build the Markdown document body: a header with counts, a Status
    legend, a note on the live-graph-is-closed invariant, an optional
    working-set-view banner, a live-nodes table (ranked by circle-count
    then id) with a leaf marker and a `ruled` marker per row, each live
    node's description, a Live issue-relationships section, a Gone quiet section (any
    live node last cited before the graph's most recent circle),
    a Leads section, a Closed section (grouped by settled/declined/
    retired), and an Issue-relationship census section;

    if (any of the literal placeholder strings "nNNNN", "nMMMM", "nPPPP"
        appears anywhere in the assembled document body) then {
        print a REFUSAL message naming which placeholder(s) were found;
        leave issues/INDEX.md UNCHANGED; return 1
    } else {
        write the body to issues/INDEX.md;
        print a one-line summary of what was written;
        return 0
    }

## COMMAND-LINE ARGUMENTS
- (no arguments): summarises the whole `issues/` tree, every status.
- `--working-set nNNNN,nNNNN,...` (or `--working-set=...`, or bare ids following the flag without commas — the parser accepts either): restrict the index to the named nodes plus anything they have a live edge to. Ids may be given as a bare number, `nNNNN`, or a prefixed filename stem (`L_n9999`); `normalise_id()` resolves all three.
- `--live`: adds every node whose status is `"live"` to the working set (composable with `--working-set`).

## DEPENDENCIES
Standard library: `collections`, `sys`, `datetime`, `pathlib`, `__future__.annotations`. Sibling module: `issue_schema` (as `S`, for `S.nodes()`, `S.load()`, `S.unwrap()` — every field is read through the schema module so this file carries no parsing logic of its own).

## EXTERNAL FILES
Read: every `issues/*nNNNN.toml` node file, via `issue_schema`.

Written: `issues/INDEX.md` — unless the assembled body would contain a leftover placeholder id (`nNNNN`/`nMMMM`/`nPPPP`), in which case the write is refused and the existing file is left untouched (see BUGS/context below — this refusal was added 2026-08-08 after a prior pass corrupted the module's own prose with placeholder ids that then leaked into the generated file).

## NETWORK ACCESS
None.

## HUMAN I/O
Stdout only, no stdin. Prints an unknown-id notice when a working set names ids not in the graph, either a REFUSAL message (with the placeholder ids found, and a pointer to decision D36) or a success summary of what was written. Exit codes: 1 if the placeholder-refusal path is taken, or 0 on a normal successful write. (There is no explicit non-zero path for, e.g., a malformed `--working-set` argument — it degenerates to an empty or partial id list rather than erroring.)

## OPERATION

### `load()`
    {
        for every node file (via S.nodes()), read it through issue_schema
        and build a per-node summary dict: file name, label, unwrapped
        description, status, the set of parts holding evidence, evidence
        count, the sorted set of circle_ sources cited, all edges (typed
        open/retired), the live-edges-only subset, a count of quotes that
        are Self's own OR formally adopted from a part (per the
        2026-08-02 ruling that an adopted statement counts as Self's own
        testimony), the set of adopted parts, and whether the label has
        been formally ruled.
    }

### `normalise_id(x)`
    { identical in behaviour to issue_draw.py's function of the same name:
      strip a status prefix, strip leading n/N, zero-pad a bare digit id. }

### `parse_working_set(argv, g)`
    if ("--live" is present) then {
        include every id in g whose status is "live"
    }
    for each argv token, matching "--working-set X" or "--working-set=X" {
        split X on commas (trimming whitespace) and include those ids
    }
    normalise and return the collected ids.

### `working_set(g, chosen)`
    {
        partition chosen into known (kept) and unknown ids; for every kept
        node, follow its live edges and pull in any endpoint not already
        kept, recording it as pulled. Returns (keep, pulled, unknown).
    }

## BUGS
None found.

WITHDRAWN 2026-08-27 — the `working_set()` / `keep` note recorded here. It reached its own verdict
inside its own sentence ("nothing is actually wrong here; flagged and then dismissed as not a
defect") and should never have been left standing in a BUGS section: a reader scanning for open
defects has to read to the end of a paragraph to learn there is none. The values are used, just
filtered rather than iterated directly.

RESOLVED 2026-08-19 (review tier 2 #24): `ruled`/`n_all` used to be computed twice, and a SECOND near-identical working-set banner followed the first — gated on a condition only a `--working-set` restriction could produce, and instructing "Regenerate with `--all`, `--limit N`", flags this tool has never accepted. One banner remains, computed once; the misleading self-instructions are gone.
