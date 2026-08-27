#!/usr/bin/env python3
"""
rounds.py — the circle's turn engine: ask_statement (a part's one
statement, truncation-marked rather than lost), the blind opening
round and the sequential rounds after it, the since-Self scheduler
guard, and /tokens' per-part block table (token_table — Self's
explicit ruling placed it here, with the lifecycle that owns the
blocks it measures). Phase 2 stage 7, the last extraction of the
coordinator partitioning (2026-08-16); until then all of it lived in
circle.py. Verbatim move — bodies and comments unchanged, except
console output and the failure ledger go through seam.emit/seam.fail
by attribute access.

This module is the split's KEYSTONE CONSUMER, deliberately last: it
calls the transport (llm_client.call), the prompt view
(prompt_build.render_messages), the annotation system (markers'
apply_remember/strip_malformed_markers/route_markers) and the
transcript writers (transcript_store's statement_line/append) — one
round, four owners, each reached through its own module. MAX_TOKENS /
MAX_SINCE_SELF / TRUNCATION_MARKER travel with it: the ceiling, the
per-Self cap and the truncation contract are round semantics, not
transport settings.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import random
import re

import seam
import token_count as TC
from llm_client import call, MODEL
from markers import (apply_remember, strip_malformed_markers,
                     route_markers, REMEMBER_RE)
from paths import PART_TAGS
from prompt_build import render_messages
from transcript_store import statement_line, append, withheld

# ~100 words is ~135 tokens; the ceiling is deliberately far above the word cap so
# that hitting it means genuine runaway generation, not a part finishing a slightly
# long thought. Raised 400 -> 600 (2026-07-26): at 400 a part that overran twice was
# silently dropped from the circle, and a dropped statement is unrecoverable — the
# nightly cannot distinguish it from chosen silence. Truncation is an error, not a
# statement; see ask_statement().
# Raised 600 -> 1000, ruled 2026-08-04. The truncation retry was firing on
# statements of ~87 words, which is nowhere near 600 tokens of output — this
# model bills THINKING against max_tokens, so a part reasoning carefully was
# being cut off mid-sentence and asked to start again shorter. Self: "the
# request carries more tokens than a slightly longer response, so response
# brevity is a convenience for me, nothing else."
#
# A ceiling is not a spend. Output is billed on tokens PRODUCED, so raising
# this costs nothing until a statement actually gets longer; the word rule in
# process_core is the control, and this is only headroom for the thinking.
MAX_TOKENS = 2500
# RAISED FROM 1000, 2026-08-06. Five parts ran long in circle_2026-08-06_1012
# and a part truncated TWICE, which is a data failure. The ceiling is
# headroom for THINKING, which bills against it — so a part that thinks for
# 800 tokens has 200 left for a 150-word statement, and the retry telling it
# to be shorter does not shorten its thinking.
#
# A CEILING IS NOT A SPEND. Unused tokens cost nothing; only what is actually
# emitted is billed. That circle spent $3.72 with 33,674 output tokens across
# 88 calls — 383 on average, nowhere near 1000. The truncations were thinking,
# not verbosity, and the fix is headroom rather than a shorter instruction.
MAX_SINCE_SELF = 2                      # process_core: max 2 statements per Self turn

TRUNCATION_MARKER = "[statement truncated at the token ceiling -- incomplete]"


# Meter/METER MOVED to llm_client.py, 2026-08-16 (phase 2 stage 1) -
# the usage meter and its lock; METER here is the SAME instance,
# imported at the top of this file (mutated in place, never
# reassigned - the seam.FAILURES contract).

# ------------------------------------------------------------------ API# ------------------------------------------------------------------ API
_TO_RE = re.compile(r"^\s*\[To:\s*([^\]]+)\]\s*:?\s*", re.IGNORECASE)
_SELFNAME_RE = re.compile(
    r"^\s*\[?(" + "|".join(re.escape(t) for t in PART_TAGS.values()) + r")\]?\s*:\s*",
    re.IGNORECASE,
)


# call(), the API preflight ladder (BACKOFF/_transient/with_backoff/
# _no_sdk_retries), the key diagnostics (_env_file_key/_mask/
# key_source_note/explain_api_failure), preflight_api() and prewarm()
# MOVED to llm_client.py, 2026-08-16 (phase 2 stage 1) - verbatim,
# comments and the 2026-08-09 ruling included. ask_statement below
# STAYS: round-logic wearing an API call (goes with rounds, stage 7).
# _TO_RE/_SELFNAME_RE above stay with it - they parse a STATEMENT,
# not the transport.


# A PART THAT SPEAKS AND THEN SIGNS OFF HAS SPOKEN
# (R262, 2026-08-20). The pass test below is
# WHOLE-TEXT and always has been, so a part that said its piece and put
# `[pass]` on the end had that marker carried verbatim into the transcript
# and into the room. It reads there as a third party passing, because the
# coordinator's own pass report goes to the COMMAND channel and never
# looked like that. Five statements in circle_2026-08-20_0845 carry one,
# every time as the last line of a real statement, two of them answered by
# other parts.
#
# DELIBERATELY NARROW: only a whole final LINE that is nothing but the
# bracketed form. A statement ending in the word "pass" is a part using
# the word, and is left alone. Anything that IS only a pass never reaches
# here -- the whole-text test catches it first and the turn stays a pass.
_TRAILING_PASS_RE = re.compile(r"\n\s*\[pass\]\.?\s*$", re.I)


def for_display(text: str) -> str:
    """The statement as the ROOM SEES IT: whitespace-only lines dropped,
    every real line break kept. DISPLAY ONLY
    (R263, 2026-08-20).

    THE RECORD IS NOT ROUTED THROUGH THIS, and cannot be by accident: the
    two call sites emit this while the `append` beside them writes
    `record`, which is a different string already. So no stored transcript
    changes shape, no close report's sha256 moves, and dreaming still
    reads the part's own paragraphing. What changes is only that a reply
    stops being spread over three screens of blank line -- the blank line
    BETWEEN replies is the emit's own leading "\n" and is untouched."""
    return "\n".join(ln for ln in text.splitlines() if ln.strip())


