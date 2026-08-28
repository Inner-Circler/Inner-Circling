#!/usr/bin/env python3
"""
remember.py — the REMEMBER register. A part's own `[remember: <text>]`
note to its future self (docs/BNF.md's ANNOTATION rules, Self's
ruling 2026-08-12).

    python coordinator/remember.py --part <part>
    python coordinator/remember.py --part <part> --project

WHAT A REMEMBER IS. A part writes `[remember: "<text>"]` — at most once
per circle — and `<text>` is trusted verbatim as its own note to its own
future self.

WHEN IT IS WRITTEN, RULED 2026-08-19 (R255): AT CLOSE, in the same reply
that carries the four short_term sections, up to AUTHORED_WORD_CAP words.
The in-round path (markers.apply_remember()) is unchanged and still
works — a part that has something it knows now need not hold it — but
the close is what process_core.md teaches (both the annotation and,
since R-NEW 2026-08-22, the standing guidance beside it),
because at close the part has the whole circle to draw on rather than
the part of it that had happened yet. ONE cap covers both paths:
has_remembered() is the single answer, so spending it in a round leaves
none at close. UNLIKE an ask (asks.py), there is no
second derivation call: the part already knows why it is writing this, so
`derivation_guidance` (process_core.md §REMEMBER, Block 1 since R-NEW) is given at
authoring time instead of a model re-deriving intent after the fact from a
statement written for a different purpose.

NEVER VETTED. Unlike self/best_practices.toml's PRACTICE LIFECYCLE,
nothing here is staged, approved, denied, or seen by Self at all — a
remember never reaches the circle, another part, or the UI. It reaches
only this part's own future BLOCK 4.

FIELDS:

    date      when the record was written, UTC ISO
    circle    the OT it was written in. Not in the original two-field
              spec ("members: date, text") — added because the marker is
              stripped from the transcript at write time (it must never
              reach a future prompt or another part), which means the
              one-per-part-per-circle cap cannot be re-derived by
              rescanning the transcript the way unruled_proposals()/
              propose_proposals() does. `circle` is the durable, resume-safe
              answer to "has this part already used its one remember this
              circle" — has_remembered() reads it back off disk, so a
              --resume sees the same answer a live run would.
    text      the part's own words, truncated to RECORD_CAP chars.
              Stored VERBATIM, not wrapped — migrate_dreams.py's own
              lesson: self_schema.wrap()'s hard-wrap can land inside a
              quoted span and unwrap()'s rejoin does not perfectly
              reverse it.
    class     ADDED 2026-08-17 (D23, best_practices.toml's per-part
              entries moved here): free-text, absent on both live
              [remember: ...] records and DREAMING-authored ones alike
              — present only on a record COORDINATOR-migrated in from
              elsewhere. "better_option" is the one value minted so
              far. Not read by project()/block(); a marker for a human
              or a future filter, not the projection path.
    salience  ADDED 2026-08-22 (docs/INTER_CIRCLE_DESIGN_V2.md, "DREAMING
              extension" — chat-confirmed direction, not yet its own
              RULINGS.md entry): one of passing|notable|charged|resolved,
              PART-AUTHORED ONLY via DREAMING's own reflective pass — the
              coordinator never scores one (R175: no external mechanism
              grading what a part said). Present only on a
              DREAMING-authored record from this build forward; absent on
              every older record and on a live [remember: ...], both of
              which score as "passing" (zero weight) at render time. An
              absent or unparseable model answer coerces to "passing"
              rather than refusing the DREAMING call over one bad tag —
              see coerce_salience().

BUDGETS. Ruled 2026-08-12, widened 2026-08-19 (R255):

    AUTHORED_WORD_CAP = 1000   words, a PART's own authored memory,
                               truncated (not refused)
    RECORD_CAP        = 600    chars, a COORDINATOR-minted record —
                               dreaming's own (inter_circle.py),
                               quote-as-mark's "lands", anything
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
memories, or ~40 short ones, in view. Flagged for Self.

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
import self_schema as SS                                       # noqa: E402
# paths.py is "the one home" these constants were re-derived beside
# (2026-08-19, review tier 5 #41): this module carried its own ROOT and
# SANDBOX with the R176 comment pasted in — the fossil of the 8-file
# sweep that constant exists to prevent. On the NEXT sandbox relocation,
# paths.py updates WriteGuard's allow-list and this module together, so
# path_for() and guard.check() cannot disagree and crash every
# sandbox-mode [remember: ...]. (Tests still rebind RM.ROOT — a module
# attribute assignment overrides an imported binding the same way.)
from paths import ROOT, SANDBOX                                # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TABLE = "remember"
# id/chain ADDED 2026-08-15 with the DREAMING build (docs/
# INTER_CIRCLE_DESIGN.md <memory_reflexive>): a DREAMING-authored record
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
AUTHORED_WORD_CAP = 1000   # words, a PART's own [remember: ...] (R255)
BUDGET = 24000      # chars, projected per part per block (see the header)

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
SALIENCE_K = 3

# THE GATE'S CEILING, and it is deliberately NOT a third budget. Added
# 2026-08-20, after it refused a real live close.
#
# ifs_model.REGISTERS reads ONE number per register, in CHARS, and cannot
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
# still fails. THE WRITERS KEEP THE REAL BUDGETS -- truncate() at
# RECORD_CAP, truncate_words() at AUTHORED_WORD_CAP -- and nothing here
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
GATE_CHAR_CEILING = 12000


def _now() -> str:
    # SS.now(), not a fourth private spelling (2026-08-19, review tier 5
    # #42): this was a verbatim re-implementation — UTC ISO, microseconds
    # — of the function whose own docstring says it is "shared by every
    # register that dates its own records". The microsecond precision the
    # old comment defended (two same-second records must not tie in
    # project()'s newest-first sort) is exactly what SS.now() provides,
    # and _split() compares these stamps against mid_term's cutoff format
    # — one spelling means they can never drift apart.
    return SS.now()


def truncate(text: str, cap: int = RECORD_CAP) -> str:
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


def coerce_salience(raw: str | None) -> str:
    """A part's own SALIENCE answer, normalized. Anything outside
    SALIENCE_VALUES -- absent, malformed, a stray sentence -- coerces to
    "passing" rather than refusing the whole DREAMING call over one bad
    tag (the design's own rule, echoing dream_one's cap-crunch discipline:
    truncate/coerce and report, never refuse the run)."""
    v = (raw or "").strip().lower()
    return v if v in SALIENCE_VALUES else "passing"


def truncate_words(text: str, cap: int) -> str:
    """First `cap` words, TRUNCATED not refused — the same rule
    truncate() follows, in the unit R255 stated the ceiling in.

    LINE STRUCTURE IS PRESERVED, and that is the whole reason this is not
    truncate() with an arithmetic conversion. truncate() opens with
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
    return base / "self" if part == SELF else base / "parts" / part


