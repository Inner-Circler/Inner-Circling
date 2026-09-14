#!/usr/bin/env python3
"""
remember_manager.py — the REMEMBER register. A part's own `[remember: <text>]`
(remember.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)
note to its future self (docs/BNF.md's ANNOTATION rules, Self's
ruling 2026-08-12).

    python coordinator/remember_manager.py --part <part>
    python coordinator/remember_prompt_projection.py --part <part>    the projection, since 2026-09-03

THE TWO PROJECTIONS LEFT THIS FILE 2026-09-03 (B99 stage 17b, F5 under R435): a part's BLOCK 3/4
halves are remember_prompt_projection.py (project, project_settled/project_tail, block_settled/
block_tail, scored_order) and Self's /remember-list pull is remember_list_projection.py
(recall_listing, recall_record). This file is the RECORD's reader/writer and nothing else.

WHAT A REMEMBER IS. A part writes `[remember: "<text>"]` — at most once
per circle — and `<text>` is trusted verbatim as its own note to its own
future self.

WHEN IT IS WRITTEN, RULED 2026-08-19 (R255): AT CLOSE, in the same reply
that carries the four short_term sections, up to AUTHORED_WORD_CAP words.
The in-round path (annotations.remember_apply()) is unchanged and still
works — a part that has something it knows now need not hold it — but
the close is what process_core.md teaches (both the annotation and,
since R300 (2026-08-22), the standing guidance beside it),
because at close the part has the whole circle to draw on rather than
the part of it that had happened yet. ONE cap covers both paths:
remember_has_written() is the single answer, so spending it in a round leaves
none at close. UNLIKE an ask (asks.py), there is no
second derivation call: the part already knows why it is writing this, so
`derivation_guidance` (process_core.md §REMEMBER, Block 1 since R300) is given at
authoring time instead of a model re-deriving intent after the fact from a
statement written for a different purpose.

NEVER VETTED. Unlike self/best_practices.toml's PRACTICE LIFECYCLE,
nothing here is staged, approved, denied, or seen by Self at all — a
remember never reaches the circle, another part, or the UI. It reaches
only this part's own future BLOCK 4.

FIELDS:

    date      when the record was written, UTC ISO
    circle    the OT it was written in. Not in the original two-field
              spec ("members: date, text") — added because the annotation is
              stripped from the transcript at write time (it must never
              reach a future prompt or another part), which means the
              one-per-part-per-circle cap cannot be re-derived by
              rescanning the transcript the way proposal_unruled_list()/
              proposal_collect() does. `circle` is the durable, resume-safe
              answer to "has this part already used its one remember this
              circle" — remember_has_written() reads it back off disk, so a
              --resume sees the same answer a live run would.
    text      the part's own words, truncated to RECORD_CAP chars.
              Stored VERBATIM, not wrapped — migrate_dreams.py's own
              lesson: REGISTER_CLASS.register_wrap()'s hard-wrap can land inside a
              quoted span and unwrap()'s rejoin does not perfectly
              reverse it.
    class     ADDED 2026-08-17 (D23, best_practices.toml's per-part
              entries moved here): free-text, absent on both live
              [remember: ...] records and DREAMING-authored ones alike
              — present only on a record COORDINATOR-migrated in from
              elsewhere. "better_option" is the one value minted so
              far. Not read by project()/block_settled()/block_tail(); a marker for a human
              or a future filter, not the projection path.
    salience  ADDED 2026-08-22 (docs/INTER_CIRCLE_DESIGN_V2.md, "DREAMING
              extension" — chat-confirmed direction, not yet its own
              ruling under rulings/): one of passing|notable|charged|resolved,
              PART-AUTHORED ONLY via DREAMING's own reflective pass — the
              coordinator never scores one (R175: no external mechanism
              grading what a part said). Present only on a
              DREAMING-authored record from this build forward; absent on
              every older record and on a live [remember: ...], both of
              which score as "passing" (zero weight) at render time. An
              absent or unparseable model answer coerces to "passing"
              rather than refusing the DREAMING call over one bad tag —
              see remember_salience_coerce().

BUDGETS. Ruled 2026-08-12, widened 2026-08-19 (R255):

    AUTHORED_WORD_CAP = 1000   words, a PART's own authored memory,
                               truncated (not refused)
    RECORD_CAP        = 600    chars, a COORDINATOR-minted record —
                               dreaming's own (inter_circle.py),
                               quote-as-lands's "lands", anything
                               migrated in. UNCHANGED by R255: widening
                               what a part may say must not silently
                               widen what dreaming may write.
    BUDGET            = 24000  chars, projected per part per block

TWO WRITERS, TWO CEILINGS, and the register holds both side by side. The
projection does not care which wrote a record; only `class` tells them
apart, and only for a reader.

BUDGET IS CLAUDE'S ARITHMETIC, NOT A RULING. R255 set the 1000 words and
said nothing about the window. At the old 6,000 the window held ~10
records of 600 chars; ONE full-length authored memory is ~6,600 chars,
so leaving BUDGET alone would have made a long memory silently evict
every older one the circle after it wrote it — a projection regression
caused by a ruling that was about authoring. 24,000 keeps ~4 full-length
memories, or ~40 short ones, in view. RULED KEPT, both numbers together,
2026-09-14 (R567, the operator: "c."): measured over the
92 memories then on file, a word is 6.0 characters (median 5.97), so the
cap is ~6,000 characters and the window holds four of them — the ratio
this paragraph sized it for; no part had come within half of the cap
(median 100 words, largest 497). A cap raised alone would let one memory
evict nearly every older one; if it is ever raised, the window rises
with it.

ACCUMULATE, NEVER PRUNE. Nothing here ever deletes a record. project()
windows the projected VIEW to the budget, newest first; the register
itself only grows. A part's only lever over what stays in view is to
write about something again — recency IS the priority signal, so there is
no second annotation for supersede/retire.
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import REGISTER_CLASS as SS                                       # noqa: E402
import record_paths as _RP                                         # noqa: E402
import setting_manager as SET                                         # noqa: E402
import JOURNAL_CLASS                                               # noqa: E402
# record_paths.py is "the one home" these constants were re-derived beside
# (2026-08-19, review tier 5 #41): this module carried its own ROOT and
# SANDBOX with the R176 comment pasted in — the fossil of the 8-file
# sweep that constant exists to prevent. On the NEXT sandbox relocation,
# record_paths.py updates WriteGuard's allow-list and this module together, so
# remember_locate() and guard.check() cannot disagree and crash every
# sandbox-mode [remember: ...]. (Tests still rebind RM.ROOT — a module
# attribute assignment overrides an imported binding the same way.)
from record_paths import ROOT, SANDBOX                                # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TABLE = "remember"
# id/chain ADDED 2026-08-15 with the DREAMING build (docs/
# INTER_CIRCLE_DESIGN_V2.md, DREAMING): a DREAMING-authored record
# carries "MEM-"-prefixed id (per-part high-water next_id, minted by the
# COORDINATOR — R170) and, when it continues the prior dreamt memory, a
# chain naming that record's id. LIVE [remember: ...] records stay id-less
# — backward compatible by the record spec's own rule, and dumps() renders
# old records byte-identically because ORDER only ever grew around them.
# `class` ADDED 2026-08-17 (D23) the same way — optional, present only on
# a best_practices.toml entry migrated in by the coordinator.
# `salience` ADDED 2026-08-22 (DESIGN_V2 DREAMING extension) — LAST, same
# reason: an existing record without one must keep dumping byte-identical.
ORDER = ("id", "date", "circle", "text", "chain", "class", "salience")

RECORD_CAP = 600    # chars, a COORDINATOR-minted record (see the header)
AUTHORED_WORD_CAP = SET.setting_value_read("remember_word_cap", 1000)   # words, a PART's
                    # own [remember: ...] (R255)
BUDGET = SET.setting_value_read("remember_budget", 24000)   # chars, projected per part per
                    # block (see the header)

# ------------------------------------------------------- salience (DESIGN_V2)
# "DREAMING extension -- salience-aware promotion/demotion",
# docs/INTER_CIRCLE_DESIGN_V2.md. Self-reported by the part in its own
# DREAMING pass, never coordinator-computed (see the ORDER comment above
# and R175). What follows is the MECHANICAL half: how a self-reported tag
# moves a record in BLOCK 3/4 windowing. None of the numbers below are
# ruled -- Claude's arithmetic, same discipline as BUDGET/GATE_CHAR_CEILING
# above -- flagged for Self.
SALIENCE_VALUES = ("passing", "notable", "charged", "resolved")
SALIENCE_WEIGHT = {"passing": 0, "notable": 1, "charged": 1, "resolved": 2}

# K: the most positions a record's salience + chain-depth bonus may move it
# AHEAD of its pure-recency rank. Unspecified by the design ("K unspecified
# -- an empirical choice, not designed here"). 3 is picked here: enough for
# a genuinely charged/resolved memory to clear a couple of merely-newer
# passing ones without a short, deeply-chained thread jumping the whole
# window. Flagged for Self, not a ruling.
SALIENCE_K = SET.setting_value_read("salience_lift", 3)

# THE GATE'S CEILING, and it is deliberately NOT a third budget. Added
# 2026-08-20, after it refused a real live close.
#
# register_gate.REGISTERS reads ONE number per register, in CHARS, and cannot
# tell this register's TWO WRITERS apart: a coordinator-minted record and a
# part's own authored one both leave `class` unset today (only
# "better_option" is ever set). So the gate must admit the WIDER of the two
# ceilings -- and the wider one, R255's 1000 WORDS, is stated in a unit the
# gate does not measure.
#
# 12,000 IS A CEILING, NOT A TARGET. Twelve characters per word is about
# double what this corpus actually runs at (the seven authored records of
# circle 2026-08-20_0845 measured 983-1,513 chars), so a legitimate
# full-length memory cannot reach it while a runaway or a corrupted record
# still fails. THE WRITERS KEEP THE REAL BUDGETS -- remember_truncate() at
# RECORD_CAP, remember_words_truncate() at AUTHORED_WORD_CAP -- and nothing here
# widens either of them. Like BUDGET above, this is Claude's arithmetic and
# not a ruling; flagged for Self.
#
# WHY A CONSTANT HERE AND NOT A LITERAL THERE: that dict's own
# circle_history row already carries the lesson, two rows below the
# remember one -- "CAP IS IMPORTED, NOT COPIED. This row said 600 until
# 2026-08-15 and went on saying it after R191 raised circle_history.CAP to
# 8000 -- two places asserting the same number, one of them stale, which
# the gate then enforced against real records that were correct." The
# remember row said 600 and went on saying it after R255 raised the
# authored ceiling. The identical defect, one row up, unnoticed because
# nothing had written a long memory yet.
GATE_CHAR_CEILING = SET.setting_value_read("remember_gate_ceiling", 12000)


def _now() -> str:
    # SS.register_now(), not a fourth private spelling (2026-08-19, review tier 5
    # #42): this was a verbatim re-implementation — UTC ISO, microseconds
    # — of the function whose own docstring says it is "shared by every
    # register that dates its own records". The microsecond precision the
    # old comment defended (two same-second records must not tie in
    # project()'s newest-first sort) is exactly what SS.register_now() provides,
    # and _split() compares these stamps against mid_term's cutoff format
    # — one spelling means they can never drift apart.
    return SS.register_now()


def remember_truncate(text: str, cap: int = RECORD_CAP) -> str:
    """Hard cap at `cap` chars. Trims back to the last word boundary rather
    than slicing mid-word, UNLESS that boundary is far enough back that
    doing so would throw away a large fraction of the budget — then the
    hard cut stands."""
    text = " ".join(text.split())
    if len(text) <= cap:
        return text
    cut = text[:cap]
    sp = cut.rfind(" ")
    if sp > cap * 0.6:
        cut = cut[:sp]
    return cut.rstrip()


def remember_salience_coerce(raw: str | None) -> str:
    """A part's own SALIENCE answer, normalized. Anything outside
    SALIENCE_VALUES -- absent, malformed, a stray sentence -- coerces to
    "passing" rather than refusing the whole DREAMING call over one bad
    tag (the design's own rule, echoing part_dream's cap-crunch discipline (dream_one until 2026-09-03):
    truncate/coerce and report, never refuse the run)."""
    v = (raw or "").strip().lower()
    return v if v in SALIENCE_VALUES else "passing"


def remember_words_truncate(text: str, cap: int) -> str:
    """First `cap` words, TRUNCATED not refused — the same rule
    remember_truncate() follows, in the unit R255 stated the ceiling in.

    LINE STRUCTURE IS PRESERVED, and that is the whole reason this is not
    remember_truncate() with an arithmetic conversion. remember_truncate() opens with
    `" ".join(text.split())`, which flattens every paragraph break into a
    single space — invisible at 600 characters, and destructive at 1000
    words, where a part's memory may have paragraphs it meant. This slices
    the ORIGINAL string at the end of the cap-th word instead, so a
    memory that fits is returned byte-for-byte and one that does not keeps
    its shape up to the cut.

    The ellipsis marks the cut in the record. A silent truncation reads
    later as a part that stopped mid-sentence."""
    if len(text.split()) <= cap:
        return text
    end = 0
    for seen, m in enumerate(re.finditer(r"\S+", text), start=1):
        end = m.end()
        if seen == cap:
            break
    # Attached, not spaced: " ..." would make the record cap+1 words by
    # any counter a reader or a probe uses, which is a cap that does not
    # mean what it says.
    return text[:end].rstrip() + "..."


# ------------------------------------------------------------------- paths
# SELF IS NOT A PART, AND ITS REGISTER IS NOT UNDER parts/.
#
# docs/BNF.md, SELF: "Self's own reflexive note, private, unvetted — written
# to self/remember.toml". Until 2026-08-15 this module could not express that:
# every path was ROOT/"parts"/<name>, so _real_path("self") resolved to
# parts/self/remember.toml — a directory that does not exist and a part that
# is not on the roster. Added with R193's migration, which routes concluded
# threads out of self.md into Self's own REMEMBER.
#
# One sentinel rather than a second module: the RECORD is identical, the caps
# are identical, and the only thing that differs is where the file sits.
SELF = "self"


def _root_for(part: str, base: pathlib.Path) -> pathlib.Path:
    """`base` is the live or sandbox tree root. Self's register lives at
    <base>/self/remember.toml; a part's at <base>/parts/<part>/."""
    return _RP.record_dir(base, "self") if part == SELF else _RP.record_dir(base, "parts") / part


