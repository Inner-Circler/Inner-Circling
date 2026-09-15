#!/usr/bin/env python3
"""
parts_prompt_projection.py — every parts/<p>/* read Block 3's assembler needs,
(parts_projection.py until 2026-09-03 — F5 under R435: a PROMPT projection says so in its name)
pulled out of role_context.py, 2026-09-02, on direct instruction: the same
move group_context.py/group_attention.py/topic_prompt_projection.py already made
for their own registers, extended here with part_roster.py folded in too — a
part's own directory (long_term.md, part.toml) and part_roster.py's own
import-time reading of that same directory (TAG_BY_DIR, IDENTITY_TAILS)
are one subject, not two, once nothing outside this file needs to touch
either directly.

    python coordinator/parts_prompt_projection.py <dir>    header + ident_core +
                                                     identity_tail, concatenated

OWNS FOUR OF BLOCK 3's SEVEN SEGMENTS: <header> (the part's own Tag,
substituted into a fixed template), <ident_core> (long_term.md, read and
stripped), <identity_tail> (the part's own speaking-rules tail and
rendered [context] answers, both from part.toml), and, since 2026-09-02,
<part_practices> (part_practices_render(), self/best_practices.toml's own
narrowcast rows — a DIFFERENT register from the other three, moved here
on direct instruction rather than staying paired with its BLOCK 1
counterpart in one shared module, since the two consumers may diverge in
what they render even though both read one register today; see that
function's own docstring). role_context.py calls each of the four, then
supplies the "## Your identity\n" heading between the first two itself —
the literal glue between segments is the assembler's own job; the
segments themselves are this module's.

<header> WAS PROVENANCE-ONLY, AND NOW IS A REAL CALL — the one exception
found 2026-09-02 when a direct question asked whether every edge into a
block was a verified, real, per-request call. part_roster.py:scan() runs once,
at part_roster.py's own import; nothing called it at prompt-assembly time, so
the graph drew it dashed. part_header_render(), below, DOES run at request time — it
still reads part_roster.TAG_BY_DIR, itself built by that same import-time
scan(), but the function credited with the text a part actually receives
is now one this module calls for real, not one whose only connection is
where the underlying data first came from.
"""

from __future__ import annotations

import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import part_roster as R
from record_paths import ROOT, record_dir
import record_model as M


def record_ro_read(p: pathlib.Path) -> str:
    """Read-only by construction. Fails loudly rather than silently
    degrading. Duplicate of process_core_prompt_projection.record_ro_read()
    and memory/issue_prompt_projection.record_ro_read() — small enough that
    importing across files to share it would carry more risk (a circular
    import back into group_context.py) than the duplication does.

    THE TWIN-NAMING WAS MISSING HERE, and only here, until 2026-09-09
    (audit-register 2026-09-09 #64). Both siblings carried it; the
    2026-09-09 register's own predecessor cleared this clone group on the
    strength of "each names the other two", which was true of two of the
    three. `git log -S "circular"` on this file returns nothing, so it was
    never a regression — the claim was wrong when it was made."""
    return p.read_text(encoding="utf-8")


def part_settled_strip(text: str) -> str:
    """Drop '## Settled' and everything after it before sending a part its own
    long_term.md.

    Settled entries are 22.9% of the memory files (32.5% for one part) and
    they are concluded history — a resolved 2026-06-17 concern sitting in the same
    file, in the same format, at the same apparent weight as live material. The
    cost is not tokens, which are cached; it is attention competing with what is
    actually live. The section stays on disk untouched and the nightly still reads
    it; only the prompt is trimmed. (2026-07-27, per the issue-model decision that
    settled material does not reach a part.)"""
    i = text.find("\n## Settled")
    return text if i < 0 else text[:i].rstrip() + "\n"


def part_identity_strip(text: str) -> str:
    """Drop everything from `record_model.IDENTITY_END` onward in a long_term.md.

    THE DELIMITER IS NOT `## Dream entries` ANY MORE — Self, 2026-08-22:
    *"do not restore the obsolete ## Dream entries heading as a delimiter; add a
    valid delim like '## required end' and change to code accordingly."* The
    dream corpus moved to `parts/<p>/dreams.toml` on 2026-08-12, so that heading
    had been standing over a one-line tombstone with zero entries under it in all
    seven files. IMPORTED, not re-typed: `record_model` owns the boundary because it
    is the module that verifies what sits either side of it, and two spellings of
    one delimiter is how the two sides stop agreeing.

    What remains is the part's foundational identity — the material no nightly
    process authored. These sections are NOT equal (1,186 chars for the
    Soul against 4,158 for another part), so differences observed between parts in
    a circle may be differences in specification rather than in part."""
    i = text.find("\n" + M.IDENTITY_END)
    return text if i < 0 else text[:i].rstrip() + "\n"


def part_header_render(part: str) -> str:
    """<header> — '# You are the "<Tag>" part (<dir>).\\n\\n'. MOVED from
    role_context.py's own block(), 2026-09-02, where it built this line
    inline. The Tag comes from part_roster.TAG_BY_DIR (record_paths.PART_TAGS is the
    same dict, aliased); reading it through roster directly here, now that
    roster is imported in this file rather than role_context.py, removes
    one hop of indirection."""
    return f'# You are the "{R.TAG_BY_DIR[part]}" part ({part}).\n\n'


