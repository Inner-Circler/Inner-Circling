# DEPENDENCY_MANAGER.PY(1)

## NAME
dependency_manager.py — the DEPENDENCY map: what still leans on a record when it is about to be
removed, and the plan that removes or preserves each dependent first. Report only here; the
removal verbs and the vetting loop act on a plan. Ruled R570 (2026-09-15).

## SYNOPSIS
    python coordinator/dependency_manager.py --of <id-or-Tag> [--kind <kind>] [--json]

    import dependency_manager as DM
    DM.dependency_dependents_read(kind, ident)       one hop, read only
    DM.dependency_plan(kind, ident)                  the transitive plan, cycle-safe
    DM.dependency_plan_is_blocked(plan)              a REMOVE step or a ring blocks the act
    DM.dependency_plan_render(plan)                  the lines Self reads
    DM.dependency_ids_read(row) · dependency_placeholders_read(row) · dependency_ring_find(rows, id, deps)
    DM.dependency_target_parse(text[, kind])

## DESCRIPTION
The operator, 2026-09-15: *"Can an action that would break a dependency be determined, and the
dependency(s) be staged for explanation, vetting, and prior removal? And the final action be
automatically rejected if its dependencies are not removed?"* — *"build the whole thing,
preserve what is requires so as not to break anything."*

THE MAP IS DECLARED, NEVER DISCOVERED. `REFERENCES` names every field in the record that points
at another record's id, what it points at, and what a removal of the target does to the holder:

    remove     the holder must go first, by its own verb. An issue-relationship whose end would
               stop being live — the closure rule issue_status.py already refuses on. The
               dependent carries the line that removes it.
    preserve   the holder stays, on purpose. A retired part's quotes stay attributed (a quote is
               that part's own words, marked retired); a practice addressed to it stays the
               record and reaches no prompt while it is retired; an observation chain keeps its
               shell (purge keeps the id, so a chain onto it never breaks); a coalesce group is
               provenance, never a dependency.
    cascade    a proposal that depends on a denied one is denied with it — the vetting loop's
               rule, listed here so the plan says it.
    handled    the removal verb does it itself — /part-retire takes the name off the group's
               roles in the same act.

A reference the map does not declare does not exist to the walker: a self-reference enters only
where a record shape says so.

THE PLAN. `dependency_plan(kind, id)` walks the REMOVE dependents transitively, leaves first —
a dependent's own dependents before it — with a visited set and an on-stack set, so a back edge
is a RING reported as one group (ruled together or not at all) and nothing is walked twice.
Preserved, handled and cascade dependents are listed, never acted on. A plan with a REMOVE
step or a ring BLOCKS the final act. Today every REMOVE dependent is an issue-relationship,
which has no dependents of its own, so the walk is one hop deep; the walker is general because
the map will grow.

WHO ACTS ON IT. A removal verb (issue-status to a non-live value, part-retire, practice-delete,
observation-retire, observation-purge) asks for the plan first. Preserved-only: the verb keeps
its own contract and notes what is preserved. Blocked: the verb refuses the act and stages the
plan as proposals — each REMOVE step, then the removal itself depending on all of them — so
the dependents are explained, vetted and removed first at the next checkpoint, and the final
act is denied by cascade if any of them is denied (proposal_vetting.py). The `<proposal>`
row's `depends_on` carries "P-n" or "P-n:<token>"; a ring is refused at staging.

## MAIN
`--of <id-or-Tag>` prints the plan and writes nothing. The kind is inferred from the id's
prefix (n → issue, BP- → practice, CO-/SO- → observation, TP- → topic, P- → proposal; anything
else a part's Tag or directory), or given with `--kind`. `--json` prints the plan too. Exit 0
with a plan, 2 on usage.

## COMMAND-LINE ARGUMENTS
    --of <text>       the record
    --kind <kind>     issue | issue-relationship | practice | better-option | observation | part | topic | proposal
    --json            print the plan as JSON after the text

## DEPENDENCIES
    issue_index                 issue_index_read — labels, statuses, edges, who holds quotes
    practice_manager            practice_read — addressees
    circle_observation_manager  circle_observation_read — chains
    proposal_manager            proposal_read — depends_on
    proposal_group_manager      proposal_group_read — members (public since 2026-09-15)
    part_add                    part_rows_read — the roster
All late, through `READERS`, which a probe swaps for synthetic data.

## EXTERNAL FILES
Read: the bound group's issues, best_practices, circle_observation_log, proposals, coalesce and
parts/ — each through its own reader. Written: nothing.

## NETWORK ACCESS
None.

## HUMAN I/O
The CLI prints; nothing is asked.

## OPERATION

### `dependency_plan(kind, ident)`
    walk(k, i):
        if (k i is on the stack) then { record the ring from there; return }
        if (visited) then { return }
        mark visited; push
        for each dependent of (k, i):
            remove   -> walk(dependent) first, then append it once
            preserve / handled / cascade -> list it
        pop
    return {target, remove (leaves first), preserve, handled, cascade, rings}

### `dependency_ring_find(rows, new_id, new_deps)`
    the depends_on graph of `rows` plus the new row; a depth-first walk from new_id that meets
    itself returns the ring as ids, else [] — the register refuses a row that would close one.

## BUGS
None known. Two observations from the first build: a part is resolved by Tag or directory,
case-insensitively, and an unknown name is looked up as given (it will simply have no
dependents); and `issue_index_read` reads every node, so a plan over a large graph is a full
read — acceptable at a checkpoint, and nothing here caches.
