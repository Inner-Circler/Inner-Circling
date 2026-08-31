#!/usr/bin/env python3
"""
transcript_store.py — the transcript's persistence and parsing layer,
plus the close/commit recorders. Phase 1 step 3 of the coordinator
partitioning (2026-08-16); until then every function here lived in
circle.py. Verbatim move — bodies and their comments unchanged, except
that console output goes through `seam.emit`/`seam.fail` by attribute
access (the seam contract in seam.py).

WHAT LIVES HERE. Writing the transcript file (write_lf/open_transcript/
append), the working-set history and the no-trace discard of an
unspoken open, the statement line grammar and its exact inverse
(parse_transcript proves itself against render_transcript before any
resume), replaying a transcript back into loop state, and the durable
close records (commit_sandbox/commit_circle/run_verifier).

WHAT DOES NOT. collect_short_terms stays in circle.py — it calls the
Messages API per part, which makes it close ORCHESTRATION; a
persistence module that talks to the network would be the layering
inversion this split exists to prevent (phase-1 review, 2026-08-16).
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

import identity as ID              # SELF_ID + the display name
import roster as R
import seam
import self_schema as SS
from paths import ROOT, SANDBOX, SELF_DIR
from write_guard import WriteGuard

# THIS IS A DISPLAY NAME ONLY (R132/R144 — see circle.py's config
# block). Every comparison uses ID.SELF_ID; CONSOLE_NAME is what this
# installation WRITES and is only consulted here to recognise what it
# has written before (parse_transcript's is_self_tag call).
SELF_DISPLAY = ID.DISPLAY
CONSOLE_NAME = ID.user_name()


# ------------------------------------------------------------------ transcript file
# LF everywhere, explicitly. Python's text mode defaults to newline=None, which on
# Windows translates every "\n" to "\r\n" -- so this script silently wrote CRLF
# while every file reaching the tree through any other route was LF. That is not a
# cosmetic split: circle_close.py records each short_term's sha256 at close and
# re-verifies it at the nightly reconcile, ifs_model.py enforces byte-identical
# dream bodies, and git is the rollback target. All three need bytes to be stable
# and to mean one thing. (Fixed 2026-07-26; the eight CRLF files from
# circle_2026-07-26_1910 are left as-is -- their hashes are already in
# work/logs/close_2026-07-26_1910.json and rewriting them would fake a DRIFT.)
def write_lf(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def open_transcript(guard: WriteGuard, path: pathlib.Path, ot: str, topic: str) -> None:
    guard.check(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    head = f"# Circle — {topic or '(no topic)'} — {ot}\n\n"
    if topic:
        head += f"CIRCLE: {topic}\n"
    write_lf(path, head)


def append(guard: WriteGuard, path: pathlib.Path, line: str) -> None:
    guard.check(path)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write("\n" + line + "\n")


# ------------------------------------------------------------- working set
# Ruled 2026-08-03: "prior to CIRCLE topic the coordinator can accept the input
# of — and keep a history of — the working set selected by me."
#
# `apply_working_set()` REMOVED 2026-08-11: it substituted the `## Issues`
# section into a rendered self/circle_briefing.md. build_briefing(chosen)
# now takes the working set directly and constructs circle_objectives from
# it — there is no rendered file to substitute into. prompt_capture still
# records what was actually sent, so the working set stays recoverable from
# the capture even years later.

WORKING_SETS = SELF_DIR / "working_sets.toml"

# NEXT.md B14, R210 (2026-08-17): working_sets.md -> .toml, the same
# self_schema.py registers under self/ already use. No id, no next_id —
# nothing cites an entry by id, only by its own `circle` field, and the
# register-intake gate (bnf_conformance.py) binds only next_id-bearers.
#
# ONE PREAMBLE, defined once, used by both the lazy-create path below and
# the one-off migration driver that moved the .md file's one row across
# (not checked in — self_schema.py's own docstring names dropping a
# preamble in a format migration as the failure this project keeps
# finding). Wrapped via SS.wrap() at import time, same as every other
# self/*.toml register's preamble — an unwrapped single line would be
# unreadable in a diff and would trip the 116-char line limit.
WORKING_SETS_PREAMBLE = SS.wrap(
    "Which issues each circle was shown, chosen by Self at open. "
    "chosen is \"none\" for no issues at all (the blank answer's meaning "
    "since the default flipped, R301), [] for the whole live graph (all), "
    "or the issue ids. Ruled 2026-08-03. Withdrawn in "
    "the one case ruled 2026-08-09: a circle that died before its first "
    "statement leaves no trace, so its transcript is removed and this "
    "entry with it. An entry naming a transcript that does not exist is "
    "a dangling reference, not a record of what a room was shown. "
    "Nothing else is ever removed, and nothing is ever edited in place.")

WORKING_SET_ORDER = ("circle", "chosen", "topic")


def _working_sets_doc() -> dict:
    if WORKING_SETS.is_file():
        return SS.load(WORKING_SETS)
    return {"register": "working_sets",
            "doc": {"preamble": WORKING_SETS_PREAMBLE}, "working_set": []}


def record_working_set(ot: str, chosen: "list[str] | None", topic: str,
                       live: bool) -> None:
    """Append to self/working_sets.toml. A history, so a later reading of a
    transcript can ask what the room was shown, not only what it said.

    `chosen` carries the working set's three states (ask_working_set):
    None — no issues at all, recorded as the grammar's own word, "none",
    because TOML has no null; [] — the whole live graph; a list — those
    issues. `list(chosen)` unconditionally raised TypeError on None, which
    was every live open whose blank answer took the default — the suites
    never saw it because the sandbox returns before the append.

    topic is stored whole — the truncate-to-100-chars-plus-ellipsis rule
    the .md form used was a display convention for a flat file, not a
    property of the data; the transcript always held the whole thing."""
    if not live:
        return
    WORKING_SETS.parent.mkdir(parents=True, exist_ok=True)
    doc = _working_sets_doc()
    doc["working_set"].append(
        {"circle": ot,
         "chosen": "none" if chosen is None else list(chosen),
         "topic": topic})
    SS.save(WORKING_SETS, doc, "working_set", WORKING_SET_ORDER)


# ------------------------------------------------- discarding an unspoken open
# RULED 2026-08-09: a run that dies before its first statement leaves NO
# TRACE. Self had just deleted two such stubs by hand — circle_2026-08-08_1101
# (killed by the `m.group(1)` NameError) and circle_2026-08-09_1507 (killed by
# a 401 in prewarm) — and ruled that the coordinator should not be making them.
#
# THE TEST IS THE BYTES, not a flag. If the transcript on disk is still
# EXACTLY what open_transcript wrote, nothing was ever said and there is
# nothing to lose. If a single statement landed, the file differs and this is
# a no-op — a partial transcript is a real record, crash-safe by design, and
# resumable. That makes the discard safe to attempt from any exit path rather
# than only from the ones someone remembered to cover.
def _withdraw_working_set(ot: str, live: bool) -> None:
    """Remove this circle's working-set entry. The register's own preamble
    says appended-and-withdrawn: an entry naming a transcript that does not
    exist is not a record of what a room was shown, it is a dangling
    reference. Nothing else reads this file.

    Removes every row matching `ot` rather than only the last (the .md form's
    `rfind` found the LAST occurrence because entries were appended in file
    order and never reordered) — `circle` is unique per open, so the two are
    equivalent in practice; this is the simpler statement of the invariant,
    not a behavior change. atomic_write is LF-only regardless of what wrote
    the bytes it replaces — see its own docstring."""
    if not live or not WORKING_SETS.is_file():
        return
    doc = _working_sets_doc()
    rows = doc.get("working_set", [])
    kept = [row for row in rows if row.get("circle") != ot]
    if len(kept) == len(rows):
        return
    doc["working_set"] = kept
    SS.save(WORKING_SETS, doc, "working_set", WORKING_SET_ORDER)


def discard_empty_open(path: pathlib.Path, ot: str, head: bytes,
                       live: bool) -> bool:
    """True if a transcript that was opened and never spoken in was removed."""
    try:
        if not path.is_file() or path.read_bytes() != head:
            return False
    except OSError:
        return False
    path.unlink()
    _withdraw_working_set(ot, live)
    return True


def statement_line(display: str, to: str | None, text: str) -> str:
    return f"[{display}]" + (f" [To: {to}]" if to else "") + f": {text}"


# ------------------------------------------------------------------ resume
# A circle is one process, and until 2026-08-02 that meant a circle was also one
# uninterrupted sitting: if the process ended, the circle ended. On 2026-08-02 a
# Ctrl-C typed into the wrong window killed circle_2026-08-02_1259 after its
# blind round, and there was no way back into it.
#
# Resuming is legitimate HERE and would not be in most systems, for one reason:
# THE PARTS ARE STATELESS. Each turn is a fresh Messages API call whose entire
# view is rebuilt from the transcript. So the transcript is not a log OF the
# state, it IS the state, and reopening a circle is reconstructing nothing —
# it is reading back the same bytes the next call would have been given anyway.
#
# The one thing that could go wrong is a parser that disagrees with the writer.
# So the parser is written as the exact inverse of `statement_line` + `append`,
# and it PROVES it on the file in front of it: parse, re-render, require the
# bytes to be identical. A transcript that does not round-trip cannot be
# resumed — it is refused, not repaired. That check makes the class of bug
# impossible rather than unlikely, which is the same discipline
# prompt_capture.py applies to the emitted prompt.
#
# Legacy transcripts (June 2026, written by hand before this coordinator
# existed) do not round-trip and are correctly refused: timestamp speakers like
# `[22:10]`, `---` rules, blank lines inside statements. Refusing them is right.
# They are history, not resumable sessions.

_STMT_RE = re.compile(
    r"\[([^\]]+)\](?:\s\[To:\s*([^\]]+)\])?:\s(.*)", re.DOTALL)
_HEAD_RE = re.compile(r"# Circle — (.*) — (\d{4}-\d{2}-\d{2}_\d{4})")
# THE READ DIRECTION ENUMERATES RETIRED SPELLINGS. PART_TAGS is what a new
# statement is WRITTEN as; this is what an existing transcript is READ by,
# and those are not the same set once a tag is renamed. A rename in 2026-08
# broke reading 56 lines carrying the earlier spelling — `unknown speaker
# tag`, raised on a transcript this project wrote itself. The record is
# never rewritten, so the reader has to carry the history. Same shape as
# identity.HISTORICAL_NAMES for Self, and circle_close.TAG_TO_DIR for the
# close verifier.
#
# WHERE THAT HISTORY LIVES IS NOW A PART'S OWN FILE (R123). It was a dict
# typed here, holding one installation's rename in a module that SHIPS; it
# is `alt_tags` in parts/<dir>/part.toml, and roster.DIR_BY_TAG_ALL is the
# read direction assembled from it. Empty in this tree, deliberately —
# ruled 2026-08-08 that the one retired tag is not to be recognised — so
# this changes nothing today and means the next rename needs no code.
TAG_TO_PART = dict(R.DIR_BY_TAG_ALL)


def render_line(e: dict) -> str:
    """The exact line `append` was given for this entry.

    `raw` WINS OVER `text` WHEREVER IT IS PRESENT. Since 2026-08-18 the two
    diverge for exactly one reason: a statement carrying a `[remember: ...]`
    bracket goes to the ROOM stripped (`text`) and to the FILE intact
    (`raw`) — the 2026-08-14 ruling, docs/BNF.md REMEMBER. `append` was
    given `raw`, so reproducing "the exact line" means reproducing `raw`;
    rendering `text` here would silently rewrite the record on every resume
    and fail test_resume's byte-for-byte inverse check — which is the
    intended failure, and the reason this is one lookup rather than a
    caller-by-caller convention."""
    raw = e.get("raw")
    if raw is not None:
        e = {**e, "text": raw}
    if e["speaker"] == "__scribe__":
        return e["text"]
    if e["speaker"] == ID.SELF_ID:
        # THE RECORD'S OWN DISPLAY, NOT THE CONFIGURED NAME. A resumed
        # transcript must re-render byte-identically to what is on disk, and
        # a 2026-07 circle recorded one name while this installation may
        # now write `[Self]:`. Rendering the current name here would rewrite
        # history on every resume and fail test_resume's inverse check.
        return f"[{e['display']}]: {e['text']}"
    return statement_line(e["display"], e.get("to"), e["text"])


def render_transcript(ot: str, topic: str, transcript: list[dict]) -> str:
    """Rebuild the whole file from the in-memory transcript.

    Mirrors open_transcript() + one append() per entry, and nothing else. If
    this ever drifts from those two functions the round-trip check fails and
    resume stops working — which is the intended failure, loud and immediate."""
    # THE HEADER IS RE-EMITTED, NOT RE-DERIVED. A coordinator transcript
    # puts the same string in the header and in CIRCLE:, so deriving one
    # from the other was invisible. Two agent-teams circles do not: their
    # header carries a SHORT LABEL and CIRCLE: carries the full topic, so
    # re-deriving rewrote the title on every resume and the round-trip
    # check failed on a file nobody had touched.
    #
    # A transcript is this project's only literal record. Reproducing it
    # means reproducing what it says, not what this format would say.
    head = next((e.get("header") for e in transcript
                 if e.get("is_topic")), None)
    out = f"# Circle — {head or topic or '(no topic)'} — {ot}\n\n"
    if topic:
        out += f"CIRCLE: {topic}\n"
    for e in transcript:
        if e.get("is_topic"):
            continue                      # carried by the CIRCLE: line above
        out += "\n" + render_line(e) + "\n"
    return out


def withheld(e: dict) -> bool:
    """RECORDED, BUT NEVER IN THE ROOM. One predicate for the whole class,
    added 2026-08-18 when it gained its second member.

        cmd             an echoed /issue ruling. RULED 2026-08-04: "Recorded
                        to the circle, but not sent to parts."
        remember_only   a statement that was ENTIRELY a [remember: ...].
                        RULED 2026-08-18: the turn is still a pass, and the
                        bracket still reaches the transcript file.

    FOUR READERS MUST AGREE, and until this existed they agreed by
    coincidence. render_messages() must not show it to a part;
    rebuild_state() must not move a counter for it; statements() must not
    let /issue-evidence-add address it; addressed_since() must count it as
    neither a statement nor an address. Each was its own `e.get("cmd")`
    test or no test at all, so adding a second member meant finding all
    four — and the one that gets missed fails silently, in one direction
    only. The live/resume divergence rebuild_state's own comment records is
    exactly that shape, and addressed_since() had no test whatsoever."""
    # recall_only joined 2026-08-30 (R402), the THIRD member: a statement
    # that was ENTIRELY a [recall: ...] — the query reaches the file, the
    # room hears a pass, and the answer rides privately in that part's own
    # next request.
    return bool(e.get("cmd") or e.get("remember_only")
                or e.get("recall_only"))


def _split_remember(e: dict) -> None:
    """Give a parsed statement the same room/record split the live loop gives
    a fresh one, in place: `raw` becomes the file's own bytes, `text` becomes
    what the room may see.

    THE RESUME PATH'S HALF OF THE 2026-08-14 RULING, built 2026-08-18. The
    live loop strips the bracket before `text` reaches render_messages(), and
    writes the unstripped line to the file. Reading that file back without
    this would hand the bracket straight to the next prompt — every part
    would read a private note that was never in the room, and the leak would
    open only on resume, which is the hardest case to notice.

    NO-OP WHEN THERE IS NO BRACKET, deliberately: `raw` is absent rather than
    equal to `text`, so nothing changes for the 40-odd transcripts written
    before the ruling, and `render_line`'s lookup falls through to `text`
    exactly as it always did.

    Calls markers.strip_remember() — the one spelling of "strip and tidy",
    shared with the live path, so a resumed circle's in-memory statement is
    byte-identical to what a live one held. The import is function-local:
    markers.py reaches into the issue-graph modules, and this file is
    imported by things that have no business pulling those in."""
    import markers as MK
    import recall_index as RC
    has_rem = bool(MK.REMEMBER_RE.search(e["text"]))
    has_rec = bool(RC.RECALL_RE.search(e["text"]))
    if not (has_rem or has_rec):
        return
    e["raw"] = e["text"]
    text = e["text"]
    if has_rem:
        text = MK.strip_remember(text)
    if has_rec:
        # The recall bracket takes the identical resume treatment (R402):
        # strip_recall is spelled once, in recall_index, for the same
        # byte-identity reason strip_remember is spelled once in markers.
        text = RC.strip_recall(text)
    e["text"] = text
    # SELF-IDENTIFYING ON THE WAY BACK IN, the same discipline the `cmd`
    # flag follows ("a recorded Self line beginning `/` can only be an
    # echoed command"). Nothing left for the room means the whole statement
    # was the annotation, which is the one shape that reaches the file as a
    # pass — RULED 2026-08-18. Restoring the flag here is what keeps a
    # RESUMED circle from replaying it as a real turn and handing a part a
    # statement the live run never gave it.
    #
    # SET OR CLEAR, never just set (2026-08-19). parse_transcript()'s
    # continuation merge re-runs this on a statement it may have flagged a
    # block earlier: "[remember: x]\n\nMore text" parses as a bracket-only
    # block (flag set) plus a continuation (text re-derived as "More
    # text"). Leaving the stale flag standing made withheld() hide the
    # SPOKEN statement from the whole room on resume — the counters and
    # every part's view silently diverged from what the live loop held.
    if not e["text"]:
        if has_rem:
            e["remember_only"] = True
        else:
            e.pop("remember_only", None)
        if has_rec:
            e["recall_only"] = True
        else:
            e.pop("recall_only", None)
    else:
        e.pop("remember_only", None)
        e.pop("recall_only", None)


# The line circle.py emits at open to say where it is writing. This module
# owns the transcript's persistence AND its parsing, so it owns reading that
# announcement back too — B57(2), 2026-08-19. Until then the same regex lived
# in three places (ui/tests/test_circle_engine.py, ui/tests/circle_test.py and the run
# skill's driver.py), copied down to the incident comment below, which is
# three chances to fix one of them and leave the others.
#
# `.+`, NOT `\S+`, AND THE REASON IS THIS REPOSITORY'S OWN PATH. It contains a
# space — "Inner Circling" — which `\S+` truncates at, so the match silently
# fails and the caller leaves its sandbox transcript behind; the NEXT run then
# hits circle.py's "still open" guard instead of the prompt it expected. Found
# by test_circle_engine.py's first run, which left circle_2026-08-10_1635.md.
ANNOUNCED_RE = re.compile(
    r"transcript: (.+circle_\d{4}-\d{2}-\d{2}_\d{4}\.md)\s*$")


def announced_path(emitted) -> pathlib.Path | None:
    """The transcript path circle.py announced, scraped from what it emitted.

    `emitted` is one emitted line or an iterable of them; the first match
    wins, which is what every caller wanted (the path is announced once, at
    open). Returns None when nothing announced one.

    `$` is END OF STRING, not end of line — no `re.M`. That is what all three
    copies did, and this move is meant to change no behaviour; a caller
    handing in a multi-line chunk with the announcement buried mid-way got
    None before and gets None now."""
    texts = (emitted,) if isinstance(emitted, str) else emitted
    for text in texts:
        m = ANNOUNCED_RE.search(text)
        if m:
            return pathlib.Path(m.group(1))
    return None


def parse_transcript(raw: str) -> tuple[str, str, list[dict]]:
    """(open_time, topic, transcript). Raises ValueError on anything unexpected.

    Deliberately strict. A transcript is the project's only literal record; a
    parser that guesses at a malformed one would launder damage into a live
    circle."""
    lines = raw.split("\n")
    m = _HEAD_RE.fullmatch(lines[0]) if lines else None
    if not m:
        raise ValueError("not a coordinator transcript: unparseable header line")
    ot = m.group(2)
    if len(lines) < 2 or lines[1] != "":
        raise ValueError("expected a blank line after the header")

    i, topic, transcript = 2, "", []
    if i < len(lines) and lines[i].startswith("CIRCLE: "):
        topic = lines[i][len("CIRCLE: "):]
        transcript.append({"speaker": ID.SELF_ID, "display": SELF_DISPLAY,
                           "text": topic, "is_topic": True,
                           # what the header actually said, kept so
                           # render_transcript can reproduce it verbatim
                           "header": m.group(1)})
        i += 1

    blocks: list[list[str]] = []
    cur: list[str] | None = None
    while i < len(lines):
        if lines[i] == "":
            if i + 1 < len(lines):        # not the file's trailing newline
                cur = []
                blocks.append(cur)
            i += 1
            continue
        if cur is None:
            raise ValueError(f"line {i + 1}: content with no separating blank line")
        cur.append(lines[i])
        i += 1

    for b in blocks:
        body = "\n".join(b)
        sm = _STMT_RE.fullmatch(body)
        if not sm:
            note = body.startswith("[") and body.endswith("]")
            if note:
                # A statement whose LAST paragraph is only its
                # [remember: ...] bracket writes bytes indistinguishable
                # from a coordinator note — and render_messages() carries
                # every Scribe line into every part's prompt, so reading
                # it as one handed the private annotation to the whole
                # room on resume (found 2026-08-19; the round-trip check
                # could not catch it, because a Scribe note re-renders
                # byte-identically too). A bracket-shaped block that
                # carries a remember marker and follows a real statement
                # is that statement's continuation, never a note: the
                # coordinator's own notes carry no remember bracket, by
                # construction. Function-local import for the same reason
                # _split_remember's is.
                import markers as MK
                import recall_index as RC
                if ((MK.REMEMBER_RE.search(body)
                     or RC.RECALL_RE.search(body)) and transcript
                        and not transcript[-1].get("is_topic")
                        and transcript[-1].get("speaker") != "__scribe__"):
                    note = False        # fall through to the merge below
            if note:
                # A note the coordinator wrote for readers — the blind-round
                # marker and its kin. Parts never see a speaker for it.
                transcript.append({"speaker": "__scribe__", "display": "Scribe",
                                   "text": body})
                continue
            # A PARAGRAPH BREAK INSIDE A STATEMENT. `append` writes "\n" + line
            # + "\n" and uses a blank line as the record separator, so a part
            # that emits two paragraphs produces bytes indistinguishable from
            # two records. This is not hypothetical: the Child did it in
            # circle_2026-08-01_1203.
            #
            # KNOWN HOLE, and it cannot be closed in this format — see
            # test_resume.py. Text appended after a statement is absorbed INTO
            # that statement and re-renders identically, so the round-trip
            # check cannot tell a real paragraph break from a line someone
            # added by hand. Git covers hand edits; this covers the parts.
            if not transcript or transcript[-1].get("is_topic"):
                raise ValueError(
                    f"continuation with no statement before it: {body[:60]!r}")
            prev = transcript[-1]
            # THE CONTINUATION IS APPENDED TO THE RECORD, THEN RE-SPLIT.
            # `raw` is the file's own bytes, so it must grow by exactly the
            # block that was read; `text` is then re-derived rather than
            # extended, because the bracket may span nothing here and
            # everything in the paragraph that follows.
            prev["text"] = prev.get("raw", prev["text"]) + "\n\n" + body
            prev.pop("raw", None)
            _split_remember(prev)
            continue
        display, to, text = sm.group(1), sm.group(2), sm.group(3)
        if display in TAG_TO_PART:
            e = {"speaker": TAG_TO_PART[display], "display": display, "text": text}
            _split_remember(e)
            if to:
                e["to"] = to
            transcript.append(e)
        elif ID.is_self_tag(display, CONSOLE_NAME):
            # A KNOWN SELF TAG — parts are matched first, then this. Before
            # 2026-08-07 the test compared against one hardcoded name, so a
            # transcript was readable only by the installation that wrote it.
            # Passing CONSOLE_NAME (not SELF_DISPLAY) keeps this call
            # recognising whatever this installation used to WRITE, even
            # from before the 2026-08-11 ruling fixed writing to "Self" —
            # the 42 pre-existing circles, the agent-teams era's `[Self]:`,
            # and today's `[Self]:` all parse, and each re-renders as the
            # name it was written with.
            #
            # KNOWN, not merely unrecognised. See identity.HISTORICAL_NAMES
            # for what the permissive version cost.
            e = {"speaker": ID.SELF_ID, "display": display, "text": text}
            # A COMMAND IS SELF-IDENTIFYING: Self's statements reach the room
            # by being typed WITHOUT a leading slash (the dispatcher consumes
            # anything with one), so a recorded Self line beginning `/` can
            # only be an echoed command. Restoring the flag here is what keeps
            # a RESUMED circle from replaying every graph ruling to the parts.
            if text.startswith("/"):
                e["cmd"] = True
            else:
                # Only a SPOKEN Self line can carry a remember bracket. An
                # echoed command never reaches the room at all (`cmd`), so
                # splitting one would invent a `raw` that changes nothing
                # and costs a dict key on every graph ruling ever recorded.
                _split_remember(e)
            transcript.append(e)
        else:
            raise ValueError(f"unknown speaker tag [{display}]")
    return ot, topic, transcript


def rebuild_state(transcript: list[dict], parts: list[str]) -> tuple[dict, dict, list]:
    """Replay the transcript to recover exactly what the loop was holding.

    Mirrors the two places the live loop mutates this state: run_round /
    run_blind_round increment a part and set `last`; a Self statement resets
    every count to 0 and clears `last`, per process_core."""
    since_self = {p: 0 for p in parts}
    state = {"last": None}
    absent = []
    for e in transcript:
        if e.get("is_topic") or e["speaker"] == "__scribe__":
            continue
        # RULED 2026-08-04 (D16, "no"): a /command does NOT reset the
        # counters. The room never heard it — that is the whole of the
        # ruling that it is recorded but not sent — so nothing about the
        # room's state may move because of it.
        #
        # THIS WAS A LIVE/RESUME DIVERGENCE. The live loop already got it
        # right by not touching `since_self` in the /issue branch; this
        # replay did not, because a command is a Self entry and every Self
        # entry reset the counts. A circle resumed after a command would
        # have granted every part a fresh two statements that the original
        # run did not. Found by testing the ruling rather than the code.
        if withheld(e):
            continue
        if e["speaker"] == ID.SELF_ID:
            since_self = {p: 0 for p in parts}
            state["last"] = None
        else:
            if e["speaker"] in since_self:
                since_self[e["speaker"]] += 1
            else:
                absent.append(e["speaker"])
            state["last"] = e["speaker"]
    return since_self, state, sorted(set(absent))


def load_for_resume(path: pathlib.Path, ot: str,
                    parts: list[str]) -> tuple[str, list[dict], dict, dict]:
    """Read a transcript back, PROVING the read is faithful before returning it."""
    if not path.is_file():
        raise ValueError(f"no transcript at {path}")
    raw = path.read_text(encoding="utf-8")
    got_ot, topic, transcript = parse_transcript(raw)
    if got_ot != ot:
        raise ValueError(f"header says {got_ot}, filename says {ot}")
    rendered = render_transcript(ot, topic, transcript)
    if rendered != raw:
        n = next((k for k in range(min(len(raw), len(rendered)))
                  if raw[k] != rendered[k]), min(len(raw), len(rendered)))
        raise ValueError(
            "REFUSING to resume: this transcript does not round-trip.\n"
            f"     first difference at byte {n}\n"
            f"     on disk:  {raw[n:n + 60]!r}\n"
            f"     re-render:{rendered[n:n + 60]!r}\n"
            "     The parser and the writer disagree, so anything read from\n"
            "     here would be a guess. Nothing was modified.")
    since_self, state, absent = rebuild_state(transcript, parts)
    if absent:
        raise ValueError(
            f"transcript contains part(s) not in this roster: {', '.join(absent)}\n"
            "     Resume with the same roster the circle opened with.")
    return topic, transcript, since_self, state


# ------------------------------------------------------------------ close records
def commit_sandbox(ot: str) -> None:
    """B13, ruled 2026-08-03 (D10). A sandbox circle commits its OWN output
    and nothing else.

    Two path roots only, never `git add -A`:
        work/sandbox/circles/circle_<OT>.md
        work/sandbox/prompts/<OT>/

    Tagged `circle/sandbox/<OT>` so it cannot collide with a live
    `circle/<OT>`. Before this, `circle_2026-08-03_2208` had to be committed
    by hand and Self had to ask for it — the design work rests on these
    captures and they were the only records the program did not keep."""
    try:
        import gitrepo as G
    except ImportError:
        return
    # A CLOSE REPORT, even in the sandbox. Without one, circle_state.py can
    # never answer "did this close?" — it can only wait 45 minutes and guess.
    # On 2026-08-06 that gap meant a closed circle still read as possibly
    # open, which is the same uncertainty that let E12 happen in the other
    # direction. A record of the close is cheap; inferring one is not.
    logs = ROOT / "work" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    tpath = SANDBOX / "circles" / f"circle_{ot}.md"
    try:
        import hashlib as _h
        raw = tpath.read_bytes() if tpath.is_file() else b""
        (logs / f"close_{ot}.json").write_text(json.dumps({
            "circle": ot, "mode": "sandbox",
            "closed": datetime.datetime.now().isoformat(timespec="seconds"),
            "transcript": {"bytes": len(raw),
                           "sha256": _h.sha256(raw).hexdigest()},
            "short_terms": "not verified — a dry-run close report covers the transcript alone",
        }, indent=2) + "\n", encoding="utf-8", newline="\n")
    except Exception as e:                                   # noqa: BLE001
        seam.emit("command", f"  close report not written — {e}")

    paths = [SANDBOX / "circles" / f"circle_{ot}.md",
             logs / f"close_{ot}.json"]
    for pdir in sorted((SANDBOX / "prompts").glob(f"{ot}*")):
        if pdir.is_dir():
            paths += sorted(pdir.glob("*"))
    paths += sorted((SANDBOX / "circles").glob(f"commands_{ot}.toml"))
    paths = [p for p in paths if p.is_file()]
    if not paths:
        return
    marks_ = {"ok": "  ", "did": "  ", "warn": "  ", "note": "  ",
              "fail": "  !! "}
    G.commit_paths(paths, f"sandbox circle {ot}",
                   lambda k, m: seam.emit("command", f"{marks_[k]}{m}"),
                   tag=G.tag_name("circle", "sandbox", ot))


def circle_commit_paths(ot: str, written: list[str]) -> list[pathlib.Path]:
    """Every path this circle's own commit stages. PURE — no git, no writes —
    so what a close records can be asserted without a repository, which is
    what nothing could do while this list lived inside `commit_circle`.

    THE TWO REGISTERS JOINED 2026-08-26, on the operator's word, after a
    real circle's leftovers deadlocked a `pull-main`: the lab's tree was
    dirty with `self/working_sets.toml` and `self/proposals.toml`, and the
    merge refuses a dirty tree — correctly. Both are this circle's own
    output and neither was staged by anything:

        working_sets.toml   written at OPEN — what this circle was shown
        proposals.toml      written by vetting DURING and AT the close

    The close's own order is what makes staging them here correct rather
    than hopeful: `vet_pending_proposals("at close", ...)` runs before
    `mark_close_started()`, which runs before the short_terms, the verifier
    and this commit, so both files are final by the time it fires. And
    SYNTHESIS does not write either — it reads confirmed proposals — so the
    second commit has no later state of them to carry.

    Staging an unchanged file is a no-op, so a circle that added no
    proposal simply commits the transcript it was always going to.

    The two work/logs markers — `closing_<OT>.json` and `dream_<OT>.json` —
    are deliberately NOT here. They are memos, not records: the close
    report supersedes the first (`mark_close_started`: "IT IS NEVER
    DELETED. A close report supersedes it") and the `dream/<OT>` tag is the
    authority for the second. `.gitignore` carries both, with that reason
    written beside them."""
    paths = [ROOT / "circles" / f"circle_{ot}.md",
             ROOT / "work" / "logs" / f"close_{ot}.json"]
    # work/prompts/<OT>/ and every work/prompts/<OT>_resume_<k>/
    # a resumed sitting wrote. The resume captures were missed on the first
    # live resume, 2026-08-02.
    for pdir in sorted((ROOT / "work" / "prompts").glob(f"{ot}*")):
        if pdir.is_dir():
            paths += sorted(pdir.glob("*"))
    paths += [ROOT / "parts" / p / f"short_term_{ot}.md" for p in written]
    # The graph-rulings record, when this circle wrote one. commit_sandbox
    # always staged its sandbox twin; the live path omitted it (2026-08-18
    # review, tier 2 #18), so the one file the gate's provenance greps
    # rely on sat untracked forever — "never add -A" means nothing else
    # ever swept it in.
    paths += sorted((ROOT / "circles").glob(f"commands_{ot}.toml"))
    paths += [p for p in (ROOT / "self" / "working_sets.toml",
                          ROOT / "self" / "proposals.toml") if p.is_file()]
    return paths


def commit_circle(ot: str, written: list[str]) -> None:
    """Record this circle in git: the transcript, each short_term it wrote, and
    the close report. ONLY those paths — never `add -A`, so a file you were
    editing while the circle ran is not swept into a machine commit.

    Non-fatal by design. git is the rollback target, not part of the circle; a
    missing repository must not cost you a closed circle.

    Lost its `marks_file` parameter and self/leads.md handling 2026-08-14,
    when MARK was retired wholesale (docs/BNF.md) — write_marks()/
    append_leads(), the only writers of either path, are gone with it.
    self/leads.md itself is left in place, frozen: real history, not
    deleted, just no longer appended to."""
    try:
        import gitrepo as G
    except ImportError:
        return
    marks_ = {"ok": "  ", "did": "  ", "warn": "  ", "note": "  ", "fail": "  !! "}

    def log(kind, msg):
        seam.emit("command", f"{marks_[kind]}{msg}")

    paths = circle_commit_paths(ot, written)
    seam.emit("command")
    G.commit_paths(paths, f"circle {ot}: {len(written)} short_term(s)", log,
                   tag=G.tag_name("circle", ot))


def run_verifier(ot: str) -> int:
    """Returns the verifier's exit code. A non-zero code means the close report
    records a missing short_term — the caller must NOT report a clean close."""
    cmd = [sys.executable, str(ROOT / "coordinator" / "circle_close.py"),
           "--short-term-only", "--open-time", ot, "--write-report"]
    seam.emit("command", f"\n  $ {' '.join(cmd)}")
    # CAPTURED, never inherited (the operator's lab close, 2026-08-30): a child
    # writing to the real stdout lands inside the Ticker bridge's NDJSON
    # protocol stream, and every report line arrives as a loud
    # "unparseable event". The seam is the one road to a pane. Same
    # contract issue_draw's spawn in circle.py already keeps; the child
    # writes UTF-8 into the pipe because cp1252 is the piped default.
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    for line in (r.stdout or "").splitlines():
        seam.emit("command", line.rstrip())
    for line in (r.stderr or "").splitlines():
        seam.emit("command", f"  !! {line.rstrip()}")
    seam.emit("command", f"  verifier exit {r.returncode}"
              + ("" if r.returncode == 0 else "  <-- ACTION NEEDED"))
    if r.returncode != 0:
        seam.fail(f"circle_close.py exited {r.returncode} — the close report "
                  f"work/logs/close_{ot}.json records an unmet short_term")
    return r.returncode
