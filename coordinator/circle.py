#!/usr/bin/env python3
"""
IFS inner circle — local coordinator (direct Messages API).

WHAT THIS IS
    THE DRIVER, NOT THE PROGRAM. A local Python "Scribe" drives the parts as
    direct, stateless Messages API calls; a part's statement is the HTTP return
    value. There is no agent-teams runtime, no SendMessage, no teammate file
    writes, no sandbox mount in the write path. Almost everything this file once
    held now lives in its own module and is called from here — the turn engine
    (rounds.py), the annotation grammar (markers.py), the four-block assembly
    (prompt_build.py), the transport (llm_client.py).

    THE AGENT-TEAMS PATH IS GONE, not parallel. This paragraph said that
    mechanism was "UNTOUCHED and fully operational" until 2026-08-27 — a month
    after it was retired (2026-07-26), and nine days after `scripts/`, one of
    the four paths it named, was deleted outright. There is one path.

TWO MODES, AND ONE IS REQUIRED
    --live      Permits writing:
                  circles/circle_<OT>.md
                  parts/<name>/short_term_<OT>.md   (that name only)
                  work/logs/                        (via circle_close.py)
                Nothing else, ever. Enforced by assert_write_safe().
    --dry-run   The test rig: no network, no API key needed, every part passes.
                Writes only under work/sandbox/.

    A BARE INVOCATION REFUSES (R360, 2026-08-27, exit 2). The old bare default
    — real model calls with the writes sent to work/sandbox/ — was the practice
    mode R250 deprecated, and practice lives in the lab checkout now. This
    section described that default as the live behaviour until the day it went.

INTEROP
    Transcript lines use the canonical "[Tag]:" / "[Tag] [To: X]:" form that
    coordinator/circle_close.py::parts_that_spoke() parses. short_term files carry
    the four canonical sections. At close in --live mode this script shells out
    to coordinator/circle_close.py --short-term-only --write-report, so the durable
    close report work/logs/close_<OT>.json is produced by the SAME verifier as
    always.

    NOTHING RE-VERIFIES THAT REPORT AUTOMATICALLY, and this said "the nightly
    --reconcile guard keeps working unchanged". There has been no nightly since
    2026-07-28. circle_audit.py phase 2 runs --reconcile — when a human runs it.

RUN
    pip install anthropic python-dotenv
    set ANTHROPIC_API_KEY=...            (or put it in the project .env)
    python coordinator/circle.py --live
    python coordinator/circle.py --dry-run
    python coordinator/circle.py --dry-run --parts <part1>,<part2>
"""

from __future__ import annotations

import argparse
import atexit
import datetime
import os
import pathlib
import random
import re
import sys

import pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
del _pl
import identity as ID              # SELF_ID + the display name
import issue_commands as IC        # /issue-label-update, issue-relationship-add
import roster as R                 # B29: the one roster every reader shares
import check_integrity as CI       # the corruption gate, run before anything opens
from paths import ROOT, SANDBOX, PART_TAGS   # phase-1 step 0: one home
                                   # for path constants (2026-08-16)
import seam                        # the I/O seams + failure ledger
                                   # (phase-1 step 1, 2026-08-16)
from seam import FAILURES, fail    # aliases to the SAME list object and
                                   # the same never-rebound function
from write_guard import WriteGuard, _within  # phase-1 step 2
import command_surface as CS       # phase-2 stage 0 (2026-08-16): the
                                   # command-pane constants + dev_mode.
                                   # dev_mode is REBOUND — always
                                   # CS.dev_mode, never a from-import.
from command_surface import KNOWN_CMDS
from llm_client import (call, METER, prewarm, preflight_api,  # phase-2
                        MODEL, KEY_MISSING_HELP,
                        key_source_note, explain_api_failure,  # stage 1:
                        RATE_CACHE_WRITE_1H,                   # the API
                        RATE_CACHE_READ, SHORT_TERM_SECTIONS)  # transport
from prompt_build import (render_messages, load_shared,       # phase-2
                          build_briefing,                     # stage 2:
                          shared_block, system_blocks,        # the prompt's
                          block_order)                        # construction
import markers as MK               # phase-2 stage 3: the annotation system
import quote_as_mark as QM         # R155's channel: Self quoting a part
                                   # IS a ratification. NOT in markers —
                                   # that module is the BRACKET grammar
                                   # and this mechanism has no bracket.
from markers import (apply_self_remember, REMEMBER_RE,
                     strip_malformed_markers, route_markers,
                     unruled_proposals, show_unruled_proposals,
                     stage_propose_proposals)
apply_remember = MK.apply_remember     # test-surface re-export (called only)
# Re-exported for the test surface (all CALLED there, never rebound —
# the alias-assignment form because this file no longer calls them
# itself, and an unused from-import would fail the pyflakes gate):
extract_markers = MK.extract_markers
propose_proposals = MK.propose_proposals
coalesce_propose_proposals = MK.coalesce_propose_proposals
convergence_queue = MK.convergence_queue
_normalize_edge = MK._normalize_edge
import help_system as HS           # phase-2 stage 5 (built 4th)
from help_system import help_text, junk_help
# Test-surface re-exports (called, never rebound):
object_classes = HS.object_classes
object_class_help_text = HS.object_class_help_text
_HELP_ONE_LINERS = HS._HELP_ONE_LINERS
import vetting as VT               # phase-2 stage 4 (built 6th)
from vetting import vet_pending_proposals
from rounds import (run_round, run_blind_round,    # phase-2 stage 7:
                    token_table)                   # the turn engine
# (graph_now/_propose_approve/_propose_command_shape are deliberately
# NOT re-exported: the tests patch and call them on their owners —
# vetting and markers — per the late-binding contract.)
from commands import (dispatch_dev_cmd,                   # phase-2
                      resolve_statement,                   # stage 6
                      show_statements)                     # (built 5th)
# The cmd_* implementations are NO LONGER imported here — B61,
# 2026-08-21: the Self> loop delegates every non-circle-dependent verb
# to dispatch_dev_cmd() and branches nothing it also handles. See the
# loop, and coordinator/tests/test_dispatch_partition.py.
from transcript_store import (               # phase-1 step 3 — the
    write_lf, open_transcript, append,       # transcript's persistence
    discard_empty_open, record_working_set,  # and parsing layer; these
    load_for_resume,                         # are the names this file
    commit_sandbox, commit_circle,           # still calls itself
    run_verifier,
)
import transcript_store as TS
import token_count as TC
statement_line = TS.statement_line     # test-surface re-export (called only)

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ------------------------------------------------------------------ I/O seams
# MOVED to seam.py, 2026-08-16 (phase 1 step 1) — the seam contract and
# its history live there now. These two wrappers keep this file's ~170
# call sites reading unchanged while still LATE-BINDING through the
# seam module on every call: circling.py and the test harnesses rebind
# `seam.emit`/`seam.read_line`, and the wrappers see the rebound
# version because the lookup happens at call time, not at import.
#
# REBIND seam.emit / seam.read_line, NEVER these two names. Rebinding
# `circle.emit` would capture this file's own calls and nothing else —
# an extracted module's output would silently keep going to the real
# stdout. The one rebinding surface is seam.py.


def emit(channel: str, text: str = "", **kwargs) -> None:
    seam.emit(channel, text, **kwargs)


def read_line(prompt: str = "", channel: str = "command",
              prefill: str = "") -> str:
    # `channel` says WHICH pane asks and answers - R221, 2026-08-17. It is
    # meaningless to a standalone terminal run and load-bearing under
    # ui/circling.py, exactly like emit's. The default is "command"
    # because that lane is private (docs/BNF.md line 105); the three
    # circle-lane reads in this file each ask for it by name.
    #
    # `prefill` (2026-08-20, finding 2) asks the reader to open with that
    # text already typed and the cursor at its end. An AFFORDANCE, not a
    # contract — see seam.read_line: a plain terminal ignores it, so every
    # caller must also say the same thing in words.
    # prefill BY KEYWORD, deliberately: a rebound read_line only has to
    # accept the two positional arguments it always did, plus `**_`.
    # Passing it positionally would break every stub in the suites at
    # once, for an argument most of them have no opinion about.
    return seam.read_line(prompt, channel, prefill=prefill)


def read_line_no_annotation(prompt: str, where: str,
                            channel: str = "circle",
                            prefill: str = "") -> str:
    """RULED 2026-08-18 (R225), verbatim: "a [remember: ...] or
    [propose ...] is valid ONLY at the circle pane self> (aka user_name>)
    prompt; typing any annotation into the topic (or the active issues set
    selection) is invalid, say so and return to the prompt."

    THE TWO OPENING PROMPTS ONLY - the topic and the working set. The
    Self> loop below is the prompt where an annotation IS valid, and it
    does not come through here.

    REJECT THE WHOLE LINE, NEVER STRIP IT. strip_malformed_markers() is
    the other shape and is the right one for speech: remove the broken
    span, keep the statement. A topic is not a statement, so there is no
    remainder worth keeping - stripping would open the circle under a
    topic the typist never wrote, which is worse than asking again. The
    ruling says "say so and return to the prompt": a loop, not a repair.

    WHY THE TOPIC NEEDED THIS AT ALL. It is appended to the transcript
    with `is_topic`, and prompt_build.render_messages() skips only `cmd`
    entries - so a topic renders to EVERY part as a user turn. A
    `[remember: ...]` typed there was neither captured (no
    apply_self_remember on that path) nor stripped (no
    strip_malformed_markers either), and reached all seven parts
    verbatim: the exact opposite of the private note it asks for, and
    E06's contamination through a door nothing was watching.

    Warnings go to the COMMAND channel, following the two complaints that
    already exist about these prompts' input - the working set's own
    unknown-node notice, and strip_malformed_markers()'s - rather than
    putting a diagnostic into the room's pane.

    EOFError/KeyboardInterrupt PROPAGATE UNTOUCHED, so each call site's
    cancel path is exactly what it was before this function existed.
    Returns the accepted line, stripped, as the bare read_line().strip()
    it replaces did."""
    while True:
        raw = read_line(prompt, channel=channel, prefill=prefill).strip()
        prefill = ""          # offered once; a re-ask after an annotation
                              # is a different question from a re-ask after
                              # an invalid id, and must not re-seed the line
        found = MK.annotations_in(raw)
        if not found:
            return raw
        more = f" (+{len(found) - 1} more)" if len(found) > 1 else ""
        emit("command", f"  !! {found[0]}{more} - an annotation is not valid "
             f"in the {where}.")
        # THE SPELLINGS COME FROM THE GRAMMAR, 2026-08-20 (code review): this
        # line said `[propose ...]` — the d-less form R273 retired — so a
        # typist who followed the hint would have spoken it to the room as
        # prose and staged nothing. ASK_KEYWORDS is what ASK_RE is built
        # from, so the hint and the parser cannot disagree again.
        forms = " and ".join(f"[{k}: ...]" for k in MK.ASK_KEYWORDS)
        emit("command", f"     {forms} are valid only "
             f"at the {CONSOLE_NAME}> prompt, in an open circle.")
        emit("command", f"     Nothing was recorded. Type the {where} again.")


# THE WORDS ARE THE OPERATOR'S — R330, 2026-08-23: *"Ensure
# the working set question is presented in terms of "Do you have specific
# issues you would like to focus on today ('?' to review) ? ""*. It was
# `CIRCLE issues (blank = none, 'all', '?'): ` — a legend, not a question. The
# GRAMMAR below is unchanged: blank is still no issues, `none` and `all` are
# still accepted; `all` is simply no longer advertised. `?` lists and re-asks,
# as it always did. The dual pane's blank-answer echo read its legend out of
# the old prompt's "blank = ..." and now takes its "(blank)" fallback.
#
# THE LEGEND RETURNED, IN HIS WORDS — R344,
# 2026-08-25 (D61 a): *"blank for no, 'all', or a comma separated list of
# line numbers"* — added after he typed "16" at a numbered-in-his-head
# listing that carried no numbers and no hint of what an answer looks like.
# The `?` listing is numbered now and digits-only tokens ARE line numbers;
# issue ids keep their `n` prefix and still work.
WORKING_SET_PROMPT = ("\nDo you have specific issues you would like to focus "
                      "on today ('?' to review) ? (blank for no, 'all', or a "
                      "comma separated list of line numbers) ")


