# ISSUE_PROMPT_PROJECTION.PY(1)

*issue_projection.py until 2026-09-03 (F5, R435).*

*Title corrected 2026-08-17 — this man page's own header still said
CHECK_ISSUES.PY from before the module was renamed to
`issue_prompt_projection.py`; unrelated to today's relations_brief rename,
fixed while already here.*

## NAME
issue_prompt_projection.py — verify the live issue graph is sound to project into a prompt, and provide the projections `prompt_build.py` builds Block 2 (circle_objectives) from.

## SYNOPSIS
    python memory/issue_prompt_projection.py    verify SHAPE and PROVENANCE over the live graph

## DESCRIPTION
This module used to both project the live issue graph into a file (`self/circle_briefing.md`) and verify that projection — the same one-module shape as `check_better_options.py`, referred to in an earlier version of this file's own docstring as B9. That file was retired 2026-08-11, and with it the projection step: `prompt_build.py`'s `circle_briefing_build()` (moved out of `circle.py` in phase 2 stage 2, 2026-08-16) now calls straight into this module's `issue_block_render()`, `project_working_set()` and `issue_relationship_brief()` functions at prompt-assembly time — `project_working_set_flat()` and `narrative()` are both retired (see their own sections below), not among the functions actually called today — with no intermediate file for anything to go stale against. What remains as this module's own command-line behavior is the gate: does the live graph itself have the shape those functions need, so that whatever they build for a prompt is sound.

The provenance discipline the module still documents predates that retirement. Until 2026-08-03 the whole projection was blocked on rewriting each live issue node's description into Self's own words, because projecting the original derivation's machine-authored wording into a part's prompt would put a machine's account of Self into the room as though it were his testimony. Self ruled 2026-08-03 to project with provenance instead of waiting for every node to be individually ratified: every projected block states plainly whose words it carries — "ruled by Self in `<circle>`" for a node Self has ratified in session, or "the 2026-07-27 derivation's wording — NOT YET RULED" for one that has not. The docstring frames the tradeoff directly: waiting for perfect attestation before any node reached a part would have delayed the whole graph's usefulness to protect an accuracy claim nobody was making.

What a live-node block carries is deliberately narrow in the RICH blank-working-set case: label and id, the provenance line, and the node's absence clause (what it looks like when the issue is *not* firing) — not its full description. The absence clause was chosen over the description on the reasoning that it is the more actionable half in a room: a part cannot notice a pattern from reading a definition, but it can notice that something arrived and was not converted, argued down, or priced. A hand-written narrative that predated the graph was once a second, disjoint source this module never merged into the graph's own projection — none of the live nodes were findable in it, so folding one into the other would have silently lost whichever was replaced. It was migrated into the graph and retired 2026-08-14, and the function that read it went at B46, 2026-08-17; the graph is now the whole of what this module projects.

