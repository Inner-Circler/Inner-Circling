#!/usr/bin/env python3
"""
remember_list_projection.py — the REMEMBER register's LIST projection: Self's own `/remember-list
[<n>]` pull (docs/BNF.md REMEMBER_PROJECTION, the SELF half — R224, 2026-08-18).

IN remember.py UNTIL 2026-09-03 (B99 stage 17b; F5 under R435). remember_list() and
remember_record_show() and their file-order helper moved verbatim; only this header and the imports are
new — and RENAMED (R436, R442; mine): recall_listing -> remember_list, recall_record -> remember_record_show.
Nothing here reaches a circle: a PART's projection is remember_prompt_projection.py, pushed
into its prompt; this one renders on request at the command pane.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from remember_manager import remember_read, SELF, ORDER                                       # noqa: E402
from REGISTER_CLASS import register_list_footer, register_record_show                         # noqa: E402

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
# practice_manager.practice_list()'s own numbering explicitly is not.
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
    """File order. `remember_read()` is documented unordered, so this states the
    order recall depends on rather than inheriting it by luck."""
    return list(remember_read(part))


def remember_list(part: str = SELF) -> str:
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
    out.append("\n" + register_list_footer(len(es), "/remember-list"))
    return "\n".join(out)


def remember_record_show(n: int, part: str = SELF) -> str:
    """`/remember-list <n>` (also `recall <n>`): the whole record, every field it carries.

    EVERY FIELD, not a chosen few. A live record has date/circle/text; a
    DREAMING-authored one also has id and chain; a migrated one has class.
    Naming them here would mean this function needs editing every time the
    register grows a field, and the failure would be silent — a field
    present on disk and invisible to the one command that exists to show
    it. So it renders what is there, through REGISTER_CLASS.register_record_show():
    the register's ORDER, then every key ORDER does not name (B133)."""
    es = _ordered(part)
    if not es:
        return "  nothing remembered yet"
    return register_record_show(es, n, ORDER, body="text", verb="/remember-list")