def ask_statement(client, part: str, blocks: list[dict], transcript: list[dict],
                  dry: bool) -> tuple[str | None, str | None]:
    """Returns (statement, to_whom) or (None, None) for a pass."""
    text, stop = call(client, part, blocks, render_messages(part, transcript),
                      MAX_TOKENS, dry)
    if stop == "max_tokens":
        # Truncation is a failure, not a statement. One retry, then give up.
        seam.emit("command", f"  [{part} ran long — asking again, shorter]")
        msgs = render_messages(
            part, transcript,
            "(the circle comes to you — speak in UNDER 150 words and finish "
            "your sentence, or reply [pass])",
        )
        text, stop = call(client, part, blocks, msgs, MAX_TOKENS, dry)
        if stop == "max_tokens":
            # Do NOT downgrade a truncation to a pass. A part that tried to speak
            # and was cut off would otherwise be indistinguishable from a part that
            # chose silence — and the nightly's transcript safety net deliberately
            # exempts genuinely silent parts, so nothing downstream would ever catch
            # it. That was the one data-loss path in this pipeline with no net.
            # Keep what was said and mark it: the marker is line-TRAILING, so
            # circle_close.py::parts_that_spoke() still counts the statement, the
            # part still writes a short_term, and dreaming still sees engagement.
            if text and text.strip():
                seam.fail(f"{PART_TAGS[part]} truncated twice at {MAX_TOKENS} tokens — "
                     f"incomplete statement KEPT and marked in the transcript; "
                     f"review before the nightly runs")
                text = text.strip() + " " + TRUNCATION_MARKER
            else:
                seam.fail(f"{PART_TAGS[part]} truncated twice at {MAX_TOKENS} tokens with "
                     f"no recoverable text — statement LOST; this part may now read "
                     f"as silent to the nightly")
                return None, None
    if not text or text.strip().lower() in ("[pass]", "pass", "[pass]."):
        return None, None
    # BEFORE anything else reads it: the record, the room, render_messages'
    # rebuild of every other part's view, and route_markers all take their
    # text from here, and none of them should ever see the sign-off.
    text = _TRAILING_PASS_RE.sub("", text)
    text = _SELFNAME_RE.sub("", text.strip())
    to = None
    m = _TO_RE.match(text)
    if m:
        to = m.group(1).strip()
        text = _TO_RE.sub("", text).strip()
    return (text or None), to


