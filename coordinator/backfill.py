#!/usr/bin/env python3
"""
backfill.py — the transcript safety net: a part that SPOKE never reads as silent.

WHAT THIS IS FOR. A part's short_term is written at close. If that write is
lost, or lands malformed, the part is INDISTINGUISHABLE downstream from a part
that was silent — `part_dreaming.part_dream()` guards on a bare
`if st_path.is_file():`, and silence is a designed, legal, non-SUSPECT outcome
("an unchanged document and an empty MEMORY"). So the register gate passes,
the close passes, and that part's identity simply does not move for that
circle. No error anywhere.

A MALFORMED RECORD IS WORSE THAN A MISSING ONE: `is_file()` is true, so it is
fed to dreaming unrepaired and unflagged.

WHY IT IS ITS OWN MODULE. B54, 2026-08-19. The detect half lived in
circle_audit.py's phase 2 and the repair half in its phase 3, entangled with
that file's Run/phase/transaction machinery and callable by nothing else — and
NOTHING CALLED EITHER on the path that now matters. `circle_process()` runs
synchronously at every live `/close` (B3/R189) and did neither, with dreaming
as the first thing it does. The logic moved here so both drivers share ONE
implementation: circle_audit at audit time, inter_circle as step 0 of every
live close.

THE ORDERING IS LOAD-BEARING AND WAS ALREADY WRITTEN DOWN. circle_audit's own
failure text says *"backfill from the transcript before dreaming"*. Any fix
that runs after dreaming repairs the file and not the dream, which is the part
that mattered.

THE MODEL CALL IS INJECTED, not built here. inter_circle has `_call` and
circle_audit has its own; this module takes whichever the caller has, in one
shape, so neither driver has to adopt the other's.

BOTH OF THOSE ARE NOW llm_client.stream_call_once — 2026-08-28, stage 1 of the
provider socket. This paragraph said circle_audit "builds its own
`Anthropic()`", which was true and is the thing that changed: five modules
each had their own client, none of them on the retry ladder or the meter.
The injection contract here is untouched; what the two callers inject is now
the same function.
"""
from __future__ import annotations

import pathlib

import record_model as M
import part_roster as R
import short_term_manager as STM
import record_paths as _RP                                         # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

STATEMENT_RE = R.statement_re(R.TAGS)


@_RP.group_follow
def _grammar_rebind() -> None:
    """The CURRENT group's Tags — B117 stage 5 (2026-09-07): compiled once at import for the
    default group, recompiled after record_paths.group_set() so a band close backfills its own
    roster's statements."""
    global STATEMENT_RE
    STATEMENT_RE = R.statement_re(R.TAGS)


# The reply is four prose sections for a whole circle. 16,000 was set in
# circle_audit and is kept rather than re-guessed — see the stop_reason check
# in `reconstruct`, which is what actually catches a ceiling set too low.
BACKFILL_MAX_TOKENS = 16000

BACKFILL_PROMPT = (
    "The record of this circle you were asked for at close was lost before it "
    "reached disk. Write it again now, from the transcript above.\n\n"
    "Ground 'What I said' and 'What I observed in others' in what is actually in "
    "the transcript — your own lines for the first, the other parts' for the "
    "second. 'Shifts' and 'Current emotional state' are yours to say.\n\n"
    "Reply with the four sections and nothing else:\n\n"
    "## What I said\n## What I observed in others\n"
    "## Shifts toward other parts\n## Current emotional state\n\n"
    "Begin with '## What I said'."
)


def part_spoke_read(transcript: pathlib.Path) -> dict[str, int]:
    """part dir -> how many statements it made. The transcript is the
    authoritative account of what was said, which is what makes it the thing
    to check a missing record against."""
    counts: dict[str, int] = {}
    try:
        text = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    for line in text.splitlines():
        m = STATEMENT_RE.match(line)
        if m:
            d = R.DIR_BY_TAG[m.group(1)]
            counts[d] = counts.get(d, 0) + 1
    return counts


# MOVED AGAIN, 2026-09-04 (B96, R434): to short_term_manager.py, the record's one
# reader/writer, so the .toml branch and the legacy .md branch draw the same
# well-formed line through the same parser the close writes with. It came here
# from record_model.py on 2026-09-03 (cohesion re-homing, stage 4). The name stays
# reachable as BF.short_term_verify — both callers here and the suite use it.
short_term_verify = STM.short_term_verify


def short_term_backfill_path(part: str, ot: str) -> pathlib.Path:
    """Where this part's record of this circle is, or where a repair goes: the
    existing file whatever its suffix (a malformed record is repaired IN PLACE),
    else the format the circle's OTHER parts are in, else the live format —
    .toml since R434. One rule for the text and the path, so the two callers
    (inter_circle's step 0, circle_audit's phase 3) cannot disagree."""
    return STM.short_term_path_new(_RP.record_dir(ROOT, "parts"), part, ot)


