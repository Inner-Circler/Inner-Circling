#!/usr/bin/env python3
"""
self_observation_log.py — the SELF_OBSERVATION register. SYNTHESIS's note to
Self about the CIRCLE as a working body: its pace, what it avoided, where it
went easily. Addressed to Self, about the room, never about Self.

    python coordinator/self_observation_log.py            listing
    python coordinator/self_observation_log.py --init     write the empty register
    python coordinator/self_observation_log.py --show     newest entry, in full

RULED R256, 2026-08-19, closing B14's DESIGNED half. The log was
`self/self_observation_log.md` and B14 called it an INERT designed datastore —
"nothing writes them today (synthesis is off)". That premise had been false
since 2026-08-15: B3/R189 wired inter_circle.py into `/close`, and R179 had
already ruled SYNTHESIS writes this file. It is a LIVE append target, so it
converts; `self/self.md` does not, because SYNTHESIS reads it back as prompt
input and replaces it whole — a document's shape, not a register's.

    id      "SO-" DIGIT+, per-register high-water next_id, minted by the
            COORDINATOR after SYNTHESIS returns (R170's discipline).
    date    UTC ISO, microseconds. The 29 DAY-SCOPED migrated records carry
            midnight UTC of the day their own header line names — the only
            precision the .md ever held. SO-0030 carries its commit time.
    circle  the OT this entry is ABOUT. ABSENT on 29 of the 30 migrated
            records: the retired nightly ran per NIGHT over whatever circles
            had accumulated, so those entries are day-scoped, not
            circle-scoped. Every record written from here on has one.
    text    the OBSERVATION section, VERBATIM. Multi-line prose, never
            whitespace-collapsed — this is the one place circle_history.py's
            template does not transfer: its `" ".join(text.split())` holds one
            paragraph, while an observation carries "Patterns:" / "Relationship
            dynamics:" / "Opportunities:" structure that flattening destroys.
    note    an annotation ABOUT the record rather than part of it. Present
            only where one is owed — the 2026-08-19 migration set it on the
            single record whose own header line had already been lost.

NO CAP, deliberately. circle_history's CAP/TARGET pair exists because SYNTHESIS
is *asked* for a bounded HISTORY (R191/R192) and the register refuses a breach;
nothing upstream bounds OBSERVATION, so a cap here would be a gate failing on
legitimate output rather than a contract being enforced. Same reasoning
self/best_practices.toml records for its own `cap: None`.

ACCUMULATE, NEVER PRUNE. At most one record per processed circle; the register
gate (docs/REGISTER_GATE_DESIGN.md) enforces that in paired mode. WRITERS: the
phase-2 driver (inter_circle.py), and circle_audit.py's --stage-synthetic,
which mints one real record to rehearse phases 6-9.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import self_schema as SS                                       # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Rebindable for probes — test suites never write the live register.
PATH = ROOT / "self" / "self_observation_log.toml"

TABLE = "observation"
ORDER = ("id", "date", "circle", "text", "salience", "chain", "note")
# salience + chain ADDED 2026-08-26 (R358): SYNTHESIS follows the dreaming
# model — its OBSERVATION is shown the most recent record here and may
# CONTINUE it, with self-assessed SALIENCE, exactly as a part's dreaming
# pass does with its remember chain. Records written before R358 carry
# neither field, which is the same shape remember.toml's pre-DESIGN_V2
# records have: absent, not empty.

# GENERIC, and it must stay generic: packaging/scaffold/self/README.md's own
# rule is that each delegate is byte-equivalent to the document its reader
# builds when the file is absent — which is _doc()'s output, this string
# included. The live register's own preamble is LONGER (it carries the
# 2026-08-19 migration's account of itself); _doc() reads the file whenever
# one exists, so that text persists and only a fresh install ever sees this.
_PREAMBLE = (
    "SELF_OBSERVATION -- what SYNTHESIS noticed about the CIRCLE as a "
    "working body: its pace, what it avoided, where it went easily. "
    "Addressed to Self, about the room, never about Self. One record per "
    "processed circle; accumulate, never prune. No cap: nothing upstream "
    "bounds an OBSERVATION, so this register does not refuse one either.")


def _rel() -> str:
    """PATH for printing. `PATH.relative_to(ROOT)` raises when PATH has been
    rebound to a temp file, which is exactly what the probe suite does to the
    constant above — so a module whose PATH is documented as rebindable must
    not assume PATH is still under ROOT."""
    try:
        return PATH.relative_to(ROOT).as_posix()
    except ValueError:
        return str(PATH)


def _doc() -> dict:
    if PATH.is_file():
        return SS.load(PATH)
    return {"register": "self_observation", "next_id": 1,
            "doc": {"preamble": _PREAMBLE}, TABLE: []}


def entries() -> list[dict]:
    return _doc().get(TABLE, [])


def most_recent() -> dict | None:
    es = sorted(entries(), key=lambda r: r.get("date", ""))
    return es[-1] if es else None


def render_new(doc: dict, circle: str, text: str,
               note: str | None = None, salience: str | None = None,
               continues: bool = False) -> tuple[dict, dict]:
    """PURE — one new entry for the phase-2 driver.

    VERBATIM but for an outer strip. A trailing newline would survive into
    `text` and then not survive `_lit()`'s own `rstrip`, so save()'s
    round-trip guard would refuse the write; stripping here is what keeps the
    record and its rendering the same bytes.

    `salience` and `continues` are R358's dreaming-model fields:
    `continues` chains the new record to the most recent one already in
    `doc` — every SO record carries an id, so unlike remember.py's chain
    there is no id-less record to step over."""
    import copy
    text = text.strip()
    if not text:
        raise ValueError("empty OBSERVATION — nothing to record")
    doc = copy.deepcopy(doc)
    recs = doc.setdefault(TABLE, [])
    n = doc.get("next_id", 1)
    rec = {"id": f"SO-{n:04d}", "date": SS.now(), "circle": circle,
           "text": text}
    if salience:
        rec["salience"] = salience
    if continues and recs:
        rec["chain"] = recs[-1]["id"]
    if note:
        rec["note"] = note
    recs.append(rec)
    doc["next_id"] = n + 1
    return doc, rec


def main() -> int:
    a = sys.argv[1:]
    if "--init" in a:
        if PATH.is_file():
            print(f"  {_rel()} already exists — untouched")
            return 0
        SS.save(PATH, _doc(), TABLE, ORDER)
        print(f"  wrote {_rel()} (empty register)")
        return 0
    if "--show" in a:
        rec = most_recent()
        if rec is None:
            print("  (no entries)")
            return 0
        print(f"  {rec['id']}  {rec.get('circle', '(day-scoped)')}  "
              f"{rec['date']}")
        print(f"  {rec['text']}")
        return 0
    es = entries()
    print(f"  {len(es)} entr{'y' if len(es) == 1 else 'ies'}")
    for r in sorted(es, key=lambda x: x.get("date", "")):
        print(f"  {r['id']}  {r['date'][:10]}  "
              f"{r.get('circle', '(day-scoped)')}  {len(r.get('text', '')):,}"
              f" chars" + ("  [note]" if r.get("note") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