def remember_locate(part: str, guard) -> pathlib.Path:
    """The live or sandbox root, guard-checked exactly like every other
    write a live circle makes (short_term_<OT>.toml's own pattern in
    circle.py). `guard` is duck-typed: `.live`, `.ot`, `.check(path)`."""
    base = SANDBOX if not guard.live else ROOT
    return guard.check(_root_for(part, base) / "remember.toml")


def _real_path(part: str) -> pathlib.Path:
    """The REAL file, unconditionally — for prompt-assembly reads. Live and
    sandbox circles both read a part's actual identity from ROOT/parts/
    already (long_term.md, mid_term.md both do
    this); only WRITES are sandboxed. Same rule here."""
    return _root_for(part, ROOT) / "remember.toml"


def _load(p: pathlib.Path) -> dict:
    return SS.register_read(p) if p.is_file() else {TABLE: []}


# ------------------------------------------------------------------ register
def remember_read(part: str) -> list[dict]:
    """Every remember on file for `part`, unordered. Always the REAL file —
    see _real_path()."""
    return _load(_real_path(part)).get(TABLE, [])


def remember_has_written(part: str, guard) -> bool:
    """Has `part` already written a remember THIS circle? Reads whichever
    root `guard` would write to (live or sandbox), so a sandbox test run
    never sees a real circle's record or vice versa.

    A CLASS-BEARING RECORD IS NOT THE ENTITY'S OWN USE, and is skipped —
    2026-08-19, with quote-as-lands (R251). The cap this
    answers is "at most one per part per circle" on the entity's own
    DELIBERATE annotation: the `[remember: ...]` it typed. `class` is
    present only on a record the COORDINATOR minted (see ORDER's own
    note) — quote_as_lands's "lands", the migrated "better_option" — and
    counting one of those would spend an entity's one use on something
    it never wrote. Without this, the first quote Self ratifies in a
    circle silently refuses Self's own remember for the rest of it."""
    p = remember_locate(part, guard)
    if not p.is_file():
        return False
    return any(r.get("circle") == guard.ot and not r.get("class")
               for r in _load(p).get(TABLE, []))


