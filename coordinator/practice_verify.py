#!/usr/bin/env python3
"""
practice_verify.py — the VERIFIER of self/best_practices.toml (check_best_practices.py
until 2026-09-03, R435: verifiers take _verify).

    python coordinator/practice_verify.py

THE REGISTER ITSELF LIVES IN practice_manager.py since 2026-09-03 (cohesion re-homing
stage 7, R440 closing D80): the reader/writer, the addressees, the PRACTICE LIFECYCLE
staging (pending/render_stage/approve/deny) and the cmd> surface (add/delete/listing)
all moved there verbatim, and this file reads them as PM. What stays here is what the
pre-commit hook runs: the tally, shape, kind and routing checks below. The register's
own history (R133-R137) and record shape are in practice_manager.py's docstring.

WHAT IS ASSERTED

    TALLY       header states N entries; N matches the live count.
    SHAPE       every id is `BP-` + 4 digits, unique, below next_id; every
                addressee is a known one; every title is non-empty.
    KIND        (R421/B90) a non-empty `kind` never appears on a row whose
                addressee is not "Self" — one-directional; plenty of
                `addressee = "Self"` rows still carry `kind = ""`.
    ROUTING     the actual functions circle.py's prompt assembly calls —
                process_core_prompt_projection.group_best_practices() (BLOCK 1),
                parts_prompt_projection.part_practices_render() (BLOCK 3), MOVED
                OUT of this file 2026-09-02, on direct instruction: the
                write/read/validate side of the register stays unified
                here, but each block's own text-rendering lives with its
                own consumer, since the two may diverge in shape (new
                fields per type) even though they read one register —
                are run and checked directly, via a lazy cross-import
                (see _routing_check()), same discipline as before the
                move: a part's own narrowcast entries reach it, no OTHER
                part's narrowcast entries do, and broadcast entries reach
                every part alike. Runs against the real functions, not a
                model of them — the point E09 taught.

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
import practice_manager as PM                                   # noqa: E402  the register
import part_roster as R                                              # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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
    (the duplicate-staging case annotations.py's coalesce docstring names as
    a known limitation) puts nothing extra in the rendered text, and
    text matching cannot attribute the line to one row or the other —
    so the twin case is an ACCEPTED DETECTION HOLE, recorded here: a
    leak of a duplicate-titled row is invisible to this check by
    construction, and flagging it anyway blocked commits on rows that
    had not leaked."""
    out = set()
    for q in PM.practice_read():
        st = q.get("state")
        if st is None or (isinstance(st, str)
                          and st.startswith("accepted by Self")):
            out.add(q.get("title", ""))
    return out


def _kind_check() -> list[str]:
    """R421/B90: `kind` is the better-option sub-taxonomy (invitation, lens,
    diagnostic, ...) inherited from the pre-2026-08-11 better_options.toml
    merge — free-text, and read by nobody but a human revising or citing an
    entry (never projected). Every row that carries one is addressed to
    Self today; the reverse does not hold (plenty of `addressee = "Self"`
    rows still carry `kind = ""`), so this is ONE-DIRECTIONAL: a non-empty
    `kind` on a broadcast-to-all or narrowcast row is a hand-edit slip, not
    a valid combination, and is the only thing this checks."""
    fails: list[str] = []
    for p in PM.practice_read():
        kind = p.get("kind", "")
        if isinstance(kind, str) and kind.strip() and p.get("addressee") != "Self":
            fails.append(f"{p.get('id', '?')}: kind={kind.strip()[:40]!r} is "
                         f"set but addressee is {p.get('addressee')!r}, not "
                         f"'Self' — kind is a better-option-only field")
    return fails


