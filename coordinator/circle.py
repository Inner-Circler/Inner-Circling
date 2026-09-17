#!/usr/bin/env python3
"""
IFS inner circle — local coordinator (direct Messages API).

WHAT THIS IS
    THE DRIVER, NOT THE PROGRAM. A local Python "Coordinator" drives the parts as
    direct, stateless Messages API calls; a part's statement is the HTTP return
    value. There is no agent-teams runtime, no SendMessage, no teammate file
    writes, no sandbox mount in the write path. Almost everything this file once
    held now lives in its own module and is called from here — the turn engine
    (circle_rounds.py), the annotation grammar (annotations.py), the four-block assembly
    (prompt_build.py), the transport (llm_client.py).

    THE AGENT-TEAMS PATH IS GONE, not parallel. This paragraph said that
    mechanism was "UNTOUCHED and fully operational" until 2026-08-27 — a month
    after it was retired (2026-07-26), and nine days after `scripts/`, one of
    the four paths it named, was deleted outright. There is one path.

TWO MODES, AND ONE IS REQUIRED
    --live      Permits writing:
                  circles/circle_<OT>.md
                  parts/<name>/short_term_<OT>.toml (that name only; .md
                                                    for a resumed pre-B96 close)
                  work/logs/                        (via circle_close_verify.py)
                Nothing else, ever. Enforced by assert_write_safe().
    --dry-run   The test rig: no network, no API key needed, every part passes.
                Writes only under work/sandbox/.

    A BARE INVOCATION REFUSES (R360, 2026-08-27, exit 2). The old bare default
    — real model calls with the writes sent to work/sandbox/ — was the practice
    mode R250 deprecated, and practice lives in the lab checkout now. This
    section described that default as the live behaviour until the day it went.

INTEROP
    Transcript lines use the canonical "[Tag]:" / "[Tag] [To: X]:" form that
    coordinator/circle_close_verify.py::parts_that_spoke() parses. short_term files carry
    the four canonical sections. At close in --live mode this script shells out
    to coordinator/circle_close_verify.py --short-term-only --write-report, so the durable
    close report work/logs/close_<OT>.json is produced by the SAME verifier as
    always.

    NOTHING RE-VERIFIES THAT REPORT AUTOMATICALLY, and this said "the nightly
    --reconcile guard keeps working unchanged". There has been no nightly since
    2026-07-28. circle_audit.py phase 2 runs --reconcile — when a human runs it.

RUN
    pip install -r requirements.txt      NOT a package list. tomli_w is the FIRST
                                         third-party import this file reaches
                                         (issue_commands -> issue_schema), ahead of
                                         anthropic and dotenv, so any install short of
                                         the file fails here rather than at the API call.
    set ANTHROPIC_API_KEY=...            (or put it in the project .env)
    python coordinator/circle.py --live
    python coordinator/circle.py --dry-run
    python coordinator/circle.py --dry-run --parts <part1>,<part2>
"""

from __future__ import annotations

import argparse
import datetime
# `os` went with the client construction at stage 2 (R382) — its only readers
# here were the ANTHROPIC_API_KEY check and the .env fallback, both of which
# are the provider's business now.
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
import part_roster as R                 # B29: the one roster every reader shares
from record_paths import (ROOT, PART_TAGS, SANDBOX_CIRCLES, record_dir,       # phase-1 step 0:
                          record_rel)   # one home for path constants (2026-08-16)
import record_paths as _RP
SANDBOX = _RP.SANDBOX              # a probe seam: test_quote_as_lands reads circle.SANDBOX
import seam                        # the I/O seams + failure record
import setting_manager as SET             # self/settings.toml — the override register
import phase_clock as PC           # wall-clock per phase + the close heartbeat
                                   # (phase-1 step 1, 2026-08-16)
from seam import FAILURES, fail    # aliases to the SAME list object and
                                   # the same never-rebound function
from write_guard import WriteGuard  # phase-1 step 2
import command_surface as CS       # phase-2 stage 0 (2026-08-16): the
                                   # command-pane constants + dev_mode.
                                   # dev_mode is REBOUND — always
                                   # CS.dev_mode, never a from-import.
from command_surface import KNOWN_CMDS
from llm_client import (METER, KEY_MISSING_HELP, KEY_MISSING_BRIEF,
                        stream_client_build, stream_key_present_read)
import llm_client as LC            # LC.MODEL, read at use: a setting-owned constant is never
                                   # from-imported (a copy the settings refresh cannot reach)
# THE OTHER FOUR LEFT WITH THE OPEN STEP, 2026-09-09: stream_key_source_note,
# stream_failure_explain, RATE_CACHE_WRITE_1H and RATE_CACHE_READ are the API check's and
# the pre-warm's, and both of those are circle_open.py's now.
# SHORT_TERM_SECTIONS left this import 2026-09-02: the only reader here was
# _short_term_call's missing-headings test, which is the disassembler's now.
import annotations as MK           # phase-2 stage 3: the annotation system
import quote_as_lands as QM        # R155's channel: Self quoting a part
                                   # IS a ratification. NOT in annotations —
                                   # that module is the BRACKET grammar
                                   # and this mechanism has no bracket.
from annotations import (remember_self_apply, REMEMBER_RE,
                     annotation_malformed_strip, annotation_route)
from propose_lifecycle import (proposal_unruled_list,      # stage 8, 2026-09-03:
                               proposal_unruled_show,  # the PROPOSE LIFECYCLE
                               proposal_stage)  # left annotations.py
# The test-surface re-exports this file carried (remember_apply, extract_
# annotations, statement_line, three help_system names, and last the four
# propose names) are all gone since 2026-09-03: every suite calls the owner.
import help_system as HS           # phase-2 stage 5 (built 4th)
from help_system import command_help_render, junk_help
import proposal_vetting as VT      # phase-2 stage 4 (built 6th)
from proposal_vetting import proposal_vet
from circle_rounds import (circle_round_run,  # phase-2 stage 7:
                    part_token_table)                   # the turn engine
# (graph_now/_propose_approve/_propose_command_shape are deliberately
# NOT re-exported: the tests patch and call them on their owners —
# vetting and annotations — per the late-binding contract.)
from commands import (command_dev_dispatch,                   # phase-2
                      command_args_quote, QUOTED_ARG_COMMANDS,  # 2026-09-15
                      statement_resolve,                   # stage 6
                      statement_show)                     # (built 5th)
# The cmd_* implementations are NO LONGER imported here — B61,
# 2026-08-21: the Self> loop delegates every non-circle-dependent verb
# to command_dev_dispatch() and branches nothing it also handles. See the
# loop, and coordinator/tests/test_dispatch_partition.py.
from transcript_store import (  # phase-1 step 3 — the
    circle_transcript_append,                             # transcript's persistence
    circle_sandbox_commit, circle_commit,                 # and parsing layer; these
    circle_close_verifier_run,                            # are the names this file
)                                                         # still calls itself
# circle_transcript_open / _discard_empty / _resume_read left with the OPEN STEP, 2026-09-09 —
# opening, withdrawing and resuming a transcript are all circle_open.py's now.
import transcript_store as TS
import circle_close as CC
import circle_open as CO   # the open step (2026-09-09)          # stage 12, 2026-09-03: the close step

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
    # because that channel is private (docs/BNF.md line 105); the three
    # circle-channel reads in this file each ask for it by name.
    #
    # `prefill` (2026-08-20, finding 2) asks the reader to open with that
    # text already typed and the cursor at its end. An AFFORDANCE, not a
    # contract — see seam.read_line: a plain terminal ignores it, so every
    # caller must also say the same thing in words.
    # prefill BY KEYWORD, deliberately: a rebound read_line only has to
    # accept the two positional arguments it always did, plus `**_`.
    # Passing it positionally would break every stub in the suites at
    # once, for an argument most of them have no opinion about.
    # timed_read: every second at a prompt lands under the one
    # waiting_on_self span, so no phase ever carries human time (2026-08-30).
    return PC.stream_timed_read(seam.read_line, prompt, channel, prefill=prefill)


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

    REJECT THE WHOLE LINE, NEVER STRIP IT. annotation_malformed_strip() is
    the other shape and is the right one for speech: remove the broken
    span, keep the statement. A topic is not a statement, so there is no
    remainder worth keeping - stripping would open the circle under a
    topic the typist never wrote, which is worse than asking again. The
    ruling says "say so and return to the prompt": a loop, not a repair.

    WHY THE TOPIC NEEDED THIS AT ALL. It is appended to the transcript
    with `is_topic`, and prompt_build.prompt_messages_render() skips only `cmd`
    entries - so a topic renders to EVERY part as a user turn. A
    `[remember: ...]` typed there was neither captured (no
    apply_self_remember on that path) nor stripped (no
    strip_malformed_annotations either), and reached all seven parts
    verbatim: the exact opposite of the private note it asks for, and
    E06's contamination through a door nothing was watching.

    Warnings go to the COMMAND channel, following the two complaints that
    already exist about these prompts' input - the working set's own
    unknown-node notice, and annotation_malformed_strip()'s - rather than
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
        found = MK.annotation_find(raw)
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
        #
        # SELF_KEYWORDS, NOT ASK_KEYWORDS, since 2026-08-30: `recall` joined
        # the taught set on 2026-08-29 and this line began promising the
        # operator that `[recall: ...]` was valid at the circle prompt. It
        # never was by design and is refused there now, so the hint names
        # what SELF may type. Still derived, never a literal — a keyword
        # added to ASK_KEYWORDS reaches this line by itself unless
        # PART_ONLY_KEYWORDS withholds it.
        forms = " and ".join(f"[{k}: ...]" for k in MK.SELF_KEYWORDS)
        emit("command", f"     {forms} are valid only "
             f"at the {CONSOLE_NAME}> prompt, in an open circle.")
        emit("command", f"     Nothing was recorded. Type the {where} again.")


