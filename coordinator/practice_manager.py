"""
practice_manager.py — the PRACTICE register: the one reader/writer for
self/best_practices.toml, and its PRACTICE LIFECYCLE staging (practice_pending_list,
practice_stage_render, practice_approve, practice_deny).

RENAMED 2026-09-03 (stage 7c; R436, R442 — practice_stage_render as the operator spelled it, the
rest by the same pattern, class word first, plain method word; four re-spelled on his cues the
same day — the method word is a VERB: read_by_id, is_eligible, pending_list, list):

    practices -> practice_read        by_id -> practice_read_by_id        eligible -> practice_is_eligible
    broadcast -> practice_broadcast   narrowcast -> practice_narrowcast   add -> practice_add
    pending -> practice_pending_list       render_stage -> practice_stage_render
    approve -> practice_approve       deny -> practice_deny          listing -> practice_list
    delete -> practice_delete         (the constants and ORDER are unchanged)

SPLIT OUT OF check_best_practices.py, 2026-09-03 (cohesion re-homing stage 7, R440
closing D80; the name under R435, Q-B: a register is <CLASS>_manager.py). That file
keeps the VERIFIER — tally, shape, kind and routing checks, run by the pre-commit
hook — and reads this module as PM. Every function below is the verbatim body it had
there; only the file moved. Its history and record shape, carried over:

REWRITTEN 2026-08-11 (R133-R137). Three registers became one: this file used
to hold ONLY circle-facing practices, addressed by a `**<Addressee>** —` text
prefix that `circle.py` scraped out of a rendered `self/circle_briefing.md`.
Two things changed that:

    R133   self/better_options.toml — "how you move" — merged in as
           `addressee = "Self"` records. "Better option" is not a second
           class; it is what a <practice> whose addressee is "Self" is
           CALLED. Broadcast to every part, deliberately, so parts can
           reinforce or suggest evolutions.
    R134   the `**<Addressee>** —` literal prefix retired. Routing is by
           the `addressee` FIELD alone. The prefix existed only because the
           TOML had no reliable field to route on; it now does, and
           `circle.py` no longer parses `self/circle_briefing.md` for
           practices AT ALL — this file is read directly at prompt-assembly
           time. `## Best practices` and `## Better options` no longer
           exist in the briefing (see self/circle_briefing.md's own note).
    R135   projection collapses to `title` ALONE, for every entry. Not the
           whole record. `origin`/`in_room`/`kind`/`record` are read by
           Self and by whoever revises or cites an entry — never spent as
           tokens in a part's prompt. Same discipline that split
           better_options out in the first place (2026-08-02, 62% of
           projected content addressed to nobody in the room), one step
           further: three projected pieces down to one.
    R136   `<practice>` is one production, not two shapes. Every record
           carries the same fields; `kind` is `""` on most circle-behavior
           entries and populated on those descended from better_options.
           R421/B90 (2026-08-31) added the one-directional check that
           enforces the half of that correlation the data actually
           supports: see `_kind_check()`.
    R137   crisis safety content (988/741741/findahelpline.com) moved OUT
           of this register entirely, into `coordinator/process_core.md` as
           static text every part reads unconditionally — found live
           inside a better_options `in_room` field, which the title-only
           rule would have silently stopped projecting.

RECORD SHAPE

    id          "BP-NNNN", stable, never reused — ONE id space; proposal
                staging rows use it too, there is no second prefix
    addressee   "All parts" | "Self" | <PartTag>
    title       the ONE thing that projects
    origin      provenance; record-only
    in_room     practical guidance; record-only
    kind        free-text categorization; record-only
    record      further reasoning; record-only
    state       STAGING (see docs/BNF.md's PRACTICE LIFECYCLE).
                absent = established | "proposed" | "accepted by Self
                <ISO datetime>" | "denied by Self <ISO datetime>"
                (2026-08-12: practice_deny() tombstones rather than deletes). A
                `state = "proposed"` or "denied by Self ..." row is never
                PROJECTS-eligible, whatever its `op` — see practice_is_eligible()/
                practice_broadcast()/practice_narrowcast() below.
    op          STAGING ONLY, present iff state = "proposed":
                "add" | "revise" | "delete"
    target_id   STAGING ONLY: the BP-ID a revise/delete row is about
    sources     PERMANENT since 2026-09-08 ("Structured"): [display, ...],
                every speaker who raised it. Staging-only until then.
    circle      STAGING ONLY: the OT the proposal was raised in
    proposed_at STAGING ONLY: ISO timestamp

A row's staging fields (op/target_id/circle/proposed_at) exist ONLY while
state = "proposed" — the vetting functions below strip them the moment a
row resolves (accepted, revise applied, or deleted).

A SETTLED PROPOSED ROW IS NO LONGER INDISTINGUISHABLE from one Self typed
directly with /practice-add, and that is the deliberate consequence of
keeping `sources`: a row carrying one says which members converged on it,
and a row Self typed has none. That distinction is the point — it was
previously recoverable only by parsing the `author` sentence.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import REGISTER_CLASS as SS                                       # noqa: E402
import part_roster as R                                              # noqa: E402
import PROPOSE_CLASS                                            # noqa: E402
from record_paths import BEST_PRACTICES                                # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parent.parent
# The register's path comes from paths.py since 2026-08-16 (phase 1
# step 0) — this module and REGISTER_CLASS.py each hardcoded their own
# copy before that. BP stays this module's name for it: tests swap
# PM.BP to a temp file, and _doc()/save read the global late, so that
# monkeypatch keeps working.
BP = BEST_PRACTICES


def _bp_rebind() -> None:
    """The CURRENT group's register — B117 stage 4 (2026-09-07): BLOCK 1's practices are the
    group's own. A probe's PM.BP swap holds until something calls group_set()."""
    global BP
    import record_paths as _RP
    BP = _RP.BEST_PRACTICES


import record_paths as _RPf                                            # noqa: E402
_RPf.group_follow(_bp_rebind)

# "All parts" and "Self" BROADCAST (-> BLOCK 1); a PartTag NARROWCASTS
# (-> BLOCK 3, that part alone). B29: PartTag list derived from part_roster.py,
# alphabetical-by-dir-name order.
BROADCAST_ADDRESSEES = ("All parts", "Self")
PART_ADDRESSEES = tuple(R.TAG_BY_DIR[d] for d in R.ALPHA_DIR_NAMES)
ADDRESSEES = BROADCAST_ADDRESSEES + PART_ADDRESSEES


def _addressees_rebind() -> None:
    """The two tuples follow the roster at every record_paths.group_set() — a follower after
    part_roster's own, so it reads the rescanned tables (R548: circle.py re-binds the group at
    every open whose parts/ moved; another session's 2026-09-11 close-out). Readers use attribute
    access (practice_verify's PM.ADDRESSEES), so reassignment is enough."""
    global PART_ADDRESSEES, ADDRESSEES
    PART_ADDRESSEES = tuple(R.TAG_BY_DIR[d] for d in R.ALPHA_DIR_NAMES)
    ADDRESSEES = BROADCAST_ADDRESSEES + PART_ADDRESSEES


_RPf.group_follow(_addressees_rebind)

ID_RE = re.compile(r"^BP-(\d{4,})$")


def _doc() -> dict:
    return SS.register_read(BP) if BP.is_file() else {
        "register": "best_practices", "next_id": 1, "practice": []}


def practice_read() -> list[dict]:
    """Every record, parsed. The one reader. Delegates to the shared
    PROPOSE-class base (_PC, defined below the mutation constants) —
    resolved at call time, so definition order is not a problem and the
    test harnesses' _doc/BP swaps keep working."""
    return _PC.entries()


def practice_read_by_id(pid: str) -> dict | None:
    return _PC.by_id(pid)


def practice_is_eligible(p: dict) -> bool:
    """PROJECTS-eligible: state is absent, or an acceptance — never a
    pending proposal, and never a denial (2026-08-12's tombstone: practice_deny()
    used to delete the row outright, so `state != "proposed"` was
    accidentally correct — a denied row simply didn't exist to be
    checked. Now that denial keeps the row, this must say so explicitly
    rather than rely on the absence of a third state that no longer
    holds)."""
    state = p.get("state")
    # isinstance, not just None-vs-string: a hand edit can write an
    # unquoted TOML date or bool here, and `.startswith` on one crashed
    # prompt assembly for every circle open (2026-08-18 review, tier 3
    # #30). A malformed state projects nothing; main() below reports it.
    return state is None or (isinstance(state, str)
                             and state.startswith("accepted by Self"))


def practice_broadcast() -> list[dict]:
    return [p for p in practice_read()
            if p["addressee"] in BROADCAST_ADDRESSEES and practice_is_eligible(p)]


def practice_narrowcast(part_tag: str) -> list[dict]:
    return [p for p in practice_read() if p["addressee"] == part_tag and practice_is_eligible(p)]


# ------------------------------------------------------------------ projection
# THE PROJECTION IS `id — title` (R135 gave title alone; R401 added the id:
# "practice_id (yes add)" — a BP- id a part cannot see is a breadcrumb it
# cannot quote). No per-shape branch: a "Self" record and a "Learner"
# record project through the exact same line. _entry_line_in() below is
# the same line's READER and moves in lockstep, or the leak checks go
# silently blind (they match the full rendered line).

# broadcast_block()/narrowcast_block() MOVED OUT, 2026-09-02, on direct
# instruction — process_core_prompt_projection.group_best_practices() (BLOCK 1),
# parts_prompt_projection.part_practices_render() (BLOCK 3). practice_broadcast()/practice_narrowcast()
# above (the raw eligible-row lists) and practice_is_eligible()/practice_read() stay here:
# they are the register's own read/validate side, used by _routing_check()
# below as well as by the two moved renderers, not just by them. Text
# RENDERING is what moves, because it is the one thing expected to diverge
# in shape between the two consumers over time, not the row-level query.


# ------------------------------------------------------------------ mutation
# WHO A ROW IS FOR IS `addressee`, AND IT IS THE ONLY THING SEPARATING
# THE TWO OBJECTS THIS REGISTER HOLDS — R133 merged
# self/better_options.toml in here, so a PRACTICE ("All parts", how the
# CIRCLE behaves) and a BETTER OPTION ("Self", "how you move") are rows
# of one table with one id series. 15 and 19 of the 34 rows today.
#
# ADD IS THE ONLY OPERATION THAT HAS TO BE TOLD WHICH. A row already in
# the register carries its own addressee, so nothing that finds one needs
# a second name for it.
PRACTICE_ADDRESSEE = "All parts"
BETTER_OPTION_ADDRESSEE = "Self"


def _body_normalise(text: str) -> str:
    """A title as it is stored: newlines joined, and ONE pair of surrounding
    double quotes removed (the operator, 2026-09-14: "strip the quotes in
    code"). `[proposed: /practice-add "when a part..."]` had reached BP-0048
    with both quote marks in its title — the quotes are the command's
    punctuation, not the practice's words, and the fold is the PROPOSE
    class's own (PROPOSE_CLASS.propose_quotes_strip), the same pair the
    bracket grammar folds off its body. A quote INSIDE the title is kept; a
    body that was nothing but the pair is empty, which practice_add()
    refuses as it always has."""
    return PROPOSE_CLASS.propose_quotes_strip(" ".join(text.split("\n")).strip())


def practice_add(text: str, addressee: str = PRACTICE_ADDRESSEE) -> tuple[bool, str]:
    """Append a row, addressed to the whole circle by default.

    RULED 2026-08-05: *"a best-practice ought to be general and addressed to
    the entire circle"* — unchanged by the 2026-08-11 rewrite. `title` is
    VERBATIM, punctuation and all; no bold is forced onto it, because the
    literal-prefix era that required a specific shape to filter on is over
    (R134) — `addressee` alone routes it now.

    `addressee` GAINED A PARAMETER 2026-08-20 rather than this file
    gaining a second function: BETTER_OPTION_ADDRESSEE is the only other
    value, the row shape is identical, and a near-copy of this body would
    be a second place for that shape to drift."""
    body = _body_normalise(text)
    if not body:
        # NO VERB NAME HERE. This branch mapped `addressee` back to a
        # command spelling for one afternoon, which reversed a decision
        # commands.py already owns and re-spelled two COMMANDS entries
        # byte-for-byte with nothing checking the copies agreed. The
        # caller names its own verb; this says only what went wrong.
        return False, "nothing to add"
    doc = _doc()
    pid = _PC.allocate_id(doc)
    doc.setdefault("practice", []).append({
        "id": pid, "addressee": addressee, "title": body,
        "origin": "Self", "in_room": "", "kind": "", "record": "",
    })
    _PC.save(doc)
    return True, f"{doc['practice'][-1]['id']} added — {body[:44]}..."


# `amended` — the date of the last in-place update (practice_update(); R465, B116,
# 2026-09-07). Absent until one; replaced each time; no prior wording, no reason —
# git is the journal.
ORDER = ("id", "addressee", "title", "origin", "in_room", "kind", "record", "amended",
         "state", "op", "target_id", "sources", "circle", "proposed_at")

# `sources` SURVIVES RESOLUTION — ruled 2026-09-08, VERBATIM: "Structured". The same ruling
# and the same reasoning as proposal_manager.py's, applied to the sibling register that shares
# PROPOSE_CLASS: a practice can be proposed by several members converging in one circle, and
# after resolution that list was recoverable only by reading the `author` sentence.
# `op` and `target_id` still go — they are the staging INSTRUCTION, spent once the row is
# ruled — and so do `circle` and `proposed_at`, for the reasons proposal_manager.py records.
STAGING_ONLY = ("op", "target_id", "circle", "proposed_at")


def _now() -> str:
    # UTC since 2026-08-16, RULED — proposals.py's convention becomes the
    # standard for every new stamp; the naive-local stamps already sitting
    # in settled rows are HISTORY and stay exactly as written. Nothing
    # orders rows by parsing these strings (verified across coordinator/,
    # memory/ and scripts/ before the change), so mixed conventions in one
    # file cost nothing beyond honesty about when each row was ruled.
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


_ENTRIES_RE = re.compile(r"\*\*Entries: \d+\*\*")


def _sync_tally(doc: dict) -> None:
    """Keep the header's `**Entries: N**` claim true. main()'s TALLY
    check reads it back out of the raw file text, so ANY write that
    skips this fails the very next practice_verify.py run — which
    is the pre-commit hook, which runs at the end of the SAME /close
    that just staged something. Call this right before every SS.register_write()
    that can change the row count."""
    n = len(doc.get("practice", []))
    pre = doc.get("doc", {}).get("preamble", "")
    if pre and _ENTRIES_RE.search(pre):
        doc["doc"]["preamble"] = _ENTRIES_RE.sub(f"**Entries: {n}**", pre, count=1)


# The shared PROPOSE-class base (docs/HELP_DESIGN.md §6, built
# 2026-08-16 — propose_class.py). LAMBDAS, NOT VALUES: the test
# harnesses swap BP and _doc as module attributes of THIS module, and
# these lambdas re-read the globals on every call, so the monkeypatches
# keep working. _sync_tally rides post_mutate so every base save keeps
# the header's `**Entries: N**` claim true — same order every direct
# _sync_tally-then-SS.register_write call here always used. `_now` is this
# register's own (naive local time — a real divergence from
# proposal_manager.py's UTC, preserved; see PROPOSE_CLASS.py's header). Only
# the SIMPLE resolution paths ride the base — the op dispatch in
# practice_approve() below stays this module's own, per R202's scope (practice
# folding is a separate, later ruling).
_PC = PROPOSE_CLASS.ProposeClass(
    table="practice", order=ORDER, staging_only=STAGING_ONLY,
    path_fn=lambda: BP, doc_fn=lambda: _doc(),
    now_fn=lambda: _now(), new_id=lambda n: f"BP-{n:04d}",
    author_field="origin", post_mutate=_sync_tally)


def practice_pending_list() -> list[dict]:
    """Every row awaiting a ruling — the vetting queue, both checkpoints
    (at /close and at the next priming) read this and nothing else."""
    return _PC.pending()


def practice_stage_render(doc: dict, op: str, *, addressee: str = "", title: str = "",
                 record: str = "", target_id: str = "",
                 sources: list[str] | None = None,
                 circle: str = "") -> tuple[dict, str]:
    """PURE — one new BP-id row, state='proposed', on a COPY of `doc`.
    The phase-2 driver (coordinator/inter_circle.py) stages this render
    for SYNTHESIS's BLOCK 1 CANDIDATEs; stage() below is the same logic
    plus the write, so the row shape exists exactly once."""
    import copy
    doc = copy.deepcopy(doc)
    pid = _PC.allocate_id(doc)
    row = {"id": pid, "addressee": addressee, "title": title,
           "origin": "", "in_room": "", "kind": "", "record": record,
           "state": "proposed", "op": op,
           "sources": sorted(sources or []), "circle": circle,
           "proposed_at": _now()}
    if target_id:
        row["target_id"] = target_id
    doc.setdefault("practice", []).append(row)
    _sync_tally(doc)
    return doc, pid


# stage() STOOD HERE AND IS DELETED, 2026-08-20. It was practice_stage_render() plus
# the write, and its only two callers went with the annotation path B60
# retired: annotations.stage_practice_proposals() in production, and one test
# of that function. practice_stage_render() is PURE and survives — inter_circle's
# SYNTHESIS calls it and stages the result through its own transaction,
# which is the shape a writer should have.
#
# pyflakes does not flag an unused module-level function, so nothing here
# would ever have said so.


def _provenance(row: dict) -> str:
    """The speaker IS known — `sources`/`circle` carry it — this just
    keeps it from being thrown away when the staging fields are
    dropped at acceptance. Only used where `origin` is still blank: a
    revision's target may already carry real provenance from wherever
    it was first authored, and this never overwrites that. The one copy
    now lives in PROPOSE_CLASS.py; this delegates."""
    return _PC.provenance(row)


def practice_approve(pid: str, title: str = "") -> tuple[bool, str]:
    """Rule FOR a pending row. `title` overrides an op=revise row's own
    title when Self authors the final wording at vetting time rather
    than accepting a non-unanimous proposal's placeholder verbatim —
    see docs/BNF.md's non-unanimous-revise note."""
    doc = _doc()
    ps = doc.get("practice", [])
    row, why = _PC.find_pending(ps, pid)
    if row is None:
        return False, why
    op = row.get("op")
    when = f"accepted by Self {_now()}"
    if op == "add":
        if not row.get("origin", "").strip():
            row["origin"] = _provenance(row)
        row["state"] = when
        _PC.drop_staging(row)
    elif op in ("revise", "delete"):
        target = next((p for p in ps if p["id"] == row.get("target_id")), None)
        if target is None:
            return False, f"{pid}: target {row.get('target_id')!r} no longer exists"
        if op == "revise":
            target["title"] = (title or row["title"]).strip()
            if not target["title"]:
                return False, f"{pid}: no revision text — pass one to practice_approve()"
            if not target.get("origin", "").strip():
                target["origin"] = _provenance(row)
            target["state"] = when
        else:                                              # delete
            ps.remove(target)
        ps.remove(row)
    else:
        return False, f"{pid}: unknown op {op!r}"
    _PC.save(doc)
    return True, f"{pid} approved ({op})"


def practice_deny(pid: str) -> tuple[bool, str]:
    """Rejected proposals are TOMBSTONED, not deleted — ruled 2026-08-12:
    a denial that leaves no trace cannot be told apart from one that
    never happened. `state` -> "denied by Self <datetime>"; staging
    fields (op/target_id/circle/proposed_at) are dropped, the
    same as practice_approve() already does, so a denied row is otherwise
    indistinguishable in shape from an accepted one — only `state` says
    which. `sources` is KEPT on both since 2026-09-08 ("Structured"), which
    matters most here: a denied row is the one whose wording did NOT land,
    and who proposed it is exactly what a later reader would ask. practice_is_eligible() (above) must treat this state as non-projecting;
    it is not "proposed", so the OLD `state != "proposed"` shortcut
    would have wrongly let it through — fixed in the same change.
    Delegates to PROPOSE_CLASS.deny, the shared base — the tally rides
    its post_mutate hook."""
    return _PC.deny(pid)


def _rows(better_options: bool) -> list[dict]:
    """The two listings' partition of the one register (R133): the rows
    addressed to Self are the BETTER OPTIONS — "how you move"; every
    other row — the circle's, and the ones addressed to one part — is a
    PRACTICE. 2026-08-21: /better-option-list minted, /practice-list
    narrowed to its half."""
    return [p for p in practice_read()
            if (p.get("addressee") == BETTER_OPTION_ADDRESSEE) == better_options]


def practice_list(better_options: bool = False) -> str:
    """A NUMBERED list, because /practice-delete takes a list number.

    The number is positional and is NOT an id: it changes when an entry is
    deleted. `id` (BP-NNNN) is the stable handle — used by the in-circle
    proposal annotations (docs/BNF.md), never by this listing.

    TWO LISTINGS SINCE 2026-08-21, each numbered on its own: the default is
    /practice-list's (every row not addressed to Self); `better_options=True`
    is /better-option-list's (the rows addressed to Self). practice_delete() below
    addresses the PRACTICE numbering, as /practice-delete's own help says."""
    ps = _rows(better_options)
    if not ps:
        return "  no better options" if better_options else "  no best practices"
    out = []
    for i, e in enumerate(ps, 1):
        one = " ".join(e["title"].split())
        out.append(f"  {i:>2}. [{e['id']}] {e['addressee']:<10} "
                   f"{one[:56]}{'...' if len(one) > 56 else ''}")
    out.append("\n" + SS.register_list_footer(len(ps), _list_verb(better_options)))
    return "\n".join(out)


def _list_verb(better_options: bool) -> str:
    return "/better-option-list" if better_options else "/practice-list"


def practice_record_show(n: int, better_options: bool = False) -> str:
    """`/practice-list <n>` or `/better-option-list <n>`: that row WHOLE, numbered as its own
    listing numbers it — every field, through REGISTER_CLASS.register_record_show() (B133)."""
    return SS.register_record_show(_rows(better_options), n, ORDER, body="title",
                                   verb=_list_verb(better_options))


def practice_delete(n: int) -> tuple[bool, str]:
    """Remove the n-th row AS /practice-list NUMBERS THEM — the practice
    rows, not the whole register (2026-08-21, with the split above). A
    better option has no delete verb yet; the register is hand-editable
    TOML."""
    doc = _doc()
    ps = doc.get("practice", [])
    shown = [p for p in ps if p.get("addressee") != BETTER_OPTION_ADDRESSEE]
    if not 1 <= n <= len(shown):
        return False, f"{n} is not in 1..{len(shown)} — /practice-list"
    gone = shown[n - 1]
    ps.remove(gone)
    _PC.save(doc)
    one = " ".join(gone["title"].split())
    return True, f"removed {n}. [{gone['id']}] {one[:48]}..."


def practice_update(n: int, text: str) -> tuple[bool, str]:
    """Replace the n-th listed practice's title in place — same id, same origin, same
    position AS /practice-list NUMBERS THEM — and stamp `amended` with today's date
    (R465, B116, 2026-09-07). The prior wording is not kept on the row: git is the journal.
    Rides REGISTER_CLASS.register_row_update(); the text takes practice_add()'s own
    normalisation and its empty-body refusal. A row still awaiting Self's ruling
    (state "proposed") is refused — rule on it first; a change to a proposal's text is a
    change to what was proposed."""
    body = _body_normalise(text)
    doc = _doc()
    ps = doc.get("practice", [])
    shown = [p for p in ps if p.get("addressee") != BETTER_OPTION_ADDRESSEE]

    def _precheck(fields: dict, row: dict) -> str:
        if not fields["title"]:
            return "nothing to update"
        if row.get("state") == "proposed":
            return f"[{row['id']}] is still proposed — rule on it before changing its text"
        return ""

    # THE PRIOR TITLE IS ECHOED BACK, 2026-09-09 (audit-register 2026-09-09 #1). `shown`
    # above filters the addressee = Self rows out, so this verb numbers rows the way
    # /practice-list does — and /better-option-list numbers the Self rows ON THEIR OWN.
    # Reading "3." off that list and typing it here rewrites the third CIRCLE practice,
    # a live BLOCK 1 row, and the register keeps no prior wording to notice it by. The
    # help gloss now carries /practice-delete's disclaimer; this makes a mis-aimed
    # update VISIBLE the moment it lands, which a warning read beforehand cannot.
    was = ""
    if 1 <= n <= len(shown):
        was = str(shown[n - 1].get("title", ""))

    ok, msg, row = SS.register_row_update(
        doc, "practice", locate=n, listed=shown, precheck=_precheck,
        fields={"title": body, "amended": SS.register_now()[:10]})
    if not ok:
        return False, msg + (" — /practice-list" if "1.." in msg else "")
    _PC.save(doc)
    return True, (f"updated {n}. [{row['id']}] {body[:48]}...\n"
                  f"           was: {was[:48]}...")
