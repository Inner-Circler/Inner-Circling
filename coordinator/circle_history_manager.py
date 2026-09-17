#!/usr/bin/env python3
"""
circle_history_manager.py — the CIRCLE_HISTORY register. SYNTHESIS's one durable
(circle_history.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)
record per circle: what the circle was, and what moved.

    python coordinator/circle_history_manager.py            listing
    python coordinator/circle_history_manager.py --init     write the empty register
    python coordinator/circle_history_manager.py --show     newest entry, in full

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
import REGISTER_CLASS as SS                                       # noqa: E402
import record_paths as _RP                                         # noqa: E402
import JOURNAL_CLASS                                               # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Rebindable for probes — test suites never write the live register.
PATH = _RP.CIRCLES_DIR / "circle_history.toml"


@_RP.group_follow
def _path_rebind() -> None:
    """The CURRENT group's register — B117 stage 4 (2026-09-07)."""
    global PATH
    PATH = _RP.CIRCLES_DIR / "circle_history.toml"

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
    "at /close's second phase (each run is fed the prior entry; it asks for "
    "7200 characters and caps at 8000). chain names the predecessor. "
    "Accumulate, never prune; the register gate enforces append-only.")


# The shared LEDGER/JOURNAL core (B105, 2026-09-05 — JOURNAL_CLASS.py). LAMBDA, NOT A VALUE:
# path_fn re-reads PATH from THIS module's own globals on every call, so the probe suites'
# rebind of `circle_history_manager.PATH` (a module attribute) keeps working exactly as it did
# before this existed.
_JC = JOURNAL_CLASS.JournalClass(
    table=TABLE, id_prefix="CH-", cap=CAP, cap_label="HISTORY",
    register="circle_history", preamble=_PREAMBLE, path_fn=lambda: PATH)


def _doc() -> dict:
    return _JC.doc()


def circle_history_read() -> list[dict]:
    return _JC.read()


def circle_history_latest_read() -> dict | None:
    return _JC.latest()


def circle_history_is_empty() -> bool:
    """True while no circle has been processed — the operator's "first circle" (2026-09-16,
    R571), which circle_open.py welcomes instead of asking a topic.
    SYNTHESIS writes the first CH- row at the first live close it processes, so a first
    circle that is aborted, run dry, or whose processing fails leaves this True, and the
    next open is welcomed again."""
    return not _JC.read()


def _rel() -> str:
    """PATH for printing. `PATH.relative_to(ROOT)` raises when PATH has been rebound to a
    temp file, which is exactly what a probe suite does to the constant above — so a module
    whose PATH is documented as rebindable must not assume PATH is still under ROOT.
    circle_observation_manager.py and circle_journal_manager.py both already carry this fix
    (their own docstrings named this module as the one that "predates it and still assumes" —
    found true, and fixed here, when B105's own new direct test rebound PATH the same way)."""
    try:
        return PATH.relative_to(ROOT).as_posix()
    except ValueError:
        return str(PATH)


def circle_history_new_render(doc: dict, circle: str, text: str) -> tuple[dict, dict]:
    """PURE — one new entry for the phase-2 driver, chained to the newest
    prior entry when one exists. REFUSES oversize (ValueError) rather than
    truncating; the caller reports and the prior entry stays current. Row
    construction (id mint, date stamp, chain, cap refusal) delegates to
    JOURNAL_CLASS.py's shared new_render() (B105); this module still owns its
    own text normalization — whitespace-collapsed to one paragraph, unlike
    circle_observation_manager.py's verbatim multi-line OBSERVATION text."""
    text = " ".join(text.split())
    return _JC.new_render(doc, {"circle": circle, "text": text}, chain=True)


def main() -> int:
    a = sys.argv[1:]
    if "--init" in a:
        if PATH.is_file():
            print(f"  {_rel()} already exists — untouched")
            return 0
        SS.register_write(PATH, _doc(), TABLE, ORDER)
        print(f"  wrote {_rel()} (empty register)")
        return 0
    if "--show" in a:
        rec = circle_history_latest_read()
        if rec is None:
            print("  (no entries)")
            return 0
        print(f"  {rec['id']}  {rec.get('circle', '?')}  {rec['date']}")
        print(f"  {rec['text']}")
        return 0
    es = circle_history_read()
    print(f"  {len(es)} entr{'y' if len(es) == 1 else 'ies'}")
    for r in sorted(es, key=lambda x: x.get("date", "")):
        print(f"  {r['id']}  {r.get('circle', '?')}"
              + (f"  chain->{r['chain']}" if r.get("chain") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
