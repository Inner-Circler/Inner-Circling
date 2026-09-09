#!/usr/bin/env python3
"""
part_dreaming.py — DREAMING: one PART's pass over the circle that just closed.

MOVED OUT OF inter_circle.py, 2026-09-03 (cohesion re-homing stage 11, NEXT.md B99; the
names are Q-D's — part_dreaming for the per-part pass, circle_synthesis for the circle-wide
one). inter_circle.py keeps the DRIVER (circle_process: the marker, the capture, the seven
calls in parallel, the transaction, the commit, the diagnostic); this module is what one
part's pass IS. Every function below is the verbatim body it had there; only the file moved.

    DREAMING_PROMPT_V1   the pass's prompt — versioned code, never a payload
    DREAM_MAX_TOKENS     its cap (settings-overridable)
    _call                the one call every pass makes, through the transport; circle_synthesis
                         and the driver's diagnostic read it here (PD._call), and the probes
                         rebind it here
    _report_chars        the dev-mode footprint line every call reports through
    circle_capsule_build   ONE call per circle (never per part) — the shared room capsule
                         part_dream()'s prompt reads beside a part's own lines (R451, D86 a,
                         2026-09-04: the per-part Dreaming input; docs/MEMORY_DESIGN.md)
    part_dream            the pass: a PAYLOAD, writes nothing
    part_dream_grounding_check   B91 (2026-09-04): is the MEMORY grounded in this part's own
                         material? SUSPECT notes, never a refusal, never a content change

RENAMED AT THE MOVE (R436, R442 — 2026-09-03), the class word first, the body
untouched: dream_one -> part_dream. The _private names are unchanged.

Design: docs/INTER_CIRCLE_DESIGN_V2.md (DREAMING); the salience/chain rules are DESIGN_V2's and
R358's; R248's reconstruction mark is read here and nowhere else.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import remember_manager as RM                                          # noqa: E402
import part_mid_term_manager as MT                                          # noqa: E402
import part_roster as R                                             # noqa: E402
import short_term_manager as STM                               # noqa: E402  the record's one reader (B96)
import command_surface as CS                                   # noqa: E402  dev_mode,
                                                               # attribute access only
import llm_client as LC                                        # noqa: E402  the transport
import LLM_response_disassembler as RD                         # noqa: E402  every read
                                                               # of a reply (2026-09-02)
import setting_manager as SET                                         # noqa: E402
import transcript_store as TS                                  # noqa: E402  the one parser
                                                               # (B91, 2026-09-04)
from record_paths import ROOT, record_dir                             # noqa: E402

# RAISED 2026-08-21 (the operator: "raise the caps as you suggest"), after the
# lab circle 2026-08-21_1139: child and mourner stopped at max_tokens=4,000 with
# only ~4.5k chars of visible reply. A probe the same day showed why —
# claude-sonnet-5 THINKS ADAPTIVELY BY DEFAULT (a bare messages.create with no
# `thinking` parameter returned content blocks ['thinking', 'text']), and its
# thinking tokens COUNT AGAINST max_tokens. The visible document is the same
# size it always was; the budget it shares is not. 4,000 was "proven
# sufficient, 7/7 parts" only while the thinking stayed small.
DREAM_MAX_TOKENS = SET.setting_value_read("dream_max_tokens", 8000)    # was 4000 — see above

# B91, 2026-09-04: the grounding heuristic's threshold — how many distinct
# content words a spoken part's MEMORY must share with its own lines before
# the run report stops calling it SUSPECT. THE NUMBER IS CLAUDE'S READING,
# not a ruling: 3 is the smallest count that a memory paraphrasing one of
# the part's own sentences clears and a memory about another part's moment
# usually does not. Tunable through the settings register; below
# system_unique_home_verify's MIN_NUMBER, so no shared-fact question arises.
DREAM_GROUNDING_MIN_OVERLAP = SET.setting_value_read("dream_grounding_min_overlap", 3)

# ---------------------------------------------------------------- prompts
# VERSIONED CODE CONSTANTS (docs/INTER_CIRCLE_DESIGN_V2.md) — the chain and
# format mechanics live here, never in a payload. One conformance against
# the ICD's committed text, flagged to its owner rather than silent: the
# "emit no other text at column 0" line is DROPPED — a self.md replacement
# CONTAINS column-0 `## ` headings, so the parser below splits on the exact
# header lines instead, each required once, in order.
#
# PART_RELATIONSHIP DROPPED, 2026-08-22 — see inter_circle's own module
# docstring, "part_relationships IS INERT." DREAMING asks for, and parses,
# MEMORY alone now.

DREAMING_PROMPT_V1 = """\
You are {part}'s dreaming pass for the circle that just closed ({ot}).

