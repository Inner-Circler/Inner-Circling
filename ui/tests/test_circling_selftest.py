#!/usr/bin/env python3
"""
test_circling_selftest.py — the two-pane UI engine's self-test, headless (no TTY).

    python ui/tests/test_circling_selftest.py
    python ui/circling.py --selftest            the same suite, run through the program's own flag

WAS `self_test()` INSIDE ui/circling.py from the file's first day until 2026-09-03 (B99 stage 15,
R435: a suite lives in tests/, beside test_circling.py and test_circle_engine.py). The body is the
one that lived there — its 339 checks unchanged — read through `C.`: every name it took bare from
circling's own namespace is `C.<name>` now, the six stdlib modules are imported here, and the one
`global COLOR` became reads and writes of `C.COLOR` (COLOR is the write-time tint main() arms;
the checks below arm and disarm the PROGRAM's copy, not this file's). `vars(C)` is what
`globals()` was: the program's namespace, where main_loop is faked and C._WIN_SCAN_EXT is looked for.

The program's `--selftest` flag still runs this file, because the shipped bundle, install.py and
the scaffold README all say `ui/circling.py --selftest`; whether the suite itself ships is an
open decision (NEXT.md).

Exit 0 on all PASS; the tally line `SELF-TEST: ...` is what install.py reads.
"""

from __future__ import annotations

import io
import pathlib
import queue
import re
import subprocess
import sys
import threading
import time

UI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(UI))
sys.path.insert(0, str(UI.parent / "coordinator"))
sys.path.insert(0, str(UI.parent / "memory"))            # issue_schema, for _nodes()

import circling as C  # noqa: E402

# The test's own placeholder for a speaking part. Never a real part Tag: this
# file ships, and a recipient should not meet another person's parts in it.
PLACEHOLDER_PART = "Alpha"


