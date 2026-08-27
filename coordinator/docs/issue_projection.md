# ISSUE_PROJECTION.PY(1)

*Title corrected 2026-08-17 — this man page's own header still said
CHECK_ISSUES.PY from before the module was renamed to
`issue_projection.py`; unrelated to today's relations_brief rename,
fixed while already here.*

## NAME
issue_projection.py — verify the live issue graph is sound to project into a prompt, and provide the projections `circle.py` builds Block 2 (circle_objectives) from.

## SYNOPSIS
    python memory/issue_projection.py    verify SHAPE and PROVENANCE over the live graph

## DESCRIPTION
This module used to both project the live issue graph into a file (`self/circle_briefing.md`) and verify that projection — the same one-module shape as `check_better_options.py`, referred to in an earlier version of this file's own docstring as B9. That file was retired 2026-08-11, and with it the projection step: `circle.py`'s `build_briefing()` now calls straight into this module's `block()`, `project_working_set()`, `project_working_set_flat()`, `issue_relationship_brief()` and `narrative()` functions at prompt-assembly time, with no intermediate file for anything to go stale against. What remains as this module's own command-line behavior is the gate: does the live graph itself have the shape those functions need, so that whatever they build for a prompt is sound.

The provenance discipline the module still documents predates that retirement. Until 2026-08-03 the whole projection was blocked on rewriting each live issue node's description into Self's own words, because projecting the original derivation's machine-authored wording into a part's prompt would put a machine's account of Self into the room as though it were his testimony. Self ruled 2026-08-03 to project with provenance instead of waiting for every node to be individually ratified: every projected block states plainly whose words it carries — "ruled by Self in `<circle>`" for a node Self has ratified in session, or "the 2026-07-27 derivation's wording — NOT YET RULED" for one that has not. The docstring frames the tradeoff directly: waiting for perfect attestation before any node reached a part would have delayed the whole graph's usefulness to protect an accuracy claim nobody was making.

What a live-node block carries is deliberately narrow in the RICH blank-working-set case: label and id, the provenance line, and the node's absence clause (what it looks like when the issue is *not* firing) — not its full description. The absence clause was chosen over the description on the reasoning that it is the more actionable half in a room: a part cannot notice a pattern from reading a definition, but it can notice that something arrived and was not converted, argued down, or priced. A hand-written narrative that predated the graph was once a second, disjoint source this module never merged into the graph's own projection — none of the live nodes were findable in it, so folding one into the other would have silently lost whichever was replaced. It was migrated into the graph and retired 2026-08-14, and the function that read it went at B46, 2026-08-17; the graph is now the whole of what this module projects.

Beyond the base per-node block, this module implements two further, more targeted views over the same graph data, both called directly by `circle.py::build_briefing()` rather than exposed as a command-line flag of this file's own: a **working-set** projection, where Self names one or more focus node ids at circle open and the room receives those nodes in full plus their one-hop live-edge neighbors ("periphery") briefly (`project_working_set`) — and a **relations brief** (`issue_relationship_brief`, named `relations_brief` until R219, 2026-08-17), a heavily pared-down replacement for a prior `docs/issue_relationship_types.md` that had gone into a circle whole at 1,808 tokens (31% of one part's prompt) and, measured across 27 part statements, was never once referenced by name for any of its edge types. The relations brief gives only what a part needs to *do* relation work: what each edge type means, a one-line disambiguation test for choosing between them, what is currently live, and open questions plus proposed-but-unconfirmed edges scoped to the current working set, so a part named as someone whose confirmation is being sought actually sees the question. (A FLAT working-set variant, `project_working_set_flat()`, served the retired `--minimal` baseline — it dropped the focus/periphery split, provenance and live edges by the 2026-08-03 ruling, and both it and the mode's relations-brief exclusion retired with `--minimal` at R360, 2026-08-27; git holds the function.)

## MAIN
    main():
        nodes = live_nodes()
        if (no live nodes exist) then {
            print "FAIL  no live issues found in issues/"; return 1
        }
        for each live node:
            build its projected block via block(); accumulate any SHAPE
            failures (missing label, missing absence clause, or a `ruled`
            provenance naming a transcript that does not exist)
        count how many of those blocks carry Self's ruling (vs. the
        derivation's wording, by checking for the "*ruled by Self" marker
        text)
        print the live-node count and the ruled/unruled split
        if (any failure was accumulated) then {
            print the failure count and each failure, indented; return 1
        } else {
            print a PASS line; return 0
        }

    if (__name__ == "__main__") then { raise SystemExit(main()) }

This module's `if __name__ == "__main__"` block no longer branches on any flag — it did, before 2026-08-11, on `--preview` and `--project`; both are gone along with the file-projection feature they drove.

## COMMAND-LINE ARGUMENTS
- (no arguments): the only supported invocation. Runs `main()`, the SHAPE + PROVENANCE verification pass over the live graph, and exits 1 on any failure, 0 on a clean PASS. Any other argv content is silently ignored — nothing in the script inspects `sys.argv` any more.

