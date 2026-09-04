#!/usr/bin/env python3
"""
instrument_manager.py — the one reader of `self/instruments.toml`, and the gate over
(instruments.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)
what it puts into a prompt.

    python coordinator/instrument_manager.py           verify the register
    python coordinator/instrument_manager.py --show    print the block, and whose it is

WHAT THIS IS FOR. Two published psychological instruments measured this
installation's operator on 2025-11-30, and their results lived until
2026-08-27 in two PNG screenshots that no code had ever read. Four places in
the tree described the operator from them — `self/self.md`, `docs/origin.md`
§3, `parts/learner/long_term.md`, and through that last one the Learner's live
BLOCK 3 — and all four read a PERCENTILE as though it were a SCORE. That is
not a wording slip: the instruments report both quantities, they disagree
constantly, and the absolute half is the one that says how strongly a belief
is actually held.

    Good           24/50, midpoint 25       one point below centre
                   12th percentile          lower than 88% of people

Both true. "Pessimistic" follows from the second read alone and does not
survive the first. THE REGISTER KEEPS BOTH so that no future reader has to
choose, and this module refuses a prompt block whose numbers are not in it.

THE FILE IS OPTIONAL AND ITS ABSENCE IS NOT A FAILURE. `self/` never ships —
it is in `packaging/ignore.txt` wholesale — so an installed bundle has no
`instruments.toml` at all, and `instrument_block_render()` returns ε there exactly as it does
for a user who has taken no instrument. A missing file is a person who has not
answered a questionnaire, which is the ordinary case and not an error. A
CORRUPT file is `record_verify.py`'s business, not this module's.

IT REACHES ONE PART, NOT SEVEN — ruled 2026-08-27, the same day the first
version put it in BLOCK 1 and Self objected: BLOCK 1 and 2 are the CIRCLE's
identity and objectives, so a profile there lets *"every part get to know Self
intimately, which is in opposition to the nature of a part"*. It belongs in
BLOCK 3, to the Soul alone — *"isolating it from group knowledge and giving
the Soul a unique role: carrier of the unseen roots of the self"*. Which part
is named by `[block] part` in the register, never here.

WHY THE PROSE LIVES IN THE REGISTER AND NOT HERE. `[block]` in the TOML
carries the words that reach that part's prompt. That is the operator's own
self-description, and hardcoding it in a coordinator module would put it
somewhere they cannot edit without touching code — the same reasoning that
returned `best_practices.toml` to `self/` on 2026-08-16. This module reads;
the register speaks.

WHAT `main()` ASSERTS

    BOUNDS        every score is 0-50 and every percentile 0-100. A score is
                  not a percentile and the whole register exists because those
                  were once confused; the gate says so in numbers.
    REFERENCE     every row names an administration that exists.
    STRUCTURE     PI-99's published shape — 1 primary, 3 secondary, and 22
                  tertiary dimensions split 7 Safe / 7 Enticing / 3 Alive /
                  5 neutral. Taken from the instrument's own report page, so a
                  transcription that drops or duplicates a row fails here
                  rather than silently projecting a short profile.
    PVQ SHAPE     4 higher-order and 19 basic values.
    BACKED        THE ONE THAT MATTERS. Every number in the block's prose must
                  be a `score`, a `percentile`, or a percentile's complement,
                  belonging to a row flagged `prompt = true`. Dates and the
                  scale's own 0/25/50 are exempt and named below.

That last check is this module's reason to exist. The block is prose a human
edits; the rows are the record. Nothing else in the project would notice if the
two drifted, and drift here means a part is told a number about the operator
that no instrument produced. It is the same shape as `check_best_practices`'s
verbatim arrival check, pointed at the one block whose content is claims about
a person.

IT DOES NOT CHECK WHETHER THE PROSE IS TRUE. A number can resolve to a row and
still be described wrongly; only the operator can catch that, which is why the
block is theirs to edit. What the gate removes is the invented number.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import REGISTER_CLASS as SS                                       # noqa: E402

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes this project
# prints. Degrade instead of crashing: a probe that dies formatting its own
# PASS message reports a failure that is not there.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTER = ROOT / "self" / "instruments.toml"

# The response scale's own numbers, and nothing else. Dates are stripped
# before this applies — see `_prose_numbers`.
SCALE_LITERALS = {0, 25, 50}

# PI-99's published structure (Clifton et al., 2019), as the instrument's own
# report page states it. `Good` is computed from 71 of the 99 items directly —
# it is NOT the mean of the three secondaries, which is the single fact about
# this instrument most likely to be guessed wrong.
PI99_TERTIARY = {"Safe": 7, "Enticing": 7, "Alive": 3, "neutral": 5}


def instrument_read() -> dict:
    """The register, or {} when there is none. Absence is not a failure."""
    if not REGISTER.is_file():
        return {}
    return SS.register_read(REGISTER)


def instrument_block_render(part: str) -> str:
    """`part`'s BLOCK 3 instruments section, or "" if it carries none.

    Returned verbatim from the register: heading, blank line, body. No
    derivation and no summarizing — the same directness BLOCK 3 already uses
    for the identity tail this sits beside.

    ONE PART, NAMED BY THE REGISTER. `[block] part` says whose this is, and
    every other part gets ε. Ruled 2026-08-27, on Self's objection to the
    BLOCK 1 version this replaces: BLOCK 1 is the CIRCLE's identity, so a
    profile there tells all seven who Self is intimately, *"which is in
    opposition to the nature of a part"*. The Soul carries it instead —
    *"the unseen roots of the self"* — which is what parts/soul/long_term.md
    already says it carries: timeframe, parent genetics, gender, race,
    cultural and economic and religious and educational context.

    THE PART NAME IS DATA, NOT CODE. It is a directory name in a
    per-installation register, so a rename follows by itself and nothing
    shipped mentions a part — the B29/R123 class, and the same choice
    identity_tail() made."""
    doc = instrument_read()
    b = doc.get("block") or {}
    if (b.get("part") or "").strip() != part:
        return ""
    head, body = (b.get("heading") or "").strip(), (b.get("body") or "").strip()
    if not body:
        return ""
    return f"{head}\n\n{body}" if head else body


def instrument_rows_read(doc: dict) -> list[dict]:
    """Every dimension row, of both kinds, in file order."""
    return list(doc.get("belief", [])) + list(doc.get("value", []))


def _prose_numbers(text: str) -> list[int]:
    """Integers a reader would take as a claim about the operator.

    ISO dates go first — `2025-11-30` is provenance, not a measurement, and
    leaving its parts in would have the gate demand a row scoring 2025."""
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)       # citation years
    return [int(m) for m in re.findall(r"\d+", text)]


def instrument_backed_list(doc: dict) -> list[str]:
    """Numbers in the block's prose with no prompt-flagged row behind them."""
    ok: set[int] = set(SCALE_LITERALS)
    for r in instrument_rows_read(doc):
        if not r.get("prompt"):
            continue
        s, p = r.get("score"), r.get("percentile")
        if isinstance(s, int):
            ok.add(s)
        if isinstance(p, int):
            ok.update({p, 100 - p})     # "lower than 88%" IS percentile 12
    body = (doc.get("block") or {}).get("body") or ""
    return [f"block cites {n} — no prompt-flagged row carries it as a score, "
            f"a percentile, or a percentile's complement"
            for n in sorted(set(_prose_numbers(body)) - ok)]