def path_for(part: str, guard) -> pathlib.Path:
    """The live or sandbox root, guard-checked exactly like every other
    write a live circle makes (short_term_<OT>.md's own pattern in
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
    return SS.load(p) if p.is_file() else {TABLE: []}


# ------------------------------------------------------------------ register
def entries(part: str) -> list[dict]:
    """Every remember on file for `part`, unordered. Always the REAL file —
    see _real_path()."""
    return _load(_real_path(part)).get(TABLE, [])


def has_remembered(part: str, guard) -> bool:
    """Has `part` already written a remember THIS circle? Reads whichever
    root `guard` would write to (live or sandbox), so a sandbox test run
    never sees a real circle's record or vice versa.

    A CLASS-BEARING RECORD IS NOT THE ENTITY'S OWN USE, and is skipped —
    2026-08-19, with quote-as-mark (R251). The cap this
    answers is "at most one per part per circle" on the entity's own
    DELIBERATE annotation: the `[remember: ...]` it typed. `class` is
    present only on a record the COORDINATOR minted (see ORDER's own
    note) — quote_as_mark's "lands", the migrated "better_option" — and
    counting one of those would spend an entity's one use on something
    it never wrote. Without this, the first quote Self ratifies in a
    circle silently refuses Self's own remember for the rest of it."""
    p = path_for(part, guard)
    if not p.is_file():
        return False
    return any(r.get("circle") == guard.ot and not r.get("class")
               for r in _load(p).get(TABLE, []))


