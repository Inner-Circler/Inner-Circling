#!/usr/bin/env python3
"""
group_context.py — the SOLE assembler of prompt Block 1 (circle_identity):
process_core.md, with the length rule's two numbers substituted in. The
operator, 2026-09-02: "a group_context.py ... responsible for every prompt element
written to Block 1 ... none aware of any of the others, all of the code
responsible for those fragment assemblies exists exclusively in the
corresponding single file." docs/CIRCLE_TYPES_DESIGN.md has the assessment
this build follows; docs/BNF.md's <circle_identity> production (BLOCK 1)
is the grammar this implements.

MOVED VERBATIM from prompt_build.py's group_shared_read(), 2026-09-02 — same name,
same body, same docstring, so its 30+ existing external callers (grep
confirms callers across coordinator/, work/ablations/, work/tools/) keep
working unchanged via prompt_build.py's own re-export.

BLOCK 1'S PRACTICES MOVED HERE TOO, 2026-09-02 (closing the gap this
docstring itself used to describe): `group_context_block_render()`, below, merges group_shared_read()'s
text with process_core_prompt_projection.group_best_practices() — the DECISION
that Block 1 is "core, then a blank line, then the broadcast" lives in the
one file responsible for Block 1, not in prompt_build.py's prompt_part_assemble().
Before this, group_shared_read() alone was Block 1's core but not its full text,
which was the one place this module fell short of the exclusive-assembler
shape role_context.py already achieves for Block 3's narrowcast half.
group_best_practices() ITSELF moved again, same day: check_best_practices.
broadcast_block() -> process_core_prompt_projection.group_best_practices() — that
module keeps the register's read/write/validate side unified, but the
BLOCK 1-shaped rendering now lives with its own consumer (see
process_core_prompt_projection.py's own docstring).

read_ro() AND THE TWO LENGTH-RULE CONSTANTS MOVED OUT, 2026-09-02 — to
process_core_prompt_projection.py. This module's own docstring used to explain why
they were duplicated here rather than imported from prompt_build.py; that
question is moot now that they live in a real column 2 ingredient module
instead, closing the one gap left when this file was found to be the only
one of the four sole assemblers still reading a file directly rather than
calling out to one. See process_core_prompt_projection.circle_identity_text_render().
"""

from __future__ import annotations


def group_shared_read() -> str:
    """process_core.md's own text, length-rule numbers already substituted
    — see process_core_prompt_projection.circle_identity_text_render(), which does the actual
    read. Concerns and the briefing text were the other two things this
    used to return.

    Concerns: the OC register (self/open_concerns.toml, concerns.py) is
    RETIRED outright, 2026-08-13 — vestigial: it had already been reduced,
    2026-08-05, to something Self deployed by speaking it himself, directly,
    into the circle pane rather than an ambient prompt channel, and nothing
    used that deployment path since. No successor; Self speaks whatever he
    wants directly, as any other statement.

    Briefing: self/circle_briefing.md is GONE (2026-08-11) — circle_objectives
    is built directly by circle_briefing_build(chosen), not read from a file here.

    NOT A GENERATED FILE, and the distinction matters because this project
    retired one. self/circle_briefing.md was written to disk by one process
    and read back by another, so it could go stale between them; nothing is
    written here, there is no second copy, and the source of truth is still
    process_core.md plus the register. instrument_manager.py already puts register
    content into a block this way.

    STILL BYTE-IDENTICAL FOR EVERY PART: both numbers are circle-wide, so
    BLOCK 1 is the same bytes for all seven and the cached prefix is
    unaffected. A change to either does move those bytes, which is why both
    settings are next_circle — the fold happens before any prompt is warmed."""
    import process_core_prompt_projection as PCP
    return PCP.circle_identity_text_render()


def group_context_block_render(core: str) -> tuple[str, int]:
    """The full BLOCK 1 text: `core` (group_shared_read()'s own text), the
    circle-wide best-practices broadcast, and CIRCLE_JOURNAL's newest entry
    (B94 stage 5, 2026-09-04), all merged. `core` is a parameter rather than
    a fresh group_shared_read() call so the caller's one-read-per-
    circle timing (all seven parts share the same bytes) is preserved
    exactly as it was when this concatenation lived in prompt_build.py's
    assemble_part() — this function only moved WHERE the decision is made,
    not WHEN group_shared_read() runs.

    CIRCLE_JOURNAL: the NEWEST entry only, never "the last few" — its own
    fold is already incremental revision (docs/MEMORY_DESIGN.md), so the
    newest entry already carries forward what matters from every prior one;
    reading more would repeat that same material, already folded, a second
    time. ε when the register is empty (a fresh install, or before this
    tree's first circle has closed) — same optional-source shape best
    practices already has, just below.

    Returns (the merged text, the practices text's own length in chars) —
    the count is a diagnostic for prompt_capture's manifest, mirroring
    role_context.part_context_block_render()'s own narrowcast_chars. Not
    also returning CIRCLE_JOURNAL's own length: nothing downstream reads a
    second count yet, and one would be added the day something does,
    exactly as this docstring itself says of any other change here."""
    import process_core_prompt_projection as PCP
    import circle_journal_manager as CJ
    prac = PCP.group_best_practices()
    journal = CJ.circle_journal_latest_read()
    parts = [core]
    if prac.strip():
        parts.append(prac.rstrip("\n"))
    if journal:
        parts.append("## Circle identity\n\n" + journal["text"])
    return "\n\n".join(parts), len(prac)
