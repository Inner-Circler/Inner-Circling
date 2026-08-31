#!/usr/bin/env python3
"""
check_best_practices.py — the one reader/writer for self/best_practices.toml.

    python coordinator/check_best_practices.py

REWRITTEN 2026-08-11 (R133-R137). Three registers became one: this file used
to hold ONLY circle-facing practices, addressed by a `**<Addressee>** —` text
prefix that `circle.py` scraped out of a rendered `self/circle_briefing.md`.
Two things changed that:

    R133   self/better_options.toml — "how SELF moves" — merged in as
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
           entries and populated on those descended from better_options,
           and nothing in the schema requires that correlation.
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
                (2026-08-12: deny() tombstones rather than deletes). A
                `state = "proposed"` or "denied by Self ..." row is never
                PROJECTS-eligible, whatever its `op` — see eligible()/
                broadcast()/narrowcast() below.
    op          STAGING ONLY, present iff state = "proposed":
                "add" | "revise" | "delete"
    target_id   STAGING ONLY: the BP-ID a revise/delete row is about
    sources     STAGING ONLY: [display, ...], every speaker who raised it
    circle      STAGING ONLY: the OT the proposal was raised in
    proposed_at STAGING ONLY: ISO timestamp

A row's staging fields (op/target_id/sources/circle/proposed_at) exist
ONLY while state = "proposed" — the vetting functions below strip them
the moment a row resolves (accepted, revise applied, or deleted), so a
settled row is indistinguishable from one Self typed directly with
/practice-add.

WHAT IS ASSERTED

    TALLY       header states N entries; N matches the live count.
    SHAPE       every id is `BP-` + 4 digits, unique, below next_id; every
                addressee is a known one; every title is non-empty.
    ROUTING     the actual functions circle.py's prompt assembly calls
                (broadcast_block / narrowcast_block, below) are run and
                checked directly: a part's own narrowcast entries reach
                it, no OTHER part's narrowcast entries do, and broadcast
                entries reach every part alike. Runs against the real
                functions, not a model of them — the point E09 taught.

Exit 0 clean, 1 on any failure. Run by the pre-commit hook on any commit
touching self/best_practices.toml.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import self_schema as SS                                       # noqa: E402
import roster as R                                              # noqa: E402
import propose_class                                            # noqa: E402
from paths import BEST_PRACTICES                                # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = pathlib.Path(__file__).resolve().parent.parent
# The register's path comes from paths.py since 2026-08-16 (phase 1
# step 0) — this module and self_schema.py each hardcoded their own
# copy before that. BP stays this module's name for it: tests swap
# BPX.BP to a temp file, and _doc()/save read the global late, so that
# monkeypatch keeps working.
BP = BEST_PRACTICES

# "All parts" and "Self" BROADCAST (-> BLOCK 1); a PartTag NARROWCASTS
# (-> BLOCK 3, that part alone). B29: PartTag list derived from roster.py,
# alphabetical-by-dir-name order.
BROADCAST_ADDRESSEES = ("All parts", "Self")
PART_ADDRESSEES = tuple(R.TAG_BY_DIR[d] for d in R.ALPHA_DIR_NAMES)
ADDRESSEES = BROADCAST_ADDRESSEES + PART_ADDRESSEES

ID_RE = re.compile(r"^BP-(\d{4,})$")


def _doc() -> dict:
    return SS.load(BP) if BP.is_file() else {
        "register": "best_practices", "next_id": 1, "practice": []}


def practices() -> list[dict]:
    """Every record, parsed. The one reader. Delegates to the shared
    PROPOSE-class base (_PC, defined below the mutation constants) —
    resolved at call time, so definition order is not a problem and the
    test harnesses' _doc/BP swaps keep working."""
    return _PC.entries()


def by_id(pid: str) -> dict | None:
    return _PC.by_id(pid)


