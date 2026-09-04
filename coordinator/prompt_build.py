#!/usr/bin/env python3
"""
prompt_build.py — the prompt's construction: the identity read-layer,
circle_objectives (build_briefing), the four-block
assembly (system_blocks and kin), and the transcript-to-messages view
(render_messages). Phase 2 stage 2 of the coordinator partitioning
(2026-08-16); until then all of it lived in circle.py. Verbatim move —
bodies and comments unchanged.

THE PAYOFF THIS STAGE EXISTS FOR: five live modules (circle_audit.py,
prompt_show.py, block_overlap_verify.py, midterms_project.py,
part_mid_term_manager.py) imported the whole 4,000-line orchestrator to build or
inspect prompts; they import this module now. part_mid_term_manager.py and this
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

import record_paths as _P
from transcript_store import circle_transcript_is_withheld   # the recorded-but-never-in-the-room test
from llm_client import CACHE_TTL   # prompt_cache_control_read()'s TTL — the transport owns it
import llm_client as _LC           # PROVIDER_IMPL — prompt_cache_control_read()'s wire form is the
                                   # provider's, stage 2 (R382)
import setting_manager as SET             # the length rule's two numbers

# THE FOUR BLOCKS' OWN ASSEMBLERS, 2026-09-02 (docs/CIRCLE_TYPES_DESIGN.md).
# Re-exported by NAME, unchanged, so every existing external caller
# (30+ for load_shared, 50+ for build_briefing, plus read_ro/strip_settled/
# strip_to_identity/identity_tail/PART_OBJECTIVES_EMPTY's own callers —
# grep-confirmed before this move) keeps working via `prompt_build.
# load_shared`/`prompt_build.circle_briefing_build`/etc. or a
# `from prompt_build import ...` exactly as before. The real logic now
# lives exclusively in these four files; nothing here decides what any
# block contains any more.
import group_context as _GC
import group_attention as _GA
import role_context as _RC
import role_attention as _RA
# read_ro/strip_settled/strip_to_identity/identity_tail moved ONE HOP
# FURTHER, 2026-09-02: role_context.py -> parts_prompt_projection.py, on the same
# "pull the parts/<p>/* read out" instruction group_context.py/
# group_attention.py/topic_prompt_projection.py already answered for their own
# registers. The alias below still resolves; nothing importing
# prompt_build.record_ro_read (part_mid_term_manager.py, at its own module level) needed to
# change, since it never knew or cared which file actually held the body.
import parts_prompt_projection as _PP
# ISSUE_MODEL moved the SAME HOP FURTHER, same day: group_attention.py ->
# memory/issue_prompt_projection.py, on direct instruction — the prologue is
# issue-graph material, not this assembler's just because it used to read
# the file directly. Its own alias below resolves the same way.
# UNLIKE THE OTHER THREE (all in coordinator/), this one crosses into
# memory/ — group_attention.py's own build_briefing() only ever imported
# it LAZILY, at call time, never at its own module top, and that was
# deliberate: memory/ is not guaranteed on sys.path yet at prompt_build.py's
# import time, only by the time a circle actually opens. quote_verify.py/
# circle.py/vetting.py resolve the same need the same way — inserting
# memory/ themselves rather than assuming an earlier import already did.
import sys as _sys
_sys.path.insert(0, str(_P.ROOT / "memory"))
import issue_prompt_projection as _IP                                # noqa: E402
# EACH ALIAS CARRIES ITS OWNER'S NAME, 2026-09-03 (B99's residue, the estimate's item 1g).
# They were load_shared/build_briefing/read_ro/strip_settled/strip_to_identity/
# identity_tail/role_context_block/finalize_block4 — the spellings stage 19 retired at
# their owners, kept alive here by the facade. The facade itself stands: this file is
# the one executor of all four blocks, asked for directly. An alias that renames what it
# re-exports is a second name for one fact, which is what the sweep was for.
group_shared_read = _GC.group_shared_read
circle_briefing_build = _GA.circle_briefing_build
ISSUE_MODEL = _IP.ISSUE_MODEL
record_ro_read = _PP.record_ro_read
part_settled_strip = _PP.part_settled_strip
part_identity_strip = _PP.part_identity_strip
part_identity_tail_render = _PP.part_identity_tail_render
PART_OBJECTIVES_EMPTY = _RA.PART_OBJECTIVES_EMPTY
# role_context.part_context_block_render()/role_attention.part_attention_finalize() ADDED 2026-09-02: the two
# remaining real-code call sites that reached an assembler directly instead
# of through prompt_build.py (circle.py's own Phase 2 for BLOCK 4, via a
# local `import role_attention as RA`; midterms_project.py's diagnostic
# read of a part's BLOCK 3 identity, via `import role_context as RC`) —
# asked directly to make prompt_build.py the one executor of all four.
# prompt_part_assemble() below already calls _RC.part_context_block_render/_RA.part_attention_stage internally for
# the normal one-part-at-open assembly; finalize() is BLOCK 4's own later,
# topic-dependent SECOND pass (role_attention.py's own docstring), which
# prompt_part_assemble() never ran — this is its first re-export, not a duplicate
# of one prompt_part_assemble() already had.
part_context_block_render = _RC.part_context_block_render
part_attention_finalize = _RA.part_attention_finalize

# PART_TAGS — no internal use here since the block-3/4 move, 2026-09-02, but
# real external callers still reach it as `prompt_build.PART_TAGS`
# (block_overlap_verify.py, part_mid_term_manager.py, midterms_project.py, prompt_show.py,
# circle_audit.py, all `import prompt_build as C` then `C.PART_TAGS`).
PART_TAGS = _P.PART_TAGS

HERE = pathlib.Path(__file__).resolve().parent

# THE LENGTH RULE, ruled by the operator 2026-08-28, in his own sentence:
# "aim for 60 words or fewer and never exceed 150; reformulate down to less
# than 150 in all cases." process_core.md carries that sentence with these two
# numbers as placeholders, and load_shared() puts them in.
#
# ONE SOURCE FOR BOTH PLACES THE NUMBER APPEARS, which is the actual fix. The
# rulebook said "never exceed 100" while circle_rounds.py's truncation retry told a
# part to "speak in UNDER 150 words", and process.md said a stale 100 beside a
# stale ceiling of 600 — three documents, three literals, no way for any of
# them to notice the others. circle_rounds.py imports LENGTH_MAX_WORDS from here now,
# so the room's rule and the retry's cannot disagree again.
#
# NOTHING COUNTS WORDS. The rule is advisory and always has been; no code in
# the statement path measures one. Measured 2026-08-28 across the 374 part
# statements in the parseable corpus, all of which ran under the previous
# "aim 120, never exceed 200": median 98 words — 0.82x the aim — with 2.1%
# over the cap. An advisory rule demonstrably shapes these parts, which is
# why the operator's ruling is that never enforcing it is fine.
LENGTH_AIM_WORDS = SET.setting_value_read("statement_aim_words", 60)
LENGTH_MAX_WORDS = SET.setting_value_read("statement_max_words", 150)


def prompt_cache_control_read() -> "dict | None":
    """The wire form of "this block is stable, cache it" — THE PROVIDER'S,
    since stage 2 (R382). `{"type": "ephemeral", "ttl": ...}` is Anthropic's
    spelling of a request this project makes in its own terms, and it was the
    most vendor-specific thing left in prompt assembly.

    A provider with no prompt cache returns None; the caller then sends no
    marker at all and the Meter's cache columns read zero, which is correct
    rather than broken.

    THE TTL IS THE OPERATOR'S `cache_ttl` TUNING when set (`/settings-update
    cache_ttl 5m`), else llm_client.CACHE_TTL — since 2026-09-04. Until then
    this line sent the constant and the knob, accepted and stored, changed
    nothing on the wire (audit-register 2026-09-04, #7)."""
    impl = _LC.PROVIDER_IMPL
    return impl.cache_control(impl.cache_ttl(_LC.TUNING, CACHE_TTL))


# read_ro/strip_settled/strip_to_identity/identity_tail moved to
# parts_prompt_projection.py, 2026-09-02 — re-exported above by name.


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


def system_blocks(ident: str, objectives: str, identity: str, tail: str) -> list[dict]:
    """Three cache breakpoints plus one uncached tail — pure packaging, now.
    Building any of the four texts is group_context.py's (BLOCK 1, core and
    practices both, since 2026-09-02), group_attention.py's (BLOCK 2),
    role_context.py's (BLOCK 3) or role_attention.py's (BLOCK 4) job; this
    function only decides where the cache breakpoints go.

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

    `tail` must never be empty — the API rejects an empty text block, and a
    part with no open material would otherwise fail to open the circle;
    role_attention.part_attention_stage() already applies PART_OBJECTIVES_EMPTY."""
    seq = [ident, objectives, identity]
    return [{"type": "text", "text": t, "cache_control": prompt_cache_control_read()} for t in seq] \
        + [{"type": "text", "text": tail}]


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
# favour of self/best_practices.toml's own `addressee` field, read directly:
# process_core_prompt_projection.group_best_practices() inside group_context.
# block() (BLOCK 1), parts_prompt_projection.part_practices_render() inside
# role_context.part_context_block_render() (BLOCK 3) -- moved out of check_best_practices.py,
# 2026-09-02, to sit with their own consumers rather than staying paired
# with each other. See ifs_model.py for the matching cleanup.

# `strip_resolved()` REMOVED 2026-08-05. It dropped a `## Resolved` heading
# from open_concerns.md before the file reached a part. Both halves of its
# job are gone: the file no longer reaches a part at all (R082), and
# `resolved` is a field of a TOML record rather than a position after a
# heading. Its reasoning — that a file called open_concerns must not spend a
# fifth of itself on closed ones — is preserved in R-record and in
# strip_settled(), which still applies it where it still bites.


