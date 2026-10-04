#!/usr/bin/env python3
"""
remember_prompt_projection.py — the REMEMBER register's PROMPT projection: what of a part's own
remember.toml reaches BLOCK 3 (settled, cached) and BLOCK 4 (the tail, live), and the salience/chain
order both are cut from.

    python coordinator/remember_prompt_projection.py --part <part>     the whole-register view

IN remember.py UNTIL 2026-09-03 (B99 stage 17b; F5 under R435: a projection is its consumer's, and
says so in its name). The bodies are the ones that lived there — remember_project(), the cutoff-aware split
(B44, R170), remember_rank() and its two helpers, remember_settled_project()/remember_tail_project() and the two
block_*() doors the four-block assembly calls — moved verbatim; only this header and the imports are
new — and RENAMED IN THE NEXT COMMIT (R436, R442: class word first, a verb after; mine, to be overruled
by name): project -> remember_project, project_settled/project_tail -> remember_settled_project/
remember_tail_project, block_settled/block_tail -> remember_settled_render/remember_tail_render,
scored_order -> remember_rank. The register keeps the record: remember_read(), add(), the chain, the salience vocabulary and the
caps this file reads from it. Constants are imported by name because remember_manager.py never rebinds
them (the ROOT the suites DO rebind is read inside remember_read(), which is the register's own).

    remember_project(part)                       the whole register, newest first, under BUDGET — the CLI and
                                        the cutoff=None degrade path
    remember_settled_project / remember_tail_project      the same split at part_mid_term_manager.part_mid_term_cutoff_read(part)
    remember_settled_render / remember_tail_render          (text, note) — what prompt_build's Block 3 / Block 4 call
    remember_rank(part)                  the salience/chain-depth order part_mid_term_manager.part_mid_term_refresh() reads
    remember_window_read(part, cutoff)   every memory with its target block and whether it lands — the
                                        ordering tool's estimate, cut by the same _fit() the two windows use

SELF'S ORDERING IS RESPECTED HERE (2026-10-02). remember_ordering_manager.py holds, per entity, the
memories Self has ordered and the ones Self sidelined. _arrange() is the one place that order is applied,
for both windows, remember_rank() and remember_window_read() alike: a sidelined memory is left out; a
memory the ordering does not name is unsorted and goes first, newest first under the bounded salience
reorder; the ordered ones follow, most kept first — the list top-down, read until the budget is spent,
never reversed. With no ordering on file _arrange() returns exactly the salience order this module has
always cut its windows from.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from remember_manager import remember_read                          # noqa: E402
import remember_manager as RM                                       # noqa: E402  RM.BUDGET, RM.SALIENCE_K,
# RM.SALIENCE_WEIGHT read at use — a setting-owned constant is never from-imported (a copy the
# settings refresh at the fold cannot reach; 2026-09-14)
import remember_ordering_manager as ROM                             # noqa: E402  Self's ordering


# ------------------------------------------------------------ Self's ordering
def _load(part: str) -> tuple[list[dict], dict[int, str], dict]:
    """ONE read of the register and of Self's ordering of it: the records in file order, each
    record's ordering key by the record's own identity, and the ordering. Every function below
    arranges the SAME list objects it read here — a second remember_read() would hand back new
    dicts the key map does not know."""
    records = remember_read(part)
    keys = {id(r): k for r, k in zip(records, ROM.remember_ordering_keys_read(records))}
    return records, keys, ROM.remember_ordering_read(part)


def _arrange(es: list[dict], keys: dict[int, str], ordering: dict,
             depths: dict[str, int]) -> list[dict]:
    """`es` — one window's records, newest first — in the order that window is cut from.

    A SIDELINED memory is left out. An UNSORTED one (the ordering does not name it: it was written
    after the last save) goes first, newest first under the bounded salience reorder — the rule
    that applied to every record before an ordering existed. The ORDERED ones follow, most kept
    first, exactly as Self left them: salience does not move a memory Self has placed.

    NO ORDERING ON FILE IS THE OLD ORDER, by construction and not by a branch: nothing is
    sidelined, nothing is ordered, every record is unsorted, and this returns
    _salience_order(es, depths)."""
    sidelined = ordering.get("sidelined") or {}
    rank = {k: i for i, k in enumerate(ordering.get("order") or [])}
    kept = [r for r in es if keys.get(id(r)) not in sidelined]
    unsorted = [r for r in kept if keys.get(id(r)) not in rank]
    ordered = sorted((r for r in kept if keys.get(id(r)) in rank),
                     key=lambda r: rank[keys[id(r)]])
    return _salience_order(unsorted, depths) + ordered

# ----------------------------------------------------------------- projection
# HEAD_NONE (an explicit "## What you have chosen to remember / *Nothing
# on file yet.*" heading) DELETED 2026-09-01 -- audit-register.md #30
# found it zero-reference: remember_project() below returns "" for a part with no
# memories (the `if not es:` branch), never this constant. Whether a part
# with no memories SHOULD see an explicit empty-state heading instead of
# silence is an open design question, not decided by this deletion --
# flagged for a ruling, not resolved here.


def remember_project(part: str) -> tuple[str, dict]:
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
    field. So the only lever a part actually had was to write the thing
    again, which is what the standing guidance tells it to do — TRUE AS
    MEASURED UNTIL 2026-08-29, when remember_expand.py (tier A recall)
    gave eviction a topic-conditional return path: a seed matching the
    day's topic or focus issues re-enters BLOCK 4 quoted above its minting
    circle's excerpt, trial arm permitting. The standing view this
    function renders is unchanged either way."""
    records, keys, ordering = _load(part)
    es = sorted(records, key=lambda r: r.get("date", ""), reverse=True)
    if not es:
        return "", {"part": part, "total": 0, "shown": 0, "omitted": 0,
                    "chars": 0}
    # BOUNDED salience/chain-depth reorder (DESIGN_V2, 2026-08-22) — a
    # no-op on any record without a salience tag, so this is byte-identical
    # to before on every register that predates the extension. Self's
    # ordering, when there is one, is applied in the same place: _arrange().
    # `es` stays the whole list, so a sidelined memory counts as on file and
    # as omitted — the header's two words for exactly what it is.
    body, shown, used = _window(_arrange(es, keys, ordering, _chain_depths(es)))
    omitted = len(es) - shown
    head = (f"## What you have chosen to remember\n\n"
            f"*{len(es)} on file, {shown} shown here within your "
            f"{RM.BUDGET}-character budget ({used} used), {omitted} "
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


# ------------------------------------------------------- cutoff-aware split
# B44, RULED 2026-08-15 (the "Projection" ruling, R170's
# "mechanical selection... no LLM call, no new artifact"). Until this, the
# WHOLE register rode in BLOCK 4 (block(), retired 2026-09-03, D81) — uncached, resent every
# circle regardless of how old a memory was. This splits it at `cutoff`
# (part_mid_term_manager.part_mid_term_cutoff_read(part)'s own "when" — this part's identity was
# last derived): everything on file BEFORE that moment is SETTLED (it was
# already there the last time this part's identity was distilled) and
# rides BLOCK 3's cache boundary; everything from that moment on is the
# TAIL — small, uncached, live, same as BLOCK 4 always was.
#
# `remember_project()` above is UNCHANGED and still the whole-register view — this
# module's own CLI (`--part <name>`, main() below; there is no `--project` flag)
# and `cutoff=None`'s degrade path both still want it.


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
                    k: int | None = None) -> list[dict]:
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
    against unscored data (every bonus 0) reorders nothing.

    `k` defaults to RM.SALIENCE_K AT THE CALL, not at def time: a default argument is an
    import-time copy, and the settings refresh at the fold cannot reach one."""
    if k is None:
        k = RM.SALIENCE_K
    ranked = []
    for i, r in enumerate(es):
        bonus = min(RM.SALIENCE_WEIGHT.get(r.get("salience"), 0)
                    + depths.get(r.get("id"), 0), k)
        target = max(0, i - bonus)
        ranked.append((target, -bonus, i, r))
    ranked.sort(key=lambda t: (t[0], t[1], t[2]))
    return [r for *_prefix, r in ranked]


def remember_rank(part: str) -> list[dict]:
    """This part's whole register, newest-first recency BOUNDED-reordered
    by salience/chain-depth — part_mid_term_manager.part_mid_term_derive()'s DESIGN_V2 input (step 8:
    "the score-ranked record order"). Not used by remember_project()'s own budget
    window's SOURCE list (that stays entries(part) — this is a separate,
    read-only view for the mid_term derivation call).

    Self's ordering applies here as it does to the windows (_arrange): a sidelined
    memory is not in the list, and an ordered one stands where Self placed it."""
    records, keys, ordering = _load(part)
    es = sorted(records, key=lambda r: r.get("date", ""), reverse=True)
    return _arrange(es, keys, ordering, _chain_depths(records))


def _line(r: dict) -> str:
    """One memory as its window renders it."""
    # TAGGED WITH THE CIRCLE IT WAS WRITTEN IN — R<OT>:, the operator's
    # own spelling, 2026-08-27. The register has stamped `circle` on
    # every record since the field was added; until now the projection
    # threw it away, so a part received an undated list and could not
    # tell a memory written last night from one written in June.
    #
    # THE Coordinator STAMPS IT; A PART NEVER TYPES ONE. A part cannot:
    # the OT reaches no block and no message of its view — verified
    # 2026-08-27 against prompt_messages_render() and a rendered prompt — so a
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
    return f"\n- {tag}{r['text']}\n"


def _fit(es: list[dict]) -> list[tuple[dict, str]]:
    """The records of `es` that fit BUDGET, in order, each with the text it renders as. ONE
    definition of "fits the budget" for the windows and for the ordering tool's estimate
    (remember_window_read), so the estimate cannot drift from what a prompt carries.

    `break`, not `continue`, at the budget edge — see _window()."""
    out: list[tuple[dict, str]] = []
    used = 0
    for r in es:
        block = _line(r)
        if used + len(block) > RM.BUDGET:
            break
        out.append((r, block))
        used += len(block)
    return out


def _window(es: list[dict]) -> tuple[str, int, int]:
    """Newest-first BUDGET window over an already-filtered/sorted `es` —
    the record-rendering half of remember_project()'s mechanism, factored out so
    remember_settled_project()/remember_tail_project() — and, since 2026-08-19, remember_project()
    itself (review, tier 5 #43: a third inline copy of this loop
    survived its own factoring-out) — share ONE definition of "fits the
    budget". The head line stays each caller's own: BLOCK 3's settled
    header and BLOCK 4's tail header must not share literal text
    (block_overlap_verify.py, R158).

    `break`, not `continue`, at the budget edge (tier 5 #57): skipping
    an over-budget NEWER record and going on rendering older ones was
    fill-packing, while every header says "{omitted} OLDER omitted" and
    The 2026-08-12 ruling frames the budget as "pushing an older one
    out of view" — recency is the priority lever, so the window ends at
    the first record that does not fit. Measured before changing:
    2026-08-19, no part's register comes near BUDGET, so no live
    projection changes a byte.

    The loop itself is _fit(), and one memory's rendering is _line()."""
    fit = _fit(es)
    return "".join(b for _r, b in fit), len(fit), sum(len(b) for _r, b in fit)


def _split_records(records: list[dict], cutoff: str | None) -> tuple[list[dict], list[dict]]:
    """`records`, newest-first, split at `cutoff` — a
    'YYYY-MM-DDTHH:MM:SS' UTC prefix, part_mid_term_manager.part_mid_term_cutoff_read()'s own
    format. A record strictly BEFORE `cutoff` is SETTLED; everything else
    (including a same-second write — see refresh_cutoff()'s docstring) is
    the TAIL. `cutoff=None` puts everything in the tail — nothing has been
    distilled yet, so nothing can be called settled."""
    es = sorted(records, key=lambda r: r.get("date", ""), reverse=True)
    if cutoff is None:
        return [], es
    settled = [r for r in es if r.get("date", "")[:19] < cutoff]
    tail = [r for r in es if r.get("date", "")[:19] >= cutoff]
    return settled, tail


def _split(part: str, cutoff: str | None) -> tuple[list[dict], list[dict]]:
    """This part's remember records, split at `cutoff` — _split_records() over one read."""
    return _split_records(remember_read(part), cutoff)


def remember_settled_project(part: str, cutoff: str | None) -> tuple[str, dict]:
    """BLOCK 3's mechanical remember window (B44) — everything on file as
    of this part's last mid_term refresh, budgeted and rendered exactly as
    remember_project() always has, never routed through mid_term's own LLM
    derivation."""
    records, keys, ordering = _load(part)
    settled, _tail = _split_records(records, cutoff)
    if not settled:
        return "", {"part": part, "total": 0, "shown": 0, "omitted": 0,
                    "chars": 0}
    # Chain depth is computed over the WHOLE register (ancestry can cross
    # the settled/tail boundary), the bounded reorder only over this window
    # (DESIGN_V2, 2026-08-22) — and Self's ordering with it (_arrange).
    body, shown, used = _window(_arrange(settled, keys, ordering, _chain_depths(records)))
    omitted = len(settled) - shown
    head = (f"## What you have chosen to remember\n\n"
            f"*{len(settled)} on file as of your last identity refresh, "
            f"{shown} shown here within your {RM.BUDGET}-character budget "
            # NOT "older omitted" — see remember_project()'s own note on the
            # bounded salience/chain-depth reorder just above.
            f"({used} used), {omitted} omitted from view. Nothing "
            f"here is owed to anyone — say it again if it still matters.*\n")
    return head + body, {"part": part, "total": len(settled), "shown": shown,
                         "omitted": omitted, "chars": used}


def remember_tail_project(part: str, cutoff: str | None) -> tuple[str, dict]:
    """BLOCK 4's uncached tail (B44) — only what this part has written
    SINCE its last mid_term refresh. `cutoff=None` degrades to remember_project()'s
    original whole-register view, unchanged — a part whose mid_term has
    never been derived sees exactly what BLOCK 4 always showed it."""
    if cutoff is None:
        return remember_project(part)
    records, keys, ordering = _load(part)
    _settled, tail = _split_records(records, cutoff)
    if not tail:
        return "", {"part": part, "total": 0, "shown": 0, "omitted": 0,
                    "chars": 0}
    body, shown, used = _window(_arrange(tail, keys, ordering, _chain_depths(records)))
    omitted = len(tail) - shown
    head = (f"## Remembered since your last identity refresh\n\n"
            f"*{len(tail)} written this circle so far, {shown} shown here "
            f"within your {RM.BUDGET}-character budget ({used} used)"
            # NOT "older omitted" — see remember_project()'s own note.
            + (f", {omitted} omitted from view" if omitted else "")
            + f". Carries into your identity at the next refresh.*\n")
    return head + body, {"part": part, "total": len(tail), "shown": shown,
                         "omitted": omitted, "chars": used}


def remember_settled_render(part: str, cutoff: str | None) -> tuple[str, str]:
    """WHAT prompt_build.py's BLOCK 3 assembly calls (B44)."""
    text, st = remember_settled_project(part, cutoff)
    note = f"{st['shown']}/{st['total']} shown"
    if st.get("omitted"):
        note += f" · {st['omitted']} omitted"
    return text, note


def remember_tail_render(part: str, cutoff: str | None) -> tuple[str, str]:
    """WHAT prompt_build.py's BLOCK 4 assembly calls (B44) — replaces the
    unconditional block(part) call there."""
    text, st = remember_tail_project(part, cutoff)
    note = f"{st['shown']}/{st['total']} shown"
    if st.get("omitted"):
        note += f" · {st['omitted']} omitted"
    return text, note


# ------------------------------------------------------- the tool's estimate
def remember_window_read(part: str, cutoff: str | None,
                         ordering: "dict | None" = None) -> dict:
    """Every memory `part` has on file, in the order the ordering tool lists them, each with the
    BLOCK it is bound for and whether it lands there — what ui/remember_ordering.py shows as
    "expected to land in the prompt".

    AN ESTIMATE OF THE NEXT OPEN, MADE BY THE CODE THAT OPENS IT: the same split at `cutoff`
    (BLOCK 3 before it, BLOCK 4 from it on; everything BLOCK 4 when it is None), the same
    _arrange() and the same _fit() the two windows call. An estimate because a circle closing
    before that open adds memories ahead of these and moves the cutoff.

    `ordering` is a WORKING ordering in remember_ordering_read()'s shape — the tool's list
    before it is saved — judged in place of the one on file. Nothing here writes.

    Returns {cutoff, budget, blocks: {3: {total, shown, omitted, chars}, 4: {...}}, rows}. A row
    is {key, record, block, chars, sorted, sidelined, lands}: `chars` what the memory costs its
    window, `sorted` whether the ordering names it, `sidelined` when Self sidelined it or None,
    `lands` True, False (cut), or None for a sidelined memory. Rows run unsorted first — BLOCK 4's
    then BLOCK 3's, each as its window arranges them — then the ordered, most kept first."""
    records, keys, saved = _load(part)
    ordering = saved if ordering is None else ordering
    rank = {k: i for i, k in enumerate(ordering.get("order") or [])}
    sidelined = ordering.get("sidelined") or {}
    depths = _chain_depths(records)
    settled, tail = _split_records(records, cutoff)
    rows: dict[str, dict] = {}
    blocks: dict[int, dict] = {}
    unsorted: list[str] = []
    for number, es in ((4, tail), (3, settled)):
        arranged = _arrange(es, keys, ordering, depths)
        fit = _fit(arranged)
        landed = {id(r) for r, _b in fit}
        blocks[number] = {"total": len(es), "shown": len(fit), "omitted": len(es) - len(fit),
                          "chars": sum(len(b) for _r, b in fit)}
        for r in es:
            k = keys[id(r)]
            rows[k] = {"key": k, "record": r, "block": number, "chars": len(_line(r)),
                       "sorted": k in rank, "sidelined": sidelined.get(k),
                       "lands": None if k in sidelined else id(r) in landed}
        unsorted += [keys[id(r)] for r in arranged if keys[id(r)] not in rank]
    ordered = sorted((k for k in rows if k in rank), key=lambda k: rank[k])
    placed = set(unsorted) | set(ordered)
    # A sidelined memory the ordering does not place (a hand-made file can say so; the tool's
    # own save always places it) is still a row — last, where the least kept stand.
    stray = [k for k in rows if k not in placed]
    return {"cutoff": cutoff, "budget": RM.BUDGET, "blocks": blocks,
            "rows": [rows[k] for k in unsorted + ordered + stray]}


def main() -> int:
    a = sys.argv[1:]
    part = a[a.index("--part") + 1] if "--part" in a else None
    if not part:
        print("  --part <name> required")
        return 1
    text, st = remember_project(part)
    print(text or "  (nothing on file)")
    print(f"\n  {st}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
