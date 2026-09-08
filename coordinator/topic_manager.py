#!/usr/bin/env python3
"""
topic_manager.py — the TOPIC register. SYNTHESIS's unvetted BLOCK 2 material,
(topics.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)
one short paragraph per record, projected into the next circle's working
surface for the room to review.

    python coordinator/topic_manager.py            listing
    python coordinator/topic_manager.py --init     write the empty register file
    python coordinator/topic_prompt_projection.py   the BLOCK 2 projection, as sent (this file's
                                            --block until 2026-09-03, stage 17c)

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
    date    UTC ISO, microseconds (REGISTER_CLASS.register_now()).
    text    one short paragraph, CAP-truncated at a word boundary
            (remember.truncate — a topic losing its tail is still a
            topic, unlike a relationships record losing a part).
    state   "open" | "closed by Self <datetime>". Closed rows are
            TOMBSTONES, never deleted — same reasoning as a denied
            practice (2026-08-12): a closure that leaves no trace cannot
            be told apart from one that never happened.

PROJECTION MOVED OUT, 2026-09-02 — see topic_prompt_projection.py. It renders
every OPEN topic, newest first, windowed to BUDGET chars — recency is
the only priority lever, remember_manager.py's own discipline — under a header
that states shown/omitted, so the room knows when older topics have
aged out of view. group_attention.py's circle_briefing_build() calls it to
build BLOCK 2's fifth part: a topic is a thread carried from a past
circle. (--minimal promised these absent; that mode retired R360.) This
file keeps BUDGET (topic_prompt_projection.py reads it as TOP.BUDGET) since
the number is a register-sizing decision, not a rendering one.

DISPOSITION. A topic stays open until Self closes it (/topic-close TP-n).
The ratified design wrote this verb "/topic close"; it ships as
`/topic-close` per the ruled `<object>-<method>` production (docs/BNF.md,
COMMAND) — B16 blocks renaming EXISTING verbs, not conforming new ones.

WRITER. SYNTHESIS renders one row per BLOCK 2 CANDIDATE item through
topic_new_render() and stages the document in its Transaction
(coordinator/inter_circle.py); add(), the direct write that stood beside
it, went 2026-09-03 (D81) — nothing called it, and this line said
SYNTHESIS did. The register is NO LONGER EMPTY: R193's
self.md decomposition seeded 25 open rows on 2026-08-15, so block() emits
~2,573 chars and BLOCK 2 is NOT byte-identical to before this file existed.
This docstring said the opposite until that migration ran, and nothing
caught it — the claim was true when written and quietly stopped being
true. docs/BNF.md's circle_briefing_build production carries part 5 as of the
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
import REGISTER_CLASS as SS                                       # noqa: E402
import record_paths as _RP                                         # noqa: E402
import setting_manager as SET                                         # noqa: E402
import remember_manager as RM                                          # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Module-level, rebindable — test_topic_manager.py points this at a temp file so
# no probe ever writes a TP- row into the live register (a tombstone
# register makes a probe's leftovers permanent; see test_system_lint_verify.py's
# same outside-the-tree pattern).
PATH = _RP.SELF_DIR / "topics.toml"


@_RP.group_follow
def _path_rebind() -> None:
    """The CURRENT group's register — B117 stage 4 (2026-09-07); a probe's PATH rebind holds
    until something calls record_paths.group_set()."""
    global PATH
    PATH = _RP.SELF_DIR / "topics.toml"

TABLE = "topic"
# `amended` — the date of the last in-place update (topic_update(); R465, B116, 2026-09-07).
# Absent until one; replaced each time; no prior wording, no reason — git is the journal.
ORDER = ("id", "circle", "date", "text", "state", "amended")

CAP = 800       # chars per topic — one short paragraph
BUDGET = SET.setting_value_read("topics_budget", 2400)   # chars projected into BLOCK 2,
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
        return SS.register_read(PATH)
    return {"register": "topics", "next_id": 1,
            "doc": {"preamble": _PREAMBLE}, TABLE: []}


def _save(doc: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    SS.register_write(PATH, doc, TABLE, ORDER)


# ------------------------------------------------------------------ register
def topic_read() -> list[dict]:
    """Every topic on file, open and tombstoned alike, unordered."""
    return _doc().get(TABLE, [])


def topic_open_read() -> list[dict]:
    """OPEN topics, newest first — the projection order."""
    es = [t for t in topic_read() if t.get("state") == "open"]
    return sorted(es, key=lambda t: t.get("date", ""), reverse=True)


def topic_new_render(doc: dict, circle: str, text: str) -> tuple[dict, dict]:
    """PURE — one open topic appended to a COPY of `doc`; the phase-2
    driver stages the render and the register gate verifies it
    (docs/REGISTER_GATE_DESIGN.md), so validation exists exactly once
    (add(), the same logic plus a direct _save(), went 2026-09-03, D81)."""
    import copy
    doc = copy.deepcopy(doc)
    n = doc.get("next_id", 1)
    rec = {"id": f"TP-{n:04d}", "circle": circle, "date": SS.register_now(),
           "text": RM.remember_truncate(text, CAP), "state": "open"}
    doc.setdefault(TABLE, []).append(rec)
    doc["next_id"] = n + 1
    return doc, rec


def topic_close(tid: str) -> tuple[bool, str]:
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
    row["state"] = f"closed by Self {SS.register_now()}"
    _save(doc)
    return True, f"{tid} closed — kept as a tombstone"


def topic_update(tid: str, text: str) -> tuple[bool, str]:
    """Replace one OPEN topic's text in place — same id, same circle, same date — and
    stamp `amended` with today's date (R465, B116, 2026-09-07). Located by id, the way
    every topic verb addresses a row (/topic-list prints ids, not numbers). The text
    takes topic_new_render()'s own rule: CAP-truncated at a word boundary, never refused
    for length; an empty text is refused. A tombstone is not updated — closed rows are
    history. Rides REGISTER_CLASS.register_row_update(); the save is this module's."""
    body = " ".join(text.split())

    def _precheck(fields: dict, row: dict) -> str:
        if not fields["text"]:
            return "nothing to update"
        if row.get("state") != "open":
            return f"{row.get('id')} is not open (state={row.get('state')!r}) — a tombstone"
        return ""

    doc = _doc()
    ok, msg, row = SS.register_row_update(
        doc, TABLE, locate=tid, precheck=_precheck,
        fields={"text": RM.remember_truncate(body, CAP), "amended": SS.register_now()[:10]})
    if not ok:
        return False, msg
    _save(doc)
    return True, f"{tid} updated — {row['text'][:48]}..."


def topic_wrap(s: str, n: int) -> list[str]:
    """`s` wrapped to `n` columns, as a list of lines, beneath a label.
    MOVED FROM self_schema.py 2026-09-03 (cohesion re-homing, stage 4): it
    was written as every register topic_list()'s hard-wrap convention and this
    is the one listing that uses it."""
    import textwrap
    return textwrap.wrap(s, n) or [""]


def topic_list() -> str:
    es = topic_read()
    closed = sum(1 for t in es if t.get("state") != "open")
    out = [f"  {len(es) - closed} open topic(s), {closed} closed"]
    for t in topic_open_read():
        out.append(f"  {t['id']}  {t.get('circle', '?')}")
        for ln in topic_wrap(t.get("text", ""), 72):
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
    print(topic_list())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
