# ISSUE_STATUS.PY(1)

## NAME
issue_status.py — change one or more nodes' status as a single atomic act: the status write, the file rename, and the audit-trail history line together, refusing if it would break graph closure, then regenerating the derived views.

## SYNOPSIS
    python memory/issue_status.py nNNNN nMMMM --to lead --ruled "the words that decided it" [--source REF] [--dry-run]

## DESCRIPTION
`issue_status.py` implements "operation 7" of the project's `operations.md`, along with its two mandatory consequences (operations 8 and 9), as one program rather than three separate hand edits. The docstring's argument is that a status change is measurably never a single write: setting `status` is the decision (Self's), renaming the file to match its new status prefix is clerical, and appending a description-history line explaining the change is also clerical — but the rename is the only one of the three the gate (`issue_gate.py`) would catch if it were forgotten, and a missing history line is otherwise silent even though it is "the one field that records why any of the rest is as it is." The design principle stated explicitly: "A consequence must never be able to occur without its decision," and — deliberately going further — the inverse holds too, so the decision cannot occur without its consequences either; one call performs all three, or none.

Before writing anything, the script checks graph closure: since an edge is legal only when both of its ends are live, demoting a node out of `live` can invalidate an edge belonging to some other node this command was never pointed at, and any such break is refused outright rather than silently repaired — retiring the offending edge is treated as its own separate ruling, and inferring it here would be the program making a decision that belongs to a human.

After a real (non-dry-run) status change, the script also re-runs a fixed chain of downstream generators — today two: `issue_index.py`, `issue_gate.py`. A third, `check_issues.py --project`, was removed from this chain 2026-08-11 alongside `self/circle_briefing.md`'s own retirement: that step used to regenerate the file circle_objectives was read from, and the docstring originally framed the whole chain as needed because "a demoted node would otherwise keep being presented to the room as live until the next scheduled nightly run." `circle.py::build_briefing()` now reads `issues/*.toml` directly at prompt-assembly time, so a status change is reflected the moment the next circle opens — there is no projection step left to miss. A fourth, `issue_draw.py issues/`, was dropped 2026-08-13: `issue_draw.py` is a development tool — a picture for a human to read, nothing a part or a gate reads back — so it moved to `work/graph/` beside its own output and is no longer auto-regenerated; run it by hand when the picture is wanted current.

## MAIN
    parse arguments: one or more node ids, required --to (a legal status),
    optional --ruled text, optional --source, optional --dry-run;

    load every node in the graph (_load_all());
    if (any given node id is not in the graph) then {
        print "no such issue: <ids>"; return 2
    }
    if (any given node already has the target status) then {
        print "already `<status>`" listing them; return 2
    }
    if (moving the given nodes to the target status would leave any edge
        with a non-live end — checked in BOTH directions, since an edge
        pointing at a moving node can live in another node's own file — via
        _closure_breaks()) then {
        print a REFUSED message listing every breaking edge and an
        instruction to retire the edge first; return 1
    }

    build today's date and the shared description-history line (with
    Self's stated ruling and source circle/session, if given);
    for each moving node, sorted {
        compute its old status (before mutation) and destination path;
        set its status field in memory and append the history line to its
            description_history;
        print the transition and the planned rename and history excerpt;
        if (--dry-run) then { skip to the next node without writing }
        if (the destination path differs from the current path) then {
            attempt `git mv` first (so the rename is recorded as a rename,
                preserving file history, rather than a delete+add);
            if (git mv fails — untracked file or no repo) then {
                fall back to a plain filesystem rename
            }
        }
        save the mutated document (via issue_schema.save) to the
            destination path
    }

    if (--dry-run) then {
        print "nothing written"; return 0
    }

    for each of the two downstream scripts, in a fixed order {
        run it as a subprocess;
        print the script's own designation and the last two lines of its
            combined stdout/stderr;
        if (it exited non-zero) then {
            print a warning that the writes are already on disk, the
                graph may now be inconsistent, and `git checkout issues/
                self/` reverts them;
            return 1
        }
    }
    return 0

## COMMAND-LINE ARGUMENTS
- `nodes` (required, one or more positional arguments): the node ids to move, each a bare id like `nNNNN`.
- `--to STATUS` (required): the target status; must be one of `issue_schema.STATUSES` (live/root/settled/declined/retired/lead).
- `--ruled TEXT` (optional, default empty): the human's own words explaining the ruling, written verbatim into the history line if given.
- `--source REF` (optional, default empty): the circle or session identifier the ruling was made in, recorded in the history line if given.
- `--dry-run` (optional flag): compute and print the full plan (transitions, renames, history excerpts) but write nothing and skip the downstream regeneration chain entirely.

## DEPENDENCIES
Standard library: `argparse`, `datetime`, `pathlib`, `subprocess`, `sys`, `__future__.annotations`. Sibling modules: `identity` (as `ID`, for `ID.DISPLAY` — a fixed, non-identifying display string, "Self," written into the history line as "Ruled by Self." Before R132 (2026-08-11) this line called `ID.user_name()`, a per-installation configurable label; that ruling closed personalization for anything reaching a prompt, since a node's provenance text is read directly into circle_objectives (`circle.py::build_briefing()` via `check_issues.block()`)); `issue_schema` (as `S`, for `S.nodes()`, `S.load()`, `S.path_for()`, `S.save()`, `S.STATUSES`, `S.ROOT`). External program: `git` (invoked via `subprocess.run(["git", "mv", ...])` for renames that preserve file history) and Python itself (`sys.executable`, to invoke the two downstream coordinator scripts as subprocesses).

## EXTERNAL FILES
Read: every `issues/*nNNNN.toml` node file, via `issue_schema` (`_load_all()`).

Written: the TOML file for each node being moved, at its new status-prefixed path (via `issue_schema.save()`), with the old path removed via `git mv` or a plain rename when the destination path differs — all skipped entirely under `--dry-run`. Indirectly, whatever the two downstream scripts (`issue_index.py`, `issue_gate.py`) themselves write, run as a fixed chain immediately after a real (non-dry-run) status change.

## NETWORK ACCESS
None directly. (The downstream scripts it invokes are not verified here beyond their designations; other docs in this set describe `issue_gate.py` and `issue_index.py` as read-only/local.)

## HUMAN I/O
Stdout only, no stdin. Prints unknown-node and already-at-status errors, a REFUSED closure-violation report with each breaking edge listed, a per-node transition/rename/history-excerpt trace, a dry-run confirmation, and — on a real run — the designation and tail output of each downstream script as it runs, plus a recovery hint if one of them fails. Exit codes: 2 for an unknown node id or a no-op (already at target status); 1 for a closure-violation refusal, or for a downstream script failing after the graph writes already landed; 0 for a completed dry run or a fully successful real run.

## OPERATION

### `_load_all()`
    { load every issues/ node via issue_schema, keyed by its id, each
      value the (path, parsed-document) pair. }

### `_closure_breaks(g, moving, to)`
    if (the target status is "live") then { return no breaks — moving
        something TO live can never violate the both-ends-live rule }
    for each node in the graph {
        for each of its non-retired edges {
            if (neither this node nor the edge's target is among the
                nodes being moved) then { skip — irrelevant to this move }
            compute the "other" end(s) of the edge not being moved;
            if (every other end is currently live) then {
                this edge WOULD break once the moving end(s) leave live
                status — record it, noting whether it belongs to the
                moving node's own file or to another node's file
            }
        }
    }
    return every recorded breaking edge description.

### `_history_line(to, ruled, source, today)`
    {
        build a Markdown bullet: today's date, the new status, "Ruled by
        Self" (ID.DISPLAY, a fixed non-identifying string — R132, 2026-08-11,
        closed the previous ID.user_name() call as a personalization
        channel into a node's provenance text, which reaches every part's
        prompt directly), the source circle/session if given, and the
        ruling's own words in quotes if given. Old history lines written
        before R132 with a personal name are left as they are; only what
        this function writes going forward changed.
    }

## BUGS
None found. The module's own comment at the "was = doc["status"]" line explicitly documents and forestalls a bug it is careful to avoid — reading the old status *before* mutating the dict, noting the alternative "printed `lead -> lead`" — so the trap it warns about is already handled correctly in the code as written.