def add(part: str, guard, text: str, cls: str | None = None,
        word_cap: int | None = None) -> dict:
    """Append ONE record. Never checks the cap itself — the caller
    (markers.apply_remember() in a round, apply_close_remember() at
    close) decides whether this is the part's one use; this function only
    writes.

    `cls` fills the optional `class` field, and only a COORDINATOR-minted
    record passes one — quote_as_mark.py is the first live caller
    (2026-08-19). A live `[remember: ...]` leaves it None and the key
    stays absent, so those records still render byte-identically.

    `word_cap` selects the AUTHORED ceiling (R255) over the default
    coordinator one. Passing it is what makes a record the part's own
    words rather than a minted summary of them; every caller that omits
    it keeps RECORD_CAP's 600 characters exactly as before."""
    p = path_for(part, guard)
    doc = _load(p)
    body = truncate_words(text, word_cap) if word_cap else truncate(text)
    rec = {"date": _now(), "circle": guard.ot, "text": body}
    if cls:
        rec["class"] = cls
    doc.setdefault(TABLE, []).append(rec)
    p.parent.mkdir(parents=True, exist_ok=True)
    SS.save(p, doc, TABLE, ORDER)
    return rec


def render_dreamt(doc: dict, text: str, circle: str,
                  continues: bool, salience: str | None = None) -> tuple[dict, dict]:
    """PURE — the DREAMING tail for the phase-2 driver: mutates a COPY of
    `doc` (the loaded register) with one coordinator-minted MEM- record,
    returns (new_doc, record). No I/O here: the driver stages the render
    and the register gate verifies it (docs/REGISTER_GATE_DESIGN.md).
    `continues` is the model's own "CONTINUES" signal; the chain names
    the most recent id-bearing record — the same record newest_dreamt()
    showed the model as "your own chain", so the two definitions of
    "prior memory" cannot disagree. A live [remember: ...] written since
    the last dreaming is id-less and is SKIPPED, not a chain-breaker:
    until 2026-08-19 this tested recs[-1] alone, so a part that used its
    live remember in the very circle being dreamed silently lost the
    chain the model had asserted. Id-less records still cannot be chain
    TARGETS, and the gate refuses a chain that names no id in this
    file — chaining past them satisfies it (membership, not adjacency:
    ifs_model's CHAIN-TARGET check).

    `salience` (DESIGN_V2 DREAMING extension, 2026-08-22): the part's own
    SALIENCE answer, ALREADY coerced by the caller (coerce_salience()) —
    this function only stores what it is given. `None` leaves the field
    absent entirely, same as every record minted before this build, so a
    caller with nothing to say about salience keeps this function's output
    byte-identical to before this change."""
    import copy
    doc = copy.deepcopy(doc)
    recs = doc.setdefault(TABLE, [])
    n = doc.get("next_id", 1)
    rec = {"id": f"MEM-{n:04d}", "date": _now(), "circle": circle,
           "text": truncate(text)}
    if continues:
        prior = next((r for r in reversed(recs) if r.get("id")), None)
        if prior is not None:
            rec["chain"] = prior["id"]
    if salience is not None:
        rec["salience"] = salience
    recs.append(rec)
    doc["next_id"] = n + 1
    return doc, rec


def chain_of(doc: dict, rec_id: str) -> list[dict]:
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


def qualifying_chain(doc: dict, rec: dict) -> bool:
    """DESIGN_V2's LONG_TERM_CANDIDATE trigger: `rec` (already staged into
    `doc`) terminates a chain of 3+ records, its own salience is
    "resolved", and at least one PRIOR link in the chain is tagged
    notable or charged. Never auto-writes long_term.md — the caller
    surfaces a candidate topic; a human applies it by hand, same as every
    long_term.md edit today."""
    if rec.get("salience") != "resolved":
        return False
    chain = chain_of(doc, rec.get("id", ""))
    if len(chain) < 3:
        return False
    return any(r.get("salience") in ("notable", "charged") for r in chain[1:])


def newest_dreamt(part: str) -> dict | None:
    """The most recent DREAMING-authored record (id-bearing), or None —
    what DREAMING_PROMPT_V1's "most recent memory in your own chain" means,
    and the ONE record the Privacy invariant lets SYNTHESIS see."""
    es = [r for r in entries(part) if r.get("id")]
    return sorted(es, key=lambda r: r.get("date", ""))[-1] if es else None


