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

circle_identity_text_render() is the column 2 ingredient; group_context.py's group_shared_read()
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


# ----------------------------------------------------------------- the layers
# BLOCK 1 SPLITS INTO TWO LAYERS — R464 ("Split first", 2026-09-06), B115, built 2026-09-07 to
# docs/CIRCLE_TYPES_DESIGN.md's classification. The UNIVERSAL layer is the circling mechanics every
# group shares — the four-block overview, the speaking rules, the annotation grammar, the crisis
# section (always, every group), the close format. Where the rulebook said something true of ONE
# group only — its title, what a part is, the register it speaks from, the commands it may propose,
# the dual-mirror, the Soul, its goals, its honesty examples, mutual knowing — the universal layer
# carries a SLOT MARK, one line, and the group's own layer file carries that slot's text under the
# matching mark. Composing is line substitution and nothing else: the IFS layer over the universal
# reproduces the pre-split rulebook byte for byte (coordinator/tests/test_process_core_layers.py holds
# the sha256). A group whose layer omits a slot gets nothing there — the mark line vanishes.
#
#     universal:  <!-- layer: the_soul -->          one line, where the section was
#     layer:      <!-- slot: the_soul -->           then the section's bytes, verbatim
#
LAYER_MARK = "<!-- layer: "
SLOT_MARK = "<!-- slot: "
MARK_END = " -->"

# THE GROUP'S LAYER. circle.py sets it at open from the group's own descriptor `layer` field
# (groups/<name>/group.toml, group_manager.group_layer_read()); a circle opened without --group, a
# descriptor with no `layer`, and every install this bundle ships run the IFS layer — DEFAULT_LAYER is
# the literal the packaging scan traces, so the file ships. A path is read relative to the tree.
DEFAULT_LAYER = HERE / "process_ifs.md"
_LAYER: "pathlib.Path | None" = None


def circle_identity_layer_set(layer: "str | pathlib.Path | None") -> pathlib.Path:
    """Choose the layer file for this circle. None -> DEFAULT_LAYER. Returns the path chosen;
    refuses loudly if it does not exist — a circle must not open on a rulebook with a hole."""
    global _LAYER
    p = DEFAULT_LAYER if layer is None else pathlib.Path(layer)
    if not p.is_absolute():
        p = HERE.parent / p
    if not p.is_file():
        raise FileNotFoundError(f"BLOCK 1 layer file not found: {p}")
    _LAYER = p
    return p


def circle_identity_layer_read() -> pathlib.Path:
    return _LAYER if _LAYER is not None else DEFAULT_LAYER


# THE GROUP'S WORD FOR ONE OF ITS MEMBERS — D104 (2026-09-07), on D99's ruling that PART is
# IFS speak for a ROLE. The universal layer is read by EVERY group and said "part" 29 times, so the
# band's three roles were told they are parts by the layer that carries only what is true of any
# group. The word is a token now, filled per group, so no prompt mixes the two: the IFS group
# declares "part" in its own descriptor and reads exactly as it always has, and a group that
# declares nothing gets the product's word.
#
# `{Part}` in the short_term template is NOT this token — it is a placeholder for the speaker's own
# name — and nothing here touches it.
DEFAULT_WORDS = ("role", "roles")
IFS_WORDS = ("part", "parts")               # what a circle opened without --group gets, as with
_WORDS: "tuple[str, str] | None" = None     # DEFAULT_LAYER above: the shipped install is the family


def circle_identity_words_set(words: "tuple[str, str] | None") -> tuple[str, str]:
    """Choose this circle's word for one of its members, singular and plural. None -> the IFS
    group's, matching DEFAULT_LAYER. Returns what was chosen."""
    global _WORDS
    _WORDS = tuple(words) if words else IFS_WORDS               # type: ignore[assignment]
    return _WORDS


def circle_identity_words_read() -> tuple[str, str]:
    return _WORDS if _WORDS is not None else IFS_WORDS


def _mark_name(line: str, prefix: str) -> "str | None":
    """The slot name a mark line names, or None when the line is not that mark."""
    body = line.rstrip("\n")
    if body.startswith(prefix) and body.endswith(MARK_END):
        return body[len(prefix):-len(MARK_END)].strip()
    return None


def circle_identity_slots_read(layer_text: str) -> dict[str, str]:
    """A layer file's slots: {name: the bytes under its mark, verbatim}. Text before the first
    mark is ignored — a layer file may open with a comment for its reader."""
    slots: dict[str, str] = {}
    cur: "str | None" = None
    buf: list[str] = []
    for ln in layer_text.splitlines(keepends=True):
        name = _mark_name(ln, SLOT_MARK)
        if name is not None:
            if cur is not None:
                slots[cur] = "".join(buf)
            cur, buf = name, []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        slots[cur] = "".join(buf)
    return slots


def circle_identity_marks_read(universal_text: str) -> list[str]:
    """The slot names the universal layer carries, in file order."""
    out = []
    for ln in universal_text.splitlines(keepends=True):
        name = _mark_name(ln, LAYER_MARK)
        if name is not None:
            out.append(name)
    return out


def circle_identity_layers_render(universal_text: str, layer_text: "str | None") -> str:
    """The universal layer with each slot mark replaced by the layer's bytes for that slot —
    or by nothing, when the layer has no such slot or there is no layer at all. Pure text; the
    length-rule substitution is circle_identity_text_render()'s, applied after."""
    slots = circle_identity_slots_read(layer_text) if layer_text else {}
    out: list[str] = []
    for ln in universal_text.splitlines(keepends=True):
        name = _mark_name(ln, LAYER_MARK)
        out.append(slots.get(name, "") if name is not None else ln)
    return "".join(out)


def circle_identity_text_render() -> str:
    """BLOCK 1's rulebook text: the universal layer (process_core.md) with the group's layer
    composed in (R464, B115, 2026-09-07 — for the IFS group, byte-identical to the one-file
    rulebook it replaced), then the length rule's two numbers substituted. THE ONE PLACE either
    file is read — thirty-plus callers go through group_context.group_shared_read(), which calls
    straight into this — so there is nowhere else for the composition or the substitution to be
    missed.

    `.replace()`, not `.format()`: the document is prose that may legally
    contain a brace, and a rulebook must not fail to load because someone
    wrote one."""
    universal = record_ro_read(HERE / "process_core.md")
    layer = record_ro_read(circle_identity_layer_read())
    one, many = circle_identity_words_read()
    return (circle_identity_layers_render(universal, layer)
            .replace("{LENGTH_AIM}", str(LENGTH_AIM_WORDS))
            .replace("{LENGTH_MAX}", str(LENGTH_MAX_WORDS))
            .replace("{Members}", many.capitalize()).replace("{members}", many)
            .replace("{Member}", one.capitalize()).replace("{member}", one))


def group_best_practices() -> str:
    """BLOCK 1's contribution — every part reads this, identically. MOVED
    from check_best_practices.group_best_practices(), 2026-09-02, same body;
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
