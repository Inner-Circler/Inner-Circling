#!/usr/bin/env python3
"""
LLM_response_disassembler.py — bursts the REMOTE_AGENT_REPLY package.

ONE REPLY, ONE BUNDLE, EVERY READ IN ONE PLACE. Every model call this
project makes comes back in the same shape — text, a stop reason, usage, and
(since R386) the thinking — and until 2026-09-02 each consumer read the
pieces it wanted straight off whatever tuple its own transport wrapper
handed it: `call()` returned (text, raw_stop), `call_once()` returned
(text, usage, stop), inter_circle/coalesce/dream_history each re-shaped
that again, and SEVEN sites tested the vendor's own word
`stop == "max_tokens"` to ask one question, "was this cut off?". The
work/graph/llm_response_data_flow picture drew that as it was: every
consumer reaching into the response itself.

This module is the second column of that picture, made real. The transport
hands a raw response to message_burst(); message_burst() returns a Reply; every consumer
reads the Reply by NAME (reply.text, reply.truncated, reply.usage) and
never the wire. The same discipline the 2026-09-02 prompt-assembly refactor
gave the OTHER direction — ingredient functions that read files, block
assemblers that only assemble — applied to the reply coming back.

TWO HALVES, IN THE CIRCLE'S OWN TIME. The reads a reply gets IN-CIRCLE
(a statement, a short_term at /close) and the reads it gets INTER-CIRCLE
(dreaming, synthesis, mid_term, coalesce, a dream fold, a backfill) are
different grammars over the same package; they sit under their own
headings below so the picture's third column can be read straight off
this file.

WHAT STAYS WHERE IT WAS, and why each is not a "reply read":
  - providers.read()/thinking_record(): WHERE a piece sits in a reply is the
    vendor's business (R382). message_burst() takes the provider's Turn and asks the
    provider for the thinking; it never touches a content block.
  - annotations.py's ASK_RE family, split_close_remember(), recall_index's
    RECALL_RE: the ANNOTATION grammar, cited by docs/BNF.md's own @file
    tags — and they read Self's typed input as much as a part's reply
    (apply_self_remember, annotations_in at the opening prompts). The
    in-circle reads here CALL them; the grammar keeps one home.
  - part_mid_term_manager.part_mid_term_suspect_read(): a write gate over mid_term's own budget
    constants; it takes a Reply now and tests reply.truncated, which is the
    read this module owns.

LEAF MODULE. rounds, circle, llm_client, inter_circle, mid_term, backfill,
coalesce and dream_history all take this; it takes none of them. What it
takes at import is providers and the two constants it must not copy
(ifs_model.SHORT_TERM_SECTIONS, record_paths.PART_TAGS). annotations — the
grammar above — is reached inside message_close_split() alone, at call time:
annotations pulls in memory/issue_commands, and llm_client (which every
suite and every tool loads) must stay importable with only coordinator/ on
sys.path, as it was before this module existed.
"""
from __future__ import annotations

import re

import providers as _providers
from ifs_model import SHORT_TERM_SECTIONS
from record_paths import PART_TAGS


# ============================================================== the bundle
class Reply:
    """One reply, burst. `text` is what the model said (stripped, the
    transcript's own form); `stop` the normalised reason (providers.STOP_*)
    and `raw_stop` the vendor's word; `usage` the provider's own object
    (the Meter reads it by attribute); `thinking` the recorded reasoning
    or None when not asked for; `record` the capture's response dict —
    the shape turn_contract.toml checks, built once here so the thing
    recorded and the thing returned are the same burst."""

    __slots__ = ("text", "stop", "raw_stop", "usage", "thinking", "id",
                 "model", "record", "dry_run")

    def __init__(self, text: str, stop: str, raw_stop: str, usage, *,
                 thinking: "str | None" = None, id: "str | None" = None,
                 model: "str | None" = None, record: "dict | None" = None,
                 dry_run: bool = False) -> None:
        self.text = text
        self.stop = stop
        self.raw_stop = raw_stop
        self.usage = usage
        self.thinking = thinking
        self.id = id
        self.model = model
        self.record = record if record is not None else {
            "text": text, "stop_reason": raw_stop, "usage": message_usage_record(usage)}
        self.dry_run = dry_run

    @classmethod
    def canned(cls, text: str, raw_stop: str = "end_turn", usage=None,
               *, dry_run: bool = True) -> "Reply":
        """A reply that came from no wire — the dry-run provider's fixture,
        and every suite's fake. The record is the three keys the dry path
        has always written."""
        stop = _providers.AnthropicProvider.STOP_MEANING.get(
            raw_stop, _providers.STOP_OTHER)
        return cls(text, stop, raw_stop, usage, dry_run=dry_run)

    @property
    def truncated(self) -> bool:
        """Ran out of room — the retry-worthy stop, and the one every
        consumer used to test as the literal "max_tokens"."""
        return self.stop == _providers.STOP_TRUNCATED

    @property
    def empty(self) -> bool:
        return not self.text.strip()

    @property
    def output_tokens(self) -> "int | None":
        return message_out_tokens_read(self.usage)

    def __repr__(self) -> str:
        return (f"Reply(text={self.text[:40]!r}..., stop={self.stop!r}, "
                f"raw_stop={self.raw_stop!r})")