Below: your own identity as the circle sees it (your distillate); your own lines from the
closed circle — every statement you made and every line another part addressed to you,
verbatim, in original order, each with the one line said just before it kept for reply
context; a short shared capsule of what else happened in the room, the same words every
part reads; your own short_term for it, if you spoke; and — if one exists — the most
recent memory in your own chain (a note your dreaming pass left for you last time,
including how charged it was, if you said so).

Write only about what YOU said or experienced. If no short_term for you appears above, you
did not speak this circle; nothing above is yours to claim in your own voice, however
vivid, and MEMORY should be empty.

Write AT MOST ONE memory to carry forward to your own next circle. This is not a
summary of the circle — it is a note from you, to your future self, in your own voice,
about what to hold going into the next one. If a prior memory exists below, either
continue it (reference what it said, extend it) or let it stand and write nothing new
— a memory you choose not to change is not a failure. Keep it under {cap} characters.

OUTPUT FORMAT, exactly. Section headers, each alone on its own line, at column 0,
spelled exactly as shown. Print MEMORY even when it is empty — the header and nothing
under it. Print SALIENCE whenever MEMORY is not empty; omit it entirely (no header at
all) when MEMORY is empty. Print RESOLUTION only when it applies.

MEMORY
    Either one memory as plain prose, or — if you are continuing the prior memory
    rather than starting a new thread — a first line reading exactly "CONTINUES"
    followed by the memory. Empty if you are letting the prior memory stand.

SALIENCE
    Required whenever MEMORY is not empty. Your own sense of how charged this memory
    is — exactly one word: passing, notable, charged, or resolved. "passing" is
    ordinary; "notable" is worth a second look later; "charged" is something live and
    unsettled; "resolved" is a charge that has actually settled. Your own judgment,
    never a score anyone else assigns.

RESOLUTION
    Only if this memory resolves a prior memory you tagged "charged" — a line
    naming what settled. Leave the section entirely absent otherwise.
"""


# _truncate_at/_norm_len/_usage_dict/_merge_usage/_out_tokens MOVED to
# LLM_response_disassembler (truncate_at/norm_len/usage_counts/merge_usage/
# out_tokens), 2026-09-02 — reads of the reply, beside every other one.
# _usage_dict here was a second copy of llm_client's, with a different
# answer (ints only vs. the whole model_dump()); the disassembler keeps both
# under names that say which is which.
# --------------------------------------------------------- the room capsule
# ONE model call per circle, never per part (R451, D86 a, 2026-09-04) — every
# part reads the SAME capsule text; a difference between two parts' dreams
# can never be traced to a different capsule, because there is only one.
CAPSULE_CAP = SET.setting_value_read("dream_capsule_cap", 1200)   # chars, the shared paragraph
CAPSULE_MAX_TOKENS = SET.setting_value_read("dream_capsule_max_tokens", 1500)

ROOM_CAPSULE_PROMPT_V1 = """\
Below is the full transcript of one circle that just closed. Write ONE short paragraph, at
most {cap} characters, giving a plain, high-level account of what happened in the room:
what was discussed, what shifted, what stayed unresolved.

