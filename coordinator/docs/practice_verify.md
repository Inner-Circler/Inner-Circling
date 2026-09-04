# PRACTICE_VERIFY.PY(1)

## NAME
practice_verify.py — the VERIFIER of `self/best_practices.toml`. Named `check_best_practices.py` until
2026-09-03 (R435: verifiers take `_verify`), and until that day also the register's one reader/writer —
that half is `practice_manager.py` now: a merged register of circle-facing practices and Self-facing "better options," with its own CRUD surface, the resolution half of a staging/vetting pipeline, and a verifier.

## SYNOPSIS
    python coordinator/practice_verify.py

Everything this module offered BESIDES the verifier until 2026-09-03 (`add`, `delete`, `listing`, `pending`, `render_stage`, `approve`, `deny`, and the read helpers `practices`/`by_id`/`eligible`/`broadcast`/`narrowcast`) is `practice_manager.py`'s now — `practice_add`, `practice_delete`, `practice_list`, `practice_pending_list`, `practice_stage_render`, `practice_approve`, `practice_deny`, `practice_read`, `practice_read_by_id`, `practice_is_eligible`, `practice_broadcast`, `practice_narrowcast` — called by `commands.py`'s `/practice-add`, `/better-option-add`, `/practice-list`, `/practice-delete`; `inter_circle.py`'s SYNTHESIS; the vetting loop. The two BLOCK renderers (`broadcast_block`, `narrowcast_block`) left even earlier, 2026-09-02, for `process_core_prompt_projection.group_best_practices()` and `parts_prompt_projection.part_practices_render()`. What is defined HERE is `_entry_line_in`, `_projecting_titles`, `_kind_check`, `_routing_check` and `main` — there is no further command-line surface. The DESCRIPTION below is the register's account and reads as it did before the split; the names in it are `practice_manager.py`'s.