def message_burst(impl, resp, *, record_thinking: bool) -> Reply:
    """The one place a raw response becomes a Reply. `impl` is the provider
    that sent the request and reads its own wire; `record_thinking` is
    llm_client.RECORD_THINKING, passed rather than imported so this module
    stays a leaf.

    THE RECORD'S TEXT IS THE RAW JOIN, NOT THE STRIPPED ONE — the capture
    has always kept the reply before anything trimmed it, and a turn file
    written today must hash like one written yesterday. Turn.raw_text is
    that join; Turn.text is what the room gets.

    THE THINKING KEY'S PRESENCE IS THE RECORD OF THE SETTING (llm_client's
    own rule, kept): when recording is on the key is written even if the
    model thought nothing."""
    turn = impl.read(resp)
    record = {
        "id": getattr(resp, "id", None),
        "model": getattr(resp, "model", None),
        "stop_reason": getattr(resp, "stop_reason", None),
        "text": turn.raw_text,
        "usage": message_usage_record(turn.usage),
    }
    thinking = None
    if record_thinking:
        tr = impl.thinking_record(resp)
        record.update(tr)
        thinking = tr.get("thinking")
    return Reply(turn.text, turn.stop, turn.raw_stop, turn.usage,
                 thinking=thinking, id=record["id"], model=record["model"],
                 record=record)


# ---------------------------------------------------------------- usage
def message_usage_record(u) -> "dict | None":
    """The usage as the CAPTURE keeps it: the SDK's whole model_dump(),
    nested details included — usage.output_tokens_details.thinking_tokens
    is where "thinking is 55% of output tokens" was measured. A fake with
    no model_dump() gives the four top-level counts."""
    if u is None:
        return None
    try:
        return u.model_dump()                           # the SDK's pydantic object
    except AttributeError:
        return {k: getattr(u, k) for k in
                ("input_tokens", "output_tokens",
                 "cache_creation_input_tokens", "cache_read_input_tokens")
                if hasattr(u, k)}


def message_usage_counts_read(u) -> "dict | None":
    """The usage as ARITHMETIC reads it: integer fields only, so two calls'
    usage can be summed. anthropic's Usage is a pydantic model — no .get(),
    and iterating it yields (name, value) pairs, not keys — so a dict-style
    merge over the raw object always raised and silently dropped the
    second call's cost."""
    if u is None or isinstance(u, dict):
        return u
    dump = getattr(u, "model_dump", None)
    if callable(dump):
        return {k: v for k, v in dump().items() if isinstance(v, int)}
    # A fake, or a vendor object with no dump: the four counts by name.
    # vars() was the fallback until 2026-09-02 and read {} off any object
    # whose counts are class attributes — every suite's stub.
    return {k: getattr(u, k) for k in
            ("input_tokens", "output_tokens",
             "cache_creation_input_tokens", "cache_read_input_tokens")
            if isinstance(getattr(u, k, None), int)}


def message_usage_merge(a, b):
    """Two calls' usage, summed where both are present. A re-ask is a REAL
    cost and must appear in the run's total; dropping it would under-report
    exactly the case worth watching. Returns a plain dict when it actually
    merged — message_out_tokens_read() reads both shapes."""
    if a is None:
        return b
    if b is None:
        return a
    da, db = message_usage_counts_read(a), message_usage_counts_read(b)
    return {k: (da.get(k, 0) or 0) + (db.get(k, 0) or 0)
            for k in set(da) | set(db)}


def message_out_tokens_read(u) -> "int | None":
    """output_tokens off a Usage object OR a message_usage_merge() dict."""
    if isinstance(u, dict):
        return u.get("output_tokens")
    return getattr(u, "output_tokens", None)