# THE WORKING SET QUESTION — WORKING_SET_PROMPT and working_set_ask(), with the R330/R344
# history above them — MOVED to working_set_manager.py, 2026-09-03 (cohesion re-homing
# stage 10). main() calls WS.working_set_ask(IP, read_line=read_line_no_annotation): the
# reader is a parameter, so R225's annotation refusal at this prompt stays this file's.

# ------------------------------------------------------------------ paths
# ROOT and SANDBOX (and PART_TAGS, further down) moved to record_paths.py,
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
#   CONSOLE_NAME   ID.user_name_read(), from $IFS_USER_NAME in .env. Shown only
#                  at the console prompt and in /help — never written to a
#                  transcript, never sent to a model.
#
# THIS IS A DISPLAY NAME ONLY. Every comparison uses ID.SELF_ID.
SELF_DISPLAY = ID.DISPLAY
CONSOLE_NAME = ID.user_name_read()


def circle_prompt_read() -> str:
    """The Self> prompt's text, with the BOUND GROUP — R563 (2026-09-12): "add the bound group in
    /status and prompt line". Every self/ register a cmd> verb writes is the bound group's, so the
    prompt says which: `Self (ifs)> `. Read at every prompt, not once, because the window and the
    Ticker run more than one circle in a process and the group can change at an open. ui/circling.py's
    _circle_prompt() reads THIS, so the two prompts cannot disagree. Console-only, as CONSOLE_NAME
    is: never written to a transcript, never sent to a model."""
    return f"{CONSOLE_NAME} ({_RP.group_read()})> "

# MODEL MOVED to llm_client.py, 2026-08-16 (phase 2 stage 1), with
# CACHE_TTL, the RATE_* table and SHORT_TERM_SECTIONS — the transport
# owns its model id and rates; the names this file still uses are
# imported at the top.
# MAX_SINCE_SELF stopped being imported here 2026-08-20: /status's own
# since-Self loop moved INTO part_token_table (the round column), so this
# file no longer names the ceiling anywhere.
# MAX_TOKENS, MAX_SINCE_SELF and (below) TRUNCATION_MARKER MOVED to
# rounds.py, 2026-08-16 (phase 2 stage 7) — ceiling, per-Self cap and
# the truncation contract are round semantics; comments included.

# PART_TAGS (parts/<dir> -> transcript tag, B29) moved to record_paths.py with
# its comment, 2026-08-16 — imported at the top of this file.

# The default roster IS THE DEFAULT GROUP'S MEMBERS — the `ifs` row of the groups register —
# B117 stage 1 (R466/R467, 2026-09-07): never the parts/ scan again, so a directory added under
# parts/ cannot widen the plain live open (MAX_MEMBERS is 9). The scan is the fallback only
# where no `ifs` row exists (a fresh bundle's empty delegate).


def _default_parts_read() -> list[str]:
    import group_manager as _GA
    members = _GA.group_resolve(_GA.DEFAULT_GROUP)
    return list(members) if members else list(R.DIR_NAMES)


DEFAULT_PARTS = _default_parts_read()


def _roster_refresh() -> None:
    """THE ROSTER IS READ AT EVERY OPEN, not once per process — R548 (D127,
    2026-09-11): "the part must be included next circle". circling.py and the Ticker run main()
    more than once in one process, and DEFAULT_PARTS, PART_TAGS and the statement grammars were
    the ones read at import, so a part /part-add wrote between two circles was missing from the
    second. group_set() on the bound group runs every follower, the roster's own rescan among
    them. Called first thing in main(); a circle already open is untouched.

    ONLY WHEN THE ROSTER MOVED. group_set() also re-binds every register's path, and a probe
    that points registers at scratch files before running main() — ui/tests/circle_test.py —
    must keep them, or its writes land in the real record. So parts/ is scanned, and the group
    re-bound only when what the scan finds differs from the tables this process holds.
    DEFAULT_PARTS, a read of group.toml with no side effect, is read every time."""
    global DEFAULT_PARTS
    roster, alt, tails, _probs = R.part_scan()
    if (roster, alt, tails) != (R.ROSTER, R.ALT_TAGS, R.IDENTITY_TAILS):
        _RP.group_set(_RP.group_read())
    DEFAULT_PARTS = _default_parts_read()


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


# ------------------------------------------------------------------ failure record
# MOVED to seam.py, 2026-08-16 (phase 1 step 1), so extracted modules
# can report a data failure without importing this file. FAILURES and
# fail are imported at the top — the same list object and the same
# function; circle_failures_report() below still reads the one record.

# TRUNCATION_MARKER MOVED to rounds.py with part_statement_ask (stage 7).


# ------------------------------------------------------------------ write guard
# MOVED to write_guard.py, 2026-08-16 (phase 1 step 2) — WriteGuard and
# _within, verbatim, comments included; imported at the top of this
# file. The class raises rather than emits, which is what made it the
# safest first extraction.


# --------------------------------------------- prompt construction
# MOVED to prompt_build.py, 2026-08-16 (phase 2 stage 2): the
# identity read-layer (read_ro/strip_settled/strip_to_identity),
# circle_objectives construction (circle_briefing_build + ISSUE_MODEL),
# the four-block assembly (ORDER/block_order/system_blocks/
# group_shared_read) and the transcript-to-messages view (prompt_messages_render)
# - verbatim, comments included. shared_block()+system_blocks()'s
# two-step dance was RETIRED 2026-09-02 in favour of one call,
# prompt_part_assemble() (prompt_build.py) — see role_context.py/
# role_attention.py's own module docstrings. The names this file
# still calls are imported at the top.

# --------------------------------------------- the turn engine
# MOVED to rounds.py, 2026-08-16 (phase 2 stage 7, the last
# extraction): _TO_RE/_SELFNAME_RE + part_statement_ask, the blind round
# (BLIND_CLOSE/circle_blind_round_run), part_token_table,
# part_addressed_since and circle_round_run — verbatim, comments included.
# main() imports circle_round_run/circle_blind_round_run/part_token_table at the top.


# ------------------------------------------------------------------ close
# THE CLOSE AIM AND THE HEARTBEAT — ruled 2026-08-30, the operator: "After
# circle /close, I want to aim for no more than 5 minutes, and progress must
# be being reported in the command pane at least every 10 seconds, even if
# its just a spinner." The aim is REPORTED, never enforced: a slow close must
# not fail a close that otherwise held (the spend report's own rule).
CLOSE_AIM_SECONDS = SET.setting_value_read("close_aim_seconds", 300)
# PAST THE AIM IS REPORTED; PAST THIS IS THE ALARM (R540). Between the
# two is the range the operator called "not unusual".
CLOSE_ALARM_SECONDS = SET.setting_value_read("close_alarm_seconds", 600)
# close_heartbeat_seconds is READ BY inter_circle.py NOW, not here — the close
# shares the one beat armed at open, and a constant nothing reads is a claim
# that something still does.
# THE GENERAL RULE'S CADENCE — the operator, 2026-09-09: *"If there is ever a
# measured delay of over 3 seconds between user input and any output -- or
# between any output and another output (rather than waiting on user input) --
# and there is a clock to watch this, then a progress indication, e.g. a
# concatenated "." is to be added (every 3 seconds)."*
#
# ITS OWN SETTING, NOT close_heartbeat_seconds. That one is the CLOSE's
# cadence and its default is 10; folding the two would change the close's
# rhythm as a side effect of a rule about the whole run, and a setting is
# supposed to be the one place a value is chosen.
PROGRESS_SECONDS = SET.setting_value_read("progress_seconds", 3)


def system_progress_arm() -> None:
    """Start this run's progress beat. Safe to call more than once.

    STOP FIRST, so this run's beat is its own. main() runs more than once in a
    UI process, and every early return between the arming and the close — an
    /abort above all — leaves one going; a second arming returns False and the
    new run would inherit the old one's notify. Stopping first bounds that to
    "between runs" rather than "forever", and costs nothing when none runs.

    ONE BEAT FOR THE RUN. The close used to arm a second at its own cadence;
    a second arming silently discarded it, so the close keeps its stopwatch
    (close_begin) and shares this one.

    CALLED FROM TWO DOORS. The circle open, before the SDK import; and
    circle_file(), because --file-circle returns long before the open's arming
    and its git commit was measured at 57s and 71s on the two newest closes,
    unmarked — a recovery the close itself prints to a person who is already
    worried about whether their circle survived."""
    PC.PHASES.stop_heartbeat()
    PC.PHASES.start_heartbeat(PROGRESS_SECONDS,
                              notify=system_progress_render,
                              quiet_since=seam.system_output_quiet_seconds)


