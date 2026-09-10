#!/usr/bin/env python3
"""
seam.py — the coordinator's I/O seams, and its failure record. Phase 1
step 1 of the coordinator partitioning (2026-08-16); until then both
lived at the top of circle.py.

THE SEAM CONTRACT (docs/dual_pane_integration.md §1). A standalone run
(no circling.py involved) must behave exactly as before these seams
existed: `emit`'s default body is exactly `print(text)`, channel
ignored; `read_line`'s is exactly `input(prompt)`, channel ignored the
same way (it gained one 2026-08-17, R221 — see its own comment for why
the default is "command"). `circling.py`'s
CircleEngine adapter is the only production code that ever rebinds
them, at runtime, to push onto queues instead; the coordinator test
harnesses rebind them the same way to capture output and script input.

REBIND THIS MODULE'S ATTRIBUTES, NEVER COPIES OF THEM. Every consumer
reaches these as `seam.emit(...)` / `seam.read_line(...)` — circle.py
does it through two thin delegating wrappers so its ~170 existing call
sites read unchanged, and every extracted module does it directly.
`from seam import emit` would copy the function object at import time
and go stale the moment circling.py or a test rebinds `seam.emit` —
that module's output would then leak to the real stdout, invisibly to
every coordinator-side check. Same trap, same rule as `circle.dev_mode`
(see the comment beside that flag in circle.py).
"""

from __future__ import annotations

import time

# WHEN SOMETHING WAS LAST PRINTED, and whether a progress line is open on the
# console right now. Module state, read through the two `system_*` functions
# below — never imported by value, for the same reason emit and read_line are
# not: a copy taken at import time freezes an answer that changes every line.
_last_output: float = time.monotonic()
_progress_open: bool = False

# IS THERE A COMMAND PANE IN THIS RUN? False is the standalone answer: one
# terminal, one prompt, nothing to route between — the same fact `emit`'s
# "state" branch below already acts on ("A standalone terminal has no panes
# to inform"), named here so a caller can ASK it rather than infer it.
# ui/circling.py sets it True where it rebinds the two seams, and restores it
# with them. THE TICKER GETS IT TRANSITIVELY, not by setting it itself: its
# bridge drives a CircleEngine and that engine's start() is what sets it, so a
# grep of ui/ticker/ for this name finds nothing and the fact still holds.
#
# REBIND IT, NEVER COPY IT — the module rule above applies to this exactly as
# it does to emit and read_line. `seam.COMMAND_PANE`, never
# `from seam import COMMAND_PANE`, which would freeze the standalone answer
# into any module imported before the adapter starts.
#
# THE ROOM'S HELP IS THE READER (help_system.circle_pane_help). A standalone
# terminal must not be told that a verb "belongs to the command pane" or that
# something answers "at the cmd> prompt" — there is no such pane and no such
# prompt in that run. It is deliberately the SMALLEST question that serves
# all three flavors: not "which window", which would need a new vocabulary and
# a third value the day a fourth flavor arrives, but the one property the help
# actually branches on. Both other flavors answer True — the two-pane UI has
# its cmd> pane and the Ticker its cmd> tab.
COMMAND_PANE = False

# Aliased to the real builtins here (not called as `print(...)` below)
# so a source-level rename sweep of every OTHER `print`/`input` call
# site can never catch these two definitions themselves.
_real_print = print
_real_input = input


def emit(channel: str, text: str = "", **kwargs) -> None:
    # THE "state" CHANNEL IS A UI SIGNAL, NOT CONSOLE TEXT — 2026-08-21,
    # from the lab circle 2026-08-21_1139's close. circle.py's /close branch
    # reports where its close is ("close-confirm-pending" while it waits for
    # the second /close, "closing" once it proceeds) so the dual pane can
    # hand the window over at the right moment and disable cmd> meanwhile.
    # A standalone terminal has no panes to inform: the default prints
    # nothing for it, and every other channel prints exactly as before.
    #
    # "redact_view" JOINED IT 2026-08-31 — the redact_view setting's live
    # toggle signal (ui/circling.py's Pane.set_redact()). A second UI-signal
    # channel rather than folding this into "state": CircleEngine._emit()
    # stores close_state = text for every "state" emission, and routing
    # "on"/"off" through it would corrupt close-state tracking.
    if channel in ("state", "redact_view"):
        return
    # A PROGRESS LINE IS CLOSED BY THE NEXT REAL OUTPUT, wherever that output
    # comes from. The dots are written with end="" so they grow on one line;
    # something has to end that line, and the only honest moment is when the
    # thing being waited on finally says something. Doing it here means no
    # caller has to remember, which is the whole reason the wait was silent in
    # the first place.
    system_output_mark()
    global _progress_open
    if _progress_open:
        _real_print("")
        _progress_open = False
    _real_print(text, **kwargs)


