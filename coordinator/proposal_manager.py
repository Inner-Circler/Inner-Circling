#!/usr/bin/env python3
"""
proposal_manager.py — the PROPOSE register, self/proposals.toml. R202,
(proposals.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)
2026-08-16, verbatim: *"the PROPOSE CLASS, syntax, and code
subsume every possible future, including 'request'."*

    python coordinator/proposal_manager.py

WHAT A PROPOSAL IS. A part's own `[proposed: <command>]` annotation
(spelled `[propose <text>]` until R273, 2026-08-20) — the ONE annotation for
staging a "future" for Self to vet. Replaces TWO earlier registers at
once: requests.py (never shipped a real row) and relation_proposals.py
(RP-N, also never shipped a real row) — both folded into this one, id
space "P-N". `text` fell into two categories, decided at STAGING time by
annotations.py's `_propose_command_shape()` and carried here as `kind`; since
R273 only the first is ever staged — a body that is not a proposable
command is MALFORMED at utterance — but the row schema still accepts
both, and the fixtures still exercise "text":

    "command"   `text` parses as a real command — identical syntax to a
                valid cmd> input (issue_commands.issue_command_parse()'s own
                issue-relationship-add grammar, or one of dispatch_dev_cmd()'s
                no-circle-needed verbs). Approval RUNS it — the one
                propose kind whose ruling fires code, same contract
                practice/relation already had.
    "text"      free-form. Approval is a pure record — Self has read it
                and marked it considered; nothing executes. This is
                exactly what a "request" always was.

Both kinds share ONE staged/vetted shape — the template every
propose-class register in this project already followed field-for-field
before this fold (the convergence ruling, "use common property
names insofar as possible across records").

RECORD SHAPE:

    id           "P-N", stable, never reused — next_id is a high-water
                 mark, the same discipline every register here uses
    kind         "command" | "text" — see above
    text         the part's own words, VERBATIM. For a "command" row,
                 this IS the command line itself — re-parsed FRESH at
                 approval time (never a stored, pre-parsed snapshot):
                 the graph a "command" row's issue-relationship-add targets may
                 have moved between staging and approval (an endpoint
                 retired, e.g.), and re-parsing against issue_commands.
                 parse()/precheck() each time is what catches that,
                 the same way _propose_approve() already re-derives
                 against graph_now() rather than trusting a cached edge.
    state        "proposed" | "accepted by Self <ISO datetime>" |
                 "denied by Self <ISO datetime>" (tombstoned, never
                 deleted)
    author       backfilled from sources/circle at resolution, same
                 _provenance()-shaped pattern every register here uses
    sources      STAGING ONLY: [display, ...], every speaker whose
                 last stance converged on this proposal this circle
    circle       STAGING ONLY: the circle_<OT> transcript ref of the
                 circle this was staged in — stamped in the prefixed
                 form by proposal_row_stage() itself (circle_ref(), R243 2026-08-19;
                 rows staged before that ruling carried the bare OT) —
                 what an approved edge's `basis` cites, if this is a
                 "command" row that writes the graph
    proposed_at  STAGING ONLY: ISO timestamp

Staging fields are dropped the moment a row resolves — a settled row
carries only id/kind/text/state/author, same discipline as every other
propose-class register in this project.

APPROVAL'S GRAPH-WRITING SIDE (for a "command" row shaped like
issue-relationship-add) lives in circle.py's `_propose_approve()`, not here — this
module stays a pure register with no knowledge of the graph or its
gate, the same separation relation_proposals.py already kept from its
own caller. `proposal_approve()`/`proposal_deny()` here are ONLY ever called after that
orchestration has already succeeded (or for a "text" row, immediately —
there is nothing else to satisfy).
"""

from __future__ import annotations

import datetime
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import REGISTER_CLASS as SS                                       # noqa: E402
import PROPOSE_CLASS                                           # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROPOSALS = SS.PROPOSALS
ORDER = ("id", "kind", "text", "state", "author", "sources", "circle",
         "proposed_at")
STAGING_ONLY = ("sources", "circle", "proposed_at")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def _doc() -> dict:
    return SS.register_read(PROPOSALS) if PROPOSALS.is_file() else {
        "register": "proposals", "next_id": 1, "proposal": []}


# The shared PROPOSE-class base (docs/HELP_DESIGN.md §6, built
# 2026-08-16 — propose_class.py). LAMBDAS, NOT VALUES: the test
# harnesses swap PROPOSALS and _doc as module attributes of THIS
# module, and these lambdas re-read the globals on every call, so the
# monkeypatches keep working. `new_id`/`_now` carry this register's own
# id format and timestamp convention (UTC, unlike best practices' local
# time — a real divergence, preserved).
_PC = PROPOSE_CLASS.ProposeClass(
    table="proposal", order=ORDER, staging_only=STAGING_ONLY,
    path_fn=lambda: PROPOSALS, doc_fn=lambda: _doc(),
    now_fn=lambda: _now(), new_id=lambda n: f"P-{n}",
    author_field="author")


def proposal_read() -> list[dict]:
    """Every proposal on file, unordered — the one reader."""
    return _PC.entries()


def proposal_pending_list() -> list[dict]:
    """Every row awaiting a ruling — the vetting queue reads this and
    nothing else, same discipline every propose-class register here
    uses."""
    return _PC.pending()