# --------------------------------------------- transcript file + working set
# MOVED to transcript_store.py, 2026-08-16 (phase 1 step 3): write_lf,
# open_transcript, append, the working-set history and the no-trace
# discard of an unspoken open, statement_line, and the whole resume
# cluster (render_line/render_transcript/parse_transcript/
# rebuild_state/load_for_resume) - verbatim, comments included. The
# names this file still calls are imported at the top.

# ------------------------------------------------------------------ scheduler
# ------------------------------------------------------------------ blind round
# CIRCLE_DESIGN.md §1. Round 1 only: every part is asked IN PARALLEL against the
# same snapshot — the topic and nothing else — and all statements are revealed
# together. Rounds 2..N stay sequential, which is what makes the circle a
# conversation rather than seven monologues.
#
# WHY. Sequential polling is a convergence engine. That is a feature for most of
# a circle and it makes one question unanswerable: when the parts agree, is the
# material one shape, or did the first speaker set a template? Those are
# indistinguishable in every transcript this project holds, which is why E04 has
# stayed open. A blind round separates them:
#
#     converge WITHOUT seeing each other   -> real convergence
#     converge only AFTER the first speaks -> template propagation
#
# circle_2026-08-01_1913 is the motivating case. Five parts, sequential, one part
# first. Content diverged completely — Feynman, Marcus Aurelius, Oliver, James,
# Cave — and the closing construction converged five for five:
# "That's the health I'm reaching for" / "the register I want" / "my healthiest
# shape" / "my healthiest register" / "the health I want". Form propagated while
# content did not, and no measurement in the project could have caught it.
#
# THE PARTS ARE NOT TOLD THE ROUND IS BLIND, and that is deliberate. Telling them
# would be an instruction ("no one else has spoken") that could itself induce
# divergence — contaminating the exact measurement the round exists to make. Each
# part is put in the position the FIRST speaker already occupies today: it sees
# the topic and nothing else. That makes the blind round a clean control against
# every existing transcript. The marker is appended AFTER the round, for readers
# and for rounds 2..N.
BLIND_CLOSE = ("[BLIND ROUND ENDS — the {n} statement(s) above were made without "
               "sight of one another. Sequential rounds follow.]")

# THE REVEAL, ruled 2026-08-05. Self: *"collect all the responses blind, then
# forward them together as an attributed block to all parts for their
# awareness and potential reply."*
#
# The statements already reached every part — they are appended to the
# transcript and render_messages rebuilds each part's view from it, so the
# One part sees the Child's and another's, attributed, from the next round
# on. What was missing was the MOMENT: the block arrived as ordinary
# conversation history, split around a part's own turn, and nothing asked
# anyone to answer it. A part's next turn came only when Self typed
# something.
#
# This names the moment and gives the room one pass at it.
REVEAL_OPEN = ("[REVEAL — every statement above was made blind. You are seeing "
               "all of them together now, for the first time. Answer what "
               "lands, dispute what does not, or [pass]. Nobody is owed a "
               "reply.]")