def prompt_part_assemble(part: str, core: str, briefing: str) -> tuple[list[dict], str]:
    """The full per-part block assembly — replaces the old shared_block() +
    system_blocks() two-step dance. shared_block() bundled BLOCK 2's
    already-built text together with BLOCK 1's and BLOCK 3's practices for
    caller convenience alone; there was no computational relationship
    between them. Ruled 2026-09-02: "this stage output should be
    detangled." This function calls each block's own exclusive module
    directly and packages the result; nothing here decides what any block
    contains — including BLOCK 1's own practices merge, moved into
    group_context.group_context_block_render() the same day, closing the one gap left after the
    first pass (that pass folded the merge in here instead, one file short
    of the exclusive-assembler shape BLOCK 3 already had).

    `part` is the DIRECTORY name, matching every other caller in this
    module. `core` is group_context.group_shared_read()'s text (once per
    circle) — group_context.group_context_block_render() merges it with the practices
    broadcast; this function never touches best_practices.toml itself
    any more. `briefing` is build_briefing's constructed circle_objectives
    text (once per circle).

    PRACTICES DO NOT COME FROM `briefing` (R134) — self/best_practices.toml
    is read directly, inside each block's own module: group_context.group_context_block_render()
    (BLOCK 1), role_context.part_context_block_render() (BLOCK 3).

    Returns (the four packaged blocks, a diagnostic note for
    prompt_capture's manifest — unchanged shape from shared_block()'s own
    note)."""
    ident, prac_len = _GC.group_context_block_render(core)
    identity, cutoff, mine_len = _RC.part_context_block_render(part)
    tail = _RA.part_attention_stage(part, cutoff)

    note = (f"objectives {len(briefing):,} + practices {prac_len:,} shared; "
            f"{mine_len:,} to block 3")
    return system_blocks(ident, briefing, identity, tail), note