# ========================================================= IN-CIRCLE reads
# A part's STATEMENT — what part_statement_ask() takes off the reply once the
# truncation retry has run. Moved here from rounds.py 2026-09-02; the
# rules and their rulings are unchanged.
_TO_RE = re.compile(r"^\s*\[To:\s*([^\]]+)\]\s*:?\s*", re.IGNORECASE)
_SELFNAME_RE = re.compile(
    r"^\s*\[?(" + "|".join(re.escape(t) for t in PART_TAGS.values()) + r")\]?\s*:\s*",
    re.IGNORECASE,
)
# A PART THAT SPEAKS AND THEN SIGNS OFF HAS SPOKEN (R262, 2026-08-20). The
# pass test below is WHOLE-TEXT and always has been, so a part that said
# its piece and put `[pass]` on the end had that marker carried verbatim
# into the transcript and into the room, where it read as a third party
# passing. DELIBERATELY NARROW: only a whole final LINE that is nothing but
# the bracketed form. A statement ending in the word "pass" is a part using
# the word, and is left alone.
_TRAILING_PASS_RE = re.compile(r"\n\s*\[pass\]\.?\s*$", re.I)
_PASS_FORMS = ("[pass]", "pass", "[pass].")


def message_is_pass(text: "str | None") -> bool:
    """The whole-text pass: the part said nothing the room can hear."""
    return not text or text.strip().lower() in _PASS_FORMS


def message_statement_read(text: str) -> "tuple[str | None, str | None]":
    """(statement, to_whom), or (None, None) for a pass. Strips, in order,
    the sign-off, a leading self-name, and the [To: ...] address — BEFORE
    anything else reads it: the record, the room, render_messages' rebuild
    of every other part's view, and route_annotations all take their text
    from here, and none of them should ever see the sign-off."""
    if message_is_pass(text):
        return None, None
    text = _TRAILING_PASS_RE.sub("", text)
    text = _SELFNAME_RE.sub("", text.strip())
    to = None
    m = _TO_RE.match(text)
    if m:
        to = m.group(1).strip()
        text = _TO_RE.sub("", text).strip()
    return (text or None), to


# A part's SHORT_TERM — the /close reply: four sections, and (R255) its
# one remember LAST. annotations.remember_close_split() is the lenient
# parser for that bracket; what this module adds is the two questions
# circle_close.short_term_collect() asks of the reply before it writes.
def short_term_missing(text: str) -> list[str]:
    """The four headings not present in the reply — the retry's and the
    refusal's test, in one place."""
    return [h for h in SHORT_TERM_SECTIONS if h not in text]


def message_close_split(text: str) -> bool:
    """Would the lenient close-remember split keep all four sections? The
    split takes everything after the opener, which is what makes a "]"
    inside a long memory safe; a bracket written mid-reply would swallow a
    heading. PURE, so it can be consulted BEFORE any write — deciding
    afterwards would leave the swallowed-heading version on file and have
    the strict retry refuse itself as a second use."""
    import annotations as MK            # at call time — see the module docstring
    return not short_term_missing(MK.remember_close_split(text)[0])


# ====================================================== INTER-CIRCLE reads
# Dreaming, synthesis, the mid_term derivation and a backfill all answer in
# NAMED SECTIONS; coalesce answers in GROUP lines; a dream fold in prose
# under a word cap. Moved here from inter_circle.py (sections/items_of/
# headings/continues/truncate_at/norm_len), proposal_group_manager.py (groups) and
# dream_history.py (word_cap), 2026-09-02.
def message_sections_read(text: str, headers: "tuple[str, ...]",
             optional: frozenset = frozenset()
             ) -> "tuple[dict | None, str | None]":
    """Split model output on EXACT header lines, in order. A header NOT in
    `optional` is required exactly once — a missing, duplicated, or
    out-of-order required header refuses the whole output: fail loud,
    never guess (R168 hands it back). A header IN `optional` may appear
    zero or one times; absent, it is simply missing from the returned dict
    rather than a refusal — DESIGN_V2's SALIENCE/RESOLUTION lines, which
    "coerce ... never refuse the whole DREAMING call over one bad tag."
    Section bodies may contain anything — including column-0 `## `
    headings, which is why 'no other text at column 0' cannot be the
    rule."""
    lines = text.splitlines()
    pos: list[tuple[str, int]] = []
    for h in headers:
        hits = [i for i, l in enumerate(lines) if l.strip() == h and l == l.lstrip()]
        if h in optional:
            if len(hits) > 1:
                return None, (f"optional header {h!r} appears {len(hits)} "
                              f"times; expected at most once")
            if hits:
                pos.append((h, hits[0]))
            continue
        if len(hits) != 1:
            return None, (f"header {h!r} appears {len(hits)} time(s); "
                          f"expected exactly once")
        pos.append((h, hits[0]))
    if [i for _h, i in pos] != sorted(i for _h, i in pos):
        return None, "headers out of order"
    out = {}
    for k, (h, i) in enumerate(pos):
        end = pos[k + 1][1] if k + 1 < len(pos) else len(lines)
        out[h] = "\n".join(lines[i + 1:end]).strip("\n").strip()
    return out, None


