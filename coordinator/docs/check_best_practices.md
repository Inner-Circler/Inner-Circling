# CHECK_BEST_PRACTICES.PY(1)

## NAME
check_best_practices.py — the one reader/writer for `self/best_practices.toml`: a merged register of circle-facing practices and Self-facing "better options," with its own CRUD surface, the resolution half of a staging/vetting pipeline, and a verifier.

## SYNOPSIS
    python coordinator/check_best_practices.py

Everything else this module offers (`add`, `delete`, `listing`, `pending`, `render_stage`, `approve`, `deny`, `broadcast_block`, `narrowcast_block`, and the read helpers `practices`/`by_id`/`eligible`/`broadcast`/`narrowcast`) is a Python function called by another program — `commands.py`'s `/practice-add`, `/better-option-add`, `/practice-list`, `/practice-delete`; `prompt_build.py` at prompt assembly; `inter_circle.py`'s SYNTHESIS; the vetting loop — there is no further command-line surface.

## DESCRIPTION
This module was rewritten 2026-08-11 (rulings R133 through R137), collapsing what had been three separate registers and a rendered-file dependency into one TOML file read and written from exactly one place. Before that rewrite, this file held ONLY circle-facing practices, each addressed by a literal `**<Addressee>** —` text prefix that `circle.py` scraped out of a rendered `self/circle_briefing.md`. Two rulings changed that: R133 merged `self/better_options.toml` — "how Self moves" — in as records whose `addressee` field is `"Self"`, on the reasoning that a "better option" is not a second kind of record, it is what a practice addressed to Self is *called*; R134 retired the literal `**<Addressee>** —` prefix entirely, since the TOML now has a real `addressee` field to route on, and `circle.py` no longer reads `self/circle_briefing.md` for practices at all (nor, as of the file's own further retirement the same day, for anything else — see `docs/BNF.md` BLOCK 2). R135 collapsed what gets projected into a part's prompt down to a record's `title` field alone, never the whole record — `origin`, `in_room`, `kind`, and `record` are read by Self and by whoever revises or cites an entry, never spent as prompt tokens. R136 unified what had briefly been two record shapes (`plain_practice`/`self_practice`) back into one `<practice>` production, now that every record shares the same field set. R137 moved crisis safety content (a helpline number and text-line short code) out of this register entirely and into `coordinator/process_core.md` as static, unconditional text — it had been living inside a better_option's `in_room` field, which R135's title-only projection rule would otherwise have silently stopped surfacing.

A record's addressee is one of "All parts" (broadcasts to BLOCK 1, `circle_identity`, read by every part), "Self" (also broadcasts to BLOCK 1 — deliberately, so the room can reinforce or suggest evolutions in how Self moves), or a specific part's tag (narrowcasts to that part's own BLOCK 3, `part_identity`, alone). A record also carries staging fields (`state`, `op`, `target_id`, `sources`, `circle`, `proposed_at`) that exist only transiently, while a staged row awaits Self's ruling. Once a staged row is approved, denied, or has a revision applied, its staging fields are stripped, leaving a settled record indistinguishable from one Self typed directly via `/practice-add` — except that a denied row keeps a `state` of `"denied by Self <datetime>"` as its tombstone (ruled 2026-08-12: a denial that leaves no trace cannot be told apart from one that never happened).

**What stages a row here changed on 2026-08-20 (B60).** The in-circle annotation path — the six `[proposed practice: ...]`/`[proposed better_option: ...]` bracket spellings, coalesced by `markers.py` and written straight into this register as `state = "proposed"` rows through a `stage()` function here — is retired. A part proposes a practice as `[proposed: /practice-add <text>]` (or `/better-option-add`), which is staged into `self/proposals.toml` and, when Self approves it, RUNS the command — that is, calls `add()` below — so this register gains a row only once the proposal has been ruled. `stage()` was deleted with its only callers. What remains of the staging half here: `render_stage()`, a PURE renderer `inter_circle.py`'s SYNTHESIS uses to stage BLOCK 1 candidates through its own transaction; and `pending()`/`approve()`/`deny()`, which still rule any `state = "proposed"` row however it got here — rows staged before B60 are still pending and still have to be rulable.

The simple resolution paths and every read go through `propose_class.ProposeClass`, the shared PROPOSE-class base (docs/HELP_DESIGN.md §6, built 2026-08-16), instantiated at module level as `_PC` with this register's own table name, field order, staging-only fields, id format (`BP-NNNN`), author field (`origin`), clock (`_now()`, UTC) and a post-mutate hook (`_sync_tally`) that keeps the file header's `**Entries: N**` claim true on every save. The lambdas it is built from re-read this module's globals on each call, so the test harnesses' practice of swapping `BP` and `_doc` as module attributes keeps working. Only `approve()`'s op dispatch (add/revise/delete) stays this module's own.

**`kind` gained an enforced half of its correlation with `addressee` on 2026-08-31 (R421/B90).** R136 (2026-08-11) left `kind` free-text, populated on rows descended from the pre-merge `better_options.toml` and empty on most others, with nothing checking the correlation. A debate over whether to merge the best-practices/better-options split away entirely (R421) surfaced that gap as one of the split's weaker points — decided to keep the split, but to stop leaving `kind` unenforced. `_kind_check()` now fails a row whose `kind` is non-empty and whose `addressee` is anything but `"Self"`. It is deliberately one-directional: every row carrying a `kind` today is addressed to Self, but plenty of `addressee = "Self"` rows (migrated wholesale from `self.md`'s Active threads, 2026-08-15) still carry `kind = ""`, so the reverse implication does not hold and is not checked.

## MAIN
    main():
        if (self/best_practices.toml does not exist) then {
            print "FAIL  ... does not exist"; return 1
        }
        read the raw file bytes; if (CRLF line endings are present) then {
            record a failure — the rest of the tree is LF
        }
        load the parsed document; if (next_id is missing or not an int)
        then { record a failure }
        read the header's stated "**Entries: N**" tally via regex over the
        raw text; if (absent) then { record a failure } else if (N does
        not match the actual entry count) then { record a failure — "it
        records the count, it does not cap it" }
        if (there are no entries at all) then { record a failure }
        for each record:
            if (its id does not match BP- followed by four or more digits)
            then { record a failure } else if (the id was already seen)
            then { record a failure } else if (next_id is an int and the
            id's number >= next_id) then { record a failure — next_id has
            fallen behind }
            if (state is present and not a string) then { record a
                failure — a hand edit lost the quotes (an unquoted TOML
                date here crashed prompt assembly until 2026-08-18) }
            else if (state is present and is neither "proposed", nor
                starts "accepted by Self ", nor starts "denied by Self ")
                then { record a failure }
            if (state is not "proposed") then { for each staging-only
                field (op, target_id, sources, circle, proposed_at): if
                (present) then { record a failure — should have been
                dropped on resolution } }
            if (state == "proposed") then {
                if (op is not add/revise/delete) then { record a failure }
                if (op is revise or delete) then { if (target_id is
                    missing) then { record a failure } else if (no record
                    has that id) then { record a failure } }
                if (op == "add") then { if (addressee is not a known one)
                    then { record a failure }; if (title is blank) then {
                    record a failure — nothing to accept } }
            } else {
                if (addressee is not a known one) then { record a failure }
                if (title is blank) then { record a failure — nothing
                    would project }
            }
        append every failure _kind_check() reports
        append every failure _routing_check() reports
        print a summary: settled count by addressee; the pending count if
        any; block 1's projected size; each part's block 3 size if
        non-empty
        if (any failure was recorded) then { print the numbered list;
            return 1 } else { print PASS; return 0 }

## COMMAND-LINE ARGUMENTS
None recognized. Running the file directly always executes `main()`'s verification pass; there is no flag parsing.

## DEPENDENCIES
Standard library: `pathlib`, `re`, `sys`, `datetime` (imported locally inside `_now()`), `copy` (imported locally inside `render_stage()`), `__future__.annotations`. Sibling modules: `self_schema` (as `SS`, for `SS.load()`/`SS.save()` — the shared TOML register reader/writer, preserving field order via the `ORDER` tuple); `roster` (as `R`, for `R.TAG_BY_DIR` and `R.ALPHA_DIR_NAMES` — the roster's directory-to-tag mapping and canonical part ordering, used to build `PART_ADDRESSEES` and to iterate every part when checking routing); `propose_class` (the shared PROPOSE-class base every read and simple resolution path delegates to); `paths` (for `BEST_PRACTICES`, the register's path — `BP` in this module since 2026-08-16). `memory/` is put on `sys.path` for the issue-graph code (R203).

## EXTERNAL FILES
Read: `self/best_practices.toml`, via `self_schema.load()` — every function in this module that reads the register goes through `_doc()`, which calls this (directly, or through `_PC.entries()`).

Written: `self/best_practices.toml`, via `_PC.save()` → `self_schema.save()` — by `add()`, `approve()`, `deny()` and `delete()`. `_PC.save()` runs `_sync_tally()` first so the header's `**Entries: N**` claim is accurate before every save. `render_stage()` writes nothing (it returns a modified COPY of the document for its caller to stage). `main()` itself writes nothing; it is read-only.

## NETWORK ACCESS
None.

## HUMAN I/O
`main()`: stdout only — a summary line, a pending-count line if applicable, per-block size lines, and either a PASS line or a numbered FAILURE list. Exit 0 on a clean pass, 1 on any failure. No stdin. The mutation functions (`add`, `approve`, `deny`, `delete`) return `(bool, message)` tuples for their own callers to print or act on — they do not print anything themselves; `render_stage()` returns `(doc, pid)`.

## OPERATION

### `_doc()`
    {
        Load the register via self_schema, or return a fresh empty
        document shape (register name, next_id=1, empty practice list) if
        the file does not exist yet.
    }

### `practices()`
    { Return every parsed record — the one reader every other function in
      this module (except the raw main() TALLY check) goes through.
      Delegates to _PC.entries(), resolved at call time. }

### `by_id(pid)`
    { Linear search for a record by its id, through _PC; None if not
      found. }

### `eligible(p)`
    { True when the record's state is absent, or is a string starting
      "accepted by Self" — never a pending proposal, and never a denial
      tombstone. The isinstance test is deliberate: an unquoted TOML date
      in `state` is a non-string and projects nothing rather than
      crashing prompt assembly; main() reports it. }

### `broadcast()` / `narrowcast(part_tag)`
    {
        broadcast(): every eligible record whose addressee is "All parts"
        or "Self". narrowcast(part_tag): every eligible record whose
        addressee equals that exact tag.
    }

### `broadcast_block()`
    if (there are no eligible "All parts" or "Self" records) then {
        return ""
    } else {
        emit a "## Best practices" heading, one bullet per "All parts"
        record's title; if any "Self" records exist, emit a
        "### Better options (for Self)" subheading with one bullet per
        their title
    }

Called directly at prompt-assembly time for BLOCK 1 — nothing renders this into `self/circle_briefing.md` or any other intermediate file.

### `narrowcast_block(part_tag)`
    if (the part has no eligible narrowcast records) then { return "" }
    else { emit "## Your best practices" plus one bullet per title }

Empty for most parts, most circles. Sourced directly from this module for BLOCK 3 — there is no per-part slice of a rendered file for a routing bug to leak through.

### `add(text, addressee=PRACTICE_ADDRESSEE)`
    {
        Collapse the text's line breaks into one line and strip it.
    }
    if (the result is empty) then {
        return (False, "nothing to add") — no verb name in the message:
        the caller (commands.py) names its own verb
    } else {
        allocate the next BP-id through _PC, append a record {id,
        addressee, title=the text VERBATIM (no bold forced on it, R134),
        origin="Self", in_room/kind/record empty}, save through _PC
        (which syncs the tally), and return (True, a confirmation naming
        the new id and a truncated title)
    }

`addressee` defaults to "All parts" (ruled 2026-08-05: a best practice is general and addressed to the whole circle). It GAINED the parameter 2026-08-20 rather than this module gaining a second function: `BETTER_OPTION_ADDRESSEE` ("Self") is the only other value, the row shape is identical, and `/better-option-add` passes it. This is the function an approved `[proposed: /practice-add ...]` ends up calling.

### `_now()`
    { The current UTC time as an ISO-8601 string to the second — the
      standard for every NEW stamp since 2026-08-16; naive-local stamps
      already in settled rows are history and stay as written. }

### `_sync_tally(doc)`
    { If the document's [doc] preamble carries "**Entries: N**", rewrite N
      to the live record count. Rides _PC's post_mutate hook so every save
      keeps the header true — main()'s TALLY check reads it back from the
      raw file, and the pre-commit hook runs main() at the end of the same
      /close that just wrote. }

### `pending()`
    { Every row whose state is "proposed" — the vetting queue; both
      checkpoints read this and nothing else. Delegates to _PC. }

### `render_stage(doc, op, *, addressee="", title="", record="", target_id="", sources=None, circle="")`
    {
        PURE. Deep-copy `doc`; allocate the next BP-id on the copy; append
        a row {id, addressee, title, origin="", in_room="", kind="",
        record, state="proposed", op, sources sorted, circle,
        proposed_at=_now()}, plus target_id only if non-empty; sync the
        copy's tally; return (the copy, the new id).
    }

The one staging renderer left here. `inter_circle.py`'s SYNTHESIS stages this render for its BLOCK 1 CANDIDATEs through its own transaction. `stage()` — this plus the write — stood beside it until 2026-08-20 and was deleted with the annotation path (B60) that was its only caller.

### `_provenance(row)`
    { Format a staged row's sources/circle into a fallback "who in
      which-circle" string, used only to backfill a settling record's
      origin field when it is still blank — never overwrites an
      already-present origin. Delegates to _PC.provenance(). }

### `approve(pid, title="")`
    look up the pending row by id through _PC.find_pending(); if (not
        found) then { return (False, "<pid> not found") }
    if (its state is not "proposed") then { return (False, "<pid> is not
        pending (state=...)") }
    if (op == "add") then {
        backfill origin from _provenance() if still blank; set state to
        "accepted by Self <now>"; strip all staging-only fields
    } else if (op is "revise" or "delete") then {
        look up the target row by target_id; if (missing) then { return
            (False, "target no longer exists") }
        if (op == "revise") then {
            overwrite the target's title with the given title override
            or the row's own proposed title; if (the result is empty)
            then { return (False, "no revision text") }
            backfill the target's origin from _provenance() if still
            blank; set the target's state to "accepted by Self <now>"
        } else {
            remove the target row outright
        }
        remove the staging row itself
    } else { return (False, "unknown op") }
    save through _PC (tally synced) and return (True, "<pid> approved (<op>)")

The `title` override is for an op=revise row whose proposed wording was non-unanimous and Self authors the final text at vetting time. No annotation syntax produces a revise or delete row any more (R270: "no successor"); this branch rules rows staged before B60.

### `deny(pid)`
    { Delegates to _PC.deny(): find the pending row (same refusals as
      approve); backfill origin from provenance if blank; set state to
      "denied by Self <now>"; drop the staging fields; save with the
      tally synced. The row is TOMBSTONED, not deleted (ruled 2026-08-12)
      — eligible() treats the tombstone as non-projecting. }

### `listing()`
    { Return a numbered, human-readable listing of every record (id,
      addressee, truncated title) for /practice-list to display, or
      "  no best practices" if empty. The number is positional, for
      /practice-delete's own argument, and is NOT the stable id — it
      shifts whenever an entry is deleted (which is why R271 forbids
      proposing one). }

### `delete(n)`
    { Remove the nth listed record (1-indexed); if n is out of range,
      return a failure tuple naming the valid range and pointing at
      /practice-list. Otherwise save through _PC (tally synced) and
      return a confirmation naming what was removed. }

### `_entry_line_in(title, block)`
    { True only when `block` carries `title` as a FULL rendered entry
      line ("- " + title), never as a substring of another line — bare
      substring matching produced a hook-blocking false positive
      (2026-08-19, tier 3 #29). }

### `_projecting_titles()`
    { The set of titles of every record whose state is None or an
      acceptance — re-derived locally, deliberately NOT through
      eligible(). A non-projecting row whose title equals a projecting
      twin's is an ACCEPTED DETECTION HOLE: text matching cannot tell the
      two lines apart, so such a twin is exempted from the leak check. }

### `_kind_check()`
    for each record:
        if (kind is a non-empty string, after stripping) then {
            if (addressee is not "Self") then { record a failure — kind
                is a better-option-only field }
        }
    return every recorded failure

One-directional (R421/B90): a non-empty `kind` off `addressee = "Self"` fails; an `addressee = "Self"` row with `kind = ""` does not, because the live register carries both.

### `_routing_check()`
    b = broadcast_block(); snapshot narrowcast_block() and narrowcast()
    once per roster tag; bcast = broadcast(); proj = _projecting_titles()
    for each part tag in the roster:
        mine = that part's snapshotted narrowcast_block()
        for every OTHER part tag:
            for each of that other part's own narrowcast records: if
            (its title appears in `mine` as a FULL rendered entry line,
            and this part has no own record with the same title) then {
            record a routing leak — this part received another part's
            narrowcast entry }
        for each of THIS part's own narrowcast records: if (its title is
        NOT found inside `mine`) then { record a failure — the part's own
        entry did not reach its own block }
        for each broadcast-eligible record: if (its title is not found
        inside `b`) then { record a failure — a broadcast entry is
        missing from broadcast_block() }
    for each record whose state is "proposed" or a denial, with a
    non-empty title:
        if (its title is in `proj`) then { skip — the projecting twin
            legitimately puts that line in the rendered text }
        if (its title appears in `b` as a full entry line) then { record
            a failure — a non-projecting row leaked into the broadcast
            block }
        for each part tag: if (its title appears in that part's
            snapshotted narrowcast_block() as a full entry line) then {
            record a failure — it leaked into a narrowcast block }
    return every recorded failure

This runs the real `broadcast_block()`/`narrowcast_block()`/`broadcast()`/`narrowcast()` functions against the real roster, not a model of either — the discipline traces to a prior real leak (E09) that a model-based check would not have caught, since the leak was in the actual filtering code, not in an assumption about it. Each real function runs ONCE per tag and its output is reused (2026-08-19, tier 5 #53); a snapshot of a real result is not a model. The non-projecting pass deliberately re-derives "non-projecting" rather than calling `eligible()`, so that a leak in `eligible()` itself is still caught (`test_routing_check_catches_a_leaked_proposed_row()` monkeypatches it to prove this).

## BUGS
None known. The O(parts × proposals) re-render recorded here until 2026-08-19 is resolved (tier 5 #53, above). This page was regenerated 2026-08-31 after R421/B90 added `_kind_check()`; the previous rendering (2026-08-20, after B60 deleted `stage()` and gave `add()` its `addressee` parameter) did not yet have it.
