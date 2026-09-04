#!/usr/bin/env python3
"""
process_core_prompt_projection.py — the raw process_core.md read and the length-rule
(process_core_projection.py until 2026-09-03 — F5 under R435: a PROMPT projection says so in its name)
substitution, pulled out of group_context.py, 2026-09-02.

On direct instruction: column 3's four sole assemblers (group_context.py,
group_attention.py, role_context.py, role_attention.py) must get every byte
of data from a column 2 ingredient function, never from a file read inside
the assembler itself. group_context.py's own load_shared() was the one
remaining exception — the record_ro_read()/HERE/process_core.md/LENGTH_AIM_WORDS/
LENGTH_MAX_WORDS machinery lived there directly, unlike every other
register this project has already split a projection module out for
(topic_manager.py -> topic_prompt_projection.py, issue_schema.py -> issue_prompt_projection.py,
parts/<p>/* -> parts_prompt_projection.py). This module closes that one gap.

circle_identity_text_render() is the column 2 ingredient; group_context.py's load_shared()
now calls it and does nothing else. The two length-rule constants move here
too — they exist only to feed this one substitution.

group_best_practices() ADDED 2026-09-02 — BLOCK 1's OTHER real ingredient
(group_context.group_context_block_render() concatenates this module's circle_identity_text_render() with
this function's own text), moved out of check_best_practices.py on direct
instruction. That module keeps the register's read/write/validate side —
practices()/eligible()/broadcast()/narrowcast() and the whole PRACTICE
LIFECYCLE — unified; only the BLOCK 1-shaped RENDERING of a broadcast row
moves here. Its BLOCK 3 counterpart, role_best_practices(), is
parts_prompt_projection.py's, not this module's — the two consumers may diverge
in what they render (new fields per type) even though both read the same
register today, so they do not share a module just because they currently
look alike.
"""

from __future__ import annotations

import pathlib

import setting_manager as SET              # the length rule's two numbers

HERE = pathlib.Path(__file__).resolve().parent

# Mirrors group_context.py's own former LENGTH_AIM_WORDS/LENGTH_MAX_WORDS
# exactly — same settings keys, same defaults. prompt_build.py/circle_rounds.py
# each keep their own independent read of the same settings source too;
# this is a third independent read, not a fourth source of truth.
LENGTH_AIM_WORDS = SET.setting_value_read("statement_aim_words", 60)
LENGTH_MAX_WORDS = SET.setting_value_read("statement_max_words", 150)


def record_ro_read(p: pathlib.Path) -> str:
    """Read-only by construction. Fails loudly rather than silently
    degrading. Duplicate of group_context.read_ro()'s old body, and of
    every other projection module's own record_ro_read() — small enough that
    importing across files to share it would carry more risk (a circular
    import back into group_context.py) than the duplication does."""
    return p.read_text(encoding="utf-8")


def circle_identity_text_render() -> str:
    """process_core.md's own text, with the length rule's two numbers
    substituted. THE ONE PLACE process_core.md is read — thirty-plus
    callers go through group_context.group_shared_read(), which calls straight
    into this — so there is nowhere else for the substitution to be
    missed.

    `.replace()`, not `.format()`: the document is prose that may legally
    contain a brace, and a rulebook must not fail to load because someone
    wrote one."""
    return (record_ro_read(HERE / "process_core.md")
            .replace("{LENGTH_AIM}", str(LENGTH_AIM_WORDS))
            .replace("{LENGTH_MAX}", str(LENGTH_MAX_WORDS)))


def group_best_practices() -> str:
    """BLOCK 1's contribution — every part reads this, identically. MOVED
    from check_best_practices.broadcast_block(), 2026-09-02, same body;
    that module's own broadcast() (the eligible-row list this filters
    from) is what stays a lazy cross-import away.

    Called directly by group_context.group_context_block_render() at prompt-assembly time;
    nothing in between reads or writes self/circle_briefing.md for this
    content."""
    import practice_manager as PM
    rows = PM.practice_broadcast()
    all_parts = [p for p in rows if p["addressee"] == "All parts"]
    for_self = [p for p in rows if p["addressee"] == "Self"]
    if not all_parts and not for_self:
        return ""
    out = ["## Best practices", ""]
    out += [f"- {p['id']} — {p['title']}" for p in all_parts]
    if for_self:
        out += ["", "### Better options (for Self)", ""]
        out += [f"- {p['id']} — {p['title']}" for p in for_self]
    return "\n".join(out)