def self_test() -> int:
    failures: list[str] = []
    total = [0]

    def check(label: str, cond: bool, detail: str = "") -> None:
        # `detail` prints ON FAILURE ONLY, and exists because a FAIL here is
        # often read on a machine nobody can reproduce on — a fresh install, a
        # platform this tree has never run. A label alone says which claim
        # broke; the detail says what was actually seen, which is the half a
        # report from elsewhere cannot supply. Same convention as the
        # coordinator suites'.
        total[0] += 1
        print(f"  {'PASS' if cond else 'FAIL'}  {label}"
              + (f"\n          {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(label)

    # FOUR CHECKS BELOW ASSERT AGAINST THIS INSTALLATION'S OWN CONTENT — a
    # practice carrying a BP- id, the issue node n0002 — and a fresh
    # install has neither. They were written in a populated tree and had
    # only ever been run in one; measured 2026-08-24 against a freshly
    # built bundle, four of the 276 FAILED there, every one for want of
    # data rather than for a defect. A shipped self-test that fails out of
    # the box teaches its reader to ignore it.
    #
    # A SKIP IS NOT A PASS AND IS NOT COUNTED AS ONE. It names the datum
    # that was missing, so a check that quietly stops running in a
    # POPULATED tree — the real hazard — shows up as a skip nobody
    # expected rather than as a green line. Same rule the hook's syntax
    # gate uses when `sh` is absent: the validator's absence is not
    # evidence of health.
    skipped: list[str] = []

    def skip(label: str, why: str) -> None:
        skipped.append(label)
        print(f"  skip  {label}")
        print(f"          — {why}")

    def _nodes() -> list:
        """Every issue node this installation holds, through the one
        reader of issues/ rather than a glob -- a filename there carries
        the STATUS in its prefix, so the directory listing is not the
        question anyone means to ask."""
        try:
            import issue_schema as _IS
            return _IS.issue_nodes_read()
        except Exception:                                    # noqa: BLE001
            return []

    def _has_issue(nid: str) -> bool:
        try:
            import issue_schema as _IS
            return any(_IS.issue_id_read(q.stem) == nid for q in _nodes())
        except Exception:                                    # noqa: BLE001
            return False

    def _has_practice() -> bool:
        try:
            import practice_manager as _PM
            return bool(_PM.practice_read())
        except Exception:                                    # noqa: BLE001
            return False

    state = C.AppState(circle_height=8, command_height=4)

    for ch in "hello circle\r":
        state.handle_key(ch)
    check("circle input submits as [You]: line",
          state.circle.lines == ["[You]: hello circle"])
    check("command pane untouched by a circle submit",
          state.command.lines == [])

    effect = state.handle_key("\t")
    check("Tab returns 'focus'", effect == "focus")
    check("focus is now command", state.focus == "command")

    # Start typing a command, but do NOT submit yet — this is the
    # in-progress-input-in-the-inactive-pane scenario the whole design
    # exists to protect.
    for ch in "issue issue-relationship-":
        state.handle_key(ch)
    check("command input buffer holds the partial line",
          state.command.input_buf == "issue issue-relationship-")

    # A part's line arrives for the OTHER pane while the above is
    # mid-typed. This is what ui_main_loop's drain does with a CircleEngine's
    # circle-channel item; here it's done directly since self_test has no
    # event loop. PLACEHOLDER_PART is the test's own name, never a real part
    # Tag: this file ships, and a recipient should not meet another person's
    # parts in it (audit-register.md #1, 2026-09-08).
    state.circle.append(f"[{PLACEHOLDER_PART}]: an independent line, interleaved")
    check("circle received the interleaved line",
          state.circle.lines[-1] == f"[{PLACEHOLDER_PART}]: an independent line, interleaved")
    check("focus did NOT move because the OTHER pane received output",
          state.focus == "command")
    check("the in-progress command buffer survived the interleaved line",
          state.command.input_buf == "issue issue-relationship-")

    for ch in "add\r":
        state.handle_key(ch)
    check("command submit is logged as a stub, not executed",
          state.command.lines[0] == "> issue issue-relationship-add"
          and "stub" in state.command.lines[1])

    effect = state.handle_key("\t")
    check("Tab back to circle", state.focus == "circle" and effect == "focus")

    # --- CircleEngine.submit_command() — the three wired verbs ----------
    # Unit-level, no real circle.py thread started: `circle` is imported
    # eagerly in __init__ now (not start()), specifically so 'help' works
    # on a bare, never-started CircleEngine — proving that here, not just
    # asserting it in a comment.
    eng = C.CircleEngine(queue.Queue())
    check("'quit' returns the quit signal, case-insensitively",
          eng.submit_command("Quit") == "quit")

    # B57(1): the consumption handshake, and the two orderings everything
    # built on it depends on. Cheap to pin, and impossible to notice broken —
    # a handshake that fires early does not fail, it misattributes output.
    check("line_taken rests SET, so a reader that never waits is unaffected",
          eng.line_taken.is_set())
    eng.submit_circle("something")
    check("submit_circle CLEARS it — the line is pending, not taken",
          not eng.line_taken.is_set())
    eng.circle_in.get_nowait()
    # A COMMAND-channel read, completed for real: pre-feed command_in so
    # _read_line's `q.get()` returns at once rather than blocking here.
    eng.command_in.put("answered")
    eng._read_line(prompt="", channel="command")
    check("a COMMAND-channel read does NOT set it — the channel scoping holds, so "
          "a queued circle line is not reported taken by the other channel",
          not eng.line_taken.is_set())
    eng.circle_in.put("answered")
    eng._read_line(prompt="", channel="circle")
    check("a CIRCLE-channel read DOES set it", eng.line_taken.is_set())
    check("...and waiting_for_input was already False when it did — a waiter "
          "released by the event never sees the stale-True window",
          not eng.waiting_for_input)
    eng.out_queue.queue.clear()

    # A RUNNING ENGINE IS THE PRECONDITION for forwarding, and since
    # 2026-08-20 the branch checks it. `_running()` is `_thread is not None
    # and not finished` — a stand-in object is enough here; start() would
    # run a real circle.
    eng._thread = object()
    # ...AND SINCE 2026-08-21 SO IS THE Self> LOOP HAVING BEEN REACHED. A
    # running engine that has not got there is OPENING — busy in the API
    # check or the pre-warm, or parked on the working-set / topic question
    # — and a forwarded line is consumed as that question's ANSWER: the
    # lab's 2026-08-21 findings were fourteen of those ("not in the graph:
    # /issue-list", "/status", "/dev", "/help, object_classes"). Busy first:
    check("running but not yet at the Self> loop, nothing pending: the "
          "phase reads 'opening'", eng._phase() == "opening")
    # 'abort' IS THE ROOM'S VERB SINCE 2026-08-31 (R414):
    # it ends the CIRCLE, so it sits beside /close, and cmd> refuses it in
    # EVERY phase the way it refuses /close — the idle, opening and
    # dead-engine guards its own local branch carried went with the branch.
    eng.submit_command("abort")
    check("'abort' at cmd> while the circle is still OPENING forwards nothing",
          eng.circle_in.empty())
    _t = eng.out_queue.get_nowait()[1]
    check("...and is refused as circle-pane speech, the list naming /abort "
          "beside /close", "circle-pane speech" in _t and "/abort" in _t
          and "/close" in _t)
    # Parked on the working-set question: refusals name it, and the verbs
    # that need no transcript RUN there.
    eng.waiting_for_input, eng.waiting_for_channel = True, "circle"
    eng.pending_prompt = "CIRCLE issues (blank = all, 'none', '?'):"
    check("parked on a circle-channel question before the loop: 'opening-q'",
          eng._phase() == "opening-q")
    eng.submit_command("abort")
    check("'abort' parked on the working-set question forwards nothing "
          "either", eng.circle_in.empty())
    check("...and is the same circle-pane refusal, not a phase message",
          "circle-pane speech" in eng.out_queue.get_nowait()[1])
    if _nodes():
        eng.submit_command("issue-list")
        check("a no-transcript verb (issue-list) typed while parked on the "
              "working-set question RUNS — the operator typed it to answer "
              "that very question — and nothing reaches circle_in",
              eng.circle_in.empty()
              and "live" in eng.out_queue.get_nowait()[1])
    else:
        skip("a no-transcript verb (issue-list) typed while parked on the "
             "working-set question RUNS — the operator typed it to answer "
             "that very question — and nothing reaches circle_in",
             "issues/ is empty — the listing has no 'live' line to find, "
             "which is correct on an install that has opened no issue yet")
    eng.out_queue.queue.clear()                     # the listing's rows
    eng.submit_command("issue-evidence-list")
    check("a verb that needs the open circle (issue-evidence-list) is refused "
          "there, naming the question the circle is asking",
          eng.circle_in.empty()
          and "CIRCLE issues" in eng.out_queue.get_nowait()[1])
    eng.waiting_for_input, eng.pending_prompt = False, ""
    eng.loop_reached = True
    check("once the Self> loop has been reached the phase is 'loop'",
          eng._phase() == "loop")
    eng.line_taken.set()
    eng.submit_command("abort")
    check("'abort' at cmd> with the Self> loop reached forwards NOTHING — "
          "the room owns the circle's end (R414)",
          eng.circle_in.empty() and eng.line_taken.is_set())
    check("...and is refused as circle-pane speech there too",
          "circle-pane speech" in eng.out_queue.get_nowait()[1])
    check("/abort typed in the CIRCLE pane passes the pane guard to "
          "circle.py's loop, whose two-step confirmation (R173) is unchanged",
          eng._CS.command_pane_verb_read("/abort") is None
          and eng._CS.verb_class("/abort") == "circle")
    check("/quit typed in the circle pane is refused by name — the "
          "window's verb, cmd> only",
          eng._CS.command_pane_verb_read("/quit") == "/quit"
          and eng._CS.verb_class("/quit") == "window")
    check("a bare word is speech in the room — 'quit' and 'close' without "
          "a slash classify as nothing",
          eng._CS.verb_class("quit") is None
          and eng._CS.verb_class("close") is None)

    # THE CRASH CASE, 2026-08-20, kept for what it still proves: after the
    # engine died, cmd> answers rather than queueing onto a channel nothing
    # drains — the answer is now the same circle-pane refusal, and the verb
    # that DOES end the window is named by the pane's own help.
    eng.finished.set()
    eng.out_queue.queue.clear()
    eng.submit_command("abort")
    check("'abort' after the engine ENDED forwards NOTHING — nothing drains "
          "circle_in once the thread is gone", eng.circle_in.empty())
    channel, text = eng.out_queue.get_nowait()
    check("...and is answered, not queued into the void",
          channel == "command" and "circle-pane speech" in text)
    eng.finished.clear()
    eng._thread = None
    eng.out_queue.queue.clear()
    eng.submit_command("abort")
    check("'abort' before any circle was started forwards nothing either",
          eng.circle_in.empty())
    check("...with the same refusal — one answer in every phase",
          "circle-pane speech" in eng.out_queue.get_nowait()[1])
    eng.out_queue.queue.clear()

    # THE PANE'S OWN VERBS ARE NAMED SOMEWHERE A READER WILL FIND THEM.
    # `quit` has worked since this dispatcher was written and appeared in
    # NO help output — /help renders circle.py's COMMANDS table, and a
    # pane-local verb cannot be a row in it.
    check("the local verb list names quit", "quit" in eng.local_verb_text())
    check("...and every verb the dispatcher actually handles locally",
          all(v in eng.local_verb_text()
              for v, _ in eng.LOCAL_VERBS))

    result = eng.submit_command("help")
    channel, text = eng.out_queue.get_nowait()
    check("'help' works before start() was ever called — no live circle needed",
          channel == "command" and "/help" in text and "quit" in text)
    check("...and cmd> help lists no circle-pane verb — each pane's help "
          "shows what that pane operates (R414)",
          not any(f"  {v} " in text or f"  {v}\xa0" in text
                  for v in ("/abort", "/close", "/round", "/pass")))
    check("'help' returns the 'help' signal (drives the pane resize)",
          result == "help")

    eng.submit_command("bogus")
    ch_j, txt_j = eng.out_queue.get_nowait()
    check("an unrecognized word is JUNK: the line that names what was typed, "
          "then a pointer to help — and NOT the listing, which is longer "
          "than the pane and scrolled the diagnosis out of sight "
          "(2026-08-24; R285 had ruled the listing)",
          ch_j == "command"
          and txt_j == "  not a command: bogus\n  See help")

    eng.submit_command("status")
    check("'status' with NO engine running refuses with a reason instead "
          "of queueing /status on a circle_in nothing drains (2026-08-21 — "
          "this branch had no guard at all)",
          eng.circle_in.empty()
          and "needs a circle open" in eng.out_queue.get_nowait()[1])
    eng._thread = object()                 # running; loop_reached is True
    eng.submit_command("status")
    check("'status' forwards /status to circle_in once a circle is at its "
          "Self> loop — the command was never reachable from THIS pane "
          "before, despite /status's own output landing on the command "
          "channel",
          eng.circle_in.get_nowait() == "/status")
    eng.loop_reached = False               # the same engine, still OPENING
    eng.submit_command("status")
    check("'status' while the circle is still opening forwards nothing "
          "and says so — on 2026-08-21 it became the working set",
          eng.circle_in.empty()
          and "still opening" in eng.out_queue.get_nowait()[1])
    eng.loop_reached = True
    eng._thread = None

    # --- 'dev' — RULED 2026-08-13: one module-global dev_mode
    # (command_surface.py since phase 2 stage 0; circle.py before),
    # reachable and toggleable whether or not a circle is running. Forwards while running (same mechanism as abort/status
    # above — real, tested via `_running()`, not a live thread, matching
    # this section's own "bare engine, no live circle.py needed" style);
    # flips the attribute directly when nothing is running to forward
    # into, since an unread queue item would otherwise toggle nothing. --
    check("bare (never-started) engine reads as not running",
          not eng._running())
    before = eng._CS.dev_mode
    eng.submit_command("dev")
    after = eng._CS.dev_mode
    check("'dev' with no engine running flips command_surface.dev_mode "
          "directly",
          after == (not before))
    channel, text = eng.out_queue.get_nowait()
    check("...and acknowledges on the command channel",
          channel == "command"
          and text.strip() == f"dev mode: {'on' if after else 'off'}")
    eng._CS.dev_mode = before  # restore — this is the real shared attribute

    eng._thread = threading.current_thread()  # fake "running", no real session
    check("with a thread set and not finished, engine now reads as running",
          eng._running())
    eng.submit_command("dev")
    # DIRECT IN EVERY PHASE since 2026-08-21 (R286). This
    # asserted a forward of "/dev" onto circle_in while running; the loop's
    # /dev handler that forward fed is gone, and dev is cmd>-only.
    check("'dev' while running at the Self> loop flips dev_mode DIRECTLY and "
          "forwards nothing — the loop has no /dev any more",
          eng.circle_in.empty() and eng._CS.dev_mode == (not before))
    eng.out_queue.get_nowait()             # its "dev mode: ..." ack
    eng._CS.dev_mode = before              # restore the shared attribute
    eng.loop_reached = False               # still OPENING: flip directly
    eng.submit_command("dev")
    check("'dev' while the circle is still opening flips dev_mode DIRECTLY "
          "rather than forwarding — forwarded, '/dev' became the working "
          "set on 2026-08-21",
          eng.circle_in.empty() and eng._CS.dev_mode == (not before))
    eng.out_queue.get_nowait()             # its "dev mode: ..." ack
    eng._CS.dev_mode = before              # restore the shared attribute
    eng.loop_reached = True
    eng._thread = None        # restore

    # --- 'resume <open_time>' — same function as circle.py's --resume,
    # from the command pane, without quitting and relaunching. the operator:
    # "when an unclosed circle is reported, support 'resume' in the
    # command pane, same function as --resume." -------------------------
    result = eng.submit_command("resume 2026-08-10_2112")
    check("'resume <open_time>' declines whatever read_line is pending — on "
          "COMMAND_IN since R221, because the read it answers (circle.py's "
          "\"type 'yes' to open a NEW circle\") is command channel; on circle_in "
          "it would sit unread and every resume would fail its 5s wait",
          eng.command_in.get_nowait() == "no")
    check("...and nothing was put on circle_in by that decline",
          eng.circle_in.empty())
    check("'resume <open_time>' acknowledges on the command channel",
          eng.out_queue.get_nowait() == ("command", "  resuming circle_2026-08-10_2112 —"))
    check("'resume <open_time>' returns the resume signal for AppState/"
          "main_loop to act on",
          result == "resume:2026-08-10_2112")

    # BARE 'resume' auto-detects from circle_state.circle_open_read() — the
    # SAME source circle.py's own "N circle(s) may still be OPEN" warning
    # is built from. the operator, after the first cut required an explicit
    # open_time: that requirement "makes no sense" from the command pane
    # (unlike the CLI flag, where you already know the OT you meant to
    # type) — "resume the circle reported." Mocked so this doesn't depend
    # on whatever is actually sitting in work/sandbox/circles/ at
    # test time. ----------------------------------------------------------
    import unittest.mock as _mock
    import circle_state as _CS

    def _candidate(ot: str) -> dict:
        return {"path": _CS.SANDBOX / f"circle_{ot}.md", "ot": ot,
                "quiet": 480.0, "why": "no close report and last written 8 min ago"}

    with _mock.patch("circle_state.circle_open_read", return_value=[]):
        result = eng.submit_command("resume")
        check("bare 'resume' with nothing open says so",
              result is None
              and eng.out_queue.get_nowait() == ("command", "  no open circle to resume"))

    with _mock.patch("circle_state.circle_open_read",
                      return_value=[_candidate("2026-08-10_2112")]):
        result = eng.submit_command("resume")
        check("bare 'resume' auto-detects the single open sandbox circle",
              result == "resume:2026-08-10_2112")
        check("the auto-detected resume still declines the pending read_line, "
              "on command_in — same channel as the explicit form above",
              eng.command_in.get_nowait() == "no")
        eng.out_queue.get_nowait()   # the acknowledgement, already covered above

    with _mock.patch("circle_state.circle_open_read",
                      return_value=[_candidate("2026-08-10_2112"),
                                    _candidate("2026-08-06_1012")]):
        result = eng.submit_command("resume")
        channel, text = eng.out_queue.get_nowait()
        check("bare 'resume' with MULTIPLE open circles refuses to guess",
              result is None and "2 open circles" in text
              and "2026-08-10_2112" in text and "2026-08-06_1012" in text)

    result = eng.submit_command("resume not-a-real-open-time")
    check("a malformed open_time is refused the same way",
          result is None)
    eng.out_queue.get_nowait()  # the explanatory message

    check("_strip_resume drops an existing --resume pair",
          C._strip_resume(["--parts", "alpha,beta", "--resume", "2026-08-01_0900"])
          == ["--parts", "alpha,beta"])
    check("_strip_resume is a no-op when there's nothing to strip",
          C._strip_resume(["--parts", "child"]) == ["--parts", "child"])

    # End-to-end through AppState._submit, proving 'quit' actually stops
    # the run loop rather than just returning the right string in isolation.
    eng2 = C.CircleEngine(queue.Queue())
    s2 = C.AppState(4, 4, backend=eng2)
    s2.focus = "command"
    s2._submit(s2.command, "quit")
    check("'quit' submitted in the command pane sets state.running False",
          s2.running is False)

    # --- the OPENING refusal, audit-register.md #13 ------------------
    # _opening_refusal() and its only call site had ZERO references across ui/tests/ and
    # were executed by nothing. What they guard is stated at the call site: without the
    # refusal, _dispatch_no_circle() runs instead and rebinds seam.read_line to the no-block
    # stub for the duration of the call, so "an engine thread that reaches a real question
    # inside that window would be handed '' for an answer." The operator had no way to see
    # that on 2026-08-21 — which is the whole reason the sentence names the question and the
    # pane it is waiting in.
    #
    # `opening` is the LAST arm of _phase(): running, the Self> loop not yet reached, and not
    # parked on a circle-channel question. Set exactly that, so the branch is reached the way
    # the engine reaches it rather than by calling the helper directly.
    eng_op = C.CircleEngine(queue.Queue())
    eng_op._thread = type("T", (), {"is_alive": lambda self: True})()
    eng_op.loop_reached = False
    eng_op.waiting_for_input = False
    eng_op.pending_prompt = "working set (issue ids, or 'none')"
    check("_phase() reports 'opening' while the API check and pre-warm run",
          eng_op._phase() == "opening")
    eng_op.out_queue = queue.Queue()
    ret = eng_op.submit_command("status")
    said = eng_op.out_queue.get_nowait()[1] if not eng_op.out_queue.empty() else ""
    check("a command typed while opening is REFUSED, not dispatched", ret is None)
    check("...and the refusal names the question the circle is waiting on",
          "working set" in said)
    check("...and the pane it is waiting in",
          "circle pane" in said)
    check("...and what was refused", "status" in said)
    eng_op.pending_prompt = None
    eng_op.out_queue = queue.Queue()
    eng_op.submit_command("status")
    said_bare = eng_op.out_queue.get_nowait()[1] if not eng_op.out_queue.empty() else ""
    check("with no pending prompt it still refuses, without inventing a question",
          "still opening" in said_bare and "asking" not in said_bare)

    # --- help/revert pane-resize signal -----------------------------
    # the operator: "If help is invoked, resize the panes to 1/5th and 4/5ths.
    # When a circle is started or continued with a user circle entry,
    # revert the pane sizes."
    eng3 = C.CircleEngine(queue.Queue())
    s3 = C.AppState(4, 4, backend=eng3)
    s3.focus = "command"
    sig = s3._submit(s3.command, "help")
    check("'help' in the command pane signals help_resize",
          sig == "help_resize" and s3.help_mode is True)

    s3.focus = "circle"
    sig = s3._submit(s3.circle, "a real statement")
    # D55(2), RULED 2026-08-20: a command-pane verb standing alone in
    # circle dialog is a NO-OP. It used to be forwarded verbatim into
    # circle.py's one Self> loop, which cannot tell which pane sent it —
    # so with dev on, `/practice-add ...` typed into the ROOM wrote a
    # practice. docs/BNF.md defines COMMAND as cmd>-only.
    print("\n  a command-pane verb standing alone in the room is a no-op")
    s_np = C.AppState(6, 6)
    s_np.focus = "circle"
    before_lines = list(s_np.circle.lines)
    s_np._submit(s_np.circle, "/practice-add hold the queue")
    check("nothing was spoken — the room's scrollback is untouched",
          s_np.circle.lines == before_lines)
    check("...and the reason lands in the COMMAND pane, never the room",
          any("ignored in the room" in l for l in s_np.command.lines))
    check("...naming the verb, so a silent swallow is not what happens",
          any("/practice-add" in l for l in s_np.command.lines))
    for verb in ("/round", "/pass", "/close"):
        s_ok = C.AppState(6, 6)
        s_ok.focus = "circle"
        s_ok._submit(s_ok.circle, verb)
        # `in`, not `[-1]`: /close appends its own hand-over line after the
        # echo (finding 11), so the echo is not the last row for that one.
        check(f"{verb} is a CIRCLE-pane verb and still goes through",
              f"[You]: {verb}" in s_ok.circle.lines)
    # BARE /help PASSES THE GUARD, 2026-08-21 (R287): the room's own help
    # answers it; `/help <arg>` and `/dev` are refused like any
    # command-pane verb.
    s_h = C.AppState(6, 6)
    s_h.focus = "circle"
    s_h._submit(s_h.circle, "/help")
    check("bare /help in the room goes THROUGH to the loop (the room form "
          "answers it) — it was refused by this guard until 2026-08-21",
          s_h.circle.lines[-1] == "[You]: /help")
    s_ha = C.AppState(6, 6)
    s_ha.focus = "circle"
    s_ha._submit(s_ha.circle, "/help object_classes")
    check("/help <arg> in the room is refused and pointed at cmd>",
          "[You]: /help object_classes" not in s_ha.circle.lines
          and any("ignored in the room" in l for l in s_ha.command.lines))
    s_hd = C.AppState(6, 6)
    s_hd.focus = "circle"
    s_hd._submit(s_hd.circle, "/dev")
    check("/dev in the room is refused — cmd>-only (R286); "
          "it used to pass because it is no PANE_OF key",
          "[You]: /dev" not in s_hd.circle.lines
          and any("/dev is a command-pane verb" in l for l in s_hd.command.lines))
    s_sp = C.AppState(6, 6)
    s_sp.focus = "circle"
    s_sp._submit(s_sp.circle, "close the door behind you")
    check("a bare word that merely looks like a verb is SPEECH — no slash, "
          "no verb (the room is the opposite of cmd>, where R201 makes the "
          "slash optional)",
          s_sp.circle.lines[-1] == "[You]: close the door behind you")
    s_an = C.AppState(6, 6)
    s_an.focus = "circle"
    # `[proposed:` — the keyword R273 fixed, 2026-08-20. This fixture said
    # `[propose:` for one afternoon, which is dialog text under that
    # grammar, so the "verb INSIDE an annotation" check was exercising
    # plain speech (the UI never validates circle input, so it passed).
    s_an._submit(s_an.circle,
                 "maybe [proposed: /issue-relationship-add n0001 leads-to n0002]")
    check("a verb INSIDE an annotation still reaches the room — it stages "
          "for a ruling, which is the one way a command may be named from "
          "here (D55(2))",
          "[proposed:" in s_an.circle.lines[-1])

    check("the next circle entry reverts — signals revert_resize",
          sig == "revert_resize" and s3.help_mode is False)

    sig = s3._submit(s3.circle, "another statement")
    check("once reverted, ordinary circle entries stay plain (no signal)",
          sig is None)

    # /close HANDS THE WINDOW OVER, 2026-08-20. Everything a close prints
    # is COMMAND channel, so before this the room went quiet and the work
    # happened in the pane that was one fifth of the screen and possibly
    # scrolled away from its own live edge.
    # SINCE 2026-08-21 THE HANDOVER FOLLOWS THE COORDINATOR'S WORD, not the
    # typed text: the first /close may only SHOW the unruled proposals and
    # ask for a second, and the operator was moved to cmd> where that
    # second /close was refused. circle.py emits state "closing" when the
    # close proceeds; main_loop hands it to on_state().
    s_cl = C.AppState(6, 6)
    s_cl.focus = "circle"
    s_cl.command.append("old line")
    s_cl.command.line_up(5)                      # scrolled away from the edge
    sig_typed = s_cl._submit(s_cl.circle, "/close")
    check("a typed /close no longer moves focus by itself — it may be a "
          "question, not a close",
          s_cl.focus == "circle" and sig_typed is None)
    sig_cl = s_cl.on_state("closing")
    check("state 'closing' echoes into the ROOM",
          s_cl.circle.lines[-1] == "Closing this circle...")
    check("...then hands focus to the command pane", s_cl.focus == "command")
    check("...scrolled back to the live edge, so the close is actually seen",
          s_cl.command.scroll_top is None)
    check("...and says what the wait is for",
          s_cl.command.lines[-1]
          == "closing the circle... collecting memories, please wait...")
    check("...signalling a FULL redraw, since both pane heights follow focus",
          sig_cl == "focus")
    check("the other tokens change nothing on screen",
          s_cl.on_state("close-confirm-pending") is None
          and s_cl.on_state("") is None)
    # THE INITIALIZATION HANDOVER (R330, 2026-08-23) — the same shape as
    # "closing", in both directions: the first-run dialogs own the command
    # pane, "Starting your circle..." hands the window back.
    s_in = C.AppState(6, 6)
    s_in.focus = "circle"
    s_in.command.append("old line")
    s_in.command.line_up(5)
    sig_in = s_in.on_state("initializing")
    check("state 'initializing' hands focus to the command pane, at its live "
          "edge, with a full redraw",
          s_in.focus == "command" and s_in.command.scroll_top is None
          and sig_in == "focus")
    sig_out = s_in.on_state("initialized")
    check("state 'initialized' hands it back to the circle pane the same way",
          s_in.focus == "circle" and s_in.circle.scroll_top is None
          and sig_out == "focus")
    # THE END OF THE CIRCLE IS ANNOUNCED — the operator, 2026-08-25: *"After
    # /close finishes its post-close processing, the UI just sits. It is not
    # clear that everything is done and ready for app exit, nor is it clear
    # how to exit."* main_loop calls this once, after the last of the
    # engine's output has been drained.
    class _Done:
        def __init__(self, crashed=None, code=0):
            self.finished = threading.Event()
            self.finished.set()
            self._thread = object()          # started, then finished
            self.crashed = crashed
            self.exit_code = code
            self.live = True

    s_fin = C.AppState(6, 6, backend=_Done())
    s_fin.focus = "circle"
    s_fin.circle.append("[Alpha]: a statement")
    sig_fin = s_fin.on_finished()
    check("the end hands focus to the command pane, with a full redraw",
          s_fin.focus == "command" and sig_fin == "focus"
          and s_fin.command.scroll_top is None)
    check("...the room is told it is over",
          "the circle is over" in s_fin.circle.lines[-1])
    check("...and the command pane names the ONE way out",
          "written everything it was going to write" in s_fin.command.lines[-2]
          and "quit" in s_fin.command.lines[-1])
    s_bad = C.AppState(6, 6, backend=_Done(code=1))
    s_bad.on_finished()
    check("a non-zero exit says a problem was reported, and claims nothing "
          "about what was written",
          "reported a problem" in s_bad.command.lines[-2]
          and "written everything" not in s_bad.command.lines[-2])
    check("speech after the end is refused, in the command pane, naming quit",
          s_fin._submit(s_fin.circle, "zz") is not None
          or "quit" in s_fin.command.lines[-1])
    check("...and the circle pane did NOT echo it",
          "[You]: zz" not in "\n".join(s_fin.circle.lines))
    check("the circle row reads (ended), even with a line still in flight",
          C._circle_prompt(s_fin).endswith("(ended)> "))
    s_fin.backend.line_taken = threading.Event()      # cleared = in flight
    check("...which is exactly the case that used to read '(waiting)'",
          C._circle_prompt(s_fin).endswith("(ended)> "))
    # AN ERROR BRINGS THE COMMAND PANE FORWARD — the operator, 2026-08-25, after an
    # open-time "its DREAMING did not run" scrolled out of the one-fifth
    # pane while the proposal listing below it took the screen. The drain
    # calls on_alert for every COMMAND-channel line, AFTER appending it; a
    # `!!` one takes focus (and with it the 4/5ths) and pins the view to the
    # alert's own row. The resize/apply ORDER below is the contract
    # main_loop follows and no suite can execute main_loop to check.
    line_al = "\n  !! circle_2026-08-21_1139: its DREAMING did not run."
    check("is_alert reads the mark through a leading newline and indent",
          C.ui_is_alert(line_al) and C.ui_is_alert("  !! LIVE, IN A WORKTREE")
          and not C.ui_is_alert("  2 practice proposal(s) awaiting a ruling"))
    s_al = C.AppState(6, 3)
    s_al.focus = "circle"
    for i in range(12):
        s_al.command.append(f"open-time line {i}")
    s_al.command.append(line_al)                 # the drain appends first
    sig_al = s_al.on_alert(line_al)
    row_al = s_al.command.last_alert_row()
    check("a `!!` command line hands focus over, with a full redraw",
          s_al.focus == "command" and sig_al == "focus")
    check("...anchored on the alert's own row, but NOT applied yet",
          s_al.command.scroll_top is None and s_al._alert_anchor == row_al)
    s_al.command.resize(9)                       # what _pane_heights gives it
    s_al.apply_alert_anchor()
    check("...applied after the resize, unclamped, the alert on top",
          s_al.command.scroll_top == row_al
          and s_al.command.visible()[0] == s_al.command.lines[row_al]
          and row_al > s_al.command._max_top())
    s_al.command.append("        [BP-0041] add — synthesis")
    check("...so what follows the alert fills in BELOW it, view unmoved",
          s_al.command.visible()[0] == s_al.command.lines[row_al]
          and s_al.command.visible()[-1].endswith("add — synthesis"))
    check("a second `!!` while pinned leaves the FIRST one anchored",
          s_al.on_alert("\n  !! and another") is None
          and s_al.command.scroll_top == row_al)
    check("an ordinary command line is not an alert at all",
          s_al.on_alert("  9 issue(s) in the working set") is None)
    s_at = C.AppState(6, 3)
    s_at.focus = "circle"
    s_at.circle.input_buf = "half a sentence, not yet said"
    for i in range(12):
        s_at.command.append(f"open-time line {i}")
    s_at.command.append(line_al)
    check("mid-sentence in the room, the alert pins WITHOUT taking focus",
          s_at.on_alert(line_al) is None and s_at.focus == "circle"
          and s_at.command.scroll_top == s_at.command.last_alert_row())
    s_ac = C.AppState(6, 3)
    s_ac.command.append(line_al)
    s_ac.on_alert(line_al)
    check("the coordinator's own handover clears a pending alert anchor",
          s_ac._alert_anchor is not None
          and s_ac.on_state("closing") == "focus"
          and s_ac._alert_anchor is None)
    # THREE DEFENSIVE BRANCHES, never taken by any suite until now
    # (audit-register 2026-09-04 #15a) — uncovered only because ui_main_loop
    # itself never runs headless (#13), not because they cannot happen.
    s_row = C.AppState(6, 3)
    check("on_alert with no matching row in the pane returns None — the "
          "line reached on_alert before the pane's own append did",
          s_row.on_alert(line_al) is None and s_row.focus != "command")
    s_noop = C.AppState(6, 3)
    check("apply_alert_anchor with nothing pending is a no-op, not an error",
          s_noop._alert_anchor is None and s_noop.command.scroll_top is None)
    s_noop.apply_alert_anchor()
    check("...and stays that way — every other reason main_loop redraws "
          "both panes hits this",
          s_noop._alert_anchor is None and s_noop.command.scroll_top is None)
    import llm_client as _LC
    import phase_clock as _PC
    real_meter = _LC.METER
    try:
        class _BrokenMeter:
            def reset(self):
                raise RuntimeError("a fake module, or a real one mid-refactor")
        _LC.METER = _BrokenMeter()
        reset_calls = []
        real_phases_reset = _PC.PHASES.reset
        _PC.PHASES.reset = lambda: (reset_calls.append(1), real_phases_reset())[-1]
        try:
            raised = False
            try:
                C._reset_process_accumulators()
            except Exception:                                # noqa: BLE001
                raised = True
        finally:
            _PC.PHASES.reset = real_phases_reset
        check("a broken accumulator's reset() does not raise past the "
              "caller — housekeeping must not block a circle opening",
              not raised)
        check("...and the OTHER accumulator's reset() still ran — one "
              "broken module does not stop the loop",
              reset_calls == [1])
    finally:
        _LC.METER = real_meter
    # TWO EMPTY LINES BEFORE SELF'S OWN LINE (2026-08-21), pane only.
    s_sp = C.AppState(6, 6)
    s_sp._submit(s_sp.circle, "first words")
    check("the first line in an empty pane takes no spacer",
          s_sp.circle.lines == ["[You]: first words"])
    s_sp.circle.append("[Alpha]: a reply")
    s_sp._submit(s_sp.circle, "second words")
    check("a later line is prefaced by two empty rows",
          s_sp.circle.lines[-3:] == ["", "", "[You]: second words"])
    s_or = C.AppState(6, 6)
    s_or.focus = "circle"
    sig_or = s_or._submit(s_or.circle, "ordinary speech")
    check("ordinary speech does none of it", 
          s_or.focus == "circle" and sig_or is None
          and s_or.circle.lines[-1] == "[You]: ordinary speech")
    s_nb = C.AppState(6, 6)
    s_nb.focus = "circle"
    sig_nb = s_nb._submit(s_nb.circle, "  /close  ")
    check("a typed /close, whitespace or not, is speech to forward and no "
          "longer a handover — focus stays until the coordinator says "
          "'closing'",
          s_nb.focus == "circle" and sig_nb is None
          and s_nb.circle.lines[-1] == "[You]:   /close  ")
    s_bare = C.AppState(6, 6)
    s_bare.focus = "circle"
    s_bare._submit(s_bare.circle, "close")
    check("a BARE unslashed 'close' is speech, not the verb — E11's own "
          "history is a bare `close` typed as a typo",
          s_bare.focus == "circle")

    # --- THE CLOSE'S OWN STATE at the command pane (2026-08-21) ----------
    eng_cs = C.CircleEngine(queue.Queue())
    eng_cs._thread = threading.Thread(target=lambda: None)   # "running"
    eng_cs.loop_reached = True
    eng_cs.close_state = "closing"
    check("_command_prompt reads the closing notice while the close proceeds",
          C._command_prompt(C.AppState(4, 4, backend=eng_cs))
          == "closing the circle — collecting memories, please wait (input disabled) ")
    r_cs = eng_cs.submit_command("status")
    check("a cmd> line while closing is refused with a notice, not run",
          r_cs is None and eng_cs.circle_in.empty()
          and "input is disabled" in eng_cs.out_queue.get_nowait()[1])
    check("...but 'quit' is still honoured — a hung close stays escapable",
          eng_cs.submit_command("quit") == "quit")
    eng_cs.waiting_for_input, eng_cs.waiting_for_channel = True, "command"
    eng_cs.pending_prompt = "[BP-7] a)pprove, d)eny, s)kip ?"
    eng_cs.submit_command("s")
    check("a command-channel question the CLOSE itself asks (vetting at close) "
          "still takes its answer while closing",
          eng_cs.command_in.get_nowait() == "s")
    check("...and owns the cmd> row over the closing notice",
          C._command_prompt(C.AppState(4, 4, backend=eng_cs)).startswith("[BP-7]"))
    eng_cs.waiting_for_input, eng_cs.pending_prompt = False, ""
    eng_cs.close_state = "close-confirm-pending"
    eng_cs.submit_command("close")
    check("while the circle waits for its SECOND /close, 'close' at cmd> is "
          "FORWARDED into the room — the one circle verb cmd> passes on",
          eng_cs.circle_in.get_nowait() == "/close"
          and "forwarded" in eng_cs.out_queue.get_nowait()[1])
    eng_cs.close_state = ""
    eng_cs.submit_command("/close")
    check("...and with no confirmation pending it is refused as before",
          eng_cs.circle_in.empty()
          and "circle-pane speech" in eng_cs.out_queue.get_nowait()[1])
    check("the engine's _emit routes a 'state' item to close_state AND the "
          "queue — the screen handles it in order with the output around it",
          (eng_cs._emit("state", "closing") or True)
          and eng_cs.close_state == "closing"
          and eng_cs.out_queue.get_nowait() == ("state", "closing"))

    # --- "(waiting)" THE INSTANT A LINE IS SUBMITTED (2026-08-21) --------
    eng_w = C.CircleEngine(queue.Queue())
    eng_w.waiting_for_input = True          # parked at Self>, as the flags say
    eng_w.speaking_turn = True
    eng_w.loop_reached = True               # a Self> park implies the loop
    s_w = C.AppState(4, 4, backend=eng_w)
    check("parked at Self>: the plain prompt",
          C._circle_prompt(s_w) == eng_w._C.circle_prompt_read())
    eng_w.submit_circle("a statement")      # engine thread has NOT woken yet
    check("the moment a line is submitted the row says (waiting), even "
          "though the engine's own flags still read 'parked' — line_taken "
          "is cleared on this thread, before the put; NAMED since D62 (a)",
          C._circle_prompt(s_w)
          == f"{eng_w._C.circle_prompt_read()[:-2]} (waiting — the parts are replying)> ")
    eng_w.line_taken.set()                  # the read returned...
    eng_w.waiting_for_input = False         # ...and the loop is busy
    check("...and stays (waiting) while the parts reply",
          C._circle_prompt(s_w)
          == f"{eng_w._C.circle_prompt_read()[:-2]} (waiting — the parts are replying)> ")
    eng_w.waiting_for_input = True
    check("...until the loop is back at its read",
          C._circle_prompt(s_w) == eng_w._C.circle_prompt_read())

    # --- B66: the tick's baseline is what was DRAWN, never a loop copy --
    # The install circle's screen, 2026-08-25: an invalid working-set
    # answer was refused and the question re-asked, but the row kept
    # saying "(waiting)" with the cursor at the question's own column.
    # The prompt had gone question -> waiting -> the SAME question; the
    # waiting draw happened on the keystroke path, which never told the
    # tick's loop-local baseline, so the returned question compared equal
    # to it. The baseline is Pane.input_prompt_drawn now, written by the
    # drawers themselves — this exercises exactly the A -> B -> A shape.
    eng_b66 = C.CircleEngine(queue.Queue())
    eng_b66.waiting_for_input, eng_b66.waiting_for_channel = True, "circle"
    eng_b66.pending_prompt = "Do you have specific issues to focus on ?"
    s_b66 = C.AppState(4, 4, backend=eng_b66)
    sink_b66: list[str] = []
    q_prompt = C._circle_prompt(s_b66)
    C._render_input_row(s_b66, "circle", q_prompt, sink_b66.append, 100)
    check("B66: the drawer records the prompt it drew on the pane",
          s_b66.circle.input_prompt_drawn == q_prompt)
    eng_b66.submit_circle("16")             # the keystroke path's state
    w_prompt = C._circle_prompt(s_b66)
    check("B66: the submitted line flips the live prompt to a waiting form",
          w_prompt != q_prompt)
    C._render_input_row(s_b66, "circle", w_prompt, sink_b66.append, 100)
    eng_b66.line_taken.set()                # consumed; the SAME question back
    check("B66: the re-asked question DIFFERS from what is on screen — the "
          "A->B->A shape a loop-local baseline compared equal, so the tick "
          "now sees a repaint owing",
          C._circle_prompt(s_b66) == q_prompt
          and C._circle_prompt(s_b66) != s_b66.circle.input_prompt_drawn)

    # --- A BLANK ANSWER IS ECHOED AS THE QUESTION'S OWN LEGEND (2026-08-21)
    eng_b = C.CircleEngine(queue.Queue())
    eng_b.waiting_for_input, eng_b.waiting_for_channel = True, "circle"
    eng_b.pending_prompt = "CIRCLE issues (blank = all, 'none', '?'):"
    s_b = C.AppState(4, 4, backend=eng_b)
    s_b._submit(s_b.circle, "")
    check("a blank working-set answer echoes as '[You]: (blank = all)' — the "
          "legend read off the question, not a coordinator word the pane "
          "learned",
          s_b.circle.lines[-1] == "[You]: (blank = all)")
    eng_b.pending_prompt = "CIRCLE topic (blank = open):"
    s_b._submit(s_b.circle, "")
    check("...and the topic's as '(blank = open)'",
          s_b.circle.lines[-1] == "[You]: (blank = open)")
    # THE TWO-PART HINT (2026-09-15): the legend regex stops at the comma, so the
    # shipped roster's longer prompt still echoes the blank as '(blank = open)'.
    eng_b.pending_prompt = "CIRCLE topic (blank = open, ? for suggestions):"
    s_b._submit(s_b.circle, "")
    check("...and the two-part topic prompt's too — '? for suggestions' is not "
          "read into the legend",
          s_b.circle.lines[-1] == "[You]: (blank = open)")
    s_b._submit(s_b.circle, "n0010")
    check("a typed answer echoes as itself",
          s_b.circle.lines[-1] == "[You]: n0010")


    # --- Tab reshapes the split, and the split IS the focus indicator
    # (2026-08-18). The heights and the header/chrome text are checkable
    # here; the main_loop wiring that applies them on a real keypress
    # needs a TTY and is not reachable from a headless run. ------------
    demo_rows = 40
    tall_circle = C._pane_heights(demo_rows, "circle")
    tall_command = C._pane_heights(demo_rows, "command")
    check("the FOCUSED pane gets the larger share, whichever one it is",
          tall_circle[0] > tall_circle[1] and tall_command[1] > tall_command[0])
    check("_pane_heights is an exact mirror — focus picks the slot, never "
          "the tuple order",
          tall_circle == tuple(reversed(tall_command)))

    s_tab = C.AppState(*tall_circle)
    check("the opening split matches AppState's opening focus (CIRCLE tall)",
          s_tab.circle.height > s_tab.command.height)
    s_tab.handle_key("\t")
    s_tab.resize(*C._pane_heights(demo_rows, s_tab.focus))
    check("after one Tab COMMAND is the taller pane — which is now the "
          "whole of how the UI says where typing lands",
          s_tab.command.height > s_tab.circle.height)
    s_tab.handle_key("\t")
    s_tab.resize(*C._pane_heights(demo_rows, s_tab.focus))
    check("Tab back restores the opening split exactly",
          (s_tab.circle.height, s_tab.command.height) == tall_circle)

    hdr_focused: list[str] = []
    C.ui_pane_header_render(s_tab, "circle", 80, hdr_focused.append)
    s_tab.handle_key("\t")                     # same pane, now UNfocused
    hdr_unfocused: list[str] = []
    C.ui_pane_header_render(s_tab, "circle", 80, hdr_unfocused.append)
    check("a pane's header is byte-identical focused or not — the [FOCUS] "
          "tag is gone, not merely moved",
          hdr_focused == hdr_unfocused
          and "FOCUS" not in "".join(hdr_focused))
    chrome_out: list[str] = []
    C.ui_chrome_render(s_tab, 80, chrome_out.append)
    check("the status line no longer names the focused pane either",
          "focus:" not in "".join(chrome_out).lower())

    # --- 'resume <OT>' typed in the command pane propagates through
    # AppState._submit exactly like 'quit'/'help' already do ------------
    eng6 = C.CircleEngine(queue.Queue())
    s6b = C.AppState(4, 4, backend=eng6)
    s6b.focus = "command"
    sig = s6b._submit(s6b.command, "resume 2026-08-10_2112")
    check("AppState._submit relays the resume signal for main_loop",
          sig == "resume:2026-08-10_2112")

    # --- Merged verb surface (stages 5/6, RULED 2026-08-13) — unit level,
    # bare/never-started engine so no real circle.py thread is needed,
    # same style as the quit/abort/help/status checks above. ------------
    eng8 = C.CircleEngine(queue.Queue())
    eng8.submit_command("round")
    check("bare engine: 'round' is refused as circle-pane-only, not "
          "'not understood'",
          "circle-pane speech" in eng8.out_queue.get_nowait()[1])
    eng8.submit_command("pass")
    check("'pass' refused the same way",
          "circle-pane speech" in eng8.out_queue.get_nowait()[1])

    eng8.submit_command("issue-evidence-list")
    check("an attest-class verb (issue-evidence-list) with no circle running "
          "refuses with a reason, not 'not understood'",
          "needs a circle open" in eng8.out_queue.get_nowait()[1])

    eng8.submit_command("bogus-verb-nobody-registered")
    check("a genuinely unrecognized word is JUNK — answered with the help "
          "listing headed by the line naming it (2026-08-21)",
          eng8.out_queue.get_nowait()[1].startswith(
              "  not a command: bogus-verb-nobody-registered"))

    # TWO CLAIMS, SPLIT 2026-09-16: that the verb is AVAILABLE with no circle
    # running, and that it lists THIS INSTALLATION's practices. Only the second
    # needs data, and rolling them together meant a fresh install — the tree
    # where "does the command pane work at all?" matters most — skipped both and
    # tested neither.
    eng8.submit_command("practice-list")
    channel, text = eng8.out_queue.get_nowait()
    check("an always-available verb (practice-list) works with no "
          "circle running, calling circle.py's own function directly",
          channel == "command" and "not understood" not in text.lower(),
          f"reply was ({channel!r}, {text!r})")
    if _has_practice():
        check("...and the reply carries this installation's own ruled "
              "practices", "[BP-" in text, f"reply was {text!r}")
    else:
        skip("...and the reply carries this installation's own ruled "
             "practices",
             "self/best_practices.toml holds no entries — the assertion "
             "looks for a BP- id, and a fresh install has ruled none in")

    # DEV ON for the next four: /prompt-show, /issue-apply, /issue-status and
    # /issue-label-update are DEV-table verbs since 2026-08-21
    # (R288), and with dev off the pane answers them as
    # JUNK — pinned first, then the real dispatch with dev on.
    eng8.submit_command("prompt-show circle")
    ch_g, txt_g = eng8.out_queue.get_nowait()
    check("a DEV-table verb typed with dev OFF is JUNK at the pane itself — "
          "answered with the help listing, never dispatched (2026-08-21; "
          "until then the pane ran a dev verb with no circle regardless)",
          ch_g == "command" and txt_g.startswith("  not a command: prompt-show")
          and "BLOCK 1" not in txt_g)
    _dev_before8 = eng8._CS.dev_mode
    eng8._CS.dev_mode = True
    eng8.submit_command("prompt-show circle")
    channel, text = eng8.out_queue.get_nowait()
    check("prompt-show works with no circle running too",
          channel == "command" and "BLOCK 1" in text)

    eng8.submit_command("issue-apply")
    check("issue-apply with no args reports its usage (ported from "
          "ic.py, unaffected by the no-circle path)",
          eng8.out_queue.get_nowait()[1].strip().startswith("usage:"))

    # R261, 2026-08-20: the VERB IS THE HEAD. These read `issue nNNNN
    # status` and `issue issue-label-update ...` — two commands behind one
    # word, told apart by whether the FIRST ARGUMENT looked like a node id.
    # The split they were checking is unchanged and still matters: a NODE's
    # status runs here and now, a RULING batches at close and needs a
    # circle. Only the spelling moved.
    #
    # THE SUBMIT IS UNCONDITIONAL NOW, and only the assertion about its CONTENT
    # is guarded — the same reply is what the underscore check below compares
    # against, and that check needs no data at all.
    eng8.submit_command("issue-status n0002")
    _hyphen = eng8.out_queue.get_nowait()
    if _has_issue("n0002"):
        check("'issue-status nNNNN' (bare property, no circle needed) READS a "
              "real issue's status — the construct's read half",
              _hyphen[0] == "command" and _hyphen[1].strip().startswith("n0002:"),
              f"reply was {_hyphen!r}")
    else:
        skip("'issue-status nNNNN' (bare property, no circle needed) READS a "
             "real issue's status — the construct's read half",
             "issues/ holds no n0002 — this half of the construct is the "
             "READ, so it needs a node that exists")

    eng8.submit_command('issue-label-update n0002 "x" "y"')
    check("'issue-label-update ...' refuses as needing a circle — it "
          "attests against a transcript and batches at close, and no "
          "argument inspection is involved in telling it apart any more",
          "needs a circle open" in eng8.out_queue.get_nowait()[1])

    # FINDING 14, the same day: `/topic_close` was refused twice as "not
    # understood". An underscore is a typo, not a second grammar — and the
    # normaliser is shared with circle.py so it cannot be fixed in one
    # dispatcher and left broken in the others.
    # THE NORMALISER NEEDS NO DATA, and this check used to behave as though it
    # did: it read a real node's status back, so a fresh install skipped the one
    # assertion that is purely about spelling. Submit BOTH spellings at the same
    # id and require the SAME answer — whatever that answer is, a status or a
    # complaint that the node is unknown, only a RESOLVED underscore can produce
    # it, because an unresolved one is "not understood". Strictly stronger than
    # the old form, and true in an empty tree. 2026-09-16.
    eng8.submit_command("issue_status n0002")
    _under = eng8.out_queue.get_nowait()
    check("an UNDERSCORE resolves to the hyphen the table holds",
          _under == _hyphen and "not understood" not in _hyphen[1].lower(),
          f"hyphen -> {_hyphen!r}; underscore -> {_under!r}")
    eng8._CS.dev_mode = _dev_before8          # restore the shared attribute

    # --- leading slash is OPTIONAL in the command pane, never required
    # (2026-08-16). "/" only disambiguates command from dialog in the
    # CIRCLE pane (docs/HELP_DESIGN.md §0) — everything typed HERE is
    # already a command. Before this fix, the merged verb surface below
    # unconditionally PREPENDED "/" to the first word, so a user typing
    # "/help" got "//help", matched no PANE_OF key, and fell through to
    # "not understood, see 'help'" — exactly what the operator reported. ---------
    eng_slash = C.CircleEngine(queue.Queue())
    r_bare = eng_slash.submit_command("help")
    t_bare = eng_slash.out_queue.get_nowait()
    eng_slash2 = C.CircleEngine(queue.Queue())
    r_slash = eng_slash2.submit_command("/help")
    t_slash = eng_slash2.out_queue.get_nowait()
    check("'help' and '/help' return the same signal",
          r_bare == r_slash == "help")
    check("'help' and '/help' produce identical output", t_bare == t_slash)

    eng_slash3 = C.CircleEngine(queue.Queue())
    eng_slash3.submit_command("/practice-list")
    ch_s, txt_s = eng_slash3.out_queue.get_nowait()
    check("'/practice-list' (slashed) reaches the always-available "
          "dispatcher, not the JUNK listing",
          ch_s == "command" and "not a command" not in txt_s)

    eng_slash4 = C.CircleEngine(queue.Queue())
    eng_slash4.submit_command("//help")
    check("'//help' (two slashes) is still JUNK — not silently accepted "
          "as a third spelling",
          eng_slash4.out_queue.get_nowait()[1].startswith("  not a command: //help"))

    # The no-op read_line stub, checked in isolation (see its own
    # docstring for why: whether n0002 -> declined specifically would
    # reach a confirmation prompt at all depends on live issues/ graph
    # state — its own edges, checked elsewhere — not on this mechanism).
    result = eng8._no_block_read_line("  type 'yes' to apply: ")
    check("_no_block_read_line answers '' immediately, never blocks",
          result == "")
    check("...and echoes the prompt itself first",
          eng8.out_queue.get_nowait() == ("command", "  type 'yes' to apply: "))
    check("...then explains why, on the command channel",
          "no interactive confirmation" in eng8.out_queue.get_nowait()[1])

    # --- stage 8 (RULED 2026-08-13, Q3): CircleEngine.start(live=...)
    # argv construction. C.main() is faked here (records sys.argv,
    # returns 0 immediately) specifically so this NEVER lets a real
    # --live run reach the roster check, the API-key check, or a
    # single write under circles/parts/work — this test is about what
    # argv gets BUILT, not about running a circle. -----------------------
    captured_argv: list[list[str]] = []
    eng9 = C.CircleEngine(queue.Queue())
    orig_main = eng9._C.main            # same module for every CircleEngine
    eng9._C.main = lambda: (captured_argv.append(list(sys.argv)), 0)[1]
    try:
        eng9.start(live=False)
        check("live=False (the default) still builds --dry-run, no --live",
              eng9.finished.wait(timeout=5)
              and "--dry-run" in captured_argv[-1]
              and "--live" not in captured_argv[-1])
        check("engine.live records False", eng9.live is False)

        eng9b = C.CircleEngine(queue.Queue())
        captured_argv.clear()
        eng9b.start(live=True)
        check("live=True builds --live, no --dry-run",
              eng9b.finished.wait(timeout=5)
              and "--live" in captured_argv[-1]
              and "--dry-run" not in captured_argv[-1])
        check("engine.live records True", eng9b.live is True)

        eng9c = C.CircleEngine(queue.Queue())
        captured_argv.clear()
        eng9c.start(extra_argv=["--live", "--dry-run", "--parts", "alpha"],
                   live=False)
        check("--live/--dry-run in extra_argv are stripped regardless — "
              "the `live` parameter is the only door, RULED 2026-08-13",
              eng9c.finished.wait(timeout=5)
              and captured_argv[-1].count("--live") == 0
              and captured_argv[-1].count("--dry-run") == 1  # from live=False alone
              and "--parts" in captured_argv[-1])
    finally:
        eng9._C.main = orig_main

    # --- audit-register 2026-09-04 #3: the engine thread's `except
    # Exception` arm (circling.py's run() inner function) had never been
    # EXECUTED — only its reader, AppState.on_finished, against a stub. A
    # NameError in that arm would let a crashed circle report "finished -
    # exiting cleanly" with the traceback on a hidden stderr. Point the faked
    # C.main at a function that raises and prove the arm sets `crashed` and
    # says so on the command channel. -----------------------------------
    eng10 = C.CircleEngine(queue.Queue())
    orig_main10 = eng10._C.main

    def _boom() -> int:
        raise RuntimeError("boom")
    eng10._C.main = _boom
    try:
        eng10.start(live=False)
        finished = eng10.finished.wait(timeout=5)
        crashed_lines = []
        while True:
            try:
                crashed_lines.append(eng10.out_queue.get_nowait())
            except queue.Empty:
                break
        check("a crash inside the engine thread still sets `finished`", finished)
        check("...and records the exception on engine.crashed",
              isinstance(eng10.crashed, RuntimeError) and "boom" in str(eng10.crashed))
        check("...and says so on the COMMAND channel, naming the exception",
              any(ch == "command" and "CircleEngine crashed" in txt and "boom" in txt
                  for ch, txt in crashed_lines))
    finally:
        eng10._C.main = orig_main10

    # --- stage 8b, audit-register.md #15: THIS module's own main() — its
    # argv assembly — translating raw argv into the (extra_argv, live) pair
    # CircleEngine.start receives. Stage 8 above pins start(live=...)
    # directly; nothing connected REAL argv to it, including the one flag
    # that decides a rehearsal from a real circle. The circle is the only
    # path main() has besides --help and --selftest: every token forwards
    # except --no-color, and start() is what strips --live/--dry-run.
    # CircleEngine.start and main_loop are both stubbed so this never
    # spawns a thread, never touches circle.py, and opens nothing. --------
    captured_start: list[tuple[list[str], bool]] = []
    real_start = C.CircleEngine.start
    real_main_loop = vars(C)["ui_main_loop"]

    def _fake_start(self, extra_argv=None, live=False):
        captured_start.append((list(extra_argv or []), live))
        self.finished.set()

    C.CircleEngine.start = _fake_start
    vars(C)["ui_main_loop"] = lambda *a, **k: 0
    # THE KEY CHECK IS STUBBED, so these argv cases mean the same in a tree with a key and in
    # one without (a fresh worktree has no .env). R546's own cases follow.
    real_notice = vars(C)["_key_notice_read"]
    vars(C)["_key_notice_read"] = lambda full: ""
    real_argv = sys.argv
    try:
        sys.argv = ["circling.py", "--parts", "alpha"]
        captured_start.clear()
        check("no flags but a circle option: live=False, the option forwarded, "
              "no --live/--dry-run in extra_argv",
              C.main() == 0 and captured_start
              and captured_start[-1] == (["--parts", "alpha"], False))

        sys.argv = ["circling.py"]
        captured_start.clear()
        check("a bare run is a dry-run circle: live=False, nothing forwarded",
              C.main() == 0 and captured_start[-1] == ([], False))

        sys.argv = ["circling.py", "--live", "--parts", "alpha"]
        captured_start.clear()
        check("--live FIRST: live=True — the one door R330/Q3 rules — and "
              "main() forwards --live in extra_argv unfiltered, same as "
              "start()'s own docstring says its caller may; start() is what "
              "strips it (stage 8's own case 3)",
              C.main() == 0
              and captured_start[-1] == (["--live", "--parts", "alpha"], True))

        sys.argv = ["circling.py", "--parts", "alpha", "--live"]
        captured_start.clear()
        check("--live LAST: still live=True — position does not matter",
              C.main() == 0
              and captured_start[-1] == (["--parts", "alpha", "--live"], True))

        sys.argv = ["circling.py", "--no-color", "--parts", "alpha"]
        captured_start.clear()
        check("--no-color is this program's own flag and is NOT forwarded",
              C.main() == 0
              and captured_start[-1] == (["--parts", "alpha"], False))

        sys.argv = ["circling.py", "--dev", "--parts", "alpha"]
        captured_start.clear()
        check("--dev is forwarded verbatim, once, in the position typed — "
              "hidden from --help, unchanged in behaviour",
              C.main() == 0
              and captured_start[-1] == (["--dev", "--parts", "alpha"], False))

        sys.argv = ["circling.py", "--parts", "alpha", "--dev=false"]
        captured_start.clear()
        check("--dev=false forwards in that form, for circle.py's own parser",
              C.main() == 0
              and captured_start[-1] == (["--parts", "alpha", "--dev=false"], False))

        # R546: a live circle with no key never opens the window; the
        # whole text goes to the terminal, where the alternate screen cannot take it away.
        vars(C)["_key_notice_read"] = lambda full: "NO-KEY-WHOLE" if full else "NO-KEY-BRIEF"
        sys.argv = ["circling.py", "--live", "--parts", "alpha"]
        captured_start.clear()
        said, real_stdout = io.StringIO(), sys.stdout
        sys.stdout = said
        try:
            rc = C.main()
        finally:
            sys.stdout = real_stdout
        check("--live with no key: exit 2, the whole text on the terminal, "
              "and no engine started", rc == 2 and "NO-KEY-WHOLE" in said.getvalue()
              and not captured_start)
        sys.argv = ["circling.py", "--parts", "alpha"]
        captured_start.clear()
        check("without --live (a dry run) with no key still opens — "
              "circle.py's own short notice is what the command pane shows",
              C.main() == 0 and captured_start[-1] == (["--parts", "alpha"], False))
    finally:
        sys.argv = real_argv
        C.CircleEngine.start = real_start
        vars(C)["ui_main_loop"] = real_main_loop
        vars(C)["_key_notice_read"] = real_notice
        # AND THE TINT, which is not a stub and is easy to miss in a restore
        # block full of them. main() is REAL here — only its collaborators are
        # faked — so every call above ran `COLOR = sys.stdout.isatty() and ...`
        # for real. THAT LEAKED, AND IT COST A DAY (2026-09-16): on a machine
        # where the suite's own stdout IS a terminal, COLOR came out of this
        # block TRUE, and the _tint check 1,400 lines below then failed naming
        # _tint — a sentence about the wrong file. It never fired in this tree
        # because output here is piped, so isatty() is False and the leak wrote
        # the value the suite wanted anyway. A defect whose visibility depends
        # on whether anyone is watching is the kind this project pays for
        # twice, so the restore is explicit rather than incidental.
        C.COLOR = False

    # THE REAL FUNCTION, RUN ONCE (audit-register 2026-09-11 #11). The stub above tests the
    # two CALL SITES; this runs the BODY — its sys.path bootstrap, the llm_client import,
    # the choice of text — with only the provider's own key check rebound, so a tree with a
    # key and one without give the same answer. Its `except Exception: return ""` is why
    # this matters: a broken bootstrap would make the notice silently empty, and a person
    # installing with no key would get a window that says nothing about why nothing works.
    import llm_client as _LCK
    real_present = _LCK.stream_key_present_read
    try:
        _LCK.stream_key_present_read = lambda: False
        check("_key_notice_read(True) with no key is the provider's whole missing-key text",
              real_notice(True) == _LCK.KEY_MISSING_HELP and len(_LCK.KEY_MISSING_HELP) > 100)
        check("_key_notice_read(False) with no key is the brief — shorter, and not empty",
              real_notice(False) == _LCK.KEY_MISSING_BRIEF
              and 0 < len(_LCK.KEY_MISSING_BRIEF) < len(_LCK.KEY_MISSING_HELP))
        _LCK.stream_key_present_read = lambda: True
        check("...and with a key present both forms are \"\" — a notice never stops the window",
              real_notice(True) == "" and real_notice(False) == "")
    finally:
        _LCK.stream_key_present_read = real_present

    # --- _open_sandbox_circles(): scoped to the engine's OWN root -------
    import record_paths as _rp                       # the live root is a group's (B117)
    fake_live_entry = {"path": pathlib.Path(_rp.record_rel("circles")) / "circle_2026-08-13_0900.md"}
    fake_sandbox_entry = {"path": pathlib.Path("work") / "sandbox"
                           / "circles" / "circle_2026-08-13_0901.md"}
    eng9d = C.CircleEngine(queue.Queue())
    import circle_state as _cs
    orig_open_circles = _cs.circle_open_read
    _cs.circle_open_read = lambda: [fake_live_entry, fake_sandbox_entry]
    try:
        eng9d.live = False
        found = eng9d._open_sandbox_circles()
        check("not live -> only the SANDBOX-rooted fake entry",
              len(found) == 1 and found[0] is fake_sandbox_entry)
        eng9d.live = True
        found = eng9d._open_sandbox_circles()
        check("live=True -> only the LIVE-rooted fake entry",
              len(found) == 1 and found[0] is fake_live_entry)
    finally:
        _cs.circle_open_read = orig_open_circles

    # --- wait_for_live_engine_before_exit() — the exit-safety wait,
    # extracted specifically so it's testable without a real TTY. -------
    class _FakeEngine:
        def __init__(self, live: bool) -> None:
            self.live = live
            self.finished = threading.Event()

    out_lines: list[str] = []
    fe1 = _FakeEngine(live=False)
    C.ui_live_engine_wait(fe1, warn_after=0.05, out=out_lines.append)
    check("live=False: returns immediately, nothing printed",
          out_lines == [])

    fe2 = _FakeEngine(live=True)
    fe2.finished.set()
    C.ui_live_engine_wait(fe2, warn_after=0.05, out=out_lines.append)
    check("live=True but already finished: returns immediately too",
          out_lines == [])

    fe3 = _FakeEngine(live=True)

    def _finish_fe3_soon() -> None:
        time.sleep(0.02)
        fe3.finished.set()
    threading.Thread(target=_finish_fe3_soon, daemon=True).start()
    C.ui_live_engine_wait(fe3, warn_after=5, out=out_lines.append)
    check("live=True, finishes well within warn_after: reports finished",
          any("finished" in ln for ln in out_lines))
    check("...with no periodic re-warning (only the initial 'waiting...' "
          "announcement, never the '!! still running past ...' one)",
          not any(ln.strip().startswith("!!") for ln in out_lines))

    out_lines.clear()
    fe4 = _FakeEngine(live=True)

    def _finish_fe4_after_warning() -> None:
        time.sleep(0.15)                 # past two 0.05s warn cycles
        fe4.finished.set()
    threading.Thread(target=_finish_fe4_after_warning, daemon=True).start()
    C.ui_live_engine_wait(fe4, warn_after=0.05, out=out_lines.append)
    check("still running past warn_after: the periodic warning fires "
          "at least once before it finishes",
          any("still running" in ln for ln in out_lines))
    check("...and still reports finished once it actually does",
          any("finished" in ln for ln in out_lines[-1:]))

    # TWO KEY CLUSTERS, TWO JOBS — the operator, 2026-08-25: *"number pad to
    # scroll, dedicated to change line?"* Measured at his own terminal first:
    # numpad 7/8/9/4/6/1/2/3 arrive as lead '\x00', the arrow cluster as
    # '\xe0', with the SAME eight scan codes. poll_key's own wiring is
    # Windows-console-only and outside this suite's reach; the TABLES are
    # not, and neither is what handle_key does with the tokens.
    if "_WIN_SCAN_EXT" in vars(C):
        check("the numpad's eight scan codes and the dedicated cluster's are "
              "the same eight",
              set(C._WIN_SCAN_NUMPAD) == set(C._WIN_SCAN_EXT) == set("HPIQGOKM"))
        check("the numpad scrolls: its Up/Down/Home/End are SCROLL_KEYS",
              all(C._WIN_SCAN_NUMPAD[c] in C.SCROLL_KEYS for c in "HPGO"))
        check("the arrows edit: their Up/Down and Home/End are cursor tokens",
              C._WIN_SCAN_EXT["H"] in C.CURSOR_ROW_KEYS
              and C._WIN_SCAN_EXT["P"] in C.CURSOR_ROW_KEYS
              and C._WIN_SCAN_EXT["G"] in C.CURSOR_ENDS
              and C._WIN_SCAN_EXT["O"] in C.CURSOR_ENDS)
        check("paging stays on BOTH — NumLock on, or no numpad at all, still "
              "leaves a pane readable",
              C._WIN_SCAN_NUMPAD["I"] == C._WIN_SCAN_EXT["I"] == "PGUP"
              and C._WIN_SCAN_NUMPAD["Q"] == C._WIN_SCAN_EXT["Q"] == "PGDN")
        check("nothing scrolls sideways, so 4/6 mean the same on both",
              C._WIN_SCAN_NUMPAD["K"] == C._WIN_SCAN_EXT["K"] == "LEFT"
              and C._WIN_SCAN_NUMPAD["M"] == C._WIN_SCAN_EXT["M"] == "RIGHT")

    # VERTICAL MOVEMENT ACROSS A WRAPPED INPUT. Asserted against the ROW
    # RANGES rather than against magic indices: the wrap is at a WORD break,
    # so a hardcoded column is a statement about this sentence's spaces, not
    # about the movement — and the first version of these checks measured
    # `"x" * 60`, one unbreakable word, whose only break point is the space
    # inside the prompt itself.
    s_cur = C.AppState(6, 6)
    s_cur.circle.width = 30
    s_cur.circle.input_buf = ("the room is quieter than it was, and I want to "
                              "say why before it moves again")
    _pr = C._circle_prompt(s_cur)
    _rg = C._input_rows(_pr, s_cur.circle.input_buf, 30)
    _at = lambda row, col: _rg[row][0] + col - len(_pr)   # noqa: E731
    check("the sample input really does wrap onto three rows or more",
          len(_rg) >= 3)
    s_cur.circle.input_cursor = _at(-1, 4)
    eff = s_cur.handle_key("CUR_UP")
    check("dedicated Up moves the cursor one row up, same column, and redraws "
          "only the input",
          s_cur.circle.input_cursor == _at(-2, 4) and eff == "input")
    check("...and the pane did NOT scroll", not s_cur.circle.is_scrolled())
    s_cur.handle_key("CUR_DOWN")
    check("dedicated Down comes back down, same column",
          s_cur.circle.input_cursor == _at(-1, 4))
    s_cur.handle_key("CUR_DOWN")
    check("Down on the last row is a no-op, not a scroll",
          s_cur.circle.input_cursor == _at(-1, 4)
          and not s_cur.circle.is_scrolled())
    s_cur.circle.input_cursor = len(s_cur.circle.input_buf)
    s_cur.handle_key("CUR_UP")
    check("from the append cell, Up clamps to the last addressable column of "
          "the row above rather than running past its break",
          s_cur.circle.input_cursor <= _rg[-2][1] - 1 - len(_pr))
    s_cur.circle.input_cursor = 0
    s_cur.handle_key("CUR_UP")
    check("Up from the first row is a no-op", s_cur.circle.input_cursor == 0)
    s_cur.handle_key("CUR_END")
    check("dedicated End goes to the end of the whole input, not of its row",
          s_cur.circle.input_cursor == len(s_cur.circle.input_buf))
    s_cur.handle_key("CUR_HOME")
    check("...and Home to its start", s_cur.circle.input_cursor == 0)
    s_flat = C.AppState(6, 6)
    s_flat.circle.input_buf = "short"
    s_flat.circle.input_cursor = 2
    s_flat.circle.append("a line")
    s_flat.circle.append("another")
    s_flat.handle_key("CUR_UP")
    check("on an UNWRAPPED line with no history the arrows do nothing — they "
          "never fall back to scrolling, which is what having two clusters is for",
          s_flat.circle.input_cursor == 2 and not s_flat.circle.is_scrolled())
    check("while the numpad's own token still scrolls that same pane",
          s_flat.handle_key("UP") == "scroll" or s_flat.circle.is_scrolled())

    # THE INPUT HISTORY — the operator, 2026-09-14: *"the up and down arrows
    # (not the ones on the num pad, which are correct) will cycle upward
    # through up to 3 prior entries (and downward to empty or one currently
    # being constructed)."* Per pane, from what that pane submitted.
    s_h = C.AppState(6, 6)
    for n in range(1, 6):
        for ch in f"entry {n}\r":
            s_h.handle_key(ch)
    check("only the newest HISTORY_DEPTH entries are kept, oldest first",
          C.HISTORY_DEPTH == 3
          and s_h.circle.history == ["entry 3", "entry 4", "entry 5"])
    for ch in "draft":
        s_h.handle_key(ch)
    eff = s_h.handle_key("CUR_UP")
    check("Up on an unwrapped line brings back the previous entry, cursor at "
          "its end, redrawing only the input",
          s_h.circle.input_buf == "entry 5" and eff == "input"
          and s_h.circle.input_cursor == len("entry 5"))
    s_h.handle_key("CUR_UP")
    s_h.handle_key("CUR_UP")
    check("...and cycles upward through all three", s_h.circle.input_buf == "entry 3")
    s_h.handle_key("CUR_UP")
    check("Up at the oldest kept entry stays there — no wrap-around, no scroll",
          s_h.circle.input_buf == "entry 3" and not s_h.circle.is_scrolled())
    s_h.handle_key("CUR_DOWN")
    s_h.handle_key("CUR_DOWN")
    check("Down walks back toward the newest", s_h.circle.input_buf == "entry 5")
    s_h.handle_key("CUR_DOWN")
    check("Down past the newest restores the line that was being constructed",
          s_h.circle.input_buf == "draft" and s_h.circle.history_pos is None)
    s_h.handle_key("CUR_DOWN")
    check("...and a further Down is a no-op", s_h.circle.input_buf == "draft")
    for ch in "\r":
        s_h.handle_key(ch)
    s_h.handle_key("CUR_UP")
    check("a submitted draft becomes the newest entry", s_h.circle.input_buf == "draft")
    s_h.handle_key("CUR_DOWN")
    check("Down past the newest with no draft is empty", s_h.circle.input_buf == "")
    check("the numpad's own tokens are untouched: UP still scrolls, never recalls",
          s_h.handle_key("UP") == "scroll" and s_h.circle.input_buf == "")
    check("the command pane keeps its OWN history, empty until it submits",
          s_h.command.history == [] and s_h.handle_key("\t") == "focus"
          and s_h.handle_key("CUR_UP") == "input" and s_h.command.input_buf == "")
    for ch in "status\r":
        s_h.handle_key(ch)
    s_h.handle_key("CUR_UP")
    check("...and recalls what IT submitted", s_h.command.input_buf == "status")
    s_w = C.AppState(6, 6)
    s_w.circle.width = 30
    for ch in "before\r":
        s_w.handle_key(ch)
    s_w.circle.input_buf = ("the room is quieter than it was, and I want to "
                            "say why before it moves again")
    s_w.circle.input_cursor = len(s_w.circle.input_buf)
    s_w.handle_key("CUR_UP")
    check("inside a WRAPPED line Up moves a row first, not into history",
          s_w.circle.input_buf.startswith("the room") and s_w.circle.history_pos is None)
    s_w.circle.input_cursor = 0
    s_w.handle_key("CUR_UP")
    check("...and from its first row Up recalls, parking the wrapped draft",
          s_w.circle.input_buf == "before" and s_w.circle.draft.startswith("the room"))

    # PARKED AT A READ = EXIT AT ONCE — the operator, 2026-08-25: *"Exit at
    # once whenever the circle is waiting for input; keep waiting only while
    # a close or an API call is in flight."* The engine can only finish if
    # this UI answers it, and this UI has just been quit.
    class _ParkedEngine:
        def __init__(self, waiting: bool = True) -> None:
            self.live = True
            self.finished = threading.Event()
            self.waiting_for_input = waiting
            self.circle_in: "queue.Queue[str]" = queue.Queue()
            self.command_in: "queue.Queue[str]" = queue.Queue()

    out_lines.clear()
    fe5 = _ParkedEngine()
    C.ui_live_engine_wait(fe5, warn_after=30, out=out_lines.append)
    check("parked at a read: returns AT ONCE, without the 'waiting...' "
          "announcement",
          out_lines and "WAITING FOR YOU TO TYPE" in out_lines[0]
          and not any("still running" in ln for ln in out_lines))
    check("...and says the transcript is intact and the circle left open",
          "intact" in out_lines[0] and "OPEN" in out_lines[0])
    check("a line already queued is NOT parked — that line is about to "
          "become work", C._parked_on_read(fe5) and
          (fe5.circle_in.put("hello") or not C._parked_on_read(fe5)))
    check("a command-channel line queued counts the same",
          fe5.circle_in.get() == "hello" and C._parked_on_read(fe5)
          and (fe5.command_in.put("yes") or not C._parked_on_read(fe5)))
    check("mid-flight (no pending read) is NOT parked — it keeps waiting",
          not C._parked_on_read(_ParkedEngine(waiting=False)))
    check("a backend with none of these attributes reads NOT parked",
          not C._parked_on_read(_FakeEngine(live=True)))
    # PHASE-AWARE, 2026-09-15 — the operator, after quitting at cmd> while
    # the circle was still asking its working-set question: *"the message
    # is misdirecting."* Every read the open step makes precedes the
    # transcript mint, so an engine parked before the loop has written
    # nothing and left nothing open; the message must not say otherwise.
    fe6 = _ParkedEngine()
    fe6.loop_reached = False
    fe6.pending_prompt = "working set (issue ids, none, or all)"
    out_lines.clear()
    C.ui_live_engine_wait(fe6, warn_after=30, out=out_lines.append)
    check("parked BEFORE the loop: says still OPENING, no transcript, nothing "
          "left open — and names the question it was asking",
          out_lines and "OPENING" in out_lines[0]
          and "NO TRANSCRIPT" in out_lines[0]
          and "Nothing is left open" in out_lines[0]
          and "working set (issue ids, none, or all)" in out_lines[0]
          and "intact" not in out_lines[0]
          and "left OPEN" not in out_lines[0])
    fe7 = _ParkedEngine()
    fe7.loop_reached = True
    check("parked AT the loop: the transcript text, unchanged",
          C._parked_exit_text(fe7) == C._PARKED_EXIT)
    check("...and a backend without loop_reached reads as the loop",
          C._parked_exit_text(_ParkedEngine()) == C._PARKED_EXIT)

    # AND THE SECOND TEST, INSIDE THE WAIT: an engine that is working when
    # quit is typed, then comes back asking a question nobody can answer,
    # must exit there rather than move the wedge one step along.
    out_lines.clear()
    fe6 = _ParkedEngine(waiting=False)

    def _park_fe6_soon() -> None:
        time.sleep(0.05)
        fe6.waiting_for_input = True
    threading.Thread(target=_park_fe6_soon, daemon=True).start()
    C.ui_live_engine_wait(fe6, warn_after=30, out=out_lines.append)
    check("in flight at first, then parked: the wait notices and exits",
          any("WAITING FOR YOU TO TYPE" in ln for ln in out_lines)
          and not any("finished" in ln for ln in out_lines))

    # --- CircleEngine._read_line: circle.py's own CONSOLE_NAME-style
    # plain speaking prompt is suppressed (circling already draws an
    # equivalent "Self> " input-row prompt); every other prompt — the
    # working-set question, the topic question, a yes/no confirmation —
    # still echoes, since those carry real content. Reported live: a
    # bare duplicate prompt row landing right above the real "Self> "
    # input row on every single turn. -----------------------------
    eng4 = C.CircleEngine(queue.Queue())
    plain_prompt = f"\n{eng4._C.circle_prompt_read()}"     # circle.py's own Self-turn prompt (R563)
    holder: dict[str, str] = {}

    def _blocked_read(prompt: str, channel: str = "circle") -> None:
        # channel="circle" by default: every prompt this block exercises
        # (the speaking turn, the topic question) is circle channel under
        # R221, and _read_line's own default is "command".
        holder["result"] = eng4._read_line(prompt, channel)

    t = threading.Thread(target=_blocked_read, args=(plain_prompt,))
    t.start()
    eng4.circle_in.put("a statement")
    t.join(timeout=2)
    check("circle.py's own plain speaking prompt is NOT echoed into the "
          "pane — circling already shows an equivalent 'Self> ' row",
          eng4.out_queue.empty() and holder["result"] == "a statement")

    # SINCE 2026-08-21 A CIRCLE-CHANNEL QUESTION IS NOT ECHOED EITHER (the operator:
    # the scrollback line was redundant to the prompt row that carries it);
    # what the probe pins now is that the question OWNS THE ROW while the
    # read waits, and that nothing lands in scrollback.
    seen: dict[str, str] = {}

    def _blocked_read_watching(prompt: str, channel: str = "circle") -> None:
        holder["result"] = eng4._read_line(prompt, channel)

    t2 = threading.Thread(target=_blocked_read_watching,
                           args=("\nCIRCLE topic (blank = open): ",))
    t2.start()
    for _ in range(200):
        if eng4.waiting_for_input:
            break
        time.sleep(0.005)
    seen["row"] = eng4.pending_prompt
    eng4.circle_in.put("")
    t2.join(timeout=2)
    check("a circle-channel QUESTION (the topic prompt) is NOT echoed into "
          "scrollback — the row carries it (2026-08-21)",
          eng4.out_queue.empty() and holder["result"] == "")
    check("...and the question owned the input row while the read waited",
          seen["row"] == "CIRCLE topic (blank = open):")

    circle_src = (C.COORD_DIR / "circle.py").read_text(encoding="utf-8")
    check("circle.py's own Self-turn read_line call still has the exact "
          "shape this suppression assumes — catches drift if that call "
          "site ever changes format",
          'cmd = read_line(f"\\n{circle_prompt_read()}", channel="circle").strip()'
          in circle_src)                      # R563: the prompt is circle_prompt_read()'s

    # --- RULED 2026-08-13: only one prompt, and it names CONSOLE_NAME —
    # _circle_prompt() must derive from circle.py's own attribute, not a
    # second hardcoded literal that can silently disagree with it the
    # moment IFS_USER_NAME is set to anything other than the default. ---
    eng7 = C.CircleEngine(queue.Queue())
    s7 = C.AppState(4, 4, backend=eng7)
    check("circle-pane prompt reads circle.py's own CONSOLE_NAME, not a "
          "second hardcoded literal (shown waiting/opening — eng7 was never "
          "started, so waiting_for_input is still False)",
          C._circle_prompt(s7)
          == f"{eng7._C.circle_prompt_read()[:-2]} (waiting — opening the circle)> ")
    eng7.waiting_for_input = True
    check("...and drops the (waiting) suffix once actually parked at "
          "read_line — same name either way",
          C._circle_prompt(s7) == eng7._C.circle_prompt_read())

    # --- waiting_for_input: the replacement signal for the suppressed
    # echo above. True only while the background thread is actually
    # parked in read_line(); the render layer (_circle_prompt) reflects
    # this so a user can tell "will my Enter be read right now" without
    # the duplicate prompt row. -----------------------------------------
    eng5 = C.CircleEngine(queue.Queue())
    check("not waiting before any read_line has been reached",
          eng5.waiting_for_input is False)

    seen_waiting: dict[str, bool] = {}

    def _blocked_read_observing(prompt: str, channel: str = "circle") -> None:
        holder["result"] = eng5._read_line(prompt, channel)

    t3 = threading.Thread(target=_blocked_read_observing, args=(plain_prompt,))
    t3.start()
    for _ in range(200):                      # wait for the thread to block
        if eng5.waiting_for_input:
            break
        time.sleep(0.005)
    seen_waiting["mid"] = eng5.waiting_for_input
    eng5.circle_in.put("a statement")
    t3.join(timeout=2)
    check("waiting_for_input is True while genuinely blocked in read_line",
          seen_waiting["mid"] is True)
    check("waiting_for_input clears again once unblocked",
          eng5.waiting_for_input is False)

    # --- _circle_prompt: what the render layer actually shows ----------
    demo_state = C.AppState(circle_height=3, command_height=3)  # backend=None
    check("no backend (demo path) — always the plain prompt, unaffected",
          C._circle_prompt(demo_state) == "Self> ")

    busy_state = C.AppState(circle_height=3, command_height=3, backend=eng5)
    check("a real engine NOT yet blocked in read_line shows as busy, "
          "named from CONSOLE_NAME (not necessarily 'Self' — whatever "
          "IFS_USER_NAME is set to; eng5's speaking turn above set "
          "loop_reached, so the busy state names the parts)",
          C._circle_prompt(busy_state)
          == f"{eng5._C.circle_prompt_read()[:-2]} (waiting — the parts are replying)> ")

    eng5.waiting_for_input = True
    check("a real engine genuinely blocked in read_line shows the plain "
          "prompt, same name — safe to type, it will be read now",
          C._circle_prompt(busy_state) == eng5._C.circle_prompt_read())

    # --- Regression: body text and cursor column must come from the SAME
    # read of waiting_for_input, not two independent ones. Reported live:
    # the body showed "Self (waiting)> " while the cursor sat at the column
    # "Self> " would have used — right before the "w" — because the flag
    # flipped between the two reads. A backend whose flag toggles on
    # EVERY access pins this down: render_input_line must draw the body
    # and place the cursor from one shared value, or they will disagree
    # every single call (not just occasionally, as the live race did). --
    class _TogglingBackend:
        def __init__(self) -> None:
            self._n = 0

        @property
        def waiting_for_input(self) -> bool:
            self._n += 1
            return self._n % 2 == 1

    tb_state = C.AppState(circle_height=3, command_height=3,
                        backend=_TogglingBackend())
    tb_state.focus = "circle"
    tb_out: list[str] = []
    C.ui_input_line_render(tb_state, tb_out.append)
    tb_blob = "".join(tb_out)
    long_prompt, short_prompt = "Self (waiting)> ", "Self> "
    used_long = long_prompt in tb_blob
    expected_len = len(long_prompt if used_long else short_prompt)
    cursor_cols = re.findall(r"\x1b\[\d+;(\d+)H", tb_blob)
    check("render_input_line's cursor column matches whichever prompt it "
          "actually drew, even when the backend's flag toggles on every "
          "read — proves body and cursor share ONE read, not two",
          cursor_cols and int(cursor_cols[-1]) == expected_len + 1)

    # --- R221: the CHANNEL split. A command-channel read must ask in the
    # COMMAND pane and be answered from it, because docs/BNF.md line 105
    # keeps RATIFICATION_DIALOG (and every other Coordinator->Self
    # exchange) out of the circle entirely. Before this, _read_line put
    # EVERY prompt on "circle" and drained circle_in, so vetting asked in
    # the circle pane while the proposal being ruled on sat in command —
    # and answering where you were reading returned "not understood". ---
    eng8 = C.CircleEngine(queue.Queue())
    vet_prompt = "  [BP-7] a)pprove, d)eny, s)kip ? "
    held: dict[str, str] = {}

    def _vet_read() -> None:
        held["answer"] = eng8._read_line(vet_prompt)      # default = command

    t8 = threading.Thread(target=_vet_read)
    t8.start()
    for _ in range(200):                                  # wait to park
        if eng8.waiting_for_input:
            break
        time.sleep(0.005)
    # THE QUESTION RIDES THE cmd> ROW, NOT SCROLLBACK — 2026-08-21, the
    # lab's finding 1, the operator: "overload the prompt instead". Until then
    # this check asserted ("command", vet_prompt) was QUEUED for the pane
    # — the question as a scrollback line above a row that still said
    # "cmd> ". Nothing is queued now; pending_prompt holds the question
    # and _command_prompt renders it as the input row.
    check("a command-channel read_line puts NOTHING in the command pane's "
          "scrollback — the question is the input row, not a line above it",
          eng8.out_queue.empty())
    check("...and holds the question, stripped, for the row",
          eng8.pending_prompt == vet_prompt.strip())
    s8 = C.AppState(4, 4, backend=eng8)
    check("...which _command_prompt renders as the cmd> row while it waits",
          C._command_prompt(s8) == vet_prompt.strip() + " ")
    check("...while the circle row shows (waiting) — and NAMES the other "
          "pane as what it waits on (D62 a)",
          "(waiting — a question below in COMMANDS)" in C._circle_prompt(s8))
    check("...and records which channel it is waiting on",
          eng8.waiting_for_channel == "command")
    check("...and is NOT the speaking turn, so a bare Enter still means "
          "'answer', not 'catch me up'",
          eng8.speaking_turn is False)

    # PROBE 2: the answer forwards VERBATIM, ahead of every dispatch path.
    # "/StAtEmEnTs" must NOT become "/statements" (submit_command's normal
    # `head + rest_of_line` reconstruction), and "abort" must NOT be
    # intercepted — as the local verb it was, or as the circle-pane verb
    # it is since 2026-08-31 — RULED: a pending question owns the pane,
    # forward everything.
    check("a line typed at the command pane while a command read is "
          "pending forwards VERBATIM, not through the dispatcher",
          eng8.submit_command("/StAtEmEnTs") is None
          and eng8.command_in.get_nowait() == "/StAtEmEnTs")
    check("...and nothing was queued to circle_in by that forward",
          eng8.circle_in.empty())
    eng8.submit_command("abort")
    check("...and even a local verb forwards verbatim rather than being "
          "intercepted — interception is how 'abort' used to be swallowed",
          eng8.command_in.get_nowait() == "abort")
    eng8.submit_command("a")
    t8.join(timeout=2)
    check("the command pane's answer is what the blocked read returns",
          held.get("answer") == "a")
    check("waiting_for_channel resets once the read unblocks",
          eng8.waiting_for_input is False
          and eng8.waiting_for_channel == "circle")
    check("...and the cmd> row is 'cmd> ' again the moment the read "
          "returns — 'restore after a valid reply'",
          C._command_prompt(s8) == "cmd> ")

    # PROBE 3: the empty-Enter carve-out. proposal_vetting.py offers "(or Enter to
    # skip)" and the working-set/topic prompts are both "blank = ..." —
    # all three were unreachable while handle_key dropped whitespace-only
    # lines before the seam. The carve-out must NOT extend to the speaking
    # turn, which is circle channel AND the steady state of a running circle.
    eng9 = C.CircleEngine(queue.Queue())
    s9 = C.AppState(4, 4, backend=eng9)
    s9.focus = "command"
    eng9.waiting_for_input, eng9.waiting_for_channel = True, "command"
    check("_answering is True for the pane a pending command read drains",
          s9._answering(s9.command) is True)
    check("...and False for the other pane",
          s9._answering(s9.circle) is False)
    s9.handle_key("\r")                                   # bare Enter
    check("a bare Enter reaches the seam while a command read is pending "
          "— this is vetting's '(or Enter to skip)', unreachable before",
          eng9.command_in.get_nowait() == "")

    eng9.waiting_for_channel, eng9.speaking_turn = "circle", True
    s9.focus = "circle"
    check("_answering is False on Self's speaking turn, even though it IS "
          "circle channel and pending — a bare Enter there still means "
          "'catch me up', per the affordance at handle_key",
          s9._answering(s9.circle) is False)
    s9.handle_key("\r")
    check("...so nothing is posted, and the pane is not disturbed",
          eng9.circle_in.empty())

    check("_answering is False with no backend at all — the demo and "
          "self-test path must behave exactly as it did before R221",
          C.AppState(4, 4)._answering(C.AppState(4, 4).circle) is False)

    # --- THE MIRROR EDGE, 2026-08-21: a line typed into the ROOM while a
    # COMMAND-channel question is pending BEFORE the Self> loop exists would
    # sit on circle_in until the next circle-channel read — the working-set
    # question — and become the working set, the same way a cmd> line did
    # in the other direction. Refused with the question named; once the
    # loop is reached, speech is queued as it always was. -----------------
    eng10 = C.CircleEngine(queue.Queue())
    s10 = C.AppState(4, 4, backend=eng10)
    eng10.waiting_for_input, eng10.waiting_for_channel = True, "command"
    eng10.pending_prompt = "[BP-7] a)pprove, d)eny, s)kip ?"
    s10._submit(s10.circle, "hello room")
    check("circle-pane speech while a command-channel question is pending "
          "BEFORE the loop is refused — nothing reaches circle_in",
          eng10.circle_in.empty())
    check("...the notice lands in the COMMAND pane and names the question",
          any("a)pprove" in ln for ln in s10.command.lines))
    check("...and the room shows no '[You]:' echo for it",
          not any(ln.startswith("[You]:") for ln in s10.circle.lines))
    eng10.loop_reached = True
    s10._submit(s10.circle, "hello room")
    check("the same line AFTER the loop is reached is queued as speech — "
          "mid-circle statements during a pending ruling are untouched "
          "(ruled 2026-08-20)",
          eng10.circle_in.get_nowait() == "hello room"
          and s10.circle.lines[-1] == "[You]: hello room")

    # --- _command_prompt: the cmd> row's text, 2026-08-21 -----------------
    check("_command_prompt: no backend — the plain 'cmd> '",
          C._command_prompt(C.AppState(4, 4)) == "cmd> ")
    eng11 = C.CircleEngine(queue.Queue())
    s11 = C.AppState(4, 4, backend=eng11)
    eng11.waiting_for_input, eng11.waiting_for_channel = True, "circle"
    eng11.pending_prompt = "CIRCLE topic (blank = open):"
    check("_command_prompt: a pending CIRCLE-channel question leaves the cmd> "
          "row alone — it belongs to the other pane",
          C._command_prompt(s11) == "cmd> ")
    eng11.waiting_for_channel = "command"
    eng11.pending_prompt = "type 'yes' to apply:"
    check("_command_prompt: a pending COMMAND-channel question IS the row",
          C._command_prompt(s11) == "type 'yes' to apply: ")
    eng11.waiting_for_input = False
    check("_command_prompt: 'cmd> ' is back the moment nothing is pending",
          C._command_prompt(s11) == "cmd> ")
    chrome11: list[str] = []
    C.ui_chrome_render(s11, 80, chrome11.append)
    check("the status line no longer says '(grows to 4/5ths)' (2026-08-21)",
          "4/5ths" not in "".join(chrome11) and "[Tab] pane" in "".join(chrome11))

    # --- append() splits embedded newlines into separate rows -----------
    # Regression for a real bug: circle.py's read_line prompts and many
    # emit() calls carry a leading/embedded "\n" (a plain-terminal
    # spacer convention) that broke the fixed-row renderer — see
    # Pane.append's docstring.
    p0 = C.Pane("T", "t> ", height=4)
    p0.append("\nCIRCLE issues (blank = all): ")
    check("a leading \\n becomes its own (blank) row, not lost",
          p0.lines == ["", "CIRCLE issues (blank = all): "])
    p0.append("a\nb\nc")
    check("multiple embedded \\n become multiple rows",
          p0.lines[-3:] == ["a", "b", "c"])
    p0.append("plain, no newline")
    check("a plain line is still exactly one row",
          p0.lines[-1] == "plain, no newline")

    # WRAPPING, 2026-08-20. The body wrote `text[:width]` and TRUNCATED: a
    # statement longer than the terminal was cut and the remainder was never
    # on screen at all, which is why resizing did not bring it back. the operator
    # found it in the first live lab circle.
    print("\n  wrapping — nothing leaves the screen, and a resize reflows")
    check("no width means no wrapping — a bare Pane is unchanged",
          C.ui_line_wrap("x" * 99, None) == ["x" * 99])
    check("a line that fits is returned untouched",
          C.ui_line_wrap("exactly twenty chars", 20) == ["exactly twenty chars"])
    check("a long line breaks on spaces, never mid-word",
          all(len(r) <= 24 for r in C.ui_line_wrap(
              "[Alpha]: a long statement that must wrap", 24)))
    check("...and loses nothing — the words come back in order",
          " ".join(C.ui_line_wrap("[Alpha]: a long statement that must wrap", 24)).split()
          == "[Alpha]: a long statement that must wrap".split())
    check("the continuation carries the source line's own indent, so an "
          "indented block does not fall back under a label column",
          [r[:4] for r in C.ui_line_wrap("    focus n0021 and a long tail here", 22)]
          == ["    ", "    "])
    check("a word longer than the width is CUT rather than left to overflow",
          C.ui_line_wrap("a" * 30, 12) == ["a" * 12, "a" * 12, "a" * 6])
    check("an empty line stays one empty row — a spacer is still a spacer",
          C.ui_line_wrap("", 20) == [""])

    pw = C.Pane("c", "> ", 10)
    pw.set_width(20)
    pw.append("one two three four five six seven")
    check("append wraps at the pane's width", len(pw.lines) > 1)
    check("...and the SOURCE line is kept whole for re-wrapping",
          pw.logical == ["one two three four five six seven"])
    wide = len(pw.lines)
    pw.set_width(80)
    check("widening REFLOWS rather than re-truncating — fewer rows, same text",
          len(pw.lines) < wide and pw.lines == ["one two three four five six seven"])
    pw.set_width(20)
    check("narrowing reflows back", len(pw.lines) == wide)
    check("set_width is idempotent — the same width does not rebuild",
          (pw.set_width(20), pw.lines == pw.lines)[1])

    # --- THE STILL-WORKING ROW (2026-09-16; its ruling cites this suite) ----------
    # The operator: *"stack '… still working' as Claude code does? By cycling the
    # initial character"*, and *"Still working vanishes after."* One row per wait,
    # its glyph turning in place, gone when anything else is said or the program
    # stops to wait for an answer.
    print("\n  the still-working row — one row, a turning glyph, gone when the wait ends")
    _circle_src = (C.COORD_DIR / "circle.py").read_text(encoding="utf-8")
    PL = C.ui_progress_line_read()
    check("the pane reads the beat's line from its one home, command_surface — the match "
          "is exact, so a second copy that drifted would silently stack again",
          PL is not None and PL == C._command_surface().PROGRESS_LINE)
    check("...and circle.py sends that same constant to the command pane, not a literal",
          'emit("command", CS.PROGRESS_LINE)' in _circle_src)
    pg = C.Pane("cmd", "cmd> ", 6)
    pg.append("  something the program said")
    for _ in range(3):
        pg.append(PL)
    check("three beats in a row make ONE row, not a stack",
          pg.logical.count(PL) == 1 and len(pg.lines) == 2)
    check("...drawn as the first glyph and 'still working…', never the beat's own text",
          pg.lines[-1] == f"  {C.PROGRESS_FRAMES[0]} still working…" and pg.progress)
    pg.progress_advance()
    check("a frame turns the glyph IN PLACE — same row count, the next glyph",
          len(pg.lines) == 2 and pg.lines[-1] == f"  {C.PROGRESS_FRAMES[1]} still working…")
    for _ in range(len(C.PROGRESS_FRAMES) - 1):
        pg.progress_advance()
    check("...and the frames cycle back to the first", pg.progress_frame == 0)
    pg.set_width(40)
    check("a resize rebuilds the row as the glyph, not as the beat's text",
          pg.lines[-1].endswith("still working…") and PL not in pg.lines)
    pg.append("  the next real line")
    check("any other line ends the wait: the row is GONE, not left behind",
          not pg.progress and PL not in pg.logical
          and pg.lines == ["  something the program said", "  the next real line"])
    check("...and a pane with no row has nothing to turn", pg.progress_advance() is False)

    sp = C.AppState(6, 6)
    check("a beat lands in the command pane and says it changed it",
          C.ui_output_append(sp, "command", PL) and sp.command.progress)
    check("a line in the CIRCLE pane ends the wait too, and reports the command "
          "pane changed", C.ui_output_append(sp, "circle", "[Soul]: a statement")
          and not sp.command.progress and sp.circle.lines[-1] == "[Soul]: a statement")

    class _Waiting:
        waiting_for_input = False
    sw = C.AppState(6, 6, backend=_Waiting())
    sw.command.append(PL)
    check("while the program is working and not waiting, the row stays",
          C.ui_progress_wait_ended(sw, finished=False) is False and sw.command.progress)
    sw.backend.waiting_for_input = True
    check("once it waits for an answer, the row is dropped",
          C.ui_progress_wait_ended(sw, finished=False) and not sw.command.progress)
    sw.backend.waiting_for_input = False
    sw.command.append(PL)
    check("...and once it has ended", C.ui_progress_wait_ended(sw, finished=True)
          and not sw.command.progress)

    check("a bare Windows console gets plain glyphs — it draws a dingbat as a box",
          C.ui_progress_frames_read({}, "win32") == C.PROGRESS_FRAMES_PLAIN)
    check("...Windows Terminal gets the dingbats",
          C.ui_progress_frames_read({"WT_SESSION": "x"}, "win32") == C.PROGRESS_FRAMES)
    check("...and so does every other platform",
          C.ui_progress_frames_read({}, "linux") == C.PROGRESS_FRAMES)

    for _few in (1, 12):                  # fewer lines than the pane holds, and more
        sr = C.AppState(6, 6)
        for _i in range(_few):
            sr.command.append(f"  line {_i} before the wait")
        sr.command.append(PL)
        _painted: list[str] = []
        C.ui_pane_render(sr, "command", 80, _painted.append)
        _row0 = [t for t in _painted if t.endswith(f"  {C.PROGRESS_FRAMES[0]} still working…")]
        _frame: list[str] = []
        C.ui_progress_frame_render(sr, 80, _frame.append)
        check(f"{_few} line(s) above: a frame writes ONE row, not the pane body",
              len(_frame) == 1 and _frame[0].count(C.CLR_LINE) == 1
              and _frame[0].endswith(f"  {C.PROGRESS_FRAMES[1]} still working…"))
        check(f"{_few} line(s) above: ...on the very screen row the body drew it on",
              len(_row0) == 1 and bool(_frame)
              and _frame[0].split(C.CLR_LINE)[0] == _row0[0].split(C.CLR_LINE)[0])
        check(f"{_few} line(s) above: ...and records it as painted, so the next drain "
              "does not repaint the body", not sr.command.body_needs_repaint(
                  C._input_geometry(sr, "command", C._command_prompt(sr), 80)["k"]))
    sr.command.line_up()
    _scrolled: list[str] = []
    C.ui_progress_frame_render(sr, 80, _scrolled.append)
    check("scrolled away from the live edge, a frame draws no single row — the "
          "body's own freeze decides", sr.command.is_scrolled() and not any(
              t.endswith("still working…") and t.count(C.CLR_LINE) == 1 for t in _scrolled))

    # --- set_redact: toggling is architecturally a resize (2026-08-31) --
    sys.path.insert(0, str(C.COORD_DIR))   # _command_surface()'s own pattern
    import redaction_manager as _RDX
    import stream_redaction as _SR
    import tempfile as _tempfile
    _live_alias, _live_map = _RDX.ALIAS_PATH, _RDX.MAP_PATH
    with _tempfile.TemporaryDirectory() as _td:
        _RDX.ALIAS_PATH = pathlib.Path(_td) / "redaction.toml"
        _RDX.MAP_PATH = pathlib.Path(_td) / "redaction_map.toml"
        _SR._alias_cache.update(mtime="unread", re=None, form_to_row={})
        _RDX.alias_add("Alice Smith", "person", ["Alice"])

        pr = C.Pane("c", "> ", 10)
        pr.set_width(40)
        pr.append("Alice Smith walked in.")
        before = list(pr.lines)
        check("redact_view starts off", not pr.redact_view)
        check("unredacted by default", "Alice Smith" in before[0])

        pr.set_redact(True)
        check("toggling ON redacts an ALREADY-SHOWN line, not only future "
              "ones — the whole point of sharing _rebuild() with resize",
              "Alice Smith" not in pr.lines[0] and "P1" in pr.lines[0])
        check(".logical (the record) is untouched by redaction",
              pr.logical == ["Alice Smith walked in."])

        pr.set_redact(True)
        check("set_redact is idempotent — the same flag does not rebuild",
              pr.lines == pr.lines)

        pr.set_redact(False)
        check("toggling OFF restores the original rendering",
              pr.lines == before)

        for n in range(8):
            pr.append(f"Alice Smith line {n}, long enough to wrap at 40")
        pr.height = 3
        pr.scroll_top = pr._max_top()   # pin to the current bottom-most top
        wide_lines, wide_top = len(pr.lines), pr.scroll_top
        pr.set_redact(True)             # "P1" is shorter -> fewer rows
        check("redacting shrank the row count (shorter token, same lines)",
              len(pr.lines) < wide_lines)
        check("an out-of-range scroll_top clamps under set_redact exactly "
              "as it does under set_width/resize — same _rebuild(), same "
              "clamp, never left pointing past the new end",
              pr.scroll_top <= pr._max_top())
        check("...and it actually WOULD have been out of range unclamped "
              "— the test is real, not vacuously true",
              wide_top > pr._max_top())
        pr.set_redact(False)
        check("toggling back restores the wider row count",
              len(pr.lines) == wide_lines)
    _RDX.ALIAS_PATH, _RDX.MAP_PATH = _live_alias, _live_map
    _SR._alias_cache.update(mtime="unread", re=None, form_to_row={})

    # --- Scrolling: Pane-level, direct (no AppState involved) -----------
    p = C.Pane("T", "t> ", height=4)
    for n in range(10):
        p.append(f"line {n}")
    check("following by default shows the tail",
          p.visible() == ["line 6", "line 7", "line 8", "line 9"])
    check("not scrolled while following", not p.is_scrolled())

    p.line_up(2)
    check("line_up(2) moves the view up by two",
          p.visible() == ["line 4", "line 5", "line 6", "line 7"])
    check("is_scrolled once scroll_top is set", p.is_scrolled())

    p.append("line 10")
    check("a new line while scrolled does NOT move the pinned view",
          p.visible() == ["line 4", "line 5", "line 6", "line 7"])
    check("hidden_below counts what's below the pinned view",
          p.hidden_below() == 3)   # lines 8, 9, 10 are below "line 7"
    check("hidden_above counts what's above the pinned view",
          p.hidden_above() == 4)   # lines 0, 1, 2, 3 are above "line 4"

    p2 = C.Pane("T2", "t2> ", height=4)
    for n in range(6):
        p2.append(f"x{n}")
    check("hidden_above is nonzero even while following, if scrollback "
          "exceeds the pane height", p2.hidden_above() == 2)

    p.jump_top()
    check("jump_top pins to the very first line",
          p.visible()[0] == "line 0")

    p.jump_bottom()
    check("jump_bottom resumes following",
          not p.is_scrolled() and p.visible()[-1] == "line 10")

    p.line_up(1)
    p.page_down()
    check("page_down past the live edge resumes following",
          not p.is_scrolled())

    # --- Scrolling: routed through AppState, to the FOCUSED pane only ---
    s2 = C.AppState(circle_height=3, command_height=3)
    for n in range(8):
        s2.circle.append(f"c{n}")
    for n in range(8):
        s2.command.append(f"m{n}")
    # focus is circle (default) — UP must move circle, not command
    s2.handle_key("UP")
    check("UP with circle focused scrolls circle, not command",
          s2.circle.is_scrolled() and not s2.command.is_scrolled())

    s2.toggle_focus()
    s2.handle_key("PGUP")
    check("PGUP with command focused scrolls command, not the already-"
          "scrolled circle pane (each pane's position is independent)",
          s2.command.is_scrolled() and s2.circle.is_scrolled())

    effect = s2.handle_key("DOWN")
    check("a named scroll token is never appended as literal text",
          s2.command.input_buf == "")
    check("a named scroll token returns the 'scroll' effect tag",
          effect == "scroll")

    # --- Scrolling away from the live edge IS the freeze — verified at
    # the mechanism level, not just at visible(). Proven end to end
    # through the renderer: body content that arrives while scrolled must
    # not reach the screen; the header's live count must, and the body
    # must catch up, intact, once scrolled back to the live edge. --------
    s3 = C.AppState(circle_height=3, command_height=3)
    for n in range(6):                    # more than the height, or there's
        s3.circle.append(f"before-scroll-{n}")   # nothing to scroll away to
    out0: list[str] = []
    C.ui_full_render(s3, width=80, write=out0.append)   # first paint, establishes _painted

    s3.handle_key("UP")
    check("scrolling away from the live edge sets is_scrolled",
          s3.circle.is_scrolled())
    scrolled_out: list[str] = []
    C.ui_pane_render(s3, "circle", width=80, write=scrolled_out.append)  # paints
    check("that scroll got painted once — the view actually moved",
          "".join(scrolled_out).strip() != "")

    check("with the scrolled view now painted, nothing pending changed it",
          not s3.circle.body_needs_repaint())

    s3.circle.append("during-scroll — should not reach the screen yet")
    check("appending while scrolled does NOT flip body_needs_repaint — "
          "this IS the freeze, no separate toggle needed",
          not s3.circle.body_needs_repaint())
    out1: list[str] = []
    C.ui_pane_render(s3, "circle", width=80, write=out1.append)
    blob1 = "".join(out1)
    check("header updates immediately (the live count)",
          "above" in blob1 or "below" in blob1 or "scrolled" in blob1)
    check("body content that arrived while scrolled is NOT drawn",
          "during-scroll" not in blob1)

    s3.handle_key("END")   # back to the live edge
    check("End resumes following", not s3.circle.is_scrolled())
    out2b: list[str] = []
    C.ui_pane_render(s3, "circle", width=80, write=out2b.append)
    blob2b = "".join(out2b)
    check("on catching up, the line that arrived while scrolled is now "
          "shown, intact — nothing was lost", "during-scroll" in blob2b)

    # --- A bare Enter (empty input) is a second way to catch up, next to
    # End — it posts nothing but still reflows to the live edge, for
    # whichever pane is focused. -------------------------------------------
    s6 = C.AppState(circle_height=3, command_height=3)
    for n in range(6):
        s6.circle.append(f"before-{n}")
    s6.handle_key("UP")
    check("scrolled away, as the setup for this check",
          s6.circle.is_scrolled())
    s6.circle.append("arrived-while-scrolled")
    effect = s6.handle_key("\r")               # bare Enter, input_buf is ""
    check("a bare Enter on an empty line posts nothing",
          s6.circle.lines[-1] == "arrived-while-scrolled")
    check("but it DOES resume following, same as End",
          not s6.circle.is_scrolled())
    check("and it's reported as a 'scroll' effect so the pane repaints",
          effect == "scroll")
    out6: list[str] = []
    C.ui_pane_render(s6, "circle", width=80, write=out6.append)
    check("the repaint actually shows the line that arrived while scrolled",
          "arrived-while-scrolled" in "".join(out6))

    s7 = C.AppState(circle_height=3, command_height=3)
    s7.circle.append("only-one-line")            # nothing to scroll away to
    effect7 = s7.handle_key("\r")
    check("a bare Enter while already following stays the cheap no-op it "
          "always was — no false 'scroll' effect from a following pane",
          effect7 == "input" and not s7.circle.is_scrolled())

    # --- Paste batching: read_burst groups a fast-arriving run of
    # characters into ONE text unit instead of N, and treats an Enter
    # mid-burst as paste content, not a submit. Uses an injected `poll` so
    # this needs no real stdin. -------------------------------------------
    fake_stream = iter(["b", "c", " ", "d"])
    units = C.ui_burst_read("a", poll=lambda: next(fake_stream, None))
    check("a burst of plain characters becomes ONE 'text' unit",
          units == [("text", "abc d")])

    fake_stream2 = iter([])
    units2 = C.ui_burst_read("\r", poll=lambda: next(fake_stream2, None))
    check("a standalone Enter (nothing buffered behind it) is a real "
          "'key' unit, never batched", units2 == [("key", "\r")])

    fake_stream3 = iter(["i", "\n", "n", "e", "2"])
    units3 = C.ui_burst_read("l", poll=lambda: next(fake_stream3, None))
    check("a CR/LF encountered MID-burst (a multi-line paste) becomes a "
          "space inside the batch, not a submit",
          units3 == [("text", "li ne2")])

    fake_stream4 = iter(["b", "\t", "c"])
    units4 = C.ui_burst_read("a", poll=lambda: next(fake_stream4, None))
    check("a control key mid-burst ends the current batch and is its own "
          "unit, in order, without losing what came after it",
          units4 == [("text", "ab"), ("key", "\t"), ("text", "c")])

    # --- THE TWO PLATFORM ARMS, COMPARED WITHOUT RUNNING EITHER (audit #16). ------
    # ui/circling.py's `if IS_WINDOWS:` split means ~90 lines of the POSIX arm are dark
    # by construction on this host: its raw_mode uses termios, and _read_escape reads real
    # stdin through select, which on Windows works only on sockets. It SHIPS — the export
    # bundle goes to Inner-Circler/Inner-Circling and circling.py is a packaging entry
    # point since R314 — so a recipient on Linux or macOS runs code nothing here executes.
    #
    # What IS checkable anywhere is the CONTRACT BETWEEN THE ARMS, read off the AST: a
    # name added to one arm and forgotten in the other, and a key one platform can emit
    # that the other cannot handle. That is the realistic regression; executing termios
    # is not.
    import ast as _ast
    _src = pathlib.Path(C.__file__).read_text(encoding="utf-8")
    _split = [n for n in _ast.parse(_src).body
              if isinstance(n, _ast.If) and isinstance(n.test, _ast.Name)
              and n.test.id == "IS_WINDOWS"]
    check("ui/circling.py still has exactly one module-level `if IS_WINDOWS:` split",
          len(_split) == 1)
    if _split:
        def _defined(body):
            out = set()
            for n in body:
                if isinstance(n, (_ast.FunctionDef, _ast.ClassDef)):
                    out.add(n.name)
                elif isinstance(n, _ast.Assign):
                    out.update(t.id for t in n.targets if isinstance(t, _ast.Name))
            return out

        def _key_vocab(body):
            out = set()
            for n in body:
                if isinstance(n, _ast.Assign) and isinstance(n.value, _ast.Dict):
                    out.update(v.value for v in n.value.values
                               if isinstance(v, _ast.Constant))
            return out

        _win, _posix = _defined(_split[0].body), _defined(_split[0].orelse)
        _pub = lambda s: {n for n in s if not n.startswith("_")}   # noqa: E731
        check("both platform arms define the SAME public surface — a backend added to one "
              "and forgotten in the other is what this catches",
              _pub(_win) == _pub(_posix) == {"enable_vt_mode", "poll_key", "raw_mode"})

        # THE POSIX VOCABULARY MOVED OUT OF ITS ARM, 2026-09-09, under the "yes split"
        # ruling: POSIX_ESC is module-level now precisely so it can be asserted on
        # Windows, which means the else-arm no longer carries a dict literal at all and
        # an AST-only read of it returns the empty set. Reading the real object is the
        # stronger check anyway — it cannot drift from what the code actually looks up,
        # where a source-shape read can. The arm is still scanned, so a table added back
        # inside it would still be counted rather than silently ignored.
        _wv = _key_vocab(_split[0].body)
        _pv = set(C.POSIX_ESC.values()) | _key_vocab(_split[0].orelse)
        check("no key the POSIX arm emits is unknown to the win32 arm", not (_pv - _wv))
        # THE ONE ASYMMETRY IS DELIBERATE, so it is pinned rather than merely allowed:
        # ui/circling.py:500-509 says the dedicated cursor cluster is emitted "only where
        # the two key clusters can be told apart, which today is Windows alone (\xe0 vs
        # \x00); no POSIX terminal distinguishes the numpad". If that set ever changes,
        # this fails and the comment has to change with it.
        check("...and the only keys win32 can emit that POSIX cannot are exactly the "
              "documented cursor cluster",
              (_wv - _pv) == set(C.CURSOR_ROW_KEYS) | set(C.CURSOR_ENDS))

    # --- enable_vt_mode's WINDOWS BODY, executed (audit-register 2026-09-09 #29). --
    # The key layer's exemption above is correct and stays: the POSIX arm is UNDEFINED
    # in this process, so no fake can reach it and the honest close is a Linux runner,
    # which this project's local-only constraint does not have. But the exemption was
    # covering one thing it did not have to: enable_vt_mode's win32 body was 0 of 9
    # statements ON WINDOWS, where it is perfectly reachable — it just needs
    # ctypes.windll patched, since a probe must not reconfigure the real console it is
    # printing to.
    #
    # WHAT IT ASSERTS IS THE DOCSTRING'S OWN PROMISE: "Never fatal — if the console
    # handle can't be reconfigured, the escapes may just not render". A legacy conhost
    # that refuses the mode change must cost the UI nothing, and that swallow is the
    # whole reason the try/except is there. It also pins the VT bit, so a call that
    # silently stopped requesting ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004) — which
    # would leave escapes unrendered on legacy conhost and look like a font problem —
    # fails here rather than in someone's terminal.
    if C.IS_WINDOWS:
        import ctypes as _ct

        class _FakeKernel32:
            def __init__(self, blow_up: bool) -> None:
                self.blow_up, self.set_with = blow_up, []

            def GetStdHandle(self, _n):     # noqa: N802
                return 1

            def GetConsoleMode(self, _h, _ref):   # noqa: N802
                return 1

            def SetConsoleMode(self, _h, mode):   # noqa: N802
                self.set_with.append(mode)
                if self.blow_up:
                    raise OSError("simulated legacy-conhost refusal, from a probe")
                return 1

        class _FakeWinDLL:
            def __init__(self, k) -> None:
                self.kernel32 = k

        _real_windll = _ct.windll
        for _blow_up in (False, True):
            _k = _FakeKernel32(_blow_up)
            _raised = None
            try:
                _ct.windll = _FakeWinDLL(_k)
                C.enable_vt_mode()
            except BaseException as _exc:                       # noqa: BLE001
                _raised = _exc
            finally:
                _ct.windll = _real_windll
            _label = "a console that REFUSES the mode change" if _blow_up else "a normal console"
            check(f"enable_vt_mode() against {_label} does not raise — the docstring's "
                  f"'never fatal' promise, executed", _raised is None)
            check(f"...and it did reach SetConsoleMode ({_label})", len(_k.set_with) == 1)
            if _k.set_with:
                check(f"...asking for ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004) "
                      f"({_label})", bool(_k.set_with[0] & 0x0004))
    else:
        skip("enable_vt_mode's win32 body",
             "not Windows — the arm is undefined in this process, which is the "
             "standing exemption, not a gap this file can close")

    # --- ui_main_loop's RESUME SWAP, read rather than run (audit #9). ------------
    # ui_main_loop is ~409 lines and the product path since R314, and the only suite
    # that reaches C.main() REPLACES it (vars(C)["ui_main_loop"] = lambda: 0), so every
    # `if engine is not None` branch is dark. It has already cost a day once: an import
    # inside it raised ModuleNotFoundError for a full day (95f8b15).
    #
    # Driving the whole loop headless is a bigger build than this file should carry, but
    # its WORST case is specific and stated in its own comment: losing `live` across the
    # engine swap sends `--resume <OT>` WITHOUT `--live`, "which looks for the transcript
    # under sandbox/circles/ instead of circles/ — wrong file, not just wrong mode". That
    # is a source-shape claim, and this asserts it: the replacement engine's live= comes
    # from the OLD engine, not from a literal and not from the ambient mode.
    _swap = _src.split("was_live = engine.live", 1)
    check("ui_main_loop's resume swap still captures the old engine's live flag",
          len(_swap) == 2)
    if len(_swap) == 2:
        _after = _swap[1].split("ui_full_render", 1)[0]
        check("...and hands that captured flag to the replacement engine's start(), so a "
              "resumed live circle does not go looking under work/sandbox/",
              "engine.start(" in _after and "live=was_live" in _after)
        check("...and the resume argv is rebuilt through _strip_resume rather than appended "
              "blindly, so a second resume cannot stack two --resume pairs",
              "_strip_resume(extra_argv)" in _after)

    # --- Astral characters (tier 4 #39): Windows getwch() delivers an
    # emoji as two UTF-16 surrogates, each of which fails the
    # isprintable() gates — poll_key pairs them (Windows-console wiring,
    # untestable here) via _surrogate_pair, whose math and downstream
    # acceptance are what this can assert anywhere. ---------------------
    heart = C._surrogate_pair("\ud83d", "\udc94")
    check("_surrogate_pair combines a UTF-16 pair into ONE code point",
          heart == "\U0001f494" and len(heart) == 1)
    check("...which the isprintable() gates accept", heart.isprintable())
    fake_stream5 = iter([heart, "x"])
    units5 = C.ui_burst_read("a", poll=lambda: next(fake_stream5, None))
    check("a paired astral char rides a text burst like any character",
          units5 == [("text", f"a{heart}x")])

    # --- THE POSIX ESCAPE TABLE, asserted on Windows. Ruled 2026-09-09 by the
    # operator ("yes split"), after the 2026-09-08 audit found the POSIX branch of
    # ui/circling.py structurally unreachable here: sys.platform is win32, so the
    # module never DEFINES those functions and no suite can import them. That
    # branch ships — ui/circling.py is a packaging entry point and the bundle
    # publishes to GitHub — so a recipient on Linux or macOS runs code nobody in
    # this project has ever run. The table and its lookup moved above IS_WINDOWS
    # and are pure, so they are covered now on every platform.
    #
    # THE EXEMPTION, NAMED RATHER THAN LEFT IMPLICIT, which is the whole point of
    # the split: what remains uncovered here is _chars_read's select+os.read on a
    # real descriptor and poll_key's isatty wiring, plus raw_mode's termios/tty
    # calls. The ASSEMBLY those feed is covered below as of 2026-09-15 — it moved
    # out for that reason, after the POSIX-only version of it stranded two thirds
    # of every arrow key on macOS with every probe here green.
    # Those need a real POSIX terminal and cannot be reached from this machine by
    # any fake, because the names do not exist in this process. enable_vt_mode's
    # Windows ctypes body is uncovered for the mirror-image reason: legacy conhost
    # only, never Windows Terminal. Both are known gaps, not oversights. -------
    check("every POSIX escape sequence maps to a token",
          all(isinstance(v, str) and v for v in C.POSIX_ESC.values()))
    check("the CSI and SS3 forms of one arrow agree",
          C.ui_posix_escape_read("\x1b[A") == C.ui_posix_escape_read("\x1bOA") == "UP")
    check("...and so do the three forms of Home",
          C.ui_posix_escape_read("\x1b[H") == C.ui_posix_escape_read("\x1bOH")
          == C.ui_posix_escape_read("\x1b[1~") == "HOME")
    check("every token the table yields is one handle_key already knows",
          set(C.POSIX_ESC.values()) <= {"UP", "DOWN", "LEFT", "RIGHT",
                                        "PGUP", "PGDN", "HOME", "END"})
    check("a bare ESC yields nothing, so _read_escape keeps reading",
          C.ui_posix_escape_read("\x1b") is None)
    check("...as does a partial sequence, the case that decides the loop continues",
          C.ui_posix_escape_read("\x1b[") is None)
    check("an unmapped sequence yields nothing rather than raising",
          C.ui_posix_escape_read("\x1b[Z") is None)

    # --- the assembler and its queue, 2026-09-15 -------------------------------
    # THE macOS ARROW BUG, pinned. Every arrow did nothing there while backspace
    # and tab were fine, because the reader asked select() about the DESCRIPTOR
    # and then read from sys.stdin, a BUFFERED TEXT STREAM: the first read took
    # the ESC and swallowed "[" and "D" into Python's own buffer, where select
    # cannot see them, so the sequence was abandoned as a bare ESC and the two
    # characters sat stranded. A single-byte key never touched the second layer,
    # which is why only the arrows looked broken.
    #
    # Both halves are pure now and take their reader as an argument, so the shape
    # that caused it — THE WHOLE SEQUENCE IN ONE READ — is exercised right here,
    # on a platform that cannot run the branch it lives in.
    def _reader(*reads):
        """A char reader that yields these batches in order, then nothing."""
        batches = [list(r) for r in reads]
        return lambda _timeout: batches.pop(0) if batches else []

    pend: list = []
    one = _reader("\x1b[D")                       # all three at once — the bug
    first = C.ui_pending_char_read(pend, one, 0)
    check("a burst hands back its first character and QUEUES the rest",
          first == "\x1b" and pend == ["[", "D"])
    check("...and the queue is what the assembler reads, so the arrow survives "
          "arriving in a single read",
          C.ui_escape_assemble(
              lambda t: C.ui_pending_char_read(pend, one, t)) == "LEFT")
    check("the queue is drained by that, leaving nothing stranded", pend == [])

    pend2: list = []
    drip = _reader("\x1b", "[", "D")              # one character per read
    C.ui_pending_char_read(pend2, drip, 0)
    check("a sequence dripped one character per read still assembles",
          C.ui_escape_assemble(
              lambda t: C.ui_pending_char_read(pend2, drip, t)) == "LEFT")

    pend3: list = []
    tail = _reader("\x1b[Dx")                     # an arrow with a keystroke behind it
    C.ui_pending_char_read(pend3, tail, 0)
    C.ui_escape_assemble(lambda t: C.ui_pending_char_read(pend3, tail, t))
    check("a character typed behind an arrow is still waiting, not lost",
          pend3 == ["x"])

    def _next(*reads):
        """A next_char(timeout) over those batches, with a queue of its own — the
        two signatures differ and mixing them is its own small trap: _reader is a
        chars_read (a LIST per call), next_char is one character or None."""
        p: list = []
        r = _reader(*reads)
        return lambda t: C.ui_pending_char_read(p, r, t)

    check("a bare ESC with nothing behind it assembles to nothing",
          C.ui_escape_assemble(_next()) is None)
    check("an unmapped sequence assembles to nothing rather than raising",
          C.ui_escape_assemble(_next("[Z")) is None)
    check("the SS3 form assembles too — a terminal left in application mode",
          C.ui_escape_assemble(_next("OD")) == "LEFT")
    check("an empty read is None, never an exception",
          C.ui_pending_char_read([], _reader(), 0) is None)

    # --- poll_key's OWN wiring, not just the pairing math (audit-register.md #39,
    # 2026-09-08). The comment above said this was "untestable here", and that was true only
    # while msvcrt was reached directly: it is a module-level name, so a fake one drives the
    # real poll_key on any platform. What this reaches that _surrogate_pair alone does not:
    # the \xe0 scan-code lead, the kbhit()/getwch() pairing handshake, and the ungetwch()
    # push-back — the last of which is the one branch whose failure REORDERS a person's
    # keystrokes rather than dropping one. -------------------------------------------------
    if hasattr(C, "msvcrt"):
        class _FakeMsvcrt:
            def __init__(self, keys): self.keys, self.pushed = list(keys), []
            def kbhit(self): return bool(self.keys or self.pushed)
            def getwch(self): return self.pushed.pop() if self.pushed else self.keys.pop(0)
            def ungetwch(self, c): self.pushed.append(c)

        real_msvcrt = C.msvcrt
        try:
            C.msvcrt = _FakeMsvcrt(["q"])
            check("poll_key returns a plain character unchanged", C.poll_key() == "q")

            C.msvcrt = _FakeMsvcrt(["\xe0", "H"])          # the extended-key lead + scan code
            check("poll_key maps an \\xe0 scan code through the extended table",
                  C.poll_key() == C._WIN_SCAN_EXT.get("H"))

            C.msvcrt = _FakeMsvcrt(["\ud83d", "\udc94"])   # a real emoji keystroke
            check("poll_key pairs a surrogate pair into ONE astral character",
                  C.poll_key() == heart)

            # THE DEGRADATION, AND THE ORDERING GUARANTEE. A lone high surrogate is corrupt
            # input; the follower must come back NEXT, not be swallowed.
            fake = _FakeMsvcrt(["\ud83d", "z"])
            C.msvcrt = fake
            lone = C.poll_key()
            check("a lone high surrogate passes through unpaired", lone == "\ud83d")
            check("...and its non-surrogate follower is pushed back, not consumed",
                  C.poll_key() == "z")
            check("...so the isprintable() gates drop the surrogate and keep the follower",
                  not lone.isprintable() and "z".isprintable())

            C.msvcrt = _FakeMsvcrt([])
            check("poll_key returns None when nothing is waiting", C.poll_key() is None)
        finally:
            C.msvcrt = real_msvcrt
    s_emoji = C.AppState(circle_height=3, command_height=3)
    s_emoji.handle_key(heart)
    check("handle_key inserts it into the input buffer",
          s_emoji.circle.input_buf == heart)

    # --- Pane heights fit the terminal (tier 4 #40): the 6/4 floors used
    # to be unconditional, so any terminal under 24 rows needed more rows
    # than existed and the bottom rows overwrote one another every tick.
    # The invariant: the two heights never exceed what the chrome leaves,
    # whenever at least two rows exist to split. --------------------------
    fits = all(sum(C._pane_heights(r, f)) <= max(2, r - 9)
               for r in range(10, 41) for f in ("circle", "command"))
    check("pane heights fit within rows-9 across 10..40-row terminals "
          "(9 chrome rows since B67's spacer above the divider)",
          fits)
    check("both panes keep at least one row even on a pathological screen",
          min(C._pane_heights(8, "circle")) >= 1)
    check("full-size terminals keep the exact 4/5ths split (one row "
          "smaller than pre-B67 — the spacer took it)",
          C._pane_heights(30, "circle") == (16, 5)
          and C._pane_heights(30, "command") == (5, 16))
    check("the ruled 6/4 floors still hold where they fit",
          C._pane_heights(25, "circle")[1] == 4)

    # --- The input WRAPS AT A WORD BREAK inside the pane width (2026-08-21,
    # the operator: "it currently scrolls the line left when approaching the right
    # bound"); it was a cursor-anchored single-row window from tier 4 #38
    # until then. _input_layout is the single computation both the row
    # drawers and render_cursor read, so text and cursor cannot disagree.
    check("a fitting line is one row, cursor after its last character "
          "(the legacy shape)",
          C._input_layout("p> ", "abc", 3, 80) == (["p> abc"], 0, 7))
    check("width=None (no terminal) is one row whatever the length",
          C._input_layout("p> ", "x" * 100, 100, None) == (["p> " + "x" * 100], 0, 104))
    words = " ".join(["word"] * 60)           # 299 chars, breakable
    rows_w, r_w, c_w = C._input_layout("Owner> ", words, len(words), 80)
    check("a 300-char line of words in an 80-column pane is four rows, each "
          "under the width, every break at a space",
          len(rows_w) == 4 and all(len(r) <= 80 for r in rows_w)
          and all(r.endswith(" ") for r in rows_w[:-1])
          and "".join(rows_w) == "Owner> " + words)
    check("...with the cursor on the LAST row, after its last character",
          r_w == 3 and c_w == len(rows_w[3]) + 1)
    rows_l, r_l, c_l = C._input_layout("Owner> ", words, len(words) - 100, 80)
    check("LEFT x100 puts the cursor on an earlier row at the matching "
          "column — the rows do not move, the cursor does",
          rows_l == rows_w and r_l < 3 and 1 <= c_l <= 80
          and rows_l[r_l][c_l - 1] == ("Owner> " + words)[7 + len(words) - 100])
    rows_h, r_h, c_h = C._input_layout("Owner> ", words, 0, 80)
    check("...and at the start of the text the cursor is on row 0, just "
          "after the prompt",
          r_h == 0 and c_h == 8 and rows_h == rows_w)
    rows_x, r_x, c_x = C._input_layout("p> ", "x" * 100, 100, 20)
    check("a word longer than a row is cut at width-1 per row — the append "
          "cell stays on screen (col never exceeds the width)",
          all(len(r) <= 19 for r in rows_x) and c_x <= 20
          and "".join(rows_x) == "p> " + "x" * 100)
    check("the exact-width boundary: a line of exactly `width` chars wraps "
          "its last character rather than hanging the cursor at width+1",
          C._input_layout("", "x" * 40, 40, 40)[1:] == (1, 2))
    rows_c, r_c, _ = C._input_layout("p> ", " ".join(["w"] * 100), 0, 20, max_rows=3)
    check("max_rows caps what is SHOWN to the run containing the cursor row",
          len(rows_c) == 3 and r_c == 0)
    rows_c2, r_c2, _ = C._input_layout("p> ", " ".join(["w"] * 100),
                                     len(" ".join(["w"] * 100)), 20, max_rows=3)
    check("...anchored at the end when the cursor is at the end",
          len(rows_c2) == 3 and r_c2 == 2)
    tb2 = C.AppState(circle_height=3, command_height=3)
    tb2.handle_text(" ".join(["yy"] * 60))
    out_narrow: list[str] = []
    C.ui_input_line_render(tb2, out_narrow.append, 40)
    drawn_rows = re.findall(r"\x1b\[\d+;1H\x1b\[2K([^\x1b]*)", "".join(out_narrow))
    check("render_input_line writes every wrapped row and never a byte past "
          "the width",
          drawn_rows and all(len(r) <= 40 for r in drawn_rows))
    g2 = C._input_geometry(tb2, "circle", C._circle_prompt(tb2), 40)
    check("the input takes its rows FROM THE BODY, bottom up — k rows of "
          "input leave height-(k-1) body rows",
          g2["k"] > 1 and g2["body_rows"] == tb2.circle.height - (g2["k"] - 1)
          and g2["first_row"] == C._pane_rows(tb2, "circle")["input"] - (g2["k"] - 1))
    check("...and the body repaint gate knows the row count — a change in "
          "k alone is a repaint",
          tb2.circle.body_needs_repaint(g2["k"]) is False
          or tb2.circle.body_needs_repaint(g2["k"] + 1) is True)

    s4 = C.AppState(circle_height=3, command_height=3)
    effect = s4.handle_text("pasted text")
    check("handle_text bulk-appends in one call and returns 'input'",
          s4.circle.input_buf == "pasted text" and effect == "input")

    # --- Left/Right move the cursor WITHIN the input line, not just
    # append-at-end/backspace-at-end — the operator: "I'd like the left/right
    # arrows to support moving on the line for edit." -------------------
    s8 = C.AppState(circle_height=3, command_height=3)
    for ch in "abd":
        s8.handle_key(ch)
    check("typed text lands at the end by default",
          s8.circle.input_buf == "abd" and s8.circle.input_cursor == 3)

    s8.handle_key("LEFT")
    check("LEFT moves the cursor back one", s8.circle.input_cursor == 2)
    s8.handle_key("c")
    check("typing at a mid-line cursor INSERTS, not appends",
          s8.circle.input_buf == "abcd" and s8.circle.input_cursor == 3)

    for _ in range(10):
        s8.handle_key("LEFT")
    check("LEFT is bounded at column 0, never goes negative",
          s8.circle.input_cursor == 0)

    for _ in range(10):
        s8.handle_key("RIGHT")
    check("RIGHT is bounded at the end of the buffer",
          s8.circle.input_cursor == len(s8.circle.input_buf) == 4)

    s8.handle_key("LEFT")
    s8.handle_key("\x7f")   # backspace
    check("backspace at a mid-line cursor removes the char BEFORE it, "
          "not always the last character in the buffer",
          s8.circle.input_buf == "abd" and s8.circle.input_cursor == 2)

    s8.handle_key("\r")
    check("submitting resets the cursor along with the buffer",
          s8.circle.input_cursor == 0)

    s9 = C.AppState(circle_height=3, command_height=3)
    s9.handle_key("a")
    s9.handle_key("d")
    s9.handle_key("LEFT")
    s9.handle_text("bc")
    check("a paste (handle_text) inserts at the cursor too, not just "
          "appends at the end",
          s9.circle.input_buf == "abcd" and s9.circle.input_cursor == 3)

    out_cursor: list[str] = []
    C.ui_cursor_render(s9, out_cursor.append)
    L9 = C._layout(s9)
    expected_cursor = C._move(L9["circle_input_row"],
                             len(s9.circle.prompt) + s9.circle.input_cursor + 1)
    check("render_cursor positions the terminal cursor at input_cursor, "
          "not at the end of the buffer",
          out_cursor[0] == expected_cursor)

    # --- Resize: a terminal resize can't be prevented from inside this
    # process (see main_loop's comment — ConPTY hides the real window
    # handle), so the fallback is to detect it and recover cleanly rather
    # than leave stale geometry on screen. Tested at the Pane/AppState
    # level, which is where the actual recovery logic (new height, clamped
    # scroll, forced repaint) lives. -----------------------------------
    p3 = C.Pane("T3", "t3> ", height=10)
    for n in range(20):
        p3.append(f"r{n}")
    p3.line_up(5)                          # scroll_top now 5 (max_top=10)
    check("scrolled before resize, at a position only valid for height 10",
          p3.scroll_top == 5)
    p3.resize(4)                            # shrink — max_top is now 16
    check("resize updates height", p3.height == 4)
    check("resize does not touch the underlying lines, only what's shown",
          len(p3.lines) == 20)
    check("a scroll_top that's still valid after a resize is left alone",
          p3.scroll_top == 5)

    p5 = C.Pane("T5", "t5> ", height=3)
    for n in range(10):
        p5.append(f"u{n}")
    p5.line_up(3)                           # max_top was 7 -> scroll_top = 4
    check("scrolled to a position valid for the OLD, smaller height",
          p5.scroll_top == 4)
    p5.resize(8)                            # max_top is now 2 — 4 no longer fits
    check("resize clamps an out-of-range scroll_top into the new bounds "
          "instead of leaving it pointing past the end",
          p5.scroll_top == p5._max_top() == 2)

    check("resize resets the painted cache so the next render repaints "
          "unconditionally, regardless of whether visible() happens to "
          "coincide with the old painted content",
          p3._painted is None)

    s5 = C.AppState(circle_height=3, command_height=3)
    for n in range(10):
        s5.circle.append(f"cc{n}")
        s5.command.append(f"mm{n}")
    s5.resize(circle_height=6, command_height=2)
    check("AppState.resize fans out to both panes independently",
          s5.circle.height == 6 and s5.command.height == 2)
    out_resize: list[str] = []
    C.ui_full_render(s5, width=80, write=out_resize.append)
    check("render_full after a resize runs clean at the new geometry",
          "CIRCLE" in "".join(out_resize)
          and "COMMANDS" in "".join(out_resize))

    # Renderer smoke test: capture output into a list instead of a real
    # terminal, and check it doesn't crash and mentions both panes.
    out: list[str] = []
    C.ui_full_render(state, width=80, write=out.append)
    blob = "".join(out)
    check("render_full ran without raising and drew both headers",
          "CIRCLE" in blob and "COMMANDS" in blob)
    check("render_full shows the interleaved part line",
          PLACEHOLDER_PART in blob)

    # The header's scroll tag: both counts appear once scrolled.
    out2: list[str] = []
    C.ui_full_render(s2, width=80, write=out2.append)
    blob2 = "".join(out2)
    check("header shows an 'above' count for a scrolled pane",
          "above" in blob2 and "below" in blob2 and "scrolled" in blob2)

    quit_effect = state.handle_key("\x03")
    check("Ctrl-C sets running False", quit_effect == "quit"
          and state.running is False)

    # --- COLOR is a write-time tint, armed only by main() (D64 a) -------
    # THIS CHECK SETS THE STATE IT NAMES, since 2026-09-16. It used to read
    # "with COLOR off (every suite's state)" and then assert without setting
    # anything — so it tested the claim AND an assumption about ambient state
    # at once, and when it failed on a macOS install neither this tree nor any
    # reading of main() could account for it: --selftest returns before COLOR
    # is armed, so the module default of False should still be standing. An
    # assumption that cannot be derived is one to establish instead of argue
    # about, and the claim under test is unchanged either way.
    # THE TWO CLAIMS ARE SEPARATE NOW, and that is the repair. The first is an
    # OBSERVATION about ambient state — nothing in main() should have armed the
    # tint by the time --selftest runs — and the second is the BEHAVIOUR. Rolled
    # together, a false observation was reported as a broken _tint, which is a
    # sentence about the wrong file.
    _color_was = C.COLOR
    try:
        check("COLOR is off when the suite reaches here — the stage-8 block "
              "above restored the tint its real main() calls armed",
              _color_was is False,
              f"COLOR was {_color_was!r} on entry, so something armed it and "
              f"did not put it back. _tint is not at fault. The known source "
              f"is the stage-8 C.main() checks, whose restore is explicit.")
        C.COLOR = False
        _off = C._tint(C.C_ERR, "  !! boom")
        check("with COLOR off _tint is byte-inert", _off == "  !! boom",
              f"_tint returned {_off!r} with COLOR={C.COLOR!r}; "
              f"C_ERR={C.C_ERR!r} C_OFF={C.C_OFF!r}")
        C.COLOR = True
        check("with COLOR on it wraps and resets, nothing else",
              C._tint(C.C_ERR, "  !! boom") == f"{C.C_ERR}  !! boom{C.C_OFF}",
              f"_tint returned {C._tint(C.C_ERR, '  !! boom')!r}")
        check("...and an empty string stays empty — no stray escape codes "
              "on blank rows", C._tint(C.C_CHROME, "") == "",
              f"_tint returned {C._tint(C.C_CHROME, '')!r} for an empty string")
    finally:
        # FALSE, not whatever it was on entry: every rendering check after this
        # compares plain bytes, so leaving a stray True here would turn one
        # anomaly into a cascade of failures that all name the wrong thing.
        C.COLOR = False

    # --- THE CIRCLE PANE IS PRIMARY, and every automatic handover gives it
    # back. The operator, 2026-09-16: *"Always focus on it unless the user tabs
    # to cmd> or the process requires input in cmd>, and when a cmd> input
    # (series) is complete, focus on the last pane the user had selected via
    # tab."* Three mechanisms, and the interesting part is where they meet. ---
    fs = C.AppState(circle_height=8, command_height=4)
    check("focus opens on the circle pane, and that is also the remembered one",
          fs.focus == "circle" and fs.user_focus == "circle")

    check("a pending command-channel question takes focus",
          fs.command_read_follow(True) == "focus" and fs.focus == "command")
    check("...and asking again while it is still pending changes nothing — the "
          "call is per-tick and only a CHANGE redraws",
          fs.command_read_follow(True) is None)

    for _ in range(C.AppState.READ_HANDBACK_TICKS - 1):
        fs.command_read_follow(False)
    check("a GAP inside the series does not hand focus back — vetting asks once "
          "per row, and bouncing on each gap is the defect this prevents",
          fs.focus == "command")
    check("once the series has genuinely stopped, focus returns",
          fs.command_read_follow(False) == "focus" and fs.focus == "circle")

    # The same run again, but the person tabbed to cmd> first: the hand-back is
    # to THEIR pane, which is the whole of "the last pane the user had selected".
    fs2 = C.AppState(circle_height=8, command_height=4)
    fs2.handle_key("\t")
    check("Tab records the person's own choice", fs2.user_focus == "command")
    fs2.handle_key("\t")
    fs2.handle_key("\t")
    check("...and the LAST Tab is the one that counts",
          fs2.user_focus == "command" and fs2.focus == "command")
    fs2.command_read_follow(True)
    for _ in range(C.AppState.READ_HANDBACK_TICKS + 1):
        fs2.command_read_follow(False)
    check("a series that ends hands back to the TABBED pane, not to circle",
          fs2.focus == "command")

    # An error is not a question and never completes — ruled 2026-09-16, (a),
    # keeping the 2026-08-25 handover intact underneath the new rule.
    fs3 = C.AppState(circle_height=8, command_height=4)
    fs3.command.append("  !! its DREAMING did not run")
    check("an error takes focus, as it has since 2026-08-25",
          fs3.on_alert("  !! its DREAMING did not run") == "focus"
          and fs3.focus == "command")
    fs3.command_read_follow(True)
    for _ in range(C.AppState.READ_HANDBACK_TICKS + 1):
        fs3.command_read_follow(False)
    check("a question ending UNDER an error does not hand focus away from it",
          fs3.focus == "command")
    fs3.handle_key("\t")               # ONE Tab: cmd> -> circle
    check("...and a Tab is what releases the error's hold — the person saying "
          "they have read it",
          fs3.focus == "circle" and fs3._alert_holds is False)
    fs3.command_read_follow(True)
    for _ in range(C.AppState.READ_HANDBACK_TICKS + 1):
        fs3.command_read_follow(False)
    check("...after which a question hands back normally again",
          fs3.focus == "circle")

    # The initialization handover is the archetype of "the process requires
    # input in cmd>", and used to hand back to a hardcoded "circle".
    fs4 = C.AppState(circle_height=8, command_height=4)
    fs4.handle_key("\t")                       # the person chose cmd>
    fs4.on_state("initializing")
    check("the first-run dialogs take the command pane", fs4.focus == "command")
    fs4.on_state("initialized")
    check("...and hand back to the person's pane, not to a hardcoded circle",
          fs4.focus == "command")

    # --- backspace at column 0 must be a no-op, never a delete of the LAST
    # character with the cursor going to -1 — audit-register.md #39:
    # AppState.handle_key()'s `if pane.input_cursor > 0:` guard is what
    # this line covers by hitting the mid-line case; only cursor == 0 was
    # dark. ---------------------------------------------------------------
    bs_state = C.AppState(circle_height=8, command_height=4)
    bs_state.handle_key("\t")
    check("fresh command pane starts with an empty input buffer",
          bs_state.command.input_buf == "" and bs_state.command.input_cursor == 0)
    bs_state.handle_key("\x7f")
    check("backspace (\\x7f) at column 0 on an empty buffer is a no-op",
          bs_state.command.input_buf == "" and bs_state.command.input_cursor == 0)
    bs_state.handle_key("\b")
    check("backspace (\\b) at column 0 on an empty buffer is a no-op",
          bs_state.command.input_buf == "" and bs_state.command.input_cursor == 0)
    for ch in "abc":
        bs_state.handle_key(ch)
    bs_state.command.input_cursor = 0
    bs_state.handle_key("\x7f")
    check("backspace with the cursor moved back to column 0 (non-empty "
          "buffer) leaves the buffer untouched, not the LAST character "
          "deleted",
          bs_state.command.input_buf == "abc" and bs_state.command.input_cursor == 0)

    # --- a FRESH PROCESS must import circling.py clean. Every other suite
    # here imports `circling` only after this file's own
    # sys.path.insert(COORD_DIR) above, which masks exactly the defect a
    # real, freshly-started process hits (audit-register.md #5: a
    # coordinator-only import at module scope raised ModuleNotFoundError
    # for a full day, 95f8b15, 2026-09-03). A subprocess is the only way
    # to see what a real invocation sees. `--help` is the door: it exits
    # on its own, opens no window and starts no engine, so the check is
    # not timing-dependent. ---------------------------------------------
    try:
        proc = subprocess.run(
            [sys.executable, str(UI / "circling.py"), "--help"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, cwd=str(UI.parent), timeout=30)
        text = proc.stdout.decode("utf-8", "replace")
        _fresh_ok = (proc.returncode == 0 and "Traceback" not in text
                     and text.startswith(C.HELP_TEXT.splitlines()[0]))
        check("a fresh interpreter runs circling.py --help clean: exit 0, the "
              "usage line first, no traceback", _fresh_ok)
        if not _fresh_ok:
            print(f"      child returncode {proc.returncode!r}, output ({len(text)} chars):")
            for _line in (text.splitlines() or ["<nothing on stdout/stderr>"]):
                print(f"        | {_line}")
    except (OSError, subprocess.TimeoutExpired) as exc:        # noqa: BLE001
        skip("fresh-process --help check",
             f"could not run a child interpreter ({exc})")

    print()
    if failures:
        if skipped:
            print(f"  {len(skipped)} skipped for missing data (see 'skip' "
                  f"lines above) — not counted as passes")
        print(f"SELF-TEST: FAIL ({len(failures)} of {total[0]})")
        return 1
    if skipped:
        print(f"  {len(skipped)} check(s) SKIPPED for missing data — a fresh "
              f"install has no issue graph and no ruled practices yet, and "
              f"these read one back. Not counted as passes:")
        for s in skipped:
            print(f"      {s[:96]}")
    print(f"SELF-TEST: PASS ({total[0]} of {total[0]})")
    return 0


if __name__ == "__main__":
    sys.exit(self_test())