def remember_add(part: str, guard, text: str, cls: str | None = None,
        word_cap: int | None = None) -> dict:
    """Append ONE record. Never checks the cap itself — the caller
    (annotations.remember_apply() in a round, apply_close_remember() at
    close) decides whether this is the part's one use; this function only
    writes.

    `cls` fills the optional `class` field, and only a COORDINATOR-minted
    record passes one — quote_as_lands.py is the first live caller
    (2026-08-19). A live `[remember: ...]` leaves it None and the key
    stays absent, so those records still render byte-identically.

    `word_cap` selects the AUTHORED ceiling (R255) over the default
    coordinator one. Passing it is what makes a record the part's own
    words rather than a minted summary of them; every caller that omits
    it keeps RECORD_CAP's 600 characters exactly as before."""
    p = remember_locate(part, guard)
    doc = _load(p)
    body = remember_words_truncate(text, word_cap) if word_cap else remember_truncate(text)
    rec = {"date": _now(), "circle": guard.ot, "text": body}
    if cls:
        rec["class"] = cls
    doc.setdefault(TABLE, []).append(rec)
    p.parent.mkdir(parents=True, exist_ok=True)
    SS.register_write(p, doc, TABLE, ORDER)
    return rec


# The shared LEDGER/JOURNAL core (B105, 2026-09-05 — JOURNAL_CLASS.py). Only
# remember_dreamt_render() below has this shape — remember_add() (a part's own live
# [remember: ...]) is id-less, mints no next_id, and is NOT part of it; every path-resolution
# function above, the salience constants, word-cap truncation, and remember_chain_read()/
# remember_chain_qualifies() stay this module's own, unchanged. No cap here: RECORD_CAP
# truncation already happened via remember_truncate() below, before this ever sees the text.
_JC = JOURNAL_CLASS.JournalClass(table=TABLE, id_prefix="MEM-", cap=None)


