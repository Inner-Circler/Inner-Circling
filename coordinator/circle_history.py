#!/usr/bin/env python3
"""
circle_history.py — the CIRCLE_HISTORY register. SYNTHESIS's one durable
record per circle: what the circle was, and what moved.

    python coordinator/circle_history.py            listing
    python coordinator/circle_history.py --init     write the empty register
    python coordinator/circle_history.py --show     newest entry, in full

RULED: R165 promoted `self/narrative_arc.md`'s append-only bullet to a
`<memory_reflexive>`-shaped TOML record; R186 (H1) added the PRIOR entry
to SYNTHESIS's inputs, so each entry can genuinely continue the last, and
bound HISTORY at {history_cap}. R191 raised that cap 600 -> 8000: 600 was
set by analogy to RECORD_CAP, which holds one part's note to itself, not
the durable account of a whole circle. `self/narrative_<date>.md`'s
longhand is unaffected and gains no writer here.

    id      "CH-" DIGIT+, per-register high-water next_id, minted by the
            COORDINATOR after SYNTHESIS returns (R170's discipline). The
            id space is NEW with this file — flagged for docs/BNF.md's
            register-of-registers table, no collision on 2026-08-15.
    circle  the OT this entry is ABOUT.
    date    UTC ISO, microseconds.
    text    the HISTORY section's prose. TARGET (7200) is what the prompt
            asks for; CAP (8000) is what this register refuses at. A cut
            history entry is a worse record than the prior one standing
            alone, so it is REFUSED, never truncated — and a TARGET breach
            gets one insistent re-ask before it can become a CAP breach.
    chain   the predecessor entry's id — set by the coordinator whenever
            one exists (a linked list by construction; content continuity
            comes from SYNTHESIS actually reading the prior entry, R186).

ACCUMULATE, NEVER PRUNE. One record per processed circle at most; the
register gate (docs/REGISTER_GATE_DESIGN.md) enforces exactly that in
paired mode. WRITER: the phase-2 driver only.
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Rebindable for probes — test suites never write the live register.
PATH = ROOT / "self" / "circle_history.toml"

TABLE = "history"
ORDER = ("id", "date", "circle", "text", "chain")
# {history_cap}. RAISED 600 -> 8000 , 2026-08-15 (R191), after the
# first real rehearsal refused a 43-statement circle's HISTORY at 795 chars.
# R186/H5 had set 600 BY ANALOGY — "the same RECORD_CAP every other record
# uses" — but remember's 600 holds one part's note to itself, while this is
# the durable account of a whole circle, the record meant to propagate
# forward through circles. The analogy was to the wrong neighbour.
#
# Safe to raise: nothing projects this register into a prompt block. Its one
# consumer is SYNTHESIS's own input, which reads the single most recent entry
# (R186/H1), so the cost of the larger cap is bounded at one record per run.
CAP = 8000

# WHAT THE PROMPT ASKS FOR, 10% under the cap the register ENFORCES.
# R192, 2026-08-15: "set the MAX_SIZE sent to the LLM to 7200,
# allowing a 10% overshoot."
#
# The two numbers do different jobs, and collapsing them is what made the
# first breach expensive. CAP is a REFUSAL — it protects the register and
# must never move to accommodate a model. TARGET is an INSTRUCTION, and a
# model asked for exactly its hard limit has no room to be slightly long
# without being refused. The 800-char gap absorbs ordinary overshoot; a
# breach of TARGET is survivable and triggers one insistent re-ask (see
# inter_circle), while a breach of CAP is not.
TARGET = 7200

_PREAMBLE = (
    "CIRCLE_HISTORY -- one durable entry per circle, written by SYNTHESIS "
    "at /close's second phase (R165 promoted narrative_arc.md's bullet to "
    "this record; R186 feeds each run the prior entry; R191/R192 ask for "
    "7200 and cap at 8000). chain names the predecessor. Accumulate, never "
    "prune; the "
    "register gate enforces append-only.")


def _doc() -> dict:
    if PATH.is_file():
        return SS.load(PATH)
    return {"register": "circle_history", "next_id": 1,
            "doc": {"preamble": _PREAMBLE}, TABLE: []}


def entries() -> list[dict]:
    return _doc().get(TABLE, [])


def most_recent() -> dict | None:
    es = sorted(entries(), key=lambda r: r.get("date", ""))
    return es[-1] if es else None


def render_new(doc: dict, circle: str, text: str) -> tuple[dict, dict]:
    """PURE — one new entry for the phase-2 driver, chained to the newest
    prior entry when one exists. REFUSES oversize (ValueError) rather than
    truncating; the caller reports and the prior entry stays current."""
    import copy
    text = " ".join(text.split())
    if len(text) > CAP:
        raise ValueError(f"HISTORY is {len(text):,} chars, cap is {CAP} — "
                         f"refused, not truncated")
    doc = copy.deepcopy(doc)
    recs = doc.setdefault(TABLE, [])
    n = doc.get("next_id", 1)
    rec = {"id": f"CH-{n:04d}", "date": SS.now(), "circle": circle,
           "text": text}
    if recs and recs[-1].get("id"):
        rec["chain"] = recs[-1]["id"]
    recs.append(rec)
    doc["next_id"] = n + 1
    return doc, rec


def main() -> int:
    a = sys.argv[1:]
    if "--init" in a:
        if PATH.is_file():
            print(f"  {PATH.relative_to(ROOT)} already exists — untouched")
            return 0
        SS.save(PATH, _doc(), TABLE, ORDER)
        print(f"  wrote {PATH.relative_to(ROOT)} (empty register)")
        return 0
    if "--show" in a:
        rec = most_recent()
        if rec is None:
            print("  (no entries)")
            return 0
        print(f"  {rec['id']}  {rec.get('circle', '?')}  {rec['date']}")
        print(f"  {rec['text']}")
        return 0
    es = entries()
    print(f"  {len(es)} entr{'y' if len(es) == 1 else 'ies'}")
    for r in sorted(es, key=lambda x: x.get("date", "")):
        print(f"  {r['id']}  {r.get('circle', '?')}"
              + (f"  chain->{r['chain']}" if r.get("chain") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