## DESCRIPTION
This module was rewritten 2026-08-11 (rulings R133 through R137), collapsing what had been three separate registers and a rendered-file dependency into one TOML file read and written from exactly one place. Before that rewrite, this file held ONLY circle-facing practices, each addressed by a literal `**<Addressee>** —` text prefix that `circle.py` scraped out of a rendered `self/circle_briefing.md`. Two rulings changed that: R133 merged `self/better_options.toml` — "how Self moves" — in as records whose `addressee` field is `"Self"`, on the reasoning that a "better option" is not a second kind of record, it is what a practice addressed to Self is *called*; R134 retired the literal `**<Addressee>** —` prefix entirely, since the TOML now has a real `addressee` field to route on, and `circle.py` no longer reads `self/circle_briefing.md` for practices at all (nor, as of the file's own further retirement the same day, for anything else — see `docs/BNF.md` BLOCK 2). R135 collapsed what gets projected into a part's prompt down to a record's `title` field alone, never the whole record — `origin`, `in_room`, `kind`, and `record` are read by Self and by whoever revises or cites an entry, never spent as prompt tokens. R136 unified what had briefly been two record shapes (`plain_practice`/`self_practice`) back into one `<practice>` production, now that every record shares the same field set. R137 moved crisis safety content (a helpline number and text-line short code) out of this register entirely and into `coordinator/process_core.md` as static, unconditional text — it had been living inside a better_option's `in_room` field, which R135's title-only projection rule would otherwise have silently stopped surfacing.

A record's addressee is one of "All parts" (broadcasts to BLOCK 1, `circle_identity`, read by every part), "Self" (also broadcasts to BLOCK 1 — deliberately, so the room can reinforce or suggest evolutions in how Self moves), or a specific part's tag (narrowcasts to that part's own BLOCK 3, `part_identity`, alone). A record also carries staging fields (`state`, `op`, `target_id`, `sources`, `circle`, `proposed_at`) that exist only transiently, while a staged row awaits Self's ruling. Once a staged row is approved, denied, or has a revision applied, its staging fields are stripped, leaving a settled record indistinguishable from one Self typed directly via `/practice-add` — except that a denied row keeps a `state` of `"denied by Self <datetime>"` as its tombstone (ruled 2026-08-12: a denial that leaves no trace cannot be told apart from one that never happened).

**What stages a row here changed on 2026-08-20 (B60).** The in-circle annotation path — the six `[proposed practice: ...]`/`[proposed better_option: ...]` bracket spellings, coalesced by `annotations.py` and written straight into this register as `state = "proposed"` rows through a `stage()` function in the register module — is retired. A part proposes a practice as `[proposed: /practice-add <text>]` (or `/better-option-add`), which is staged into `self/proposals.toml` and, when Self approves it, RUNS the command — that is, calls `practice_manager.practice_add()` — so this register gains a row only once the proposal has been ruled. `stage()` was DELETED with its only callers (B60); no function of that name exists. What remains of the staging half, all in `practice_manager.py`: `practice_stage_render()`, a PURE renderer `inter_circle.py`'s SYNTHESIS uses to stage BLOCK 1 candidates through its own transaction; and `practice_pending_list()`/`practice_approve()`/`practice_deny()`, which still rule any `state = "proposed"` row however it got here — rows staged before B60 are still pending and still have to be rulable.

The simple resolution paths and every read go through `propose_class.ProposeClass`, the shared PROPOSE-class base (docs/HELP_DESIGN.md §6, built 2026-08-16), instantiated at module level as `_PC` with this register's own table name, field order, staging-only fields, id format (`BP-NNNN`), author field (`origin`), clock (`_now()`, UTC) and a post-mutate hook (`_sync_tally`) that keeps the file header's `**Entries: N**` claim true on every save. The lambdas it is built from re-read this module's globals on each call, so the test harnesses' practice of swapping `BP` and `_doc` as module attributes keeps working. Only `practice_approve()`'s op dispatch (add/revise/delete) stays this module's own.

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
Standard library: `pathlib`, `re`, `sys`, `__future__.annotations`. Sibling modules: `practice_manager` (as `PM` — the register: `practice_read`, `practice_read_by_id`, `practice_broadcast`, `practice_narrowcast`, `BP`, `ROOT`, `ID_RE`, `ADDRESSEES`, `STAGING_ONLY`, `_doc`); `roster` (as `R`, for `R.TAG_BY_DIR` — the roster's directory-to-tag mapping, iterated when checking routing); and, imported inside `_routing_check()` and `main()`, `process_core_prompt_projection` (`group_best_practices`) and `parts_prompt_projection` (`part_practices_render`) — the two BLOCK renderers the routing check runs for real. `REGISTER_CLASS`, `PROPOSE_CLASS` and `record_paths` are `practice_manager`'s imports now, not this file's.

## EXTERNAL FILES
Read: `self/best_practices.toml`, via `REGISTER_CLASS.register_read()` — every function in this module that reads the register goes through `_doc()`, which calls this (directly, or through `_PC.entries()`).

Written: nothing — this file is the verifier and is read-only. The register's writes (`self/best_practices.toml`, via `_PC.save()` → `REGISTER_CLASS.register_write()`, by `practice_add()`, `practice_approve()`, `practice_deny()` and `practice_delete()`, with `_sync_tally()` run first so the header's `**Entries: N**` claim is accurate before every save; `practice_stage_render()` returns a modified COPY for its caller to stage and writes nothing) are `practice_manager.py`'s since 2026-09-03.

## NETWORK ACCESS
None.

## HUMAN I/O
`main()`: stdout only — a summary line, a pending-count line if applicable, per-block size lines, and either a PASS line or a numbered FAILURE list. Exit 0 on a clean pass, 1 on any failure. No stdin. (`practice_manager`'s mutation functions — `practice_add`, `practice_approve`, `practice_deny`, `practice_delete` — return `(bool, message)` tuples for their own callers to print or act on and print nothing themselves; `practice_stage_render()` returns `(doc, pid)`.)

## OPERATION

The register functions this page used to document — `_doc`, `practices`, `by_id`, `eligible`,
`broadcast`/`narrowcast`, `add`, `_now`, `_sync_tally`, `pending`, `render_stage`, `_provenance`, `approve`,
`deny`, `listing`, `delete` — are in `coordinator/docs/practice_manager.md` since 2026-09-03; the verifier
reads them as `PM.*`. What stays here is the checking half:

### `_entry_line_in(title, block)`
    { True only when `block` carries `title` as a FULL rendered entry
      line ("- " + title), never as a substring of another line — bare
      substring matching produced a hook-blocking false positive
      (2026-08-19, tier 3 #29). }

### `_projecting_titles()`
    { The set of titles of every record whose state is None or an
      acceptance — re-derived locally, deliberately NOT through
      PM.practice_is_eligible(). A non-projecting row whose title equals a projecting
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
    b = process_core_prompt_projection.group_best_practices(); snapshot
    parts_prompt_projection.part_practices_render() and PM.practice_narrowcast()
    once per roster tag; bcast = PM.practice_broadcast(); proj = _projecting_titles()
    for each part tag in the roster:
        mine = that part's snapshotted parts_prompt_projection.part_practices_render()
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
        missing from process_core_prompt_projection.group_best_practices() }
    for each record whose state is "proposed" or a denial, with a
    non-empty title:
        if (its title is in `proj`) then { skip — the projecting twin
            legitimately puts that line in the rendered text }
        if (its title appears in `b` as a full entry line) then { record
            a failure — a non-projecting row leaked into the broadcast
            block }
        for each part tag: if (its title appears in that part's
            snapshotted parts_prompt_projection.part_practices_render() as a full entry line) then {
            record a failure — it leaked into a narrowcast block }
    return every recorded failure

This runs the real `process_core_prompt_projection.group_best_practices()`/`parts_prompt_projection.part_practices_render()`/`PM.practice_broadcast()`/`PM.practice_narrowcast()` functions against the real roster, not a model of either — the discipline traces to a prior real leak (E09) that a model-based check would not have caught, since the leak was in the actual filtering code, not in an assumption about it. Each real function runs ONCE per tag and its output is reused (2026-08-19, tier 5 #53); a snapshot of a real result is not a model. The non-projecting pass deliberately re-derives "non-projecting" rather than calling `PM.practice_is_eligible()`, so that a leak in `PM.practice_is_eligible()` itself is still caught (`test_routing_check_catches_a_leaked_proposed_row()` monkeypatches it to prove this).

## BUGS
None known. The O(parts × proposals) re-render recorded here until 2026-08-19 is resolved (tier 5 #53, above). This page was regenerated 2026-08-31 after R421/B90 added `_kind_check()`; the previous rendering (2026-08-20, after B60 deleted `stage()` and gave `add()` its `addressee` parameter) did not yet have it.
