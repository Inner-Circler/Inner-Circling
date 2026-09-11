#!/usr/bin/env python3
"""
phase_clock.py — wall-clock accounting per phase, and the close heartbeat.

    from phase_clock import PHASES
    with PHASES.span("inter.dreaming"):
        ...

RULED 2026-08-30, the operator: *"Inter-circle also needs time accounting
per phase, that is where my concern currently most lies. After circle
/close, I want to aim for no more than 5 minutes, and progress must be
being reported in the command pane at least every 10 seconds, even if its
just a spinner."*

WHY A CLOCK AT ALL. Nothing in this tree measured wall time. The Meter
counts tokens and cost; the close reports carry sizes and hashes; the
per-turn capture stamps each request to the second but records no
duration. Total time is dominated by human time, which is out of scope —
what this measures is everything else: agent time (API calls in flight)
and local work, per named phase, so "which phase is expensive" is a fact
on file rather than a guess. Human time is not invisible either: every
console read is wrapped in the WAITING span, so it is separated out, never
smeared into a phase.

THREE THINGS, ONE MODULE:

    span(name)        a context manager. Records seconds per named phase,
                      aggregated by name. Spans nest; open them from the
                      main thread only (the stack is one stack, and the
                      dreaming pool's workers must not push onto it —
                      the "inter.dreaming" span wraps the whole pool).
    close_begin()     starts the close stopwatch. snapshot() carries the
                      elapsed, circle.circle_spend_report_write() files it, and
                      report_close() says whether the aim was met.
    heartbeat         a daemon thread that reports the open span's name
                      and age at a fixed interval, through `notify`, while
                      the close pipeline works. start_heartbeat() is
                      reentrant — a second caller (inter_circle run by
                      hand) gets False and must not stop a beat it did
                      not start.

STDLIB ONLY, DELIBERATELY. proposal_vetting.py, circle.py and inter_circle.py all
import this; a project import here is a cycle waiting to happen.

THE RECORD IS work/logs/spend_<OT>.json — this module writes no file of
its own. The spend report already exists per circle, is written at the one
moment the numbers are complete, and fails open; the phases ride it as a
`phases` list rather than earning a second file about the same close.
"""
from __future__ import annotations

import contextlib
import datetime
import threading
import time

# The span every console read records under. One name for every prompt —
# the Self> loop, the open's working-set and topic questions, vetting's
# rulings — because the question "how much of this circle was waiting on
# a human" has one answer, not one per prompt.
WAITING = "waiting_on_self"