def run_blind_round(client, parts, sysblocks, transcript, since_self, state,
                    guard, path, dry, *, live: bool) -> int:
    """Round 1, parallel and blind. Returns the number of statements made.

    Every part is asked against `snapshot`, a copy of the transcript as it stood
    before the round — so a statement made during the round cannot reach any
    other part, whatever order the threads finish in. The append order is the
    shuffled order, not the completion order, so a run is reproducible under
    --seed and the transcript does not record network timing as if it were
    conversational order."""
    order = parts[:]
    random.shuffle(order)
    snapshot = list(transcript)          # frozen: nothing said now is visible now
    results: dict[str, tuple] = {}

    def ask(part):
        return part, ask_statement(client, part, sysblocks[part], snapshot, dry)

    seam.emit("command", f"  asking {len(order)} part(s) in parallel — none will see another")
    if dry:
        for p in order:
            results[p] = ask(p)[1]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(order)) as ex:
            for fut in concurrent.futures.as_completed(
                    [ex.submit(ask, p) for p in order]):
                part, out = fut.result()
                results[part] = out

    spoke = 0
    for part in order:                   # reveal in shuffled order, not arrival
        text, to = results.get(part, (None, None))
        display = PART_TAGS[part]
        if text is None:
            seam.emit("command", f"  {display}: (passes)")
            seam.emit("circle", f"\n{display} passes")
            continue
        raw = text
        text, recorded = apply_remember(guard, part, display, text)
        why = " — REMEMBER recorded)" if recorded else ")"
        if text:
            text = strip_malformed_markers(text, display)
            if not text:
                why = " — malformed marker only)"
        if not text:
            # THE TURN IS STILL A PASS — RULED 2026-08-18, and deliberately
            # unchanged: no since_self increment, no state["last"], no
            # statement spent, the part said nothing the room can hear.
            # What DID change is that the RECORD no longer loses the bracket.
            # It was the one case the 2026-08-14 retention ruling could not
            # reach, because a pass wrote no line at all.
            #
            # `remember_only` is what keeps the pass a pass everywhere the
            # entry is later read — see transcript_store.withheld(). The file
            # line is indistinguishable from an ordinary statement, which is
            # why the flag is RE-DERIVED on resume rather than stored.
            record = strip_malformed_markers(raw.strip(), display, quiet=True)
            if record and REMEMBER_RE.search(raw):
                transcript.append({"speaker": part, "display": display,
                                   "text": "", "raw": record,
                                   "remember_only": True, "to": to})
                append(guard, path, statement_line(display, to, record))
            seam.emit("command", f"  {display}: (passes{why}")
            seam.emit("circle", f"\n{display} passes")
            continue
        # THE ROOM AND THE RECORD PART COMPANY HERE. Ruled 2026-08-14, built
        # 2026-08-18 (docs/BNF.md, REMEMBER). `text` is the ROOM's: the
        # bracket is gone, and it is what the transcript ENTRY carries, what
        # render_messages() rebuilds every part's view from, and what
        # route_markers() reads. The circle PANE shows for_display(text) --
        # the same string with its whitespace-only lines dropped, 2026-08-20,
        # and that transform reaches nothing else. `record` is
        # COORDINATOR's: this part's own statement with the remember bracket
        # intact — valid or malformed alike — and it goes to the transcript
        # FILE and nowhere else.
        #
        # ONLY A STATEMENT THAT ACTUALLY CARRIES A BRACKET TAKES THE SECOND
        # PATH. apply_remember() collapses runs of spaces and blank lines as
        # part of removing a bracket, and that collapse has reached the file
        # since the day it was written; re-deriving `record` from the raw
        # text unconditionally would quietly stop collapsing them and rewrite
        # the shape of every ordinary statement. The guard keeps this change
        # to exactly the statements the ruling is about.
        #
        # `quiet`: the room pass above already warned about each malformed
        # marker. Two notices for one bracket read as two brackets.
        record = text
        if REMEMBER_RE.search(raw):
            record = strip_malformed_markers(raw.strip(), display, quiet=True)
        since_self[part] = since_self.get(part, 0) + 1
        state["last"] = part
        entry = {"speaker": part, "display": display, "text": text, "to": to}
        if record != text:
            entry["raw"] = record
        transcript.append(entry)
        append(guard, path, statement_line(display, to, record))
        seam.emit("circle", f"\n{statement_line(display, to, for_display(text))}")
        route_markers(display, text, live=live)
        spoke += 1

    note = BLIND_CLOSE.format(n=spoke)
    transcript.append({"speaker": "__scribe__", "display": "Scribe", "text": note})
    append(guard, path, note)
    # RULED 2026-08-13: "do not echo part protocol machinery to Self." This
    # note is a coordinator/LLM-part implementation detail — the room needs
    # it (render_messages() carries every __scribe__ line into each part's
    # rebuilt prompt) and the record needs it (the two lines above, both
    # unconditional), but no interface shows it to Self as circle dialog.
    # No seam.emit() at all, on any channel.
    if not spoke:
        seam.emit("command", "  (silence — every part passed)")
        return spoke

    # THE REVEAL. One sequential pass over the same block, so the room can
    # answer what it could not see while speaking.
    #
    # IT COSTS A STATEMENT. Every part leaves the blind round at 1 of 2, so a
    # part that replies here reaches the limit and is held until Self speaks.
    # That is the protocol working rather than a side effect: the room speaks
    # blind, reacts once, and then it is Self's turn. Making the reveal free
    # would let a circle run four deep before he was consulted.
    transcript.append({"speaker": "__scribe__", "display": "Scribe",
                       "text": REVEAL_OPEN})
    append(guard, path, REVEAL_OPEN)
    # RULED 2026-08-13: "do not echo part protocol machinery to Self" —
    # see the BLIND_CLOSE note above. No seam.emit() here either.
    # `last` IS CLEARED. The blind statements were simultaneous; the reveal
    # order is a shuffle, not a sequence. Leaving `last` set would deny the
    # reveal to whichever part the shuffle happened to put last — the
    # never-speak-twice-in-a-row rule applied to a turn nobody took after.
    state["last"] = None
    spoke += run_round(client, parts, sysblocks, transcript, since_self,
                       state, guard, path, dry, live=live)
    return spoke


