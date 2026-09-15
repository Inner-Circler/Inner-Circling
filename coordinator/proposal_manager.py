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
    sources      PERMANENT since 2026-09-08 ("Structured"): [display, ...],
                 every speaker whose last stance converged on this
                 proposal in the circle it was staged in. Staging-only
                 until then, flattened into `author` and dropped — which
                 left "which members converged on this?" answerable only
                 by parsing a sentence. The list stays a list.
    circle       STAGING ONLY: the circle_<OT> transcript ref of the
                 circle this was staged in — stamped in the prefixed
                 form by proposal_row_stage() itself (circle_ref(), R243 2026-08-19;
                 rows staged before that ruling carried the bare OT) —
                 what an approved edge's `basis` cites, if this is a
                 "command" row that writes the graph
    proposed_at  STAGING ONLY: ISO timestamp
    part         an EVIDENCE OFFER only — `[proposed: /issue-evidence-add nNNNN
    quote        "why"]`, whose statement is the one the bracket rode in
                 (R541): the speaker's directory id and
                 the words, verbatim, read off that statement at the close.
                 `text` names no statement, so approval takes these two, and the
                 row's `circle` as the evidence `source`. Absent on every other
                 row, so an old row renders exactly as it did. Kept at resolution.

Staging fields are dropped the moment a row resolves — a settled row
carries id/kind/text/state/author AND `sources`, the last of these since
2026-09-08 ("Structured"). Every other propose-class register here shares
the discipline and the exception: the LIST is kept because prose degrades
a list, and `circle`/`proposed_at` are single values `author` and `state`
already carry.

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


def _proposals_rebind() -> None:
    """The CURRENT group's register — B117 stage 4 (2026-09-07). Registered below, after
    REGISTER_CLASS's own follower, so SS.PROPOSALS has already moved when this reads it."""
    global PROPOSALS
    PROPOSALS = SS.PROPOSALS


import record_paths as _RPf                                                # noqa: E402
_RPf.group_follow(_proposals_rebind)
ORDER = ("id", "kind", "text", "state", "author", "sources", "circle",
         "proposed_at", "part", "quote", "depends_on", "minted")
# `sources` SURVIVES RESOLUTION — ruled 2026-09-08, VERBATIM: "Structured".
#
# It was dropped here with `circle` and `proposed_at`, after _provenance() flattened both into
# the `author` string ("Alpha, Beta in circle_2026-09-08_1234"). That is lossy in the one
# direction provenance is ever used: asking which speakers converged on something, across
# circles, meant parsing prose. The 1:1 WORDING was never at risk — every row keeps its own
# `text`, tombstoned and never deleted, and the coalesce enacts the primary member's own words
# rather than model-merged prose — but the SOURCE LIST was structured only until the moment
# the row was ruled on.
#
# `circle` AND `proposed_at` STILL GO. The circle is preserved in `author` and is a single
# value a sentence carries perfectly well; `proposed_at` is staging bookkeeping, and the
# resolution timestamp lives in `state`. Only the field that was a LIST — the one prose
# genuinely degrades — is kept.
STAGING_ONLY = ("circle", "proposed_at")


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


# ------------------------------------------------------------------ dependencies
# R570, 2026-09-15 — the operator: *"can staging be ordered such that
# dependents (such as relations) follow what they depend upon (such as issues), and the
# creation of the second unblocks the resolution of the dependent? And further, if the prior
# is rejected at vetting, then any dependents are automatically rejected?"*
#
# `depends_on` is a LIST OF STRINGS, the shape `sources` already proves the writer handles:
# "P-7" waits on P-7; "P-7:nMMMM" also names the placeholder P-7's minted id fills. `minted`
# is the id an approval produced (an issue's nNNNN, a practice's BP-NNNN), kept on the
# accepted row so a dependent vetted at a LATER checkpoint still resolves. Both survive
# resolution: they are provenance, not staging bookkeeping.
DEPENDS_SEP = ":"


def proposal_dependency_ids_read(row: dict) -> list[str]:
    """The proposal ids `row` depends on."""
    return [s.split(DEPENDS_SEP, 1)[0] for s in row.get("depends_on", []) if s]