def short_term_needs_backfill(ot: str) -> list[tuple[str, int, str]]:
    """[(part, statements, why)] for every part that SPOKE in this circle and
    has no well-formed record.

    A SILENT PART IS NOT HERE, and that exemption is load-bearing: absence for
    a part that never spoke is correct, not a loss, and writing one a record
    would FABRICATE engagement it never had.

    Malformed counts as missing — `check_short_term` already draws that line
    (four sections, in order, each with something under it), and an empty
    section is exactly the shape that passes a naive "are the headings there"
    test while telling a reader nothing."""
    out: list[tuple[str, int, str]] = []
    transcript = _RP.record_dir(ROOT, "circles") / f"circle_{ot}.md"
    for part, n in sorted(part_spoke_read(transcript).items()):
        f = short_term_backfill_path(part, ot)
        bad = [x for x in short_term_verify(f.as_posix(), M.record_bytes_read(f),
                                             part, ot) if x.level == "FAIL"]
        if bad:
            out.append((part, n, f"{bad[0].code}: {bad[0].message}"))
    return out


def short_term_header_render(part: str, ot: str, tag: str) -> str:
    """The reconstruction's own header, carrying the R248 mark.

    THE MARK IS THE POINT, not the sentence around it. `record_model` owns the
    literal and the reader (`is_reconstructed`), so the thing that writes it
    and the things that act on it cannot drift apart — which is what the old
    prose-only note allowed, since nothing parsed it. The sentence itself is
    short_term_manager's since B96: a .toml carries `reconstructed = true`
    instead, and renders this same header back when a prompt needs it."""
    return STM.short_term_header_render(tag, ot, reconstructed=True)


def short_term_backfill(part: str, ot: str, tag: str, system: str,
                call) -> tuple[str, str | None]:
    """Write one part's short_term again, from the transcript. Returns
    (text, error) — exactly one of them is meaningful.

    `call(system, user_text, max_tokens) -> LLM_response_disassembler.Reply`
    is the caller's own model path.

    THIS VALIDATES WHAT CAME BACK, because the failure it guards against is
    silent: this model charges thinking against max_tokens, so a ceiling sized
    for the answer alone can be consumed before any text is produced and the
    reply arrives EMPTY rather than truncated (found 2026-07-27, an 8,000
    ceiling returning zero characters for a ~2,500-token answer). A
    reconstruction that is not checked is the loss it was meant to repair,
    with a file in front of it."""
    transcript_path = _RP.record_dir(ROOT, "circles") / f"circle_{ot}.md"
    try:
        transcript = transcript_path.read_text(encoding="utf-8")
    except OSError as e:
        return "", f"cannot read {transcript_path.name}: {e}"
    user = (f"## Transcript of circle_{ot}\n\n{transcript}\n\n"
            f"{BACKFILL_PROMPT}")
    reply = call(system, user, BACKFILL_MAX_TOKENS)
    body = reply.text.strip()
    if reply.truncated or not body:
        return "", (f"stop_reason={reply.raw_stop}, {len(body)} chars of text — "
                    f"the record was not produced. Raise BACKFILL_MAX_TOKENS "
                    f"if this recurs.")
    # THE CIRCLE'S OWN FORMAT (B96, R434): the text is rendered for the path
    # short_term_backfill_path() names — .toml beside .toml siblings, .md into a
    # legacy circle — and verified under that name, through the one reader.
    dest = short_term_backfill_path(part, ot)
    rec = STM.short_term_record_build(part, tag, ot, body, reconstructed=True)
    out = STM.short_term_render(rec, STM.FORMAT_NEW if dest.suffix == ".toml"
                                else STM.FORMAT_LEGACY)
    rel = dest.relative_to(ROOT).as_posix()
    bad = [x for x in short_term_verify(rel, out.encode("utf-8"), part, ot)
           if x.level == "FAIL"]
    if bad:
        return "", f"regenerated record is malformed — {bad[0].code}: {bad[0].message}"
    return out, None


# --------------------------------------------------------------- what it costs
# PRICED FROM THE LIVE RATE TABLE, not from a number typed once — 2026-08-28.
# circle_audit's --dry-run said "~${len(todo) * 0.03}", a per-item price
# hardcoded inside a print. Two things were wrong with it: rates rise on
# 2026-09-01 and nothing would have moved it, and it was WRONG ANYWAY —
# roughly half, as the measured sizes below show.
#
# THE SIZES ARE MEASURED AND NAMED, so the assumption is visible rather than
# buried in an arithmetic expression. From circle 2026-08-21_1139's own
# captures: a short_term's reply ran a median of 1,116 output tokens, and a
# part's request carried 24,651 input tokens (10,139 written to cache +
# 14,512 read from it).
#
# A BACKFILL PAYS FULL PRICE FOR ALL OF IT. It runs outside a circle, so there
# is no warmed prefix to read from and every input token is uncached — which
# is exactly why the old estimate was low.
TYPICAL_INPUT_TOKENS = 24_651
TYPICAL_OUTPUT_TOKENS = 1_116


def short_term_backfill_cost_estimate(n: int) -> float:
    """Roughly what `n` backfills cost, in dollars, at whatever the rate table
    currently says. AN ESTIMATE, and labelled as one wherever it prints: a
    part that spoke twice has a longer transcript to reconstruct from than one
    that spoke once, and nothing here knows which."""
    import llm_client as LC
    r_in, _cw, _cr, r_out = LC.stream_rates_read(LC.MODEL)
    per = (TYPICAL_INPUT_TOKENS * r_in
           + TYPICAL_OUTPUT_TOKENS * r_out) / 1_000_000
    return n * per