def eligible(p: dict) -> bool:
    """PROJECTS-eligible: state is absent, or an acceptance — never a
    pending proposal, and never a denial (2026-08-12's tombstone: deny()
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


def broadcast() -> list[dict]:
    return [p for p in practices()
            if p["addressee"] in BROADCAST_ADDRESSEES and eligible(p)]


def narrowcast(part_tag: str) -> list[dict]:
    return [p for p in practices() if p["addressee"] == part_tag and eligible(p)]


# ------------------------------------------------------------------ projection
# THE PROJECTION IS `id — title` (R135 gave title alone; R401 added the id:
# "practice_id (yes add)" — a BP- id a part cannot see is a breadcrumb it
# cannot quote). No per-shape branch: a "Self" record and a "Learner"
# record project through the exact same line. _entry_line_in() below is
# the same line's READER and moves in lockstep, or the leak checks go
# silently blind (they match the full rendered line).

def broadcast_block() -> str:
    """BLOCK 1's contribution — every part reads this, identically.

    Called directly by circle.py at prompt-assembly time; nothing in
    between reads or writes self/circle_briefing.md for this content."""
    all_parts = [p for p in broadcast() if p["addressee"] == "All parts"]
    for_self = [p for p in broadcast() if p["addressee"] == "Self"]
    if not all_parts and not for_self:
        return ""
    out = ["## Best practices", ""]
    out += [f"- {p['id']} — {p['title']}" for p in all_parts]
    if for_self:
        out += ["", "### Better options (for Self)", ""]
        out += [f"- {p['id']} — {p['title']}" for p in for_self]
    return "\n".join(out)


def narrowcast_block(part_tag: str) -> str:
    """BLOCK 3's contribution for ONE part — empty for most parts, most
    circles. Sourced from THIS file directly; there is no intermediate
    per-part slice in self/circle_briefing.md to leak from (E09's failure
    mode no longer has a text layer to occur in)."""
    mine = narrowcast(part_tag)
    if not mine:
        return ""
    return "\n".join(["## Your best practices", ""]
                     + [f"- {p['id']} — {p['title']}" for p in mine])


# ------------------------------------------------------------------ mutation
# WHO A ROW IS FOR IS `addressee`, AND IT IS THE ONLY THING SEPARATING
# THE TWO OBJECTS THIS REGISTER HOLDS — R133 merged
# self/better_options.toml in here, so a PRACTICE ("All parts", how the
# CIRCLE behaves) and a BETTER OPTION ("Self", how SELF moves) are rows
# of one table with one id series. 15 and 19 of the 34 rows today.
#
# ADD IS THE ONLY OPERATION THAT HAS TO BE TOLD WHICH. A row already in
# the register carries its own addressee, so nothing that finds one needs
# a second name for it.
PRACTICE_ADDRESSEE = "All parts"
BETTER_OPTION_ADDRESSEE = "Self"


def add(text: str, addressee: str = PRACTICE_ADDRESSEE) -> tuple[bool, str]:
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
    body = " ".join(text.split("\n")).strip()
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


ORDER = ("id", "addressee", "title", "origin", "in_room", "kind", "record",
         "state", "op", "target_id", "sources", "circle", "proposed_at")

STAGING_ONLY = ("op", "target_id", "sources", "circle", "proposed_at")


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
    skips this fails the very next check_best_practices.py run — which
    is the pre-commit hook, which runs at the end of the SAME /close
    that just staged something. Call this right before every SS.save()
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
# _sync_tally-then-SS.save call here always used. `_now` is this
# register's own (naive local time — a real divergence from
# proposals.py's UTC, preserved; see propose_class.py's header). Only
# the SIMPLE resolution paths ride the base — the op dispatch in
# approve() below stays this module's own, per R202's scope (practice
# folding is a separate, later ruling).
_PC = propose_class.ProposeClass(
    table="practice", order=ORDER, staging_only=STAGING_ONLY,
    path_fn=lambda: BP, doc_fn=lambda: _doc(),
    now_fn=lambda: _now(), new_id=lambda n: f"BP-{n:04d}",
    author_field="origin", post_mutate=_sync_tally)


def pending() -> list[dict]:
    """Every row awaiting a ruling — the vetting queue, both checkpoints
    (at /close and at the next priming) read this and nothing else."""
    return _PC.pending()


def render_stage(doc: dict, op: str, *, addressee: str = "", title: str = "",
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


# stage() STOOD HERE AND IS DELETED, 2026-08-20. It was render_stage() plus
# the write, and its only two callers went with the annotation path B60
# retired: markers.stage_practice_proposals() in production, and one test
# of that function. render_stage() is PURE and survives — inter_circle's
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
    now lives in propose_class.py; this delegates."""
    return _PC.provenance(row)