def message_items_read(section: str) -> list[str]:
    """'- ' items, each possibly wrapping onto following lines."""
    out, cur = [], []
    for l in section.splitlines():
        if l.lstrip().startswith("- "):
            if cur:
                out.append(" ".join(cur))
            cur = [l.lstrip()[2:].strip()]
        elif cur and l.strip():
            cur.append(l.strip())
    if cur:
        out.append(" ".join(cur))
    return [x for x in out if x]


def message_headings_read(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if l.startswith("## ")]


def message_continues(section: str) -> "tuple[bool, str]":
    """(continues, body): a section whose FIRST line is the bare word
    CONTINUES chains onto the prior record, and the body is what follows
    it. DREAMING's MEMORY and SYNTHESIS's OBSERVATION read the same signal
    (R358: the observation follows the dreaming model) — one split, not
    two."""
    s = section.strip()
    if not s:
        return False, ""
    first, *rest = s.splitlines()
    if first.strip() == "CONTINUES":
        return True, "\n".join(rest).strip()
    return False, s


def message_truncate(text: str, cap: int) -> str:
    """Cut `text` to at most `cap` characters at the LAST WHITESPACE before
    the cap — never mid-word — and strip the ragged end. The operator,
    2026-08-21: *"a cap-crunch must not cause a fail; report, but truncate
    at the cap and allow."* A text already within the cap comes back
    unchanged, byte for byte. A text with no whitespace before the cap is
    hard-cut at it rather than refused — the rule is truncate-and-allow."""
    if len(text) <= cap:
        return text
    cut = text[:cap]
    sp = max(cut.rfind(" "), cut.rfind("\n"), cut.rfind("\t"))
    if sp > 0:
        cut = cut[:sp]
    return cut.rstrip()


def message_length_norm(s: str) -> int:
    """Length as circle_history_manager.circle_history_new_render() will measure it — it collapses
    whitespace before checking the cap, so measuring the raw section would
    over-count and trigger a re-ask that the register would have accepted."""
    return len(" ".join(s.split()))


def message_word_cap_read(text: str, cap: int) -> "tuple[str, bool]":
    """(text, cut) — over `cap` words the reply is truncated whitespace-
    aware and reported, never refused (a dream fold's own rule)."""
    words = text.split()
    if len(words) <= cap:
        return text, False
    return " ".join(words[:cap]), True


# THE GROUPING PASS answers one line per group, in the format proposal_group_manager.SYSTEM
# dictates; this is the reader of that line.
_GROUP_LINE_RE = re.compile(
    r"^GROUP:\s*(?P<members>\S+(?:\s+\S+)*?)\s*\|\s*PRIMARY:\s*(?P<primary>\S+)"
    r"\s*\|\s*GLOSS:\s*(?P<gloss>.+?)\s*$")


def message_groups_read(reply: str, valid_refs: set) -> "tuple[list[dict], list[str]]":
    """(groups, notes). Every invalid line is DROPPED with a note, never
    guessed at: unknown ref, fewer than two members, a duplicate member, a
    member already claimed by an earlier group, a primary outside the
    group. A blank reply is a valid no-groups answer."""
    out: list[dict] = []
    notes: list[str] = []
    claimed: set = set()
    for raw in reply.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _GROUP_LINE_RE.match(line)
        if not m:
            notes.append(f"unparseable line dropped: {line[:80]!r}")
            continue
        members = m.group("members").split()
        primary = m.group("primary")
        if len(set(members)) != len(members):
            notes.append(f"duplicate member in group dropped: {members}")
            continue
        if len(members) < 2:
            notes.append(f"singleton group dropped: {members}")
            continue
        bad = [x for x in members if x not in valid_refs]
        if bad:
            notes.append(f"unknown ref(s) {bad} — group dropped")
            continue
        if any(x in claimed for x in members):
            notes.append(f"overlapping group dropped: {members}")
            continue
        if primary not in members:
            notes.append(f"primary {primary!r} outside its group — dropped")
            continue
        claimed.update(members)
        out.append({"members": members, "primary": primary,
                    "gloss": m.group("gloss")})
    return out, notes
