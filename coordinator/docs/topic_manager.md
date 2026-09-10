# TOPICS(1)

## NAME

topic_manager.py — the TOPIC register: unvetted synthesis material carried into the next circle's BLOCK 2 for the room to examine.

## SYNOPSIS

    python coordinator/topic_manager.py            the listing
    python coordinator/topic_manager.py --init     write the empty register file
    python coordinator/topic_prompt_projection.py   the BLOCK 2 projection, exactly as sent

(As a library: `topic_read()`, `topic_open_read()`, `topic_new_render(doc, circle, text)` from the phase-2 driver, `topic_close(id)` from Self's `/topic-close`, `topic_update(id, text)` from `/topic-update` (R465, B116), and `topic_prompt_projection.topic_block_render()` from `group_attention.circle_briefing_build()`.)

## DESCRIPTION

A topic is cross-part, part-agnostic material that synthesis judged worth the next room's attention: an open question the circle did not close, a tension worth naming aloud, an unconfirmed proposal worth discussing. It reaches the next circle's objectives block as **a thing to discuss, never as a directive** — the ruling that governs BLOCK 1 still holds, and only Self-vetted material lands there.

What makes this register unusual is that it is a **direct write with no vetting checkpoint**. R184 ruled exactly that: unvetted synthesis output may reach BLOCK 2 as a means of letting the circle itself review the proposal. That is the whole point, and it is what separates this register from every PROPOSE-class one, where Self rules before anything moves.

**Ids are minted by the coordinator, never by the model.** A topic is `TP-` plus a serial number from a high-water mark in the file. A gap in the numbering is a closure, and a number is never reused.

**A topic is truncated, not refused, at 800 characters.** A topic that loses its tail is still a topic — unlike a record whose meaning depends on every field being present. The truncation happens at a word boundary.

**Closing a topic leaves a tombstone.** `state` moves from `open` to `closed by Self <datetime>` and the row stays on file forever. A closure that leaves no trace cannot be told apart from one that never happened.

**Closing is immediate and always writes the live register.** It shares the contract that adding a practice has: written the moment Self rules it, not undone by `/abort`, and a `/topic-close` typed during a harness circle still writes the real register — the ruling is Self's regardless of which tree the circle's transcript is going to.

**The projection is a recency window.** `topic_block_render()` (`block()` before it moved to coordinator/topic_prompt_projection.py, 2026-09-03) renders open topics newest first up to a 2,400-character budget, under a header that states how many are open, how many are shown and how many are older and out of view — so the room can see when something has aged out rather than silently missing it. The window stops at the first topic that does not fit rather than skipping it to pack a smaller older one in: recency is the only priority lever here.

**An empty register changes nothing.** `topic_block_render()` returns an empty string when nothing is open, so the objectives block is byte-identical to what it would have been without this register at all.

## MAIN

    Read the command-line arguments.
    if ("--init" appears) then {
        if (self/topics.toml already exists) then {
            print that it exists and was left untouched; return 0.
        } else {
            write the empty register and print the path; return 0.
        }
    }
    otherwise {
        print the listing: the open and closed counts, then every OPEN topic
        with its id, its circle, and its text wrapped to 72 columns.
        return 0.
    }

## COMMAND-LINE ARGUMENTS

    (none)      the listing — counts, then each open topic with its text.
    --init      create self/topics.toml as an empty register. Refuses to
                overwrite an existing one, printing and exiting 0.
    (--block, the projection printed byte for byte, was this file's until 2026-09-03; it is
    topic_prompt_projection.py's own main now — stage 17c, so the register imports nothing above it.) Default: off.

Matched by presence, not position.

## DEPENDENCIES

`REGISTER_CLASS` for load/save/timestamps and prose wrapping; `setting_manager` for the caps; `remember_manager` for its word-boundary truncation, so "how a record is cut" has one definition in the project rather than two. `pathlib`, `sys`, `copy`.

## EXTERNAL FILES

    self/topics.toml    READ by every verb; WRITTEN by --init, by add() when
                        synthesis emits a candidate, and by close() when Self
                        rules on one.

`PATH` is module-level and rebindable; the probe suite points it at a temporary file so no test ever writes a `TP-` row into the live register — in a tombstone register, a probe's leftovers would be permanent.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout; reads no input. Standard output is reconfigured to UTF-8 with replacement on import.

## OPERATION

### _doc() / _save(doc)
The register from disk, or a fresh in-memory one when the file is absent; and the save, which creates the parent directory if needed.

### topic_read() / topic_open_read()
Every topic, open and tombstoned alike, in file order; and the open ones sorted newest first, which is the projection order.

### topic_new_render(doc, circle, text) (`render_new()` before the B99 re-homing, 2026-09-03)
    Work on a deep COPY of the register.
    Mint "TP-" plus next_id, four digits; stamp the circle and the UTC time;
        truncate the text to CAP at a word boundary; set state to "open".
    Append, advance next_id, return (the new register, the new record).

Pure, so the phase-2 driver can stage the render and have the register gate verify it before anything is written. The writing caller below is this function plus the save, which is what keeps the validation in exactly one place. (This said "`add()` below", and `add()` has no successor under any spelling — a reader following it found no such function and no note saying where it went. audit-register 2026-09-09 `#42`.)

### topic_new_render(doc, circle, text)
Render one open topic and write the register. The coordinator calls this once per BLOCK 2 candidate item after the synthesis call returns.

### topic_close(tid)
(`close()` before the B99 re-homing, 2026-09-03.)
    Load the register and find the row with this id.
    if (there is no such row) then { return (false, "<id> not found"). }
    if (the row is not open) then { return (false, naming its actual state). }
    Set state to "closed by Self <utc timestamp>", save, and return
        (true, "<id> closed — kept as a tombstone").

### topic_update(tid, text)
    Replace one OPEN topic's text in place (R465, B116, 2026-09-07): same id, circle
        and date; `amended` set to today's date; the text CAP-truncated at a word
        boundary as topic_new_render() does; no prior wording kept — git is the journal.
    if (there is no such row) then { return (false, "<id> not found"). }
    if (the text is empty) then { return (false, "nothing to update"). }
    if (the row is not open) then { return (false, naming its state — a tombstone). }
    Otherwise change the row through REGISTER_CLASS.register_row_update() (id
        immutable), save, and return (true, "<id> updated — <text>...").

### topic_prompt_projection.topic_block_render() (`block()` here before it moved, 2026-09-03)
    if (no topic is open) then { return "" — the objectives block is unchanged. }
    Walk the open topics newest first, rendering each as one bullet naming its
        id and the circle it came from.
    if (adding the next bullet would exceed BUDGET) then { stop here. }
    Return a header stating the open count, the shown count and the omitted
        count, followed by the bullets.

### topic_list() (`listing()` before the B99 re-homing, 2026-09-03)
The human view: the open and closed counts, then each open topic's id and circle with its text wrapped and indented.

## BUGS

None found. Two intentional behaviours worth naming: the projection window stops at the first oversized topic instead of skipping it, which is deliberate and documented in the source; and `close()` writes the live register even from a harness circle, which is the ruled contract rather than an isolation leak.