def system_progress_render(line: str) -> None:
    """What a beat looks like, per window and per dev state.

    THE DOT IS AN EXAMPLE, NOT A MANDATE — *"a progress indication, e.g. a
    concatenated '.'"*. A phase name is technical detail, which this project
    already gates on dev, so:

        dev on          the phase line, which says WHICH slow thing is running
        a command pane  CS.PROGRESS_LINE; a pane holds lines, and dots cannot
                        concatenate there — CircleEngine._emit drops end= and
                        flush= by design. ui/circling.py keeps it as ONE row
                        whose glyph turns, dropped when the wait ends
        a terminal      the concatenated dot, which is the one window where it
                        joins onto one line and the one window with no loop of
                        its own to draw an indicator from"""
    if CS.dev_mode:
        emit("command", line)
    elif seam.COMMAND_PANE:
        emit("command", CS.PROGRESS_LINE)
    else:
        seam.system_progress_tick()


def issue_graph_redraw() -> None:
    """Redraw the picture of the issue graph, if the graph has moved since
    it was last drawn. LIVE closes only; the caller gates it.

    WHY AT A CLOSE. A circle is the one thing that moves this graph, and it
    moves it by two routes, both of which are complete by the time this
    runs: a ruling Self types at cmd> or embeds as an annotation, applied
    by issue_commands.issue_command_apply() over the circle's own batch; and a
    `[proposed: ...]` row a part offered, accepted at the vetting
    checkpoint and applied by that same function through proposal_vetting.py.
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
            [sys.executable, "ui/issue_draw.py", record_rel("issues") + "/", "--if-stale"],
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


# THE CLOSE STEP — SHORT_TERM_PROMPT and its cap, the start-of-close marker
# (CLOSING_MARK, circle_close_mark, _close_began), the open-time reports
# (_failed_phase2, _interrupted_closes), _dest_for, _short_term_call,
# short_term_collect, _prompt_blocks_changed and circle_resumable_list — MOVED to
# circle_close.py, 2026-09-03 (cohesion re-homing stage 12, B5/C: that file
# IS the close step; the verifier it shelled out to is circle_close_verify.py).
# This file reads them as CC. commit_sandbox, circle_commit and run_verifier —
# the durable close records — are transcript_store's since 2026-08-16.


# -------------------------------------------------------------- statements
# MOVED to commands.py, 2026-08-16 (phase 2 stage 6, built fifth):
# statements()/statement_resolve()/statement_show() — the 1-based
# numbering /issue-evidence-list shows and `/issue-evidence-add` resolves
# against. Imported at the top of this file.

# --------------------------------------------- the annotation system
# MOVED to annotations.py, 2026-08-16 (phase 2 stage 3): ASK_RE and the
# whole bracket grammar (_propose_command_shape/annotation_extract —
# PRACTICE_KINDS and BPID_RE went with the six retired keywords,
# 2026-08-20), REMEMBER's write path (REMEMBER_RE/
# apply_remember/apply_self_remember), the malformed/retired strip
# (strip_malformed_annotations; RETIRED_REQUEST_RE and
# NEAR_MISS_PROPOSED_RE are gone — an unrecognised bracket is dialog
# text now), live routing
# (annotation_route), proposal_unruled_list, the close-time coalescing
# (_norm_text/
# proposal_collect/proposal_coalesce/_normalize_edge/
# proposal_convergence_queue — RETIRED 2026-09-04, B98), the staging writer (
# proposal_stage), proposal_unruled_show and _wrap58 - verbatim,
# comments and R202 included. The propose half of that moved AGAIN on
# 2026-09-03, to propose_lifecycle.py (cohesion re-homing stage 8). The
# names this file still calls are imported at the top.
# Vetting MOVED to proposal_vetting.py, 2026-08-16 (phase 2 stage 4, built
# sixth): graph_now (per Self's ruling — _propose_approve is its one
# consumer), _practice_describe/_practice_approve/_propose_describe/
# _propose_approve/_propose_deny and proposal_vet — verbatim,
# comments included. main() imports proposal_vet at the top;
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

def _dev_bool(v: str) -> bool:
    """--dev's VALUE FORM, added alongside the bare flag: `--dev=true` /
    `--dev=false`, so a caller that already has a boolean (e.g. circling.py
    forwarding its own --dev=... token verbatim) can say so explicitly
    rather than only being able to assert it present. `--dev` bare still
    means true (nargs="?", const=True below) — the original R286 door is
    unchanged. No other flag in this file takes `=value`; this is the one
    exception, because a caller forwarding a value needs to forward
    "false" too, and store_true has no way to say that."""
    s = v.strip().lower()
    if s == "true":
        return True
    if s == "false":
        return False
    raise argparse.ArgumentTypeError(f"--dev expects true or false, got {v!r}")


# --------------------------------------------------------------------------
# The ic.py-era dev commands and their dispatcher MOVED to
# commands.py, 2026-08-16 (phase 2 stage 6, built fifth):
# cmd_prompt_show, cmd_topic_list/close, cmd_practice_list/delete/
# add, _run_captured, cmd_issue_apply, cmd_issue_status_show/set/op,
# dispatch_dev_cmd and cmd_issue_object — verbatim, the STAGE 2
# ruling and R161 comments included. Until B61 (2026-08-21) this file
# still CALLED ten of them by name from its own Self> loop, one branch
# each, duplicating command_dev_dispatch()'s chain; the loop now delegates
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
        gitrepo.system_git_unconfigured_report_reset()
    except ImportError:
        pass
    _roster_refresh()
    ap = argparse.ArgumentParser(description="IFS circle — local coordinator")
    ap.add_argument("--live", action="store_true",
                    help="write to the group's own record — groups/<group>/circles/ and "
                         "groups/<group>/parts/<name>/short_term_<OT>.toml — and run "
                         "coordinator/circle_close_verify.py at close")
    ap.add_argument("--dry-run", action="store_true",
                    help="no network, no API key needed; every part passes")
    ap.add_argument("--parts", default=",".join(DEFAULT_PARTS),
                    # COUNTED, NOT TYPED. This read "the six speaking parts"
                    # while the default has been every part in the roster —
                    # and the roster is now whatever parts/ holds (R123), so
                    # any number written here is wrong for someone.
                    # NAMES THE MECHANISM THE CODE USES — audit-register.md #18, 2026-09-08.
                    # It said "all N part(s) in parts/", six lines below the comment stating
                    # "never the parts/ scan again" (B117 stage 1, R466/R467): the default is
                    # the DEFAULT GROUP'S MEMBERS, and the scan is only the fallback where no
                    # group row exists. The path was wrong too — there is no parts/ at the
                    # root, it is groups/<group>/parts/. The COUNT was always right, being
                    # computed.
                    help=f"comma-separated part dirs (default: all "
                         f"{len(DEFAULT_PARTS)} member(s) of the default group). "
                         f"A reduced roster is for TESTING — omitted parts are "
                         f"absent from the circle and stay unaware of it.")
    ap.add_argument("--group", default=None,
                    help="open on a NAMED group (coordinator/group_manager.py, "
                         "groups/<name>/group.toml) instead of --parts — a "
                         "deliberately different roster, not a reduced one, "
                         "so the REDUCED LIVE ROSTER warning below does not "
                         "fire for it. Mutually exclusive with --parts.")
    ap.add_argument("--recall-arm", default="delivered",
                    choices=["off", "delivered", "withheld"],
                    # docs/MEMORY_DESIGN.md and R460 (2026-09-06, which closed the
                    # recall trial) are named in this comment rather than in help=,
                    # which a recipient reads and who has neither. 2026-09-09.
                    #
                    # DEFAULT ON SINCE R526 (2026-09-10): the
                    # operator, asked whether search should be on for every circle,
                    # off for every circle, or left disagreeing between the doors —
                    # "on everywhere". It was `off` here while the Ticker defaulted
                    # it ON citing R460's own words, so what a part could actually
                    # do depended on which window opened the circle, while BLOCK 1
                    # taught the bracket unconditionally to all seven.
                    # IT COSTS NO MODEL CALL — the search reads a local index
                    # (recall_index.py, embed_store.py); neither module calls the
                    # API. What it costs is BLOCK 4 bytes when a seed matches, and
                    # the index build at open, which R470/B121 already moved onto a
                    # background thread so it overlaps the pre-warm.
                    # AND IT CANNOT BREAK AN OPEN: a missing fastembed raises
                    # IndexUnavailable, which recall_index_arm_start() catches and
                    # reports, and which a query answers privately with the reason.
                    help="tier A recall (remember_expand.py): expand "
                         "topic-matched seeds into each part's BLOCK 4. "
                         "Default: on ('delivered'). 'off' answers a part's "
                         "search privately without running it; 'withheld' "
                         "computes and logs the packs without delivering them "
                         "— the control arm of the recall trial, now closed, "
                         "kept for a future trial, no UI sends it.")
    # --no-prewarm AND --no-blind ARE RETIRED, 2026-09-09 (the operator:
    # *"remove --no-prewarm, remove --no-blind"*). Both were opt-outs nothing in
    # the tree ever passed: --no-prewarm arrived in the first commit with no
    # help text and no ruling, --no-blind on 2026-08-01 in the commit that built
    # the blind round, and a sweep of every .py, .md, .toml, .txt and .json
    # found no invocation of either — only prose. The pre-warm now always runs
    # (subject to its own early returns: a dry run and a provider with no cache
    # both skip it inside stream_prewarm), and the opening round is always
    # BLIND. circle_round_run() is untouched and still runs every round after
    # the opening.
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
    # HIDDEN FROM --help, UNCHANGED IN BEHAVIOUR — 2026-09-09, the operator:
    # *"leave --dev handling unchanged but remove it from the circle.py help
    # response: it is hidden."* argparse.SUPPRESS drops the option from the
    # rendered --help and touches nothing about parsing: every form below still
    # works, and `if args.dev` still sets CS.dev_mode exactly as it did.
    #
    # THE PROSE MOVED, IT WAS NOT LOST. What this help string said is now in
    # _dev_bool's docstring above and in coordinator/docs/circle.md, which is
    # where a supported-but-hidden flag belongs: absent from --help, present in
    # the manual. The four forms, for a reader who reaches this line —
    #     (absent)      dev off, the default
    #     --dev         on   (const=True; type= is never applied to a const)
    #     --dev=true    on    --dev true   on   (the space form parses too)
    #     --dev=false   declines to turn it on; it cannot turn a set flag off,
    #                   because the branch below is `if args.dev` with no else
    # It turns dev on at the open; `/dev` typed at the Self> prompt toggles
    # it (R542), as the command pane's own unlisted `dev`
    # does.
    ap.add_argument("--dev", nargs="?", const=True, default=False, type=_dev_bool,
                    help=argparse.SUPPRESS)
    ap.add_argument("--list-resumable", action="store_true",
                    help="show circles that have a transcript but no close report")
    ap.add_argument("--file-circle", metavar="OPEN_TIME", default=None,
                    # R506, 2026-09-09 — in the comment, not in help=.
                    help="file a closed circle whose save git refused, then "
                         "reflect on it. Nothing is restarted and "
                         "nothing is re-asked: the circle is already complete "
                         "on disk, so this repeats the save alone and then "
                         "runs the dreaming and synthesis the close skipped. "
                         "Refuses a circle that has already been reflected on.")
    ap.add_argument("--dev-cmd", nargs=argparse.REMAINDER, metavar="VERB ...",
                    help="run ONE always-available command directly from the "
                         "shell, no circle needed — RULED 2026-08-13: a "
                         "development tool able to operate independently of "
                         "any circle in progress. Bypasses dev_mode entirely: this is "
                         "already a deliberate shell invocation, not "
                         "something that could leak into a running circle. "
                         "e.g. --dev-cmd practice-list, --dev-cmd "
                         "practice-add \"text\", --dev-cmd issue n0002 "
                         "status, --dev-cmd part-add \"<describe>\" \"<name>\" "
                         "(both given: added at once, no dialog). "
                         "issue-label-update/issue-relationship-add/"
                         "close/abort/etc. are refused here — they attest against "
                         "a transcript, so they need an actual circle open.")
    args = ap.parse_args()

    # --dev: dev mode ON from the open (R286, 2026-08-21). The standalone
    # terminal has no cmd>, so its dev state comes from this flag or from
    # `/dev` at the Self> prompt (R542). The dual pane's
    # command pane has its own unlisted `dev`, and --dev-cmd forces dev on
    # for its one call.
    #
    # SCOPE WIDENED, 2026-09-01 (the operator, this session): dev_mode used
    # to gate only DEV_SUBSET_COMMANDS and the /help browsing surface (docs/BNF.md).
    # It now ALSO gates the coalesce/prompt-capture/pre-warm/opening-round
    # progress lines below and in llm_client.stream_prewarm()/circle_rounds.circle_blind_round_run
    # — one switch for "developer view," not two. BNF.md's dev-mode section
    # is updated to match.
    if args.dev:
        CS.dev_mode = True

    if args.list_resumable:
        return CC.circle_resumable_list()

    # BEFORE THE MODE CHECK, like --list-resumable above it: this acts on a
    # circle that has already closed, so it opens nothing and needs neither
    # --live nor --dry-run. It DOES write and it DOES call the model, which
    # is why it names the circle explicitly rather than guessing the newest.
    if args.file_circle:
        # circle_file() CALLS THE MODEL (the reflection), and the client build below — where a
        # live run's missing key gets R330's page — never runs for this dispatch (R546).
        if not stream_key_present_read():
            emit("command", "\n" + KEY_MISSING_HELP + "\n")
            return 2
        return CC.circle_file(args.file_circle)

    if args.dev_cmd is not None:
        if not args.dev_cmd:
            emit("command", "  usage: --dev-cmd VERB [args...], e.g. "
                  "--dev-cmd practice-list")
            return 2
        head = CS.command_head_normalise(args.dev_cmd[0])
        # THE SHELL ATE THE QUOTES. `--dev-cmd part-add "<describe>" "<name>"` arrives as
        # two bare elements; joined bare, _issue_add_args() reads the line as ONE describe
        # and the name is lost (the operator, 2026-09-15: "A --dev-cmd should flow
        # through"). For the quoted-string verbs each element is one string again; every
        # other verb keeps the bare join (`--dev-cmd issue n0002 status`).
        if len(args.dev_cmd) > 1 and head in QUOTED_ARG_COMMANDS:
            rest_text = " " + command_args_quote(args.dev_cmd[1:])
        else:
            rest_text = " " + " ".join(args.dev_cmd[1:]) if len(args.dev_cmd) > 1 else ""
        # "Bypasses dev_mode entirely" (help text above) was written but
        # never enforced — dev_mode defaults False at process start, so
        # e.g. `--dev-cmd help object_classes` hit the same gate a
        # command-pane user with dev off would, contradicting this door's
        # own documented contract. (The `global dev_mode` SyntaxError trap
        # the old comment documented died with the global itself —
        # CS.dev_mode is a plain attribute write now.)
        CS.dev_mode = True
        if not command_dev_dispatch(head, rest_text):
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
    roster_problems = R.part_verify()
    if roster_problems:
        emit("command", "\n  !! THE ROSTER DOES NOT VERIFY — no circle opened.")
        for p in roster_problems:
            emit("command", f"     {p}")
        emit("command", f"\n     {len(DEFAULT_PARTS)} part(s) would have been in this "
              f"circle: {', '.join(DEFAULT_PARTS) or '(none)'}")
        emit("command", "     python coordinator/part_roster.py")
        return 2

    if not args.live and not args.dry_run:
        # THE PRACTICE MODE IS RETIRED — R250 deprecated it in favor of the
        # lab, and R360 (D65 a) executed the retirement: a bare invocation
        # used to open a REAL-model circle whose writes went to
        # work/sandbox/ — a person practicing outside the record. The lab
        # is where practice lives now; --dry-run (no model calls, every
        # part passes) remains the harnesses' own mode, unchanged.
        # THE SECOND AND THIRD LINES WERE WRITTEN FOR THIS TREE AND SHIPPED TO
        # EVERYONE, 2026-09-09 (audit-register 2026-09-09 #9). They named "the
        # lab checkout", which a recipient does not have, and cited R249, which
        # is in packaging/ignore.txt and has never shipped. This refusal is the
        # likeliest first thing a person sees after installing the bundle — it
        # fires on `circle.py` with no mode — so it was the worst possible place
        # for a citation only this tree can resolve. It is also the exact example
        # packaging/shipped_references.py was built to catch, and quotes in its
        # own man page as its reason for existing.
        emit("command", "Choose a mode: --live (the real circle) or "
                        "--dry-run (no model calls; the test rig).")
        emit("command", "  --dry-run is the way to try the mechanics without "
                        "touching the record:")
        emit("command", "  it opens a real circle, and every write lands under "
                        "work/sandbox/ instead.")
        # AND WHAT --live WILL NEED, when it is not there — R546: this is
        # the likeliest first run of a fresh install, so the whole text rides it.
        if not stream_key_present_read():
            emit("command", "\n" + KEY_MISSING_HELP + "\n")
        return 2


    used_group = args.group is not None
    if used_group and args.parts != ",".join(DEFAULT_PARTS):
        emit("command", "--group and --parts were both given — use one, not "
                        "both.")
        return 2
    # A BARE OPEN NEEDS A DEFAULT GROUP — R468, B120 stage 4 (2026-09-07): one installed group,
    # or one whose group.toml says `default = true`; otherwise --group is required and this is
    # the one sentence that says so. No literal group name is depended on.
    if not used_group:
        why = _RP.group_default_refusal_read()
        if why:
            emit("command", f"  {why}")
            return 2
    import group_manager as GA
    import process_core_prompt_projection as PCP
    if used_group:
        resolved = GA.group_resolve(args.group)
        if resolved is None:
            emit("command", f"no group named {args.group!r} — "
                            f"/group-list (or group_manager.group_rows_read()) shows what "
                            f"exists")
            return 2
        parts = resolved
        # THE GROUP'S TREE — R467, B117 stage 3 (2026-09-07): a circle opened on a group reads
        # and writes that group's RECORD, groups/<name>/. group_set() rebinds record_paths'
        # constants and runs every follower (roster's tables, in place), so PART_TAGS and
        # record_dir() below already answer for this group. Before anything reads the record.
        if args.group != _RP.DEFAULT_GROUP:
            _RP.group_set(args.group)
    else:
        parts = [p.strip() for p in args.parts.split(",") if p.strip()]
    # BLOCK 1's group layer (R464, B115, 2026-09-07): the group row's `layer` file, or the IFS
    # layer for a row without one and for every circle opened without --group. Set BEFORE the
    # one group_shared_read() below, which composes it in. A missing file refuses the open.
    PCP.circle_identity_layer_set(GA.group_layer_read(args.group) if used_group else None)
    # ...and its word for one of its members (D104): the IFS group declares "part", a group that
    # declares nothing gets "role", and a circle opened without --group gets the family's, as the
    # layer above does. Set here so BLOCK 1 never mixes the two words in one prompt.
    PCP.circle_identity_words_set(
        (GA.group_member_words_read(args.group) or PCP.DEFAULT_WORDS) if used_group else None)
    bad = [p for p in parts if p not in PART_TAGS or not (record_dir(ROOT, "parts") / p).is_dir()]
    if bad:
        emit("command", f"unknown part(s): {', '.join(bad)}")
        return 2
    if args.seed is not None:
        random.seed(args.seed)

    # A reduced roster is a testing affordance. In a LIVE circle it has a real
    # cost: an omitted part is absent from the transcript, writes no short_term,
    # and dreaming reads "no short_term for this circle" as no
    # engagement (part_dreaming.part_dream()) — indistinguishable from
    # a part who was present and chose silence. It gets no dream entry and no
    # relationship update. It learns of the circle only indirectly, through
    # whatever the issue graph's state has become by the next circle it attends.
    missing_roster = [p for p in DEFAULT_PARTS if p not in parts]
    # A NAMED GROUP IS DELIBERATE, NEVER "REDUCED" — the warning below exists
    # to catch an ACCIDENTALLY partial --parts roster in a live IFS circle;
    # --group ifs-that-cuts-someone or a genuinely different roster (an
    # engineering group, say) chose its own membership on purpose and gets no
    # scare, per docs/CIRCLE_TYPES_DESIGN.md.
    if args.live and missing_roster and not used_group:
        emit("command", "\n  !! REDUCED LIVE ROSTER")
        emit("command", f"     absent: {', '.join(PART_TAGS[p] for p in missing_roster)}")
        emit("command", "     These parts will not be present, will write no short_term, and")
        emit("command", "     dreaming will record no engagement for them. They will learn")
        emit("command", "     of this circle only indirectly, via the issue graph's state next")
        emit("command", "     time they attend. Prefer --dry-run for partial rosters.")
        if not args.yes and read_line("     type 'yes' to proceed: ").strip().lower() != "yes":
            emit("command", "     cancelled.")
            # 2, NOT 1. Exit 1 means a circle RAN and its record is
            # incomplete — the thing dreaming/reconcile must be told about. A
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
        # ONE HOME since 2026-09-09 — the open step needs this too, so the body is
        # circle_open.circle_transcript_path_read() and this is the local spelling of it.
        return CO.circle_transcript_path_read(args.live, t)

    ot: str | None = args.resume
    guard: WriteGuard | None = None
    path: pathlib.Path | None = None
    if args.resume:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}", ot):
            emit("command", f"--resume wants an open time like 2026-08-02_1259, got {ot!r}")
            return 2
        closed = ROOT / "work" / "logs" / f"close_{ot}.json"
        import short_term_manager as STM
        done = STM.short_term_glob(record_dir(ROOT, "parts"), ot)      # either suffix (B96)
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
            # not. short_term_collect() keeps the already-written files,
            # so resuming an interrupted close collects only the missing.
            try:
                _, _, tr0 = TS.circle_transcript_parse(
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

    # THE BEAT STARTS HERE, BEFORE THE SDK IMPORT — moved up from just before
    # the record sweep, 2026-09-09. `stream_client_build()` below pays the
    # first `import anthropic` in the process: measured 1.7-2.8s across eight
    # runs on a warm tree, of which the import alone is 2.45s. Under three
    # seconds only by the margin of a warm file cache, and the first launch
    # after a reboot crosses it with nothing on screen. Nothing between here
    # and the sweep needs the beat off, and a dot before the banner is honest.
    #
    # IT CANNOT REACH FURTHER BACK. The interpreter start and `import circle`
    # are 0.33-0.56s more, and no Python of ours is running yet to mark them.
    system_progress_arm()

    client = None
    if not args.dry_run:
        # THE PROVIDER BUILDS IT — stage 2 of the socket (R382). This block
        # named `anthropic` three ways: the import, the key variable, and the
        # `.env` fallback. All three are one vendor's, and after stage 2 the
        # ONLY module in the tree that names the SDK is providers.py.
        #
        # THE TWO FAILURES STAY DISTINGUISHABLE, because they need different
        # answers from a person: the package missing is an install, and the
        # key missing is R330's whole page of how to get one and where to put
        # it. stream_client_build() raises for the second and lets the first through
        # as ImportError.
        try:
            client = stream_client_build()
        except ImportError:
            emit("command", "pip install anthropic")
            return 2
        except RuntimeError:
            # HOW TO GET ONE, WHERE TO PUT IT, HOW TO KEEP IT — R330,
            # 2026-08-23. This printed one line, `set
            # ANTHROPIC_API_KEY (env var or project .env)`, which is the whole
            # answer for the person who wrote it and none of the answer for
            # a first-run user. The text is the provider's, since every word
            # of it is that vendor's console.
            emit("command", "\n" + KEY_MISSING_HELP + "\n")
            return 2

    mode = "LIVE" if args.live else "sandbox"
    emit("command", f"\nIFS circle coordinator — {mode} — "
          f"{ot or 'open time assigned when the topic is entered'}")
    # B56(1), 2026-08-19: NAME THE TREE, at open. Named as the one thing to
    # watch on 2026-08-04 and never built. record_paths.ROOT is derived from
    # __file__, so a circle run inside a worktree already reads and writes
    # only that worktree — which is what makes running a LIVE circle in a lab
    # tree by mistake both possible and, until this line, invisible.
    #
    # gitrepo owns the question — one home for it, since the tag namer
    # (B56(5)) asks it too and two copies of "am I in a lab" would be the
    # three-copies problem B57(2) just finished undoing.
    import gitrepo as _G
    in_main_checkout = _G.system_git_is_main_checkout()
    emit("command", f"tree: {ROOT}"
         + ("" if in_main_checkout else "   (A WORKTREE, not the main checkout)"))
    if args.live and not in_main_checkout:
        # The files are contained by construction; the REFS are not. A
        # worktree shares .git, so this circle's own `circle/<OT>` and its
        # processing's `dream/<OT>` land in the repository-wide namespace the
        # main tree's already_processed() reads. B56(5) is the fix; until it
        # lands, saying so is.
        # NEXT.md's B56(5) is the fix and is named in the comment above, not in
        # the message: this line ships, and a recipient has no NEXT.md. 2026-09-09.
        emit("command", "  !! LIVE, IN A LINKED WORKTREE. Files are this tree's "
                        "alone; the TAG namespace belongs to the whole "
                        "repository and is shared with its other checkouts.")
    emit("command", f"parts: {', '.join(parts)}")
    if path:
        emit("command", f"transcript: {path}")
    if not args.live:
        # B32 + R176: the old text said "work/ is write-protected", which was
        # already false (work/logs/ is written via circle_close_verify.py) and became
        # doubly so when sandbox output moved UNDER work/. Name the one root
        # that is actually writable instead of listing what is not.
        emit("command", "sandbox mode: writes land under work/sandbox/ only; "
                        "circles/ and parts/ are untouched.")
    # A DRY RUN NEEDS NO KEY AND SAYS WHAT A LIVE ONE WILL — R546. The short
    # form: the run goes on. Through the command channel, so circling.py's command pane shows it too.
    if args.dry_run and not stream_key_present_read():
        emit("command", "\n" + KEY_MISSING_BRIEF)

    # THE OPEN STEP IS circle_open.py's, 2026-09-09. Everything from the corruption gate
    # to the opening round left this function; what remains here is the flags above and the
    # Self> loop below, which is what main() is actually for. The same carve as
    # circle_close.py (B99 stage 12) at the other end of the circle.
    #
    # IT RETURNS ONE OF TWO THINGS and the check below is not a formality: an int is a
    # REFUSAL — the corruption gate, the API check, a client that will not build, a declined
    # roster, an unusable --resume — and every one of them must still stop the program with
    # its own exit code, having written nothing.
    opened = CO.circle_open(args, client, parts, ot, path, guard)
    if isinstance(opened, int):
        return opened
    ot, path, guard = opened.ot, opened.path, opened.guard
    transcript, sysblocks = opened.transcript, opened.sysblocks
    since_self, state = opened.since_self, opened.state
    issue_cmds, circle_ref = opened.issue_cmds, opened.circle_ref
    # ASSIGNED HERE, not in the open step. circle_open() cannot `global CONSOLE_NAME` on this
    # module's behalf — it would bind its own — and the Self> prompt below reads THIS one.
    global CONSOLE_NAME
    CONSOLE_NAME = opened.console_name

    closing_confirmed = False
    abort_confirmed = False
    aborted = False

    while True:
        try:
            # THE PROMPT IS THE CONFIGURED NAME, CONSOLE-ONLY. Ruled
            # 2026-08-07 (support IFS_USER_NAME), narrowed 2026-08-11: this
            # text never leaves the console — the transcript always records
            # SELF_DISPLAY ("Self") regardless of what this prompt shows, so
            # personalising it here carries no PII into a part's prompt.
            cmd = read_line(f"\n{circle_prompt_read()}", channel="circle").strip()
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
        # A RECALL IS A PART'S, NOT SELF'S — RULED 2026-08-30, the operator,
        # verbatim: *"refuse it."* Asked as a decision because nothing
        # enforced it: apply_recall() is called from circle_rounds.py alone, so a
        # `[recall: ...]` typed here was neither executed, nor stripped, nor
        # refused. withheld() was False for it, so render_messages() spoke it
        # to all seven parts as ordinary Self speech and the raw line entered
        # the transcript — E06's contamination shape, through the one door
        # R225's guard never covered.
        #
        # REFUSED, NOT STRIPPED, and that is R225's own distinction: the
        # topic prompt loops until the line is clean rather than repairing
        # it, because a statement silently shortened is one the typist never
        # chose. Same here — nothing is recorded, nothing is searched, and
        # the whole line comes back to be retyped. The complaint goes to the
        # COMMAND channel, never into the room's pane.
        #
        # BEFORE EVERY BRANCH BELOW, so a recall cannot ride into the room
        # inside a line that also carries speech, and before the /close and
        # /abort verbs so it can never sit between Self and ending a circle.
        stray = MK.part_only_in(cmd)
        if stray:
            more = f" (+{len(stray) - 1} more)" if len(stray) > 1 else ""
            emit("command", f"  !! {stray[0]}{more} — a recall is a part's "
                 f"own search of its own record, not Self's.")
            emit("command", "     Your own record reads back with "
                 "`remember-list` at the command pane.")
            emit("command", "     Nothing was recorded, nothing was searched. "
                 "Type your statement again.")
            continue
        # RULED 2026-08-17 (R205): "/close" is start-anchored, not exact —
        # `/close this circle` closes same as bare `/close`, any text after
        # the verb is accepted and ignored, never parsed, never stored. The
        # space in "/close " is the token boundary: it admits "/close ..."
        # without also admitting "/closeout" or similar.
        if cmd == "/close" or cmd.startswith("/close "):
            props = proposal_unruled_list(transcript, issue_cmds)
            if props and not closing_confirmed:
                # Ruled 2026-08-04: surfaced at close, for Self to rule on
                # or pass. Shown ONCE — a second /close proceeds, so a
                # proposal can never block a circle from ending.
                proposal_unruled_show(props)
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
            # path's way to EVERY VERB, one row each; the dual pane's room
            # refuses every `/help <arg>`, so it never arrives from there.
            # SWAPPED 2026-09-11 (R554): bare /help under
            # dev shows the class rows, /help all the enumeration — until
            # then each showed the other's. `all` is command_help_render()'s
            # own word since 2026-09-15, so the command pane's no-circle
            # door and --dev-cmd answer it too; this loop no longer
            # branches on it.
            if not arg:
                emit("circle", HS.circle_pane_help())
            else:
                emit("command", command_help_render(arg))
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
                  f"\n  group {_RP.group_read()}"
                  f"\n  {len(parts)} parts")
            emit("command", part_token_table(parts, sysblocks, since_self,
                                        client, LC.MODEL, args.dry_run))
            emit("command", f"\n  running cost ${METER.cost():.4f} over {METER.calls} calls")
            continue
        if cmd in ("/round", "/pass"):
            # RULED 2026-08-10: /pass is a new alias equalling /round —
            # both spellings name the one operation the circle pane
            # recognizes beyond speech itself (circling_and_evolving.md
            # §5, §9). Not a rename: /round keeps working unchanged.
            with PC.PHASES.span("round"):
                circle_round_run(client, parts, sysblocks, transcript, since_self,
                          state, guard, path, args.dry_run, live=args.live)
            continue
        # /dev TOGGLES DEV HERE — R542, the operator: *"there
        # is a command /dev, such that when it is entered, it turns dev=true, and
        # the entire help structure becomes visible"*, then *"The command /dev
        # must toggle."* Every help path reads CS.dev_mode live, so the next
        # /help answers at the new tier. Named by no listing (R199; R527, "ALWAYS
        # hidden"), and never spoken: this branch continues before anything is
        # recorded. Only the standalone terminal arrives here — both UIs' circle
        # panes refuse /dev by name (R286, command_surface.verb_class) and each
        # command pane keeps its own `dev`. EXACT, as that `dev` is: "/dev on"
        # must not be a toggle in disguise.
        if cmd == "/dev":
            CS.dev_mode = not CS.dev_mode
            emit("command", "  dev: " + ("on" if CS.dev_mode else "off"))
            continue
        # THE ALLOWED QUESTION IS command_surface's — 2026-09-09. It was
        # `not in USER_SUBSET_COMMANDS` here, which made a `-list` verb's
        # availability depend on which of two tables it happened to sit in;
        # the operator ruled every `-list` verb runnable regardless of dev.
        if (cmd.startswith("/")
                and not CS.command_is_allowed(
                    CS.command_head_normalise(cmd.split(" ", 1)[0]),
                    CS.dev_mode, surface=CS.SURFACE_SELF)):
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
        # /issue-evidence-list [<n>] — named /statements until 2026-08-21 (D59).
        # The bare verb, or the verb and one argument (B133): the loop owns it
        # because it reads the live transcript, which no dispatcher has.
        if cmd == "/issue-evidence-list" or cmd.startswith("/issue-evidence-list "):
            statement_show(transcript, cmd[len("/issue-evidence-list"):])
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
        head = (CS.command_head_normalise(cmd.split(" ", 1)[0])
                if cmd.startswith("/") else "")
        # ONE DISPATCHER — B61, 2026-08-21 (the operator: "tidy now"). Ten verbs
        # used to be branched here by hand, each a copy of the branch
        # commands.command_dev_dispatch() already had for it, and nothing
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
            circle_transcript_append(guard, path, f"[{SELF_DISPLAY}]: {cmd}")
        if head and command_dev_dispatch(
                head, cmd.split(" ", 1)[1] if " " in cmd else "",
                record=_record_practice_cmd,
                guard=guard):
            continue
        if head in IC.HEADS:
            c, why = IC.issue_command_parse(cmd, circle_ref)
            if c is None:
                emit("command", f"  {why}")
                continue
            if c["verb"] == "issue-evidence-add":
                # IC.issue_command_parse() stays pure — it only knows the statement
                # NUMBER. Resolving it against the live transcript (same
                # numbering /issue-evidence-list shows) belongs here, the same way
                # IC.issue_precheck() below needs the live graph passed in.
                stmt_e, why3 = statement_resolve(transcript, c["stmt"])
                if stmt_e is None:
                    emit("command", f"  {why3}")
                    continue
                c["part"] = stmt_e["speaker"]
                c["quote"] = stmt_e["text"]
                c["source"] = circle_ref
            if why2 := IC.issue_precheck(c, VT.issue_graph_now_read()):
                emit("command", f"  {why2}")
                continue
            c["index"] = len(transcript)
            issue_cmds.append(c)
            # ECHOED TO THE RECORD, WITHHELD FROM THE ROOM (ruled 2026-08-04).
            # `append` writes the transcript file; the `cmd` flag keeps
            # prompt_messages_render from ever showing it to a part. Both halves are
            # needed: the file is what the gate will verify the edge against.
            transcript.append({"speaker": ID.SELF_ID, "display": SELF_DISPLAY,
                               "text": cmd, "cmd": True})
            circle_transcript_append(guard, path, f"[{SELF_DISPLAY}]: {cmd}")
            emit("command", f"  recorded — {IC.issue_describe(c)}"
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
        #
        # "Known:" IS WHAT THIS DEV STATE ADVERTISES — R542:
        # *"An UNKNOWN COMMAND prints the items visible according to the state
        # of dev."* The predicate /help lists by (R527), so a typo never names a
        # verb /help would not; /dev is in no table and never appears.
        if cmd.startswith("/"):
            head = CS.command_head_normalise(cmd.split(" ", 1)[0])
            known = [h for h in KNOWN_CMDS
                     if CS.command_is_listed(h, CS.dev_mode, surface=CS.SURFACE_SELF)]
            emit("command", f"  UNKNOWN COMMAND {head} — not sent to the room. "
                  f"Known: {', '.join(known)}")
            emit("command", f"  (to say this to the parts, retype it without the "
                  f"leading slash)")
            continue
        if not cmd:
            continue
        raw = cmd
        cmd, self_remembered = remember_self_apply(guard, SELF_DISPLAY, cmd)
        if self_remembered:
            emit("command", "  (remember recorded to self/remember.toml — "
                  "stripped, private)")
        if cmd:
            cmd = annotation_malformed_strip(cmd, SELF_DISPLAY)
        if not cmd:
            # STILL A PASS — no since_self reset, no state["last"], no round
            # run; Self said nothing the room can hear. RULED 2026-08-18, the
            # same as a part's remember-only turn in circle_rounds.py, and the RECORD
            # keeps the bracket the same way: one withheld entry, one file
            # line, `remember_only` re-derived on resume. See that comment,
            # and transcript_store.circle_transcript_is_withheld().
            #
            # A whole line that was only a MALFORMED non-remember annotation still
            # writes nothing at all — there is no record to complete, which is
            # what `REMEMBER_RE.search(raw)` distinguishes.
            record = annotation_malformed_strip(raw.strip(), SELF_DISPLAY,
                                             quiet=True)
            if record and REMEMBER_RE.search(raw):
                transcript.append({"speaker": ID.SELF_ID,
                                   "display": SELF_DISPLAY, "text": "",
                                   "raw": record, "remember_only": True})
                circle_transcript_append(guard, path, f"[{SELF_DISPLAY}]: {record}")
            continue
        # THE ROOM AND THE RECORD PART COMPANY HERE, exactly as they do for
        # a part in circle_rounds.py — see that comment for the whole of it. Self's
        # own remember is no more the room's business than a part's: `cmd`
        # (stripped) is what the transcript entry, every rebuilt prompt and
        # annotation_route() get; `record` (bracket intact) is what the
        # transcript FILE gets. Ruled 2026-08-14, built 2026-08-18.
        record = cmd
        if REMEMBER_RE.search(raw):
            record = annotation_malformed_strip(raw.strip(), SELF_DISPLAY,
                                             quiet=True)
        # QUOTE-AS-LANDS — R155, routed to an unvetted REMEMBER 2026-08-19
        # (R251). BEFORE the append, and that ordering is
        # the mechanism, not a preference: `transcript` must hold only
        # PRIOR statements for "a prior statement in this circle" to
        # mean anything, and the `/issue-evidence-list` numbers it records stay
        # valid because the list only ever grows. Reads `cmd` — the
        # ROOM's text — so an already-stripped bracket can never be
        # mistaken for quoted material.
        QM.lands_quote_apply(guard, transcript, cmd)
        entry = {"speaker": ID.SELF_ID, "display": SELF_DISPLAY, "text": cmd}
        if record != cmd:
            entry["raw"] = record
        transcript.append(entry)
        circle_transcript_append(guard, path, f"[{SELF_DISPLAY}]: {record}")
        annotation_route(SELF_DISPLAY, cmd, live=args.live)
        since_self = {p: 0 for p in parts}     # Self spoke — reset, per process_core
        state["last"] = None
        with PC.PHASES.span("round"):
            circle_round_run(client, parts, sysblocks, transcript, since_self, state,
                      guard, path, args.dry_run, live=args.live)

    # ---- the circle's graph rulings -------------------------------------
    # Written for EVERY circle, sandbox or live, beside its transcript. A
    # sandbox circle stops here: the record is a proposal to the live tree
    # that has not touched it, and `python memory/issue_commands.py
    # <that file>` is how it gets there once Self has read it.
    if issue_cmds and not aborted:
        cdir = record_dir(ROOT, "circles") if args.live else SANDBOX_CIRCLES
        crec = cdir / f"commands_{ot}.toml"
        crec.write_text(IC.issue_dump(issue_cmds, circle_ref), encoding="utf-8",
                        newline="\n")
        # COMMAND CHANNEL, 2026-08-21 — the operator, reading his close:
        # *"Proper output is in the wrong pane (circle), put it in command."*
        # This report is Coordinator->Self about the record, never room
        # dialog; it printed on the circle channel since the day the
        # channels were classified.
        emit("command", f"\n  {len(issue_cmds)} graph ruling(s): "
              f"{crec.relative_to(ROOT)}")
        for c in issue_cmds:
            emit("command", f"    {IC.issue_describe(c)}")
        if args.live:                     # ruled 2026-08-04: automatic
            ok, msg = IC.issue_command_apply(issue_cmds)
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
        # THE BEAT ENDS WITH THE CIRCLE, not only with a close. It is armed at
        # open now, so an abort is a path that has one running and never
        # reached the close's stop.
        PC.PHASES.stop_heartbeat()
        emit("circle", f"\naborted. transcript kept: {path}")
        if args.live and any(e["speaker"] in PART_TAGS for e in transcript):
            emit("command", "  NOTE: no short_terms were collected. Parts that spoke have no")
            emit("command", "  record of this circle, and nothing backfills them")
            emit("command", "  automatically — an /abort never reaches dreaming. Repair by hand:")
            emit("command", "    circle_audit.py --backfill --commit")
        emit("command", METER.report())
        return circle_failures_report()

    # THE SEPARATE PRACTICE STAGING CALL IS GONE, 2026-08-20 (B60). A
    # practice is proposed as `[proposed: /practice-add ...]` and a better
    # option as `[proposed: /better-option-add ...]`, so both are staged by
    # the ONE call below and RUN at approval. Its malformed report went with
    # it: a malformed annotation is now reported at the moment it is spoken,
    # by annotation_malformed_strip(), which is where R231 asked for it and is
    # strictly earlier than /close.
    #
    # R202, 2026-08-16: ONE staging call replaces the separate request/
    # relation ones — `[proposed: <command>]` covers every future now
    # (spelled `[propose <text>]` until R273).
    # ADDITIVE, ALONGSIDE the existing proposal_unruled_show()/`/issue
    # issue-relationship-add` path below (unchanged) for an
    # issue-relationship-add attempt specifically — #32, Self's
    # explicit scope. issue_cmds is complete by this point (the Self>
    # loop has ended), so this can safely dedupe against every /issue
    # issue-relationship-add Self already typed this circle.
    staged_propose_ids = proposal_stage(ot, transcript, issue_cmds,
                                                  args.live)
    if staged_propose_ids:
        # COMMAND, not circle: this is Coordinator reporting an operation
        # to Self, which docs/BNF.md line 105 keeps out of the circle
        # entirely. Corrected with R221 channel work (NEXT.md B51 records
        # that this one fix needed no ruling of its own).
        emit("command", f"\n  {len(staged_propose_ids)} proposal(s) staged: "
              f"{', '.join(staged_propose_ids)}")
    # CHECKPOINT 1 — immediately after the write. Shows EVERY currently
    # pending row, across every propose-class kind, not only this
    # circle's additions: a skip from an earlier close reappears here
    # too, same as it will at the next priming (docs/BNF.md
    # PRACTICE LIFECYCLE, Vetting).
    # NEXT.md D14, 2026-08-17: no longer `if args.live:` around the vetting
    # call — proposal_vet() itself now handles sandbox (describe +
    # validate, never rule). The topics report below stays live-only; it is
    # unrelated to vetting and out of this ruling's scope.
    # the coalesce refresh, same guard and same reasons as the open
    # checkpoint's (R356/E22) — the close is where a circle's own
    # [proposed: ...] rows have just been staged, so this is the pass
    # the operator's "once, at circle end" ruling names (R356).
    if args.live:
        try:
            import proposal_group_manager as CG
            CG.proposal_group_refresh(
                say=lambda m: emit("command", m) if CS.dev_mode else None)
        except Exception as e:
            emit("command", f"  coalesce: skipped ({e})")
    confirmed_this_close = proposal_vet("at close", args.live,
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
    # itself. See issue_draw.issue_draw_is_stale().
    # THE CLOSE STOPWATCH AND THE HEARTBEAT (2026-08-30) start HERE — after
    # the vetting checkpoint, which is human time, and before the first
    # automated step. Everything below is what the <=5-minute aim covers,
    # and while it runs the command pane hears something at least every
    # PROGRESS_SECONDS, even if only the beat.
    # THE STOPWATCH ONLY. The beat was armed at open and is already running at
    # PROGRESS_SECONDS; arming a second one here returned False and silently
    # discarded its own close_heartbeat_seconds anyway, so that arming is
    # gone rather than left looking effective. close_begin() is what supplies
    # the "(Ns since /close)" suffix the beat's dev line carries.
    PC.PHASES.close_begin()

    if args.live:
        with PC.PHASES.span("close.redraw_graph"):
            issue_graph_redraw()

    # THE START-OF-CLOSE MARKER, 2026-08-23. Written HERE and not at the
    # `/close` verb: everything above this line can still return without
    # collecting anything (/abort), and a marker for a close that
    # never began would make the next open report a circle that is fine. This
    # is the last statement before the first short_term could be written, which
    # is exactly the window _interrupted_closes() could not see into.
    if args.live:
        CC.circle_close_mark(ot)
    emit("command", "\ncollecting short_terms:")
    try:
        with PC.PHASES.span("close.short_terms"):
            written = CC.short_term_collect(client, parts, sysblocks, transcript,
                                             ot, guard, args.dry_run)
    except KeyboardInterrupt:
        # The second Ctrl-C on 2026-08-02 landed here and left a traceback, no
        # short_terms and no close report. The transcript was never at risk —
        # it is written statement by statement — so say so, and say how to get
        # back in, rather than printing a stack trace at someone mid-circle.
        fail("close INTERRUPTED — short_terms incomplete")
        emit("command", "\n  !! close interrupted. THE TRANSCRIPT IS INTACT — every")
        emit("command", "     statement was written as it was made; nothing is lost.")
        # THE MODE MUST MATCH THIS SESSION'S OWN, 2026-09-01 (audit-register.md
        # #25) — a hardcoded --live here told a --dry-run session to resume
        # with --live, which circle_path() (above) resolves to ROOT/circles/
        # instead of the SANDBOX the transcript actually lives under. The
        # identical shape D-c (R428) fixed two lines below, on the one line
        # its approved scope did not touch.
        resume_flag = "--live" if args.live else "--dry-run"
        emit("command", f"     resume:   python coordinator\\circle.py {resume_flag} "
                        f"--resume {ot}")
        if args.live:
            emit("command", "     or repair by hand:  circle_audit.py --backfill --commit")
        # else: circle_audit.py --backfill only ever touches a LIVE close's
        # short_terms (short_term_backfill_step() is step 0 of a LIVE circle_process) —
        # a dry-run circle never reaches dreaming, so --resume is the only
        # real repair here.
        PC.PHASES.stop_heartbeat()
        emit("command", METER.report())
        return circle_failures_report()
    if args.live:
        # NOT GATED ON dev — the one line a person hears between the last short_term and
        # the spend report when dev is off, because circle_process()'s narration below is.
        # Filing comes first, so the line names all three rather than "synthesis" alone.
        emit("command", "\nfiling, then dreaming and synthesis — 5-10 minutes is not unusual")
        with PC.PHASES.span("close.verifier"):
            circle_close_verifier_run(ot)
        # THE SPAN LABEL KEEPS THE PRE-B99 NAME, DELIBERATELY — audit-register.md #22,
        # 2026-09-08. It is not prose: rulings/R470.toml cites `close.commit_circle` verbatim,
        # with its measured 32.59s, as the phase that must finish before dreaming. Renaming
        # it to match transcript_store.circle_commit() would silently break that citation,
        # and a ruling is the one record a rename may not reach.
        with PC.PHASES.span("close.commit_circle"):
            filing = circle_commit(ot, written)
        # PHASE 2 — dreaming then synthesis, synchronous, AFTER the circle's
        # own commit (R167: a phase-2 failure leaves the circle safely
        # committed; R168: failures write a report, get one diagnostic
        # call, and hand back — no automated catch-up). LIVE ONLY:
        # SYNTHESIS writes self/, which no sandbox may touch.
        if CS.dev_mode:
            emit("command", "\nphase 2 — dreaming and synthesis "
                  "(coordinator/inter_circle.py):")
        import inter_circle as ICP
        # THE WHOLE NARRATIVE IS TECHNICAL DETAIL, gated together
        # (2026-09-01) — dreaming/synthesis progress, staging + gate,
        # mid_term refresh, git-commit mechanics, even the failure
        # diagnosis text circle_process() prints on its own way out. Safe
        # to gate as one block because the FAILURE case has its own
        # unconditional signal regardless: the fail() calls below, which
        # fire whether or not that narration was ever shown.
        #
        # A REFUSED DISTILLATE IS NEITHER NARRATION NOR FAILURE. A mid_term
        # derivation refused as SUSPECT returns 0 — a report, not a failed
        # close (R532) — so no fail() says it. Its lines travel `warn`,
        # which is never gated.
        #
        # A CIRCLE THAT IS NOT FILED IS NOT REFLECTED ON. R506, 2026-09-09,
        # the operator: "Stop, do not reflect on a circle that is not filed.
        # Do support reflection if the circle is later filed." At
        # 2026-09-09_1122 the gate refused this commit and phase 2 ran
        # anyway, writing dreaming and synthesis into the live tree on top of
        # a circle git had declined — and then failed its OWN commit for the
        # same reason, leaving the operator one re-run away from dreaming
        # twice. Reflection is now downstream of the filing, not beside it.
        #
        # "refused" ONLY. A tree that keeps no history has not refused
        # anything (R349's Tier 1), and withholding dreaming there would
        # punish the supported case rather than the broken one.
        if filing == "refused":
            fail("the circle is written but NOT FILED — git refused the "
                 "commit; see the 'fail' line above for why. Nothing you "
                 "wrote is lost, and no reflection has run on it. When the "
                 "refusal is fixed, file it and reflect in one step:\n"
                 f"    python coordinator\\circle.py --file-circle {ot}")
        elif ICP.circle_process(ot, live=True, confirmed=confirmed_this_close,
                                say=lambda s: emit("command", s) if CS.dev_mode
                                              else None,
                                warn=lambda s: emit("command", s)):
            fail("phase 2 (dreaming/synthesis) did not complete — the "
                 "circle itself is filed; see work/logs/"
                 f"dream_error_{ot}.json and re-run by hand")
    else:
        emit("command", "  (sandbox mode: verifier not run — it reads the live tree)")
        circle_sandbox_commit(ot)
        emit("command", "  (sandbox mode: no dreaming/synthesis — phase 2 "
              "writes self/, live circles only)")
    emit("command", METER.report())
    circle_spend_report_write(ot, guard.live)
    # THE DELTA REPORT (circle_stats, 2026-08-30) — what this circle changed
    # across the registers, both segments. AFTER write_spend_report so the
    # spend it cites is on file; LIVE ONLY, because its anchors are the two
    # machine commits a sandbox never makes. Fails open, like the spend
    # report above it and for the same reason.
    if args.live:
        try:
            import circle_delta as CD
            with PC.PHASES.span("close.delta_report"):
                CD.circle_delta_at_close(ot, lambda s: emit("command", s))
        except Exception as e:                                 # noqa: BLE001
            emit("command", f"  circle_delta skipped "
                            f"({type(e).__name__}: {e})")
    PC.PHASES.stop_heartbeat()
    PC.PHASES.report_close(lambda s: emit("command", s), CLOSE_AIM_SECONDS,
                           CLOSE_ALARM_SECONDS)
    emit("circle", f"\nclosed. transcript: {path}")
    return circle_failures_report()


def circle_spend_report_write(ot: str, live: bool) -> "pathlib.Path | None":
    """work/logs/spend_<OT>.json — WHAT THIS CIRCLE COST, per provider and
    model. 2026-08-28, the operator: "provider/model costs should be
    independently tracked and inspectable".

    NOTHING KEPT IT BEFORE. METER was read at four sites in this file, every
    one of them an emit to the console, and close_<OT>.json carries the
    transcript, the verifier result and each part's size and sha256 — no
    usage, no cost. Every circle's spend was printed once and lost, which is
    why "what does the inter-circle half actually cost" could not be answered
    from the record at all.

    WRITTEN HERE BECAUSE THE METER LIVES HERE. circle_close_verify.py writes the
    close report from a SEPARATE PROCESS, shelled out to, and has no access
    to this process's meter — so the two records stay separate rather than
    one pretending to hold the other's facts.

    AFTER inter_circle, deliberately: the dreaming, synthesis and
    distillation calls all meter through the same METER since stage 1, so a
    report written before them would record the circle and silently omit the
    half this exists to measure.

    THE RATES TRAVEL WITH THE ROWS (Meter.rows()), so a later price change
    cannot reprice history — the 2026-09-01 rise is exactly the event that
    would otherwise quietly rewrite what every past circle "cost".

    THE PHASES RIDE THIS FILE (2026-08-30): PHASES.snapshot() adds a
    `phases` list — wall-clock per named phase, waiting_on_self separated
    out — plus `close_seconds` against `close_aim_seconds`. Spend and time
    are the same question, "what did this circle cost", so they share the
    one record rather than earning a second file about the same close. One
    span is later than this write, close.delta_report; the heartbeat still
    reports it, the file just cannot hold it."""
    if not live:
        return None                    # a sandbox circle spends nothing real
    try:
        import json
        from atomic_write import record_atomic_write     # local, as elsewhere here
        payload = {"open_time": ot,
                   "written_at": datetime.datetime.now().isoformat(timespec="seconds"),
                   "close_aim_seconds": CLOSE_AIM_SECONDS,
                   **PC.PHASES.snapshot(),
                   **METER.snapshot()}
        dest = ROOT / "work" / "logs" / f"spend_{ot}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        record_atomic_write(dest, json.dumps(payload, indent=2) + "\n")
        emit("command", f"  spend recorded: {dest.name}")
        return dest
    except Exception as e:                                     # noqa: BLE001
        # FAILS OPEN. A circle's record is the transcript and the short_terms;
        # losing the accounting must never fail a close that otherwise held.
        emit("command", f"  spend report skipped ({type(e).__name__}: {e})")
        return None


def circle_failures_report() -> int:
    """Exit 0 only when the circle produced a complete record. Anything in the
    record — a truncated statement, an unwritten short_term, a non-zero verifier —
    is a data problem that must be visible to whatever ran this script."""
    if not FAILURES:
        return 0
    emit("command", f"\n{'=' * 68}")
    emit("command", f"  {len(FAILURES)} DATA FAILURE(S) THIS CIRCLE — record is incomplete:")
    for f in FAILURES:
        emit("command", f"    - {f}")
    # "See CLAUDE.md" named a file that never ships — 2026-09-09. The repair for
    # what actually failed is printed below this line anyway, which is the thing
    # a reader needs; the pointer was to this tree's own operating notes.
    emit("command", "  Resolve before the next circle opens.")
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
        # THE TWO PHASE-2 SHAPES NEED OPPOSITE REPAIRS, 2026-08-30 (the lab
        # close of 2026-08-29_2359 read the wrong one off this banner). A
        # failure BEFORE Transaction.commit staged nothing and the re-run is
        # clean by construction (R168); one AFTER it left the live tree
        # updated and uncommitted, and a re-run would DREAM AGAIN on top of
        # it. The report's own rerun_safe field says which this was; a
        # report without one (or unreadable) gets no asserted repair at all.
        rerun = None
        try:
            import json as _json
            rep_ = _json.loads(
                (ROOT / "work" / "logs" / f"dream_error_{ot_}.json")
                .read_text(encoding="utf-8"))
            rerun = rep_.get("rerun_safe")
        except Exception:
            pass
        if rerun is True:
            emit("command", f"  the repair is: python coordinator/"
                            f"inter_circle.py --ot {ot_} --live  (nothing "
                            f"was written by the failed run; see the report "
                            f"it names)")
        elif rerun is False:
            emit("command", f"  DO NOT re-run inter_circle for {ot_} — "
                            f"dreaming already landed in the live tree, "
                            f"uncommitted. The report above carries the "
                            f"by-hand commit repair.")
        else:
            emit("command", f"  the repair depends on which step failed — "
                            f"read work/logs/dream_error_{ot_}.json before "
                            f"acting; a partial phase 2 must NOT be re-run.")
    emit("command", f"{'=' * 68}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