def remember_dreamt_render(doc: dict, text: str, circle: str,
                  continues: bool, salience: str | None = None) -> tuple[dict, dict]:
    """PURE — the DREAMING tail for the phase-2 driver: mutates a COPY of
    `doc` (the loaded register) with one coordinator-minted MEM- record,
    returns (new_doc, record). No I/O here: the driver stages the render
    and the register gate verifies it (docs/REGISTER_GATE_DESIGN.md).
    `continues` is the model's own "CONTINUES" signal; the chain names
    the most recent id-bearing record — the same record remember_newest_dreamt_read()
    showed the model as "your own chain", so the two definitions of
    "prior memory" cannot disagree. A live [remember: ...] written since
    the last dreaming is id-less and is SKIPPED, not a chain-breaker:
    until 2026-08-19 this tested recs[-1] alone, so a part that used its
    live remember in the very circle being dreamed silently lost the
    chain the model had asserted. Id-less records still cannot be chain
    TARGETS, and the gate refuses a chain that names no id in this
    file — chaining past them satisfies it (membership, not adjacency:
    record_model's CHAIN-TARGET check). JOURNAL_CLASS.py's own chain_target()
    (B105) is this exact rule, generalized — the most recent ID-BEARING row
    in file order, skipping id-less ones.

    `salience` (DESIGN_V2 DREAMING extension, 2026-08-22): the part's own
    SALIENCE answer, ALREADY coerced by the caller (remember_salience_coerce()) —
    this function only stores what it is given. `None` leaves the field
    absent entirely, same as every record minted before this build, so a
    caller with nothing to say about salience keeps this function's output
    byte-identical to before this change."""
    fields = {"circle": circle, "text": remember_truncate(text)}
    if salience is not None:
        fields["salience"] = salience
    return _JC.new_render(doc, fields, chain=continues)