def ask_working_set(IP, prompt: str = WORKING_SET_PROMPT):
    """The working set, asked until it is answerable. FINDING 2, 2026-08-20.

        (blank)   NO issues at all — the prologue and nothing else
        none      the same, said out loud
        all       the whole live graph
        ?         the live issues, NUMBERED, then ask again
        1, 3...   line numbers into that listing (R344, D61 a: a
                  digits-only token is a line number, the order the
                  id order `?` prints)
        nNNNN...  those issues, validated

    NOT ASKED AT ALL WHEN THERE IS NOTHING TO CHOOSE FROM — R330,
    2026-08-23: *"If there are no issues[], do not ask the working
    set question."* main() tests `IP.live_nodes()` first and takes the blank
    answer (None) silently; a fresh installation that recorded no issue reaches
    the topic question directly. This function is unchanged by that — the
    decision is the caller's, so a driver that wants the question can still
    call it.

    THE DEFAULT FLIPPED — R-NEW, 2026-08-22, Self ruled: *"issues are important to
    include only when specifically discussing some set of issue and
    issue-relations — so the default ought to be to NOT include them,
    issues=none, rather than issues=all."* Blank used to mean the whole graph.
    Nothing about the GRAMMAR changed — `none`, `all` and an id list all mean
    exactly what they meant, and `chosen is None` was already the ruled
    spelling for "no issues" (finding 2, 2026-08-20). Only which answer blank
    maps to changed.

    Measured, and the reason it is not merely a preference: with the whole
    graph in block 2, the Child was identified by a blind reader 44% of the
    time; with the `## Issues` section removed, 72% (n=25, p=0.045). The graph
    costs the parts their own distinctness, so it should be paid for when the
    circle is about those issues and not otherwise.

    "ISSUE", NEVER "NODE", IN ANYTHING THIS PROMPTS OR PRINTS — RULED
    2026-08-21, after the lab's second day: *"'node' is graph speak, can be
    applied to all of our graphed anything, it is ambiguous. 'issue ids'
    are what a user must see, specific to this application. Ruling: do not
    surface 'node'. Replace it with the class of node being referenced."*
    The code below still says node where it means the graph; the operator
    reads "issue".

    Returns a list of ids, `[]` for the whole graph (`all`), or None for no
    issues (blank or `none`). THE THREE ANSWERS ARE STILL DIFFERENT and the
    types still say so: `[]` means "no FOCUS, project everything", None means
    "no issues in this circle at all". What changed in R-NEW is only which of
    them BLANK selects — `none` is now the synonym for blank, and `all` is the
    word that must be typed.

    AN INVALID ID DOES NOT OPEN A CIRCLE. It printed `unknown node(s)
    ignored:` and carried on — so on 2026-08-20 a `/status` typed one
    prompt too early became the working set, was "ignored", and the circle
    opened anyway with no focus at all. Nothing is ignored now: the invalid
    ones are named and the question is asked again.

    THE VALID ONES COME BACK ALREADY TYPED, which is the ruled behaviour —
    "position the cursor at the end so that the user can correct the
    entries; an enter alone would submit the list of just those that are
    valid". `prefill` is an affordance the dual pane honours and a plain
    terminal cannot, so the same subset is ALSO printed in words: the
    coordinator never depends on the reader having a cursor.

    `?` RESETS THE LINE rather than prefilling it — you asked what exists,
    you did not offer an answer."""
    prefill = ""
    while True:
        try:
            raw = read_line_no_annotation(prompt, "working set",
                                          channel="circle", prefill=prefill)
        except (EOFError, KeyboardInterrupt):
            emit("command", "\n  (no working set — this circle carries no issues)")
            return None
        word = raw.strip().lower()
        if word in ("", "none"):
            emit("command", "  none — this circle carries no issues at all.")
            return None
        if word == "all":
            emit("command", "  all — the whole live graph.")
            return []
        if word == "?":
            try:
                g = IP.graph()
            except Exception as e:                             # noqa: BLE001
                emit("command", f"  (the graph will not load: {e})")
                g = {}
            emit("circle", f"\n  {len(g)} live issue(s)")
            for i, nid in enumerate(sorted(g), 1):
                label = (g[nid]["doc"].get("label") or "(no label)")
                emit("circle", f"    {i:>2}  {nid}  {label[:64]}")
            prefill = ""
            continue
        pairs = IP.parse_working_set_pairs(raw)
        # A DIGITS-ONLY TOKEN IS A LINE NUMBER — R344
        # (D61 a), 2026-08-25. The order is the `?` listing's own: the live
        # graph in id order, so "1, 3" means the first and third rows whether
        # or not `?` was actually typed this time. An id keeps its `n` prefix
        # — before this, a bare "16" normalised to id 0016 and the refusal
        # named an issue id at someone answering with a line number.
        if any(t.isdigit() for t, _ in pairs):
            try:
                order = sorted(IP.graph())
            except Exception as e:                             # noqa: BLE001
                emit("command", f"  (the graph will not load: {e})")
                return []
            bad = [t for t, _ in pairs
                   if t.isdigit() and not 1 <= int(t) <= len(order)]
            if bad:
                emit("command", "  not on the listing: " + ", ".join(bad)
                     + f" — {len(order)} issue(s); ? lists them numbered")
                keep = [t for t, _ in pairs if t not in bad]
                prefill = " ".join(keep)
                emit("command", "     asking again"
                     + (f" — keeping: {prefill}" if prefill else ""))
                continue
            pairs = [(t, order[int(t) - 1]) if t.isdigit() else (t, nid)
                     for t, nid in pairs]
        ids = [nid for _, nid in pairs]
        try:
            focus, _, unknown = IP.resolve(ids)
        except Exception as e:                                 # noqa: BLE001
            emit("command", f"  (the graph will not load: {e})")
            return []
        if not unknown:
            return ids
        # ECHO WHAT WAS TYPED, not what it normalised to. normalise_id()
        # strips a leading `n` and any `X_` status prefix, so `nZZZZ` comes
        # back as `ZZZZ` — and a refusal naming a string the operator never
        # typed is a refusal they have to decode before they can act on it.
        # First-wins: two spellings of one id are one id, and the first is
        # the one they read.
        as_typed: dict[str, str] = {}
        for tok, nid in pairs:
            as_typed.setdefault(nid, tok)
        # "not issue ids", and what one looks like — 2026-08-21. This said
        # "not in the graph: ..." / "none of those were node ids." and the
        # operator's own words were *"I do not know what 'node ids' refers
        # to"*: the refusal named the graph's concept, not the thing he was
        # being asked for. He was being asked for ISSUE ids.
        emit("command", "  not issue ids: "
             + ", ".join(as_typed.get(u, u) for u in unknown))
        # ...and the line comes back in their spelling too. It re-parses to
        # the same ids, so nothing is lost by keeping it theirs.
        prefill = " ".join(as_typed.get(f, f) for f in focus)
        emit("command", "     asking again"
             + (f" — the valid ones are: {prefill}" if prefill
                else " — an issue id looks like n0010; ? lists them, Enter "
                     "alone (or none) is no issues, all is the whole graph."))


# ------------------------------------------------------------------ paths
# ROOT and SANDBOX (and PART_TAGS, further down) moved to paths.py,
# 2026-08-16 — phase 1 step 0 of the coordinator partitioning; imported
# at the top of this file. HERE stays: it is this module's own location,
# not a tree constant.
HERE = pathlib.Path(__file__).resolve().parent

# ------------------------------------------------------------------ config
# RULED 2026-08-11: a literal personal name is forbidden PII — nothing that
# reaches a transcript or a part's prompt may carry one. Two names, not one:
#
#   SELF_DISPLAY   ID.DISPLAY, fixed "Self". Written into the transcript as
#                  [Self]: and into every prompt block that names Self.
#                  Never reads configuration.
#   CONSOLE_NAME   ID.user_name(), from $IFS_USER_NAME in .env. Shown only
#                  at the console prompt and in /help — never written to a
#                  transcript, never sent to a model.
#
# THIS IS A DISPLAY NAME ONLY. Every comparison uses ID.SELF_ID.
SELF_DISPLAY = ID.DISPLAY
CONSOLE_NAME = ID.user_name()

# MODEL MOVED to llm_client.py, 2026-08-16 (phase 2 stage 1), with
# CACHE_TTL, the RATE_* table and SHORT_TERM_SECTIONS — the transport
# owns its model id and rates; the names this file still uses are
# imported at the top.
# MAX_SINCE_SELF stopped being imported here 2026-08-20: /status's own
# since-Self loop moved INTO token_table (the round column), so this
# file no longer names the ceiling anywhere.
# MAX_TOKENS, MAX_SINCE_SELF and (below) TRUNCATION_MARKER MOVED to
# rounds.py, 2026-08-16 (phase 2 stage 7) — ceiling, per-Self cap and
# the truncation contract are round semantics; comments included.

# PART_TAGS (parts/<dir> -> transcript tag, B29) moved to paths.py with
# its comment, 2026-08-16 — imported at the top of this file.

# All seven parts attend. The agent-teams path spawns all seven every circle
# (CLAUDE.md: "across 7 named parts"; "All part agents activate"), so the
# coordinator does too — omitting one is the desync described in README
# §Roster. B29: derived from roster.py rather than hand-typed.
DEFAULT_PARTS = R.DIR_NAMES

# The Soul's speaking rule — history, kept here rather than in the prompt.
#
# process_core.md once said the Soul "does not speak directly in circles… it may
# graduate to speech if a circle specifically calls for it." It then spoke in 13
# circles from 2026-06-24, kept its own short_term records of doing so, and
# developed a clear discipline about when. The written rule and the lived one
# diverged. From 2026-07-02 the gap was patched with a per-part override
# appended to the Soul's system prompt, because process_core.md was also read
# by the agent-teams path and could not be changed without affecting it. Two
# sources of truth: the document said one thing, the running system did
# another.
#
# With agent-teams retired 2026-07-26, the rule moved into process_core.md
# §The Soul, in the Soul's own words from circle_2026-07-05_1308, and the
# override was removed. The account of the change stayed in that document
# until 2026-07-27, when it was removed from there too — a paragraph of
# project history is not something a part should have to read about itself,
# and for the Soul it framed its own permission to speak as a recent
# administrative correction. It belongs in the code, addressed to whoever
# maintains this, which is what this comment is.

# cc() MOVED to prompt_build.py, 2026-08-16 (phase 2 stage 2) - the
# cache-control marker belongs with the block assembly that stamps it.


# ------------------------------------------------------------------ failure ledger
# MOVED to seam.py, 2026-08-16 (phase 1 step 1), so extracted modules
# can report a data failure without importing this file. FAILURES and
# fail are imported at the top — the same list object and the same
# function; report_failures() below still reads the one ledger.

# TRUNCATION_MARKER MOVED to rounds.py with ask_statement (stage 7).


# ------------------------------------------------------------------ write guard
# MOVED to write_guard.py, 2026-08-16 (phase 1 step 2) — WriteGuard and
# _within, verbatim, comments included; imported at the top of this
# file. The class raises rather than emits, which is what made it the
# safest first extraction.


# --------------------------------------------- prompt construction
# MOVED to prompt_build.py, 2026-08-16 (phase 2 stage 2): the
# identity read-layer (read_ro/strip_settled/strip_to_identity),
# circle_objectives construction (build_briefing + ISSUE_MODEL),
# the four-block assembly (ORDER/block_order/system_blocks/
# load_shared/shared_block) and the transcript-to-messages view
# (render_messages) - verbatim, comments included. The names this
# file still calls are imported at the top.

# --------------------------------------------- the turn engine
# MOVED to rounds.py, 2026-08-16 (phase 2 stage 7, the last
# extraction): _TO_RE/_SELFNAME_RE + ask_statement, the blind round
# (BLIND_CLOSE/REVEAL_OPEN/run_blind_round), token_table,
# addressed_since and run_round — verbatim, comments included.
# main() imports run_round/run_blind_round/token_table at the top.


# ------------------------------------------------------------------ close
# THE CLOSE ASKS FOR TWO THINGS NOW, ruled 2026-08-19 (R255): the four
# short_term sections, and — after them, last — the part's one
# `[remember: "..."]` for the circle. The two are collected in ONE reply
# rather than a second call per part because the part is already holding
# the whole circle in mind at exactly this moment, and a second call would
# pay for that context twice.
#
# THE ORDERING IS LOAD-BEARING, not stylistic. markers.split_close_remember()
# is deliberately lenient about "]" so a 1000-word memory containing one
# cannot be silently truncated mid-sentence; the price of that lenience is
# that everything after the opener is the memory. Saying "last" here, in
# process_core.md, annotation and standing guidance alike, is what makes that safe — and
# collect_short_terms() still re-checks the four headings after the split
# and falls back to the strict parse if any went missing.
SHORT_TERM_PROMPT = (
    "The circle is closing. Write your short_term record of THIS circle, in "
    "exactly these four sections, in this order, with these exact headings:\n\n"
    "## What I said\n## What I observed in others\n"
    "## Shifts toward other parts\n## Current emotional state\n\n"
    "Write substantively under each heading — this is your own memory of the "
    "circle, and dreaming reads it when the circle closes. No preamble, "
    "no closing remarks, "
    "no other headings. Begin with '## What I said'.\n\n"
    "THEN, if you have one, write your one remember for this circle — "
    "LAST, after '## Current emotional state', on its own line:\n\n"
    '[remember: "<what you are choosing to carry forward>"]\n\n'
    "It is a private note to your own future self: never shown to Self, to "
    "another part, or to the room, and it is the only thing you write "
    "tonight that you will read again. Up to 1000 words. Write it in your "
    "own voice, about what you are keeping rather than what happened. "
    "One per circle — if you already used yours in a round, this one is "
    "dropped. Writing none is a real answer and costs you nothing."
)


CLOSING_MARK = "closing_{ot}.json"


def _close_mark(ot: str) -> pathlib.Path:
    return ROOT / "work" / "logs" / CLOSING_MARK.format(ot=ot)


def mark_close_started(ot: str) -> None:
    """Write the START-OF-CLOSE marker. LIVE closes only; callers gate it.

    THE ONE CASE _interrupted_closes() COULD NOT SEE, and its own docstring
    named the fix: "a marker written at the START of a close, which nothing
    writes today". A close that died before writing ANY short_term is
    indistinguishable from an /abort and from a circle still in progress, so
    the all-missing case had to be exempted — and after 45 minutes
    circle_state stops speaking to it too, leaving it reported by nothing.

    IT IS NEVER DELETED. A close report supersedes it: transcript_store writes
    close_<OT>.json as the last act of a completed close, and every reader here
    checks that first. A deletion step is one more thing that can fail on the
    path whose failures this exists to catch."""
    import json
    from atomic_write import atomic_write
    m = _close_mark(ot)
    m.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(m, json.dumps(
        {"open_time": ot,
         "started": datetime.datetime.now().isoformat(timespec="seconds")},
        indent=2) + "\n")