def token_table(parts: list[str], sysblocks: dict, since_self: dict | None = None,
                client=None, model: str | None = None, dry: bool = False) -> str:
    """The four system blocks, per part, in tokens — THE WHOLE OF /status's
    prompt section since 2026-08-20, when /tokens was folded into it.

    RULED 2026-08-05, after Self saw seven identical briefing sizes and
    asked whether identity had stopped differing. It had not — but the only
    per-block figure the coordinator printed was block 2's, so seven
    identical numbers were the whole visible story. A per-part fact was
    invisible because nothing printed it.

    COLUMN NAMES ARE HIS, and they are the block order read aloud:

        practices   process_core.md   who we are
        context     the briefing      what we are here for
        part        identity          who you are
        todo        standing rules    what you do

    RULED 2026-08-16: blocks 1-2 (practices, context) are SHARED BY DESIGN
    (circle_identity, circle_objectives — CLAUDE.md's ORDER table) — every
    part carries the identical text, so repeating the identical number on
    seven rows said nothing seven times. Reported ONCE, as "circle
    practices" and "circle context", in a single line. Blocks 3-4 (part,
    todo) genuinely differ per part BY DESIGN, so they stay in the
    per-part table.

    The hash is no longer printed — "not useful to humans" — but the
    comparison it drove stays internal for blocks 1-2: if practices or
    context ever diverge across parts (should never happen), this says so
    instead of silently picking one number.

    THE NUMBERS ARE COUNTED, NOT ESTIMATED, since 2026-08-20 (R260). This
    read `len(text) // 4`, which runs ~30% under what is billed for this
    corpus — measured against prewarm's own cache_creation_input_tokens.
    token_count.block_tokens() asks the model service and memoizes by
    content, so the two blocks every part shares are counted once per
    CHANGE rather than once per part. A dry run, or a service that will not
    answer, falls back to the estimate AND SAYS SO in the footer: a number
    that might be either is worse than no number.

    `since_self` ADDS THE ROUND COLUMN, which is the other half of what
    /status printed as its own separate list. It is optional so a caller
    with no circle running still gets the sizes."""
    def sig(t) -> str:
        raw = t if isinstance(t, str) else (t[0] if t else "")
        return hashlib.sha256(str(raw).encode()).hexdigest()[:6]

    counts: dict[int, list[int]] = {i: [] for i in range(4)}
    shared_sigs: dict[int, set] = {0: set(), 1: set()}
    per_part: dict[str, dict[int, int]] = {}
    measured = True
    for p in parts:
        blocks = sysblocks.get(p, [])
        got, ok = TC.block_tokens(client, blocks, model or MODEL, dry)
        measured = measured and ok
        per_part[p] = {}
        for i in range(4):
            if i >= len(blocks):
                continue
            n = got[i]
            counts[i].append(n)
            if i in shared_sigs:
                shared_sigs[i].add(sig(blocks[i].get("text")))
            per_part[p][i] = n

    def shared_line(i: int, name: str) -> str:
        # NO UNIT ON THE NUMBER — the header two lines up already says
        # "in tokens", and repeating it four times across one line is what
        # made this read as a paragraph rather than a figure.
        if not counts[i]:
            return f"{name} —"
        if len(shared_sigs[i]) == 1:
            return f"{name} {counts[i][0]:,}"
        return (f"{name}: {len(shared_sigs[i])} DIFFERENT versions across "
                f"parts ({min(counts[i]):,}-{max(counts[i]):,} tokens) — "
                f"should be one")

    L = ["", "  SYSTEM PROMPT, in tokens"
         + ("" if measured else "  (ESTIMATED — see the note below)"), "",
         "  circle briefing (shared, cached):  "
         + " + ".join([shared_line(0, "practices"),
                       shared_line(1, "objectives")]),
         ""]
    head = f"  {'part':<14}{'part':>10}{'todo':>10}{'total':>9}"
    if since_self is not None:
        head += f"{'round':>8}"
    L.append(head)
    for p in parts:
        row = f"  {PART_TAGS.get(p, p):<14}"
        vals = per_part[p]
        tot = sum(vals.values())
        row += f"{vals.get(2, 0):>10,}{vals.get(3, 0):>10,}{tot:>9,}"
        if since_self is not None:
            row += f"{f'{since_self.get(p, 0)}/{MAX_SINCE_SELF}':>8}"
        L.append(row)
    if not measured:
        L += ["", "  These are ESTIMATES at "
              f"{TC.CHARS_PER_TOKEN:.1f} characters per token, not counts — "
              "no circle", "  is calling the model service. A live circle "
              "asks it and reports what it says."]
    return "\n".join(L)


