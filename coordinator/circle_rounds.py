#!/usr/bin/env python3
"""
circle_rounds.py — the circle's turn engine (rounds.py until 2026-09-03, R7 under
the <CLASS>_<process> standard, R435): part_statement_ask (a part's one
statement, truncation-marked rather than lost), the blind opening
round and the sequential rounds after it, the since-Self scheduler
guard, and /tokens' per-part block table (part_token_table — Self's
explicit ruling placed it here, with the lifecycle that owns the
blocks it measures). Phase 2 stage 7, the last extraction of the
coordinator partitioning (2026-08-16); until then all of it lived in
circle.py. Verbatim move — bodies and comments unchanged, except
console output and the failure record go through seam.emit/seam.fail
by attribute access.

RENAMED AT THE MOVE (R436, R442 — 2026-09-03), the class word first, the bodies untouched:

    run_round         -> circle_round_run          run_blind_round  -> circle_blind_round_run
    ask_statement     -> part_statement_ask        addressed_since  -> part_addressed_since
    token_table       -> part_token_table          for_display      -> statement_display
    MAX_TOKENS, MAX_SINCE_SELF, TRUNCATION_MARKER, BLIND_CLOSE   constants, unchanged
    (REVEAL_OPEN retired with the reveal round, R558, 2026-09-11)

This module is the split's KEYSTONE CONSUMER, deliberately last: it
calls the transport (llm_client.stream_call), the prompt view
(prompt_build.prompt_messages_render), the annotation system (annotations'
remember_apply/strip_malformed_annotations/annotation_route) and the
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

import command_surface as CS
import LLM_response_disassembler as RD
import seam
import setting_manager as SET
import token_count as TC
from llm_client import stream_call
import llm_client as LC            # LC.MODEL, read at use: a setting-owned constant is never
                                   # from-imported (a copy the settings refresh cannot reach)
from annotations import (remember_apply, annotation_malformed_strip,
                     annotation_route, REMEMBER_RE)
import recall_index as RC
from record_paths import PART_TAGS
from prompt_build import prompt_messages_render
import process_core_prompt_projection as PCP   # PCP.LENGTH_MAX_WORDS — the length rule's owner
                                                # since the settings refresh; read at use, same rule
from transcript_store import statement_line, circle_transcript_append, circle_transcript_is_withheld

# ~100 words is ~135 tokens; the ceiling is deliberately far above the word cap so
# that hitting it means genuine runaway generation, not a part finishing a slightly
# long thought. Raised 400 -> 600 (2026-07-26): at 400 a part that overran twice was
# silently dropped from the circle, and a dropped statement is unrecoverable — the
# close's backfill cannot distinguish it from chosen silence. Truncation is an error, not a
# statement; see part_statement_ask().
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
MAX_TOKENS = SET.setting_value_read("statement_max_tokens", 2500)
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
MAX_SINCE_SELF = SET.setting_value_read("statements_per_part", 2)   # process_core: max 2
                                        # statements per Self turn

TRUNCATION_MARKER = "[statement truncated at the token ceiling -- incomplete]"


# Meter/METER MOVED to llm_client.py, 2026-08-16 (phase 2 stage 1) -
# the usage meter and its lock; METER here is the SAME instance,
# imported at the top of this file (mutated in place, never
# reassigned - the seam.FAILURES contract).

# ------------------------------------------------------------------ API
# stream_call(), the API preflight ladder (BACKOFF/_transient/with_backoff/
# _no_sdk_retries), the key diagnostics (key_source_note/
# explain_api_failure; the _env_file_key/_mask wrappers went to the
# provider and were retired 2026-09-03), preflight_api() and prewarm()
# MOVED to llm_client.py, 2026-08-16 (phase 2 stage 1) - verbatim,
# comments and the 2026-08-09 ruling included. part_statement_ask below
# STAYS: round-logic wearing an API call (goes with rounds, stage 7).
#
# _TO_RE/_SELFNAME_RE/_TRAILING_PASS_RE and the whole-text pass test MOVED
# to LLM_response_disassembler.message_statement_read(), 2026-09-02 — they parse the
# REPLY, and every read of a reply lives there now. The retry policy stays
# here: which request to make again is round logic.


def statement_pass_announce(display: str, why: str = ")") -> None:
    """A part passed: the coordinator's line, and the room's — where there is
    a room distinct from the coordinator's pane.

    TWO CHANNELS, ONE FACT, AND THEY ONLY COLLIDE IN ONE WINDOW. The operator,
    2026-09-09: *"A circle shows this pattern or redundant output: '  Judge:
    (passes) / Judge passes'. I prefer the first line only."* In the two-pane
    UI and in the Ticker these land in different places and neither repeats the
    other. In a standalone terminal both channels print to one stdout — three
    lines, in fact, since the circle emit carries a leading newline — and there
    the pair is exactly the repetition he read.

    SO THE ROOM LINE IS SUPPRESSED ONLY WHERE THERE IS NO COMMAND PANE, and
    that is not squeamishness about a preference. The room half is the NEWER
    and TWICE-RULED half. R262 (2026-08-20) added it because `(passes)` went to
    the COMMAND channel alone — *"the one place a pass was reported was the
    pane the circle does not read"* — and R272, VERBATIM, is his own: *"A part
    that passes writes NOTHING to the transcript; the room names it —
    `Mourner passes` — and the record stays silent."* Dropping it everywhere
    would reverse both, blank the two-pane room when a part passes, and
    silently break the Ticker's front end, which matches the literal
    `<Tag> passes` to push a pass into its live corpus and is seen by no gate
    in this project.

    THE COMMAND LINE IS THE ONE THAT CAN SAY WHY. `why` closes its own
    parenthesis and carries the reason a post-strip pass emptied — a remember
    recorded, a recall asked, a malformed annotation alone. The room line is
    always the bare attribution."""
    seam.emit("command", f"  {display}: (passes{why}")
    if seam.COMMAND_PANE:
        seam.emit("circle", f"\n{display} passes")


def statement_display(text: str) -> str:
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


def part_statement_ask(client, part: str, blocks: list[dict], transcript: list[dict],
                  dry: bool) -> tuple[str | None, str | None]:
    """Returns (statement, to_whom) or (None, None) for a pass."""
    # POPPED ONCE, REUSED FOR THE RETRY (B82, 2026-08-31). recall_index's own
    # docstring already promised a SINGLE delivery ("the latest
    # <recall_result>... appended to the tail"); nothing enforced it before
    # this, and the same reply rode along, unexpired, on every later turn of
    # a circle. Capturing it here — rather than re-reading RC.recall_pending_read()
    # at each call site — clears it from the pending slot immediately while
    # still giving the truncation-retry below the SAME value: a retry is the
    # same turn asked again, not a second delivery.
    recall = RC.recall_pending_pop(part)
    reply = stream_call(client, part, blocks,
                 prompt_messages_render(part, transcript, recall=recall),
                 MAX_TOKENS, dry)
    if reply.truncated:
        # Truncation is a failure, not a statement. One retry, then give up.
        seam.emit("command", f"  [{part} ran long — asking again, shorter]")
        # THE NUMBER IS THE ROOM'S OWN, 2026-08-28. This said "UNDER 150
        # words" as a literal while process_core.md told the same part never
        # to exceed 100 — the retry contradicting the rulebook, in the one
        # moment a part is being corrected. Both read LENGTH_MAX_WORDS now.
        msgs = prompt_messages_render(
            part, transcript,
            f"(the circle comes to you — speak in UNDER {PCP.LENGTH_MAX_WORDS} "
            f"words and finish your sentence, or reply [pass])",
            recall=recall,
        )
        reply = stream_call(client, part, blocks, msgs, MAX_TOKENS, dry)
        if reply.truncated:
            # Do NOT downgrade a truncation to a pass. A part that tried to speak
            # and was cut off would otherwise be indistinguishable from a part that
            # chose silence — and the close's own transcript safety net deliberately
            # exempts genuinely silent parts, so nothing downstream would ever catch
            # it. That was the one data-loss path in this pipeline with no net.
            # Keep what was said and mark it: the marker is line-TRAILING, so
            # circle_close_verify.py::parts_that_spoke() still counts the statement, the
            # part still writes a short_term, and dreaming still sees engagement.
            if not reply.empty:
                # NAMES WHAT ACTUALLY RUNS — audit-register.md #9, 2026-09-08. This said
                # "review before the nightly runs", and there is no nightly: the tool was
                # renamed circle_audit.py on 2026-08-19 and the batch shape it implemented
                # was removed by R228. Worse, the instruction was pointless as well as
                # wrong — the transcript safety net
                # (inter_circle.short_term_backfill_step) runs automatically at every live
                # close, so by the time anyone reads this line the repair has already
                # happened. Telling the operator to act before a thing that does not exist,
                # on the one unrecoverable data-loss path in the pipeline, is the worst place
                # in the tree to be carrying a retired name.
                seam.fail(f"{PART_TAGS[part]} truncated twice at {MAX_TOKENS} tokens — "
                     f"incomplete statement KEPT and marked in the transcript; "
                     f"the close's own backfill will not touch it — review it yourself")
                return RD.message_statement_read(reply.text.strip() + " " + TRUNCATION_MARKER)
            seam.fail(f"{PART_TAGS[part]} truncated twice at {MAX_TOKENS} tokens with "
                 f"no recoverable text — statement LOST; this part may now read "
                 f"as silent to the close's own backfill "
                 f"(inter_circle.short_term_backfill_step), which exempts a genuinely "
                 f"silent part")
            return None, None
    return RD.message_statement_read(reply.text)


# --------------------------------------------- transcript file + working set
# MOVED to transcript_store.py, 2026-08-16 (phase 1 step 3): write_lf,
# open_transcript, append, the working-set history and the no-trace
# discard of an unspoken open, statement_line, and the whole resume
# cluster (render_line/render_transcript/parse_transcript/
# circle_transcript_state_rebuild/load_for_resume) - verbatim, comments included. The
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

# THE REVEAL ROUND IS RETIRED — R558, 2026-09-11. R095
# (2026-08-05) handed the blind block back to every part for one more
# statement each; in the last three circles that ran it (2026-08-21, 09-09,
# 09-10) that round was mostly the parts telling each other they had all said
# the same thing — all seven statements on 2026-09-10. The open is one
# statement per part. The blind statements reach every part with Self's next
# statement, as every statement does. `[REVEAL` lines in the record from
# 2026-08-06 to 2026-09-11 are read by circling_verify.py and written by nothing.


def circle_blind_round_run(client, parts, sysblocks, transcript, since_self, state,
                    guard, path, dry, *, live: bool) -> int:
    """Round 1, parallel and blind. Returns the number of statements made.

    Every part is asked against `snapshot`, a copy of the transcript as it stood
    before the round — so a statement made during the round cannot reach any
    other part, whatever order the threads finish in. The append order is the
    shuffled order, not the completion order, so a run is reproducible under
    --seed and the transcript does not record network timing as if it were
    conversational order."""
    RC.recall_round_reset()
    order = parts[:]
    random.shuffle(order)
    snapshot = list(transcript)          # frozen: nothing said now is visible now
    results: dict[str, tuple] = {}

    def ask(part):
        return part, part_statement_ask(client, part, sysblocks[part], snapshot, dry)

    if CS.dev_mode:
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
            statement_pass_announce(display)
            continue
        raw = text
        text, recorded = remember_apply(guard, part, display, text)
        # RECALL rides the same discipline, after remember (R402): the
        # bracket is stripped from the room here, the query executes, and
        # the private reply waits for this part's next request.
        text, asked = RC.recall_apply(part, display, text, live=live)
        notes = (["REMEMBER recorded"] if recorded else []) \
            + (["RECALL asked"] if asked else [])
        why = (" — " + ", ".join(notes) + ")") if notes else ")"
        if text:
            text = annotation_malformed_strip(text, display)
            if not text:
                why = " — malformed annotation only)"
        if not text:
            # THE TURN IS STILL A PASS — RULED 2026-08-18, and deliberately
            # unchanged: no since_self increment, no state["last"], no
            # statement spent, the part said nothing the room can hear.
            # What DID change is that the RECORD no longer loses the bracket.
            # It was the one case the 2026-08-14 retention ruling could not
            # reach, because a pass wrote no line at all.
            #
            # `remember_only` is what keeps the pass a pass everywhere the
            # entry is later read — see transcript_store.circle_transcript_is_withheld(). The file
            # line is indistinguishable from an ordinary statement, which is
            # why the flag is RE-DERIVED on resume rather than stored.
            record = annotation_malformed_strip(raw.strip(), display, quiet=True)
            if record and (REMEMBER_RE.search(raw)
                           or RC.RECALL_RE.search(raw)):
                entry = {"speaker": part, "display": display,
                         "text": "", "raw": record, "to": to}
                if REMEMBER_RE.search(raw):
                    entry["remember_only"] = True
                if RC.RECALL_RE.search(raw):
                    entry["recall_only"] = True
                transcript.append(entry)
                circle_transcript_append(guard, path, statement_line(display, to, record))
            statement_pass_announce(display, why)
            continue
        # THE ROOM AND THE RECORD PART COMPANY HERE. Ruled 2026-08-14, built
        # 2026-08-18 (docs/BNF.md, REMEMBER). `text` is the ROOM's: the
        # bracket is gone, and it is what the transcript ENTRY carries, what
        # prompt_messages_render() rebuilds every part's view from, and what
        # annotation_route() reads. The circle PANE shows statement_display(text) --
        # the same string with its whitespace-only lines dropped, 2026-08-20,
        # and that transform reaches nothing else. `record` is
        # COORDINATOR's: this part's own statement with the remember bracket
        # intact — valid or malformed alike — and it goes to the transcript
        # FILE and nowhere else.
        #
        # ONLY A STATEMENT THAT ACTUALLY CARRIES A BRACKET TAKES THE SECOND
        # PATH. remember_apply() collapses runs of spaces and blank lines as
        # part of removing a bracket, and that collapse has reached the file
        # since the day it was written; re-deriving `record` from the raw
        # text unconditionally would quietly stop collapsing them and rewrite
        # the shape of every ordinary statement. The guard keeps this change
        # to exactly the statements the ruling is about.
        #
        # `quiet`: the room pass above already warned about each malformed
        # annotation. Two notices for one bracket read as two brackets.
        record = text
        if REMEMBER_RE.search(raw) or RC.RECALL_RE.search(raw):
            record = annotation_malformed_strip(raw.strip(), display, quiet=True)
        since_self[part] = since_self.get(part, 0) + 1
        state["last"] = part
        entry = {"speaker": part, "display": display, "text": text, "to": to}
        if record != text:
            entry["raw"] = record
        transcript.append(entry)
        circle_transcript_append(guard, path, statement_line(display, to, record))
        seam.emit("circle", f"\n{statement_line(display, to, statement_display(text))}")
        annotation_route(display, text, live=live)
        spoke += 1

    note = BLIND_CLOSE.format(n=spoke)
    transcript.append({"speaker": "__coordinator__", "display": "Coordinator", "text": note})
    circle_transcript_append(guard, path, note)
    # RULED 2026-08-13: "do not echo part protocol machinery to Self." This
    # note is a coordinator/LLM-part implementation detail — the room needs
    # it (prompt_messages_render() carries every __coordinator__ line into each part's
    # rebuilt prompt) and the record needs it (the two lines above, both
    # unconditional), but no interface shows it to Self as circle dialog.
    # No seam.emit() at all, on any channel.
    if not spoke:
        seam.emit("command", "  (silence — every part passed)")
    # `last` IS CLEARED. The blind statements were simultaneous, so no part
    # spoke last; leaving `last` set would deny the next round to whichever
    # part the shuffle happened to append last — the never-speak-twice-in-a-row
    # rule applied to a turn nobody took after. The reveal round that once ran
    # here is retired (R558, 2026-09-11 — the note after
    # BLIND_CLOSE); every part leaves the open at one statement of its cap.
    state["last"] = None
    return spoke


def part_token_table(parts: list[str], sysblocks: dict, since_self: dict | None = None,
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
        got, ok = TC.block_tokens(client, blocks, model or LC.MODEL, dry)
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
         # "circle briefing" UNTIL 2026-09-08 (audit-register.md #26): one printed line
         # named the block two ways, because its own sub-count below already says
         # "objectives". <circle_objectives> is the BNF's name for it, and
         # self/circle_briefing.md — the file the old label came from — retired 2026-08-11.
         # circle_briefing_build() and the `briefing` parameter keep their names: those are
         # pinned by the grammar and are not drift. The LABEL was.
         "  circle identity + objectives (shared, cached):  "
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


def part_addressed_since(transcript: list[dict], part: str) -> bool:
    """Has `part` been addressed BY NAME since it last spoke?

    `[To: Part]` is the annotation; `prompt_messages_render` already shows it to every
    listener, so being addressed is a fact the room can see. Only statements
    after this part's own last one count — an address it has already answered
    is spent.

    A WITHHELD ENTRY IS NOT A FACT THE ROOM CAN SEE, so it counts for
    neither half (2026-08-18). Left in, a remember-only turn would set
    `last` and spend an address this part never heard answered, and a
    withheld `to` would read as an address nobody was shown. Same predicate
    as prompt_messages_render/circle_transcript_state_rebuild/statements — transcript_store.circle_transcript_is_withheld()
    exists because these four have to agree and used to do so by accident."""
    tag = PART_TAGS.get(part, "")
    last = -1
    for i, e in enumerate(transcript):
        if e["speaker"] == part and not circle_transcript_is_withheld(e):
            last = i
    for e in transcript[last + 1:]:
        if circle_transcript_is_withheld(e):
            continue
        if e.get("to") and tag.lower() in str(e["to"]).lower():
            return True
    return False


def circle_round_run(client, parts, sysblocks, transcript, since_self, state,
              guard, path, dry, *, live: bool) -> int:
    """One SEQUENTIAL round. See circle_blind_round_run for round 1.

    Parts are polled in shuffled order and each statement is appended before the
    next part is asked, so parts genuinely respond to one another within a round.
    Enforces, in code:
      - max 2 statements since Self last spoke
      - never speak twice in a row
      - one recall per part per round (recall_index.recall_round_reset())"""
    RC.recall_round_reset()
    order = parts[:]
    random.shuffle(order)
    spoke = 0
    for part in order:
        if since_self.get(part, 0) >= MAX_SINCE_SELF \
                and not part_addressed_since(transcript, part):
            continue
        if state["last"] == part:
            continue
        # B24, ruled and unbuilt until 2026-08-05. A part ADDRESSED BY NAME
        # since it last spoke may answer even at the two-statement limit.
        # Being addressed and having nothing left to spend was a silence the
        # room could not distinguish from a pass — and the addressing part
        # got no reply, which reads as a snub rather than a budget.
        text, to = part_statement_ask(client, part, sysblocks[part], transcript, dry)
        display = PART_TAGS[part]
        if text is None:
            statement_pass_announce(display)
            continue
        raw = text
        text, recorded = remember_apply(guard, part, display, text)
        # RECALL rides the same discipline, after remember (R402): the
        # bracket is stripped from the room here, the query executes, and
        # the private reply waits for this part's next request.
        text, asked = RC.recall_apply(part, display, text, live=live)
        notes = (["REMEMBER recorded"] if recorded else []) \
            + (["RECALL asked"] if asked else [])
        why = (" — " + ", ".join(notes) + ")") if notes else ")"
        if text:
            text = annotation_malformed_strip(text, display)
            if not text:
                why = " — malformed annotation only)"
        if not text:
            # THE TURN IS STILL A PASS — RULED 2026-08-18, and deliberately
            # unchanged: no since_self increment, no state["last"], no
            # statement spent, the part said nothing the room can hear.
            # What DID change is that the RECORD no longer loses the bracket.
            # It was the one case the 2026-08-14 retention ruling could not
            # reach, because a pass wrote no line at all.
            #
            # `remember_only` is what keeps the pass a pass everywhere the
            # entry is later read — see transcript_store.circle_transcript_is_withheld(). The file
            # line is indistinguishable from an ordinary statement, which is
            # why the flag is RE-DERIVED on resume rather than stored.
            record = annotation_malformed_strip(raw.strip(), display, quiet=True)
            if record and (REMEMBER_RE.search(raw)
                           or RC.RECALL_RE.search(raw)):
                entry = {"speaker": part, "display": display,
                         "text": "", "raw": record, "to": to}
                if REMEMBER_RE.search(raw):
                    entry["remember_only"] = True
                if RC.RECALL_RE.search(raw):
                    entry["recall_only"] = True
                transcript.append(entry)
                circle_transcript_append(guard, path, statement_line(display, to, record))
            statement_pass_announce(display, why)
            continue
        # THE ROOM AND THE RECORD PART COMPANY HERE. Ruled 2026-08-14, built
        # 2026-08-18 (docs/BNF.md, REMEMBER). `text` is the ROOM's: the
        # bracket is gone, and it is what the transcript ENTRY carries, what
        # prompt_messages_render() rebuilds every part's view from, and what
        # annotation_route() reads. The circle PANE shows statement_display(text) --
        # the same string with its whitespace-only lines dropped, 2026-08-20,
        # and that transform reaches nothing else. `record` is
        # COORDINATOR's: this part's own statement with the remember bracket
        # intact — valid or malformed alike — and it goes to the transcript
        # FILE and nowhere else.
        #
        # ONLY A STATEMENT THAT ACTUALLY CARRIES A BRACKET TAKES THE SECOND
        # PATH. remember_apply() collapses runs of spaces and blank lines as
        # part of removing a bracket, and that collapse has reached the file
        # since the day it was written; re-deriving `record` from the raw
        # text unconditionally would quietly stop collapsing them and rewrite
        # the shape of every ordinary statement. The guard keeps this change
        # to exactly the statements the ruling is about.
        #
        # `quiet`: the room pass above already warned about each malformed
        # annotation. Two notices for one bracket read as two brackets.
        record = text
        if REMEMBER_RE.search(raw) or RC.RECALL_RE.search(raw):
            record = annotation_malformed_strip(raw.strip(), display, quiet=True)
        since_self[part] = since_self.get(part, 0) + 1
        state["last"] = part
        entry = {"speaker": part, "display": display, "text": text, "to": to}
        if record != text:
            entry["raw"] = record
        transcript.append(entry)
        circle_transcript_append(guard, path, statement_line(display, to, record))
        seam.emit("circle", f"\n{statement_line(display, to, statement_display(text))}")
        annotation_route(display, text, live=live)
        spoke += 1
    held = [PART_TAGS[p] for p in parts
            if since_self.get(p, 0) >= MAX_SINCE_SELF
            and not part_addressed_since(transcript, p)]
    if held:
        note = (f"[{', '.join(held)} at the two-statement limit — "
                f"holding until Self re-engages.]")
        transcript.append({"speaker": "__coordinator__", "display": "Coordinator", "text": note})
        circle_transcript_append(guard, path, note)
        # RULED 2026-08-13: "do not echo part protocol machinery to Self" —
        # see circle_blind_round_run's BLIND_CLOSE note. No seam.emit() here either.
    if not spoke:
        seam.emit("command", "  (silence — every part passed or is holding)")
    return spoke