Beyond the base per-node block, this module implements two further, more targeted views over the same graph data, both called directly by `group_attention.py::circle_briefing_build()` rather than exposed as a command-line flag of this file's own: a **working-set** projection, where Self names one or more focus node ids at circle open and the room receives those nodes in full plus their one-hop live-edge neighbors ("periphery") briefly (`project_working_set`) — and a **relations brief** (`issue_relationship_brief`, named `relations_brief` until R219, 2026-08-17), a heavily pared-down replacement for `docs/issue_relationship_types.md (archived)` — the document left the tree at `048ccda`, 2026-09-07 — which had gone into a circle whole at 1,808 tokens (31% of one part's prompt) and, measured across 27 part statements, was never once referenced by name for any of its edge types. The relations brief gives only what a part needs to *do* relation work: what each edge type means, a one-line disambiguation test for choosing between them, what is currently live, and open questions plus proposed-but-unconfirmed edges scoped to the current working set, so a part named as someone whose confirmation is being sought actually sees the question. (A FLAT working-set variant, `project_working_set_flat()`, served the retired `--minimal` baseline — it dropped the focus/periphery split, provenance and live edges by the 2026-08-03 ruling, and both it and the mode's relations-brief exclusion retired with `--minimal` at R360, 2026-08-27; git holds the function.)

## MAIN
    main():
        nodes = issue_live_read()
        if (no live nodes exist) then {
            print "FAIL  no live issues found in issues/"; return 1
        }
        for each live node:
            build its projected block via issue_block_render(); accumulate any SHAPE
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

Note: `project_working_set()`, `issue_relationship_brief()`, and `issue_block_render()` are not wired to any flag here — they are library functions this module exposes for `group_attention.py::circle_briefing_build()` (and, indirectly, `prompt_build.py::project_working_set`'s own internal use of `issue_block_render()`) to call directly with a `chosen` list of node ids as a Python argument, never a CLI flag of this file. `project_working_set_flat()` and `narrative()` are retired (see their own sections below) and are not among the functions any caller reaches today.

## DEPENDENCIES
Standard library: `pathlib`, `re`, `sys`, `__future__` (`annotations`). Sibling modules: `identity.py` (imported as `ID`, for `ID.DISPLAY` — a fixed, non-identifying display string, "Self," used in every provenance line this module writes); `issue_schema.py` (imported as `S`, for `S.issue_live_read`, `S.issue_read`, `S.issue_unwrap`, `S.issue_nodes_read`, `S.EDGE_TYPES` — the one parser/grammar for issue node TOML files, per its own module contract).

## EXTERNAL FILES
Read: every live issue node file under `issues/` (via `S.issue_live_read()` / `S.issue_nodes_read()` / `S.issue_read()`); circle transcripts under `circles/` or `work/sandbox/circles/` (via `_transcript()`, to confirm a node's cited "ruled in `<circle>`" reference actually names a real transcript file). `self/issues_narrative.md` was also read, by `narrative()`, until B46 (2026-08-17) removed that function; this module opens no file under `self/` any more.

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

### `issue_block_render(p, d=None)` (`block()` before the B99 re-homing, 2026-09-03)
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

### `issue_id_normalise(x)`, `working_set_parse(s)` — MOVED to `working_set_manager.py`, 2026-09-03
    (stage 10): one id normaliser and one typed-line parser for the tree.

### `working_set_argv_parse(s)` — RETIRED 2026-09-03
    Nothing called it (issue_index.py and ui/issue_draw.py each carry
    their own argv parser). working_set_parse() stays.

### `issue_live_edges_read(d)` (`live_edges()` before the B99 re-homing, 2026-09-03)
    {
        Return a node's edges as (type, target) pairs, excluding any whose
        status is "retired".
    }

### `issue_graph_read()` (`graph()` before the B99 re-homing, 2026-09-03)
    {
        Load every node file under issues/ into a dict keyed by node id,
        each entry holding its file path, the full parsed document, its
        status, and its live edges (via issue_live_edges_read()).
    }

### `issue_resolve(chosen, g=None)` (`resolve()` before the B99 re-homing, 2026-09-03)
    `g` reuses a caller's already-built issue_graph_read() (2026-08-19, tier 5 #58 —
    one parse of issues/ per working-set projection instead of two);
    omitted, it builds its own, so every existing caller is unchanged.
    split `chosen` into:
      focus   = every id in `chosen` that exists in issue_graph_read()
      unknown = every id in `chosen` that does not
    periphery = every node reachable at depth 1 from a focus node via a
    live edge, in EITHER direction — a node that PROTECTS a focus node
    must appear even though the edge points inward toward the focus, not
    outward from it — minus the focus set itself
    return (focus, sorted periphery, unknown)

### `issue_full_render(p, d=None)`
    {
        A focus node's complete room-facing form: label, provenance line,
        full description, absence clause, and — if any live edges exist —
        a one-line summary of them. Deliberately excludes the node's Memo
        and evidence quotes, which are record rather than something a room
        needs to discuss directly. `d` reuses a doc issue_graph_read() already parsed
        (tier 5 #58); omitted, the node is loaded here as before.
    }

### `issue_brief_render(p, d=None)`
    {
        A periphery node's minimal room-facing form: label and description
        only, no provenance marker, no edges. `d` as in full_block.
    }

### `project_working_set(chosen)`
    **A ROOT IS ALWAYS SHOWN, IN FULL — R429,
    2026-09-01.** Before this ruling a root reached a live prompt only when
    an operator's chosen working set happened to have a live edge to it
    (and never at all in the blank-chosen branch, since issue_live_read() then
    was a bare filename glob that could not match an R_-prefixed file).
    Now every node whose `root` flag is set renders via issue_full_render() in
    BOTH branches below, whether or not it was named.

    if (chosen is empty) then {
        for every live node (root nodes included, since issue_live_read() now
        globs R_-prefixed files too) {
            if (its root flag is set) then {
                build its block via issue_full_render() — full detail, same as a
                chosen focus node
            } else {
                build its block via issue_block_render(), accumulating SHAPE failures
            }
        }
        if (any failure accumulated) then {
            raise RuntimeError naming every failure — this is the RICH
            path's fail-closed guard: a shape-broken node must not reach a
            live prompt even if issue_prompt_projection.py's own pre-commit gate was
            somehow bypassed
        }
        return the assembled "## Issues" section (heading, PREAMBLE, every
        node's block) as (text, an empty unknown-ids list)
    } else {
        g = issue_graph_read(), built ONCE (tier 5 #58 — this branch used to parse
        every issues/*.toml twice up front and once more per rendered
        node)
        root_ids = every id in g whose doc has the root flag set
        (focus, periphery, unknown) = resolve(chosen UNION root_ids, g) —
        resolving over the union, not chosen alone, so a root's own live
        edges pull their neighbours into periphery exactly as any other
        focus node's would
        always = root_ids not already in chosen, sorted
        build a heading naming the working set, any roots shown that were
        not named ("root(s) always shown in full: ..."), and the
        periphery (or stating plainly that no periphery reaches these
        nodes — itself called out as worth a circle to notice)
        emit issue_full_render() for every focus node (chosen ∪ roots), passing
        g's parsed doc
        if (periphery is non-empty) then { emit issue_brief_render() for every
            periphery node under a "Related" subheading, docs from g }
        return (the assembled text, unknown)
    }

The blank-`chosen` branch exists because `resolve([])` itself returns nothing at all — a working set of "everything" is not the same claim as "focused on nothing" — so blank input is handled explicitly here rather than falling through to an empty section.

**"none" IS UNCHANGED AND STILL OVERRIDES.** `chosen is None` (the
operator typed "none" at circle open) never calls this function at all —
`circle_briefing_build()` substitutes a fixed "the graph was deliberately not
brought in" line instead. A root does not force its way past that
explicit, deliberate opt-out for one circle; it is shown, always, only
within the two branches this function itself handles.

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
    g = issue_graph_read(); live = every (node id, edge type, target) triple across
    the whole graph, sorted
    emit static prose: what an edge is, that no part statement creates or
    retires one, what a proposal must state, how to dispute a live edge
    emit the GLOSS text for each of the five edge types, sorted by name
    emit the CHOOSE disambiguation table (one-line test -> edge type, for
    each of the five types)
    emit "LIVE NOW": one sentence saying a marked relation was derived and never confirmed,
    then every non-retired edge in the whole graph (not filtered by chosen), read from the
    node's own edge rows so the status survives — a `proposed` edge's line ends
    " (proposed)", an attested one carries nothing — or "- none" if there are none
    (2026-09-11: a proposed edge touching no focus node reaches the room only here)

    ws = set(chosen or []); if (ws is non-empty) then { ws |= every root id }
        — the nodes the Issues section gives whole (R547:
        by the named ids alone, a root's proposed edges and open questions were lost)
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

`chosen` filters the proposed-edges and open-questions sections to those touching the working set and the
roots; without it, every proposed edge and open question in the graph is shown. The live-edges section itself
is never filtered by `chosen`; its `(proposed)` marker is what tells a proposed edge outside that filter from
an attested one.

### `issue_shown_read(chosen)`  (R549, D128, 2026-09-11)
    if (chosen is None) then { return the empty set }          — "none": nothing shown
    if (chosen is empty) then { return the id of every live node }   — the whole graph
    else { (focus, periphery) from _working_set_resolve(chosen, issue_graph_read());
           return focus ∪ periphery }

The ids this circle's `## Issues` gives a heading — circle_open hands them to
`recall_index.recall_issues_shown_set()`, and `[recall: issues ...]` leaves exactly those
out while reaching every other node. `_working_set_resolve()` is the one resolution
`project_working_set()` renders, so the two cannot drift; `coordinator/tests/test_prompt_build.py`
holds the equality against the headings actually rendered.

### `_for_room(basis)`  (nested inside `issue_relationship_brief`)
    {
        Strip a trailing "(proposed by the derivation ...)" or "(the
        derivation recorded this ...)" parenthetical from a basis string,
        via regex substitution — that provenance is useful to an engineer
        and noise to a part being asked whether the underlying claim
        holds.
    }

### `project_working_set_flat(chosen)` — RETIRED, R360, 2026-08-27
    g = issue_graph_read()
    if (chosen is given) then { (focus, periphery, unknown) = resolve(chosen) }
    else {
        focus = every live node's id, periphery = [], unknown = [] — blank
        means the whole live graph, exactly as elsewhere; resolve([])
        itself would silently produce an empty section otherwise
    }
    emit a flat heading naming the working set (or "the whole live graph"
    if chosen was blank) and its periphery, if any
    emit issue_brief_render() for every node in focus + periphery, uniformly — no
    provenance markers, no full descriptions, no distinction between a
    focus node and a periphery one
    return (the assembled text, unknown)

This was the `--minimal`-only counterpart to `project_working_set()` — retired R360; the paragraph below records what it did.

## BUGS
RETIRED with `--minimal` (R360, 2026-08-27): the function, its FLAT_PREAMBLE constant and the SHAPE-validation asymmetry this section used to flag all left together; git holds them.

RESOLVED 2026-08-19 (review, tier 5 #51): the assertion this note reported missing — GLOSS/CHOOSE keys equal to `issue_schema.EDGE_TYPES` — is real now, import-time and raising, and the never-called `gate_edge_types()` helper is deleted. A new edge type fails every reader of this module until its gloss and chooser line exist.