def _routing_check() -> list[str]:
    """Run the REAL functions above against the REAL roster, not a model
    of either. A part must receive its own narrowcast entries and no
    other part's; broadcast entries must reach every part identically.

    EACH REAL FUNCTION RUNS ONCE PER TAG, its output reused (2026-08-19,
    review tier 5 #53): the loops below used to re-call
    PM.practice_narrowcast()/narrowcast_block() — each a fresh parse of the register
    — inside the per-part and per-proposal iterations, so one hook run
    re-parsed the same unchanged TOML seventy-odd times. Calling once
    and comparing many times checks the identical outputs; what the
    docstring's charter forbids is a MODEL of the functions, not a
    snapshot of their real results.

    CROSSES BACK INTO process_core_prompt_projection.py/parts_prompt_projection.py,
    2026-09-02 — lazily, matching the pattern group_context.py/
    role_context.py already use for their own calls INTO this module, now
    mirrored the other direction. Safe: neither side's cross-import runs
    at module-load time, only inside a function body called well after
    both modules are fully imported, so the cycle never observes a
    partially-initialized module."""
    import process_core_prompt_projection as PCP
    import parts_prompt_projection as PP
    fails: list[str] = []
    b = PCP.group_best_practices()
    nblock = {tag: PP.part_practices_render(tag) for tag in R.TAG_BY_DIR.values()}
    ncast = {tag: PM.practice_narrowcast(tag) for tag in R.TAG_BY_DIR.values()}
    bcast = PM.practice_broadcast()
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
                             f"group_best_practices()")
    for p in PM.practice_read():
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
                         f"title leaked into group_best_practices()")
        for tag in R.TAG_BY_DIR.values():
            if _entry_line_in(p, nblock[tag]):
                fails.append(f"{p['id']}: state={p.get('state')!r} but its "
                             f"title leaked into {tag}'s role_best_practices()")
    return fails


def main() -> int:
    fails: list[str] = []

    if not PM.BP.is_file():
        print(f"  FAIL  {PM.BP.relative_to(PM.ROOT)} does not exist")
        return 1

    raw = PM.BP.read_bytes()
    if b"\r\n" in raw:
        fails.append("self/best_practices.toml has CRLF line "
                     "endings; the rest is LF")

    doc = PM._doc()
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
        im = PM.ID_RE.match(pid)
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
            for k in PM.STAGING_ONLY:
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
                elif not PM.practice_read_by_id(target):
                    fails.append(f"{pid}: target_id {target!r} does not exist")
            if op == "add":
                if p.get("addressee") not in PM.ADDRESSEES:
                    fails.append(f"{pid}: addressee {p.get('addressee')!r} "
                                 f"is not one of {PM.ADDRESSEES}")
                if not p.get("title", "").strip():
                    fails.append(f"{pid}: op=add but title is empty — "
                                 f"nothing to accept")
        else:
            if p.get("addressee") not in PM.ADDRESSEES:
                fails.append(f"{pid}: addressee {p.get('addressee')!r} is not "
                             f"one of {PM.ADDRESSEES}")
            if not p.get("title", "").strip():
                fails.append(f"{pid}: title is empty — nothing would project")

    fails += _kind_check()
    fails += _routing_check()

    settled = [p for p in ps if p.get("state") != "proposed"]
    pend = [p for p in ps if p.get("state") == "proposed"]
    by_addr: dict[str, int] = {}
    for p in settled:
        by_addr[p.get("addressee", "?")] = by_addr.get(p.get("addressee", "?"), 0) + 1
    print(f"  {len(settled)} practice(s), addressed to: "
          + ", ".join(f"{k} x{v}" for k, v in sorted(by_addr.items())))
    if pend:
        print(f"  {len(pend)} pending proposal(s) — see practice_manager.practice_pending_list()")
    import process_core_prompt_projection as PCP
    import parts_prompt_projection as PP
    b = PCP.group_best_practices()
    print(f"  block 1 (broadcast): {len(b):,} chars projected to every part")
    for tag in R.TAG_BY_DIR.values():
        nb = PP.part_practices_render(tag)
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