def instrument_verify(doc: dict) -> list[str]:
    """Every complaint about the register, in report order."""
    f: list[str] = []
    if not doc:
        return f                            # absent is legal; nothing to check

    ids = {a.get("id") for a in doc.get("administration", [])}
    for r in instrument_rows_read(doc):
        who = r.get("name", "?")
        if r.get("administration") not in ids:
            f.append(f"{who}: administration {r.get('administration')!r} "
                     f"is not in this register")
        s, p = r.get("score"), r.get("percentile")
        if not isinstance(s, int) or not 0 <= s <= 50:
            f.append(f"{who}: score {s!r} is outside the 0-50 scale")
        if not isinstance(p, int) or not 0 <= p <= 100:
            f.append(f"{who}: percentile {p!r} is outside 0-100")

    for a in doc.get("administration", []):
        aid = a.get("id")
        if a.get("form") == "PI-99":
            b = [r for r in doc.get("belief", [])
                 if r.get("administration") == aid]
            for tier, want in ((1, 1), (2, 3), (3, 22)):
                got = len([r for r in b if r.get("tier") == tier])
                if got != want:
                    f.append(f"{aid}: PI-99 has {want} tier-{tier} dimensions, "
                             f"found {got}")
            for cluster, want in PI99_TERTIARY.items():
                got = len([r for r in b if r.get("tier") == 3
                           and r.get("cluster") == cluster])
                if got != want:
                    f.append(f"{aid}: PI-99 groups {want} tertiary dimensions "
                             f"under {cluster}, found {got}")
        if a.get("form") == "PVQ-RR":
            v = [r for r in doc.get("value", [])
                 if r.get("administration") == aid]
            for tier, want in (("higher-order", 4), ("basic", 19)):
                got = len([r for r in v if r.get("tier") == tier])
                if got != want:
                    f.append(f"{aid}: PVQ-RR has {want} {tier} values, "
                             f"found {got}")

    f.extend(instrument_backed_list(doc))
    return f


def main() -> int:
    if "--show" in sys.argv:
        who = ((instrument_read().get('block') or {}).get('part') or '').strip()
        text = instrument_block_render(who) if who else ''
        print(text if text else "(no instruments register — block is empty)")
        return 0

    doc = instrument_read()
    if not doc:
        print(f"no register at {REGISTER.relative_to(ROOT)} — "
              f"nothing to check, and that is legal")
        return 0

    problems = instrument_verify(doc)
    for p in problems:
        print(f"FAIL  {p}")
    if problems:
        print(f"\n{len(problems)} problem(s)")
        return 1

    n_admin = len(doc.get("administration", []))
    print(f"PASS  {n_admin} administration(s), "
          f"{len(doc.get('belief', []))} belief and "
          f"{len(doc.get('value', []))} value rows; "
          f"every number in the block is backed by a row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
