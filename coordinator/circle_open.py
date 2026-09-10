#!/usr/bin/env python3
"""
circle_open.py — THE OPEN STEP: everything between the flags and the first Self> prompt.

    circle.py main()  ->  circle_open.circle_open(...)  ->  CircleOpen | int

WHAT IT IS. The corruption gate, the settings-corrections flush, the integrity and API checks
run against each other, the circle_state warning, initialization, the working-set question,
the topic, the four-block assembly, the pre-warm, the opening blind round, and the disarm of
the withdraw-arm. It ends where `while True:` begins.

WHY IT IS ITS OWN FILE. circle.py:main() was 1,657 lines and cyclomatic complexity 229 — 3.8x
the next-largest function in the tree by lines and 2.5x by complexity. The 2026-09-09 cohesion
map measured that and it was the single largest structural outlier in coordinator/. THE SAME
MOVE WAS ALREADY MADE ONCE, for the other end: circle_close.py is the close step, carved out
by B99 stage 12 (2026-09-03). This is its twin, and main() keeps what is genuinely its own —
parsing the flags, and running the conversation.

IT RETURNS ONE OF TWO THINGS, and the caller must check which:

    CircleOpen   the circle is open; this is everything the Self> loop needs
    int          it REFUSED, and this is the exit code — 2 in every case today

Seven refusal paths reach that second arm: the corruption gate, the API check, a client that
will not build, the reduced-roster confirmation, an unparseable --resume transcript, a resume
whose circle is already closed, and a --resume with no candidate. `coordinator/tests/
test_circle_argv.py` executes five of them against the REAL entry point with two stubs, and
asserts after each that neither circles/ nor the sandbox gained a file — which is the 2026-08-09
incident's own fix ("nothing is written until the API check passes") checked rather than read.

WHAT DID NOT MOVE, and why each stayed:
    the three loop flags       closing_confirmed / abort_confirmed / aborted are `= False`
                               lines sitting immediately above `while True:`. They are the
                               loop's own state, initialised early; they belong to the loop.
    `global CONSOLE_NAME`      it is RETURNED instead. A `global` here would bind this
                               module's name while circle.py's own Self> prompt kept reading
                               circle.CONSOLE_NAME — the pre-initialization name, forever,
                               with nothing to see. The same class of defect as a
                               from-imported ROOT (see git_hook_script.py).

WHAT DID move that a reader might not expect: `discard_unspoken()`, the atexit hook that
withdraws a transcript which never got a statement. It closes over locals, but it is both
registered (atexit) and called directly INSIDE this region, so it travels whole.
"""
from __future__ import annotations
import atexit
import dataclasses
import pathlib
import datetime
import threading
import identity as ID
import record_verify as CI
from record_paths import ROOT, PART_TAGS, SANDBOX_CIRCLES, record_dir
import setting_manager as SET
import phase_clock as PC
from seam import fail
from write_guard import WriteGuard, _within
import command_surface as CS
from llm_client import (stream_prewarm, stream_api_preflight, MODEL, stream_key_source_note,
                        stream_failure_explain, RATE_CACHE_WRITE_1H, RATE_CACHE_READ)
from prompt_build import prompt_part_assemble, block_order
from group_context import group_shared_read
from group_attention import circle_briefing_build
from role_attention import part_attention_finalize
from proposal_vetting import proposal_vet
from circle_rounds import circle_blind_round_run
from transcript_store import (circle_transcript_open, circle_transcript_discard_empty,
                              circle_transcript_resume_read)
import transcript_store as TS
import working_set_manager as WS
import circle_close as CC
import token_count as TC

