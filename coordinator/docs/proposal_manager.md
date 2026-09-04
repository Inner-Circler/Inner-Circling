# PROPOSALS(1)

## NAME

proposal_manager.py — the PROPOSE register: what a part has asked Self to rule on, and what Self ruled.

## SYNOPSIS

    python coordinator/proposal_manager.py

(As a library: `entries()`, `by_id(id)`, `pending()` for the vetting queue, `proposal_row_stage(kind, text, sources, circle)` when a circle closes, and `proposal_approve(id)` / `proposal_deny(id)` / `proposal_supersede(id, circle)` when Self rules.)

## DESCRIPTION

When a part wants something to change, it does not change it. It writes `[proposed: <command>]` in its own statement, and that stages a row here for Self to rule on later. This register is the one place those futures accumulate. R202 put it plainly: the propose class, its syntax and its code subsume every possible future, including a plain request.

The register replaced two earlier ones that never shipped a real row between them — a request register and a relationship-proposal register — folded into a single id space, `P-N`.

**A row is one of two kinds, and the difference is what approval does.**

    command   the text parses as a real command — the same syntax a valid
              command-pane input would use. Approving it RUNS it.
    text      free-form. Approving it is a pure record: Self has read it and
              marked it considered. Nothing executes. This is exactly what a
              "request" always was.

Since R273 only the first kind is ever staged — a proposal body that is not a proposable command is malformed at the moment it is uttered — but the row schema still accepts both, and the fixtures still exercise the second.

**A command row is re-parsed fresh at approval time**, never approved from a stored, pre-parsed snapshot. The graph a proposal targets may have moved between the circle that staged it and the circle that rules on it — an endpoint retired, say — and re-parsing against the live grammar each time is what catches that.

**Nothing here touches the issue graph.** The graph-writing half of approving a command row lives in the circle driver; this module stays a pure register that knows only its own state. `proposal_approve()` and `proposal_deny()` are called only after that orchestration has already succeeded — or, for a text row, immediately, because there is nothing else to satisfy.

**Rulings are tombstones.** A denied or superseded row keeps its place on file with its state naming who ruled and when. A closure that leaves no trace cannot be told apart from one that never happened.

**The first proposer gets the credit.** `sources` lists every speaker whose stance converged on the proposal, kept in first-appearance order rather than alphabetically, and `author` is stamped at staging with the first of them as "<who> in <circle>". A later ruling leaves a non-blank author alone, so the credit survives; everyone else stays on record in `sources`.

**Staging fields are dropped the moment a row settles.** A resolved row carries only its id, kind, text, state and author — the same discipline every propose-class register here follows.

## MAIN

    Print a blank line, then how many proposals are pending and how many exist
    in total, then the listing.
    return 0.

Takes no arguments.

## COMMAND-LINE ARGUMENTS

None. The module is a read-only viewer from the command line; every write happens through the library functions, called by a circle.

## DEPENDENCIES

`REGISTER_CLASS` for the register's path, load and save. `PROPOSE_CLASS` — the shared PROPOSE-class base that owns id allocation, pending lookup, provenance backfill, accept and deny, so that behaviour has exactly one definition across every propose-class register. `datetime`, `pathlib`, `sys`. `memory/` is added to the import path for the issue-graph code the wider flow uses.

The shared base is configured with lambdas rather than values on purpose: test harnesses swap this module's path and document functions as attributes, and lambdas re-read those globals on every call so the substitutions keep working.

## EXTERNAL FILES

    self/proposals.toml    READ by every verb; WRITTEN by proposal_row_stage(), proposal_approve(),
                           proposal_deny() and proposal_supersede().

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout; reads no input. Standard output is reconfigured to UTF-8 with replacement on import.

## OPERATION

### entries() / by_id(pid) / pending()
Every row in file order; one row by id; and every row still awaiting a ruling. The vetting queue reads `pending()` and nothing else.

### circle_ref(circle)
    if (the value is empty, or already starts with a known transcript prefix)
        then { return it unchanged. }
    else { return it with "circle_" prepended. }

The register carries the transcript's own name rather than a bare open time, so a row is greppable and provenance backfilled from it cites a real file. Rows staged before that ruling carried the bare open time, which is why vetting re-runs this same normalisation over every row it approves — a healing guard for any bare row arriving from a backup or a hand edit.

### proposal_row_stage(kind, text, sources, circle)
    Load the register and allocate the next P- id.
    Keep the sources in the order given.
    Normalise the circle to its prefixed transcript reference.
    Stamp author as "<first source> in <circle ref>".
    Append the row with state "proposed" and the staging fields, save, and
        return the new id.

### proposal_approve(pid)
Flips the state to accepted, backfills the author if it is blank, and drops the staging fields. For a command row that writes the graph, the caller must already have prechecked and applied it successfully; this only records the ruling.

### proposal_deny(pid)
Tombstones the row. Never touches the graph — there is nothing to undo, because a denied proposal was never applied.

### proposal_supersede(pid, by_circle)
    Find the row and confirm it is still pending.
    if (it is not) then { return (false, the reason). }
    Backfill a blank author from the row's own provenance.
    Set state to "superseded by Self's direct ruling in <circle> <timestamp>",
        drop the staging fields, save.
    Return (true, a line saying Self ruled it in the room).

For a pending row Self has already ruled directly, in the circle, by speaking the command. Tombstoned like a denial and never touching the graph, because the direct ruling already did whatever the row was asking for.

### proposal_list() (`listing()` before the B99 re-homing, 2026-09-03)
    if (there are no rows) then { return "  no proposals". }
    Print PENDING first — what needs a ruling — then SETTLED, each row as its
    id, its kind or state, and the first 60 characters of its text.

## BUGS

None found. One removal worth recording rather than repeating: a module-level provenance delegate used to sit here with zero callers, five lines that existed only to be mistaken for a hook. It was deleted; the one copy lives in the shared base.
