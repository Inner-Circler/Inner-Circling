#!/usr/bin/env python3
"""
role_context.py — Block 3 (part_identity)'s sole assembler, 2026-09-02
(docs/CIRCLE_TYPES_DESIGN.md), matching group_context.py/group_attention.py's
already-shipped shape for Blocks 1/2.

COORDINATES the seven segments Block 3 is made of, gluing pieces from
five other files together with the literal structural text between them
("## Your identity\n") -- it no longer reads parts/<p>/* itself. The
part's own long_term.md (read + stripped), its speaking-rules tail and
rendered [context] answers, and its header line moved to
parts_prompt_projection.py, 2026-09-02, on direct instruction -- the same move
group_context.py/group_attention.py/topic_prompt_projection.py already made
for their own registers, with part_roster.py folded into the new module too
rather than imported here. What remains here is orchestration: call
parts_prompt_projection.py, instrument_manager.py, part_mid_term_manager.py and remember_manager.py,
concatenate what each returns.

check_best_practices.py's narrowcast_block() MOVED, SAME DAY, to
parts_prompt_projection.part_practices_render() -- this module no longer imports
check_best_practices.py (practice_manager.py / practice_verify.py since
2026-09-03) at all. The narrowcast_practices() wrapper this
file used to hold went with it; the call below is now the same direct
shape every other segment in part_context_block_render() already used.

THE cutoff FIX (ruled 2026-09-02): Block 3 and Block 4 both need the SAME
part_mid_term_manager.part_mid_term_cutoff_read(part) value -- a part's identity as of its own last
mid_term refresh -- or entries double-count or drop between "already
distilled" (Block 3's remember_prompt_projection.remember_settled_render) and "not yet distilled"
(Block 4's remember_prompt_projection.remember_tail_render). part_context_block_render() computes it ONCE and returns it;
role_attention.py receives it as a parameter and never imports mid_term
itself.

MID_TERM IS IMPORTED LAZILY (inside part_context_block_render(), not at module level). The
import cycle that once required it -- part_mid_term_manager.py importing prompt_build.py at
its own module level for the read helpers prompt_build re-exported -- closed on 2026-09-09
with the facade: part_mid_term_manager.py imports parts_prompt_projection.py as a function
local, and nothing in it imports prompt_build.py or this module. The import is kept lazy as
it was: the shape is harmless and unchanged, and it no longer guards anything.
"""

from __future__ import annotations

from record_paths import PART_TAGS


def part_context_block_render(part: str) -> tuple[str, "str | None", int]:
    """The whole of Block 3 for one part. Returns (identity_text, cutoff,
    narrowcast_chars) — cutoff and narrowcast_chars exist for callers
    (role_attention.part_attention_stage(), prompt_build.prompt_part_assemble()'s diagnostic note)
    that need them without recomputing."""
    import part_mid_term_manager as MT          # LAZY -- see module docstring
    import remember_prompt_projection as _RPP   # LAZY -- same reasoning, symmetry
    import parts_prompt_projection as PP

    who = PP.part_header_render(part)
    lt = PP.part_ident_core_render(part)
    identity = who + f"## Your identity\n{lt}"

    _it = PP.part_identity_tail_render(part)
    if _it.strip():
        identity += "\n\n" + _it.strip()

    import instrument_manager as INST
    _prof = INST.instrument_block_render(part)
    if _prof.strip():
        identity += "\n\n" + _prof.strip()

    distilled, _why = MT.part_mid_term_block_render(part)
    if distilled.strip():
        identity += f"\n\n{distilled.strip()}"

    # B44: the cutoff BLOCK 3's settled remember window and BLOCK 4's
    # tail split on — this part's identity as of its OWN last mid_term
    # refresh. None (absent/legacy mid_term) means nothing is settled
    # yet; remember_prompt_projection.remember_tail_project()'s own cutoff=None branch degrades
    # to the pre-B44 whole-register view.
    cutoff = MT.part_mid_term_cutoff_read(part)

    mine = PP.part_practices_render(PART_TAGS[part])
    if mine.strip():
        identity += "\n\n" + mine.rstrip("\n")

    settled, _swhy = _RPP.remember_settled_render(part, cutoff)
    if settled.strip():
        identity += "\n\n" + settled.strip()

    return identity, cutoff, len(mine)
