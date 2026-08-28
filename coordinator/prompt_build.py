#!/usr/bin/env python3
"""
prompt_build.py — the prompt's construction: the identity read-layer,
circle_objectives (build_briefing), the four-block
assembly (system_blocks and kin), and the transcript-to-messages view
(render_messages). Phase 2 stage 2 of the coordinator partitioning
(2026-08-16); until then all of it lived in circle.py. Verbatim move —
bodies and comments unchanged.

THE PAYOFF THIS STAGE EXISTS FOR: five live modules (circle_audit.py,
prompt_show.py, check_block_overlap.py, midterms_project.py,
mid_term.py) imported the whole 4,000-line orchestrator to build or
inspect prompts; they import this module now. mid_term.py and this
module reference each other the same way mid_term and circle.py always
did — mid_term imports prompt_build at module level for read_ro/
strip_settled, and system_blocks() imports mid_term lazily at call
time for the staleness refresh; the lazy side is what keeps the pair
import-order-safe, unchanged in shape from before the move.

Pure transformation, deliberately: nothing here emits, writes a file,
or touches the network — it reads the tree (directly and through the
register modules) and returns strings and block lists.
"""

from __future__ import annotations

import pathlib

import roster as R                 # IDENTITY_TAILS — the per-part BLOCK 3 tail
from paths import ROOT, PART_TAGS
from transcript_store import withheld   # the recorded-but-never-in-the-room test
from llm_client import CACHE_TTL   # cc()'s TTL — the transport owns it
import ifs_model as IFS            # IDENTITY_END — the long_term.md boundary

HERE = pathlib.Path(__file__).resolve().parent


def cc() -> dict:
    return {"type": "ephemeral", "ttl": CACHE_TTL}


# ------------------------------------------------------------------ identity (read-only)
def read_ro(p: pathlib.Path) -> str:
    """Read-only by construction. Fails loudly rather than silently degrading."""
    return p.read_text(encoding="utf-8")


def strip_settled(text: str) -> str:
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


def strip_to_identity(text: str) -> str:
    """Drop everything from `ifs_model.IDENTITY_END` onward in a long_term.md.

    THE DELIMITER IS NOT `## Dream entries` ANY MORE — Self, 2026-08-22:
    *"do not restore the obsolete ## Dream entries heading as a delimiter; add a
    valid delim like '## required end' and change to code accordingly."* The
    dream corpus moved to `parts/<p>/dreams.toml` on 2026-08-12, so that heading
    had been standing over a one-line tombstone with zero entries under it in all
    seven files. IMPORTED, not re-typed: `ifs_model` owns the boundary because it
    is the module that verifies what sits either side of it, and two spellings of
    one delimiter is how the two sides stop agreeing.

    What remains is the part's foundational identity — the material no nightly
    process authored. These sections are NOT equal (1,186 chars for the
    Soul against 4,158 for another part), so differences observed between parts in
    a circle may be differences in specification rather than in part."""
    i = text.find("\n" + IFS.IDENTITY_END)
    return text if i < 0 else text[:i].rstrip() + "\n"


# MOVED self/ -> issues/ 2026-08-15 (R198). It is the prologue to the issue
# graph — what an issue IS — not Self's own material, and R195 rules that
# self/* does not propagate into any prompt Block. issues/ already holds a
# non-TOML file (INDEX.md) and both scanners glob a strict node pattern
# ("*n[0-9][0-9][0-9][0-9].toml"), so a .md there is inert to them.
ISSUE_MODEL = ROOT / "issues" / "issue_model.md"
# `docs/issue_relationship_types.md` is NOT read here and has not been since the brief
# became generated. It is the engineer's document; parts get
# `issue_projection.issue_relationship_brief()`. The constant that used to point at it was
# left behind when part 3 changed, and a path constant nothing reads is how a
# reader concludes the file is still in the prompt.