def proposal_dependency_placeholders_read(row: dict) -> dict[str, str]:
    """{proposal id: placeholder token} for the entries that name a token."""
    out: dict[str, str] = {}
    for s in row.get("depends_on", []):
        pid, sep, tok = s.partition(DEPENDS_SEP)
        if sep and tok:
            out[pid] = tok
    return out


def proposal_dependency_ring_find(rows: list[dict], new_id: str,
                                  new_deps: list[str]) -> list[str]:
    """Would a row `new_id` depending on `new_deps` close a ring among `rows`? The ring as
    ids (first == last), or []. A walk with a stack and a seen set — it never loops."""
    deps: dict[str, list[str]] = {r["id"]: proposal_dependency_ids_read(r) for r in rows}
    deps[new_id] = list(new_deps)
    seen: set[str] = set()

    def walk(pid: str, stack: list[str]) -> list[str]:
        if pid in stack:
            return stack[stack.index(pid):] + [pid]
        if pid in seen:
            return []
        seen.add(pid)
        for d in deps.get(pid, []):
            ring = walk(d, stack + [pid])
            if ring:
                return ring
        return []

    return walk(new_id, [])


def _token_re(tok: str):
    import re
    return re.compile(rf"(?<![\w-]){re.escape(tok)}(?![\w-])")


def proposal_by_id_read(pid: str) -> dict | None:
    return _PC.by_id(pid)


def proposal_dependents_read(pid: str) -> list[dict]:
    """The PENDING rows that depend on `pid`."""
    return [r for r in proposal_pending_list() if pid in proposal_dependency_ids_read(r)]


def proposal_minted_write(pid: str, minted: str) -> bool:
    """Record the id `pid`'s approval produced on its row."""
    doc = _doc()
    row = next((r for r in doc.get("proposal", []) if r["id"] == pid), None)
    if row is None or not minted:
        return False
    row["minted"] = minted
    _PC.save(doc)
    return True


def proposal_placeholder_substitute(pid: str, minted: str) -> list[str]:
    """Every PENDING row whose depends_on names `pid` with a token has that token replaced
    by `minted` in its text, as a whole word. Returns the rows changed."""
    doc = _doc()
    changed: list[str] = []
    for r in doc.get("proposal", []):
        if r.get("state") != "proposed":
            continue
        tok = proposal_dependency_placeholders_read(r).get(pid)
        if tok and _token_re(tok).search(r.get("text", "")):
            r["text"] = _token_re(tok).sub(lambda _m: minted, r["text"])
            changed.append(r["id"])
    if changed:
        _PC.save(doc)
    return changed


def proposal_dependency_resolve(row: dict) -> dict:
    """Fill every token whose prior is already accepted with a minted id — the second
    checkpoint's half of substitution — and return the row as it now stands."""
    for pid in proposal_dependency_placeholders_read(row):
        prior = _PC.by_id(pid)
        if prior and str(prior.get("state", "")).startswith("accepted") and prior.get("minted"):
            proposal_placeholder_substitute(pid, prior["minted"])
    return _PC.by_id(row["id"]) or row


def proposal_dependency_state_read(row: dict) -> tuple[str, str]:
    """("ready", "") — every prior accepted and every token filled;
    ("waiting", why) — a prior is still pending;
    ("cascade", prior id) — a prior was denied or superseded, so this row falls with it;
    ("unresolved", why) — a prior is missing, or accepted without the id a token needs."""
    for s in row.get("depends_on", []):
        pid, _sep, tok = s.partition(DEPENDS_SEP)
        prior = _PC.by_id(pid)
        if prior is None:
            return "unresolved", f"it depends on {pid}, which is not on file"
        state = str(prior.get("state", ""))
        if state == "proposed":
            return "waiting", f"it waits on {pid}, which is still pending"
        if state.startswith("superseded"):
            # SELF ALREADY RULED IT IN THE ROOM: the act is done, so the dependent may go on —
            # but a direct ruling minted nothing here to fill a token with.
            if tok and _token_re(tok).search(row.get("text", "")):
                return "unresolved", (f"{pid} was ruled directly in the room and produced no "
                                      f"id here to fill {tok}")
            continue
        if not state.startswith("accepted"):
            return "cascade", pid
        if tok and _token_re(tok).search(row.get("text", "")):
            return "unresolved", (f"{pid} was approved but produced no id to fill {tok}"
                                  if not prior.get("minted")
                                  else f"{tok} is still unfilled")
    return "ready", ""