def part_ident_core_render(part: str) -> str:
    """<ident_core> — parts/<p>/long_term.md, read and stripped to just the
    part's foundational identity. MOVED verbatim from role_context.py's
    own block(), 2026-09-02 — same read, same two strips, same order."""
    base = record_dir(ROOT, "parts") / part
    return part_identity_strip(part_settled_strip(record_ro_read(base / "long_term.md")))


def part_identity_tail_render(part: str) -> str:
    """BLOCK 3's per-part tail: text belonging to ONE part, in its own voice.

    NO PART DECLARES ONE TODAY, and that is the current correct state — see
    "WHAT IT CARRIES" below. The mechanism is built, tested and unused.

    WHAT IT CARRIES. It held the Soul's speaking rules for one day
    (R303, below) and does not any more
    (R304, same date): Self rewrote
    `parts/soul/long_term.md` and its `## My role in circles` said the same
    thing better, in the same first person, landing in the same block — two
    sources for one subject, adjacent, the copy here the stricter of the two.
    What this key is FOR now is the per-user particulars an initialisation
    process will write. Self, 2026-08-22: *"I hope it can be delivered as-is
    for use by anyone, and that at initialization a to-be-created process can
    initialize soul/part.toml with specifics of the user."* `long_term.md` is
    universal and ships unchanged, naming the categories — timeframe, parent
    genetics, gender, race, cultural and economic and religious and educational
    context — without filling them. This is where they get filled. That
    process does not exist yet.

    RULED 2026-08-22 (R303): "move the Soul's instructions
    to Block 3 in first person." It was `## The Soul` in process_core.md — BLOCK
    1 — so all seven parts read one part's rules, with the operative half opening
    "If you are the Soul:". minimal_core() had already named that as E09's shape
    one block earlier, and R246 had already built the fix; but R246 aimed it at
    `--minimal` alone, as a BLOCK 4 suffix keyed `minimal_tail`. Live circles
    kept the defect. This is the same mechanism finished: ONE key, BLOCK 3, both
    modes.

    BLOCK 3 RATHER THAN BLOCK 4 because block 3 is per-part AND cached, and a
    part's speaking rules are settled content — block 4 is the uncached block for
    what has not settled. Per-part text in block 3 costs no extra cache entry:
    block 3 was always per-part.

    THE TEXT IS THE PART'S OWN, read from `parts/<dir>/part.toml` via roster —
    R246, verbatim: *"put it in a part.toml field"*. Until then this module held
    the Soul's text as a literal in a `{"soul": ...}` mapping: a part NAME typed
    into shared mechanism, the last of the class B29/R123 spent two rulings
    removing, and a rename in this exact lineage (the Soul directory's, 2026-08-08) would
    have emptied it silently. Keyed by directory, so it follows any rename.

    A part that declares none gets "", which is every part but the Soul here and
    every part but none in a fresh bundle.

    AND THE RECORDED CONTEXT, RENDERED — 2026-08-23, the initialisation process
    the paragraph above said did not exist (docs/Initialization.md, stage 1).
    After the declared tail, one sentence per ANSWERED question that declares a
    `render` string, in question order, in the part's own first person — the
    part's voice continuing, under no heading. Read from parts/<dir>/part.toml
    at CALL time, not from an import-time constant: the dialog that records the
    answers runs one step before this circle's blocks are built, and its write
    must be what they carry.

    A QUESTION WITH NO `render` IS NEVER RENDERED. That is the whole of
    R329 (R132 stands): the Soul's given and preferred
    names are recorded in the file and have no path into this block, because
    the only path is the template, and they declare none. `{answer}` is
    substituted by replace(), not str.format(), so a stray brace in an
    authored sentence is text rather than an exception.

    MOVED verbatim from role_context.py, 2026-09-02 — same body, same
    docstring, roster now imported here instead of there."""
    declared = R.IDENTITY_TAILS.get(part, "")
    ctx = R.part_context_read(part)
    if not ctx:
        return declared
    lines = []
    for q in ctx["questions"]:
        answer = (ctx["answers"].get(q["key"]) or "").strip()
        render = q.get("render")
        if answer and render:
            lines.append(render.replace("{answer}", answer))
    if not lines:
        return declared
    rendered = "\n".join(lines)
    return f"{declared.rstrip()}\n\n{rendered}" if declared.strip() else rendered


def part_practices_render(part_tag: str) -> str:
    """<part_practices> — BLOCK 3's contribution for ONE part, empty for
    most parts, most circles. MOVED from check_best_practices.
    part_practices_render(), 2026-09-02, same body; that module's own
    narrowcast() (the eligible-row list this filters from) is what stays
    a lazy cross-import away.

    Sourced from self/best_practices.toml directly; there is no
    intermediate per-part slice in self/circle_briefing.md to leak from
    (E09's failure mode no longer has a text layer to occur in). Called
    directly by role_context.part_context_block_render() — the narrowcast_practices()
    wrapper it used to go through is gone; every other segment in that
    function is already a direct call into this module."""
    import practice_manager as PM
    mine = PM.practice_narrowcast(part_tag)
    if not mine:
        return ""
    return "\n".join(["## Your best practices", ""]
                     + [f"- {p['id']} — {p['title']}" for p in mine])


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: parts_prompt_projection.py <part-directory>\n")
        return 2
    part = sys.argv[1]
    print(part_header_render(part) + f"## Your identity\n{part_ident_core_render(part)}")
    tail = part_identity_tail_render(part)
    if tail.strip():
        print("\n" + tail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