def build_briefing(chosen: list[str]) -> tuple[str, list[str]]:
    """CONSTRUCTED per circle, at its initialisation — the ONLY way
    circle_objectives (BLOCK 2) is built, for every circle, live or sandbox
    alike. Retired 2026-08-11: `self/circle_briefing.md` no longer exists.
    Up to five parts, in order (part 5 added 2026-08-15, R184 — the TOPIC
    register's open topics, coordinator/topics.py, "" while the register is
    empty; everything after part 2 was excluded under --minimal, retired
    R360):

        1  issues/issue_model.md    the prologue. What an issue IS. The one
                                    part present unconditionally.
        2  ## Issues                RICH — see below. Working-set aware: id, name and
                                    detail for each chosen node, and for each
                                    a live edge reaches.
        3  relations, BRIEF         The
                                    five type names glossed, and the live
                                    edges. Generated by issue_projection, never
                                    transcribed from docs/issue_relationship_types.md.
        4  issues_narrative.md      RETIRED — B46, 2026-08-17. The
                                    hand-written account that predated the
                                    graph was retired 2026-08-14 once its
                                    remaining entries were migrated in
                                    (commit 16cd565) and never came back;
                                    the read-and-concatenate call site
                                    (issue_projection.narrative()) had
                                    returned "" on every live circle since
                                    and was dead code. Removed along with
                                    its docs/BNF.md production.

    THE ISSUES ARE RICH, the one shape now (project_working_set): blank
    working set — every live node via block(), label, provenance ("ruled by
    Self in <circle>" or "NOT YET RULED") and its absence clause; chosen
    working set — FOCUS nodes get full detail (description + absence +
    provenance + live edges), PERIPHERY nodes name + description only. A
    FLAT variant (uniform name + description, no provenance, no edges)
    served the --minimal baseline alone — ruled 2026-08-11 that live
    circles keep the richer detail — and retired with that mode (R360).

    `self/circle_briefing.md` is GONE, not merely unread. It was a generated
    intermediate — nightly synthesis wrote it, circle.py read it back — and
    every one of its sections was already sourced from a file that owns its
    own content (issue_model.md, the live issues/*.toml graph, and, at the
    time, issues_narrative.md — itself since retired, B46 2026-08-17). This
    reads what remains directly, the same move R133-137 made for best
    practices and better options: no projection step, no derivation, no
    file in between to go stale.

    THE PROLOGUE HAS A HOME. `## What is here` used to live only inside the
    old generated briefing — 1,838 characters of the issue model with no
    source of truth, which any regeneration would have destroyed. Self
    supplied it verbatim on 2026-08-03 and it is now a file.

    PART 3 IS GENERATED, NOT COPIED, FOR LIVE CIRCLES — new as of 2026-08-11.
    Live circles never carried a relations brief before (self/circle_briefing.md
    had no such section); build_briefing() gives them the one minimal circles
    already had (that mode itself lost it the same session, and retired R360)
    (see above). `docs/issue_relationship_types.md` was sent whole into
    circle_2026-08-03_2208 — 1,808 tokens, 31% of a part's prompt — and
    across 27 part statements not one edge type was named once. It is an
    engineer's document: file paths, an edge census, a bug history, a section
    called "Where the machinery is". It stays, for me. Live parts get
    `issue_projection.issue_relationship_brief()`: the five words glossed, and what is live.

    Fails CLOSED on a missing ISSUE_MODEL: a briefing assembled without the
    prologue is a different experiment wearing the same name. Parts 3 and 4
    are the exception — see above."""
    if not ISSUE_MODEL.is_file():
        raise RuntimeError(
            f"cannot build a briefing: {ISSUE_MODEL.relative_to(ROOT)} is "
            f"missing. The prologue, the issues and the relations are the "
            f"core of it; assembling without it is a different experiment")
    import issue_projection as IP
    # `chosen is None` IS `none` — finding 2's own answer, 2026-08-20, and
    # a different thing from `[]`. An empty list means "no FOCUS, project
    # the whole live graph"; None means the operator asked for NO ISSUES,
    # and this circle carries the prologue and nothing else. Collapsing
    # them would make `none` a synonym for blank, which is exactly the
    # distinction the ruled grammar draws.
    if chosen is None:
        issues, unknown = ("## Issues\n\n(None this circle. The graph was "
                           "deliberately not brought in.)", [])
    else:
        issues, unknown = IP.project_working_set(chosen)
    parts = [read_ro(ISSUE_MODEL).rstrip("\n"), "", issues.rstrip("\n")]
    # PART 3 — see this function's docstring. Part 4 (the narrative) was
    # retired whole, B46 2026-08-17 — see the docstring's part-4 note.
    # ...and `none` takes the relations brief with it: a brief about edges
    # between issues that are not here would describe nothing this circle
    # can see.
    if chosen is not None:
        parts += ["", "---", "", IP.issue_relationship_brief(chosen).rstrip("\n")]
    # PART 5 — the TOPIC register (R184, 2026-08-15): SYNTHESIS's unvetted
    # BLOCK 2 material, open topics only, newest-first within its window
    # (coordinator/topics.py). "" while the register is empty, so this
    # line changes no briefing byte until SYNTHESIS ships a writer.
    import topics as TOP
    top = TOP.block()
    if top:
        parts += ["", "---", "", top.rstrip("\n")]
    return "\n".join(parts) + "\n", unknown