def approve(pid: str, title: str = "") -> tuple[bool, str]:
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
                return False, f"{pid}: no revision text — pass one to approve()"
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


def deny(pid: str) -> tuple[bool, str]:
    """Rejected proposals are TOMBSTONED, not deleted — ruled 2026-08-12:
    a denial that leaves no trace cannot be told apart from one that
    never happened. `state` -> "denied by Self <datetime>"; staging
    fields (op/target_id/sources/circle/proposed_at) are dropped, the
    same as approve() already does, so a denied row is otherwise
    indistinguishable in shape from an accepted one — only `state` says
    which. eligible() (above) must treat this state as non-projecting;
    it is not "proposed", so the OLD `state != "proposed"` shortcut
    would have wrongly let it through — fixed in the same change.
    Delegates to propose_class.deny, the shared base — the tally rides
    its post_mutate hook."""
    return _PC.deny(pid)


def _rows(better_options: bool) -> list[dict]:
    """The two listings' partition of the one register (R133): the rows
    addressed to Self are the BETTER OPTIONS — how the operator moves; every
    other row — the circle's, and the ones addressed to one part — is a
    PRACTICE. 2026-08-21: /better-option-list minted, /practice-list
    narrowed to its half."""
    return [p for p in practices()
            if (p.get("addressee") == BETTER_OPTION_ADDRESSEE) == better_options]


def listing(better_options: bool = False) -> str:
    """A NUMBERED list, because /practice-delete takes a list number.

    The number is positional and is NOT an id: it changes when an entry is
    deleted. `id` (BP-NNNN) is the stable handle — used by the in-circle
    proposal markers (docs/BNF.md), never by this listing.

    TWO LISTINGS SINCE 2026-08-21, each numbered on its own: the default is
    /practice-list's (every row not addressed to Self); `better_options=True`
    is /better-option-list's (the rows addressed to Self). delete() below
    addresses the PRACTICE numbering, as /practice-delete's own help says."""
    ps = _rows(better_options)
    if not ps:
        return "  no better options" if better_options else "  no best practices"
    out = []
    for i, e in enumerate(ps, 1):
        one = " ".join(e["title"].split())
        out.append(f"  {i:>2}. [{e['id']}] {e['addressee']:<10} "
                   f"{one[:56]}{'...' if len(one) > 56 else ''}")
    return "\n".join(out)


def delete(n: int) -> tuple[bool, str]:
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


# ------------------------------------------------------------------ verify
def _entry_line_in(p: dict, block: str) -> bool:
    """Does `block` carry this row as a RENDERED ENTRY — the full
    `- id — title` line (R401 added the id) — rather than anywhere in its
    text? The leak checks used bare substring matching until 2026-08-19
    (review, tier 3 #29), so a title that happened to be a substring of
    another entry's text reported a routing leak that was not there — and
    main() exits 1 in the hook, so the false positive blocked every
    commit. Takes the ROW, not the title: the rendered line carries the id,
    and a matcher spelling the line differently from the renderer is a
    detector that silently stops detecting."""
    want = f"- {p.get('id', '')} — {p.get('title', '')}"
    return any(line == want for line in block.splitlines())


def _projecting_titles() -> set[str]:
    """Titles a PROJECTING row legitimately puts into a block —
    re-derived here (state None or an acceptance), never through
    eligible(), for the same independence reason the docstring below
    gives. A non-projecting row whose title equals a projecting twin's
    (the duplicate-staging case markers.py's coalesce docstring names as
    a known limitation) puts nothing extra in the rendered text, and
    text matching cannot attribute the line to one row or the other —
    so the twin case is an ACCEPTED DETECTION HOLE, recorded here: a
    leak of a duplicate-titled row is invisible to this check by
    construction, and flagging it anyway blocked commits on rows that
    had not leaked."""
    out = set()
    for q in practices():
        st = q.get("state")
        if st is None or (isinstance(st, str)
                          and st.startswith("accepted by Self")):
            out.add(q.get("title", ""))
    return out


