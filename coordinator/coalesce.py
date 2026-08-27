#!/usr/bin/env python3
"""
coalesce.py — the PROPOSAL COALESCE (R356, B69): one reader/writer of
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

WRITTEN IMMEDIATELY, NEVER CIRCLE-COMMITTED — vet_pending_proposals()'s
own pattern for the registers it rules: this file is real on disk the
moment it changes and sits uncommitted until a human commits it.

    python coordinator/coalesce.py             state: freshness + groups
    python coordinator/coalesce.py --refresh   force one derive (model call)
    python coordinator/coalesce.py --selftest  parse/validate/hash, no API
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

TABLE = "group"
ORDER = ("id", "members", "primary", "gloss", "sources", "status")
ID_PREFIX = "CG-"
MAX_TOKENS = 4000     # thinking counts against the cap (DERIVE_MAX_TOKENS's
                      # lesson, R354); the visible output is a few lines.

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

_LINE_RE = re.compile(
    r"^GROUP:\s*(?P<members>\S+(?:\s+\S+)*?)\s*\|\s*PRIMARY:\s*(?P<primary>\S+)"
    r"\s*\|\s*GLOSS:\s*(?P<gloss>.+?)\s*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path() -> pathlib.Path:
    return ROOT / "self" / "coalesce.toml"


# --------------------------------------------------------------- pending set
def pending_set() -> list[dict]:
    """Every row awaiting a ruling, both registers, as the model and the
    hash see it: ref ("practice:BP-0044" / "propose:P-4"), text, sources,
    circle. Reads the registers through their own readers, fresh."""
    import check_best_practices as BPX
    import proposals as PR
    rows = []
    for r in BPX.pending():
        rows.append({"ref": f"practice:{r['id']}", "kind": "practice",
                     "id": r["id"], "text": r.get("title", ""),
                     "sources": list(r.get("sources", [])),
                     "circle": r.get("circle", "")})
    for r in PR.pending():
        rows.append({"ref": f"propose:{r['id']}", "kind": "propose",
                     "id": r["id"], "text": r.get("text", ""),
                     "sources": list(r.get("sources", [])),
                     "circle": r.get("circle", "")})
    return rows


def set_hash(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda x: x["ref"]):
        h.update(f"{r['ref']}\x00{r['text']}\x00".encode("utf-8"))
    return h.hexdigest()[:16]


# ------------------------------------------------------------------ the doc
def _load() -> dict:
    import self_schema as SS
    p = path()
    if p.is_file():
        return SS.load(p)
    return {"register": "coalesce", "next_id": 1, "hash": "", "derived": "",
            "note": "", TABLE: []}


def _save(doc: dict) -> None:
    import self_schema as SS
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    SS.save(p, doc, TABLE, ORDER)


# ----------------------------------------------------------- parse/validate
def parse_reply(reply: str, valid_refs: set[str]) -> tuple[list[dict], list[str]]:
    """(groups, notes). Every invalid line is DROPPED with a note, never
    guessed at: unknown ref, fewer than two members, a duplicate member, a
    member already claimed by an earlier group, a primary outside the
    group. A blank reply is a valid no-groups answer."""
    groups: list[dict] = []
    notes: list[str] = []
    claimed: set[str] = set()
    for raw in reply.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            notes.append(f"unparseable line dropped: {line[:80]!r}")
            continue
        members = m.group("members").split()
        primary = m.group("primary")
        if len(set(members)) != len(members):
            notes.append(f"duplicate member in group dropped: {members}")
            continue
        if len(members) < 2:
            notes.append(f"singleton group dropped: {members}")
            continue
        bad = [x for x in members if x not in valid_refs]
        if bad:
            notes.append(f"unknown ref(s) {bad} — group dropped")
            continue
        if any(x in claimed for x in members):
            notes.append(f"overlapping group dropped: {members}")
            continue
        if primary not in members:
            notes.append(f"primary {primary!r} outside its group — dropped")
            continue
        claimed.update(members)
        groups.append({"members": members, "primary": primary,
                       "gloss": m.group("gloss")})
    return groups, notes


# ------------------------------------------------------------------ derive
def _call(system: str, user: str, client=None) -> tuple[str, str]:
    """(text, stop_reason). A client per call, inter_circle._call's own
    shape; `client` is injectable so no test ever reaches the network."""
    if client is None:
        import llm_client as LC
        from anthropic import Anthropic
        import os
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            env = ROOT / ".env"
            if env.is_file():
                for ln in env.read_text(encoding="utf-8").splitlines():
                    if ln.strip().startswith("ANTHROPIC_API_KEY"):
                        key = ln.split("=", 1)[1].strip().strip('"').strip("'")
        client = Anthropic(api_key=key)
        model = LC.MODEL
    else:
        model = getattr(client, "model", "fake")
    resp = client.messages.create(
        model=model, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in resp.content
                   if getattr(b, "type", "") == "text").strip()
    return text, getattr(resp, "stop_reason", None) or ""


def derive(rows: list[dict], client=None) -> tuple[int, list[str]]:
    """ONE model pass over `rows`. Writes the doc: live groups replaced,
    ruled groups kept, hash and note set. Returns (n_live_groups, notes)."""
    user_lines = []
    for r in rows:
        prov = ", ".join(r["sources"]) or r["circle"] or "unknown source"
        user_lines.append(f"[{r['ref']}] ({prov})\n{r['text']}\n")
    reply, stop = _call(SYSTEM, "\n".join(user_lines), client=client)
    notes: list[str] = []
    if stop == "max_tokens":
        reply, notes = "", ["reply stopped at max_tokens — treated as no "
                            "groups; retried at the next set change"]
    groups, parse_notes = parse_reply(reply, {r["ref"] for r in rows})
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
    doc["hash"] = set_hash(rows)
    doc["derived"] = _now()
    doc["note"] = "; ".join(notes)
    _save(doc)
    return len(live), notes


def refresh_if_stale(say=print, client=None) -> str:
    """The hash guard — R356's "just before vet", made cheap. Derives only
    when the pending set's content differs from the stored hash. An empty
    set derives nothing (and clears live groups if any linger)."""
    rows = pending_set()
    doc = _load()
    if not rows:
        if any(not g.get("status") for g in doc.get(TABLE, [])):
            doc[TABLE] = [g for g in doc.get(TABLE, []) if g.get("status")]
            doc["hash"] = set_hash(rows)
            _save(doc)
        return "empty"
    if doc.get("hash") == set_hash(rows):
        return "fresh"
    say(f"  coalesce: pending set changed — one grouping pass "
        f"({len(rows)} row(s))...")
    n, notes = derive(rows, client=client)
    for note in notes:
        say(f"  coalesce: {note}")
    say(f"  coalesce: {n} group(s)")
    return f"derived {n}"


# ------------------------------------------------------------- presentation
def live_groups() -> tuple[list[dict], set[str]]:
    """(groups, member_refs) — only unruled groups whose stored hash still
    matches the CURRENT pending set; anything stale presents nothing."""
    doc = _load()
    if doc.get("hash") != set_hash(pending_set()):
        return [], set()
    groups = [g for g in doc.get(TABLE, []) if not g.get("status")]
    refs = {m for g in groups for m in g["members"]}
    return groups, refs


def mark(gid: str, status: str) -> None:
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

    valid = {"practice:BP-0042", "propose:P-4", "practice:BP-0044",
             "propose:P-1", "propose:P-2"}
    g, n = parse_reply(
        "GROUP: practice:BP-0042 propose:P-4 practice:BP-0044 | "
        "PRIMARY: practice:BP-0044 | GLOSS: one relabel-check practice",
        valid)
    case("a valid group parses whole",
         len(g) == 1 and g[0]["primary"] == "practice:BP-0044"
         and len(g[0]["members"]) == 3 and not n)
    g, n = parse_reply("GROUP: propose:P-9 propose:P-1 | PRIMARY: propose:P-1 "
                       "| GLOSS: x", valid)
    case("an unknown ref drops the group, with a note", not g and n)
    g, n = parse_reply("GROUP: propose:P-1 | PRIMARY: propose:P-1 | GLOSS: x",
                       valid)
    case("a singleton drops", not g and n)
    g, n = parse_reply(
        "GROUP: propose:P-1 propose:P-2 | PRIMARY: propose:P-1 | GLOSS: x\n"
        "GROUP: propose:P-2 propose:P-4 | PRIMARY: propose:P-4 | GLOSS: y",
        valid)
    case("an overlapping second group drops, the first stands",
         len(g) == 1 and g[0]["members"] == ["propose:P-1", "propose:P-2"])
    g, n = parse_reply("GROUP: propose:P-1 propose:P-2 | PRIMARY: propose:P-4 "
                       "| GLOSS: x", valid)
    case("a primary outside its group drops", not g and n)
    g, n = parse_reply("here are the groups I found:", valid)
    case("prose drops with a note, never guessed at", not g and n)
    g, n = parse_reply("", valid)
    case("an empty reply is a valid no-groups answer", not g and not n)

    rows = [{"ref": "propose:P-1", "text": "a"}, {"ref": "propose:P-2",
                                                  "text": "b"}]
    case("the hash is order-insensitive",
         set_hash(rows) == set_hash(list(reversed(rows))))
    case("...and text-sensitive",
         set_hash(rows) != set_hash([{"ref": "propose:P-1", "text": "a"},
                                     {"ref": "propose:P-2", "text": "c"}]))
    print(f"\n  SELF-TEST: {'PASS' if not fails else 'FAIL'} "
          f"({9 - len(fails)} of 9)")
    return 1 if fails else 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="the proposal coalesce (R356)")
    ap.add_argument("--refresh", action="store_true",
                    help="force one grouping pass (a real model call). "
                         "Default: off — a bare run only reports state.")
    ap.add_argument("--selftest", action="store_true",
                    help="parse/validate/hash checks, no API. Default: off.")
    ap.add_argument("--init", action="store_true",
                    help="write the empty register if absent "
                         "(self_observation_log's own pattern). Default: off.")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.init:
        if path().is_file():
            print(f"  {path().relative_to(ROOT)} already exists — untouched")
            return 0
        _save(_load())
        print(f"  wrote the empty register: {path().relative_to(ROOT)}")
        return 0
    rows = pending_set()
    doc = _load()
    fresh = doc.get("hash") == set_hash(rows)
    print(f"  pending rows   {len(rows)}")
    print(f"  stored groups  {sum(1 for g in doc.get(TABLE, []) if not g.get('status'))} "
          f"live · {sum(1 for g in doc.get(TABLE, []) if g.get('status'))} ruled")
    state = "fresh" if fresh else ("STALE" if rows else "empty set")
    print(f"  hash           {state}")
    if a.refresh:
        if not rows:
            print("  nothing pending — nothing to derive")
            return 0
        n, _notes = derive(rows)
        print(f"  derived {n} group(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
