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
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from remember_manager import remember_read, BUDGET, SALIENCE_K, SALIENCE_WEIGHT                      # noqa: E402

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
    es = sorted(remember_read(part), key=lambda r: r.get("date", ""), reverse=True)
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


def remember_rank(part: str) -> list[dict]:
    """This part's whole register, newest-first recency BOUNDED-reordered
    by salience/chain-depth — part_mid_term_manager.part_mid_term_derive()'s DESIGN_V2 input (step 8:
    "the score-ranked record order"). Not used by remember_project()'s own budget
    window's SOURCE list (that stays entries(part) — this is a separate,
    read-only view for the mid_term derivation call)."""
    es = sorted(remember_read(part), key=lambda r: r.get("date", ""), reverse=True)
    return _salience_order(es, _chain_depths(remember_read(part)))


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
    'YYYY-MM-DDTHH:MM:SS' UTC prefix, part_mid_term_manager.part_mid_term_cutoff_read()'s own
    format. A record strictly BEFORE `cutoff` is SETTLED; everything else
    (including a same-second write — see refresh_cutoff()'s docstring) is
    the TAIL. `cutoff=None` puts everything in the tail — nothing has been
    distilled yet, so nothing can be called settled."""
    es = sorted(remember_read(part), key=lambda r: r.get("date", ""), reverse=True)
    if cutoff is None:
        return [], es
    settled = [r for r in es if r.get("date", "")[:19] < cutoff]
    tail = [r for r in es if r.get("date", "")[:19] >= cutoff]
    return settled, tail


def remember_settled_project(part: str, cutoff: str | None) -> tuple[str, dict]:
    """BLOCK 3's mechanical remember window (B44) — everything on file as
    of this part's last mid_term refresh, budgeted and rendered exactly as
    remember_project() always has, never routed through mid_term's own LLM
    derivation."""
    settled, _tail = _split(part, cutoff)
    if not settled:
        return "", {"part": part, "total": 0, "shown": 0, "omitted": 0,
                    "chars": 0}
    # Chain depth is computed over the WHOLE register (ancestry can cross
    # the settled/tail boundary), the bounded reorder only over this window
    # (DESIGN_V2, 2026-08-22).
    settled = _salience_order(settled, _chain_depths(remember_read(part)))
    body, shown, used = _window(settled)
    omitted = len(settled) - shown
    head = (f"## What you have chosen to remember\n\n"
            f"*{len(settled)} on file as of your last identity refresh, "
            f"{shown} shown here within your {BUDGET}-character budget "
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
    _settled, tail = _split(part, cutoff)
    if not tail:
        return "", {"part": part, "total": 0, "shown": 0, "omitted": 0,
                    "chars": 0}
    tail = _salience_order(tail, _chain_depths(remember_read(part)))
    body, shown, used = _window(tail)
    omitted = len(tail) - shown
    head = (f"## Remembered since your last identity refresh\n\n"
            f"*{len(tail)} written this circle so far, {shown} shown here "
            f"within your {BUDGET}-character budget ({used} used)"
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