# ----------------------------------------------------------------- projection
HEAD_NONE = "## What you have chosen to remember\n\n*Nothing on file yet.*\n"


def project(part: str) -> tuple[str, dict]:
    """This part's memories, newest first, windowed to BUDGET chars.

    INFORMS THE PART OF ITS OWN BUDGET, per the ruling 2026-08-12 — the
    header states how many are on file, how many are shown, how many are
    omitted, and how much of the budget is spent, so the part can choose
    whether writing another is worth pushing an older one out of view.

    NOTHING IS EVER DROPPED FROM THE FILE — only from what is shown here.

    BUT AN OMITTED MEMORY DOES NOT COME BACK ON ITS OWN, and this said it
    "returns to view once newer ones age past it or are never written"
    until 2026-08-27. NEITHER CLAUSE HOLDS. Records do not age; nothing is
    ever deleted; and _window() takes a strict newest-first PREFIX — it
    `break`s at the first record that does not fit, so the shown set is
    always the newest N. The set of records NEWER than an omitted one
    therefore only ever grows, and eviction is monotonic.

    MEASURED, not reasoned: fill past BUDGET, read it back (omitted),
    write nothing (still omitted), write ten more records (still
    omitted). The one thing that could pull a record back is the bounded
    salience/chain reorder above — capped at SALIENCE_K positions, and a
    no-op on every record in this tree today, 0 of 25 carrying either
    field. So the only lever a part actually has is to write the thing
    again, which is what the standing guidance tells it to do."""
    es = sorted(entries(part), key=lambda r: r.get("date", ""), reverse=True)
    if not es:
        return "", {"part": part, "total": 0, "shown": 0, "omitted": 0,
                    "chars": 0}
    # BOUNDED salience/chain-depth reorder (DESIGN_V2, 2026-08-22) — a
    # no-op on any record without a salience tag, so this is byte-identical
    # to before on every register that predates the extension.
    es = _salience_order(es, _chain_depths(es))
    body, shown, used = _window(es)      # the ONE budget window (tier 5 #43)
    omitted = len(es) - shown
    head = (f"## What you have chosen to remember\n\n"
            f"*{len(es)} on file, {shown} shown here within your "
            f"{BUDGET}-character budget ({used} used), {omitted} "
            # NOT "older omitted" (DESIGN_V2, 2026-08-22) — the bounded
            # salience/chain-depth reorder just above can promote an
            # older record ahead of a newer one, so the omitted set can
            # hold a record NEWER than one shown. "older" was true only
            # under pure recency.
            f"omitted from view. Nothing here is owed to anyone — if "
            f"something still matters, say it again.*\n")
    return head + body, {"part": part, "total": len(es),
                         "shown": shown, "omitted": omitted,
                         "chars": used}


def block(part: str) -> tuple[str, str]:
    """WHAT circle.py's system_blocks() CALLS. Same shape as
    mid_term.block() — never a network call, serves whatever is on disk."""
    text, st = project(part)
    note = f"{st['shown']}/{st['total']} shown"
    if st.get("omitted"):
        note += f" · {st['omitted']} omitted"
    return text, note


# ------------------------------------------------------- cutoff-aware split
# B44, RULED 2026-08-15 (docs/INTER_CIRCLE_DESIGN.md, "Projection"; R170's
# "mechanical selection... no LLM call, no new artifact"). Until this, the
# WHOLE register rode in BLOCK 4 (block(), above) — uncached, resent every
# circle regardless of how old a memory was. This splits it at `cutoff`
# (mid_term.refresh_cutoff(part)'s own "when" — this part's identity was
# last derived): everything on file BEFORE that moment is SETTLED (it was
# already there the last time this part's identity was distilled) and
# rides BLOCK 3's cache boundary; everything from that moment on is the
# TAIL — small, uncached, live, same as BLOCK 4 always was.
#
# `project()` above is UNCHANGED and still the whole-register view — the
# CLI (`--project`) and `cutoff=None`'s degrade path both still want it.