Every part reads this SAME paragraph as its only view of the room beyond its own lines and
what was said to it — write it so a part who did not see who said what can still follow the
shape of the circle, without repeating any one part's words verbatim and without singling
any one part out.

OUTPUT FORMAT, exactly. One section header, alone on its own line, at column 0:

CAPSULE
    Your paragraph, plain prose, under {cap} characters.
"""


def circle_capsule_build(ot: str, transcript: str, say=lambda _s: None) -> str:
    """The shared room capsule part_dream()'s prompt reads beside a part's own lines. Called
    ONCE by the driver, before the seven parallel part_dream() calls — never inside the pool,
    or seven capsules would race to be "the" one every part reads.

    BEST-EFFORT, by design: this is peripheral awareness, not identity material (the design's
    own words), so a failure here degrades to an empty capsule and a `say()` note rather than
    failing the whole dreaming pass over it."""
    system = ROOM_CAPSULE_PROMPT_V1.format(cap=CAPSULE_CAP)
    try:
        reply = _call(system, f"# Transcript of circle {ot}\n{transcript}",
                      CAPSULE_MAX_TOKENS, kind="capsule", record=True)
        sections, err = RD.message_sections_read(reply.text, ("CAPSULE",))
        if sections is None:
            say(f"  capsule: unparseable ({err}) — dreaming proceeds without one")
            return ""
        return sections["CAPSULE"].strip()
    except Exception as e:                                            # noqa: BLE001
        say(f"  capsule: call failed ({e}) — dreaming proceeds without one")
        return ""


def _block_stats(blocks: list[str]) -> list[tuple[str, int]]:
    """(label, char count) for each block in a prompt built from '# label'
    sections — DREAMING's and SYNTHESIS's user messages, each a list of
    such blocks joined with blank lines. The label is the block's own
    heading line; the count is the block's FULL length including it, i.e.
    exactly what reaches the model, not just the body under the heading."""
    out = []
    for b in blocks:
        label = b.splitlines()[0].lstrip("#").strip() if b else "(empty)"
        out.append((label, len(b)))
    return out


def _report_chars(say, who: str, chars: dict) -> None:
    """Every LLM call in this module reports its own footprint through
    here: prompt chars (system + user) and reply chars; per-block chars too
    when the prompt was built from named '# ' sections rather than one blob
    (DREAMING, SYNTHESIS — not DIAGNOSIS, whose user message is a single
    JSON report with no block structure).

    DEV-ON DETAIL, 2026-08-21 — the operator, on the close he watched: dev
    OFF prints the headers and the errors only; dev ON prints this per-call
    footprint as well. "<part>: done — …", "FAILED —", "SUSPECT —",
    "TRUNCATED —", the phase lines and the diagnosis are never gated — those
    are what a person waiting on a close needs to read. CS.dev_mode is read
    by attribute, as every reader of that flag must (command_surface.py)."""
    if not CS.dev_mode:
        return
    system, user, reply = chars["system"], chars["user"], chars["reply"]
    say(f"  {who}: prompt {len(system) + len(user):,} chars "
        f"(system {len(system):,} + user {len(user):,}) — "
        f"reply {len(reply):,} chars")
    stats = _block_stats(chars.get("blocks") or [])
    if stats:
        w = max(len(label) for label, _ in stats)
        for label, n in stats:
            say(f"      {label:<{w}}  {n:,} chars")


# ----------------------------------------------------------------- parsing
# parse_sections/items_of/_headings MOVED to LLM_response_disassembler
# (sections/items_of/headings), 2026-09-02, with the CONTINUES-prefix split
# part_dream() and circle_synthesise() each spelled for themselves (RD.message_continues).
# The HEADER TUPLES stay here: they are the prompts' own promise of what
# comes back, and the prompt is this module's.


# ------------------------------------------------------------------- model
# _client() MOVED to llm_client.stream_client_build(), 2026-08-28 (stage 1 of the
# provider socket). It was one of five copies; two of the other four resolved
# the key by hand-parsing .env for a line starting ANTHROPIC_API_KEY, which
# reads a key the shell has already overridden. One builder now, and its
# refusal message is this one's, word for word.


def _call(system: str, user: str, max_tokens: int, *,
          kind: str = "dreaming", record: bool = False,
          part: "str | None" = None):
    """One call, its own client — a client per worker costs nothing and
    removes every thread-safety question (R170: the seven run in parallel).

    `kind` NAMES THE CALL — dreaming, synthesis, backfill, diagnosis — for
    the retry ladder's wait line and, since R412 (2026-08-30), the capture:
    until then every call this module made was labelled "dreaming", the
    synthesis and the diagnostic included. `record=True` writes the request
    to the circle's capture as it is sent, when a turn log is open (a live
    /close, or the one circle_process() opens for a hand re-run); `part` is
    who it is for, None for the circle-wide synthesis. The diagnostic is
    never recorded — it writes nothing, and the ruling left it out.

    Returns the Reply, burst (LLM_response_disassembler) — it returned
    (text, usage, stop_reason) until 2026-09-02. stop_reason lives on the
    Message response itself, NOT on usage — Usage carries only token
    counts. An earlier version of the SYNTHESIS failure path read
    `usage._stop_reason`, an attribute that does not exist on either object,
    and so silently reported no stop_reason on every failure ever seen,
    including 2026-08-09_1520 — the one case that most needed it, to tell a
    genuine max_tokens truncation apart from the model stopping on its own.
    The disassembler's burst is what makes that unrepeatable: the stop
    reason has one name, `reply.raw_stop`, and one reader.

    THROUGH THE TRANSPORT SINCE 2026-08-28 (stage 1 of the provider socket).
    This built its own client and called the SDK directly, so it had no
    retry ladder: a transient 529 in one of seven parallel dreaming calls
    failed the whole run, and staging is all-or-nothing, so the cost was a
    re-run rather than the 15-second wait the ladder would have taken. It
    also metered nothing. Both arrive with the routing; the per-call client
    R170 wanted is unchanged — call_once builds one per call unless handed
    one."""
    return LC.stream_call_once(system, user, max_tokens, kind=kind,
                        record=record, part=part)


# --------------------------------------------------------------- grounding
# B91, 2026-09-04 — IS THE MEMORY GROUNDED IN THIS PART'S OWN MATERIAL?
#
# R423 (2026-08-31): Soul, silent in circle 2026-08-31_2138, dreamed a
# first-person memory of Child's fabricated-yard moment. The prompt now tells
# a part with no short_term to leave MEMORY empty; this is the code-level
# check R423 deferred. It is PROVENANCE, checked mechanically — never a
# judgment of content (R175), never a refusal, never a change to what is
# written: a SUSPECT note in the run report, the same shape and the same
# place as the SALIENCE and RESOLUTION notes above, and like them it does
# not fail the run.
#
# Two rules. THE CERTAIN CASE: no short_term for this circle means the part
# did not speak, so a non-empty MEMORY has nothing of its own to stand on.
# THE HEURISTIC CASE — Claude's reading, not a ruling: a part that DID speak,
# whose MEMORY shares fewer than DREAM_GROUNDING_MIN_OVERLAP distinct content
# words with the union of its own statements, the lines addressed to it and
# its own short_term. When that fires, the note also says which OTHER roster
# part's Tag the memory names (case-sensitive, whole word — every Tag here is
# also a common noun, and "the child" is not the Child): the fabricated-yard
# shape was a Soul memory made of Child's lines, and the name is its symptom.
#
# THE NAME IS DIAGNOSTIC DETAIL, NOT A TRIGGER — B91's entry sketched it as
# one, and it was MEASURED before it shipped: against the two closed circles
# in this tree (2026-08-21_1139, 2026-08-09_1520), 17 of 20 committed,
# grounded memories name another part, while every one of them shares 23-71
# content words with its part's own lines. A standalone name rule would have
# called nearly every real memory SUSPECT; the overlap tells them apart, so
# the overlap is the rule. 3 sits far below the lowest real overlap seen.
# A memory can be grounded and still trip this; a fabricated one can pass
# it. That is what "heuristic" means here, and why it is a note, not a gate.
#
# The transcript is read through transcript_store's one parser, never a hand
# parse; the roster's Tags and alt_tags do the name matching, never a literal.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
# Function words and the circle's own furniture — what two texts share
# without sharing any material. Short and deliberately incomplete: the
# threshold, not this list, is the knob.
_STOPWORDS = frozenset("""
a an the and or but nor so yet if then than that this these those there here
i me my mine myself we us our ours you your yours he him his she her hers it its
they them their theirs who whom whose what which when where why how
is am are was were be been being have has had having do does did doing
will would shall should can could may might must
to of in on at by for with from into onto over under about after before
between through during without within along across around against
not no yes very just only also too own same other more most some any each
all both few many much such as up down out off again further once
circle part parts self said says say
""".split())


def _content_words(text: str) -> set[str]:
    """The distinct lowercase words of `text` that carry material: at least
    three letters and not in _STOPWORDS. A set, because the rule counts
    DISTINCT shared words — one word repeated is one word."""
    return {w.lower() for w in _WORD_RE.findall(text)
            if len(w) >= 3 and w.lower() not in _STOPWORDS}


def _own_lines(part: str, transcript: str, with_context: bool = False) -> "str | None":
    """Everything in the transcript that is THIS part's own material: its
    statements (`raw` over `text`, as circle_transcript_line_render prefers —
    a remember bracket is still the part's own words) and every line
    addressed to it, resolved through the roster's own Tag -> dir map so an
    alt_tag addressee counts. VERBATIM, in original order. None when the
    transcript does not parse: the parser is strict by design, and a
    transcript it refuses cannot ground anything either way, so the
    heuristic stands aside rather than guess.

    `with_context=True` ALSO pulls in the one entry immediately before each
    kept line, for reply context (R451, D86 a, 2026-09-04: "own lines,
    verbatim, with one line of reply context each") — a context line pulled
    in twice, or already a kept line itself, is not duplicated. That is
    part_dream()'s ACTUAL PROMPT INPUT below.

    part_dream_grounding_check() calls this WITHOUT context (the default):
    a context line is, by construction, another entry's material — usually
    another part's — and folding it into the OVERLAP CORPUS would let a
    memory built from that other part's own line read as grounded merely
    because it sits next to something addressed here. B91's heuristic exists
    to catch exactly that borrowing, so its corpus stays strict."""
    try:
        _ot, _topic, entries = TS.circle_transcript_parse(transcript)
    except ValueError:
        return None
    keep: set[int] = set()
    order: list[int] = []
    for i, e in enumerate(entries):
        if e.get("is_topic") or e.get("cmd"):
            continue
        mine = e.get("speaker") == part
        to_me = R.DIR_BY_TAG_ALL.get(e.get("to") or "") == part
        if not (mine or to_me):
            continue
        if with_context:
            j = i - 1
            while j >= 0 and (entries[j].get("is_topic") or entries[j].get("cmd")):
                j -= 1
            if j >= 0 and j not in keep:
                keep.add(j); order.append(j)
        if i not in keep:
            keep.add(i); order.append(i)
    order.sort()
    own = [entries[i].get("raw") or entries[i].get("text") or "" for i in order]
    return "\n".join(own)


def part_dream_grounding_check(part: str, memory: str, st_text: "str | None",
                               transcript: str) -> list[str]:
    """B91: SUSPECT notes about a non-empty MEMORY's provenance — see the
    section comment above. `st_text` is the part's short_term for this
    circle, None when it has none (the certain case); `transcript` is the
    closed circle's raw text, read here through the one parser.
    Returns [] when nothing is suspect. Writes nothing, refuses nothing."""
    notes: list[str] = []
    body = memory.strip()
    if not body:
        return notes
    head = " ".join(body.split())[:80]
    if st_text is None:
        notes.append(f"memory from a silent part — {R.TAG_BY_DIR[part]} has no "
                     f"short_term for this circle, yet MEMORY reads {head!r}")
        return notes
    # THE HEURISTIC CASE (Claude's reading, not a ruling): the overlap is the
    # rule; a named part is detail on the note, never a trigger of its own.
    own = _own_lines(part, transcript)
    if own is None:
        return notes
    shared = _content_words(body) & _content_words(own + "\n" + st_text)
    if len(shared) >= DREAM_GROUNDING_MIN_OVERLAP:
        return notes
    named = sorted({R.TAG_BY_DIR[d] for t, d in R.DIR_BY_TAG_ALL.items()
                    if d != part
                    and re.search(r"\b" + re.escape(t) + r"\b", body)})
    detail = f"; names {', '.join(named)} (another part)" if named else ""
    notes.append(f"memory not grounded in the part's own lines (heuristic) — "
                 f"shares {len(shared)} content word(s) with its own lines "
                 f"(threshold {DREAM_GROUNDING_MIN_OVERLAP}){detail}; "
                 f"MEMORY reads {head!r}")
    return notes


# ---------------------------------------------------------------- dreaming
def part_dream(part: str, ot: str, transcript: str, capsule: str = "") -> dict:
    """ONE part's dreaming pass — returns a PAYLOAD, writes nothing.
    A silent part (no short_term, maybe no statements) still dreams: the
    designed outcome for it is an unchanged document and an empty MEMORY,
    which is legal and non-SUSPECT.

    `capsule` IS THE SHARED ROOM CAPSULE (R451, D86 a, 2026-09-04) —
    circle_capsule_build()'s one-per-circle text, identical for every part;
    the driver computes it once and passes it in. Defaults to "" so a direct
    call (a suite, a hand re-run before a capsule exists) still runs: an
    empty capsule renders as an empty section, never a refusal."""
    tag = R.TAG_BY_DIR[part]
    distillate, _why = MT.part_mid_term_block_render(part)
    st_path = STM.short_term_locate(record_dir(ROOT, "parts") / part, ot)
    prior = RM.remember_newest_dreamt_read(part)
    own = _own_lines(part, transcript, with_context=True)
    user = [f"# Your identity distillate\n{distillate or '(none on file)'}",
            f"# Your own lines from circle {ot}\n{own or '(you have none this circle)'}",
            f"# What else happened in the room\n{capsule or '(no capsule this run)'}"]
    st_text: "str | None" = None          # None = no short_term = did not speak (B91)
    if st_path is not None:
        # WHAT THE PART SEES DOES NOT CHANGE WITH THE FORMAT (B96, R434): a
        # .toml record is rendered back into the .md shape it was written in —
        # the same header, the same four headings — and a legacy .md goes in
        # as its own bytes, as it always did. B91's grounding check reads the
        # same st_text, so it sees the .md shape for either format.
        st_rec = STM.short_term_read(st_path, part)
        st_text = (STM.short_term_prose_render(st_rec) if st_rec["format"] == STM.FORMAT_NEW
                   else st_path.read_text(encoding="utf-8"))
        # R248, 2026-08-19: "Do mark reconstructions." The mark is only worth
        # writing if the reader that matters acts on it, and this is that
        # reader — a reconstruction was written from the transcript AFTER the
        # fact, and dreaming taking it for the part's own contemporaneous
        # record is exactly the blur the ruling refuses.
        head = "# Your short_term for this circle"
        if st_rec["reconstructed"]:
            head += (" — RECONSTRUCTED from the transcript after the fact, "
                     "NOT what you wrote in the moment")
        user.append(f"{head}\n{st_text}")
    if prior:
        sal_note = f" (tagged {prior['salience']})" if prior.get("salience") else ""
        user.append(f"# The most recent memory in your chain{sal_note}\n"
                    f"{prior['text']}")
    system = DREAMING_PROMPT_V1.format(part=tag, ot=ot, cap=RM.RECORD_CAP)
    user_text = "\n\n".join(user)
    reply = _call(system, user_text, DREAM_MAX_TOKENS,
                  kind="dreaming", record=True, part=part)
    text, usage, stop_reason = reply.text, reply.usage, reply.raw_stop
    chars = {"system": system, "user": user_text, "reply": text,
             "blocks": user}
    sections, err = RD.message_sections_read(
        text, ("MEMORY", "SALIENCE", "RESOLUTION"),
        optional=frozenset({"SALIENCE", "RESOLUTION"}))
    # output_tokens AND stop_reason RIDE EVERY PAYLOAD, 2026-08-21 — the two
    # numbers that told the 2026-08-21_1139 failure apart from a header
    # mismatch, and that the report did not carry at the time.
    if sections is None:
        # RAW OUTPUT KEPT. R168 promises a diagnosis, and an unparseable
        # output cannot be diagnosed from the error string alone — the first
        # rehearsal (2026-08-09_1520) failed here and the sample was gone,
        # so re-seeing it would have cost another 8 model calls.
        return {"part": part, "error": f"unparseable output: {err}",
                "raw": text, "usage": usage, "stop_reason": stop_reason,
                "output_tokens": reply.output_tokens, "chars": chars}
    out: dict = {"part": part, "usage": usage, "suspect": [], "truncated": [],
                 "chars": chars, "stop_reason": stop_reason,
                 "output_tokens": reply.output_tokens}
    mem = sections["MEMORY"].strip()
    if mem:
        continues, body = RD.message_continues(mem)
        if not body:
            pass                        # bare CONTINUES = let it stand
        else:
            # B91, 2026-09-04: provenance, checked on the body as the model
            # wrote it (before the tolerance cut below). SUSPECT notes only —
            # the memory is kept exactly as it would have been.
            out["suspect"].extend(
                part_dream_grounding_check(part, body, st_text, transcript))
            # Same rule for the memory: over the tolerance (1.5 x
            # RECORD_CAP, the most the register ever accepted whole) it is
            # TRUNCATED there and kept, not refused. render_dreamt() then
            # applies RECORD_CAP itself, as it always has.
            limit = int(RM.RECORD_CAP * 1.5)
            if len(body) > limit:
                was = len(body)
                body = RD.message_truncate(" ".join(body.split()), limit)
                out["truncated"].append(
                    f"memory TRUNCATED at {len(body):,} chars (was {was:,}; "
                    f"the {RM.RECORD_CAP}-char cap's tolerance is {limit})")
            out["memory"] = body
            # SALIENCE (DESIGN_V2), 2026-08-22: required whenever MEMORY is
            # non-empty, but an absent or unparseable answer COERCES rather
            # than refuses the call (RM.remember_salience_coerce's own rule).
            sal_raw = sections.get("SALIENCE")
            out["salience"] = RM.remember_salience_coerce(sal_raw)
            if sal_raw is None or sal_raw.strip().lower() not in RM.SALIENCE_VALUES:
                out["suspect"].append(
                    f"SALIENCE absent or unparseable ({sal_raw!r}) — "
                    f"coerced to 'passing'")
            # RESOLUTION also chains onto the prior memory, same mechanism
            # as a MEMORY-level "CONTINUES" — either one is sufficient.
            resolution = sections.get("RESOLUTION")
            resolved = bool(resolution and resolution.strip())
            if resolved and prior and prior.get("salience") != "charged":
                out["suspect"].append(
                    "RESOLUTION claimed but the prior memory in this "
                    f"chain was not tagged 'charged' (was "
                    f"{prior.get('salience')!r})")
            out["continues"] = continues or resolved
    return out