def _routing_check() -> list[str]:
    """Run the REAL functions above against the REAL roster, not a model
    of either. A part must receive its own narrowcast entries and no
    other part's; broadcast entries must reach every part identically.

    EACH REAL FUNCTION RUNS ONCE PER TAG, its output reused (2026-08-19,
    review tier 5 #53): the loops below used to re-call
    narrowcast()/narrowcast_block() — each a fresh parse of the register
    — inside the per-part and per-proposal iterations, so one hook run
    re-parsed the same unchanged TOML seventy-odd times. Calling once
    and comparing many times checks the identical outputs; what the
    docstring's charter forbids is a MODEL of the functions, not a
    snapshot of their real results."""
    fails: list[str] = []
    b = broadcast_block()
    nblock = {tag: narrowcast_block(tag) for tag in R.TAG_BY_DIR.values()}
    ncast = {tag: narrowcast(tag) for tag in R.TAG_BY_DIR.values()}
    bcast = broadcast()
    proj_titles = _projecting_titles()
    for pid, tag in R.TAG_BY_DIR.items():
        mine = nblock[tag]
        for other_tag in R.TAG_BY_DIR.values():
            if other_tag == tag:
                continue
            for p in ncast[other_tag]:
                if p["title"] and _entry_line_in(p, mine) \
                        and not any(q.get("title") == p["title"]
                                    for q in ncast[tag]):
                    fails.append(f"{tag} receives {other_tag}'s narrowcast "
                                 f"entry {p['id']} — routing is leaking")
        for p in ncast[tag]:
            if p["title"] not in mine:
                fails.append(f"{tag}'s own entry {p['id']} did not reach "
                             f"its narrowcast block")
        for p in bcast:
            if p["title"] not in b:
                fails.append(f"broadcast entry {p['id']} is missing from "
                             f"broadcast_block()")
    for p in practices():
        # DELIBERATELY NOT eligible() — this check exists to catch
        # eligible() ITSELF leaking a non-projecting row (proven by
        # test_routing_check_catches_a_leaked_proposed_row(), which
        # monkeypatches eligible() to force exactly that and asserts this
        # function still reports it); reusing eligible() here would make
        # the detector blind to the one failure mode it exists to catch.
        # Independently re-derives "non-projecting": "proposed", or
        # "denied by Self ..." since 2026-08-12's tombstone — not just
        # the original single state.
        state = p.get("state")
        non_projecting = state == "proposed" or (
            isinstance(state, str) and state.startswith("denied by Self"))
        if not non_projecting or not p.get("title", "").strip():
            continue
        # Full-line matching, and a projecting twin exempts: see
        # _entry_line_in/_projecting_titles above (tier 3 #29 — the
        # duplicate-staged title was a hook-blocking false positive).
        if p["title"] in proj_titles:
            continue
        if _entry_line_in(p, b):
            fails.append(f"{p['id']}: state={p.get('state')!r} but its "
                         f"title leaked into broadcast_block()")
        for tag in R.TAG_BY_DIR.values():
            if _entry_line_in(p, nblock[tag]):
                fails.append(f"{p['id']}: state={p.get('state')!r} but its "
                             f"title leaked into {tag}'s narrowcast_block()")
    return fails