def _chain_depths(all_entries: list[dict]) -> dict[str, int]:
    """id -> count of PRIOR records in its own chain, walking `chain`
    pointers across the WHOLE register (never a windowed subset — depth is
    a property of ancestry, not of what happens to be in view). A record
    with no `chain` (or no `id` at all) has depth 0. A cycle (hand-edit
    damage) stops rather than loops, same guard as chain_of()."""
    by_id = {r["id"]: r for r in all_entries if r.get("id")}
    depth: dict[str, int] = {}

    def _d(rid: str, seen: frozenset) -> int:
        if rid in depth:
            return depth[rid]
        r = by_id.get(rid)
        if r is None or rid in seen:
            return 0
        chain = r.get("chain")
        d = 1 + _d(chain, seen | {rid}) if chain else 0
        depth[rid] = d
        return d

    for rid in by_id:
        _d(rid, frozenset())
    return depth


def _salience_order(es: list[dict], depths: dict[str, int],
                    k: int = SALIENCE_K) -> list[dict]:
    """`es`, already newest-first (pure recency), BOUNDED-reordered by each
    record's salience_weight + chain_depth_bonus: a record may move at
    most `k` positions AHEAD of its own recency rank, never behind it and
    never past an unbounded amount (DESIGN_V2: "the two bonuses together
    may move a record at most K positions ahead of pure recency"). A
    record with neither field (every pre-extension record, and every live
    [remember: ...]) scores a bonus of 0 and keeps its recency position
    exactly — this is a no-op on every register this ran against before
    2026-08-22.

    On a target-position TIE, the higher-bonus record wins — otherwise a
    promoted record colliding with an unbonused one at its own target
    would sort back behind it by original index and the promotion would
    do nothing. Ties among EQUAL bonus break by original index, so a run
    against unscored data (every bonus 0) reorders nothing."""
    ranked = []
    for i, r in enumerate(es):
        bonus = min(SALIENCE_WEIGHT.get(r.get("salience"), 0)
                    + depths.get(r.get("id"), 0), k)
        target = max(0, i - bonus)
        ranked.append((target, -bonus, i, r))
    ranked.sort(key=lambda t: (t[0], t[1], t[2]))
    return [r for *_prefix, r in ranked]


def scored_order(part: str) -> list[dict]:
    """This part's whole register, newest-first recency BOUNDED-reordered
    by salience/chain-depth — mid_term.derive()'s DESIGN_V2 input (step 8:
    "the score-ranked record order"). Not used by project()'s own budget
    window's SOURCE list (that stays entries(part) — this is a separate,
    read-only view for the mid_term derivation call)."""
    es = sorted(entries(part), key=lambda r: r.get("date", ""), reverse=True)
    return _salience_order(es, _chain_depths(entries(part)))


def _window(es: list[dict]) -> tuple[str, int, int]:
    """Newest-first BUDGET window over an already-filtered/sorted `es` —
    the record-rendering half of project()'s mechanism, factored out so
    project_settled()/project_tail() — and, since 2026-08-19, project()
    itself (review, tier 5 #43: a third inline copy of this loop
    survived its own factoring-out) — share ONE definition of "fits the
    budget". The head line stays each caller's own: BLOCK 3's settled
    header and BLOCK 4's tail header must not share literal text
    (check_block_overlap.py, R158).

    `break`, not `continue`, at the budget edge (tier 5 #57): skipping
    an over-budget NEWER record and going on rendering older ones was
    fill-packing, while every header says "{omitted} OLDER omitted" and
    The 2026-08-12 ruling frames the budget as "pushing an older one
    out of view" — recency is the priority lever, so the window ends at
    the first record that does not fit. Measured before changing:
    2026-08-19, no part's register comes near BUDGET, so no live
    projection changes a byte."""
    lines, used, shown = [], 0, 0
    for r in es:
        # TAGGED WITH THE CIRCLE IT WAS WRITTEN IN — R<OT>:, the operator's
        # own spelling, 2026-08-27. The register has stamped `circle` on
        # every record since the field was added; until now the projection
        # threw it away, so a part received an undated list and could not
        # tell a memory written last night from one written in June.
        #
        # THE COORDINATOR STAMPS IT; A PART NEVER TYPES ONE. A part cannot:
        # the OT reaches no block and no message of its view — verified
        # 2026-08-27 against render_messages() and a rendered prompt — so a
        # part-authored tag could only ever be guessed. Stamping also covers
        # the 25 records already on file, which no instruction could.
        #
        # THE TEXT IS UNTOUCHED, which is the point: the tag is a prefix
        # OUTSIDE `r['text']`, so what a part gets back is still its own
        # words byte-for-byte. An absent or blank `circle` renders bare
        # rather than as `R: ` — no record has one today, and a degrade is
        # cheaper than a migration.
        ot = str(r.get("circle") or "").strip()
        tag = f"R{ot}: " if ot else ""
        block = f"\n- {tag}{r['text']}\n"
        if used + len(block) > BUDGET:
            break
        lines.append(block)
        used += len(block)
        shown += 1
    return "".join(lines), shown, used