def remember_chain_read(doc: dict, rec_id: str) -> list[dict]:
    """This record and every ancestor reachable via `chain`, TERMINAL
    record first (`rec_id` itself), oldest last. Pure — reads `doc`,
    mutates nothing. A malformed cycle (hand-edit damage; the gate would
    refuse it on commit, but this must not hang inspecting a candidate
    before the gate runs) stops rather than loops."""
    by_id = {r["id"]: r for r in doc.get(TABLE, []) if r.get("id")}
    out: list[dict] = []
    seen: set[str] = set()
    cur = rec_id
    while cur and cur in by_id and cur not in seen:
        r = by_id[cur]
        out.append(r)
        seen.add(cur)
        cur = r.get("chain")
    return out


def remember_chain_qualifies(doc: dict, rec: dict) -> bool:
    """DESIGN_V2's LONG_TERM_CANDIDATE trigger: `rec` (already staged into
    `doc`) terminates a chain of 3+ records, its own salience is
    "resolved", and at least one PRIOR link in the chain is tagged
    notable or charged. Never auto-writes long_term.md — the caller
    surfaces a candidate topic; a human applies it by hand, same as every
    long_term.md edit today."""
    if rec.get("salience") != "resolved":
        return False
    chain = remember_chain_read(doc, rec.get("id", ""))
    if len(chain) < 3:
        return False
    return any(r.get("salience") in ("notable", "charged") for r in chain[1:])


def remember_newest_dreamt_read(part: str) -> dict | None:
    """The most recent DREAMING-authored record (id-bearing), or None —
    what DREAMING_PROMPT_V1's "most recent memory in your own chain" means,
    and the ONE record the Privacy invariant lets SYNTHESIS see."""
    es = [r for r in remember_read(part) if r.get("id")]
    return sorted(es, key=lambda r: r.get("date", ""))[-1] if es else None


def main() -> int:
    a = sys.argv[1:]
    part = a[a.index("--part") + 1] if "--part" in a else None
    if not part:
        print("  --part <name> required")
        return 1
    es = sorted(remember_read(part), key=lambda r: r.get("date", ""), reverse=True)
    print(f"  {len(es)} remember(s) for {part}")
    for r in es:
        print(f"\n  {r['date']}  {r.get('circle', '?')}\n    {r['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