def circle_ref(circle: str) -> str:
    """The circle_/sandbox_-prefixed transcript reference — the form the
    issue gate's attested-edge basis regex demands (R061; the ref->path
    mapping itself is issue_schema.circle_transcript's, one copy). Bare
    open times gain circle_: staging is live-only (annotations.
    proposal_stage returns [] for sandbox), so a bare OT can
    only mean circle_. Prefixed and empty values pass through unchanged.

    RULED 2026-08-19 (R243): proposal_row_stage() applies this at the moment a row
    is written, so the register itself carries the transcript's own
    name — greppable, and provenance backfilled from it cites the real
    file. Rows staged before R243 carried the bare OT (annotations passed
    the open time straight through), which is why vetting re-runs this
    same normalization over every row it approves: the healing guard
    for any bare row that still arrives from a backup or a hand-edit.
    Moved here from vetting._gate_circle_ref same date — the register's
    own format belongs to the register's one writer."""
    if not circle or circle.startswith(("circle_", "sandbox_")):
        return circle
    return f"circle_{circle}"


def proposal_row_stage(kind: str, text: str, sources: list[str], circle: str) -> str:
    """Append ONE new P-id row, state='proposed'. The caller (circle.py's
    proposal_coalesce()) decides what a converged group's
    kind/text/sources are; this only writes them — except `circle`,
    normalized to the prefixed transcript ref (circle_ref(), R243).
    Returns the new id.

    FIRST PROPOSER GETS CREDIT, 2026-08-21 (the operator's words): `sources`
    is kept IN THE ORDER GIVEN — proposal_coalesce() passes
    first-appearance order — and `author` is stamped at staging with the
    first of them, "<who> in <circle>", the same provenance shape accept()
    used to backfill from ALL of them at resolution. accept() leaves a
    non-blank author alone, so the credit survives the ruling; the others
    stay on record in `sources`. Both used to be alphabetical."""
    doc = _doc()
    pid = _PC.allocate_id(doc)
    srcs = list(sources)
    ref = circle_ref(circle)
    credit = (f"{srcs[0]} in {ref}" if srcs and ref else (srcs[0] if srcs else ""))
    doc.setdefault("proposal", []).append({
        "id": pid, "kind": kind, "text": text, "state": "proposed",
        "author": credit, "sources": srcs,
        "circle": ref, "proposed_at": _now()})
    _PC.save(doc)
    return pid


def proposal_supersede(pid: str, by_circle: str) -> tuple[bool, str]:
    """A pending row Self has ALREADY RULED IN THE ROOM by a direct command
    — 2026-08-21 (F6, *"yes"*). TOMBSTONED like proposal_deny(), never deleted: state
    names the circle whose direct ruling made it moot, staging fields drop,
    the row stays on record. Never touches the graph — his ruling already
    did whatever this row asked for."""
    doc = _doc()
    row, why = _PC.find_pending(doc.get("proposal", []), pid)
    if row is None:
        return False, why
    if not row.get("author", "").strip():
        row["author"] = _PC.provenance(row)
    row["state"] = (f"superseded by Self's direct ruling in {by_circle} "
                    f"{_now()}")
    _PC.drop_staging(row)
    _PC.save(doc)
    return True, f"{pid} superseded — Self ruled it in the room ({by_circle})"


# A module-level _provenance() delegate used to sit here — zero callers
# (accept() reaches provenance through _PC internally), five lines that
# existed only to be mistaken for a hook, since check_best_practices'
# same-named wrapper IS called (2026-08-18 review, tier 5 #49). Deleted;
# the one copy lives in PROPOSE_CLASS.provenance().


def proposal_approve(pid: str) -> tuple[bool, str]:
    """The WRITE side of a ruling FOR — flips state, backfills author,
    drops staging fields (PROPOSE_CLASS.accept, the shared base). For a
    "command" row that writes the graph (issue-relationship-add), the caller
    (circle.py's `_propose_approve()`) must have already run
    issue_commands.issue_precheck()/apply() successfully before calling this —
    this module never touches the graph itself, only its own state. For
    a "text" row, this IS the whole of approval — there is nothing else
    to satisfy."""
    return _PC.accept(pid)


def proposal_deny(pid: str) -> tuple[bool, str]:
    """Denied proposals are TOMBSTONED, not deleted — the same
    2026-08-12 ruling every propose-class proposal_deny() follows
    (PROPOSE_CLASS.deny, the shared base). Never touches the graph —
    there is nothing to undo, since a denied proposal was never
    applied."""
    return _PC.deny(pid)


def proposal_list() -> str:
    """A numbered list, matching every propose-class register's own
    proposal_list() shape — pending first (what needs a ruling), then
    settled."""
    rs = proposal_read()
    if not rs:
        return "  no proposals"
    pend = [r for r in rs if r.get("state") == "proposed"]
    settled = [r for r in rs if r.get("state") != "proposed"]
    out = []
    if pend:
        out.append("  PENDING:")
        for r in pend:
            out.append(f"    [{r['id']}] ({r.get('kind', '?')}) "
                       f"{r['text'][:60]}")
    if settled:
        out.append("  SETTLED:")
        for r in settled:
            out.append(f"    [{r['id']}] ({r.get('state', '?')}) "
                       f"{r['text'][:60]}")
    return "\n".join(out)


def main() -> int:
    print(f"\n  {len(proposal_pending_list())} pending, {len(proposal_read())} total\n{proposal_list()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