@dataclasses.dataclass
class CircleOpen:
    """What an opened circle IS — the one labelled package the open step hands back.

    Ruled by the operator 2026-09-09 ("a - one labelled package") over the alternative of thirteen
    positional values, on the ground that a field added or removed later is then a one-place
    change and no caller can transpose two of them.

    THREE FIELDS ARE IN-OUT: ot, path and guard go in and can come back changed — a --resume
    adopts an existing open time and its transcript path, and the guard is rebuilt on it.
    """
    ot: str                       # the open time, minted here or adopted from --resume
    path: pathlib.Path            # the transcript
    guard: object                 # the write-safety gate, bound to this circle
    transcript: list              # every statement so far: empty, or a resume's own
    sysblocks: dict               # the four assembled blocks, per part
    since_self: dict              # per-part statements since Self last spoke
    state: dict                   # the round's own state ({"last": <part>})
    issue_cmds: list              # /issue rulings queued for the close (R079)
    circle_ref: str               # how this circle is cited in the record
    # resume_flag is NOT a field. It looked like one to the interface scan — the open step
    # assigns it and the Self> loop reads a name spelled the same — but the two are
    # INDEPENDENT local computations of one pure expression on args, one at
    # circle_open.py:572 and one at circle.py:1560. Nothing crosses. Passing it would
    # have made a shared fact out of a coincidence of naming.
    console_name: str             # what the Self> prompt is called — see below




def circle_transcript_path_read(live: bool, ot: str) -> pathlib.Path:
    """Where this circle's transcript goes — the live tree or the sandbox.

    ONE HOME, 2026-09-09. It was a nested def inside circle.py's main(); the open step needs
    it too, and a second copy of a two-line path derivation is exactly the shape
    system_unique_home_verify.py exists to keep out of constants. main()'s own helper now
    delegates here.
    """
    return (record_dir(ROOT, "circles") if live else SANDBOX_CIRCLES) / f"circle_{ot}.md"



