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
    _real_print(text, **kwargs)


def read_line(prompt: str = "", channel: str = "command",
              prefill: str = "") -> str:
    # `channel` is ignored here, exactly as `emit`'s is: a standalone run
    # has one terminal and nothing to route between. It exists for the
    # dual-pane adapter, which routes the prompt AND the answer by it.
    #
    # THE DEFAULT IS "command" BECAUSE IT FAILS SAFE (R221, 2026-08-17).
    # docs/BNF.md line 105 rules RATIFICATION_DIALOG — and COMMAND, and
    # CP_PROTOCOL — never visible to the circle; a call site added later
    # without thought therefore lands in the private lane rather than
    # leaking a Coordinator prompt into the room's pane. Only three sites
    # in this project are circle lane, and each says so explicitly:
    # working_set_manager.py's working-set question (circle.py's until
    # 2026-09-03, stage 10) and circle.py's topic and CONSOLE_NAME
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
    # the adapter's signature, not this one, decides their lane.
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