def main() -> int:
    fails: list[str] = []

    if not BP.is_file():
        print(f"  FAIL  {BP.relative_to(ROOT)} does not exist")
        return 1

    raw = BP.read_bytes()
    if b"\r\n" in raw:
        fails.append("self/best_practices.toml has CRLF line "
                     "endings; the rest is LF")

    doc = _doc()
    ps = doc.get("practice", [])
    next_id = doc.get("next_id")
    if not isinstance(next_id, int):
        fails.append("`next_id` is missing or not an int")

    text = raw.decode("utf-8")
    m = re.search(r"\*\*Entries: (\d+)\*\*", text)
    if not m:
        fails.append("header does not state the tally as `**Entries: N**`")
    elif len(ps) != int(m.group(1)):
        fails.append(f"header tallies {m.group(1)} entries; {len(ps)} are "
                     f"present. Update the tally — it records the count, "
                     f"it does not cap it.")

    # AN EMPTY REGISTER IS NOT A DEFECT, 2026-08-24. This was
    # `fails.append("no entries found")`, and it made a FRESH INSTALL fail
    # its own verifier before the recipient had touched anything: the
    # shipped self/best_practices.toml is a deliberately EMPTY delegate,
    # and "Empty is correct" is the doctrine the bundle's own README and
    # every self/ delegate are built on. A gate that refuses the shipped
    # state teaches a recipient to ignore gates.
    #
    # NOTHING IS LOST, BECAUSE THE TALLY ALREADY CARRIED IT. The case this
    # was defending against is a register that lost its rows — and a file
    # whose header claims `**Entries: 35**` with none present fails the
    # tally check above, by name and with both numbers. The only case this
    # line caught alone was the one where the header AGREES that there are
    # none, which is exactly the legitimate one.
    if not ps:
        print("  note  the register is empty — legitimate on a fresh "
              "install; entries arrive as you rule them in")

    seen_ids: set[str] = set()
    for p in ps:
        pid = p.get("id", "")
        im = ID_RE.match(pid)
        if not im:
            fails.append(f"entry has a malformed id: {pid!r}")
        elif pid in seen_ids:
            fails.append(f"duplicate id: {pid}")
        elif isinstance(next_id, int) and int(im.group(1)) >= next_id:
            fails.append(f"{pid} is >= next_id ({next_id}) — next_id has "
                         f"fallen behind the ids actually in use")
        seen_ids.add(pid)

        state = p.get("state")
        # isinstance FIRST: `state = 2026-08-12` unquoted parses as a TOML
        # date, passed the != test, and `.startswith` then died with a
        # traceback — the hook blocked every commit with a crash instead
        # of this FAIL line (2026-08-18 review, tier 3 #30).
        if state is not None and not isinstance(state, str):
            fails.append(f"{pid}: state is {type(state).__name__} "
                         f"({state!r}) — a hand edit lost the quotes; "
                         f"state must be a string")
        elif state is not None and state != "proposed" \
                and not state.startswith("accepted by Self ") \
                and not state.startswith("denied by Self "):
            fails.append(f"{pid}: state {state!r} is not 'proposed', "
                         f"'accepted by Self <datetime>', or "
                         f"'denied by Self <datetime>'")
        if state != "proposed":
            for k in STAGING_ONLY:
                if k in p:
                    fails.append(f"{pid}: staging field {k!r} present but "
                                 f"state is {state!r} — should have been "
                                 f"dropped on resolution")

        if state == "proposed":
            op = p.get("op")
            if op not in ("add", "revise", "delete"):
                fails.append(f"{pid}: state=proposed but op is {op!r}")
            if op in ("revise", "delete"):
                target = p.get("target_id", "")
                if not target:
                    fails.append(f"{pid}: op={op} needs a target_id")
                elif not by_id(target):
                    fails.append(f"{pid}: target_id {target!r} does not exist")
            if op == "add":
                if p.get("addressee") not in ADDRESSEES:
                    fails.append(f"{pid}: addressee {p.get('addressee')!r} "
                                 f"is not one of {ADDRESSEES}")
                if not p.get("title", "").strip():
                    fails.append(f"{pid}: op=add but title is empty — "
                                 f"nothing to accept")
        else:
            if p.get("addressee") not in ADDRESSEES:
                fails.append(f"{pid}: addressee {p.get('addressee')!r} is not "
                             f"one of {ADDRESSEES}")
            if not p.get("title", "").strip():
                fails.append(f"{pid}: title is empty — nothing would project")

    fails += _routing_check()

    settled = [p for p in ps if p.get("state") != "proposed"]
    pend = [p for p in ps if p.get("state") == "proposed"]
    by_addr: dict[str, int] = {}
    for p in settled:
        by_addr[p.get("addressee", "?")] = by_addr.get(p.get("addressee", "?"), 0) + 1
    print(f"  {len(settled)} practice(s), addressed to: "
          + ", ".join(f"{k} x{v}" for k, v in sorted(by_addr.items())))
    if pend:
        print(f"  {len(pend)} pending proposal(s) — see check_best_practices.pending()")
    b = broadcast_block()
    print(f"  block 1 (broadcast): {len(b):,} chars projected to every part")
    for tag in R.TAG_BY_DIR.values():
        nb = narrowcast_block(tag)
        if nb:
            print(f"  block 3 ({tag}): {len(nb):,} chars")

    if fails:
        print(f"\n  {len(fails)} FAILURE(S):")
        for f in fails:
            print(f"    - {f}")
        return 1
    print("  PASS — tally, ids, addressees and routing all hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