def circle_open(args, client, parts: list, ot: str, path: pathlib.Path,
                guard) -> "CircleOpen | int":
    """Open the circle. Returns CircleOpen, or an exit code if it refused."""
    # THE FOUR NAMES circle.py OWNS, bound here rather than imported at module load.
    # circle imports this module, so a module-level `import circle` would be a load-time
    # cycle; a lazy bind inside the function is the same cycle-breaker circle_close.py:551
    # uses. BINDING, NOT COPYING, and that distinction is load-bearing for `emit`: it calls
    # seam.emit at CALL time, and ui/circling.py REBINDS seam.emit to put text on its own
    # queues. Copying the wrapper would give one fact two homes; from-importing seam.emit
    # would go stale at the rebind, invisibly (seam.py's own contract).
    import circle as _C
    emit = _C.emit
    read_line = _C.read_line
    read_line_no_annotation = _C.read_line_no_annotation
    SELF_DISPLAY = _C.SELF_DISPLAY

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
    # SETTINGS CORRECTIONS, FLUSHED HERE — 2026-08-28. They are collected at
    # IMPORT, which in the two-pane UI happens before seam.emit is rebound, so
    # printing them where they are found would put them under the alt-screen
    # and lose them. This is the first point in the open where a surface
    # certainly exists.
    SET.setting_corrections_flush(lambda t: emit("command", t))

    # LABEL AND RESULT ARE ONE emit() CALL, for both checks below — never two
    # joined by end=" "/flush=True. The dual-pane adapter (ui/circling.py
    # CircleEngine._emit) queues one pane line per emit() call and has no
    # notion of "still on the previous line", so a partial-line label
    # followed by a separate result call renders as two lines there even
    # though a real terminal shows them joined. Emitting the whole
    # "<check>: <result>" string in a single call is what makes the two
    # environments agree, so the check's outcome must be known before
    # anything is emitted for it.

    # THE TWO CHECKS RUN AT ONCE — the operator's ruling, 2026-09-09. They contend for
    # nothing: the sweep is disk and CPU and opens no socket, the preflight is one network
    # round trip and reads no file. Measured on circle 2026-09-09_1122, the pair cost
    # 4.53s + 1.42s in series; concurrently the pair costs the longer of the two.
    #
    # THE BEAT ABOVE STILL NAMES THE SWEEP, which is why it is armed first and why this
    # ordering is not arbitrary. current() reports the INNERMOST open span, so while both
    # run it names the preflight — but the preflight is the short one (1.42s against
    # PROGRESS_SECONDS, 3), so it has popped before the first beat can fire, and every
    # beat a person actually sees is the sweep's. The long operation is still the one
    # named on screen.
    #
    # THE ORDER OF OUTPUT IS UNCHANGED, and that is why the results are held rather than
    # emitted where they are found: integrity, then the key-source note, then the api line.
    # A reader (and every probe that greps this output) sees exactly what it saw before.
    #
    # WHAT IT COSTS, NAMED: a corrupted tree now spends ONE preflight call, where the
    # serial order refused before reaching it. The refusal message no longer claims
    # otherwise. Nothing is WRITTEN either way, which is what the 2026-08-09 ruling
    # actually protects — no transcript, no working-set entry, no topic asked for.
    #
    # PhaseClock.span() is safe on two threads: it is lock-guarded and pops its OWN
    # (name, t0) entry rather than the top of the stack, so two open spans record
    # correctly and neither leaves the stack lying about who is open.
    _sweep: dict = {}

    def _open_integrity_sweep() -> None:
        try:
            with PC.PHASES.span("open.integrity_check"):
                _sweep["out"] = CI.record_sweep()
        except BaseException as _exc:                            # noqa: BLE001
            _sweep["exc"] = _exc                                 # re-raised on the main thread

    _sweep_thread = threading.Thread(target=_open_integrity_sweep,
                                     name="open-integrity-sweep")
    _sweep_thread.start()

    # THE API CHECK, as early as it can be run: the client exists, and nothing
    # has been typed or written. See the preflight block above for the ruling.
    _note = stream_key_source_note()
    _why = None
    if client is not None:
        # The span wraps the WHOLE check, so the timing goes around it, not through it.
        with PC.PHASES.span("open.api_check"):
            _why = stream_api_preflight(client, args.dry_run)

    _sweep_thread.join()
    if "exc" in _sweep:
        raise _sweep["exc"]
    _findings, _seen = _sweep["out"]

    if _findings:
        emit("command", "\nintegrity check: FAILED")
        emit("command", f"\n  !! {len(_findings)} operational file(s) are corrupted. "
                        f"The circle was NOT opened.\n")
        for _f in _findings:
            emit("command", f"     {_f.path}")
            emit("command", f"         {_f.defect}")
            emit("command", f"         {_f.remedy}")
        emit("command", "\n     Nothing was written — no transcript, no working-set "
                        "entry, no topic asked for.\n     Repair or restore the file(s) "
                        "above, then open again.")
        return 2
    emit("command", f"\nintegrity check: ok ({_seen} files)")

    # No blank line ahead of it: the integrity check above already opened
    # this section, and the two checks read as one block, not two.
    if _note:
        emit("command", f"\n  !! {_note}")
    if client is not None:
        if _why:
            emit("command", "api check: FAILED")
            emit("command", f"\n  !! {_why}")
            emit("command", "\n     Nothing was written — no transcript, no working-set "
                  "entry.\n     Fix the key and open again; the topic has not "
                  "been asked for yet.")
            return 2
        emit("command", "api check: ok")

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
            base = (record_dir(ROOT, "circles") if args.live else SANDBOX_CIRCLES).resolve()
            openc = [c for c in circle_state.circle_open_read()
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
        interrupted = CC._interrupted_closes(base) if args.live else []
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
        for ot_f in CC._failed_phase2(base):
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
    # 2026-08-17: no longer `and args.live` — proposal_vet() now
    # runs in sandbox too, describing and validating without ruling.
    if not args.resume:
        # THE COALESCE REFRESH, R356 (B69) — hash-guarded, so it makes a
        # model call only when the pending set changed since it last ran.
        # It lives HERE, at the real checkpoints, and NOT inside
        # proposal_vet(): the suites drive that loop live against
        # temp registers, and a refresh inside it sent a real model call
        # from a test run (E22). Live only; fails open — a suggestion pass
        # must never block a circle's open.
        if args.live:
            try:
                import proposal_group_manager as CG
                # ROUTINE CHATTER, dev-gated (2026-09-01) — the exception
                # branch below stays unconditional: a failure is not chatter.
                CG.proposal_group_refresh(
                    say=lambda m: emit("command", m) if CS.dev_mode else None)
            except Exception as e:
                emit("command", f"  coalesce: skipped ({e})")
        proposal_vet("before this circle's prompts are warmed", args.live)

        # THE SETTINGS FOLD, 2026-08-28 (R379). A change to
        # anything that shapes a prompt block, the model, or a budget a block
        # is sized against is written to [pending] and lands HERE — the one
        # moment it can move without changing block 1 out from under a
        # transcript already in flight. That is the hazard the comment above
        # this checkpoint already names for the practice register; a setting
        # carries it too, and more directly.
        #
        # BEFORE prompt assembly and BEFORE prewarm, deliberately: a fold
        # after either would warm a cache for one value and run the circle on
        # another. It is also before the resume branch's reach, because a
        # RESUMED circle must keep the settings its own transcript began
        # under — `if not args.resume` above is what gives it that.
        try:
            import setting_manager as _SET
            folded = _SET.setting_pending_fold()
            if folded:
                emit("command", "\nsettings now in force for this circle:")
                for k in folded:
                    emit("command", f"  {k} = {_SET.setting_active_read().get(k)}")
        except Exception as e:                                 # noqa: BLE001
            # FAILS OPEN, like the coalesce refresh above it. A settings file
            # that cannot be folded must not stop a circle opening; the
            # defaults are what the code runs on, and they are sound.
            emit("command", f"  settings: fold skipped ({e})")

    # INITIALIZATION — R330 (docs/Initialization.md §2): the first-run
    # dialogs, between CHECKPOINT 2 and the working-set question, so THIS
    # circle's blocks are built from what they record — the Soul's and
    # Child's context (R331) and, while issues/ is empty, one first issue
    # (R324/R328). run_initialization() holds the four skips itself (not
    # live, resume, --yes, no interactive surface) and is silent when
    # nothing is due; it ends with "Starting your circle..." and the focus
    # handover ("state" tokens) when anything fired.
    import initialization as INIT
    INIT.initialization_run(live=args.live, resume=args.resume, yes=args.yes)

    # THE ANSWER NAMES THE CONSOLE THE SAME CIRCLE IT IS GIVEN. CONSOLE_NAME
    # was bound once, at import — BEFORE the dialog above records
    # preferred_name — so the first circle a person ever ran kept showing the
    # .env name they were asked to replace (found 2026-08-25, the "Sally"
    # install: the answer landed in part.toml, R325's order resolves it
    # first, and the prompt said the old name anyway). Re-resolve after the
    # dialog: this module's own Self> prompt and ui/circling's _circle_prompt
    # both read the attribute at each render, so both follow. transcript_
    # store's copy is rebound too — it compares historic Self tags with it.
    # CONSOLE_NAME IS RETURNED, NOT REBOUND HERE. `global` in this module would bind
    # THIS module's name, and circle.py's own Self> prompt reads circle.CONSOLE_NAME —
    # it would have gone on showing the pre-initialization name, silently. The caller
    # assigns its own from the record. transcript_store's copy is set here because that
    # one IS the module attribute every writer reads.
    console_name = ID.user_name_read()
    TS.CONSOLE_NAME = console_name

    core = group_shared_read()
    # ONE BUILD, AFTER the working set is chosen — RULED 2026-08-19 (R244;
    # 2026-08-18 review #58, second half). The open used to build every
    # part's blocks for the whole graph BEFORE asking, then rebuild them
    # all for the chosen set — and the first build's only surviving output
    # was a whole-graph price line plus the "N tokens fewer" comparison: a
    # price nobody paid, bought with a doubled wait. The price of what
    # THIS open actually sends still prints below, every open.
    # None, NOT [] — R301 (2026-08-22) flipped the default to "no issues", and
    # --resume does not re-ask. Leaving this at `[]` would have made resume the
    # one path that still silently brought the whole graph in.
    chosen: "list[str] | None" = None
    import issue_prompt_projection as IP
    # NO LIVE ISSUE, NO QUESTION — R330, 2026-08-23: *"If
    # there are no issues[], do not ask the working set question."* The
    # answer blank would give, taken silently: None is "no issues in this
    # circle at all", the ruled spelling (finding 2, 2026-08-20). Leads and
    # settled issues do not count — live_nodes() is what BLOCK 2 projects,
    # so an empty one means there was nothing to choose from. A root DOES
    # count now (R429, 2026-09-01: a root is live) — so
    # in THIS tree, which already carries two roots that can never be
    # retired, live_nodes() can no longer be empty and this question is
    # asked at every future circle open. It stays empty-checked, not
    # deleted, for a fresh install with no issues/ at all.
    if not args.resume and IP.live_nodes():
        chosen = WS.working_set_ask(IP, read_line=read_line_no_annotation)
    with PC.PHASES.span("open.prompt_build"):
        briefing, unknown = circle_briefing_build(chosen)
        if unknown:
            emit("command", f"  unknown issue id(s) ignored: {', '.join(unknown)}")
        if chosen:
            focus, per, _ = IP.issue_resolve(chosen)
            emit("circle", f"  focus {', '.join(focus) or '—'}"
                  + (f" · related {', '.join(per)}" if per
                     else " · NO LIVE ISSUE-RELATIONSHIP reaches these"))
        sysblocks, notes = {}, {}
        for p in parts:
            sysblocks[p], notes[p] = prompt_part_assemble(p, core, briefing)
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
    # graph, which after R301 is the one thing it never means.
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
            import topic_manager as TOP
            n_open = len(TOP.topic_open_read())
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
        if circle_transcript_discard_empty(path, ot, _opened["head"], args.live):
            emit("command", f"\n  circle_{ot} discarded — nothing was ever said.")
            emit("command", "     transcript and working-set entry removed; the record "
                  "is unchanged.")
            # NO TRACE includes the capture: the Block files and whatever
            # pre-warm turns were recorded before the failure. Exactly the
            # files the manifest lists, by name — never a glob (E12).
            if _cap["dir"] is not None:
                try:
                    import prompt_capture as _PC
                    n = _PC.prompt_capture_discard(_cap["dir"])
                    if n:
                        emit("command", f"     prompt capture removed "
                                        f"({n} file(s)).")
                except Exception as e:                       # noqa: BLE001
                    emit("command", f"     prompt capture NOT removed — {e}")

    resumed = None
    if args.resume:
        try:
            resumed = circle_transcript_resume_read(path, ot, parts)
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
        path = circle_transcript_path_read(args.live, ot)
        # REFUSED, not warned. open_transcript truncates — write_lf is
        # write_text — and there was no check at all, so two --live opens in
        # the same clock minute meant the second one silently destroyed the
        # first one's transcript. --resume already refuses to reopen a CLOSED
        # circle; this is the same refusal for a LIVE one, which is the case
        # that loses data rather than merely confusing a reader.
        if path.exists():
            # SAME BUG SHAPE AS #25's fix below (audit-register.md, found
            # independently while regression-testing that fix): this check
            # runs for --dry-run too (path is circle_path(ot), which is
            # SANDBOX-relative there), so the resume hint must match.
            resume_flag = "--live" if args.live else "--dry-run"
            emit("command", f"\n  !! {path} already exists — refusing to overwrite it.")
            emit("command", "     Two circles opened in the same minute share an open")
            emit("command", "     time. Wait for the clock to turn over, or resume that")
            emit("command", f"     one: python coordinator\\circle.py {resume_flag} "
                            f"--resume {ot}")
            return 2
        circle_transcript_open(guard, path, ot, topic)
        WS.working_set_record(ot, chosen, topic, args.live)
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
    #
    # TIER A RECALL (remember_expand.py, ruled 2026-08-29) — HERE, after the
    # topic is known and BEFORE the capture below, because the capture
    # records BLOCK 4 as sent and the pack is part of the emitted program.
    # Off unless the trial arm says otherwise; its own module guarantees a
    # failure here cannot cost the open. part_attention_finalize() is BLOCK 4's own
    # Phase 2 (role_attention.py's module docstring) — it delegates to
    # remember_expand.remember_expand_apply() rather than reimplementing it. Called through
    # prompt_build.py's own re-export, 2026-09-02, on direct instruction
    # that only prompt_build.py execute any of the four sole assemblers —
    # this was the one real call site still importing role_attention.py
    # itself, since 2026-09-02's own block-3/4 extraction shipped it that
    # way.
    part_attention_finalize(sysblocks, parts, topic, chosen, ot, arm=args.recall_arm)
    # PART-INITIATED RECALL (recall_index.py, R402) arms from the same
    # flag, and clears here because CircleEngine runs this main() inside a
    # long-lived UI process — module state must not survive one circle
    # into the next.
    import recall_index as RC
    RC.recall_clear()
    RC.recall_arm_set(args.recall_arm)
    # AND THE INDEX IS ARMED HERE, ON A BACKGROUND THREAD — R470/B121. It
    # overlaps the capture, the pre-warm and the opening round, all of which are
    # API waits, so the fastembed model load and the first-ever embed of six
    # cold parts are paid before anyone types rather than inside the first
    # part's turn. Returns immediately; a failure is reported and costs nothing,
    # because recall_execute()'s own lazy refresh is still the fallback.
    RC.recall_index_arm_start(parts, live=args.live)
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
        pdir = prompt_capture.prompt_capture_write(cap_ot, sysblocks, notes, args.live,
                                    names=block_order())
        _cap["dir"] = pdir
        if pdir and args.resume:
            # Compare BLOCKS, not files. A resume capture has its own
            # directory, `<OT>_resume_<k>/`, and the manifest's per-block
            # sha256 is the thing that means "the part runs a different
            # program" — the first live resume (2026-08-02) diffed whole
            # capture files and reported every part CHANGED on a header
            # line alone.
            changed = CC._prompt_blocks_changed(cap_root / ot, pdir, parts)
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
        if CS.dev_mode:
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
        prompt_capture.prompt_turn_log_open(pdir, ot)
    except Exception as e:                                   # noqa: BLE001
        fail(f"per-turn capture could not be opened: {e}")

    # ALWAYS — the --no-prewarm opt-out is retired (2026-09-09). The three
    # outcomes are stream_prewarm's own and unchanged: a dry run returns before
    # any call, so does a provider with no prompt cache, and otherwise one
    # zero-output-token call per part writes the shared prefix. A --resume
    # re-warms too, as it always did: this sits ahead of the resumed branch.
    if CS.dev_mode:
        emit("command", "\npre-warming caches:")
    try:
        with PC.PHASES.span("open.prewarm"):
            stream_prewarm(client, parts, sysblocks, args.dry_run)
    except Exception as e:                                   # noqa: BLE001
        # The 2026-08-09 traceback's exact site. Seven API calls, and a
        # failure in any of them used to print a stack trace over a
        # transcript that was already on disk.
        emit("command", f"\n  !! PRE-WARM FAILED — {stream_failure_explain(e)}")
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
    else:
        # BLIND, ALWAYS — the --no-blind opt-out is retired (2026-09-09). It
        # existed so the PRIOR sequential protocol could still be run for the
        # opening round; nothing in the tree ever passed it and no probe ever
        # covered the branch. circle_round_run() is NOT orphaned by this: it is
        # what runs every round after the opening, from the Self> loop below.
        if CS.dev_mode:
            emit("command", "\nopening round — BLIND (parallel; CIRCLE_DESIGN §1).")
        with PC.PHASES.span("round"):
            circle_blind_round_run(client, parts, sysblocks, transcript, since_self,
                            state, guard, path, args.dry_run, live=args.live)

    # DISARMED. Past this point the circle has had its opening round, and
    # whatever the transcript holds is the record — including an empty one, if
    # every part passed. The ruling covers a run that DIES before its first
    # statement, not a circle that reached the Self prompt.
    if _opened:
        _opened["armed"] = False

    return CircleOpen(ot=ot, path=path, guard=guard, transcript=transcript,
                      sysblocks=sysblocks, since_self=since_self, state=state,
                      issue_cmds=issue_cmds, circle_ref=circle_ref,
                      console_name=console_name)