def _split(part: str, cutoff: str | None) -> tuple[list[dict], list[dict]]:
    """This part's remember records, newest-first, split at `cutoff` — a
    'YYYY-MM-DDTHH:MM:SS' UTC prefix, mid_term.refresh_cutoff()'s own
    format. A record strictly BEFORE `cutoff` is SETTLED; everything else
    (including a same-second write — see refresh_cutoff()'s docstring) is
    the TAIL. `cutoff=None` puts everything in the tail — nothing has been
    distilled yet, so nothing can be called settled."""
    es = sorted(entries(part), key=lambda r: r.get("date", ""), reverse=True)
    if cutoff is None:
        return [], es
    settled = [r for r in es if r.get("date", "")[:19] < cutoff]
    tail = [r for r in es if r.get("date", "")[:19] >= cutoff]
    return settled, tail


def project_settled(part: str, cutoff: str | None) -> tuple[str, dict]:
    """BLOCK 3's mechanical remember window (B44) — everything on file as
    of this part's last mid_term refresh, budgeted and rendered exactly as
    project() always has, never routed through mid_term's own LLM
    derivation."""
    settled, _tail = _split(part, cutoff)
    if not settled:
        return "", {"part": part, "total": 0, "shown": 0, "omitted": 0,
                    "chars": 0}
    # Chain depth is computed over the WHOLE register (ancestry can cross
    # the settled/tail boundary), the bounded reorder only over this window
    # (DESIGN_V2, 2026-08-22).
    settled = _salience_order(settled, _chain_depths(entries(part)))
    body, shown, used = _window(settled)
    omitted = len(settled) - shown
    head = (f"## What you have chosen to remember\n\n"
            f"*{len(settled)} on file as of your last identity refresh, "
            f"{shown} shown here within your {BUDGET}-character budget "
            # NOT "older omitted" — see project()'s own note on the
            # bounded salience/chain-depth reorder just above.
            f"({used} used), {omitted} omitted from view. Nothing "
            f"here is owed to anyone — say it again if it still matters.*\n")
    return head + body, {"part": part, "total": len(settled), "shown": shown,
                         "omitted": omitted, "chars": used}


def project_tail(part: str, cutoff: str | None) -> tuple[str, dict]:
    """BLOCK 4's uncached tail (B44) — only what this part has written
    SINCE its last mid_term refresh. `cutoff=None` degrades to project()'s
    original whole-register view, unchanged — a part whose mid_term has
    never been derived sees exactly what BLOCK 4 always showed it."""
    if cutoff is None:
        return project(part)
    _settled, tail = _split(part, cutoff)
    if not tail:
        return "", {"part": part, "total": 0, "shown": 0, "omitted": 0,
                    "chars": 0}
    tail = _salience_order(tail, _chain_depths(entries(part)))
    body, shown, used = _window(tail)
    omitted = len(tail) - shown
    head = (f"## Remembered since your last identity refresh\n\n"
            f"*{len(tail)} written this circle so far, {shown} shown here "
            f"within your {BUDGET}-character budget ({used} used)"
            # NOT "older omitted" — see project()'s own note.
            + (f", {omitted} omitted from view" if omitted else "")
            + f". Carries into your identity at the next refresh.*\n")
    return head + body, {"part": part, "total": len(tail), "shown": shown,
                         "omitted": omitted, "chars": used}


def block_settled(part: str, cutoff: str | None) -> tuple[str, str]:
    """WHAT prompt_build.py's BLOCK 3 assembly calls (B44)."""
    text, st = project_settled(part, cutoff)
    note = f"{st['shown']}/{st['total']} shown"
    if st.get("omitted"):
        note += f" · {st['omitted']} omitted"
    return text, note


