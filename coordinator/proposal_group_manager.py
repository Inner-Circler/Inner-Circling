#!/usr/bin/env python3
"""
proposal_group_manager.py — the PROPOSAL COALESCE (R356, B69): one reader/writer of
(coalesce.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)
self/coalesce.toml, and the one model pass that groups a pending queue.

WHAT THIS IS. The vetting queue accumulates rows that are one ask in
different words — across circles, across authors, and across the propose
and practice registers. 2026-08-26's live case: BP-0042 + P-4 + BP-0044,
one practice in three wordings from three circles (the newest of which
itself said it had recurred); P-1 + P-2, one label act a word variant
apart; P-3 + BP-0043, one practice in two registers. The part-memory
pipeline consolidates on recurrence (DREAMING's CONTINUES chain,
distillation's reinforcement keeper-signal); the proposal pipeline
duplicated on it, and Self cleared the duplicates by hand. Ruled R356:
ONE model pass over the WHOLE pending set, run just before the vetting
ask, hash-guarded on the set's content so it fires only when the set
changed — in practice once per circle, at close, after the circle's new
proposals are staged; the next open presents the same groups for free.

THE MODEL ONLY SUGGESTS. A group is a presentation: vetting shows it as
one strengthened ask carrying its recurrence count and source circles,
and Self rules it. Accepting enacts the PRIMARY member through that
member's own existing approve path — the member's OWN WORDS are what land
in the record, never model-merged prose (the same "prefer the part's own
words" rule mid_term's derivation holds) — and denies the other members
through their own deny paths. A split dissolves the group for this
queue-state and the members are asked individually, this same session.
Nothing merges silently, and nothing here writes the proposal or practice
registers — vetting rules through their own one-writers; this module
writes ONLY self/coalesce.toml.

PROVENANCE. A non-primary member accepted-away reads "denied" in its own
register; the WHY lives here — the ruled group keeps its members, primary,
gloss and full ruling mapping forever in its `status` field. Ruled groups
survive every re-derive; only live (unruled) groups are replaced when the
pending set changes. A split group can be re-proposed by a later derive
after the set changes — Self's split holds for a queue-state, not forever,
by design: a recurrence after new evidence is a fair re-ask.

FAILS OPEN, DELIBERATELY. Vetting is how circles open; a suggestion pass
must never block it. A model reply that cannot be parsed, a truncated
reply (stop_reason max_tokens), or any invalid line writes an EMPTY live
set with the current hash and a `note` saying why — the queue is still
vetted, just ungrouped, and the next set change retries. Every invalid
line is dropped with a note, never guessed at.

WRITTEN IMMEDIATELY, NEVER CIRCLE-COMMITTED — proposal_vet()'s
own pattern for the registers it rules: this file is real on disk the
moment it changes and sits uncommitted until a human commits it.

    python coordinator/proposal_group_manager.py             state: freshness + groups
    python coordinator/proposal_group_manager.py --refresh   force one derive (model call)
    python coordinator/proposal_group_manager.py --selftest  parse/validate/hash, no API
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

TABLE = "group"
ORDER = ("id", "members", "primary", "gloss", "sources", "status")
ID_PREFIX = "CG-"
# THE CAP IS llm_client.AUX_MAX_TOKENS, read at the call (2026-08-28).
# Thinking counts against it (DERIVE_MAX_TOKENS's lesson, R354) and the
# visible output is a few lines — reasoning shared with inter_circle's
# diagnostic call, which held the same literal; llm_client owns it. A local
# MAX_TOKENS alias stood here until 2026-09-03.
import LLM_response_disassembler as RD                         # noqa: E402
import record_paths as _RP                                         # noqa: E402

SYSTEM = """\
You are grouping a vetting queue for an IFS-circle coordinator. Below are
pending proposals, each with a ref, its provenance, and its text. Group ONLY
rows that are the SAME ask in different words — the same intended practice,
or the same intended command. Sharing a theme is NOT the same ask; when in
doubt, do not group. A group has at least two members and no row may appear
in two groups.

PRIMARY is the member whose own wording should be enacted if Self accepts
the group — prefer the most complete and most recent. For command-shaped
proposals, group only commands whose effect is identical, and PRIMARY is
the exact command that should run.

Output format, exactly, one line per group, nothing else. Emit NOTHING at
all when no rows qualify.

