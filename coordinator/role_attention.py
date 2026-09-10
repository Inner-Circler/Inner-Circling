#!/usr/bin/env python3
"""
role_attention.py — Block 4 (part_objectives)'s sole assembler, 2026-09-02,
matching group_context.py/group_attention.py's already-shipped shape for
Blocks 1/2.

BLOCK 4 IS BUILT IN TWO PASSES, NOT BY DESIGN CHOICE HERE BUT BY A REAL
TIMING CONSTRAINT already present in circle.py before this move: part_attention_stage()
runs where system_blocks() always ran, immediately after the working set is
chosen and BEFORE the topic exists (the remember tail does not need a
topic); part_attention_finalize() runs later, once the topic and chosen focus nodes are
known, and is the one and only call site for remember_expand.remember_expand_apply() — a
DELIBERATELY SEPARATE module (a flag-gated, killable Tier A recall trial,
per docs/MEMORY_DESIGN.md's own decision table) that this module delegates
COMPUTATION to rather than reimplements. "Remember" stays one notion with
one home; what is split here is WHEN each half of Block 4 can run, not
what either half means.

THIS MODULE IS THE ONLY WRITER OF sysblocks[p][3], since 2026-09-02 —
remember_expand.remember_expand_apply() used to reach into sysblocks itself; asked why a
different file was touching a block it does not own, with no ruling
(R387 named the PLACEMENT, never the write mechanism) requiring it, apply()
was changed to return {part: pack_text} and hand it back. part_attention_finalize() below
does the actual write, matching Block 1/2/3's own shape exactly: an
ingredient returns text, only the assembler ever touches the packaged
block structure.
"""

from __future__ import annotations

PART_OBJECTIVES_EMPTY = "(nothing pending for you this circle)"


def part_attention_stage(part: str, cutoff: "str | None") -> str:
    """Phase 1: the remember tail — entries not yet folded into mid_term's
    distillate, as of the SAME cutoff role_context.part_context_block_render() used for the
    settled half. Called before the topic is known; ask fragments and
    anything else topic-dependent are not part of this phase."""
    import remember_prompt_projection as RPP
    tail, _why = RPP.remember_tail_render(part, cutoff)
    return tail.strip() or PART_OBJECTIVES_EMPTY


def part_attention_finalize(sysblocks: dict, parts: list, topic: str,
             chosen: "list[str] | None", ot: str,
             arm: "str | None" = None) -> None:
    """Phase 2: once the topic and chosen focus nodes are known. Delegates
    the COMPUTATION to remember_expand.remember_expand_apply() — this function IS the call
    site circle.py used to own directly; moving it here only relocates WHO
    calls remember_expand, not what it does. THE WRITE ITSELF is this
    function's own, since 2026-09-02: apply() returns {part: pack_text}
    rather than reaching into sysblocks itself, so this is the one place
    BLOCK 4's uncached tail can gain a second, topic-dependent piece.

    apply() already never raises — every failure inside it degrades to an
    empty dict, same guarantee it always gave. The try/except below is
    defence in depth for the write loop itself, not a new risk it covers:
    `parts` is the same list circle.py used to build `sysblocks`, so every
    part here already has a sysblocks[p][3] to write into."""
    import remember_expand as REX
    try:
        packs = REX.remember_expand_apply(parts, topic, chosen, ot, arm=arm)
    except Exception:                                        # noqa: BLE001
        return   # never cost an open
    for p, pack in packs.items():
        if p not in sysblocks:
            continue
        # PART_OBJECTIVES_EMPTY IS AN ALTERNATIVE, NOT A PREFIX — the whole
        # block when there is nothing, replaced outright the moment there is
        # something. Appending gave a part with an empty remember tail and a
        # non-empty recall pack "(nothing pending for you this circle)" and
        # then the pack: a sentence saying nothing is pending, followed by
        # the thing that is. No <part_objectives> production admits that
        # string, and the grammar is right — this is the assembler catching
        # up to it (audit-register 2026-09-09 #53). The combination is
        # REACHABLE: the tail is cut at part_mid_term_cutoff_read() and is ε
        # once every record predates it, while remember_expand builds the
        # pack from the register whole, with no cutoff filter.
        if sysblocks[p][3]["text"].strip() == PART_OBJECTIVES_EMPTY:
            sysblocks[p][3]["text"] = pack
        else:
            sysblocks[p][3]["text"] += "\n\n" + pack