Note: `project_working_set()`, `project_working_set_flat()`, `issue_relationship_brief()`, `block()`, and `narrative()` are not wired to any flag here — they are library functions this module exposes for `circle.py::build_briefing()` (and, indirectly, `circle.py::project_working_set`'s own internal use of `block()`) to call directly with a `chosen` list of node ids as a Python argument, never a CLI flag of this file.

## DEPENDENCIES
Standard library: `pathlib`, `re`, `sys`, `__future__` (`annotations`). Sibling modules: `identity.py` (imported as `ID`, for `ID.DISPLAY` — a fixed, non-identifying display string, "Self," used in every provenance line this module writes); `issue_schema.py` (imported as `S`, for `S.live_nodes`, `S.load`, `S.unwrap`, `S.nodes`, `S.EDGE_TYPES` — the one parser/grammar for issue node TOML files, per its own module contract).

## EXTERNAL FILES
Read: every live issue node file under `issues/` (via `S.live_nodes()` / `S.nodes()` / `S.load()`); circle transcripts under `circles/` or `work/sandbox/circles/` (via `_transcript()`, to confirm a node's cited "ruled in `<circle>`" reference actually names a real transcript file). `self/issues_narrative.md` was also read, by `narrative()`, until B46 (2026-08-17) removed that function; this module opens no file under `self/` any more.

Written: nothing. This module writes no file of its own as of 2026-08-11 — `self/circle_briefing.md`, the one file it used to write under `--project`, is retired.

## NETWORK ACCESS
None.

## HUMAN I/O
Stdout only, from `main()`: the live-node count and ruled/unruled split, then either a numbered FAILURE list (exit 1) or a PASS line (exit 0). No stdin is read anywhere in this module.

## OPERATION

### `_transcript(ref)`
    {
        Map a "circle_<OT>" or "sandbox_<OT>" reference string to its file
        path — the sandbox prefix routes to work/sandbox/circles/
        instead of circles/, so a ruling made in a stripped-memory room is
        visibly marked as such wherever it is cited.
    }

### `block(p)`
    load node p via issue_schema
    if (the node has no Label) then { record "no Label — nothing to
        project" as a failure }
    if (the node has no absence clause) then { record "no absence clause —
        nothing usable in a room" as a failure }
    if (a label_ruled value is set but does not resolve, via _transcript(),
        to a real transcript file) then { record a failure — the block
        cannot claim Self's authority on a circle that did not happen }
    build the provenance line: "*ruled by Self in <ref>*" if label_ruled is
    set, else "*the 2026-07-27 derivation's wording — NOT YET RULED*"
    return (the assembled "### id — label\nprovenance\n**Absent when:**
    absence" block text, the accumulated failures list)

### `narrative()` — REMOVED, B46 2026-08-17
    Read self/issues_narrative.md if it exists, stripped its own header up
    to the first "\n---\n" separator, and returned the remainder verbatim;
    "" if the file did not exist. The file was retired 2026-08-14, so the
    function read an absent one and returned "" on every circle for three
    days before it and its BLOCK 2 call site were deleted together. Listed
    here because a man page that simply loses a function looks like a
    documentation gap rather than a decision.

### `normalise_id(x)`
    {
        Strip an "L_" / leading "n" / leading "N" style prefix down to the
        bare zero-padded "n9999" form, so "2", "nPPPP" and "L_n9999" all
        normalise to the same handle. Non-numeric input passes through
        unchanged.
    }

### `parse_working_set(s)`
    {
        Split a free-text string on commas and/or whitespace into a list
        of normalised ids via normalise_id(), dropping empty tokens.
    }

### `live_edges(d)`
    {
        Return a node's edges as (type, target) pairs, excluding any whose
        status is "retired".
    }

### `graph()`
    {
        Load every node file under issues/ into a dict keyed by node id,
        each entry holding its file path, the full parsed document, its
        status, and its live edges (via live_edges()).
    }

### `resolve(chosen, g=None)`
    `g` reuses a caller's already-built graph() (2026-08-19, tier 5 #58 —
    one parse of issues/ per working-set projection instead of two);
    omitted, it builds its own, so every existing caller is unchanged.
    split `chosen` into:
      focus   = every id in `chosen` that exists in graph()
      unknown = every id in `chosen` that does not
    periphery = every node reachable at depth 1 from a focus node via a
    live edge, in EITHER direction — a node that PROTECTS a focus node
    must appear even though the edge points inward toward the focus, not
    outward from it — minus the focus set itself
    return (focus, sorted periphery, unknown)

### `full_block(p, d=None)`
    {
        A focus node's complete room-facing form: label, provenance line,
        full description, absence clause, and — if any live edges exist —
        a one-line summary of them. Deliberately excludes the node's Memo
        and evidence quotes, which are record rather than something a room
        needs to discuss directly. `d` reuses a doc graph() already parsed
        (tier 5 #58); omitted, the node is loaded here as before.
    }

### `brief_block(p, d=None)`
    {
        A periphery node's minimal room-facing form: label and description
        only, no provenance marker, no edges. `d` as in full_block.
    }

### `project_working_set(chosen)`
    if (chosen is empty) then {
        for every live node, build its block via block(), accumulating
        SHAPE failures
        if (any failure accumulated) then {
            raise RuntimeError naming every failure — this is the RICH
            path's fail-closed guard: a shape-broken node must not reach a
            live prompt even if issue_projection.py's own pre-commit gate was
            somehow bypassed
        }
        return the assembled "## Issues" section (heading, PREAMBLE, every
        node's block) as (text, an empty unknown-ids list)
    } else {
        g = graph(), built ONCE (tier 5 #58 — this branch used to parse
        every issues/*.toml twice up front and once more per rendered
        node)
        (focus, periphery, unknown) = resolve(chosen, g)
        build a heading naming the working set and its periphery (or
        stating plainly that no periphery reaches these nodes — itself
        called out as worth a circle to notice)
        emit full_block() for every focus node, passing g's parsed doc
        if (periphery is non-empty) then { emit brief_block() for every
            periphery node under a "Related" subheading, docs from g }
        return (the assembled text, unknown)
    }

The blank-`chosen` branch exists because `resolve([])` itself returns nothing at all — a working set of "everything" is not the same claim as "focused on nothing" — so blank input is handled explicitly here rather than falling through to an empty section.

### the GLOSS/CHOOSE vocabulary check  (replaced `gate_edge_types()`, 2026-08-19)
    {
        Import-time, a plain raise (never `assert`, which -O would
        strip): if GLOSS's keys or CHOOSE's types differ from
        issue_schema.EDGE_TYPES in either direction, every reader of
        this module fails loudly — the pre-commit hook runs main() on
        any issues/ commit — until the new type's meaning and chooser
        line are written for the room. This is the check the GLOSS
        comment always CLAIMED (review, tier 5 #51); gate_edge_types(),
        the zero-caller helper seemingly built for it, is deleted.
    }

### `issue_relationship_brief(chosen=None)`  (named `relations_brief` until R219, 2026-08-17)
    g = graph(); live = every (node id, edge type, target) triple across
    the whole graph, sorted
    emit static prose: what an edge is, that no part statement creates or
    retires one, what a proposal must state, how to dispute a live edge
    emit the GLOSS text for each of the five edge types, sorted by name
    emit the CHOOSE disambiguation table (one-line test -> edge type, for
    each of the five types)
    emit "LIVE NOW": every live edge in the whole graph (not filtered by
    chosen), or "- none" if there are none

    ws = set(chosen or [])
    collect `prop`: every edge across the whole graph whose status is
    "proposed", filtered to those touching `ws` if `ws` is non-empty
    collect `opens`: every open proposal on a node or edge in scope
    (scoped to `ws` the same way)

    if (opens is non-empty) then {
        emit an "OPEN QUESTIONS" section: for each, the question text,
        the specific relation being asked about if the proposal names one
        (target node's label included when known), and who asked it and
        in which source
    }
    if (prop is non-empty) then {
        emit a "PROPOSED, NEVER PUT TO A ROOM" section: for each proposed
        edge, who is asked to confirm or dispute it, and its basis text
        with the machine-provenance parenthetical stripped via
        _for_room()
    }
    return the assembled text

`chosen` filters the proposed-edges and open-questions sections to those touching the working set; without it, every proposed edge and open question in the graph is shown. The live-edges section itself is never filtered by `chosen`.

### `_for_room(basis)`  (nested inside `issue_relationship_brief`)
    {
        Strip a trailing "(proposed by the derivation ...)" or "(the
        derivation recorded this ...)" parenthetical from a basis string,
        via regex substitution — that provenance is useful to an engineer
        and noise to a part being asked whether the underlying claim
        holds.
    }

### `project_working_set_flat(chosen)`
    g = graph()
    if (chosen is given) then { (focus, periphery, unknown) = resolve(chosen) }
    else {
        focus = every live node's id, periphery = [], unknown = [] — blank
        means the whole live graph, exactly as elsewhere; resolve([])
        itself would silently produce an empty section otherwise
    }
    emit a flat heading naming the working set (or "the whole live graph"
    if chosen was blank) and its periphery, if any
    emit brief_block() for every node in focus + periphery, uniformly — no
    provenance markers, no full descriptions, no distinction between a
    focus node and a periphery one
    return (the assembled text, unknown)

This was the `--minimal`-only counterpart to `project_working_set()` — retired R360; the paragraph below records what it did.

## BUGS
RETIRED with `--minimal` (R360, 2026-08-27): the function, its FLAT_PREAMBLE constant and the SHAPE-validation asymmetry this section used to flag all left together; git holds them.

RESOLVED 2026-08-19 (review, tier 5 #51): the assertion this note reported missing — GLOSS/CHOOSE keys equal to `issue_schema.EDGE_TYPES` — is real now, import-time and raising, and the never-called `gate_edge_types()` helper is deleted. A new edge type fails every reader of this module until its gloss and chooser line exist.
