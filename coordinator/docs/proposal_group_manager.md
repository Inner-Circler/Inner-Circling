# PROPOSAL_GROUP_MANAGER.PY(1)

## NAME
proposal_group_manager.py — the PROPOSAL COALESCE (R356, B69): the one reader/writer of
`self/coalesce.toml`, and the one model pass that groups a pending vetting queue into "one ask in
different words". (`coalesce.py` until 2026-09-03 — B99 stage 18c under R435.)

## SYNOPSIS
```
python coordinator/proposal_group_manager.py             state: freshness + groups
python coordinator/proposal_group_manager.py --refresh   force one derive (a real model call)
python coordinator/proposal_group_manager.py --selftest  hash checks, no API
python coordinator/proposal_group_manager.py --init      write the empty register if absent
```
    import proposal_group_manager as CG
    CG.proposal_group_refresh(say, client) · CG.proposal_group_live_read() · CG.proposal_group_mark(gid, status)
    CG.proposal_group_pending_read() · CG.proposal_group_hash_write(rows) · CG.proposal_group_derive(rows, client)

## DESCRIPTION
The vetting queue accumulates rows that are the same ask in different words — across circles,
across authors, across the practice and propose registers. Ruled R356: ONE model pass over the WHOLE
pending set, just before the vetting ask, hash-guarded on the set's content so it fires only when the
set changed — in practice once per circle, at close; the next open presents the same groups for free.

THE MODEL ONLY SUGGESTS. A group is a presentation: vetting shows it as one strengthened ask with its
recurrence count and source circles, and Self rules it. Accepting enacts the PRIMARY member through
that member's own approve path — the member's OWN WORDS land in the record, never model-merged prose
— and denies the others through their own deny paths; a split dissolves the group for this
queue-state and the members are asked individually. This module writes ONLY `self/coalesce.toml`;
the practice and proposal registers are ruled through their own one-writers.

PROVENANCE. A ruled group keeps its members, primary, gloss and ruling in its `status` field forever
and survives every re-derive; only live (unruled) groups are replaced when the pending set changes.

FAILS OPEN, DELIBERATELY. Vetting is how circles open, so a suggestion pass must never block it: an
unparseable reply, a truncated one (`max_tokens`), or any invalid line writes an EMPTY live set with
the current hash and a `note` saying why — the queue is still vetted, just ungrouped. WRITTEN
IMMEDIATELY, never circle-committed: the file is real on disk the moment it changes.

## MAIN
    parse the arguments (below)
    if (--selftest) then { run selftest() and exit with its status }
    if (--init) then {
        if (self/coalesce.toml exists) then { say so; exit 0 }
        else { write the empty register; exit 0 }
    }
    { read the pending rows and the document; print the pending count, the live and ruled
      group counts, and the hash state — "fresh", "STALE" (rows but a different hash), or
      "empty set" }
    if (--refresh) then {
        if (nothing is pending) then { say so; exit 0 }
        else { derive once (a real model call) and print how many groups }
    }
    exit 0

## COMMAND-LINE ARGUMENTS
`--refresh`: force one grouping pass (a real model call). Default: off — a bare run only reports state.
`--selftest`: the hash checks, no API. Default: off.
`--init`: write the empty register if absent. Default: off.

## DEPENDENCIES
Standard library: `hashlib`, `pathlib`, `sys`, `datetime`, `argparse` (inside `main()`). Sibling
modules: `LLM_response_disassembler` (as `RD`: `message_groups_read()`, the one reader of the
GROUP line), `REGISTER_CLASS` (inside `_load()`/`_save()`), `practice_manager` and
`proposal_manager` (inside `proposal_group_pending_read()`, the pending rows of both registers),
`llm_client` (inside `_call()`: `stream_call_once()` and `AUX_MAX_TOKENS`).

## EXTERNAL FILES
    self/coalesce.toml         READ by every verb; WRITTEN by proposal_group_derive(),
                               proposal_group_mark(), proposal_group_refresh() (clearing stale live
                               groups on an empty set), and --init. Absent is read as the empty
                               document (register = "coalesce", next_id = 1, empty hash/derived/
                               note, no rows).
    self/best_practices.toml   READ through practice_manager.practice_pending_list().
    self/proposals.toml        READ through proposal_manager.proposal_pending_list().
    work/prompts/<OT>/         WRITTEN indirectly: the derive's turn is recorded with no part,
                               kind "coalesce" (R413), when a circle's capture is open.
    .env                       READ by llm_client only when ANTHROPIC_API_KEY is absent from the
                               environment, and only on a derive.

## NETWORK ACCESS
One Messages API call per derive (`--refresh`, or a refresh whose hash moved). `client` is injectable
so no probe reaches the network.

## HUMAN I/O
`main()` prints the state report; `proposal_group_refresh()` reports through its `say` callable
(default `print`) — one line when a pass runs, one per note, one for the count.

## OPERATION

### `proposal_group_pending_read()`
    { every row awaiting a ruling from BOTH registers, as the model and the hash see it:
      ref ("practice:BP-0044" / "propose:P-4"), kind, id, text, sources, circle — read
      through each register's own reader, fresh }

### `proposal_group_hash_write(rows)`
    { sha256 over the refs and texts in REF ORDER (so the hash is order-insensitive and
      text-sensitive), the first 16 hex characters }

### `_load()` / `_save(doc)`
    { the register through REGISTER_CLASS; absent reads as the empty document }

### `_call(system, user, client)`
    { one reply through llm_client.stream_call_once() at AUX_MAX_TOKENS, kind "coalesce",
      recorded — the injected-client contract: a fake is used exactly as given }

### `proposal_group_derive(rows, client)`
    { build one user message: each row as "[ref] (provenance)\ntext" }
    { call the model }
    if (the reply stopped at max_tokens) then { treat the text as empty; note why }
    { RD.message_groups_read() parses the GROUP lines against the known refs; every
      invalid line becomes a note and is dropped, never guessed at }
    { keep every RULED group (non-empty status); mint CG-nnnn ids for the live groups,
      each with members, primary, gloss, the union of the members' sources, status "" }
    { write the doc with the new hash, the derive time and the joined notes }
    { return (number of live groups, notes) }

### `proposal_group_refresh(say, client)`
    { read the pending rows and the doc }
    if (nothing is pending) then {
        if (live groups linger) then { drop them, store the empty set's hash, save }
        return "empty"
    } else if (the stored hash equals the pending set's) then { return "fresh" }
    else { say a pass is running; derive; say each note and the count; return "derived N" }

### `proposal_group_live_read()`
    if (the stored hash differs from the CURRENT pending set's) then { ([], set()) —
        anything stale presents nothing }
    else { (the unruled groups, the set of their member refs) }

### `proposal_group_mark(gid, status)`
    { set that group's status and save — the ruling's provenance, kept forever }

### `selftest()`
    { two cases: the hash is order-insensitive, and text-sensitive; PASS/FAIL, exit status }

## BUGS
None found. Worth knowing: `proposal_group_hash_write()` keys on ref and text only, so a change to a
row's sources or circle alone does not re-derive — deliberate, since neither changes the ask.