def system_output_mark() -> None:
    """Something reached a reader just now.

    A SEPARATE FUNCTION BECAUSE emit() IS REPLACED, NOT WRAPPED. ui/circling.py
    swaps `seam.emit` for its own `_emit`, which queues a line for a pane and
    never runs the body above — so a stamp set only inside that body is set
    only in a standalone run. It was, for a day: in both windowed flavors
    system_output_quiet_seconds() grew forever, the beat's "still talking is
    not waiting" guard never fired, and a pane got a line every three seconds
    for the whole circle however much the program was saying.

    So the stamp is a CALL any emit implementation makes, and the two that
    replace this one make it. Adding a third means calling this; the module's
    own rule — rebind the attribute, never copy it — is what makes that
    reachable from an adapter."""
    global _last_output
    _last_output = time.monotonic()


def system_output_quiet_seconds() -> float:
    """Seconds since anything was last PRINTED — the measure the >3s rule is
    actually about.

    A HEARTBEAT ON A TIMER IS NOT THE SAME RULE. `phase_clock`'s beat fires
    every `interval` whether or not the program has spoken in between, so on
    its own it marks elapsed time rather than SILENCE. The operator's rule is
    *"a measured delay of over 3 seconds between user input and any output --
    or between any output and another output"*, which is a gap since the last
    line, and this is how the beat asks about one.

    A TICK DELIBERATELY DOES NOT RESET IT. If a dot counted as output the gap
    would restart on every mark and the second dot would never come."""
    return time.monotonic() - _last_output


def system_progress_tick() -> None:
    """One mark on the current line, for a wait that has gone on too long.

    THE DOT ONLY CONCATENATES IN A TERMINAL, and that is not a defect to fix
    here. `end=""`/`flush=True` are honoured by the standalone print below;
    ui/circling.py's CircleEngine._emit drops both by design, because they have
    no meaning for a line-based pane's scrollback. So this is armed for the
    window that has no clock of its own and no other way to show a wait; the
    two windowed flavors have their own loops and their own indicators."""
    global _progress_open
    _progress_open = True
    _real_print(".", end="", flush=True)


def read_line(prompt: str = "", channel: str = "command",
              prefill: str = "") -> str:
    # `channel` is ignored here, exactly as `emit`'s is: a standalone run
    # has one terminal and nothing to route between. It exists for the
    # dual-pane adapter, which routes the prompt AND the answer by it.
    #
    # THE DEFAULT IS "command" BECAUSE IT FAILS SAFE (R221, 2026-08-17).
    # docs/BNF.md line 105 rules RATIFICATION_DIALOG — and COMMAND, and
    # CP_PROTOCOL — never visible to the circle; a call site added later
    # without thought therefore lands in the private channel rather than
    # leaking a Coordinator prompt into the room's pane. Only three sites
    # in this project are circle channel, and each says so explicitly:
    # working_set_manager.py's working-set question (circle.py's until
    # 2026-09-03, stage 10), circle_open.py's topic (circle.py's until
    # 2026-09-09, when the open step left main()) and circle.py's CONSOLE_NAME
    # speaking prompts. test_seam.py and bnf_conformance.py both count.
    #
    # `prefill` IS AN AFFORDANCE, NOT A CONTRACT, added 2026-08-20 for
    # finding 2. It asks the reader to open with `prefill` ALREADY TYPED and
    # the cursor at its end, so a rejected list can come back MINUS the
    # invalid ids and be corrected rather than retyped. A plain terminal
    # cannot do that — `input()` has no way to seed its line — so the
    # default IGNORES IT, and every caller that offers a prefill must also
    # say the same thing in words on the channel. circling's adapter is
    # the one reader that honours it.
    #
    # A REBOUND read_line's OWN default is what applies to bare calls —
    # extracted modules call `seam.read_line(prompt)` with no channel, so
    # the adapter's signature, not this one, decides their channel.
    return _real_input(prompt)


# ------------------------------------------------------------------ failure record
# Every entry here means the current circle produced an incomplete or
# damaged record. circle.main() exits non-zero while this is non-empty,
# so an unattended run can never look clean when it is not. Nothing
# anywhere may swallow a data failure.
#
# LIVES HERE, NOT IN circle.py, since 2026-08-16: extracted modules
# (transcript_store.py's verifier and commit paths first) must be able
# to report a data failure without importing the orchestrator. The list
# is only ever MUTATED IN PLACE — appended by fail(), read by
# circle.circle_failures_report() — never reassigned, which is what makes
# circle.py's `from seam import FAILURES` a safe alias to this same
# object.
FAILURES: list[str] = []


def fail(msg: str) -> None:
    # Bare `emit`, deliberately: the module-global lookup means a
    # rebound seam.emit carries this warning to the pane/capture too.
    FAILURES.append(msg)
    emit("command", f"\n  !! {msg}\n")