class PhaseClock:
    """Aggregated wall-clock per named phase, plus the close stopwatch and
    the heartbeat. One instance, PHASES, mirrors llm_client's METER."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[dict] = []
        self._stack: list[tuple[str, float]] = []
        self._close_t0: float | None = None
        self._hb_stop: threading.Event | None = None
        # THE THREAD ITSELF, kept so stop_heartbeat() can JOIN it. Flagging a thread
        # to stop does not stop it; only waiting for it does. See stop_heartbeat().
        self._hb_thread: "threading.Thread | None" = None
        self.notify = None          # callable(str) | None — bound by the caller

    # ------------------------------------------------------------- spans
    @contextlib.contextmanager
    def span(self, name: str):
        t0 = time.monotonic()
        started = datetime.datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._stack.append((name, t0))
        failed = True
        try:
            yield
            failed = False
        finally:
            secs = time.monotonic() - t0
            with self._lock:
                # Pop OUR entry, not blindly the top: an exception between
                # nested spans must not leave the stack lying about who is
                # open. Search from the top; nesting makes ours the first hit.
                for i in range(len(self._stack) - 1, -1, -1):
                    if self._stack[i] == (name, t0):
                        del self._stack[i]
                        break
                self._events.append({"phase": name, "started": started,
                                     "seconds": secs, "error": failed})

    def current(self) -> "tuple[str, float] | None":
        """(name, seconds open so far) of the innermost open span."""
        with self._lock:
            if not self._stack:
                return None
            name, t0 = self._stack[-1]
        return name, time.monotonic() - t0

    # ---------------------------------------------------- the close clock
    def close_begin(self) -> None:
        self._close_t0 = time.monotonic()

    def close_seconds(self) -> "float | None":
        return (None if self._close_t0 is None
                else time.monotonic() - self._close_t0)

    def report_close(self, say, aim_seconds: float, alarm_seconds: float) -> None:
        """One line: the close's own wall time against the ruled aim. Past the aim
        but within `alarm_seconds` it is reported plainly; past that, loudly
        (R540). An alarm set below the aim leaves no plain band, so
        every close past the aim is loud."""
        t = self.close_seconds()
        if t is None:
            return
        if t <= aim_seconds:
            say(f"\n  close pipeline: {t:.0f}s (aim <= {aim_seconds:.0f}s — met)")
        elif t <= alarm_seconds:
            say(f"\n  close pipeline: {t:.0f}s — past the {aim_seconds:.0f}s aim")
        else:
            say(f"\n  !! close pipeline: {t:.0f}s — OVER the {aim_seconds:.0f}s "
                f"aim. The phases list in the spend report says where it went.")

    # ------------------------------------------------------ the heartbeat
    def start_heartbeat(self, interval: float, notify=None, quiet_since=None) -> bool:
        """Begin the every-`interval` progress line. Returns False when a
        beat is already running — the second caller must NOT stop it.

        AND THE SECOND CALLER'S CADENCE IS DISCARDED WITH IT, which the return
        value is the only warning of. Arming at 3s for the whole run makes a
        later 10s arming a no-op; that is intended where one beat serves the
        process, and it is a silent surprise anywhere else. Honour the return.

        `quiet_since` IS WHAT MAKES THIS THE RULED BEHAVIOUR RATHER THAN AN
        APPROXIMATION OF IT. Without it the beat marks elapsed time — it fires
        every `interval` whether or not anything was printed in between. The
        operator ruled a gap *"between any output and another output"*, so a
        callable returning seconds-since-the-last-line is passed in and a tick
        is skipped while the program is still talking. Omitted, the old
        timer behaviour stands, which is what the close's own arming wants."""
        with self._lock:
            if self._hb_stop is not None:
                return False
            self._hb_stop = stop = threading.Event()
        if notify is not None:
            self.notify = notify

        # POLLED, NOT ON A GRID. `while not stop.wait(interval)` woke on a fixed
        # cadence measured from the ARMING, and a tick that found the program
        # still talking was simply dropped — so output landing just after a
        # tick pushed the first mark to the tick after next, and a silence of
        # up to TWICE the interval went unmarked. Measured at 5.96s with a
        # 3-second interval, which is the rule failing at its own number.
        #
        # Waking often and deciding cheaply is the fix: two float comparisons
        # four times a second cost nothing, and the mark then lands within a
        # quarter-second of the moment the silence actually reaches `interval`.
        #
        # SIZED TO THE INTERVAL, never a flat constant. A fixed 0.25 quietly
        # makes every interval below it unreachable — the beat cannot mark
        # faster than it wakes — and the probes drive this at hundredths of a
        # second precisely so they need no real waiting. A quarter of the
        # interval keeps the mark within 25% of its due moment at any cadence,
        # and is 0.25s at the ruled three seconds.
        POLL = max(0.005, min(0.25, interval / 4))

        def _beat() -> None:
            # From the ARMING, so the first mark is a full interval away and
            # not immediate.
            last_mark = time.monotonic()
            while not stop.wait(POLL):
                # STILL TALKING IS NOT WAITING. Checked before the phase, so a
                # long phase that is reporting as it goes stays unmarked.
                if quiet_since is not None and quiet_since() < interval:
                    continue
                # AND A MARK IS ITSELF NOT OUTPUT. The terminal's dot
                # deliberately does not reset the output stamp — otherwise the
                # second dot would never come — so the cadence BETWEEN marks is
                # kept here rather than read from quiet_since.
                if time.monotonic() - last_mark < interval:
                    continue
                cur = self.current()
                if cur and cur[0] == WAITING:
                    continue            # a human is typing; do not spin at them
                fn = self.notify
                if fn is None:
                    continue
                # STOPPED MEANS STOPPED, checked as late as possible — the cheap
                # half. The loop wakes on POLL rather than on the interval, so a
                # thread already PAST its wait when stop.set() lands is several
                # times more likely than it was, and a beat arriving after
                # stop_heartbeat() returned is a line printed over whatever the
                # caller went on to say.
                #
                # THIS CHECK ALONE ONLY NARROWS THE WINDOW; stop_heartbeat()'s
                # join is what closes it. A thread descheduled between here and
                # fn() below still prints, however late the check is made — which
                # is exactly the failure test_phase_clock.py caught about one run
                # in six, and which a blocking notify reproduces every time.
                if stop.is_set():
                    return
                total = self.close_seconds()
                tail = f" ({total:.0f}s since /close)" if total is not None else ""
                line = (f"  … still {cur[0]} ({cur[1]:.0f}s){tail}" if cur
                        else f"  … working{tail}")
                try:
                    fn(line)
                except Exception:       # noqa: BLE001 — a beat must cost nothing
                    pass
                # STAMPED EVEN IF fn RAISED. A notify that throws every time
                # would otherwise leave last_mark untouched and the beat would
                # retry it four times a second for the rest of the run.
                last_mark = time.monotonic()

        t = threading.Thread(target=_beat, name="phase-heartbeat", daemon=True)
        with self._lock:
            self._hb_thread = t
        t.start()
        return True

    # THE JOIN IS THE WHOLE PROMISE — 2026-09-09. Setting the Event only ASKS the beat
    # to stop; a thread already past its own stop check goes on to call notify, and
    # that line lands on top of whatever the caller said next. The loop's late check
    # narrows that window to a few instructions and cannot close it, which is what
    # test_phase_clock.py's "stopped means stopped" was failing on about one run in
    # six — load-dependent, so it never reproduced in a quiet loop and read as a flaky
    # test rather than the real defect it is.
    #
    # A BOUNDED join, and never on our own thread:
    #   TIMEOUT   a notify that blocks for ever must not wedge a close. The state is
    #             cleared BEFORE the join, so a later start_heartbeat() still works
    #             even if this one times out; the thread is a daemon and dies with
    #             the process.
    #   SELF      stop_heartbeat() called from inside a notify would join itself and
    #             raise. The identity test makes that a no-op instead.
    # The lock is released before joining — the beat takes it in current(), so holding
    # it across the join would deadlock the very thread we are waiting for.
    HB_JOIN_TIMEOUT = 5.0

    def stop_heartbeat(self) -> None:
        with self._lock:
            stop, self._hb_stop = self._hb_stop, None
            thread, self._hb_thread = self._hb_thread, None
        if stop is None:
            return
        stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(self.HB_JOIN_TIMEOUT)

    # --------------------------------------------------------- the record
    def snapshot(self) -> dict:
        """The spend report's payload: one row per phase NAME, in first-
        appearance order — count, total seconds, worst single span, and how
        many spans ended in an exception (0 is omitted)."""
        with self._lock:
            events = list(self._events)
        order: list[str] = []
        by: dict[str, dict] = {}
        for e in events:
            row = by.get(e["phase"])
            if row is None:
                order.append(e["phase"])
                row = by[e["phase"]] = {"phase": e["phase"], "count": 0,
                                        "seconds": 0.0, "max_seconds": 0.0,
                                        "errors": 0}
            row["count"] += 1
            row["seconds"] += e["seconds"]
            row["max_seconds"] = max(row["max_seconds"], e["seconds"])
            row["errors"] += 1 if e["error"] else 0
        rows = []
        for name in order:
            r = by[name]
            r["seconds"] = round(r["seconds"], 2)
            r["max_seconds"] = round(r["max_seconds"], 2)
            if not r["errors"]:
                del r["errors"]
            rows.append(r)
        t = self.close_seconds()
        return {"phases": rows,
                "close_seconds": None if t is None else round(t, 2)}

    def reset(self) -> None:
        """Probes, and the start of every circle after the first in one
        process.

        THIS DOCSTRING SAID "Probes only — a live process is one circle and
        never resets" until 2026-08-30, and that stopped being true the day
        the operator ruled *"support multiple circles in one app
        context"*. Spans
        aggregate by NAME, so an un-reset second circle reports its
        `open.prewarm` and `round` totals added to the first's, and its close
        stopwatch measures from a `close_begin()` that already fired. Both
        read as a slow circle rather than as a stale clock — the same failure
        shape as the Meter beside it. `CircleEngine.start()` calls this."""
        self.stop_heartbeat()
        with self._lock:
            self._events.clear()
            self._stack.clear()
        self._close_t0 = None
        self.notify = None


PHASES = PhaseClock()


def stream_timed_read(fn, *args, **kwargs):
    """Route one console read through the WAITING span — the wrapper
    circle.py's read_line() and proposal_vetting.py's direct seam reads share, so
    every second spent at a prompt lands under one name."""
    with PHASES.span(WAITING):
        return fn(*args, **kwargs)
