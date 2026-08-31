#!/usr/bin/env python3
"""
topics.py — the TOPIC register. SYNTHESIS's unvetted BLOCK 2 material,
one short paragraph per record, projected into the next circle's working
surface for the room to review.

    python coordinator/topics.py            listing
    python coordinator/topics.py --init     write the empty register file
    python coordinator/topics.py --block    the BLOCK 2 projection, as sent

RULED — R184, 2026-08-15, verbatim: *"unvetted synthesis output can
reach BLOCK 2 "what this circle is about" as a means of circle-review of
the proposal."* The MECHANISM here (this file, TP- ids, the window) is the
design ratified post-sweep the same day ("make the changes now") —
proposed by Claude, adopted by that instruction.

WHAT A TOPIC IS. Cross-part, part-agnostic material SYNTHESIS judges worth
the next room's attention: an open question the room did not close, a
tension worth naming aloud, an unconfirmed proposal worth discussing. It
reaches BLOCK 2 as a THING TO DISCUSS, never as a directive — R172 still
governs BLOCK 1, where only Self-vetted material lands. DIRECT WRITE, no
vetting checkpoint: that is exactly what R184 rules, and what separates
this register from every PROPOSE-class one.

    id      "TP-" DIGIT+, one id space, high-water `next_id`, minted by
            the COORDINATOR after the SYNTHESIS call returns — the model
            never mints its own id (R170's MEM- discipline). A gap is a
            closure; an id is never reused.
    circle  the OT whose SYNTHESIS emitted it.
    date    UTC ISO, microseconds (self_schema.now()).
    text    one short paragraph, CAP-truncated at a word boundary
            (remember.truncate — a topic losing its tail is still a
            topic, unlike a relationships record losing a part).
    state   "open" | "closed by Self <datetime>". Closed rows are
            TOMBSTONES, never deleted — same reasoning as a denied
            practice (2026-08-12): a closure that leaves no trace cannot
            be told apart from one that never happened.

PROJECTION. block() renders every OPEN topic, newest first, windowed to
BUDGET chars — recency is the only priority lever, remember.py's own
discipline — under a header that states shown/omitted, so the room knows
when older topics have aged out of view. build_briefing() appends it to
BLOCK 2: a topic is a thread carried from a past circle. (--minimal
promised these absent; that mode retired R360.)

DISPOSITION. A topic stays open until Self closes it (/topic-close TP-n).
The ratified design wrote this verb "/topic close"; it ships as
`/topic-close` per the ruled `<object>-<method>` production (docs/BNF.md,
COMMAND) — B16 blocks renaming EXISTING verbs, not conforming new ones.

WRITER. SYNTHESIS calls add() once per BLOCK 2 CANDIDATE item
(coordinator/inter_circle.py). The register is NO LONGER EMPTY: R193's
self.md decomposition seeded 25 open rows on 2026-08-15, so block() emits
~2,573 chars and BLOCK 2 is NOT byte-identical to before this file existed.
This docstring said the opposite until that migration ran, and nothing
caught it — the claim was true when written and quietly stopped being
true. docs/BNF.md's build_briefing production carries part 5 as of the
same day, for the same reason.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import self_schema as SS                                       # noqa: E402
import settings as SET                                         # noqa: E402
import remember as RM                                          # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Module-level, rebindable — test_topics.py points this at a temp file so
# no probe ever writes a TP- row into the live register (a tombstone
# register makes a probe's leftovers permanent; see test_check_lint.py's
# same outside-the-tree pattern).
PATH = ROOT / "self" / "topics.toml"

TABLE = "topic"
ORDER = ("id", "circle", "date", "text", "state")

CAP = 800       # chars per topic — one short paragraph
BUDGET = SET.value("topics_budget", 2400)   # chars projected into BLOCK 2,
                # newest first (~3 topics)

_PREAMBLE = (
    "SYNTHESIS's unvetted BLOCK 2 topics -- R184, 2026-08-15: 'unvetted "
    "synthesis output can reach BLOCK 2 ... as a means of circle-review "
    "of the proposal.' Mechanism (TP- ids, cap 800, 2,400-char "
    "newest-first window, open-until-Self-closes) ratified by Self "
    "post-sweep the same day. Direct write, never vetted -- R172 still "
    "governs BLOCK 1. Closed rows are tombstones, never deleted.")


def _doc() -> dict:
    if PATH.is_file():
        return SS.load(PATH)
    return {"register": "topics", "next_id": 1,
            "doc": {"preamble": _PREAMBLE}, TABLE: []}


def _save(doc: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    SS.save(PATH, doc, TABLE, ORDER)


# ------------------------------------------------------------------ register
def entries() -> list[dict]:
    """Every topic on file, open and tombstoned alike, unordered."""
    return _doc().get(TABLE, [])


def open_topics() -> list[dict]:
    """OPEN topics, newest first — the projection order."""
    es = [t for t in entries() if t.get("state") == "open"]
    return sorted(es, key=lambda t: t.get("date", ""), reverse=True)


def render_new(doc: dict, circle: str, text: str) -> tuple[dict, dict]:
    """PURE — one open topic appended to a COPY of `doc`; the phase-2
    driver stages the render and the register gate verifies it
    (docs/REGISTER_GATE_DESIGN.md). add() below is the same logic plus
    the write, so validation exists exactly once."""
    import copy
    doc = copy.deepcopy(doc)
    n = doc.get("next_id", 1)
    rec = {"id": f"TP-{n:04d}", "circle": circle, "date": SS.now(),
           "text": RM.truncate(text, CAP), "state": "open"}
    doc.setdefault(TABLE, []).append(rec)
    doc["next_id"] = n + 1
    return doc, rec


def add(circle: str, text: str) -> dict:
    """Append ONE open topic; the coordinator calls this once per BLOCK 2
    CANDIDATE item after SYNTHESIS returns. CAP-truncated, never refused —
    and the id is minted HERE, serially, never by the model."""
    doc, rec = render_new(_doc(), circle, text)
    _save(doc)
    return rec


def close(tid: str) -> tuple[bool, str]:
    """Self's disposition. Tombstones the row; the id never returns.
    IMMEDIATE, same contract as /practice-add: written the moment it is
    ruled, /abort does not undo it, and a sandbox circle's /topic-close
    still writes THIS live register — the ruling is Self's regardless of
    which tree the circle is writing to."""
    doc = _doc()
    row = next((t for t in doc.get(TABLE, []) if t.get("id") == tid), None)
    if row is None:
        return False, f"{tid} not found"
    if row.get("state") != "open":
        return False, f"{tid} is not open (state={row.get('state')!r})"
    row["state"] = f"closed by Self {SS.now()}"
    _save(doc)
    return True, f"{tid} closed — kept as a tombstone"


# ----------------------------------------------------------------- projection
def block() -> str:
    """The BLOCK 2 projection — "" when nothing is open, so an empty
    register leaves circle_objectives byte-identical."""
    es = open_topics()
    if not es:
        return ""
    lines, used, shown = [], 0, 0
    for t in es:
        entry = f"\n- {t['id']} (from circle {t.get('circle', '?')}): {t['text']}\n"
        if used + len(entry) > BUDGET:
            # break, not continue (2026-08-19, review tier 5 #57):
            # skipping the over-budget newer topic and rendering older
            # ones was fill-packing while the header below claims
            # "{omitted} OLDER omitted from view" and the module's own
            # docstring says recency is the only priority lever — the
            # window ends at the first topic that does not fit, same
            # rule as remember._window. Measured before changing: the
            # open register sits well under BUDGET, no live prompt
            # changes a byte.
            break
        lines.append(entry)
        used += len(entry)
        shown += 1
    omitted = len(es) - shown
    head = ("## Topics for this circle's review\n\n"
            f"*From synthesis, UNVETTED — carried here for the room to "
            f"examine, never as a directive. {len(es)} open, {shown} shown "
            f"within a {BUDGET}-character window"
            + (f", {omitted} older omitted from view" if omitted else "")
            + ".*\n")
    return head + "".join(lines)


def listing() -> str:
    es = entries()
    closed = sum(1 for t in es if t.get("state") != "open")
    out = [f"  {len(es) - closed} open topic(s), {closed} closed"]
    for t in open_topics():
        out.append(f"  {t['id']}  {t.get('circle', '?')}")
        for ln in SS.wrapn(t.get("text", ""), 72):
            out.append(f"        {ln}")
    return "\n".join(out)


def main() -> int:
    a = sys.argv[1:]
    if "--init" in a:
        if PATH.is_file():
            print(f"  {PATH.relative_to(ROOT)} already exists — untouched")
            return 0
        _save(_doc())
        print(f"  wrote {PATH.relative_to(ROOT)} (empty register)")
        return 0
    if "--block" in a:
        print(block() or "  (no open topics — projection is empty)")
        return 0
    print(listing())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