def block_tail(part: str, cutoff: str | None) -> tuple[str, str]:
    """WHAT prompt_build.py's BLOCK 4 assembly calls (B44) — replaces the
    unconditional block(part) call there."""
    text, st = project_tail(part, cutoff)
    note = f"{st['shown']}/{st['total']} shown"
    if st.get("omitted"):
        note += f" · {st['omitted']} omitted"
    return text, note


# ---------------------------------------------------------------- RECALL
# The SELF half of docs/BNF.md's REMEMBER_PROJECTION, designed 2026-08-14
# and built 2026-08-18 (R224). A PART's half is the two projections above,
# pushed into its prompt whether it asked or not; Self's is a PULL — "not
# a prompt-block injection, an on-demand pull", the BNF's own words — so
# it renders on request and nothing about it reaches a circle.
#
# FILE ORDER, OLDEST FIRST, AND THE NUMBER IS PERMANENT. Every other
# projection here sorts newest-first, because a prompt has a budget and
# recency is the priority signal. A recall list has neither problem, and
# newest-first would give record N a different meaning every time one is
# written — `recall 3` yesterday and `recall 3` today would not be the
# same memory. The register only ever grows (ACCUMULATE, NEVER PRUNE, in
# this module's own header), so position is a stable handle here in a way
# check_best_practices.listing()'s own numbering explicitly is not.
#
# PART-PARAMETRIZED BUT SELF-ONLY IN PRACTICE. `part` defaults to SELF and
# commands.py never passes anything else — deliberately. A remember is
# private to whoever wrote it (docs/BNF.md: "REMEMBER's blast radius is
# the writing entity's own future record"), so a `/recall <part>` form
# would be a privacy hole wearing a convenience's clothes. The parameter
# exists so the tests can prove the Self path reads self/remember.toml
# and nothing under parts/.
PREVIEW_WORDS = 14      # docs/BNF.md, REMEMBER_PROJECTION — its number


def _ordered(part: str) -> list[dict]:
    """File order. `entries()` is documented unordered, so this states the
    order recall depends on rather than inheriting it by luck."""
    return list(entries(part))


def recall_listing(part: str = SELF) -> str:
    """The bare `recall`: one line per record, numbered, each showing the
    first PREVIEW_WORDS words of its text."""
    es = _ordered(part)
    if not es:
        return ("  nothing remembered yet — a [remember: ...] typed at the "
                "circle prompt writes here")
    out = []
    for i, r in enumerate(es, 1):
        words = r.get("text", "").split()
        one = " ".join(words[:PREVIEW_WORDS])
        out.append(f"  {i:>3}. {r.get('date', '')[:10]}  {one}"
                   f"{'…' if len(words) > PREVIEW_WORDS else ''}")
    out.append(f"\n  {len(es)} on file · `recall <n>` for one whole")
    return "\n".join(out)


def recall_record(n: int, part: str = SELF) -> str:
    """`recall <n>`: the whole record, every field it carries.

    EVERY FIELD, not a chosen few. A live record has date/circle/text; a
    DREAMING-authored one also has id and chain; a migrated one has class.
    Naming them here would mean this function needs editing every time the
    register grows a field, and the failure would be silent — a field
    present on disk and invisible to the one command that exists to show
    it. So it renders what is there."""
    es = _ordered(part)
    if not es:
        return "  nothing remembered yet"
    if not 1 <= n <= len(es):
        return f"  {n} is not in 1..{len(es)} — `recall` lists them"
    r = es[n - 1]
    out = [f"  {n}. of {len(es)}"]
    for k in ("id", "date", "circle", "chain", "class", "salience"):
        if r.get(k):
            out.append(f"     {k:<7} {r[k]}")
    out.append("")
    for line in (r.get("text", "") or "(empty)").splitlines() or [""]:
        out.append(f"     {line}")
    return "\n".join(out)


def main() -> int:
    a = sys.argv[1:]
    part = a[a.index("--part") + 1] if "--part" in a else None
    if not part:
        print("  --part <name> required")
        return 1
    if "--project" in a:
        text, st = project(part)
        print(text or "  (nothing on file)")
        print(f"\n  {st}")
        return 0
    es = sorted(entries(part), key=lambda r: r.get("date", ""), reverse=True)
    print(f"  {len(es)} remember(s) for {part}")
    for r in es:
        print(f"\n  {r['date']}  {r.get('circle', '?')}\n    {r['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
