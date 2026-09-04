# ISSUE_DRAW.PY(1)

## NAME
issue_draw.py — render the issue graph (issues/*.toml, or a sandbox graph.json snapshot) as a force-directed SVG plus a self-contained interactive HTML page.

## SYNOPSIS
    python ui/issue_draw.py issues/
    python ui/issue_draw.py issues/ --working-set nNNNN,nNNNN,...
    python ui/issue_draw.py issues/ --if-stale
    python ui/issue_draw.py work/issue_derive/<RUN>/graph.json

`--live` retired 2026-08-13: a default run (no `--working-set`) already
builds the live-only view and embeds it in `issue_graph.html` as a toggle —
see NOTES.

**This is also run for you.** `coordinator/circle.py` invokes the third form
above at every LIVE `/close`, immediately after the vetting checkpoint and
before short_terms are collected. See NOTES, *Run at a close*.

## DESCRIPTION
`issue_draw.py` turns the issue graph into a picture: a large SVG laid out with a deterministic Fruchterman-Reingold force-directed algorithm, wrapped in a self-contained HTML page (the SVG inlined, so the page opens from disk with no network dependency) that also lists every node in a side table and supports click-to-highlight selection between the graph and the table.

The layout encodes several things at once, per the module's own docstring: a node's label sits at the node (read first), its stable id and evidence "depth" (count of distinct circles it draws evidence from) sit beneath it, its radius reflects evidence count, its fill colour reflects a tier (spine/thread/thin, by depth), a dotted ring marks a LEAF (nothing depends on it — "the tractable front"), edge colour encodes relation type, and a dashed edge marks a *proposed* rather than *attested* claim (the model's inference rather than a part's testimony). Evidence depth also biases nodes toward the centre of the picture, so the graph's spine visually sits in the middle and thin nodes fall to the rim.

The script always reads its data fresh from `issues/*.toml` via `issue_schema.py` rather than trusting a cached `graph.json` snapshot, because the docstring notes the snapshot "stops being the truth the moment a node is hand-edited, renamed, merged or added." Retired edges are read but never drawn (an edge is legal only when both ends are live, so a retired edge points at something making no live claim), and the `absence` field — once accidentally hardcoded to empty string for every node — is now correctly read from the document.

Nodes are grouped into visual clusters using greedy modularity community detection (chosen over label propagation, which the docstring says collapsed almost the whole graph into one hub-dominated community on a first attempt) and each cluster is laid out independently, then packed as a rigid block so cluster regions never overlap or interpenetrate.

## MAIN
    if fewer than 2 argv words (no path given) then {
        print a usage line and return exit code 2
    } else {
        take argv[1] as a path;
        if (--if-stale was passed AND argv[1] is a directory AND
            issue_draw_is_stale(argv[1]) is False) then {
            return exit code 0 having printed nothing and loaded nothing
        }
        if (it is a directory) then {
            load every issues/*nNNNN.toml node via issue_draw_read();
            use the NAMED output directory OUT_DIR = <repo>/work/graph/
            (never inside issues/ itself), creating it if absent, and
            print the source summary UNLESS --if-stale was passed (at a
            close there is only one possible source, and the describe()
            line below opens with the same node count)
        } else {
            parse it as a JSON graph.json snapshot and use its parent
            directory as the output location; print the source summary
        }
        parse any --working-set arguments into a chosen id list (a bare
        --live is accepted but ignored, with a note printed to say so —
        see NOTES);
        drop every edge whose target is not a known node in the loaded
        graph;
        if (a working set was named) then {
            trim the graph to those ids plus anything they point at
            (issue_working_set_limit()); report unknown ids and pulled-in
            targets
        }
        compute inbound-edge counts and evidence-depth for every node;
        lay the (possibly trimmed) graph out (layout()) and render it to
        SVG (build_svg());
        if (no working set was named) then {
            compute the subset of nodes whose status is "live";
            if (there is a live subset smaller than the whole graph) then {
                lay that subset out and render it independently as a
                second SVG, so the interactive page can offer a live/all
                toggle without one layout distorting the other
            }
        }
        write issue_graph.svg and issue_graph.html into the output
        directory, embedding both SVGs (one hidden) in the HTML when a
        live view was built;
        print one describe() line naming what the picture shows, one line
        naming the files and the SVG's size, and one line carrying the
        HTML's file:// address (html_path.as_uri()); return 0
    }

## COMMAND-LINE ARGUMENTS
- `<path>` (required, positional): either a directory of `issues/*.toml` node files (the live graph, read fresh from disk) or a path to a `graph.json` sandbox-derivation snapshot file.
- `--working-set nNNNN,nNNNN,...` (or `--working-set=nNNNN,...`): a comma-separated list of node ids (accepted in any of the spellings `issue_id_normalise()` handles: bare number, `nQQQQ`, or a prefixed filename stem like `L_n9999`) to restrict the drawing to. Any node those named nodes point at is pulled in as well, and reported. Unknown ids are reported and ignored. There is no default restriction — omitting this flag draws every node of every status.
- `--if-stale`: draw only if the picture is behind the graph — `issue_draw_is_stale()` decides, and a run that decides "no" prints nothing, loads nothing and exits 0. Default: OFF; a bare run always redraws. Ignored when the positional argument is a `graph.json` snapshot rather than a directory, since a snapshot has no picture of its own for the live graph's staleness to be a claim about. This is the form `coordinator/circle.py` uses at a close.
- `--live`: retired 2026-08-13. Accepted for backward compatibility (prints a note explaining the replacement) but no longer filters the node set or changes the output filename — the live view it used to produce standalone is now always embedded in `issue_graph.html` as a toggle when no `--working-set` is named. See NOTES.

## DEPENDENCIES
Standard library: `itertools`, `json`, `math`, `pathlib`, `random`, `sys`, `collections.Counter`, `__future__.annotations`. Project module: `issue_schema`, in `memory/` — NOT a sibling and not on `sys.path` by default, which is why this script inserts `<repo>/memory` at import time (see BUGS for the eleven days that path was wrong) (imported locally inside `issue_draw_read()` and `_check_vocabulary()` as `S`/`_S`, for `S.issue_read()`, `S.issue_unwrap()`, and `S.EDGE_TYPES` — the last used to assert the drawing's own `EDGE_STYLE` legend table stays in sync with the schema's set of legal edge types, raising `SystemExit` at import time if they disagree).

## EXTERNAL FILES
Read: every `issues/*nNNNN.toml` file under the given directory (via `issue_schema.issue_read()`), when the argument is a directory. A `graph.json` file at the given path, when the argument is a file (parsed directly with `json.loads`, bypassing `issue_schema` entirely for that mode).

Also read, by `issue_draw_is_stale()` under `--if-stale`: the mtimes of `issue_graph.svg` and `issue_graph.html` themselves, and the mtimes of the same `issues/*nNNNN.toml` glob `issue_draw_read()` walks. Neither file existing counts as stale.

Written: `issue_graph.svg` and `issue_graph.html` in the output directory — the NAMED constant `OUT_DIR` = `<repo>/work/graph/` when drawing from `issues/`, or beside the given `graph.json` when drawing from a snapshot. **Neither output file is tracked by git** (`.gitignore`, R365): they are rebuilt at every close that needs them and committed by nothing, so a tracked copy would sit permanently dirty. The directory ships EMPTY, via `packaging/scaffold/work/graph/README.md`. Always this one stem — see NOTES for the retired `graph-live.*` pair and the `graph.*` → `issue_graph.*` rename. The script explicitly never writes into `issues/` itself.

## NETWORK ACCESS
None. The generated HTML is deliberately self-contained (SVG inlined) so it needs no network access to view either.

## HUMAN I/O
Stdout only, no stdin. Prints the node-source summary, any unknown-id or working-set-pulled-node notices, then three closing lines: what the picture shows (`describe()`), the output paths with the SVG's byte size and canvas dimensions, and the HTML's `file://` address. `coordinator/circle.py` captures this stdout and echoes it verbatim onto the command channel, so these lines are read by a person at a shell and by a person at a close, and are written once for both. The one exception is the leading `source:` line, suppressed under `--if-stale`: a close has only one possible source and `describe()` already opens with the same node count. Exit codes: 2 if no path argument is given; 0 on a normal run (no other failure path returns non-zero — `_check_vocabulary()` calls `raise SystemExit` directly, at import time, if the edge-type legend and schema disagree, which is effectively a distinct failure exit before `main()` runs).

## OPERATION

### `issue_draw_read(d)`
    {
        for every issues/*nNNNN.toml file, load it via issue_schema; pull
        its id, label, unwrapped description/absence, evidence list
        (only entries whose source starts with "circle_"), edge list
        (excluding retired edges, tagging each as attested/retired by
        status), the set of parts that gave it evidence ("held"), its
        opened-at circle (with the "circle_" prefix stripped for display),
        and its status, into a dict keyed by node id.
    }

### `_check_vocabulary()`
    if (EDGE_STYLE's keys and issue_schema.EDGE_TYPES disagree in either
        direction) then {
        raise SystemExit describing exactly which types are missing from
        the drawn legend (drawn grey, unnamed) or obsolete in it
    }
    Run once at import time, immediately after being defined.

### `tier(depth)`
    {
        walk the TIERS table (spine >=8 circles, thread >=3, else thin)
        and return the first (name, colour) whose threshold the given
        depth meets.
    }

### `communities(g)`
    {
        build a weighted adjacency count over live edges (attested edges
        weighted 2x proposed), then run greedy modularity agglomeration:
        repeatedly merge the pair of communities that most increases
        modularity, deterministically (sorted evaluation order, ties
        broken by id), until no merge would help. Returns a node-id ->
        community-id map.
    }
    if (the graph has no edges at all) then { every node is its own community }

### `_fr(ids, adj, pos, iters, k, temp, anchor, pull)`
    {
        one run of the Fruchterman-Reingold force-directed algorithm:
        repulsion between every pair of nodes, mild attraction along
        edges, an optional pull toward an anchor point, and cooling
        temperature limiting how far a node can move per iteration.
    }

### `issue_draw_box(nid)` / `issue_label_wrap(lab, width, lines)`
    {
        issue_draw_box() computes a node's on-canvas footprint (from its evidence-
        derived radius and wrapped label width) for collision purposes.
        issue_label_wrap() greedily wraps a label's words into up to 3 lines of
        30 characters, truncating with an ellipsis if it still overflows;
        the docstring notes this widened from an earlier 24x2 layout that
        truncated 22 of 32 labels.
    }

### `separate(g, pos, rounds=600)`
    {
        hard overlap removal after force-directed layout: repeatedly
        checks every node pair's bounding boxes and pushes overlapping
        pairs apart along whichever axis needs less correction, stopping
        early once a pass makes no move.
    }

### `layout(g, seed=7)`
    {
        compute communities; lay each community out independently with
        its own force-directed pass and hard separation, normalise it
        into a rectangular span, measure its bounding box, then
        shelf-pack the community boxes (tallest first) into a canvas
        whose target aspect approximates 1.7:1 regardless of node count,
        so clusters never move relative to their own members and never
        overlap each other. Returns (positions, community map).
    }

### `esc(s)`
    { HTML/XML-escape ampersand, angle brackets and double quotes. }

### `build_svg(g, pos, inbound, comm)`
    {
        compute each node's evidence depth, fit the SVG viewBox tightly
        to the actual drawn extent (clamped to a reasonable aspect ratio)
        rather than a fixed canvas, draw dashed cluster-region boxes
        labelled by their highest-degree member, draw every edge (colour
        by type, dashed if not attested, arrowhead marker, shortened to
        stop at the target node's rim), draw every node (radius by
        evidence count, colour by tier, a dotted extra ring if it is a
        leaf, wrapped label text stroked white underneath for legibility,
        id and depth caption beneath), and finally a legend block
        describing each relation colour, the dashed/proposed convention,
        and the circle-size/leaf/centre encodings.
    }

### `build_html(g, svg, order, inbound, g_live, svg_live)`
    {
        build one HTML page embedding the given SVG (and, if a live-only
        variant was computed, a second hidden SVG plus a view-toggle
        control), and a side table with one row per node — id, label,
        circle/part summary, LEAF flag, description, absence, outbound
        relationships, inbound relationships (added after a bug where the
        panel only ever showed outbound edges even though `protects` in
        particular is a claim about the target), and an evidence
        <details> block. Inline CSS styles the layout and a three-state
        selection model (chosen node / its neighbours / everything else
        dimmed). An embedded <script> wires node/row clicks to a
        highlight-and-scroll function and, when both graph variants are
        present, a view-toggle that swaps which SVG is visible, filters
        table rows by data-live, and clears selection state on every
        switch (since a node selected in "all" may not exist in "live").
    }

### `issue_id_normalise(x)`, `working_set_argv_parse(argv)` — MOVED to `working_set_manager.py`, 2026-09-03
    (stage 10). This tool reads them as `WS.*`; --live stays retired here because the shared
    parser honours it only when handed a graph, and this tool hands none. As it was:

### (was) `working_set_argv_parse(argv)`
    for each argv token {
        if (it is "--working-set" followed by another token) then {
            split that following token on commas and include the ids
        } else if (it starts with "--working-set=") then {
            split everything after the "=" on commas and include the ids
        }
    }
    normalise and return every non-empty id collected.

### `issue_working_set_limit(g, chosen)`
    {
        partition chosen ids into those present in g (kept) and those not
        (reported as unknown); for every kept node, pull in any edge
        target not already kept (reported as pulled-in) — the walk is
        working_set_manager.working_set_pull() since 2026-09-03, handed the
        DIRECTED neighbours; build a trimmed
        copy of the graph containing only the kept-plus-pulled nodes, with
        every node's edge list filtered to only point at nodes still in
        that set (so no edge is left pointing at a node that was cut).
    }

### `newest_source(d)`
    {
        stat every issues/*nNNNN.toml file under d and return the largest
        mtime found; return 0.0 when the directory holds no node files at
        all. The glob is deliberately the same one issue_draw_read() walks: a
        file this does not count is a file whose change cannot make the
        picture stale.
    }

### `issue_draw_is_stale(d=ISSUES_DIR)`
    if (issue_graph.html is missing OR issue_graph.svg is missing) then {
        return True — a fresh install has no picture yet, and that is
        exactly the case the shipped-empty work/graph/ creates
    } else {
        return True when newest_source(d) is later than the EARLIER of the
        two output files' mtimes, else False
    }

    { STALENESS, NOT A CHANGE COUNTER — a counter records the routes
      somebody thought of, while this records what the picture is made of.
      Every route a circle can move the graph by lands here (a ruling typed
      at cmd>, an annotation, a [proposed: ...] row accepted at the vetting
      checkpoint, a status change, /issue-apply), and so does the case no
      counter reaches: a circle that changed the graph and was then
      ABORTED, whose rulings are already applied while the close that would
      have redrawn never ran. The next live close catches it, because the
      question asked is about the FILES and not about that circle. A hand
      edit in a text editor is caught the same way. }

### `describe(g)`
    {
        count the loaded nodes by their status field, and count every
        non-retired edge across the graph; return one line reading
        "<N> issues (<n> live, <n> lead, ..., <r> root), <M> live
        relations", with statuses ordered by descending count and then
        alphabetically, and the root count appended last (a SUBSET of the
        live count, not an additional status — R429,
        2026-09-01 — printed only when at least one node carries the
        `root` flag).
    }

    { Written for the COMMAND PANE at a close, where the reader is the
      person whose issues these are and has just finished a circle. It
      names what is IN the picture, in the graph's own status vocabulary
      (memory/issue_schema.py STATUSES), not what the renderer did. }

## BUGS
**The `sys.path` hop to `memory/` was wrong for eleven days and nothing noticed.** The line was
written as three `.parent` steps from `__file__` — correct from `coordinator/`, correct again from
`work/graph/`, and a hard `ModuleNotFoundError` in `_check_vocabulary()` at import time from
anywhere else. It survived the 2026-08-16 move of `issue_schema.py` into `memory/` because nothing
ran this script automatically; it was found only when the script was moved again. **Fixed
2026-08-27** by deriving `ROOT` once and building every path from it, so the count of hops appears
in exactly one place. It is worth stating plainly because the same defect had two instances in one
file: this is what a path written as a number of directory hops costs.

The rest of this page's defects are NOT ASSESSED. Until the 2026-08-27 sweep this was the only one
of the 38 man pages that existed in `coordinator/docs/` at that time with no `## BUGS` section at
all (40 as of 2026-09-01 — audit-register.md #43 found "38" read as a live count rather than that
sweep's own snapshot). An absent section and
an empty one are different claims — "nobody looked" is not "nothing was found" — so this states
which it is rather than asserting "None found" on a reading that never happened.

**The reason it was missed no longer holds, and that is the change.** The page's subject used to
sit in `work/graph/`, outside every module directory a sweep walks beside the docs; it did not
ship; and nothing invoked it. All three are now false: the script is `ui/issue_draw.py`, it ships,
and a live `/close` runs it. A defect here now reaches a recipient's own screen.

## NOTES
`graph-live.svg`/`graph-live.html` retired 2026-08-13, along with `--live`'s
effect on `working_set_argv_parse()`. They were a standalone rendering of the
live-status subgraph, written under a separate filename stem so a `--live`
run wouldn't clobber the full-graph `graph.html` (that clobbering was itself
a 2026-08-05 fix). But a default run (no `--working-set` named) already
computes that same live subgraph, lays it out independently, and embeds it
in `graph.html` behind a live/all toggle — found 2026-08-13, comparing the
two: same deterministic layout, same node set, so the standalone pair was a
second copy of a picture `graph.html` already contained, and it drifted —
last regenerated 2026-08-06 while `graph.html` had moved on to 2026-08-12.
Passing `--live` today is accepted, does nothing to the output, and prints a
note pointing at the toggle.

**Run at a close, 2026-08-27 (R365).** `coordinator/circle.py::issue_graph_redraw()`
shells out to `python ui/issue_draw.py issues/ --if-stale` at every LIVE
`/close`, positioned immediately after `vetting.proposal_vet()` and
immediately before `circle_close_mark()`. That position is the whole
design: both routes by which a circle moves the graph are complete by then
— the circle's own `issue_cmds` batch, applied a few statements earlier, and
whatever the vetting checkpoint has just accepted — and nothing after it
touches `issues/` (phase 2 writes `parts/` and `self/`). It is a subprocess
rather than an import because `ui/` is not on `circle.py`'s `sys.path` and
the dependency between the two directories runs the other way; the literal
string `"ui/issue_draw.py"` in that call is also what `packaging/scan.py`
resolves in order to ship this script and this page at all.

**It cannot fail the close.** Any non-zero exit or exception becomes one
line on the command channel — `issue graph: not redrawn (...)` — and the
close carries on to collect short_terms. This is a picture; nothing reads it
back, and the BUGS section above is the reason that contract was written
rather than assumed. An `/abort` returns before this point and leaves the
picture stale on purpose; the next live close redraws it, because
`issue_draw_is_stale()` asks about the files rather than about that circle.

**Moved from `work/graph/` to `ui/`, 2026-08-27 (R365), and it SHIPS.** It stopped
being a development tool the day a close started running it: the picture is
for the person whose issues these are, so the script lives with the rest of
what that person is given, and this page moved with it from
`coordinator/docs/` to `ui/docs/`. Its four siblings stayed behind in
`work/graph/` — `command_flow_draw.py`, `prompt_grammar_draw.py`,
`coordinator_draw.py`, `system_architecture_draw.py` all draw the CODE, for
whoever is building it. This one draws the RECORD. The output stayed in
`work/graph/` alongside theirs (the operator, 2026-08-27: one folder, not two), and
`OUT_DIR` became a named constant in the same change, because it had been
derived from `__file__` and would otherwise have silently followed the
script into `ui/`.

**Moved from `coordinator/` to `work/graph/`, 2026-08-13.** `issue_draw.py`
is a development tool — a picture for a human to read, nothing a part or a
gate ever reads back — so it now lives beside its own output, alongside its
siblings `command_flow_draw.py` and `prompt_grammar_draw.py`. Its own
`sys.path` setup was updated to still find `issue_schema` in `coordinator/`
(it can no longer rely on Python's automatic script-directory entry landing
there). `issue_status.py` no longer runs it as part of its post-status-change
chain (see `issue_status.md`), and it no longer ships — its `packaging/
additions.toml` entry, and this man page's own entry, were both removed.
This doc stayed in `coordinator/docs/` rather than moving with the script,
since neither sibling had one there to match.

**Both of those last two sentences are history now**, and are kept because
they say what the 2026-08-27 move above reversed: the script ships again,
and this page moved with it. Neither needs a `packaging/additions.toml`
entry this time — `circle.py` names `ui/issue_draw.py` as a path literal, so
`packaging/scan.py` resolves the script by its dependency walk and this page
by the docs-partner rule that follows a shipped module with a `__main__`.
The hand-kept register is not involved, which is the better outcome: an
entry there is a claim someone has to remember to withdraw.

**Output renamed `graph.*` → `issue_graph.*`, 2026-08-13**, same day as the
move above. `graph.svg`/`graph.html` named no graph in particular — nothing
in `work/graph/` disambiguated it from `command_flow.*` or
`prompt_grammar.*`, its two siblings there. The NOTES paragraphs above
describing the `graph-live.*` retirement predate this rename and still say
`graph.html`, accurately, for the file as it was named at the time; every
current-behaviour section elsewhere in this doc has been updated to
`issue_graph.*`. Old `graph.svg`/`graph.html` removed from the tree; the
script run once immediately after the rename to produce
`issue_graph.svg`/`issue_graph.html` in their place.