GROUP: <ref> <ref> ... | PRIMARY: <ref> | GLOSS: <one sentence naming the shared ask>"""

# THE READER OF THAT LINE is LLM_response_disassembler.message_groups_read() (its
# _GROUP_LINE_RE), 2026-09-02 — it was parse_reply()/_LINE_RE here. The
# format above is the one home of what the model is asked for; the regex
# beside it in the disassembler is the one home of how a reply is read.


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def proposal_group_locate() -> pathlib.Path:
    return _RP.record_dir(ROOT, "self") / "coalesce.toml"


# --------------------------------------------------------------- pending set
def proposal_group_pending_read() -> list[dict]:
    """Every row awaiting a ruling, both registers, as the model and the
    hash see it: ref ("practice:BP-0044" / "propose:P-4"), text, sources,
    circle. Reads the registers through their own readers, fresh."""
    import practice_manager as PM
    import proposal_manager as PR
    rows = []
    for r in PM.practice_pending_list():
        rows.append({"ref": f"practice:{r['id']}", "kind": "practice",
                     "id": r["id"], "text": r.get("title", ""),
                     "sources": list(r.get("sources", [])),
                     "circle": r.get("circle", "")})
    for r in PR.proposal_pending_list():
        rows.append({"ref": f"propose:{r['id']}", "kind": "propose",
                     "id": r["id"], "text": r.get("text", ""),
                     "sources": list(r.get("sources", [])),
                     "circle": r.get("circle", "")})
    return rows


def proposal_group_hash_write(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda x: x["ref"]):
        h.update(f"{r['ref']}\x00{r['text']}\x00".encode("utf-8"))
    return h.hexdigest()[:16]


# ------------------------------------------------------------------ the doc
def _load() -> dict:
    import REGISTER_CLASS as SS
    p = proposal_group_locate()
    if p.is_file():
        return SS.register_read(p)
    return {"register": "coalesce", "next_id": 1, "hash": "", "derived": "",
            "note": "", TABLE: []}


def _save(doc: dict) -> None:
    import REGISTER_CLASS as SS
    p = proposal_group_locate()
    p.parent.mkdir(parents=True, exist_ok=True)
    SS.register_write(p, doc, TABLE, ORDER)


# ----------------------------------------------------------- parse/validate
# ------------------------------------------------------------------ derive
def _call(system: str, user: str, client=None):
    """The Reply, burst (LLM_response_disassembler). A client per call,
    part_dreaming._call's own shape; `client` is injectable so no test ever
    reaches the network."""
    # THROUGH THE TRANSPORT SINCE 2026-08-28 (stage 1 of the provider
    # socket). The hand-rolled key resolution that stood here read `.env`
    # line by line for one key name — which misses a key the shell has
    # already set differently, and every other spelling of the file. The
    # injected-client contract this function documents is unchanged:
    # call_once uses a fake exactly as given and reaches no network.
    import llm_client as LC
    # RECORDED WITH NO PART (R413, 2026-08-31): the grouping pass speaks for
    # the circle, so its turn file is named by kind. The /close checkpoint
    # runs while the circle's turn log is open and lands in the capture; the
    # open checkpoint runs before the next circle's capture exists and, by
    # the ruling's own bound, stays unrecorded.
    return LC.stream_call_once(system, user, LC.AUX_MAX_TOKENS, kind="coalesce",
                        client=client, record=True)


def proposal_group_derive(rows: list[dict], client=None) -> tuple[int, list[str]]:
    """ONE model pass over `rows`. Writes the doc: live groups replaced,
    ruled groups kept, hash and note set. Returns (n_live_groups, notes)."""
    user_lines = []
    for r in rows:
        prov = ", ".join(r["sources"]) or r["circle"] or "unknown source"
        user_lines.append(f"[{r['ref']}] ({prov})\n{r['text']}\n")
    reply = _call(SYSTEM, "\n".join(user_lines), client=client)
    notes: list[str] = []
    text = reply.text
    if reply.truncated:
        text, notes = "", ["reply stopped at max_tokens — treated as no "
                           "groups; retried at the next set change"]
    groups, parse_notes = RD.message_groups_read(text, {r["ref"] for r in rows})
    notes += parse_notes
    doc = _load()
    kept = [g for g in doc.get(TABLE, []) if g.get("status")]
    live = []
    src_by_ref = {r["ref"]: (r["sources"] or [r["circle"]]) for r in rows}
    for g in groups:
        gid = f"{ID_PREFIX}{doc['next_id']:04d}"
        doc["next_id"] += 1
        sources = sorted({s for m in g["members"]
                          for s in src_by_ref.get(m, []) if s})
        live.append({"id": gid, "members": g["members"],
                     "primary": g["primary"], "gloss": g["gloss"],
                     "sources": sources, "status": ""})
    doc[TABLE] = kept + live
    doc["hash"] = proposal_group_hash_write(rows)
    doc["derived"] = _now()
    doc["note"] = "; ".join(notes)
    _save(doc)
    return len(live), notes


def proposal_group_refresh(say=print, client=None) -> str:
    """The hash guard — R356's "just before vet", made cheap. Derives only
    when the pending set's content differs from the stored hash. An empty
    set derives nothing (and clears live groups if any linger)."""
    rows = proposal_group_pending_read()
    doc = _load()
    if not rows:
        if any(not g.get("status") for g in doc.get(TABLE, [])):
            doc[TABLE] = [g for g in doc.get(TABLE, []) if g.get("status")]
            doc["hash"] = proposal_group_hash_write(rows)
            _save(doc)
        return "empty"
    if doc.get("hash") == proposal_group_hash_write(rows):
        return "fresh"
    say(f"  coalesce: pending set changed — one grouping pass "
        f"({len(rows)} row(s))...")
    n, notes = proposal_group_derive(rows, client=client)
    for note in notes:
        say(f"  coalesce: {note}")
    say(f"  coalesce: {n} group(s)")
    return f"derived {n}"


# ------------------------------------------------------------- presentation
def proposal_group_live_read() -> tuple[list[dict], set[str]]:
    """(groups, member_refs) — only unruled groups whose stored hash still
    matches the CURRENT pending set; anything stale presents nothing."""
    doc = _load()
    if doc.get("hash") != proposal_group_hash_write(proposal_group_pending_read()):
        return [], set()
    groups = [g for g in doc.get(TABLE, []) if not g.get("status")]
    refs = {m for g in groups for m in g["members"]}
    return groups, refs


def proposal_group_mark(gid: str, status: str) -> None:
    doc = _load()
    for g in doc.get(TABLE, []):
        if g.get("id") == gid:
            g["status"] = status
    _save(doc)


# ------------------------------------------------------------------ selftest
def selftest() -> int:
    fails: list[str] = []

    def case(name: str, ok: bool) -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails.append(name)

    # The GROUP-line parse cases moved with the parser to
    # coordinator/tests/test_llm_response_disassembler.py, 2026-09-02.
    rows = [{"ref": "propose:P-1", "text": "a"}, {"ref": "propose:P-2",
                                                  "text": "b"}]
    case("the hash is order-insensitive",
         proposal_group_hash_write(rows) == proposal_group_hash_write(list(reversed(rows))))
    case("...and text-sensitive",
         proposal_group_hash_write(rows) != proposal_group_hash_write([{"ref": "propose:P-1", "text": "a"},
                                     {"ref": "propose:P-2", "text": "c"}]))
    print(f"\n  SELF-TEST: {'PASS' if not fails else 'FAIL'} "
          f"({2 - len(fails)} of 2)")
    return 1 if fails else 0


def main() -> int:
    import argparse
    # R356 is the ruling; kept out of description=, which argparse prints.
    ap = argparse.ArgumentParser(description="the proposal coalesce")
    ap.add_argument("--refresh", action="store_true",
                    help="force one grouping pass (a real model call). "
                         "Default: off — a bare run only reports state.")
    ap.add_argument("--selftest", action="store_true",
                    help="parse/validate/hash checks, no API. Default: off.")
    ap.add_argument("--init", action="store_true",
                    help="write the empty register if absent "
                         "(circle_observation_log's own pattern). Default: off.")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.init:
        if proposal_group_locate().is_file():
            print(f"  {proposal_group_locate().relative_to(ROOT)} already exists — untouched")
            return 0
        _save(_load())
        print(f"  wrote the empty register: {proposal_group_locate().relative_to(ROOT)}")
        return 0
    rows = proposal_group_pending_read()
    doc = _load()
    fresh = doc.get("hash") == proposal_group_hash_write(rows)
    print(f"  pending rows   {len(rows)}")
    print(f"  stored groups  {sum(1 for g in doc.get(TABLE, []) if not g.get('status'))} "
          f"live · {sum(1 for g in doc.get(TABLE, []) if g.get('status'))} ruled")
    state = "fresh" if fresh else ("STALE" if rows else "empty set")
    print(f"  hash           {state}")
    if a.refresh:
        if not rows:
            print("  nothing pending — nothing to derive")
            return 0
        n, _notes = proposal_group_derive(rows)
        print(f"  derived {n} group(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