def _deny_because(pid: str, why: str) -> bool:
    doc = _doc()
    row, _err = _PC.find_pending(doc.get("proposal", []), pid)
    if row is None:
        return False
    if not row.get("author", "").strip():
        row["author"] = _PC.provenance(row)
    row["state"] = f"denied by Self {_now()} — {why}"
    _PC.drop_staging(row)
    _PC.save(doc)
    return True


def proposal_cascade_deny(pid: str) -> list[str]:
    """Deny every PENDING row that depends on `pid`, transitively, each tombstoned with the
    prior that took it down. A visited set: a hand-edited ring cannot loop this."""
    denied: list[str] = []
    seen = {pid}
    queue = [pid]
    while queue:
        cur = queue.pop(0)
        for r in proposal_dependents_read(cur):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            if _deny_because(r["id"], f"cascade: {cur} was not accepted"):
                denied.append(r["id"])
                queue.append(r["id"])
    return denied


def proposal_dependency_repoint(old: str, new: str | None) -> list[str]:
    """A prior that left the queue WITHOUT a ruling of substance — denied only because a
    coalesced group accepted another member. Its pending dependents wait on `new` instead
    (the accepted primary, token kept), or, `new` None, simply stop waiting on it. A repoint
    that would close a ring is skipped. Returns the rows changed."""
    doc = _doc()
    rows = doc.get("proposal", [])
    changed: list[str] = []
    for r in rows:
        if r.get("state") != "proposed" or old not in proposal_dependency_ids_read(r):
            continue
        nd: list[str] = []
        for s in r.get("depends_on", []):
            pid, sep, tok = s.partition(DEPENDS_SEP)
            if pid != old:
                nd.append(s)
            elif new:
                nd.append(new + (sep + tok if tok else ""))
        others = [x for x in rows if x is not r]
        if new and proposal_dependency_ring_find(others, r["id"],
                                                 proposal_dependency_ids_read({"depends_on": nd})):
            continue
        if nd:
            r["depends_on"] = nd
        else:
            r.pop("depends_on", None)
        changed.append(r["id"])
    if changed:
        _PC.save(doc)
    return changed


def proposal_row_stage_once(kind: str, text: str, sources: list[str], circle: str, *,
                            depends_on: list[str] | None = None) -> tuple[str, bool]:
    """(id, staged) — a PENDING row with the same text is reused rather than staged twice,
    so running a verb again, or a report naming a line twice, never doubles a ruling."""
    norm = " ".join(text.split())
    for r in proposal_pending_list():
        if " ".join(r.get("text", "").split()) == norm:
            return r["id"], False
    return proposal_row_stage(kind, text, sources, circle, depends_on=depends_on), True


def proposal_row_stage(kind: str, text: str, sources: list[str], circle: str, *,
                       part: str = "", quote: str = "",
                       depends_on: list[str] | None = None) -> str:
    """Append ONE new P-id row, state='proposed'. The caller (circle.py's
    proposal_coalesce()) decides what a converged group's
    kind/text/sources are; this only writes them — except `circle`,
    normalized to the prefixed transcript ref (circle_ref(), R243).
    Returns the new id. `part`/`quote` are an evidence offer's statement
    (RECORD SHAPE above), written only when given.

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
    row = {"id": pid, "kind": kind, "text": text, "state": "proposed",
           "author": credit, "sources": srcs,
           "circle": ref, "proposed_at": _now()}
    if part:
        row["part"] = part
    if quote:
        row["quote"] = quote
    if depends_on:
        # REFUSED, NOT REPAIRED — a dependency on a row that is not on file, or one that would
        # close a ring, has no order to be vetted in. Nothing is written: the id allocated
        # above lives only in this unsaved doc (R570).
        rows = doc.get("proposal", [])
        dep_ids = proposal_dependency_ids_read({"depends_on": depends_on})
        missing = [d for d in dep_ids if d not in {r["id"] for r in rows}]
        if missing:
            raise ValueError(f"{pid} would depend on {', '.join(missing)}, which is not on "
                             f"file — nothing staged")
        ring = proposal_dependency_ring_find(rows, pid, dep_ids)
        if ring:
            raise ValueError(f"{pid} would close a ring ({' -> '.join(ring)}) — nothing staged")
        row["depends_on"] = list(depends_on)
    doc.setdefault("proposal", []).append(row)
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