def identity_tail(part: str) -> str:
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
    removing, and a rename in this exact lineage (`injured_soul` -> `soul`) would
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
    authored sentence is text rather than an exception."""
    declared = R.IDENTITY_TAILS.get(part, "")
    ctx = R.read_context(part)
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


# THE FOUR BLOCKS, NAMED SEMANTICALLY. Ruled 2026-08-06.
#
# Self: *"The labels we have are ambiguous, not semantic rich"*, then:
# *"Change label circle_practices to circle_identity on the principle that the
# identity of circling is expressed as its practices. Identities are stable but
# evolve through dreaming (per part) and synthesis (circle wide practices).
# Objectives are per-circle and evolve by carrying information that has not
# (yet) stabilized into circle or part identity into future circles."*
#
#   circle_identity    who we are, and what we do
#                      process_core (the hard rules
#                      and pass protocol now live
#                      there too, folded in 2026-08-11)
#                      + best practices. SHARED.
#   circle_objectives  what we are doing here.
#                      issues OWED, better options
#                      AVAILABLE. SHARED.
#   part_identity      who you are. long_term +
#                      relationships. PER PART.
#   part_objectives    what has not stabilised into
#                      either identity yet: your ask
#                      fragments, anything addressed
#                      to you alone. PER PART,
#                      UNCACHED.
#
# ONE ORDER NOW. `ORDER_MINIMAL` is gone: --minimal differs only in CONTENT.
# The two constants encoded a distinction that no longer exists, and keeping
# both would have outlived it.
ORDER = ("circle_identity", "circle_objectives",
         "part_identity", "part_objectives")


def block_order() -> tuple[str, ...]:
    """The emitted block order, named. `prompt_capture` labels by this and
    the leak guard finds a block by NAME, so a reorder cannot silently
    mislabel a capture. (The orders were unified 2026-08-06; the ignored
    `minimal` parameter left with the mode, R360.)"""
    return ORDER


def system_blocks(part: str, core: str, shared) -> list[dict]:
    """Three cache breakpoints plus one uncached tail.

        1. circle_identity    rarely; a practice
                              between circles
        2. circle_objectives  between circles
        3. part_identity      nightly (dreaming)
        (the 4th breakpoint is the rolling one on
         the last message block)

    A breakpoint must sit on the last block IDENTICAL across the requests
    meant to share a cache, so the varying transcript stays strictly after
    all three — and blocks 1 and 2 are now identical across all seven parts,
    which is what the 2026-08-06 restructure bought.

    **MEASURED BEFORE AND AFTER, on the same tree:**

        shared prefix, filtered briefing   6,976 chars
        shared prefix, split briefing     41,655

    The old live order put a per-part block second, so the shared prefix was
    `process_core` and nothing else — seven cache writes of a 34,000-character
    briefing to withhold at most 136 characters per part. Those 136 characters
    are now block 4, which is uncached and costs nothing to vary.

    `shared` is the tuple `(objectives, practices, part_practices)` from
    `shared_block` — objectives is `build_briefing`'s constructed text
    verbatim, practices and part_practices read directly from
    self/best_practices.toml (R134)."""
    base = ROOT / "parts" / part
    lt = strip_to_identity(strip_settled(read_ro(base / "long_term.md")))
    who = f'# You are the "{PART_TAGS[part]}" part ({part}).\n\n'
    # THE FOUR-BLOCK <part_identity>. ruled 2026-08-12 (see docs/Circle
    # BNF.txt): long_term.md ALWAYS — settled, may evolve slowly or by
    # hand; the mid_term distillate ALWAYS ATTEMPTED — evolves with
    # every synthesis; relationships.md now its OWN always-included
    # block (raw passthrough — real distillation is future work) rather
    # than a missing-mid_term fallback; part_practices appended below,
    # in every branch.
    #
    # BLOCK 3 CARRIES THE DISTILLATE WHERE ONE EXISTS. Ruled 2026-08-07:
    # *"I far prefer these appending part-identity to including
    # relationship or dreaming content unprocessed."* Measured: of
    # 26,290 characters of the Child's dream-and-relationship material,
    # about 1,400 were actionable. The rest is episode, provenance and
    # state-formula — why mid_term.py's derivation exists at all, and
    # why the historic dream corpus moved out of long_term.md into
    # dreams.toml rather than reaching a part directly (same date).
    #
    # THE `## Dreamt` SECTIONS REACH A PART ONLY THROUGH HERE. R112 sent
    # dreams to short_terms per the 2026-08-03 ruling and nothing read a
    # short_term, so they were inert until `mid_term` made them a source.
    import mid_term as MT
    distilled, _why = MT.block(part)
    # B44: the cutoff BLOCK 3's settled remember window and BLOCK 4's
    # tail split on — this part's identity as of its OWN last mid_term
    # refresh. None (absent/legacy mid_term) means nothing is settled
    # yet; remember.project_tail()'s own cutoff=None branch degrades
    # to the pre-B44 whole-register view.
    cutoff = MT.refresh_cutoff(part)
    import remember as _RM
    identity = who + f"## Your identity\n{lt}"
    # R303's tail — what the live case adds: `## The Soul`'s operative
    # half used to
    # reach all seven parts from BLOCK 1, opening "If you are the Soul:".
    _it = identity_tail(part)
    if _it.strip():
        identity += "\n\n" + _it.strip()

    # THE INSTRUMENT PROFILE, TO THE ONE PART THAT CARRIES THE ROOTS — ruled
    # 2026-08-27, the same day it was first built into BLOCK 1 and objected
    # to there. Self: BLOCK 1 and 2 are Circle Identity and Objectives, so a
    # profile in BLOCK 1 lets *"every part get to know Self intimately, which
    # is in opposition to the nature of a part"*. The place is the Soul's own
    # BLOCK 3, *"isolating it from group knowledge and giving the Soul a
    # unique role: carrier of the unseen roots of the self"*.
    #
    # This is R303/R304's rule applied to new content rather than re-learned:
    # material belonging to ONE part goes to BLOCK 3, and only what all seven
    # need belongs in BLOCK 1. The Soul was the occasion of that ruling too.
    #
    # AND IT IS THE MEASURED-EFFECTIVE FORM. parts/soul/part.toml records the
    # measurement that decided the render sentences: a planted sentence came
    # back 20/25 from FIRST-PERSON IDENTITY material against 1/25 from
    # third-person catalogue material. The BLOCK 1 version was third-person
    # catalogue prose — the losing form, in the losing block.
    #
    # WHICH PART, FROM THE DATA, NEVER FROM HERE. instruments.block(part)
    # returns ε unless the register's own [block] names this part. A part
    # NAME typed into shipped mechanism is the B29/R123 class two rulings
    # were spent removing, and keying on the directory means a rename
    # follows by itself — the same reasoning identity_tail() above uses.
    import instruments as INST
    _prof = INST.block(part)
    if _prof.strip():
        identity += "\n\n" + _prof.strip()

    if distilled.strip():
        identity += f"\n\n{distilled.strip()}"
    # RELATIONSHIPS ARE NO LONGER PROJECTED, DIRECTLY OR INDIRECTLY. R302,
    # 2026-08-22: "unwire part relationships from the prompt context. leave it
    # unconsumed for now." Then, same day, on review: "is part_relationships
    # in the prompt under any option? ... I do not want it in the prompt
    # context in any block."
    #
    # THE REGISTER AND ITS SEVEN FILES ARE UNTOUCHED, BUT NO LONGER WRITTEN,
    # as of 2026-08-22 — inter_circle.py's DREAMING call was patched to stop
    # asking for or staging a converged relationships document (no
    # part_relationships.toml write, and no LLM attention spent on one). See
    # coordinator/inter_circle.py's own module docstring, "part_relationships
    # IS INERT."
    #
    # NO LONGER READ EITHER, DIRECT OR INDIRECT. mid_term.py's sources()
    # (PROMPT bumped v6 -> v7 the same day) dropped this register as an input
    # to the BLOCK 3 distillate below (`distilled` — see mid_term.block()
    # upstream), so it is no longer folded, re-summarized, into BLOCK 3 when
    # the distillate refreshes. A repo-wide sweep confirms no live code under
    # coordinator/, ui/ or memory/ imports part_relationships or calls RELS.*
    # any more, outside this register's own module and its tests.
    #
    # WHY THE DIRECT PROJECTION WAS CUT FIRST, MEASURED. A sentence that
    # appears nowhere in the tree was planted into a part's block 3 and the
    # part was asked a question that could only be answered from it — the
    # Judge addressing the Child about how the two of them work:
    #
    #     planted in the IDENTITY material    recalled 20/25
    #     planted in THIS section             recalled  1/25
    #     this section MOVED TO THE FRONT     recalled  2/25   (position ruled out)
    #     not planted                         recalled  0/25
    #
    # Same sentence, same block, same question. It is the section, not the
    # depth: relationship material did not reach a part's speech wherever it
    # sat. Meanwhile 100% of those replies DID name a specific arrangement
    # with the Judge — invented fresh each time, while the record of it sat in
    # the prompt unread. 4,581 chars x 7 parts, every circle, bought and never
    # used.
    #
    # Each part's LAST relationships record, from before the write was
    # patched out, still stands on disk. A standing item is in NEXT.md:
    # RETIRE the seven frozen files, or LEAVE AS IS.

    objectives, practices, part_practices = shared

    # BLOCK 1 — the circle's identity. Used to be process_core + STANDING +
    # practices; STANDING is gone (2026-08-11) — its non-redundant content
    # (the hard rules, the pass protocol, the bracket/Scribe note) moved into
    # process_core.md itself, and its one dynamic line (naming Self) was
    # simply dropped, because process_core.md already said the same thing.
    # A part's identity block is now exactly two sources, not three.
    ident = core
    if practices.strip():
        ident += "\n\n" + practices.rstrip("\n")

    # THE INSTRUMENT PROFILE IS NOT HERE, AND WAS FOR ONE DAY. It landed in
    # BLOCK 1 on 2026-08-27 and moved to BLOCK 3 the same day, on Self's
    # objection: BLOCK 1 is the CIRCLE's identity, so a profile here tells
    # all seven parts who Self is intimately, *"which is in opposition to the
    # nature of a part"*. See instruments.block() and identity_tail().

    # BLOCK 3 — a ratified, THIS-part-addressed practice joins here, not
    # block 4 (R134, 2026-08-11): it is stabilised content, the same
    # standing as the mid_term distillate above it, not a not-yet-settled
    # thread. Appended after identity is fully built.
    if part_practices.strip():
        identity += "\n\n" + part_practices.rstrip("\n")

    # REMEMBER GUIDANCE IS NO LONGER APPENDED HERE. R-NEW, 2026-08-22: it is a
    # coordinator capability described in BLOCK 1, in process_core.md beside the
    # `[remember: ...]` annotation it governs — not a per-part fact. It had been
    # 1,518 bytes IDENTICAL FOR ALL SEVEN sitting in the one block that exists to
    # differ per part, which is the same shape as content-for-one-part reaching
    # everyone (E09), read in the mirror. What remains below is the part's OWN
    # remembered content, which is per-part and belongs here.
    #
    # Nothing about what a part is SENT changed — only which block carries
    # the standing guidance, and it is now sent once per circle instead of
    # seven times.

    # BLOCK 3's mechanical remember window (B44, RULED 2026-08-15 —
    # docs/INTER_CIRCLE_DESIGN.md "Projection", R170 "mechanical
    # selection... no LLM call, no new artifact"): everything this part
    # had on file as of its OWN last mid_term refresh. Reuses remember.py's
    # existing recency-window + BUDGET mechanism wholesale — never routed
    # through mid_term's own LLM derivation — and rides inside BLOCK 3's
    # existing cache boundary for free. Placed after the guidance that
    # governs it, matching REMEMBER_GUIDANCE -> the record it produced.
    settled, _swhy = _RM.block_settled(part, cutoff)
    if settled.strip():
        identity += "\n\n" + settled.strip()

    # BLOCK 4 — everything per part that has not stabilised. Uncached, so it
    # may differ freely; that is the point of putting it last.
    tail_parts = []
    # ASK FRAGMENTS (asks_extract.py) lived here 2026-08-06 through
    # 2026-08-12, then RETIRED — superseded by REMEMBER LIFECYCLE just
    # above, which gives a part the same "own accumulating BLOCK 4 material"
    # without a separate derivation pipeline. See docs/BNF.md.
    rtext, _rnote = _RM.block_tail(part, cutoff)
    if rtext.strip():
        tail_parts.append(rtext.strip())
    tail = "\n\n".join(tail_parts) if tail_parts else PART_OBJECTIVES_EMPTY

    seq = [ident, objectives, identity]
    return [{"type": "text", "text": t, "cache_control": cc()} for t in seq] \
        + [{"type": "text", "text": tail}]


# A block must never be empty — the API rejects an empty text block, and a
# part with no open material would otherwise fail to open the circle.
PART_OBJECTIVES_EMPTY = (
    "# Your objectives\n\nNothing is carried forward for you this circle."
)


# ------------------------------------------------------------------ briefing
# `split_briefing()` and `apply_working_set()` REMOVED 2026-08-11: both
# existed to filter or re-slice a rendered self/circle_briefing.md, and that
# file is gone. `build_briefing(chosen)` now IS circle_objectives, built
# directly from source files at prompt-assembly time — there is nothing
# left to split, and no rendered text to re-slice by working set (chosen
# goes straight into build_briefing instead).
#
# BEST PRACTICES REMOVED FROM PROMPT ASSEMBLY 2026-08-11 (R134), separately:
# the old per-part extraction here used to key on a "best practices" section
# and a `**<Addressee>** —` text marker — both retired the same ruling, in
# favour of self/best_practices.toml's own `addressee` field, read
# directly by system_blocks() via check_best_practices.broadcast_block()/
# narrowcast_block(). See ifs_model.py for the matching cleanup.

# `strip_resolved()` REMOVED 2026-08-05. It dropped a `## Resolved` heading
# from open_concerns.md before the file reached a part. Both halves of its
# job are gone: the file no longer reaches a part at all (R082), and
# `resolved` is a field of a TOML record rather than a position after a
# heading. Its reasoning — that a file called open_concerns must not spend a
# fifth of itself on closed ones — is preserved in R-record and in
# strip_settled(), which still applies it where it still bites.


def load_shared() -> str:
    """process_core.md alone. Concerns and the briefing text were the other
    two things this used to return.

    Concerns: the OC register (self/open_concerns.toml, concerns.py) is
    RETIRED outright, 2026-08-13 — vestigial: it had already been reduced,
    2026-08-05, to something Self deployed by speaking it himself, directly,
    into the circle pane rather than an ambient prompt channel, and nothing
    used that deployment path since. No successor; Self speaks whatever he
    wants directly, as any other statement.

    Briefing: self/circle_briefing.md is GONE (2026-08-11) — circle_objectives
    is built directly by build_briefing(chosen), not read from a file here.

    HERE, not ROOT: the rulebooks moved to coordinator/ on 2026-08-08."""
    return read_ro(HERE / "process_core.md")


def shared_block(part: str, briefing: str):
    """-> (blocks, note). `blocks` is the tuple `system_blocks` destructures.

    `part` is the DIRECTORY name (PART_TAGS[part] is its display Tag),
    matching every other caller in this module. `briefing` is
    build_briefing's constructed circle_objectives text — identical in shape
    for every circle now, live or sandbox; there is no file-derived variant
    left to distinguish.

    PRACTICES DO NOT COME FROM `briefing` (R134) — coordinator/
    best_practices.toml is read directly, via check_best_practices.py's own
    broadcast_block()/narrowcast_block(), the same lazy-import pattern
    remember.block()/mid_term.block() already use elsewhere in this
    file. (--minimal suppressed them entirely, until R360 retired that
    mode with the sandbox practice default.)"""
    import check_best_practices as BPX
    prac = BPX.broadcast_block()
    mine = BPX.narrowcast_block(PART_TAGS[part])
    note = (f"objectives {len(briefing):,} + practices {len(prac):,} shared; "
            f"{len(mine):,} to block 3")
    return ((briefing, prac, mine), note)


# ------------------------------------------------------------------ transcript view
def render_messages(part: str, transcript: list[dict], closing: str | None = None) -> list[dict]:
    """Reconstruct THIS part's view from the single canonical transcript: its own
    lines become assistant turns, everyone else's become user turns. Consecutive
    same-role turns are merged so roles alternate (API requirement) and the block
    count stays well inside the 20-block cache lookback window."""
    msgs: list[dict] = []
    for e in transcript:
        # RECORDED, BUT NEVER IN THE ROOM — transcript_store.withheld().
        # RULED 2026-08-04: "Recorded to the circle, but not sent to parts."
        # A graph ruling is not a statement to the room; nor, since
        # 2026-08-18, is a turn that was ENTIRELY a [remember: ...]. Both
        # reach the transcript file and neither enters any part's message
        # list, so neither can perturb the cached prefix either.
        if withheld(e):
            continue
        role = "assistant" if e["speaker"] == part else "user"
        # Listeners must see the addressing. Rendering a statement as bare
        # "Part: ..." when the transcript records "[Part] [To: Child]: ..."
        # would desync what the parts perceive from the durable record — and
        # being addressed is what a part answers.
        if role == "assistant":
            text = e["text"]
        else:
            addr = f' [To: {e["to"]}]' if e.get("to") else ""
            text = f'{e["display"]}{addr}: {e["text"]}'
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n\n" + text
        else:
            msgs.append({"role": role, "content": text})
    if not msgs or msgs[0]["role"] == "assistant":
        msgs.insert(0, {"role": "user", "content": "(the circle opens)"})
    tail = closing or "(the circle comes to you — speak, or reply [pass])"
    if msgs[-1]["role"] == "assistant":
        msgs.append({"role": "user", "content": tail})
    else:
        msgs[-1]["content"] += "\n\n" + tail
    last = msgs[-1]
    last["content"] = [{"type": "text", "text": last["content"], "cache_control": cc()}]
    return msgs