def redraw_issue_graph() -> None:
    """Redraw the picture of the issue graph, if the graph has moved since
    it was last drawn. LIVE closes only; the caller gates it.

    WHY AT A CLOSE. A circle is the one thing that moves this graph, and it
    moves it by two routes, both of which are complete by the time this
    runs: a ruling Self types at cmd> or embeds as an annotation, applied
    by issue_commands.apply() over the circle's own batch; and a
    `[proposed: ...]` row a part offered, accepted at the vetting
    checkpoint and applied by that same function through vetting.py.
    Drawing at the close rather than at each
    mutation means one picture per circle instead of one per ruling, and
    means the picture a person opens afterwards is of the graph they
    actually left behind.

    WHY A SUBPROCESS AND NOT AN IMPORT. ui/ is not on this process's
    sys.path and nothing in coordinator/ imports from it — the dependency
    runs the other way, ui/circling.py -> coordinator/. The literal
    "ui/issue_draw.py" below is also what packaging/scan.py resolves to
    make the tool (and its man page, by the docs-partner rule) ship at
    all; an import would leave the bundle without either.

    IT CANNOT FAIL THE CLOSE. Same contract as the coalesce refresh that
    runs a few statements earlier at the same checkpoint: any failure is
    one line on the command channel and the close carries on. This is a picture, not a record — nothing reads it
    back, and issue_draw.py has form for sitting broken unnoticed (its
    sys.path hop was wrong for eleven days because nothing ran it). It
    must never be what stands between a circle and its short_terms."""
    import subprocess
    try:
        r = subprocess.run(
            [sys.executable, "ui/issue_draw.py", "issues/", "--if-stale"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
    except Exception as e:                       # noqa: BLE001 — see docstring
        emit("command", f"  issue graph: not redrawn ({e})")
        return
    out = (r.stdout + r.stderr).rstrip()
    if r.returncode != 0:
        emit("command", f"  issue graph: not redrawn (exit {r.returncode})")
        if out:
            emit("command", out)
        return
    # SILENCE IS THE UNCHANGED CASE, and it is the common one — --if-stale
    # returns 0 having printed nothing when the picture is already right.
    if out:
        emit("command", "")
        emit("command", out)


def _close_began(ot: str) -> bool:
    """Did a close START for this circle? See mark_close_started()."""
    return _close_mark(ot).is_file()


def _failed_phase2(base: pathlib.Path) -> list[str]:
    """[open_time] for every circle whose dreaming/synthesis failed and has
    not been re-run since. Reported at open, 2026-08-23, ruled (R312).

    THE GAP. inter_circle writes work/logs/dream_error_<OT>.json, prints the
    re-run line and exits non-zero — at that close, once. Nothing mentioned it
    ever again: the transcript is committed and complete, every short_term is
    written, so _interrupted_closes() is right to stay quiet and circle_state
    has nothing to say either. The circle simply never moved anyone's identity,
    silently, from then on.

    THE TAG IS THE RESOLUTION, not the file. already_processed() reads
    `dream/<OT>` as the durable evidence a run succeeded — all-or-nothing
    staging means a failed run leaves nothing else behind — so a re-run that
    works clears this report without anyone tidying up a log. Asked through
    gitrepo.tag_name() so a lab tree asks about its own `dream/lab/<OT>`.

    QUIET ON ANYTHING IT CANNOT READ, the same rule as _interrupted_closes():
    this runs in the open path, and git being unavailable is not a reason to
    refuse to start a circle."""
    logs = ROOT / "work" / "logs"
    if not logs.is_dir():
        return []
    out = []
    for f in sorted(logs.glob("dream_error_*.json")):
        ot_i = f.stem[len("dream_error_"):]
        if ot_i.endswith("_raw"):
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}", ot_i):
            continue
        if not (base / f"circle_{ot_i}.md").is_file():
            continue
        # EITHER MARKER RESOLVES IT, 2026-08-24. Since the operator ruled
        # git optional, a completed phase 2 records itself in
        # work/logs/dream_<OT>.json as well as (or, in a tree with no git
        # history, instead of) the tag — so this asks the file first and
        # never reaches git in a bundle.
        if (logs / f"dream_{ot_i}.json").is_file():
            continue                                     # processed
        try:
            import gitrepo as _G
            rc, tags = _G.run("tag", "-l", _G.tag_name("dream", ot_i),
                              read_only=True)
            if rc != 0 or tags.strip():
                continue                 # processed, or git could not tell
        except Exception:                                        # noqa: BLE001
            continue
        out.append(ot_i)
    return out


def _interrupted_closes(base: pathlib.Path) -> list[tuple[str, list[str]]]:
    """[(open_time, parts that spoke with no short_term)] for every LIVE
    circle whose close was interrupted. Reported at open, 2026-08-20.

    THE TEST IS THE RESUME GATE'S, NOT circle_state'S, and that is the
    whole point of the function. circle_state asks "has this transcript
    been quiet for 45 minutes" — a heuristic for "is someone still in
    there", which an interrupted close passes cleanly the moment it is
    older than the window. On 2026-08-20 a live close died with four of
    seven short_terms written; by the time anyone looked, circle_state
    called it finished and the next open would have said nothing.

    A CLOSE REPORT MEANS FINISHED. transcript_store writes it as the last
    act of a completed close, so its presence ends the question no matter
    what the parts directory looks like.

    QUIET ON ANYTHING IT CANNOT READ. This runs in the open path, before
    a circle exists; an unparseable old transcript is not a reason to
    refuse to start a new one, and the audit is where that belongs.

    THE CASE NOTHING SAW IS SEEN SINCE 2026-08-23, and this paragraph
    said otherwise until 2026-08-27. A close that died before writing ANY
    short_term used to be indistinguishable here from an /abort, and
    indistinguishable to circle_state once the transcript had been quiet
    45 minutes — reported by neither, after that window. It asked for a
    marker written at the START of a close; mark_close_started() is that
    marker, and the all-missing branch below consults it.

    THE RESIDUE IS HISTORY, and it does not shrink: a circle that closed
    BEFORE the marker existed has none, so for those the old exemption
    stands exactly as it did, and circle_audit.py's transcript safety net
    is still the only thing that catches them — by hand. The exemption
    itself is deliberate and stays: without a marker, all-missing is what
    a circle actually in progress looks like, which is what
    circle_state's own warning is for."""
    out: list[tuple[str, list[str]]] = []
    for f in sorted(base.glob("circle_*.md")):
        ot_i = f.stem[len("circle_"):]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}", ot_i):
            continue
        if (ROOT / "work" / "logs" / f"close_{ot_i}.json").is_file():
            continue
        try:
            _, _, tr = TS.parse_transcript(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        spoke = {e["speaker"] for e in tr if e["speaker"] in PART_TAGS}
        if not spoke:
            continue
        missing = sorted(p for p in spoke
                         if not (ROOT / "parts" / p /
                                 f"short_term_{ot_i}.md").is_file())
        # ALL of them missing is an OPEN circle or an /abort, not an
        # interrupted close — collect_short_terms writes in roster order,
        # so a genuine interrupt leaves SOME written. circle_state's own
        # warning above is what speaks to that case.
        #
        # UNLESS A CLOSE ACTUALLY BEGAN, 2026-08-23. mark_close_started()
        # settles the ambiguity this exemption was built around: with the
        # marker on disk the circle is neither open nor aborted, so
        # all-missing is a real interrupted close and the last case nothing
        # reported is reported. Without one — every circle closed before the
        # marker existed — the exemption stands exactly as it did.
        if missing and (len(missing) < len(spoke) or _close_began(ot_i)):
            out.append((ot_i, [PART_TAGS[p] for p in missing]))
    return out


def collect_short_terms(client, parts, sysblocks, transcript, ot, guard, dry) -> list[str]:
    spoke = {e["speaker"] for e in transcript}
    written, failed = [], []
    for part in parts:
        if part not in spoke:
            emit("command", f"  {part:<12} did not speak — no short_term")
            continue
        dest = (SANDBOX / "parts" / part / f"short_term_{ot}.md") if not guard.live \
            else (ROOT / "parts" / part / f"short_term_{ot}.md")
        if dest.is_file():
            # An interrupted close already wrote this one — the resume
            # gate let the circle back in for exactly this case. The
            # first write is the record; re-deriving would overwrite it
            # with a second telling (and pay for the call again). Listed
            # in `written` so commit_circle stages it — the interrupt
            # died before any commit.
            emit("command", f"  {part:<12} kept — written before the interrupt")
            written.append(part)
            continue
        # One loop, two attempts (2026-08-19, review tier 5 #47): the
        # retry used to be a verbatim copy-paste of the first call four
        # lines apart, so any change to the request — budget, prompt,
        # a stop-reason check — had to land twice or the retry silently
        # issued the old one. Semantics unchanged: attempt 1 retries on
        # a missing section OR truncation; the retry's own result is
        # judged on sections alone, exactly as before.
        for attempt in (1, 2):
            # 5000, not 2000 (R255): four substantive sections plus a
            # remember of up to 1000 words does not fit in 2000, and the
            # failure mode is not a short answer — it is stop ==
            # "max_tokens", which this loop RETRIES, so an under-budget
            # close would have paid for two truncated calls per part and
            # then written the second one anyway.
            text, stop = call(
                client, part, sysblocks[part],
                render_messages(part, transcript, SHORT_TERM_PROMPT), 5000, dry,
                kind="short_term",
            )
            missing = [h for h in SHORT_TERM_SECTIONS if h not in text]
            if not (missing or stop == "max_tokens") or attempt == 2:
                break
            emit("command", f"  {part:<12} FAILED ({'truncated' if stop == 'max_tokens' else 'missing ' + missing[0]}) — retrying")
        if missing:
            failed.append(part)
            emit("command", f"  {part:<12} FAILED — not written")
            continue

        # THE REMEMBER COMES OUT BEFORE THE FILE IS WRITTEN (R255). A
        # short_term is read by dreaming and by circle_audit; a remember
        # reaches only this part's own BLOCK 4. Leaving the bracket in the
        # .md would put a private note into the one document another
        # process reads on the part's behalf.
        #
        # FALLBACK ON A LOST SECTION. split_close_remember() takes
        # everything after the opener, which is what makes a "]" inside a
        # long memory safe; if a part wrote the bracket mid-reply instead
        # of last, that would swallow a heading. So the split is checked,
        # not trusted: if any of the four went missing, the strict ASK_RE
        # path (apply_remember) runs instead — it keeps the sections and
        # gives up only the lenience.
        #
        # THE CHECK RUNS BEFORE ANY WRITE, and that ordering is the whole
        # correctness of the fallback. split_close_remember() is PURE, so
        # it can be consulted first. Deciding afterwards — writing the
        # lenient record, then noticing a heading had gone — would leave
        # the swallowed-heading version on file AND have the strict retry
        # refuse itself as a second use this circle, since has_remembered()
        # would already be True. One cap, read once, spent once.
        if [h for h in SHORT_TERM_SECTIONS
                if h not in MK.split_close_remember(text)[0]]:
            text, recorded = apply_remember(
                guard, part, PART_TAGS[part], text)
        else:
            text, recorded = MK.apply_close_remember(
                guard, part, PART_TAGS[part], text)
        if recorded:
            emit("command", f"  {part:<12} remember written")
        header = (f"# Short-term — {PART_TAGS[part]} — "
                  f"{ot[:10]} {ot[11:]}\n\n*(Written by the local coordinator.)*\n\n")
        guard.check(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_lf(dest, header + text.strip() + "\n")
        written.append(part)
        emit("command", f"  {part:<12} wrote {dest}")
    if failed:
        fail(f"short_term NOT WRITTEN for: {', '.join(failed)} — these parts spoke "
             f"but have no record; the nightly transcript safety net will have to "
             f"backfill them from circles/circle_{ot}.md")
    return written


# MOVED to transcript_store.py, 2026-08-16 (phase 1 step 3):
# commit_sandbox, commit_circle and run_verifier - the durable close
# records. collect_short_terms above STAYS here: it calls the
# Messages API per part, which makes it close orchestration, not
# persistence (phase-1 review).


# -------------------------------------------------------------- statements
# MOVED to commands.py, 2026-08-16 (phase 2 stage 6, built fifth):
# statements()/resolve_statement()/show_statements() — the 1-based
# numbering /issue-evidence-list shows and `/issue-evidence-add` resolves
# against. Imported at the top of this file.

# --------------------------------------------- the annotation system
# MOVED to markers.py, 2026-08-16 (phase 2 stage 3): ASK_RE and the
# whole bracket grammar (_propose_command_shape/extract_markers —
# PRACTICE_KINDS and BPID_RE went with the six retired keywords,
# 2026-08-20), REMEMBER's write path (REMEMBER_RE/
# apply_remember/apply_self_remember), the malformed/retired strip
# (strip_malformed_markers; RETIRED_REQUEST_RE and
# NEAR_MISS_PROPOSED_RE are gone — an unrecognised bracket is dialog
# text now), live routing
# (route_markers), unruled_proposals, the close-time coalescing
# (_norm_text/
# propose_proposals/coalesce_propose_proposals/_normalize_edge/
# convergence_queue), the staging writer (
# stage_propose_proposals), show_unruled_proposals and _wrap58 - verbatim,
# comments and R202 included. The names this file still calls are
# imported at the top; test-only names are re-exported beside them.
# Vetting MOVED to vetting.py, 2026-08-16 (phase 2 stage 4, built
# sixth): graph_now (per Self's ruling — _propose_approve is its one
# consumer), _practice_describe/_practice_approve/_propose_describe/
# _propose_approve/_propose_deny and vet_pending_proposals — verbatim,
# comments included. main() imports vet_pending_proposals at the top;
# the test surface reaches everything else on vetting directly.



# ------------------------------------------------------------------ main
# COMMANDS, KNOWN_CMDS, PANE_OF, DEV_MIN_CMDS and dev_mode MOVED to
# command_surface.py, 2026-08-16 (phase 2 stage 0; dev_mode's move
# ruled by Self explicitly) - comments included, the ONE-TABLE
# 2026-08-05 ruling and the third-column pane classification with
# them. The table is read from three directions (this loop, the help
# system, circling's command pane) and stages 3-7 put those readers
# in separate modules; a leaf module below all of them is what keeps
# the later extractions acyclic. dev_mode is REBOUND at runtime:
# every read and write in this file goes through CS.dev_mode
# attribute access, same contract as seam.emit.

# --------------------------------------------------------------------------
# The help system MOVED to help_system.py, 2026-08-16 (phase 2 stage
# 5, built fourth): the hot-reloaded object-class table (_hot_load/
# OBJECT_CLASSES_PATH/object_classes and kin), the issue/relationship
# read-outs, _HELP_ONE_LINERS, the dev-tiered _help_level0,
# HELP_WIDTH/_wrap80, help_text/_help_text_raw, cmd_help and
# dev_restricted_text — verbatim, comments included. The names this
# file still calls are imported at the top; test-only names are
# re-exported beside them.

def _prompt_blocks_changed(orig: pathlib.Path, new: pathlib.Path,
                           parts: list[str]) -> list[str]:
    """Parts whose EMITTED PROGRAM differs between two captures.

    Compares the manifests' per-block sha256, never the capture files, whose
    headers legitimately differ. Returns every part on any error — an unreadable
    manifest must read as "cannot show it is the same", not as "it is"."""
    try:
        import prompt_capture as PC
        a = PC.block_shas(PC.read_manifest(orig))
        b = PC.block_shas(PC.read_manifest(new))
    except Exception:
        return list(parts)
    out = []
    for p in parts:
        ha, hb = a.get(p, []), b.get(p, [])
        if not ha or ha != hb:
            out.append(p)
    return out


def list_resumable() -> int:
    """Circles with a transcript and no close report — including a close
    Ctrl-C interrupted mid-collection (some short_terms written, some
    speaking parts still without; until 2026-08-19 any short_term at all
    hid the circle here, the same over-wide test the --resume gate used).
    A circle whose every speaking part has its short_term is a finished
    close from before close reports existed, and stays hidden. Read-only."""
    rows = []
    for f in sorted((ROOT / "circles").glob("circle_*.md")):
        ot = f.stem[len("circle_"):]
        if (ROOT / "work" / "logs" / f"close_{ot}.json").is_file():
            continue
        done = {p.parent.name
                for p in (ROOT / "parts").glob(f"*/short_term_{ot}.md")}
        try:
            topic, tr, _, _ = load_for_resume(f, ot, DEFAULT_PARTS)
            spoke = {e["speaker"] for e in tr if e["speaker"] in PART_TAGS}
            if done and not (spoke - done):
                continue                     # closed, pre-close-report era
            n = sum(1 for e in tr if e["speaker"] in PART_TAGS)
            note = f"{n} statement(s)"
            if done:
                note += (f" — close interrupted, "
                         f"{len(spoke - done)} short_term(s) missing")
            rows.append((ot, note, (topic or "(no topic)")[:40]))
        except ValueError as e:
            rows.append((ot, "NOT RESUMABLE", str(e).split("\n")[0][:40]))
    if not rows:
        emit("command", "\n  no unclosed circles.")
        return 0
    emit("command", f"\n  {len(rows)} circle(s) with no close report:\n")
    for ot, n, why in rows:
        emit("command", f"    {ot}")
        emit("command", f"        {n}")
        emit("command", f"        {why}")
    return 0


# --------------------------------------------------------------------------
# The ic.py-era dev commands and their dispatcher MOVED to
# commands.py, 2026-08-16 (phase 2 stage 6, built fifth):
# cmd_prompt_show, cmd_topic_list/close, cmd_practice_list/delete/
# add, _run_captured, cmd_issue_apply, cmd_issue_status_show/set/op,
# dispatch_dev_cmd and cmd_issue_object — verbatim, the STAGE 2
# ruling and R161 comments included. Until B61 (2026-08-21) this file
# still CALLED ten of them by name from its own Self> loop, one branch
# each, duplicating dispatch_dev_cmd()'s chain; the loop now delegates
# to that one dispatcher and only dispatch_dev_cmd/resolve_statement/
# show_statements are imported. test_dispatch_partition.py keeps it so.


def main() -> int:
    # dev_mode lives in command_surface since 2026-08-16 (phase 2 stage
    # 0, ruled) — every read and write here is CS.dev_mode attribute
    # access, so the old `global dev_mode` declaration (and the
    # SyntaxError trap its comment documented for a second one) is gone
    # with the global itself.
    #
    # A NEW RUN REPORTS THE UNCONFIGURED-GIT NOTE AFRESH — once per circle
    # (R349, 2026-08-25). The flag is module
    # state in gitrepo, and one UI process can run main() more than once.
    try:
        import gitrepo
        gitrepo.reset_unconfigured_report()
    except ImportError:
        pass
    ap = argparse.ArgumentParser(description="IFS circle — local coordinator")
    ap.add_argument("--live", action="store_true",
                    help="write to circles/ and parts/<name>/short_term_<OT>.md "
                         "and run coordinator/circle_close.py at close")
    ap.add_argument("--dry-run", action="store_true",
                    help="no network, no API key needed; every part passes")
    ap.add_argument("--parts", default=",".join(DEFAULT_PARTS),
                    # COUNTED, NOT TYPED. This read "the six speaking parts"
                    # while the default has been every part in the roster —
                    # and the roster is now whatever parts/ holds (R123), so
                    # any number written here is wrong for someone.
                    help=f"comma-separated part dirs (default: all "
                         f"{len(DEFAULT_PARTS)} part(s) in parts/). "
                         f"A reduced roster is for TESTING — omitted parts are "
                         f"absent from the circle and stay unaware of it.")
    ap.add_argument("--no-prewarm", action="store_true",
                    help="skip prewarm() — the sequential, zero-output-token "
                         "calls that write each part's cached prompt prefix "
                         "before the opening round. Without it, the opening "
                         "round pays the cache-write cost on the first real "
                         "turn instead — redundantly, per concurrently-firing "
                         "part, under the default BLIND round. CACHE_TTL is "
                         "1h (chosen because circles pause longer than the "
                         "5m default), so a warmed cache ordinarily survives "
                         "to the opening round; it can still go stale if the "
                         "gap before the first real turn exceeds that hour. "
                         "Independent of --no-blind, which controls the "
                         "opening round's own protocol, not whether the "
                         "cache is warmed first.")
    ap.add_argument("--no-blind", action="store_true",
                    help="run the PRIOR protocol: a sequential opening round. "
                         "CIRCLE_DESIGN.md requires each protocol change to keep "
                         "the ability to run what came before, because these "
                         "change the loop that runs live circles.")
    ap.add_argument("--seed", type=int,
                    help="seed for random.shuffle, which sets the order parts are "
                         "polled within a round. Fixing it makes a test repeatable; "
                         "it has no effect on what the parts say. Omit for real circles.")
    ap.add_argument("--yes", action="store_true",
                    help="skip the confirmation prompt for a reduced live roster")
    ap.add_argument("--resume", metavar="OPEN_TIME",
                    help="reopen an unclosed circle, e.g. --resume 2026-08-02_1259. "
                         "The transcript must round-trip byte-for-byte or the "
                         "resume is refused. No topic prompt and no opening "
                         "round: the circle continues where it stopped.")
    ap.add_argument("--dev", action="store_true",
                    help="open with dev mode ON — the DEV-table verbs and the "
                         "help hierarchy answer at this terminal's Self> "
                         "prompt. Default: off. The standalone terminal's only "
                         "door since 2026-08-21: /dev at the circle prompt is "
                         "gone (dev is the command pane's own unlisted verb).")
    ap.add_argument("--list-resumable", action="store_true",
                    help="show circles that have a transcript but no close report")
    ap.add_argument("--dev-cmd", nargs=argparse.REMAINDER, metavar="VERB ...",
                    help="run ONE always-available command directly from the "
                         "shell, no circle needed — the ic.py replacement, "
                         "RULED 2026-08-13 ('ic.py is a development tool... "
                         "able to operate independently of any circle in "
                         "progress'). Bypasses dev_mode entirely: this is "
                         "already a deliberate shell invocation, not "
                         "something that could leak into a running circle. "
                         "e.g. --dev-cmd practice-list, --dev-cmd "
                         "practice-add \"text\", --dev-cmd issue n0002 "
                         "status. issue-label-update/issue-relationship-add/"
                         "close/abort/etc. are refused here — they attest against "
                         "a transcript, so they need an actual circle open.")
    args = ap.parse_args()

    # --dev: dev mode ON from the open (R286, 2026-08-21).
    # The Self> loop no longer recognises /dev — "dev should not be parsed in
    # circle dialog, nor recognised at self's circle prompt; it is cmd> only
    # and always hidden" — so the standalone terminal, which has no cmd>,
    # takes its dev state from this flag. The dual pane's command pane has
    # its own unlisted `dev`, and --dev-cmd forces dev on for its one call.
    if args.dev:
        CS.dev_mode = True

    if args.list_resumable:
        return list_resumable()

    if args.dev_cmd is not None:
        if not args.dev_cmd:
            emit("command", "  usage: --dev-cmd VERB [args...], e.g. "
                  "--dev-cmd practice-list")
            return 2
        head = CS.normalise_head(args.dev_cmd[0])
        rest_text = " " + " ".join(args.dev_cmd[1:]) if len(args.dev_cmd) > 1 else ""
        # "Bypasses dev_mode entirely" (help text above) was written but
        # never enforced — dev_mode defaults False at process start, so
        # e.g. `--dev-cmd help object_classes` hit the same gate a
        # command-pane user with dev off would, contradicting this door's
        # own documented contract. (The `global dev_mode` SyntaxError trap
        # the old comment documented died with the global itself —
        # CS.dev_mode is a plain attribute write now.)
        CS.dev_mode = True
        if not dispatch_dev_cmd(head, rest_text):
            emit("command", f"  {head} needs a live circle — not available via "
                  "--dev-cmd. Open one (or use circling's command pane while "
                  "one is running) for /issue-evidence-list, /issue-label-update, "
                  "/issue-relationship-add, /close, /abort, "
                  "/status.")
            return 2
        return 0

    # THE ROSTER IS READ FROM parts/, SO CHECK IT BEFORE OPENING ON IT.
    # R123: the part list is no longer typed here, it is whatever
    # `parts/*/part.toml` says. That makes a missing or malformed marker a
    # SHRINKING roster rather than an error — and a part outside the roster
    # is absent from the transcript, writes no short_term, and reads
    # downstream as no engagement rather than as a fault. Refused, not
    # warned, and refused for a sandbox run too: a probe that opens on six
    # parts and reports success is the failure this guards.
    roster_problems = R.verify()
    if roster_problems:
        emit("command", "\n  !! THE ROSTER DOES NOT VERIFY — no circle opened.")
        for p in roster_problems:
            emit("command", f"     {p}")
        emit("command", f"\n     {len(DEFAULT_PARTS)} part(s) would have been in this "
              f"circle: {', '.join(DEFAULT_PARTS) or '(none)'}")
        emit("command", "     python coordinator/roster.py")
        return 2

    if not args.live and not args.dry_run:
        # THE PRACTICE MODE IS RETIRED — R250 deprecated it in favor of the
        # lab, and R360 (D65 a) executed the retirement: a bare invocation
        # used to open a REAL-model circle whose writes went to
        # work/sandbox/ — a person practicing outside the record. The lab
        # is where practice lives now; --dry-run (no model calls, every
        # part passes) remains the harnesses' own mode, unchanged.
        emit("command", "Choose a mode: --live (the real circle) or "
                        "--dry-run (no model calls; the test rig).")
        emit("command", "  For practice without touching the record, use "
                        "the lab checkout instead — a full copy")
        emit("command", "  of the app whose record never merges back "
                        "(R249).")
        return 2


    parts = [p.strip() for p in args.parts.split(",") if p.strip()]
    bad = [p for p in parts if p not in PART_TAGS or not (ROOT / "parts" / p).is_dir()]
    if bad:
        emit("command", f"unknown part(s): {', '.join(bad)}")
        return 2
    if args.seed is not None:
        random.seed(args.seed)

    # A reduced roster is a testing affordance. In a LIVE circle it has a real
    # cost: an omitted part is absent from the transcript, writes no short_term,
    # and dreaming reads "no short_term for this circle" as no
    # engagement (inter_circle.dream_one()) — indistinguishable from
    # a part who was present and chose silence. It gets no dream entry and no
    # relationship update. It learns of the circle only indirectly, through
    # whatever the issue graph's state has become by the next circle it attends.
    missing_roster = [p for p in DEFAULT_PARTS if p not in parts]
    if args.live and missing_roster:
        emit("command", "\n  !! REDUCED LIVE ROSTER")
        emit("command", f"     absent: {', '.join(PART_TAGS[p] for p in missing_roster)}")
        emit("command", "     These parts will not be present, will write no short_term, and")
        emit("command", "     the nightly will record no engagement for them. They will learn")
        emit("command", "     of this circle only indirectly, via the issue graph's state next")
        emit("command", "     time they attend. Prefer sandbox mode for partial rosters.")
        if not args.yes and read_line("     type 'yes' to proceed: ").strip().lower() != "yes":
            emit("command", "     cancelled.")
            # 2, NOT 1. Exit 1 means a circle RAN and its record is
            # incomplete — the thing the nightly must be told about. A
            # cancelled open produced no record at all, and a caller that
            # cannot tell those apart learns nothing from either. Was 1
            # until 2026-08-09, when the contract was written down and the
            # code was found to disagree with it.
            return 2

    # THE OPEN TIME IS MINTED WHEN THE TRANSCRIPT IS OPENED, not when the
    # process starts. It used to be minted here, before two blocking input()
    # calls — so circle_2026-08-09_1507.md was written at 15:13:08, six
    # minutes after the name it carries. The name is the record's only
    # timestamp; it should say when the record began, not when someone
    # launched the program that would later begin it.
    #
    # A RESUME still knows its open time up front: it is the argument.
    def circle_path(t: str) -> pathlib.Path:
        return (ROOT if args.live else SANDBOX) / "circles" / f"circle_{t}.md"

    ot: str | None = args.resume
    guard: WriteGuard | None = None
    path: pathlib.Path | None = None
    if args.resume:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}", ot):
            emit("command", f"--resume wants an open time like 2026-08-02_1259, got {ot!r}")
            return 2
        closed = ROOT / "work" / "logs" / f"close_{ot}.json"
        done = sorted((ROOT / "parts").glob(f"*/short_term_{ot}.md"))
        if args.live and closed.is_file():
            emit("command", f"\n  circle_{ot} is already closed — refusing to reopen it.")
            emit("command", f"     close report: {closed.relative_to(ROOT)}")
            for f in done:
                emit("command", f"     short_term:   {f.relative_to(ROOT)}")
            emit("command", "     A closed circle is a finished record. Open a new circle.")
            return 2
        if args.live and done:
            # Short_terms without a close report — either a close that
            # Ctrl-C interrupted mid-collection (2026-08-18 review, tier 2
            # #15: the interrupt handler ADVERTISES `--resume`, and this
            # gate then refused it, so the advertised recovery was
            # unusable in exactly the state it printed for), or an
            # older-era close from before close reports existed. The
            # transcript itself tells the two apart: an interrupted close
            # has a SPEAKING part with no short_term; a finished one does
            # not. collect_short_terms() keeps the already-written files,
            # so resuming an interrupted close collects only the missing.
            try:
                _, _, tr0 = TS.parse_transcript(
                    circle_path(ot).read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                emit("command", f"\n  circle_{ot} has short_terms but its "
                      f"transcript will not parse — refusing to resume: {e}")
                return 2
            spoke0 = {e["speaker"] for e in tr0 if e["speaker"] in PART_TAGS}
            missing0 = sorted(spoke0 - {p.parent.name for p in done})
            if not missing0:
                emit("command", f"\n  circle_{ot} is already closed — every "
                      f"part that spoke has its short_term (a close from "
                      f"before close reports existed). Refusing to reopen.")
                return 2
            emit("command", f"\n  circle_{ot}: close was interrupted — "
                  f"{len(done)} short_term(s) already written, "
                  f"{len(missing0)} still missing ({', '.join(missing0)}).")
            emit("command", "     resuming; /close will keep the written "
                  "ones and collect only the missing.")
        guard = WriteGuard(args.live, ot)
        path = circle_path(ot)

    client = None
    if not args.dry_run:
        try:
            from anthropic import Anthropic
        except ImportError:
            emit("command", "pip install anthropic")
            return 2
        if not os.environ.get("ANTHROPIC_API_KEY"):
            try:
                from dotenv import load_dotenv
                load_dotenv(ROOT / ".env")
            except ImportError:
                pass
        if not os.environ.get("ANTHROPIC_API_KEY"):
            # HOW TO GET ONE, WHERE TO PUT IT, HOW TO KEEP IT — R330,
            # 2026-08-23. This printed one line, `set
            # ANTHROPIC_API_KEY (env var or project .env)`, which is the whole
            # answer for the person who wrote it and none of the answer for
            # a first-run user. The text lives beside the API check.
            emit("command", "\n" + KEY_MISSING_HELP + "\n")
            return 2
        client = Anthropic()

    mode = "LIVE" if args.live else "sandbox"
    emit("command", f"\nIFS circle coordinator — {mode} — "
          f"{ot or 'open time assigned when the topic is entered'}")
    # B56(1), 2026-08-19: NAME THE TREE, at open. Named as the one thing to
    # watch on 2026-08-04 and never built. paths.ROOT is derived from
    # __file__, so a circle run inside a worktree already reads and writes
    # only that worktree — which is what makes running a LIVE circle in a lab
    # tree by mistake both possible and, until this line, invisible.
    #
    # gitrepo owns the question — one home for it, since the tag namer
    # (B56(5)) asks it too and two copies of "am I in a lab" would be the
    # three-copies problem B57(2) just finished undoing.
    import gitrepo as _G
    in_main_checkout = _G.in_main_checkout()
    emit("command", f"tree: {ROOT}"
         + ("" if in_main_checkout else "   (A WORKTREE, not the main checkout)"))
    if args.live and not in_main_checkout:
        # The files are contained by construction; the REFS are not. A
        # worktree shares .git, so this circle's own `circle/<OT>` and its
        # processing's `dream/<OT>` land in the repository-wide namespace the
        # main tree's already_processed() reads. B56(5) is the fix; until it
        # lands, saying so is.
        emit("command", "  !! LIVE, IN A WORKTREE. Files are this tree's "
                        "alone; the TAG namespace is the repository's, shared "
                        "with the main checkout (NEXT.md B56).")
    emit("command", f"parts: {', '.join(parts)}")
    if path:
        emit("command", f"transcript: {path}")
    if not args.live:
        # B32 + R176: the old text said "work/ is write-protected", which was
        # already false (work/logs/ is written via circle_close.py) and became
        # doubly so when sandbox output moved UNDER work/. Name the one root
        # that is actually writable instead of listing what is not.
        emit("command", "sandbox mode: writes land under work/sandbox/ only; "
                        "circles/ and parts/ are untouched.")

    # THE INTEGRITY GATE, ahead of even the API check. It needs no client, no
    # network and no key, so a corrupted tree is discovered at zero cost — and
    # discovered BEFORE the working set and the topic are asked for, which is the
    # same ruling that put the API check here (2026-08-09): a failure that costs a
    # re-typed topic gets fixed by moving the check earlier, not by apologising.
    #
    # IT REFUSES; it does not warn. The circle_state check below deliberately only
    # warns, because only Self can know whether a listed circle was meant to be
    # resumed — that is a question. This is not: nothing downstream of here can
    # tell a corrupt file from a deliberate one, which is precisely why a part
    # once went dark rather than raised. Opening on a known-corrupt tree writes
    # that corruption into a transcript and, at close, into a sha256 that makes it
    # the record. There is no --force; the remedy is a git checkout.
    emit("command", "\nintegrity check:", end=" ", flush=True)
    _findings, _seen = CI.sweep()
    if _findings:
        emit("command", "FAILED")
        emit("command", f"\n  !! {len(_findings)} operational file(s) are corrupted. "
                        f"The circle was NOT opened.\n")
        for _f in _findings:
            emit("command", f"     {_f.path}")
            emit("command", f"         {_f.defect}")
            emit("command", f"         {_f.remedy}")
        emit("command", "\n     Nothing was written — no transcript, no working-set "
                        "entry, no API call.\n     Repair or restore the file(s) "
                        "above, then open again.")
        return 2
    emit("command", f"ok ({_seen} files)")

    # THE API CHECK, as early as it can be run: the client exists, and nothing
    # has been typed or written. See the preflight block above for the ruling.
    if note := key_source_note():
        emit("command", f"\n  !! {note}")
    if client is not None:
        emit("command", "\napi check:", end=" ", flush=True)
        if why := preflight_api(client, args.dry_run):
            emit("command", "FAILED")
            emit("command", f"\n  !! {why}")
            emit("command", "\n     Nothing was written — no transcript, no working-set "
                  "entry.\n     Fix the key and open again; the topic has not "
                  "been asked for yet.")
            return 2
        emit("command", "ok")

    # IS A CIRCLE ALREADY OPEN? CLAUDE.md has required this before any write
    # under circles/ since 2026-08-06 (LOG.md E12) and circle.py — the one
    # program that writes there — never called it.
    #
    # A WARNING, NOT A REFUSAL, and the distinction is load-bearing.
    # circle_state fails closed and calls a transcript open until it has been
    # quiet 45 minutes, so a hard refusal here would have blocked the 15:20
    # retry that recovered from the 15:07 failure — turning a fix for that
    # incident into a worse version of it. The unambiguous case, a transcript
    # already at THIS open time, is refused outright below; this one is a
    # question, because only Self knows whether the listed circle is one he
    # meant to resume.
    if not args.resume:
        try:
            import circle_state
            base = ((ROOT if args.live else SANDBOX) / "circles").resolve()
            openc = [c for c in circle_state.open_circles()
                     if _within(c["path"].resolve(), base)]
        except Exception as e:                                   # noqa: BLE001
            openc = [{"path": pathlib.Path("(unknown)"),
                      "why": f"circle_state could not tell: {e}"}]
        # AND THE QUESTION circle_state CANNOT ASK, added 2026-08-20
        # (R264 / R264). circle_state
        # asks "has this transcript been quiet 45 minutes"; an interrupted
        # CLOSE is silent to that the moment it is older than the window,
        # and on 2026-08-20 it was: a live close died with four of seven
        # short_terms written and the next open reported nothing at all.
        # The resume gate already knows the real test — a part SPOKE, has
        # no short_term, and there is no close report — so ask it here,
        # where it can still be acted on.
        interrupted = _interrupted_closes(base) if args.live else []
        for ot_i, missing_i in interrupted:
            emit("command", f"\n  !! circle_{ot_i}: its CLOSE was interrupted.")
            emit("command", f"     {len(missing_i)} part(s) spoke and have no "
                  f"short_term: {', '.join(missing_i)}")
            emit("command", "     Nothing is lost — the transcript is written "
                  "statement by statement.")
            emit("command", f"     finish it:  python coordinator\\circle.py "
                  f"--live --resume {ot_i}")
        # AND THE FAILURE THAT IS REPORTED ONCE AND NEVER AGAIN, 2026-08-23.
        # A circle whose dreaming/synthesis failed is COMPLETE by every test
        # above — transcript committed, every short_term written — so nothing
        # here spoke to it after the close that printed the re-run line. See
        # _failed_phase2(); the `dream/<OT>` tag is what clears it.
        for ot_f in _failed_phase2(base):
            emit("command", f"\n  !! circle_{ot_f}: its DREAMING did not run.")
            emit("command", "     The circle itself is complete and committed; "
                  "nothing was")
            emit("command", "     written by the failed run, so the re-run is "
                  "clean.")
            emit("command", f"     work/logs/dream_error_{ot_f}.json says why.")
            emit("command", f"     run it:     python coordinator\inter_circle.py "
                  f"--ot {ot_f} --live")
        if openc:
            emit("command", f"\n  !! {len(openc)} circle(s) may still be OPEN:")
            for c in openc:
                emit("command", f"     {c['path']}\n       {c['why']}")
            emit("command", "     If one of these is the circle you meant to continue,")
            emit("command", "     cancel and use --resume <open time> instead.")
            if not args.yes and read_line(
                    "     type 'yes' to open a NEW circle: ").strip().lower() != "yes":
                emit("command", "     cancelled.")
                return 2               # never opened — see the note above

    # CHECKPOINT 2, before prewarm — docs/BNF.md PRACTICE LIFECYCLE,
    # Vetting: <practices>/<part_practices> are cached prefixes (BLOCK 1,
    # BLOCK 3), so an approval landing after prewarm misses the circle it
    # was approved for. NOT on --resume: a resume is recovering a circle
    # whose prompts were already warmed under today's register: re-vetting
    # here would change BLOCK 1 out from under an in-flight transcript.
    # NEXT.md D14,
    # 2026-08-17: no longer `and args.live` — vet_pending_proposals() now
    # runs in sandbox too, describing and validating without ruling.
    if not args.resume:
        # THE COALESCE REFRESH, R356 (B69) — hash-guarded, so it makes a
        # model call only when the pending set changed since it last ran.
        # It lives HERE, at the real checkpoints, and NOT inside
        # vet_pending_proposals(): the suites drive that loop live against
        # temp registers, and a refresh inside it sent a real model call
        # from a test run (E22). Live only; fails open — a suggestion pass
        # must never block a circle's open.
        if args.live:
            try:
                import coalesce as CG
                CG.refresh_if_stale(say=lambda m: emit("command", m))
            except Exception as e:
                emit("command", f"  coalesce: skipped ({e})")
        vet_pending_proposals("before this circle's prompts are warmed", args.live)

    # INITIALIZATION — R330 (docs/Initialization.md §2): the first-run
    # dialogs, between CHECKPOINT 2 and the working-set question, so THIS
    # circle's blocks are built from what they record — the Soul's and
    # Child's context (R331) and, while issues/ is empty, one first issue
    # (R324/R328). run_initialization() holds the four skips itself (not
    # live, resume, --yes, no interactive surface) and is silent when
    # nothing is due; it ends with "Starting your circle..." and the focus
    # handover ("state" tokens) when anything fired.
    import initialization as INIT
    INIT.run_initialization(live=args.live, resume=args.resume, yes=args.yes)

    # THE ANSWER NAMES THE CONSOLE THE SAME CIRCLE IT IS GIVEN. CONSOLE_NAME
    # was bound once, at import — BEFORE the dialog above records
    # preferred_name — so the first circle a person ever ran kept showing the
    # .env name they were asked to replace (found 2026-08-25, the "Sally"
    # install: the answer landed in part.toml, R325's order resolves it
    # first, and the prompt said the old name anyway). Re-resolve after the
    # dialog: this module's own Self> prompt and ui/circling's _circle_prompt
    # both read the attribute at each render, so both follow. transcript_
    # store's copy is rebound too — it compares historic Self tags with it.
    global CONSOLE_NAME
    CONSOLE_NAME = ID.user_name()
    TS.CONSOLE_NAME = CONSOLE_NAME

    core = load_shared()
    # ONE BUILD, AFTER the working set is chosen — RULED 2026-08-19 (R244;
    # 2026-08-18 review #58, second half). The open used to build every
    # part's blocks for the whole graph BEFORE asking, then rebuild them
    # all for the chosen set — and the first build's only surviving output
    # was a whole-graph price line plus the "N tokens fewer" comparison: a
    # price nobody paid, bought with a doubled wait. The price of what
    # THIS open actually sends still prints below, every open.
    # None, NOT [] — R-NEW 2026-08-22 flipped the default to "no issues", and
    # --resume does not re-ask. Leaving this at `[]` would have made resume the
    # one path that still silently brought the whole graph in.
    chosen: "list[str] | None" = None
    import issue_projection as IP
    # NO LIVE ISSUE, NO QUESTION — R330, 2026-08-23: *"If
    # there are no issues[], do not ask the working set question."* The
    # answer blank would give, taken silently: None is "no issues in this
    # circle at all", the ruled spelling (finding 2, 2026-08-20). Leads,
    # roots and settled issues do not count — live_nodes() is what BLOCK 2
    # projects, so an empty one means there was nothing to choose from.
    if not args.resume and IP.live_nodes():
        chosen = ask_working_set(IP)
    briefing, unknown = build_briefing(chosen)
    if unknown:
        emit("command", f"  unknown issue id(s) ignored: {', '.join(unknown)}")
    if chosen:
        focus, per, _ = IP.resolve(chosen)
        emit("circle", f"  focus {', '.join(focus) or '—'}"
              + (f" · related {', '.join(per)}" if per
                 else " · NO LIVE ISSUE-RELATIONSHIP reaches these"))
    sysblocks, notes = {}, {}
    for p in parts:
        shared, notes[p] = shared_block(p, briefing)
        sysblocks[p] = system_blocks(p, core, shared)
    # The per-part briefing note used to print here unconditionally, every
    # open — a development artifact once circling made
    # it one of the first things on screen. REVISED 2026-08-10: moved to
    # /status alongside the parts-count summary (same move, same reason).
    # THE PRICE OF WHAT IS ACTUALLY CACHED, 2026-08-20. This line was wrong
    # three ways at once and every one of them inflated it:
    #
    #   it summed len(text)//4          ~30% under per block, but
    #   it summed ALL FOUR BLOCKS        block 4 is UNCACHED — it was in a
    #                                    figure labelled "static prefix"
    #   it summed the shared prefix      blocks 1+2 are byte-identical and
    #     ONCE PER PART                  written ONCE; the other six parts
    #                                    READ them
    #
    # Measured on 2026-08-20: it printed 61,588 tokens against a real warm
    # of 38,166. Now: blocks 1+2 once, block 3 per part, block 4 never, and
    # the numbers counted rather than estimated.
    _blocks = [sysblocks[p] for p in parts]
    _shared, _measured = TC.block_tokens(client, _blocks[0][:2], MODEL,
                                         args.dry_run) if _blocks else ([], False)
    _own = 0
    for _b in _blocks:
        _c, _m = TC.block_tokens(client, _b[:3], MODEL, args.dry_run)
        _measured = _measured and _m
        _own += _c[2] if len(_c) > 2 else 0
    toks = sum(_shared) + _own
    # Three states now, not two — `chosen` is None (no issues), [] (the whole
    # graph) or a list. `if chosen else "whole graph"` read None as the whole
    # graph, which after R-NEW is the one thing it never means.
    emit("command", "\nstatic prefix, "
          + ("THIS working set" if chosen
             else "no issues" if chosen is None else "whole graph")
          + f": {'~' if not _measured else ''}{toks:,} tokens — "
          f"{sum(_shared):,} shared, written ONCE, then read by all "
          f"{len(parts)} parts"
          f"\n  (${toks * RATE_CACHE_WRITE_1H / 1e6:.2f} to warm, "
          f"${(sum(_shared) * (len(parts) - 1) + toks) * RATE_CACHE_READ / 1e6:.3f} "
          f"per round to read)"
          + ("" if _measured else "\n  ESTIMATED — no model service was asked"))

    # OPEN TOPICS, said aloud HERE since 2026-08-20 rather than at the
    # previous circle's close (the operator's finding — this file's close
    # path carries the note). They are R184's register and they project into
    # THIS circle's BLOCK 2, so this is the moment the count is a fact
    # about what is happening rather than about what has ended — and
    # /topic-list and /topic-close are both usable from here, which at a
    # close they were not in any useful sense.
    #
    # LIVE ONLY, matching where it used to print. A sandbox circle's
    # BLOCK 2 is built from the same register but nothing it does reaches
    # it, so the invitation to retire one would be misleading.
    #
    # AND DEV ONLY, 2026-08-21 (R281): the line names
    # /topic-list and /topic-close, which are DEV-table verbs now — "for
    # now, not user facing" — and a line that names a gated verb with dev
    # off would itself reveal the gate (R199).
    if args.live and CS.dev_mode:
        try:
            import topics as TOP
            n_open = len(TOP.open_topics())
        except Exception as e:                                   # noqa: BLE001
            n_open = 0
            emit("command", f"  (topics unreadable: {e})")
        if n_open:
            emit("command", f"\n  {n_open} BLOCK 2 topic(s) open (TP-) — "
                  f"they project into THIS circle. /topic-list to review, "
                  f"/topic-close to retire.")

    # Set only on the fresh-open branch. A resume never calls
    # open_transcript, so there are no opening bytes to compare against and
    # nothing the discard may touch.
    _opened: dict | None = None
    # The capture directory THIS run wrote, if any — filled in below, read
    # by discard_unspoken(). A holder rather than a bare local because the
    # closure is defined before the capture exists (R277, 2026-08-21: the
    # capture now precedes the pre-warm, so a pre-warm failure leaves one).
    _cap: dict = {"dir": None}

    def discard_unspoken() -> None:
        """Idempotent. Registered at exit AND called directly by the failure
        paths that know they are failing, so the message lands beside the
        error rather than after the cost report."""
        if not _opened or not _opened["armed"]:
            return
        _opened["armed"] = False
        if discard_empty_open(path, ot, _opened["head"], args.live):
            emit("command", f"\n  circle_{ot} discarded — nothing was ever said.")
            emit("command", "     transcript and working-set entry removed; the record "
                  "is unchanged.")
            # NO TRACE includes the capture: the Block files and whatever
            # pre-warm turns were recorded before the failure. Exactly the
            # files the manifest lists, by name — never a glob (E12).
            if _cap["dir"] is not None:
                try:
                    import prompt_capture as _PC
                    n = _PC.discard(_cap["dir"])
                    if n:
                        emit("command", f"     prompt capture removed "
                                        f"({n} file(s)).")
                except Exception as e:                       # noqa: BLE001
                    emit("command", f"     prompt capture NOT removed — {e}")

    resumed = None
    if args.resume:
        try:
            resumed = load_for_resume(path, ot, parts)
        except ValueError as e:
            emit("command", f"\n  !! {e}")
            return 2
        topic, r_transcript, r_since, r_state = resumed
        spoke = [e for e in r_transcript
                 if e["speaker"] in PART_TAGS or
                 (e["speaker"] == ID.SELF_ID and not e.get("is_topic"))]
        emit("command", f"\nRESUMING circle_{ot} — transcript verified byte-for-byte")
        emit("command", f"  topic:      {(topic or '(no topic)')[:52]}")
        emit("command", f"  statements: {len(spoke)} · last speaker: "
              f"{PART_TAGS.get(r_state['last'], '— (Self spoke last)')}")
        emit("command", "  since Self: " + " · ".join(
            f"{PART_TAGS[p]} {r_since.get(p, 0)}" for p in parts))
        emit("command", "  no opening round — this circle already had one.")
    else:
        try:
            topic = read_line_no_annotation(
                "\nCIRCLE topic (blank = open): ", "topic",
                channel="circle")
        except (EOFError, KeyboardInterrupt):
            # The working-set prompt above has caught these since it was
            # written; this one printed a traceback. Nothing has been written
            # yet, so there is nothing to close and nothing to keep — this is
            # a cancel, not the Ctrl-C of E11, which is about a circle that
            # already exists and must not be ended by a keystroke.
            emit("command", "\n  cancelled — no circle was opened.")
            return 2
        # MINT -> CHECK -> WRITE, with nothing between them that can block.
        # An input() in this sequence would rebuild the window it closes: the
        # check would describe the tree as it was before someone went to make
        # a coffee.
        ot = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        guard = WriteGuard(args.live, ot)
        path = circle_path(ot)
        # REFUSED, not warned. open_transcript truncates — write_lf is
        # write_text — and there was no check at all, so two --live opens in
        # the same clock minute meant the second one silently destroyed the
        # first one's transcript. --resume already refuses to reopen a CLOSED
        # circle; this is the same refusal for a LIVE one, which is the case
        # that loses data rather than merely confusing a reader.
        if path.exists():
            emit("command", f"\n  !! {path} already exists — refusing to overwrite it.")
            emit("command", "     Two circles opened in the same minute share an open")
            emit("command", "     time. Wait for the clock to turn over, or resume that")
            emit("command", f"     one: python coordinator\\circle.py --live --resume {ot}")
            return 2
        open_transcript(guard, path, ot, topic)
        record_working_set(ot, chosen, topic, args.live)
        emit("command", f"\ntranscript: {path}")

        # ARMED HERE, DISARMED once the opening round has run. Registered at
        # exit as well as called directly, so it covers the paths nobody
        # enumerated — an unhandled exception, a SystemExit, a Ctrl-C during
        # pre-warm. discard_empty_open compares BYTES, so it is a no-op the
        # moment anything is said; arming it wide costs nothing.
        _opened = {"head": path.read_bytes(), "armed": True}
        atexit.register(discard_unspoken)

    # THE CAPTURE PRECEDES THE PRE-WARM (R277, 2026-08-21): the pre-warm is
    # the first request that carries a part's system prompt, and every such
    # request is recorded into the capture directory, so the directory has
    # to exist first. If the pre-warm then fails, discard_unspoken() removes
    # the capture with the transcript — "a run that dies before its first
    # statement leaves no trace" still holds.
    pdir = None
    try:
        import prompt_capture
        cap_root = ROOT / "work" / "prompts"
        cap_ot = ot
        if args.resume:
            k = 1
            while (cap_root / f"{ot}_resume_{k}").exists():
                k += 1
            cap_ot = f"{ot}_resume_{k}"
        pdir = prompt_capture.write(cap_ot, sysblocks, notes, args.live,
                                    names=block_order())
        _cap["dir"] = pdir
        if pdir and args.resume:
            # Compare BLOCKS, not files. A resume capture has its own
            # directory, `<OT>_resume_<k>/`, and the manifest's per-block
            # sha256 is the thing that means "the part runs a different
            # program" — the first live resume (2026-08-02) diffed whole
            # capture files and reported every part CHANGED on a header
            # line alone.
            changed = _prompt_blocks_changed(cap_root / ot, pdir, parts)
            if changed:
                # The emitted program is the thing a part actually runs. If it
                # moved between sittings, the second half of this circle is not
                # the same experiment as the first, and that must be on the
                # record rather than inferred later from mtimes.
                emit("command", f"\n  !! the emitted prompt CHANGED since this circle opened: "
                      f"{', '.join(changed)}")
                emit("command", f"     both captures kept: prompts/{ot}/ and "
                      f"prompts/{cap_ot}/")
            else:
                emit("command", f"\n  emitted prompt identical to prompts/{ot}/ "
                      f"for all {len(parts)} part(s)")
        # briefing.md, the old --minimal extra, is GONE with the old layout:
        # Block2_circle_objectives.md IS the constructed briefing, once, as
        # its own document — what that file existed to provide.
        if pdir:
            n = sum(f.stat().st_size for f in pdir.glob("*") if f.is_file())
            emit("command", f"\nprompts captured: {pdir.relative_to(ROOT)}  "
                  f"({n / 1024:.0f} KB, {len(parts)} part(s), verified byte-for-byte; "
                  f"every request will be recorded there)")
        else:
            emit("command", "\nprompts NOT captured — dry-run")
    except Exception as e:
        # A capture failure must not cost a circle, but it must be loud and it
        # must make the run non-zero: the emitted program is the thing no other
        # record holds.
        fail(f"prompt capture FAILED: {e}")
    try:
        import prompt_capture
        prompt_capture.open_turn_log(pdir, ot)
    except Exception as e:                                   # noqa: BLE001
        fail(f"per-turn capture could not be opened: {e}")

    if not args.no_prewarm:
        emit("command", "\npre-warming caches:")
        try:
            prewarm(client, parts, sysblocks, args.dry_run)
        except Exception as e:                                   # noqa: BLE001
            # The 2026-08-09 traceback's exact site. Seven API calls, and a
            # failure in any of them used to print a stack trace over a
            # transcript that was already on disk.
            emit("command", f"\n  !! PRE-WARM FAILED — {explain_api_failure(e)}")
            discard_unspoken()
            return 2

    transcript: list[dict] = []
    if topic:
        transcript.append({"speaker": ID.SELF_ID, "display": SELF_DISPLAY,
                           "text": topic, "is_topic": True,
                           # What the header actually says. A NEW circle
                           # derives it from the topic — open_transcript
                           # writes `# Circle — {topic} — {ot}` — so here it
                           # IS the topic. parse_transcript takes the same
                           # field off the file, where the two can differ.
                           #
                           # 2026-08-08: this line read `m.group(1)`, copied
                           # from that parser, and NameError'd every circle
                           # open for a day. The probes were green: they
                           # exercise parse/render round-trip and never
                           # execute main().
                           "header": topic})
    since_self = {p: 0 for p in parts}
    state = {"last": None}
    issue_cmds: list[dict] = []
    # A SANDBOX circle's ruling carries the `sandbox_` prefix, exactly as the
    # gate's source_of() expects (R061), so an edge attested in the sandbox
    # stays greppable as one for as long as it exists.
    circle_ref = f"{'circle' if args.live else 'sandbox'}_{ot}"

    closing_confirmed = False
    abort_confirmed = False

    # RULED 2026-08-05: "Report only the presence of /help (and the stats)
    # at circle start." The whole HELP text used to print at open and again
    # on resume — ~40 lines of reference material between Self and his
    # first statement, every circle. The commands do not change during a
    # circle; the counts do.
    # REVISED 2026-08-10: the stats half of that moved to /status (below) —
    # a development artifact once circling made it the first thing on
    # screen every open, and stale the moment the room changes mid-circle
    # where the startup print never was. /status already showed per-part
    # counters and running cost; it now answers "how many parts" too,
    # live, on request, instead of once at open. The OC register this
    # was originally built for (open-concern count) is RETIRED, 2026-08-13.
    # /help's presence still prints automatically — that part of the
    # ruling stands.
    emit("command", "\n  /help for commands")

    if resumed:
        _, transcript, since_self, state = resumed
    elif args.no_blind:
        emit("command", "\nopening round — SEQUENTIAL (prior protocol, --no-blind).")
        run_round(client, parts, sysblocks, transcript, since_self, state,
                  guard, path, args.dry_run, live=args.live)
    else:
        emit("command", "\nopening round — BLIND (parallel; CIRCLE_DESIGN §1).")
        run_blind_round(client, parts, sysblocks, transcript, since_self, state,
                        guard, path, args.dry_run, live=args.live)

    # DISARMED. Past this point the circle has had its opening round, and
    # whatever the transcript holds is the record — including an empty one, if
    # every part passed. The ruling covers a run that DIES before its first
    # statement, not a circle that reached the Self prompt.
    if _opened:
        _opened["armed"] = False

    aborted = False
    while True:
        try:
            # THE PROMPT IS THE CONFIGURED NAME, CONSOLE-ONLY. Ruled
            # 2026-08-07 (support IFS_USER_NAME), narrowed 2026-08-11: this
            # text never leaves the console — the transcript always records
            # SELF_DISPLAY ("Self") regardless of what this prompt shows, so
            # personalising it here carries no PII into a part's prompt.
            cmd = read_line(f"\n{CONSOLE_NAME}> ", channel="circle").strip()
            # THE WORD "help" ALONE IS /help — the operator, 2026-08-25
            # (R347's session): "Accept the single word
            # '[Hh]elp' alone at the circle pane prompt as a synonym for
            # /help (also allow /Help)." ALONE is the whole test — "help
            # me hold this" is speech, exactly as a bare command-pane verb
            # is a word (D55(2)). Normalised at the read, so it is a
            # command before the transcript could record it as a statement.
            if cmd in ("help", "Help", "/Help"):
                cmd = "/help"
            if closing_confirmed and not (cmd == "/close" or cmd.startswith("/close ")):
                # The operator went on with the circle after the first
                # /close: the pending-confirmation state is over for the UI
                # (the next /close still proceeds at once — closing_confirmed
                # stays). seam's "state" channel; see the /close branch.
                emit("state", "")
        except KeyboardInterrupt:
            # CTRL-C DOES NOT CLOSE A CIRCLE. On the Windows console Ctrl-C is
            # also the copy keystroke, so it is the single most likely key to
            # arrive by accident — and until 2026-08-02 it was wired straight
            # to the one irreversible operation in the program. It killed
            # circle_2026-08-02_1259 after its blind round. Closing is now
            # something only a typed word can do. See LOG.md E11.
            emit("command", "\n  (Ctrl-C — the circle is still open. /close to close, "
                  "/abort to discard, /help for the rest)")
            continue
        except EOFError:
            # Not a keystroke: stdin is gone, and looping would spin forever.
            emit("command", "\n(stdin closed — closing)")
            break
        # RULED 2026-08-17 (R205): "/close" is start-anchored, not exact —
        # `/close this circle` closes same as bare `/close`, any text after
        # the verb is accepted and ignored, never parsed, never stored. The
        # space in "/close " is the token boundary: it admits "/close ..."
        # without also admitting "/closeout" or similar.
        if cmd == "/close" or cmd.startswith("/close "):
            props = unruled_proposals(transcript, issue_cmds)
            if props and not closing_confirmed:
                # Ruled 2026-08-04: surfaced at close, for Self to rule on
                # or pass. Shown ONCE — a second /close proceeds, so a
                # proposal can never block a circle from ending.
                show_unruled_proposals(props)
                closing_confirmed = True
                # THE UI IS TOLD WHICH /close THIS WAS — 2026-08-21, the lab
                # circle 2026-08-21_1139: the dual pane moved the operator to
                # cmd> on the typed "/close" and then showed him "Type /close
                # again to proceed", which cmd> refused as circle-pane speech.
                # seam's "state" channel is a UI signal (it prints nothing on
                # a terminal): "close-confirm-pending" lets cmd> forward the
                # second /close; "closing" below is the real handover, and
                # the moment cmd> input is disabled until main() returns.
                emit("state", "close-confirm-pending")
                continue
            emit("state", "closing")
            break
        if cmd == "/abort":
            # RULED 2026-08-15 (R173, NEXT.md B41): show what will and will
            # not be undone, and require the confirmation typed once more
            # — same shape as /close's own proposal confirmation above,
            # shown ONCE per circle (a second /abort proceeds, so this can
            # never trap Self in a loop). Reversible: nothing here writes
            # anything; it only decides whether to break the loop.
            if not abort_confirmed:
                emit("command", "\n  /abort will:")
                emit("command", f"    KEEP the transcript — {path.relative_to(ROOT)}")
                if issue_cmds:
                    emit("command", f"    DISCARD {len(issue_cmds)} queued /issue "
                          f"graph ruling(s) — never applied")
                else:
                    emit("command", "    (no /issue graph rulings queued to discard)")
                emit("command", "    NOT collect short_terms — any part that spoke "
                      "has no record of this circle")
                emit("command", "    NOT undo anything already written mid-circle — "
                      "a [remember: ...] or /practice-add writes immediately, by "
                      "design, and stays written")
                emit("command", "  /abort again to confirm, or say anything else to "
                      "keep going")
                abort_confirmed = True
                continue
            aborted = True
            break
        if cmd.split(" ", 1)[0] == "/help":
            arg = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            # /help IN THE ROOM, 2026-08-20 — finding 10, and
            # docs/HELP_DESIGN.md's own line: report only what the dialog
            # pane accepts, never a command-pane-only verb.
            #
            # ONE SPELLING, 2026-08-21 (R287): the
            # `?` alias is gone — it was the only way the room's help could
            # be reached from the dual pane, because the circle pane's R268
            # guard refused `/help` itself (PANE_OF says "command"); the
            # guard lets bare `/help` through now, and an alias that worked
            # where the verb did not was the inconsistency the operator named.
            #
            # ANY BARE /help REACHING HERE CAME FROM THE CIRCLE PANE.
            # circling's command pane answers `help` locally and never
            # forwards it (CircleEngine.submit_command), so this loop only
            # ever sees the room's own — or a standalone terminal's, which
            # has one pane and is a developer path. `/help all` is that
            # path's way back to the full table; the dual pane's room
            # refuses every `/help <arg>`, so it never arrives from there.
            if not arg:
                emit("circle", HS.circle_pane_help())
            elif arg == "all":
                emit("command", help_text(""))
            else:
                emit("command", help_text(arg))
            continue
        if cmd == "/status":
            # /tokens FOLDED IN HERE, 2026-08-20, and the seven identical
            # briefing lines went with it. `notes[p]` is
            # "objectives 6,850 + practices 1,561 shared; 0 to block 3" —
            # CHARACTERS, printed once per part, and identical on every row
            # because blocks 1 and 2 are byte-identical BY CONSTRUCTION.
            # Seven rows said one thing seven times, in a unit the line
            # never named, while the /tokens table two verbs away said a
            # DIFFERENT number for the same text because it was in tokens
            # and over different spans. One report, one unit, counted.
            #
            # `notes` is still built and still written into the prompt
            # capture's manifest — it is a record of what was assembled,
            # which is a different job from telling Self the size.
            emit("command", f"\n  {ROOT.name}  ({'LIVE' if args.live else 'dry-run'})"
                  f"\n  {len(parts)} parts")
            emit("command", token_table(parts, sysblocks, since_self,
                                        client, MODEL, args.dry_run))
            emit("command", f"\n  running cost ${METER.cost():.4f} over {METER.calls} calls")
            continue
        if cmd in ("/round", "/pass"):
            # RULED 2026-08-10: /pass is a new alias equalling /round —
            # both spellings name the one operation the circle pane
            # recognizes beyond speech itself (circling_and_evolving.md
            # §5, §9). Not a rename: /round keeps working unchanged.
            run_round(client, parts, sysblocks, transcript, since_self, state,
                      guard, path, args.dry_run, live=args.live)
            continue
        # NO /dev BRANCH, 2026-08-21 (R286): "dev should not
        # be parsed in circle dialog, nor recognised at self's circle prompt;
        # it is cmd> only and always hidden." The branch that sat here
        # toggled dev mode from the room — and from the dual pane's circle
        # pane, which let `/dev` through because it is no PANE_OF key. The
        # toggle is the command pane's own unlisted `dev`; the standalone
        # terminal opens with --dev. A `/dev` typed here now falls through
        # to UNKNOWN COMMAND like any other slash word, and is never spoken.
        if (not CS.dev_mode and cmd.startswith("/")
                and CS.normalise_head(cmd.split(" ", 1)[0])
                not in CS.USER_SUBSET_COMMANDS):
            # R266, 2026-08-20: DEV MODE ADDS, IT NEVER TAKES AWAY. This
            # refused EVERY remaining "/" verb with dev off, which made the
            # user's own issue commands, practices, topics and recall
            # reachable only by knowing /dev exists — the opposite of the
            # ruling. It now refuses what is NOT in the user table, which
            # today is exactly DEV_SUBSET_COMMANDS plus a typo.
            #
            # AND IT IS ANSWERED, NEVER BARELY REFUSED, 2026-08-21 (R285): a
            # dev-table verb with dev off is JUNK, and JUNK gets an answer.
            # R335, 2026-08-24, REVERSED WHAT THAT ANSWER LOOKS LIKE while
            # keeping the substance: the error line, then "See help" — never
            # the listing, which in a pane is longer than the pane and rolls
            # the one line naming the mistake out of sight. Both lines come
            # from help_system.junk_help().
            #
            # Circle-pane input (plain speech, /round, /pass) never reaches
            # here — all three are handled above and `continue` first, the
            # same split circling_and_evolving.md §5 already draws between
            # the two panes.
            emit("command", junk_help(cmd))
            continue
        # /issue-evidence-list — named /statements until 2026-08-21 (D59).
        # Exact, like the verbs beside it: the loop owns it because it
        # reads the live transcript, which no dispatcher has.
        if cmd == "/issue-evidence-list":
            show_statements(transcript)
            continue
        # THE SLASH IS REQUIRED HERE, and this line is why — 2026-08-20.
        # `head` was the RAW first token until normalise_head() arrived with
        # finding 14 the same day, and normalise_head SUPPLIES A MISSING
        # SLASH (R201's rule, correct at "cmd> " where every line is a
        # command). Applied here it made `practice-list` typed as SPEECH
        # match `/practice-list` and RUN — in the one prompt where an
        # unmarked line is a statement to the room, not a verb. This file's
        # own refusal below has always said so: "to say this to the parts,
        # retype it without the leading slash".
        #
        # R268's neighbour, in the coordinator rather than the pane: a
        # standalone command in circle dialog is not a command.
        head = (CS.normalise_head(cmd.split(" ", 1)[0])
                if cmd.startswith("/") else "")
        # ONE DISPATCHER — B61, 2026-08-21 (the operator: "tidy now"). Ten verbs
        # used to be branched here by hand, each a copy of the branch
        # commands.dispatch_dev_cmd() already had for it, and nothing
        # asserted the two agreed; /recall shipped in one and not the other
        # (its history is on the dispatcher's docstring). Every verb that
        # does not need THIS circle — the registers, the listings, the
        # prompt dump, a NODE's own status — goes through the same
        # dispatcher the command pane and --dev-cmd use, so there is
        # exactly one place a verb is wired. What stays in this loop is
        # what genuinely needs the open circle: /help (the ROOM's form),
        # /status, /issue-evidence-list, the IC.HEADS ruling forms (they attest
        # against the transcript), /close, /abort, /round, /pass, /dev.
        # coordinator/tests/test_dispatch_partition.py asserts that partition.
        #
        # The two things the loop alone can supply ride as keywords:
        # `record`, the RECORDED-NOT-SENT transcript step the three write
        # verbs fire on success (R079's rule — the room never hears that
        # it gained a practice).
        def _record_practice_cmd() -> None:
            transcript.append({"speaker": ID.SELF_ID, "display": SELF_DISPLAY,
                               "text": cmd, "cmd": True})
            append(guard, path, f"[{SELF_DISPLAY}]: {cmd}")
        if head and dispatch_dev_cmd(
                head, cmd.split(" ", 1)[1] if " " in cmd else "",
                record=_record_practice_cmd,
                guard=guard):
            continue
        if head in IC.HEADS:
            c, why = IC.parse(cmd, circle_ref)
            if c is None:
                emit("command", f"  {why}")
                continue
            if c["verb"] == "issue-evidence-add":
                # IC.parse() stays pure — it only knows the statement
                # NUMBER. Resolving it against the live transcript (same
                # numbering /issue-evidence-list shows) belongs here, the same way
                # IC.precheck() below needs the live graph passed in.
                stmt_e, why3 = resolve_statement(transcript, c["stmt"])
                if stmt_e is None:
                    emit("command", f"  {why3}")
                    continue
                c["part"] = stmt_e["speaker"]
                c["quote"] = stmt_e["text"]
                c["source"] = circle_ref
            if why2 := IC.precheck(c, VT.graph_now()):
                emit("command", f"  {why2}")
                continue
            c["index"] = len(transcript)
            issue_cmds.append(c)
            # ECHOED TO THE RECORD, WITHHELD FROM THE ROOM (ruled 2026-08-04).
            # `append` writes the transcript file; the `cmd` flag keeps
            # render_messages from ever showing it to a part. Both halves are
            # needed: the file is what the gate will verify the edge against.
            transcript.append({"speaker": ID.SELF_ID, "display": SELF_DISPLAY,
                               "text": cmd, "cmd": True})
            append(guard, path, f"[{SELF_DISPLAY}]: {cmd}")
            emit("command", f"  recorded — {IC.describe(c)}"
                  f"   ({len(issue_cmds)} pending, applied at close)")
            continue
        # UNKNOWN SLASH-COMMANDS ARE REFUSED, NOT SPOKEN.
        # On 2026-08-01 Self typed `/mark ...` before /mark existed. It fell
        # through to the branch below, went into the transcript as a Self
        # statement, and every part read it — one part called the mark
        # "the ember-tending act", the Child said "I'm glad you marked it."
        # An unimplemented command is not inert; it becomes content, and it
        # contaminated the one measurement marks exist to protect. See
        # work/instrument/LOG.md E06.
        if cmd.startswith("/"):
            head = CS.normalise_head(cmd.split(" ", 1)[0])
            emit("command", f"  UNKNOWN COMMAND {head} — not sent to the room. "
                  f"Known: {', '.join(KNOWN_CMDS)}")
            emit("command", f"  (to say this to the parts, retype it without the "
                  f"leading slash)")
            continue
        if not cmd:
            continue
        raw = cmd
        cmd, self_remembered = apply_self_remember(guard, SELF_DISPLAY, cmd)
        if self_remembered:
            emit("command", "  (remember recorded to self/remember.toml — "
                  "stripped, private)")
        if cmd:
            cmd = strip_malformed_markers(cmd, SELF_DISPLAY)
        if not cmd:
            # STILL A PASS — no since_self reset, no state["last"], no round
            # run; Self said nothing the room can hear. RULED 2026-08-18, the
            # same as a part's remember-only turn in rounds.py, and the RECORD
            # keeps the bracket the same way: one withheld entry, one file
            # line, `remember_only` re-derived on resume. See that comment,
            # and transcript_store.withheld().
            #
            # A whole line that was only a MALFORMED non-remember marker still
            # writes nothing at all — there is no record to complete, which is
            # what `REMEMBER_RE.search(raw)` distinguishes.
            record = strip_malformed_markers(raw.strip(), SELF_DISPLAY,
                                             quiet=True)
            if record and REMEMBER_RE.search(raw):
                transcript.append({"speaker": ID.SELF_ID,
                                   "display": SELF_DISPLAY, "text": "",
                                   "raw": record, "remember_only": True})
                append(guard, path, f"[{SELF_DISPLAY}]: {record}")
            continue
        # THE ROOM AND THE RECORD PART COMPANY HERE, exactly as they do for
        # a part in rounds.py — see that comment for the whole of it. Self's
        # own remember is no more the room's business than a part's: `cmd`
        # (stripped) is what the transcript entry, every rebuilt prompt and
        # route_markers() get; `record` (bracket intact) is what the
        # transcript FILE gets. Ruled 2026-08-14, built 2026-08-18.
        record = cmd
        if REMEMBER_RE.search(raw):
            record = strip_malformed_markers(raw.strip(), SELF_DISPLAY,
                                             quiet=True)
        # QUOTE-AS-MARK — R155, routed to an unvetted REMEMBER 2026-08-19
        # (R251). BEFORE the append, and that ordering is
        # the mechanism, not a preference: `transcript` must hold only
        # PRIOR statements for "a prior statement in this circle" to
        # mean anything, and the `/issue-evidence-list` numbers it records stay
        # valid because the list only ever grows. Reads `cmd` — the
        # ROOM's text — so an already-stripped bracket can never be
        # mistaken for quoted material.
        QM.apply_quote_as_mark(guard, transcript, cmd)
        entry = {"speaker": ID.SELF_ID, "display": SELF_DISPLAY, "text": cmd}
        if record != cmd:
            entry["raw"] = record
        transcript.append(entry)
        append(guard, path, f"[{SELF_DISPLAY}]: {record}")
        route_markers(SELF_DISPLAY, cmd, live=args.live)
        since_self = {p: 0 for p in parts}     # Self spoke — reset, per process_core
        state["last"] = None
        run_round(client, parts, sysblocks, transcript, since_self, state,
                  guard, path, args.dry_run, live=args.live)

    # ---- the circle's graph rulings -------------------------------------
    # Written for EVERY circle, sandbox or live, beside its transcript. A
    # sandbox circle stops here: the record is a proposal to the live tree
    # that has not touched it, and `python memory/issue_commands.py
    # <that file>` is how it gets there once Self has read it.
    if issue_cmds and not aborted:
        cdir = (ROOT / "circles") if args.live else (SANDBOX / "circles")
        crec = cdir / f"commands_{ot}.toml"
        crec.write_text(IC.dump(issue_cmds, circle_ref), encoding="utf-8",
                        newline="\n")
        # COMMAND CHANNEL, 2026-08-21 — the operator, reading his close:
        # *"Proper output is in the wrong pane (circle), put it in command."*
        # This report is Coordinator->Self about the record, never room
        # dialog; it printed on the circle channel since the day the
        # channels were classified.
        emit("command", f"\n  {len(issue_cmds)} graph ruling(s): "
              f"{crec.relative_to(ROOT)}")
        for c in issue_cmds:
            emit("command", f"    {IC.describe(c)}")
        if args.live:                     # ruled 2026-08-04: automatic
            ok, msg = IC.apply(issue_cmds)
            emit("command", f"  {msg}")
            if not ok:
                emit("command", "  the transcript and the record are intact; fix and "
                      "re-run issue_commands.py on the record")
        else:
            emit("command", "  SANDBOX — not applied. Review, then: "
                  f"python memory/issue_commands.py "
                  f"{crec.relative_to(ROOT)}")
    elif issue_cmds:
        emit("command", f"\n  {len(issue_cmds)} graph ruling(s) DISCARDED — circle "
              f"aborted")

    if aborted:
        emit("circle", f"\naborted. transcript kept: {path}")
        if args.live and any(e["speaker"] in PART_TAGS for e in transcript):
            emit("command", "  NOTE: no short_terms were collected. Parts that spoke have no")
            emit("command", "  record of this circle. The nightly transcript safety net will")
            emit("command", "  backfill them from the transcript before dreaming.")
        emit("command", METER.report())
        return report_failures()

    # THE SEPARATE PRACTICE STAGING CALL IS GONE, 2026-08-20 (B60). A
    # practice is proposed as `[proposed: /practice-add ...]` and a better
    # option as `[proposed: /better-option-add ...]`, so both are staged by
    # the ONE call below and RUN at approval. Its malformed report went with
    # it: a malformed annotation is now reported at the moment it is spoken,
    # by strip_malformed_markers(), which is where R231 asked for it and is
    # strictly earlier than /close.
    #
    # R202, 2026-08-16: ONE staging call replaces the separate request/
    # relation ones — `[proposed: <command>]` covers every future now
    # (spelled `[propose <text>]` until R273).
    # ADDITIVE, ALONGSIDE the existing show_unruled_proposals()/`/issue
    # issue-relationship-add` path below (unchanged) for an
    # issue-relationship-add attempt specifically — #32, Self's
    # explicit scope. issue_cmds is complete by this point (the Self>
    # loop has ended), so this can safely dedupe against every /issue
    # issue-relationship-add Self already typed this circle.
    staged_propose_ids = stage_propose_proposals(ot, transcript, issue_cmds,
                                                  args.live)
    if staged_propose_ids:
        # COMMAND, not circle: this is Coordinator reporting an operation
        # to Self, which docs/BNF.md line 105 keeps out of the circle
        # entirely. Corrected with R221 lane work (NEXT.md B51 records
        # that this one fix needed no ruling of its own).
        emit("command", f"\n  {len(staged_propose_ids)} proposal(s) staged: "
              f"{', '.join(staged_propose_ids)}")
    # CHECKPOINT 1 — immediately after the write. Shows EVERY currently
    # pending row, across every propose-class kind, not only this
    # circle's additions: a skip from an earlier close reappears here
    # too, same as it will at the next priming (docs/BNF.md
    # PRACTICE LIFECYCLE, Vetting).
    # NEXT.md D14, 2026-08-17: no longer `if args.live:` around the vetting
    # call — vet_pending_proposals() itself now handles sandbox (describe +
    # validate, never rule). The topics report below stays live-only; it is
    # unrelated to vetting and out of this ruling's scope.
    # the coalesce refresh, same guard and same reasons as the open
    # checkpoint's (R356/E22) — the close is where a circle's own
    # [proposed: ...] rows have just been staged, so this is the pass
    # the operator's "once, at circle end" ruling names (R356).
    if args.live:
        try:
            import coalesce as CG
            CG.refresh_if_stale(say=lambda m: emit("command", m))
        except Exception as e:
            emit("command", f"  coalesce: skipped ({e})")
    confirmed_this_close = vet_pending_proposals("at close", args.live,
                                                ruled=issue_cmds)
    # THE OPEN-TOPICS NOTICE MOVED TO THE NEXT CIRCLE'S OPEN, 2026-08-20,
    # on the operator's finding: "This output suggests that /topic-* commands are
    # available during close. It works, but if the lifecycle is ending,
    # present this only at next circle start."
    #
    # It is not a smaller claim, it is a truer one. The notice says the
    # topics "project into the next circle" — which is a fact about an
    # open, not about a close — and it invited two commands at the one
    # moment the circle is being taken down. Printed at OPEN it names what
    # the room is ABOUT to carry, and the commands it names are usable
    # then. See the open banner, beside the working-set price line.

    # THE PICTURE OF THE GRAPH, R365, 2026-08-27. HERE and not later: every
    # ruling this circle made is applied by now — the batch above, and
    # whatever the vetting checkpoint just accepted — and nothing below
    # touches issues/ (phase 2 writes parts/ and self/). Here and not
    # earlier for the same reason: a ruling accepted at the checkpoint
    # would have missed an earlier draw.
    #
    # NOT ON THE /abort PATH, deliberately. An abort returns above this
    # line with its cmd>-typed rulings already applied, so the picture is
    # left stale — and the next live close redraws it, because what is
    # tested is the FILES against the picture, not this circle against
    # itself. See issue_draw.is_stale().
    if args.live:
        redraw_issue_graph()

    # THE START-OF-CLOSE MARKER, 2026-08-23. Written HERE and not at the
    # `/close` verb: everything above this line can still return without
    # collecting anything (/abort), and a marker for a close that
    # never began would make the next open report a circle that is fine. This
    # is the last statement before the first short_term could be written, which
    # is exactly the window _interrupted_closes() could not see into.
    if args.live:
        mark_close_started(ot)
    emit("command", "\ncollecting short_terms:")
    try:
        written = collect_short_terms(client, parts, sysblocks, transcript, ot,
                                      guard, args.dry_run)
    except KeyboardInterrupt:
        # The second Ctrl-C on 2026-08-02 landed here and left a traceback, no
        # short_terms and no close report. The transcript was never at risk —
        # it is written statement by statement — so say so, and say how to get
        # back in, rather than printing a stack trace at someone mid-circle.
        fail("close INTERRUPTED — short_terms incomplete")
        emit("command", "\n  !! close interrupted. THE TRANSCRIPT IS INTACT — every")
        emit("command", "     statement was written as it was made; nothing is lost.")
        emit("command", f"     resume:   python coordinator\\circle.py --live --resume {ot}")
        emit("command", "     or leave it: the nightly's transcript safety net backfills")
        emit("command", "     every part that spoke but has no short_term.")
        emit("command", METER.report())
        return report_failures()
    if args.live:
        run_verifier(ot)
        commit_circle(ot, written)
        # PHASE 2 — dreaming then synthesis, synchronous, AFTER the circle's
        # own commit (R167: a phase-2 failure leaves the circle safely
        # committed; R168: failures write a report, get one diagnostic
        # call, and hand back — no automated catch-up). LIVE ONLY:
        # SYNTHESIS writes self/, which no sandbox may touch.
        emit("command", "\nphase 2 — dreaming and synthesis "
              "(coordinator/inter_circle.py):")
        import inter_circle as ICP
        if ICP.process_circle(ot, live=True, confirmed=confirmed_this_close,
                              say=lambda s: emit("command", s)):
            fail("phase 2 (dreaming/synthesis) did not complete — the "
                 "circle itself is committed; see work/logs/"
                 f"dream_error_{ot}.json and re-run by hand")
    else:
        emit("command", "  (sandbox mode: verifier not run — it reads the live tree)")
        commit_sandbox(ot)
        emit("command", "  (sandbox mode: no dreaming/synthesis — phase 2 "
              "writes self/, live circles only)")
    emit("command", METER.report())
    emit("circle", f"\nclosed. transcript: {path}")
    return report_failures()


def report_failures() -> int:
    """Exit 0 only when the circle produced a complete record. Anything in the
    ledger — a truncated statement, an unwritten short_term, a non-zero verifier —
    is a data problem that must be visible to whatever ran this script."""
    if not FAILURES:
        return 0
    emit("command", f"\n{'=' * 68}")
    emit("command", f"  {len(FAILURES)} DATA FAILURE(S) THIS CIRCLE — record is incomplete:")
    for f in FAILURES:
        emit("command", f"    - {f}")
    emit("command", "  Resolve before the next circle opens. See CLAUDE.md")
    # THE REPAIR NAMED IS THE REPAIR FOR WHAT FAILED, 2026-08-21. This banner
    # named `circle_audit.py --backfill --commit` — the SHORT_TERM repair —
    # under a phase 2 (dreaming/synthesis) failure too, which that command
    # does not touch; the operator read it at the close of 2026-08-21_1139.
    # A phase-2 entry names its own dream_error_<OT>.json, and the re-run
    # line is inter_circle's. Both may print when both kinds failed.
    import re as _re
    phase2 = [f for f in FAILURES if "phase 2" in f]
    other = [f for f in FAILURES if "phase 2" not in f]
    if other:
        emit("command", "  'Circle closing' and process.md 'short_term backfill';")
        emit("command", "  the repair is: circle_audit.py --backfill --commit")
    for f in phase2:
        m = _re.search(r"dream_error_(\S+?)\.json", f)
        ot_ = m.group(1) if m else "<OT>"
        emit("command", f"  the repair is: python coordinator/inter_circle.py "
                        f"--ot {ot_} --live  (nothing was written by the "
                        f"failed run; see the report it names)")
    emit("command", f"{'=' * 68}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