# ------------------------------------------------------------------ transcript view
def prompt_messages_render(part: str, transcript: list[dict], closing: str | None = None,
                    *, recall: str | None = None) -> list[dict]:
    """Reconstruct THIS part's view from the single canonical transcript: its own
    lines become assistant turns, everyone else's become user turns. Consecutive
    same-role turns are merged so roles alternate (API requirement) and the block
    count stays well inside the 20-block cache lookback window.

    `recall` is the ONE private addition to a part's view (R402): the latest
    <recall_result> answered for THIS part, appended to the tail — never a
    prompt block (blocks are static per circle, capture-verified), never
    another part's request, and absent from the /close short_term ask, which
    passes no recall and is how "expires at /close" is enforced. It rides at
    the very end, so the shared transcript prefix caches exactly as before."""
    msgs: list[dict] = []
    for e in transcript:
        # RECORDED, BUT NEVER IN THE ROOM — transcript_store.circle_transcript_is_withheld().
        # RULED 2026-08-04: "Recorded to the circle, but not sent to parts."
        # A graph ruling is not a statement to the room; nor, since
        # 2026-08-18, is a turn that was ENTIRELY a [remember: ...]. Both
        # reach the transcript file and neither enters any part's message
        # list, so neither can perturb the cached prefix either.
        if circle_transcript_is_withheld(e):
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
    if recall:
        tail = recall + "\n\n" + tail
    if msgs[-1]["role"] == "assistant":
        msgs.append({"role": "user", "content": tail})
    else:
        msgs[-1]["content"] += "\n\n" + tail
    last = msgs[-1]
    last["content"] = [{"type": "text", "text": last["content"], "cache_control": prompt_cache_control_read()}]
    return msgs