def addressed_since(transcript: list[dict], part: str) -> bool:
    """Has `part` been addressed BY NAME since it last spoke?

    `[To: Part]` is the marker; `render_messages` already shows it to every
    listener, so being addressed is a fact the room can see. Only statements
    after this part's own last one count — an address it has already answered
    is spent.

    A WITHHELD ENTRY IS NOT A FACT THE ROOM CAN SEE, so it counts for
    neither half (2026-08-18). Left in, a remember-only turn would set
    `last` and spend an address this part never heard answered, and a
    withheld `to` would read as an address nobody was shown. Same predicate
    as render_messages/rebuild_state/statements — transcript_store.withheld()
    exists because these four have to agree and used to do so by accident."""
    tag = PART_TAGS.get(part, "")
    last = -1
    for i, e in enumerate(transcript):
        if e["speaker"] == part and not withheld(e):
            last = i
    for e in transcript[last + 1:]:
        if withheld(e):
            continue
        if e.get("to") and tag.lower() in str(e["to"]).lower():
            return True
    return False


def run_round(client, parts, sysblocks, transcript, since_self, state,
              guard, path, dry, *, live: bool) -> int:
    """One SEQUENTIAL round. See run_blind_round for round 1.

    Parts are polled in shuffled order and each statement is appended before the
    next part is asked, so parts genuinely respond to one another within a round.
    Enforces, in code:
      - max 2 statements since Self last spoke
      - never speak twice in a row"""
    order = parts[:]
    random.shuffle(order)
    spoke = 0
    for part in order:
        if since_self.get(part, 0) >= MAX_SINCE_SELF \
                and not addressed_since(transcript, part):
            continue
        if state["last"] == part:
            continue
        # B24, ruled and unbuilt until 2026-08-05. A part ADDRESSED BY NAME
        # since it last spoke may answer even at the two-statement limit.
        # Being addressed and having nothing left to spend was a silence the
        # room could not distinguish from a pass — and the addressing part
        # got no reply, which reads as a snub rather than a budget.
        text, to = ask_statement(client, part, sysblocks[part], transcript, dry)
        display = PART_TAGS[part]
        if text is None:
            seam.emit("command", f"  {display}: (passes)")
            seam.emit("circle", f"\n{display} passes")
            continue
        raw = text
        text, recorded = apply_remember(guard, part, display, text)
        why = " — REMEMBER recorded)" if recorded else ")"
        if text:
            text = strip_malformed_markers(text, display)
            if not text:
                why = " — malformed marker only)"
        if not text:
            # THE TURN IS STILL A PASS — RULED 2026-08-18, and deliberately
            # unchanged: no since_self increment, no state["last"], no
            # statement spent, the part said nothing the room can hear.
            # What DID change is that the RECORD no longer loses the bracket.
            # It was the one case the 2026-08-14 retention ruling could not
            # reach, because a pass wrote no line at all.
            #
            # `remember_only` is what keeps the pass a pass everywhere the
            # entry is later read — see transcript_store.withheld(). The file
            # line is indistinguishable from an ordinary statement, which is
            # why the flag is RE-DERIVED on resume rather than stored.
            record = strip_malformed_markers(raw.strip(), display, quiet=True)
            if record and REMEMBER_RE.search(raw):
                transcript.append({"speaker": part, "display": display,
                                   "text": "", "raw": record,
                                   "remember_only": True, "to": to})
                append(guard, path, statement_line(display, to, record))
            seam.emit("command", f"  {display}: (passes{why}")
            seam.emit("circle", f"\n{display} passes")
            continue
        # THE ROOM AND THE RECORD PART COMPANY HERE. Ruled 2026-08-14, built
        # 2026-08-18 (docs/BNF.md, REMEMBER). `text` is the ROOM's: the
        # bracket is gone, and it is what the transcript ENTRY carries, what
        # render_messages() rebuilds every part's view from, and what
        # route_markers() reads. The circle PANE shows for_display(text) --
        # the same string with its whitespace-only lines dropped, 2026-08-20,
        # and that transform reaches nothing else. `record` is
        # COORDINATOR's: this part's own statement with the remember bracket
        # intact — valid or malformed alike — and it goes to the transcript
        # FILE and nowhere else.
        #
        # ONLY A STATEMENT THAT ACTUALLY CARRIES A BRACKET TAKES THE SECOND
        # PATH. apply_remember() collapses runs of spaces and blank lines as
        # part of removing a bracket, and that collapse has reached the file
        # since the day it was written; re-deriving `record` from the raw
        # text unconditionally would quietly stop collapsing them and rewrite
        # the shape of every ordinary statement. The guard keeps this change
        # to exactly the statements the ruling is about.
        #
        # `quiet`: the room pass above already warned about each malformed
        # marker. Two notices for one bracket read as two brackets.
        record = text
        if REMEMBER_RE.search(raw):
            record = strip_malformed_markers(raw.strip(), display, quiet=True)
        since_self[part] = since_self.get(part, 0) + 1
        state["last"] = part
        entry = {"speaker": part, "display": display, "text": text, "to": to}
        if record != text:
            entry["raw"] = record
        transcript.append(entry)
        append(guard, path, statement_line(display, to, record))
        seam.emit("circle", f"\n{statement_line(display, to, for_display(text))}")
        route_markers(display, text, live=live)
        spoke += 1
    held = [PART_TAGS[p] for p in parts
            if since_self.get(p, 0) >= MAX_SINCE_SELF
            and not addressed_since(transcript, p)]
    if held:
        note = (f"[{', '.join(held)} at the two-statement limit — "
                f"holding until Self re-engages.]")
        transcript.append({"speaker": "__scribe__", "display": "Scribe", "text": note})
        append(guard, path, note)
        # RULED 2026-08-13: "do not echo part protocol machinery to Self" —
        # see run_blind_round's BLIND_CLOSE note. No seam.emit() here either.
    if not spoke:
        seam.emit("command", "  (silence — every part passed or is holding)")
    return spoke
