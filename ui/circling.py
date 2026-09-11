#!/usr/bin/env python3
"""
circling.py — THE WAY A PERSON OPENS A CIRCLE: the two-pane circle/command UI.

    python ui/circling.py             interactive: run the split-screen TUI
    python ui/circling.py --selftest  headless: exercise the engine, no TTY needed
    python ui/circling.py --circle    interactive, wired to the real CircleEngine
                                      /circle.py (--dry-run by default; see --help)
    python ui/circling.py --help      full usage, including the second self-test
                                      at ui/tests/test_circle_engine.py

PROMOTED AND RENAMED 2026-08-23 (R314), from `ui/dual_pane.py`. It was built
as a HARNESS — a cheap test of whether output arriving on its own schedule and
a user mid-keystroke could share one terminal — and the name said so. It has
been the real adapter since 2026-08-10, running circle.py's own main() in a
thread of this process behind rebound seam.py ends, and it is now the entry
point a person is meant to reach for; `coordinator/circle.py` remains the
single-pane way in and everything underneath. The name says THAT.

The old name survives in rulings/ and progress.md, which are append-only and
were deliberately not rewritten, and in docs/dual_pane_integration.md, whose
subject is the two-pane INTEGRATION design — a concept this rename does not
touch. "Dual pane" still names the shape: an upper CIRCLE pane and a lower
COMMAND pane.

WHAT THIS VALIDATES. `docs/circling_and_evolving.md (archived)` proposes a circle pane
(conversation only) and a command pane (rulings only), built so that output
landing in one can never corrupt input focused in the other — by
construction, because the two are disjoint. This harness tests the
cheaper, prior question in one process and one window, before wiring the
real `circle.py` in at all: can independent, asynchronously-arriving
output and a user mid-keystroke in a DIFFERENT pane coexist on screen
without stealing focus, corrupting the in-progress input line, or losing
a keystroke? It held (60 checks below). NOTE: the named-pipe architecture
this docstring originally measured against (§7 of that document) is
retired — `docs/dual_pane_integration.md` (2026-08-10) wires the real
`circle.py` into this same harness over one process and two in-process
seams instead, since a pipe is unneeded once both panes live here.

WHAT THIS IS NOT. Not `circle.py`. Not connected to any part, any LLM, any
real transcript. The top pane's "agents" are three daemon threads on a
random timer, each posting "<Name> statement N" from one shared,
lock-protected counter across all three — enough to be genuinely
asynchronous and unpredictable, not enough to be circle.py, and numbered
so a line lost or duplicated while scrolled away from the live edge is
visible by eye as a gap or a repeat in the sequence, not something you'd
have to take on faith. The bottom pane's input is a stub: pressing Enter
there logs the text and says so; it calls nothing in `coordinator/`.

THE BARE DEMO IS A DEVELOPMENT AFFORDANCE, AND IT IS ASSERTED ONLY AGAINST
CRASHING. Since R314 the way a person opens a circle is `--circle`, so
everything above describes a path the product does not use: the
AgentSimulator branch, its queue, the bare-line demux and the simulator's
shutdown are executed by no probe that checks what they DRAW.
`ui/tests/test_ui_main_loop.py` always supplies a fake engine, and
`test_circling_selftest.py`'s last check runs this demo as a subprocess and
asserts only that it does not exit or print a Traceback within two seconds —
which covers import-time breakage and nothing about the demo's behaviour.
Stated here rather than probed: a probe over a random-timer simulator would
assert the timer, and what could ship undetected is the demo drawing wrongly
or dropping simulator lines, which costs a developer a confusing screen and
costs a circle nothing (audit-register 2026-09-09 #63).

WHY OUTPUT CAN'T LITERALLY "PAUSE ON CLICK". A native text selection —
either because the app never enabled terminal mouse-reporting, or because
the user held Shift to override it — is specifically the case a terminal
does NOT tell the application about; that is what makes it native rather
than app-handled. So there is no click event to catch and no reliable
moment to pause on. What DOES work: every redraw was narrowed to touch
only the rows that actually changed — no more blanket full-screen clears —
so a pane you've scrolled away from the live edge (`↑`/`PageUp`/etc.) is
already left alone by new arrivals, with nothing extra to press. Scrolling
IS the freeze: `body_needs_repaint` skips a pane's body whenever
`visible()` hasn't changed, which is always true the instant you're not
following the live tail. `End` resumes. (An earlier version of this had a
separate `Ctrl-P` freeze toggle; removed once it became clear scrolling
already did the same thing, by the same mechanism, for free.)

STRUCTURE, so the parts that need a real terminal and the parts that don't
are never tangled together:

    Pane, AppState     pure data + state transitions. No I/O. Fully
                       unit-testable without a TTY — see
                       ui/tests/test_circling_selftest.py (self_test() until
                       2026-09-03; the flag still runs it).
    AgentSimulator     the only thread-based piece. Pushes lines onto a
                       queue; never touches the screen itself.
    render_*           takes an AppState and a `write` callable. Testable
                       by passing a list-collecting `write` instead of
                       `sys.stdout.write`.
    poll_key / raw_mode
                       the one genuinely OS-specific, TTY-dependent layer:
                       msvcrt on Windows, termios/select on POSIX. This is
                       the part the self-test cannot exercise and the part
                       that actually needs a person at a keyboard to judge.

CONTROLS. Tab switches focus between panes AND reshapes the split: the
focused pane gets 4/5ths of the available rows, the unfocused one 1/5th,
whichever way round focus currently sits. That IS the focus indicator —
there is no "[FOCUS]" tag on a header and no "focus: X" on the status
line any more, because the pane you are typing in is the tall one, which
is visible without reading anything. Cost of that, stated plainly since
this file documents the selection tradeoff everywhere else: a Tab is a
geometry change, so it does the same full clear-and-repaint a terminal
resize does, and a native mouse selection in progress does not survive
it. Enter submits the focused
pane's input line — and, whether or not there was anything to submit,
brings that pane back to the live edge (same effect as End). An EMPTY
Enter is a deliberate second way to do just the catch-up half of that: it
posts nothing, but still reflows a scrolled/frozen pane back to following,
for whoever just wants to be caught up without reaching for End. Up/Down/
PageUp/PageDown scroll the FOCUSED pane's own scrollback — each pane keeps
its own independent scroll position, and scrolling away from the live edge
freezes that pane's body against new arrivals, which is what to use before
a mouse click-drag-select+copy. Home jumps to the oldest line kept; End
jumps back to the live edge and resumes auto-follow. Left/Right move the
cursor within the focused pane's in-progress input line (not scrollback —
Home/End/PageUp/PageDown act on scrollback even mid-edit, matching the
rest of this cluster). Ctrl-C quits. Nothing else is bound.

RESIZING THE CONTAINING WINDOW cannot be prevented from inside this
process. `GetConsoleWindow()`-based tricks (disable the resize grip via
`SetWindowLong`, etc.) only work against a classic conhost window; under
ConPTY, which Windows Terminal uses, the child process's console window
handle is a hidden message-only pseudo-window, not the real one the user
sees and drags — nothing done to it has any visible effect
(microsoft/terminal#12570). What IS done instead: every loop tick checks
`shutil.get_terminal_size()`, and on a change, recomputes both panes'
heights, clamps any scroll position into the new bounds, and does one
full clean redraw at the new geometry (`_pane_heights`, `Pane.resize`,
`AppState.resize`, in `main_loop`) — so a resize can still happen, but no
longer leaves stale or garbled rows behind. A Tab now runs that exact
same path, since which pane is focused is itself an input to
`_pane_heights`.
"""

from __future__ import annotations

import os
import pathlib
import queue
import random
import re
import shutil
import sys
import threading
import time

# coordinator/ isn't on sys.path by default -- only needed for CircleEngine
# (real circle.py integration), never for the demo/self-test path, so this
# is cheap to always compute but nothing imports coordinator/circle.py
# eagerly; CircleEngine.start() does that lazily.
COORD_DIR = pathlib.Path(__file__).resolve().parent.parent / "coordinator"

# ui/ is this file's own directory, and it is not on sys.path when circling
# is imported rather than run — ui/tests/ imports it, and so does the Ticker
# bridge through CircleEngine. The palette is the only thing it takes from
# there, and it takes ROLES, not RGB (see C_PROMPT below).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import palette as PALETTE                                      # noqa: E402

# WINDOWS CONSOLES: same reasoning as the rest of this project's scripts —
# degrade rather than crash on characters a legacy console can't encode.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IS_WINDOWS = os.name == "nt"

# --------------------------------------------------------------------------
# Pure engine: Pane, AppState. No I/O anywhere in this section.
# --------------------------------------------------------------------------


def ui_line_wrap(line: str, width: int | None) -> list[str]:
    """One logical line -> the display rows it occupies. PURE.

    THE PANE TRUNCATED UNTIL 2026-08-20. `render_pane_body` wrote
    `text[:width]` — one `.lines` entry per screen row, sliced — so a
    statement longer than the terminal was CUT and the rest was never shown
    anywhere. the operator found it by resizing: the text does not come back,
    because it was never on screen to begin with.

    `width=None` MEANS NO WRAPPING, and that is the default a bare `Pane()`
    keeps. Every existing caller that builds a Pane without a terminal (the
    self-test, the harnesses) therefore behaves exactly as before.

    LEADING WHITESPACE BECOMES THE CONTINUATION INDENT. This project's
    coordinator output is written as indented blocks ("  warmed child ...",
    "    focus n0021"), and a wrap that returned continuations to column 0
    would put them under the label column of a two-column table — the exact
    unreadability the 116-character rule exists to prevent, one layer down.

    A WORD LONGER THAN THE WIDTH IS CUT, not left to overflow: the whole
    point is that nothing leaves the screen. An empty line stays one empty
    row rather than vanishing, so a spacer is still a spacer."""
    if width is None or width <= 0 or len(line) <= width:
        return [line]
    indent = line[:len(line) - len(line.lstrip())]
    # A continuation indent that leaves no room to write is not an indent.
    if len(indent) >= width - 8:
        indent = ""
    rows: list[str] = []
    rest = line
    while True:
        room = width if not rows else width - len(indent)
        if len(rest) <= room:
            rows.append((indent if rows else "") + rest)
            return rows
        cut = rest.rfind(" ", 0, room + 1)
        if cut <= 0:
            cut = room                      # one long word: hard cut
        rows.append(((indent if rows else "") + rest[:cut]).rstrip())
        rest = rest[cut:].lstrip()
        if not rest:
            return rows


def _command_surface():
    """coordinator/command_surface, or None where it is not importable.

    The demo path builds an AppState with no backend at all, and this file's
    own docstring says that path is "not circle.py, not connected to any
    part". It still has to answer "is this a command-pane verb", so the
    table is imported directly rather than reached through a backend that
    may not exist."""
    try:
        sys.path.insert(0, str(COORD_DIR))
        import command_surface
        return command_surface
    except Exception:                                          # noqa: BLE001
        return None


ALERT_MARK = "!!"


def ui_is_alert(line: str) -> bool:
    """Whether a COMMAND-channel line is one of circle.py's `!!` lines — the
    roster that does not verify, a corrupted operational file, an
    interrupted close, a dreaming that did not run, a pre-warm failure, a
    crashed engine. Every one of them is emitted as `"\\n  !! ..."`, and so
    is the "fail" mark in transcript_store.py's and initialization.py's own
    check listings, so the mark is the whole test.

    The leading newline is why this strips before looking: `Pane.append`
    splits that into a blank row and a text row, but the demux sees the
    line as it was emitted, ahead of the split. Stripping the indent too is
    what lets the same test read a DISPLAY row back — see
    `Pane.last_alert_row`."""
    return line.lstrip("\n ").startswith(ALERT_MARK)


class Pane:
    """One logical pane's scrollback and in-progress input line.

    `height` is how many scrollback lines are shown at once — older lines
    are kept (nothing is discarded) regardless of scroll position.

    SCROLLING, ABSOLUTE-ANCHORED. `scroll_top` is `None` while "following"
    (the normal, default state: always show the tail, exactly as before
    this existed). Scrolling up sets it to a fixed line INDEX and the view
    stays pinned to that index — not to "N lines from the bottom" — so a
    line arriving while you're reading history does not shift what you're
    looking at even slightly, matching how a terminal or a chat app
    behaves, not how a naive tail-follow would. Scrolling back down past
    the live edge resumes following (`scroll_top` returns to `None`) so a
    single scroll-to-bottom is enough to re-arm auto-follow, rather than
    needing to hold it there."""

    def __init__(self, label: str, prompt: str, height: int):
        self.label = label
        self.prompt = prompt
        self.height = height
        self.lines: list[str] = []       # DISPLAY rows, derived
        # THE SOURCE LINES, kept so a resize can RE-wrap rather than
        # re-truncate. `lines` is what every scroll computation indexes,
        # and it must stay a list of screen rows; deriving it from this on
        # a width change is what makes a narrower terminal show MORE rows
        # of the same text instead of less text.
        self.logical: list[str] = []
        self.width: int | None = None    # None = no wrapping (see wrap_line)
        # THE REDACTED VIEW (2026-08-31) — set_redact()'s own flag. Off by
        # construction for BOTH panes; only main_loop ever calls
        # set_redact(), and only on state.circle — the command pane simply
        # never has it flipped on, which is what "never in any lower tab"
        # means at this level: no per-pane-kind check needed, because
        # nothing ever calls the setter on this pane.
        self.redact_view = False
        self.input_buf = ""
        self.input_cursor = 0          # index into input_buf; 0..len(input_buf)
        self.scroll_top: int | None = None
        # What the BODY last showed — the visible rows AND how many rows the
        # input took from them (2026-08-21: the input wraps, and a wrap that
        # grows or shrinks the input moves the body's bottom edge even when
        # `visible()` itself is unchanged).
        self._painted: tuple[list[str], int] | None = None
        self.input_rows_drawn = 1      # rows the input occupied at its last draw
        # THE PROMPT ACTUALLY ON SCREEN in this pane's input row — B66,
        # 2026-08-25. Set at the two draw sites (render_pane_body and
        # _render_input_row) and nowhere else, so main_loop's prompt-change
        # tick compares against what was DRAWN rather than against its own
        # last reading. The distinction is the whole bug: the keystroke
        # path drew "(waiting)" without telling the tick, so a prompt that
        # went question -> waiting -> SAME question compared equal to the
        # tick's stale baseline and the row kept saying "(waiting)" while
        # the cursor sat at the question's own column — the operator's
        # cursor-80-columns-right screen from the install circle.
        self.input_prompt_drawn: "str | None" = None

    def append(self, line: str) -> None:
        # circle.py's own text is written for a PLAIN SCROLLING TERMINAL —
        # "\nCIRCLE issues (blank = all): " (a blank-line spacer baked into
        # the prompt itself) is completely normal there, since a bare \n
        # just advances the cursor a row before print()/input() continues.
        # `render_pane_body` writes one `.lines` entry per fixed screen
        # row via absolute cursor positioning (_move(row, 1) + text), so an
        # embedded \n is a literal linefeed landing mid-write — it shoves
        # everything after it down and left the row's positioning, and the
        # very next write (often the input-line redraw right below) paints
        # over exactly where it landed. Found live: the working-set prompt
        # never appeared, and a typed line was silently consumed as its
        # answer. Splitting here (not only where the demo path or
        # CircleEngine path calls this) makes every caller's contract
        # match reality: one row in, one row out.
        for one in (line.split("\n") if "\n" in line else [line]):
            self.logical.append(one)
            self.lines.extend(ui_line_wrap(self._display_line(one), self.width))

    def _display_line(self, one: str) -> str:
        """The rendered form of one LOGICAL line — redacted when this
        pane's redact_view is on, verbatim otherwise. Presentation only:
        `self.logical` (and everything the transcript file holds) is
        never touched, only what THIS pane derives from it for the
        screen."""
        if not self.redact_view:
            return one
        import stream_redaction as SR
        return SR.stream_redact(one)

    def body_needs_repaint(self, input_rows: int = 1) -> bool:
        """Whether the BODY rows are stale — i.e. whether `visible()` has
        actually changed since the last paint. This is what makes
        scrolling double as a freeze: while scrolled away from the live
        edge, `visible()` is pinned (see `Pane` docstring) and stays
        identical however much new content piles up underneath, so this
        keeps returning False and the body is simply never touched. The
        header is a separate concern (see `_header_text`/`render_pane`)
        and is never gated by this, so the live "N below" count can keep
        climbing without a single body row being rewritten.

        `input_rows` (2026-08-21): how many rows the wrapped input takes —
        a change there moves the body's bottom edge, so it is part of what
        "stale" means. The default keeps every legacy caller exact."""
        return (self.visible(), input_rows) != self._painted

    def mark_painted(self, input_rows: int = 1) -> None:
        self._painted = (self.visible(), input_rows)

    def visible(self) -> list[str]:
        if not self.height:
            return []
        if self.scroll_top is None:
            return self.lines[-self.height:]
        return self.lines[self.scroll_top:self.scroll_top + self.height]

    def _max_top(self) -> int:
        return max(0, len(self.lines) - self.height)

    def is_scrolled(self) -> bool:
        return self.scroll_top is not None

    def hidden_below(self) -> int:
        """Lines below the current view — 0 while following."""
        if self.scroll_top is None:
            return 0
        return max(0, len(self.lines) - (self.scroll_top + self.height))

    def hidden_above(self) -> int:
        """Lines above the current view — nonzero even while following, as
        long as there's more scrollback than fits: it's "how far you COULD
        scroll up", not just "how far you HAVE"."""
        top = self.scroll_top if self.scroll_top is not None else self._max_top()
        return max(0, top)

    def line_up(self, n: int = 1) -> None:
        max_top = self._max_top()
        if max_top == 0:
            return                      # nothing to scroll to
        current = self.scroll_top if self.scroll_top is not None else max_top
        self.scroll_top = max(0, current - n)

    def line_down(self, n: int = 1) -> None:
        if self.scroll_top is None:
            return                      # already following
        max_top = self._max_top()
        new_top = self.scroll_top + n
        self.scroll_top = None if new_top >= max_top else new_top

    def page_up(self) -> None:
        self.line_up(max(1, self.height))

    def page_down(self) -> None:
        self.line_down(max(1, self.height))

    def jump_top(self) -> None:
        if self._max_top() > 0:
            self.scroll_top = 0

    def jump_bottom(self) -> None:
        self.scroll_top = None

    def last_alert_row(self) -> int | None:
        """The row index of the most recent `!!` line, or None if this pane
        holds none. Called immediately after the alert was appended, so the
        last match IS that alert — and it is the FIRST row of it, since only
        that row carries the mark: `wrap_line` indents a continuation, it
        does not repeat what the line started with."""
        for i in range(len(self.lines) - 1, -1, -1):
            if ui_is_alert(self.lines[i]):
                return i
        return None

    def pin_top(self, index: int) -> None:
        """Anchor the view with `index` as its TOP row.

        DELIBERATELY NOT CLAMPED to `_max_top()`, unlike `resize` and
        `set_width`. Pinning an alert that has just arrived means pinning
        the LAST row, and a clamp would pull that straight back to the tail
        — where the next twenty lines of output are exactly what push the
        alert off the top of the window again. Unclamped, the view begins
        at the alert and whatever follows it fills in BELOW, which is the
        whole point. `visible()` returns a short list until it does;
        `render_pane_body` already blanks the rows it has no text for."""
        self.scroll_top = max(0, index)
        self._painted = None

    def _rebuild(self) -> None:
        """Re-derive `.lines` from `.logical` under whatever is currently
        true of this pane — width, and (2026-08-31) redact_view. Shared by
        set_width() and set_redact(): TOGGLING REDACTION IS
        ARCHITECTURALLY A RESIZE — both are "the same source lines render
        differently now" — so one rebuild body serves both rather than
        two copies of the same loop drifting apart.

        SCROLL POSITION IS CLAMPED, NOT PRESERVED, for either caller.
        Re-deriving changes how many rows the same text occupies, so an
        absolute row index means something different afterwards — see
        set_width()'s own long-standing reasoning, which now covers both."""
        rows: list[str] = []
        for one in self.logical:
            rows.extend(ui_line_wrap(self._display_line(one), self.width))
        self.lines = rows
        if self.scroll_top is not None:
            self.scroll_top = max(0, min(self.scroll_top, self._max_top()))
        self._painted = None

    def set_width(self, width: int | None) -> None:
        """Adopt a display width and RE-WRAP everything already held.

        Called by render_pane_body on every paint, so a terminal resize
        reflows the whole scrollback instead of re-slicing it. Cheap and
        idempotent: it returns at once unless the width actually moved."""
        if width == self.width:
            return
        self.width = width
        self._rebuild()

    def set_redact(self, flag: bool) -> None:
        """Flip the redacted view and re-render everything already held —
        toggling mid-circle changes what is ALREADY on screen, not only
        what arrives after, matching how Ticker's own redact toggle
        behaves (2026-08-31). Idempotent, same discipline as set_width()."""
        if flag == self.redact_view:
            return
        self.redact_view = flag
        self._rebuild()

    def resize(self, height: int) -> None:
        """Change how many lines this pane shows, e.g. after the terminal
        window itself was resized. `lines` is never touched — only how
        much of it is currently visible. If scrolled, `scroll_top` is
        clamped to the new bounds so it can't point past what the smaller
        (or larger) pane can actually show. `_painted` is reset so the
        next render unconditionally repaints the body — `visible()` will
        almost always already differ after a height change, but resetting
        outright means this doesn't depend on that being true, and a
        resize is exactly the moment a stale `_painted` would otherwise
        leave old rows uncleared on screen."""
        self.height = max(0, height)
        if self.scroll_top is not None:
            self.scroll_top = max(0, min(self.scroll_top, self._max_top()))
        self._painted = None


#  Named tokens `poll_key()` returns for keys with no single-character
#  form. Always length > 1, which is what `handle_key` uses to tell "a
#  named key" apart from "typed text" — no real keystroke can produce a
#  bare multi-character string through either input backend, since both
#  read one wide-char (Windows) or one byte (POSIX) per normal key.
SCROLL_KEYS: dict[str, str] = {
    "UP": "line_up", "DOWN": "line_down",
    "PGUP": "page_up", "PGDN": "page_down",
    "HOME": "jump_top", "END": "jump_bottom",
}

# LEFT/RIGHT move the cursor WITHIN the focused pane's in-progress input
# line — a separate table from SCROLL_KEYS because these mutate
# `input_buf`/`input_cursor`, not scrollback position, even though both
# arrive from `poll_key` as the same kind of named multi-character token.
EDIT_KEYS: dict[str, int] = {"LEFT": -1, "RIGHT": 1}

# THE DEDICATED CLUSTER'S OWN TOKENS, 2026-08-25 — a row of the INPUT, not a
# line of the PANE. `poll_key` produces these only where the two key clusters
# can be told apart, which today is Windows alone (`\xe0` vs `\x00`); no POSIX
# terminal distinguishes the numpad — most send `ESC [ A` for both — so that
# branch keeps every arrow on SCROLL_KEYS and these are simply never emitted.
CURSOR_ROW_KEYS: dict[str, int] = {"CUR_UP": -1, "CUR_DOWN": 1}
# ...and the two that go to an END of the whole input rather than of a row: a
# wrapped line is one thing being typed, and "back to the start" means the
# start of what you wrote, not of the row it happens to sit on.
CURSOR_ENDS: dict[str, str] = {"CUR_HOME": "start", "CUR_END": "end"}


class AppState:
    """Every state transition in one place, keyed by a single character (or
    one of the named tokens in `SCROLL_KEYS`).

    `handle_key` returns a short tag describing what changed, so the caller
    (interactive loop or self-test) knows how much of the screen needs
    redrawing — "input" (cheapest: one line), "submit" or "scroll"
    (redraw just the focused pane), "focus" (BOTH pane heights changed:
    focus drives the 4/5–1/5 split, so this needs the same full redraw a
    terminal resize gets, not a header touch-up as it did before),
    "quit", or None (an unhandled/control character, ignored)."""

    def __init__(self, circle_height: int, command_height: int, backend=None):
        self.circle = Pane("CIRCLE", "Self> ", circle_height)
        self.command = Pane("COMMAND", "cmd> ", command_height)
        self.focus = "circle"          # or "command"
        self.running = True
        self.help_mode = False         # True while a help listing is up.
                                        # It no longer decides the split —
                                        # focus does (see `_pane_heights`),
                                        # and help is typed in COMMAND,
                                        # which therefore already holds
                                        # focus and already has the 4/5ths.
                                        # Kept because the ruled
                                        # help/revert signal pair is what
                                        # tells `main_loop` a full redraw
                                        # is due at all.
        # docs/dual_pane_integration.md §1/§5 step 3. None (the default)
        # preserves today's self-tested stub behavior in `_submit` below,
        # byte-for-byte -- test_circling_selftest.py asserts the exact stub strings,
        # so this must stay opt-in, never a silent behavior change to the
        # demo path. A `CircleEngine` is the one real implementation today.
        self.backend = backend
        # The row `on_alert` wants pinned, waiting for the caller's
        # focus-driven resize to happen first — see `apply_alert_anchor`.
        self._alert_anchor: int | None = None

    def focused_pane(self) -> Pane:
        return self.circle if self.focus == "circle" else self.command

    def toggle_focus(self) -> None:
        """Focus alone. The pane HEIGHTS that follow from it are applied by
        whoever knows the terminal's row count — `main_loop`, via
        `_pane_heights(rows, state.focus)` — so this stays pure state, as
        every other transition in this class is, and remains callable from
        a headless self-test with no geometry in hand."""
        self.focus = "command" if self.focus == "circle" else "circle"

    def resize(self, circle_height: int, command_height: int) -> None:
        """Route a detected terminal resize to both panes. Each pane's
        scroll position and content are handled independently by
        `Pane.resize` — this just fans the new heights out."""
        self.circle.resize(circle_height)
        self.command.resize(command_height)

    def handle_key(self, ch: str) -> str | None:
        if not ch:
            return None
        pane = self.focused_pane()
        if ch in SCROLL_KEYS:
            # SCROLLING APPLIES TO WHICHEVER PANE HAS FOCUS — the same
            # model as typing. To scroll the other pane, Tab to it first.
            # Each pane keeps its own `scroll_top`, so the two are always
            # independent regardless of which one is currently reachable.
            getattr(pane, SCROLL_KEYS[ch])()
            return "scroll"
        if ch in EDIT_KEYS:
            pane.input_cursor = max(0, min(len(pane.input_buf),
                                            pane.input_cursor + EDIT_KEYS[ch]))
            return "input"
        if ch in CURSOR_ROW_KEYS:
            self.move_cursor_row(pane, CURSOR_ROW_KEYS[ch])
            return "input"
        if ch in CURSOR_ENDS:
            pane.input_cursor = (0 if CURSOR_ENDS[ch] == "start"
                                 else len(pane.input_buf))
            return "input"
        if ch == "\t":
            self.toggle_focus()
            return "focus"
        if ch in ("\r", "\n"):
            text = pane.input_buf
            pane.input_buf = ""
            pane.input_cursor = 0
            if text.strip() or self._answering(pane):
                resize_signal = self._submit(pane, text)
                return resize_signal or "submit"
            # A bare Enter on an empty line posts nothing, but still
            # reflows — the same "back to the live edge" catch-up a real
            # submit gives, for whichever pane is focused. Deliberate: an
            # empty Enter is the escape hatch for "nothing to say, just
            # catch me up" without having to reach for End. Only actually
            # redraws if it changed anything — `is_scrolled()` is checked
            # BEFORE `jump_bottom()` so a bare Enter while already
            # following stays the cheap no-op it always was.
            was_scrolled = pane.is_scrolled()
            pane.jump_bottom()
            return "scroll" if was_scrolled else "input"
        if ch in ("\x7f", "\b"):
            if pane.input_cursor > 0:
                pane.input_buf = (pane.input_buf[:pane.input_cursor - 1]
                                   + pane.input_buf[pane.input_cursor:])
                pane.input_cursor -= 1
            return "input"
        if ch == "\x03":               # Ctrl-C
            self.running = False
            return "quit"
        if len(ch) == 1 and ch.isprintable():
            pane.input_buf = (pane.input_buf[:pane.input_cursor] + ch
                               + pane.input_buf[pane.input_cursor:])
            pane.input_cursor += 1
            return "input"
        return None                    # other control chars: ignored

    def _pane_verb(self, text: str) -> str | None:
        """The command-pane verb this circle-dialog line stands alone as,
        or None. D55(2), 2026-08-20 — see `_submit`. The classifier itself
        moved to command_surface.command_pane_verb_read 2026-08-30, when the Ticker
        bridge turned out to need the same test below this pane layer;
        one classifier, both flavors."""
        cs = getattr(self, "_CS", None) or _command_surface()
        if cs is None:
            return None
        return cs.command_pane_verb_read(text)

    def _answering(self, pane: Pane) -> bool:
        """True when a blocked `read_line` will consume THIS pane's next
        line AND an empty line is a legal answer to it — which is what
        lets a bare Enter reach the seam at all.

        Three reads need it. `proposal_vetting.py` offers "(or Enter to skip)",
        and the working-set and topic prompts are both documented
        "blank = ...". Before R221 the `text.strip()` guard above dropped
        every one of them before the seam, so all three affordances were
        unreachable from this UI.

        FALSE FOR THE SPEAKING TURN, which is the load-bearing carve-out:
        `Self>` is circle channel AND the steady state of a running circle,
        so gating on the channel alone would turn every catch-up Enter
        into an empty statement plus a stray "[You]: " echo, killing the
        documented behaviour just below. FALSE with no backend at all —
        the demo and self-test path, which must keep behaving exactly as
        it did before any of this existed."""
        b = self.backend
        if b is None or not getattr(b, "waiting_for_input", False):
            return False
        if getattr(b, "speaking_turn", False):
            return False
        want = "circle" if pane is self.circle else "command"
        return getattr(b, "waiting_for_channel", "circle") == want

    def _blank_echo(self) -> str:
        """What "[You]: " shows for a BLANK line that answered a pending
        circle-channel question (2026-08-21). The question's own legend, if it
        has one — "(blank = all, 'none', '?')" -> "(blank = all)"; "(blank =
        open)" -> "(blank = open)" — else the bare fact: "(blank)"."""
        q = getattr(self.backend, "pending_prompt", "") if self.backend else ""
        m = re.search(r"blank\s*=\s*([^,)]+)", q or "")
        return f"(blank = {m.group(1).strip()})" if m else "(blank)"

    def on_state(self, token: str) -> str | None:
        """The coordinator's own word about where the close is (seam channel
        "state", 2026-08-21): main_loop calls this for every "state" item
        the engine queues. "closing" is the handover the operator asked for on
        2026-08-20 — echo into the room, move focus to the command pane,
        scroll it to its live edge, say what the wait is for — moved HERE
        from the typed "/close" (2026-08-21) because the first /close can
        be a question, not a close. Returns "focus" when both pane heights
        must be redrawn, else None. Every other token ("", "close-confirm-
        pending") changes nothing on screen: the engine keeps it for
        submit_command and the prompt renderers."""
        if token in ("closing", "initializing", "initialized"):
            # THE COORDINATOR'S OWN HANDOVER WINS over a pending alert
            # anchor. Each of these branches puts a pane at its live edge on
            # purpose, and an anchor applied afterwards — main_loop resolves
            # both in the same drain tick — would drag the view straight
            # back off it.
            self._alert_anchor = None
        if token == "closing":
            self.circle.append("Closing this circle...")
            self.focus = "command"
            self.command.jump_bottom()
            self.command.append(
                "closing the circle... collecting memories, please wait...")
            return "focus"
        # THE INITIALIZATION HANDOVER — R330, 2026-08-23 (docs/
        # Initialization.md §2.2): the first-run dialogs run on the COMMAND
        # channel before the working-set question, so the command pane takes
        # focus (and with it the 4/5ths split) for their duration, and the
        # circle pane takes it back once "Starting your circle..." has
        # printed. The same shape as "closing" above, in both directions.
        if token == "initializing":
            self.focus = "command"
            self.command.jump_bottom()
            return "focus"
        if token == "initialized":
            self.focus = "circle"
            self.circle.jump_bottom()
            return "focus"
        return None

    def move_cursor_row(self, pane: Pane, delta: int) -> None:
        """One VISUAL ROW up or down inside a wrapped input, keeping the
        column — what the dedicated Up/Down arrows do since 2026-08-25.

        NO NEW GEOMETRY. `_input_rows()` already returns each row's
        half-open range into `prompt + buf`, and it is the same function
        the row drawer and the cursor placer read, so this cannot land the
        cursor anywhere the text is not. The prompt is part of row 0, which
        is why a column landing inside it clamps to the start of the buffer
        rather than to a negative index.

        A NO-OP AT BOTH ENDS AND ON AN UNWRAPPED LINE — a text box does
        nothing when you press Up on its first row. It deliberately does
        NOT fall back to scrolling: that would put a key's meaning back
        inside the state of the line, which is the thing having two key
        clusters removes. The numpad scrolls, always.

        The append cell — the position after the last character — belongs
        to the LAST row only; an earlier row's last addressable column is
        the character before its break."""
        prompt = (_circle_prompt(self) if pane is self.circle
                  else _command_prompt(self))
        ranges = _input_rows(prompt, pane.input_buf, pane.width)
        if len(ranges) < 2:
            return
        pos = len(prompt) + pane.input_cursor
        cur = len(ranges) - 1
        for i, (_s, e) in enumerate(ranges):
            if pos < e:
                cur = i
                break
        target = cur + delta
        if not 0 <= target < len(ranges):
            return
        col = pos - ranges[cur][0]
        s, e = ranges[target]
        last = e if target == len(ranges) - 1 else max(s, e - 1)
        pane.input_cursor = max(0, min(len(pane.input_buf),
                                       min(s + col, last) - len(prompt)))

    def _ended(self) -> bool:
        """Has the engine thread finished — a close, an abort, or a crash?

        False for the demo path and for any backend that never started, so
        every caller reads "still running" where there is nothing running
        at all, which is what those paths have always assumed."""
        b = self.backend
        fin = getattr(b, "finished", None)
        return bool(b is not None and getattr(b, "_thread", None) is not None
                    and fin is not None and fin.is_set())

    def on_finished(self) -> str | None:
        """THE CIRCLE IS OVER — say so, and say how to leave. The operator,
        2026-08-25, after a live close: *"After /close finishes its
        post-close processing, the UI just sits. It is not clear that
        everything is done and ready for app exit, nor is it clear how to
        exit. ^C and /abort both seem wrong. Another /close seems
        redundant, but I tried it."* He was right on all three counts:
        /abort has nothing left to abort, a second /close is refused, and
        Ctrl-C is the documented quit but reads like an escape from
        something wrong rather than the ordinary way out.

        Called ONCE by main_loop, when the engine thread has finished AND
        its output has all been drained, so this lands last. The same
        handover shape as on_state("closing") — focus, live edge, a line
        naming the verb — because that is what put the operator in this
        pane for the close itself.

        WHAT IT CLAIMS IS WHAT THE ENGINE REPORTED. An /abort writes
        nothing and a crashed run may have written half of something, so
        the banner never says "everything is written" on its own account:
        it says the coordinator is done, and says separately whether the
        run reported a problem."""
        b = self.backend
        bad = (getattr(b, "crashed", None) is not None
               or getattr(b, "exit_code", 0) not in (0, None))
        self.focus = "command"
        self.command.jump_bottom()
        self._alert_anchor = None      # the banner is the last word
        if self.circle.lines:
            self.circle.append("")
        self.circle.append("*** the circle is over — nothing typed here "
                           "reaches it now. ***")
        self.command.append("")
        self.command.append(
            "  THE CIRCLE IS OVER — and it reported a problem; the lines "
            "above say what." if bad else
            "  THE CIRCLE IS OVER — the coordinator has finished, and has "
            "written everything it was going to write.")
        self.command.append(
            "  Nothing further happens in this window. Type  quit  to close "
            "it.")
        return "focus"

    def on_alert(self, line: str) -> str | None:
        """A COMMAND-channel line has just been appended: if it is a `!!`
        one, bring it into view. The operator, 2026-08-25, after an open-time
        "its DREAMING did not run" scrolled out of a one-fifth pane while
        the proposal listing under it took the screen: *"When a circle is
        run and errors are found, bring focus (and size) to the command
        pane and scroll to the top so that the error is visible."*

        Focus carries the SIZE with it (`_pane_heights`) — the same shape as
        the "closing" handover above — and the scroll anchor is what keeps
        the alert on screen once the output that follows it arrives.

        Returns "focus" when both pane heights must be redrawn, which is
        also when the caller owes `apply_alert_anchor()` AFTER its
        `state.resize(...)`; that method says why the order is not
        optional.

        TWO CASES DELIBERATELY DO NOT TAKE FOCUS:

        the pane is already scrolled
            the reader's own position wins. This is also what makes the pin
            one-shot: a second `!!` line in the same burst finds the pane
            scrolled and leaves the FIRST one anchored, rather than walking
            the view down to the last problem and hiding the first.
        Self is mid-sentence
            a non-empty `circle.input_buf` means a statement is part-way
            typed, and every keystroke after a focus change would land in
            cmd> instead. The alert is still pinned, so it is on screen in
            the small pane; only the handover is withheld.

        KNOWN LIMIT: a pin leaves the pane scrolled, so a LATER alert — one
        raised at /close, say — does not re-fire until the pane is caught
        up with End or a bare Enter. Telling "the reader scrolled" apart
        from "an earlier alert pinned this" needs a flag this does not
        have, and did not need to have to answer what was asked."""
        if not ui_is_alert(line):
            return None
        if self.command.is_scrolled():
            return None
        row = self.command.last_alert_row()
        if row is None:
            return None
        if self.circle.input_buf:
            self.command.pin_top(row)
            return None
        self.focus = "command"
        self._alert_anchor = row
        return "focus"

    def apply_alert_anchor(self) -> None:
        """Apply the anchor `on_alert` set — AFTER the caller's focus-driven
        `resize`, never before it. `Pane.resize` CLAMPS `scroll_top` into
        `_max_top()`, so a pin applied first is pulled silently back to the
        tail by the very resize that made the pane tall enough to read the
        alert in. The anchor and main_loop's `refocus` flag are set
        together and resolved in the same drain tick; nothing may sit
        between them.

        A no-op when nothing is pending — which is every other reason
        main_loop redraws both panes."""
        if self._alert_anchor is None:
            return
        self.command.pin_top(self._alert_anchor)
        self._alert_anchor = None

    def handle_text(self, text: str) -> str:
        """Bulk-insert a run of plain characters into the focused pane's
        input line AT THE CURSOR, in ONE mutation, for `read_burst`'s
        benefit — a paste lands as many characters at once, and the
        single-keystroke path above would mean one input_buf update AND
        one screen redraw PER CHARACTER. `read_burst` has already
        converted any embedded CR/LF to spaces before this is called, so
        nothing here needs to guard against a paste containing a line
        break. For an ordinary single keystroke (`read_burst`'s common,
        degenerate case) this behaves identically to the
        printable-character branch in `handle_key`."""
        pane = self.focused_pane()
        pane.input_buf = (pane.input_buf[:pane.input_cursor] + text
                           + pane.input_buf[pane.input_cursor:])
        pane.input_cursor += len(text)
        return "input"

    def _submit(self, pane: Pane, text: str) -> str | None:
        """WHAT SUBMIT MEANS TODAY. The circle pane always echoes the
        user's own line locally, the same as before a `CircleEngine` ever
        existed — `circle.py` never emits Self's own statement back (see
        `CircleEngine._read_line`'s comment), because in the original
        single-terminal design Self already sees what he typed. With no
        `backend` attached (`self.backend is None`, the default, and what
        the self-test exercises), the command pane stays the STUB it
        always was: it logs what was typed and says plainly that nothing
        was executed. With a `CircleEngine` attached, dispatch belongs to
        `submit_command()` — the pane's own verbs ('quit', 'abort', 'help',
        'status', 'resume', the unlisted 'dev') and the merged verb surface;
        anything that is not a COMMAND in the current dev state is JUNK and
        is answered with the help listing (R285,
        2026-08-21; it was `not understood, see 'help'` from 2026-08-10).

        RETURN VALUE: normally None. 'help_resize'/'revert_resize' when
        this submission should expand or restore the pane split — the operator:
        "If help is invoked, resize the panes to 1/5th and 4/5ths. When
        a circle is started or continued with a user circle entry,
        revert the pane sizes." `handle_key` forwards this in place of
        its usual 'submit' effect so `main_loop` knows a FULL redraw (new
        heights, not just the focused pane) is needed."""
        resize_signal = None
        if pane is self.circle:
            # THE CIRCLE IS OVER AND NOTHING CAN CONSUME A LINE — 2026-08-25.
            # `submit_circle` queues unconditionally and the engine thread is
            # gone, so a line typed here after the end sat on `circle_in`
            # forever AND cleared `line_taken`, which is what pinned the row
            # at "(waiting — the parts are replying)" in front of a finished
            # circle. Refused, in the command pane, naming the one verb that
            # ends the window.
            if self._ended():
                self.command.append(
                    "  the circle is over — nothing typed in the room "
                    "reaches it now. Type  quit  to close this window.")
                self.command.jump_bottom()
                return "focus" if self.focus == "command" else None
            # A COMMAND-PANE VERB STANDING ALONE IN CIRCLE DIALOG IS A
            # NO-OP — RULED 2026-08-20, D55(2), verbatim: *"no command pane
            # verb standing alone in any circle dialog text may EVER be
            # recognised - standalones MUST be ignored no-ops. Only
            # validated "[" ANNOTATION_COMMAND "]" may be recognised, and
            # then only to stage for user vetting."*
            #
            # IT WAS RECOGNISED, AND IT RAN. The circle pane forwards its
            # line VERBATIM into circle.py's one Self> loop, which does not
            # know which pane sent it — so with dev on, `/practice-add ...`
            # typed into the ROOM wrote a practice. docs/BNF.md defines
            # COMMAND as cmd>-only; the grammar and the code disagreed, and
            # this is the code moving.
            #
            # ENFORCED HERE BECAUSE HERE IS WHERE THE PANE IS KNOWN. Once
            # the circle pane cannot send one, anything that reaches that
            # loop wearing a command-pane head necessarily came from the
            # command pane, which is the invariant the loop has always
            # assumed and never had.
            #
            # NOT SILENT, DELIBERATELY. A no-op that says nothing is the
            # exact failure that opened the 2026-08-20 session — a typed
            # line vanishing with no trace. The notice goes to the COMMAND
            # pane, never the room: the circle sees nothing, which is what
            # "no-op" has to mean for the parts.
            head = self._pane_verb(text)
            if head is not None:
                # /quit IS THE WINDOW'S VERB, cmd>-only (2026-08-31,
                # R414) — refused here like a command-pane
                # verb, but "stage it as an annotation" is advice for a
                # command, and quit is not one
                self.command.append(
                    "  quit closes this window — type it at cmd>. Nothing "
                    "was spoken."
                    if head == "/quit" else
                    f"  {head} is a command-pane verb — ignored in the room, "
                    f"not spoken and not run. Type it at cmd>, or bracket it "
                    f"as an annotation to stage it for a ruling.")
                self.command.jump_bottom()
                return "focus" if self.focus == "command" else None
            # THE MIRROR OF submit_command's OPENING GUARD, 2026-08-21. Before
            # the Self> loop exists, a COMMAND-channel question can be pending —
            # a vetting a)pprove/d)eny/s)kip at priming, "type 'yes' to open
            # a NEW circle" — and a line typed into the ROOM then would sit
            # on circle_in until the NEXT circle-channel read, which is the
            # working-set question: it would become the working set, the
            # same way a cmd> line became one in the other direction. Refused
            # with the question named. MID-CIRCLE speech is untouched:
            # "continue to allow the user to make statements" during
            # (waiting) was ruled 2026-08-20, and once the loop is reached
            # every circle-channel read is Self's own turn.
            b = self.backend
            if (b is not None and getattr(b, "waiting_for_input", False)
                    and getattr(b, "waiting_for_channel", "circle") == "command"
                    and not getattr(b, "loop_reached", True)):
                q = getattr(b, "pending_prompt", "")
                self.command.append(
                    "  the circle is asking "
                    + (f"'{q}' " if q else "a question ")
                    + "in the command pane — answer there first; nothing "
                    "was spoken.")
                self.command.jump_bottom()
                return "focus" if self.focus == "command" else None
            # THE ECHO IS THE RECORD — 2026-08-21, the lab circle
            # 2026-08-21_1139. A circle-channel QUESTION is no longer echoed
            # into this pane (CircleEngine._read_line: the row carries it),
            # so the answer must say what it was: a blank answer to a
            # pending question is shown as the legend the question itself
            # gave — "[You]: (blank = all)" for the working set, "(blank =
            # open)" for the topic — never a bare "[You]: " that reads as
            # nothing. The legend is read off the prompt text, so this pane
            # learns no coordinator vocabulary of its own.
            shown = text if text.strip() else self._blank_echo()
            # TWO EMPTY LINES BEFORE SELF'S OWN LINE — same finding, the operator:
            # *"preface them with an extra empty line"*, his example showing
            # two. The parts' statements arrive with one blank between them;
            # Self's used to butt straight against the last part's last
            # line. The pane only, and only once the pane has content — the
            # transcript FILE already separates every entry with one blank
            # and is parsed back, so it is not touched.
            if pane.lines:
                pane.append("")
                pane.append("")
            pane.append(f"[You]: {shown}")
            if self.backend is not None:
                self.backend.submit_circle(text)
            # /close NO LONGER HANDS THE WINDOW OVER ON THE TYPED TEXT —
            # 2026-08-21 (it did since 2026-08-20). The first /close may
            # only SHOW the unruled proposals and ask for a second, and the
            # operator found himself moved to cmd> where that second /close
            # was refused. The handover now follows the coordinator's own
            # word: circle.py emits state "closing" when the close actually
            # proceeds, main_loop calls on_state(), and THAT echoes, moves
            # focus and redraws. See on_state().
            if self.help_mode:
                self.help_mode = False
                resize_signal = resize_signal or "revert_resize"
        else:
            pane.append(f"> {text}")
            if self.backend is not None:
                effect = self.backend.submit_command(text)
                if effect == "quit":
                    self.running = False
                elif effect == "help":
                    self.help_mode = True
                    resize_signal = "help_resize"
                elif effect is not None and effect.startswith("resume:"):
                    # Forwarded to main_loop verbatim (its own effect-tag
                    # convention already handles arbitrary non-None
                    # strings via `resize_signal or "submit"` below) —
                    # only main_loop can actually replace the running
                    # CircleEngine, so AppState just relays the signal.
                    resize_signal = effect
                # The real response text (help listing / not-understood /
                # abort acknowledgement) was queued by submit_command()
                # onto engine.out_queue with channel "command" —
                # main_loop's normal drain path renders it next cycle,
                # same as any other command-channel line, not appended
                # here.
            else:
                pane.append("  (stub — no command wired up; this harness only "
                             "tests focus and interleaving)")
        pane.jump_bottom()   # posting always brings you back to the live edge
        return resize_signal


# --------------------------------------------------------------------------
# AgentSimulator: the one thread-based piece. Talks to a queue, never the
# screen — so it cannot race with rendering by construction.
# --------------------------------------------------------------------------

# GENERIC BY DESIGN — audit-register.md #1, 2026-09-08. These three name the DEMO
# simulator's threads and nothing else; they never touched the roster, the record, or a
# real circle. They were three real part Tags, and this module SHIPS
# (packaging/required.toml), so every bundle carried them — three of the 84 MEDIUM findings
# packaging/sanitize.py raises and its own docstring explains: "a part name ... these
# identify a living relationship, not a mechanism." A demo needs placeholders, not somebody's
# inner life, and a recipient reading their own bundle should not meet another person's parts.
PARTS: tuple[str, ...] = ("Alpha", "Beta", "Gamma")


class AgentSimulator:
    """Three daemon threads, one per name in `PARTS`, each posting on its
    own independent random timer (2-5s) — genuinely concurrent and
    unpredictable relative to whatever the user is doing in either pane;
    that unpredictability is the point, a fixed schedule would not test
    anything.

    EVERY STATEMENT IS NUMBERED FROM ONE SHARED, LOCK-PROTECTED COUNTER
    ACROSS ALL THREADS — "Alpha statement 7", "Beta statement 8",
    "Alpha statement 9" — a single global sequence, not one per part. That
    is what turns "did scrolling away from the live edge ever lose one?"
    into something checkable by eye: the numbers must run consecutively
    with no gaps, regardless of which part said which one. A per-part
    counter would let a dropped line hide inside a still-plausible-looking
    sequence for the other two parts. The lock matters: three threads
    calling `_next_seq()` at once is exactly the race that would silently
    hand out a duplicate or skip a number if the increment weren't
    protected — verified in test_circling_selftest.py by actually running the
    simulator and checking the collected numbers are exactly consecutive."""

    def __init__(self, out_queue: "queue.Queue[str]",
                 delay_range: tuple[float, float] = (2.0, 5.0)):
        self.q = out_queue
        self.delay_range = delay_range
        self.stop_flag = threading.Event()
        self._threads: list[threading.Thread] = []
        self._seq = 0
        self._seq_lock = threading.Lock()

    def _next_seq(self) -> int:
        with self._seq_lock:
            self._seq += 1
            return self._seq

    def start(self) -> None:
        for name in PARTS:
            t = threading.Thread(target=self._run, args=(name,), daemon=True)
            t.start()
            self._threads.append(t)

    def _run(self, name: str) -> None:
        while not self.stop_flag.is_set():
            if self.stop_flag.wait(random.uniform(*self.delay_range)):
                break
            n = self._next_seq()
            self.q.put(f"[{name}]: {name} statement {n}")

    def stop(self) -> None:
        self.stop_flag.set()


# --------------------------------------------------------------------------
# CircleEngine: the real adapter, docs/dual_pane_integration.md §1/§5 step
# 3. Runs coordinator/circle.py's actual main() in a background thread of
# THIS process, rebinding its emit()/read_line() seams (added to circle.py
# in step 2; extracted to coordinator/seam.py 2026-08-16, phase 1 — the
# rebinding surface is seam.emit/seam.read_line now, which circle.py's
# own thin wrappers late-bind through) so output lands on a queue instead
# of real stdout, and input blocks on a queue instead of real stdin. Same queue-and-thread shape as
# AgentSimulator on purpose -- ui_main_loop() drains either one the same way,
# just demultiplexed by channel here since CircleEngine's items carry one.
# --------------------------------------------------------------------------


def _reset_process_accumulators() -> None:
    """Zero the two module singletons that tally ACROSS a circle, so the next
    circle in this process reports only its own.

    `llm_client.METER` prices the close's usage report; `phase_clock.PHASES`
    aggregates spans by name and holds the close stopwatch. Both were written
    when a process was one circle, and both say so in their own docstrings.

    Imported HERE rather than at module scope, and every failure swallowed:
    `llm_client` pulls in `anthropic`, and `test_circling.py` asserts that
    module never enters its process. That suite never calls `start()`, so this
    is not reached there — but a reset is housekeeping, and housekeeping must
    not be the thing that stops a circle from opening."""
    for mod, attr in (("llm_client", "METER"), ("phase_clock", "PHASES")):
        try:
            import importlib
            getattr(importlib.import_module(mod), attr).reset()
        except Exception:                                     # noqa: BLE001
            pass          # a missing or fake module is not a reason to refuse


class CircleEngine:
    """`out_queue` carries `(channel, text)` pairs — `channel` is exactly
    what `circle.py`'s own `emit()` calls were classified as by step 2/5
    (currently `"command"` almost everywhere except the two known
    transcript-echo sites fixed to `"circle"` in this step; the full
    audit is step 5's job, not redone here). `ui_main_loop()` demuxes on
    that value; nothing in this class decides CIRCLE vs COMMAND itself
    — `circle.py`'s own channel argument is the single source of truth,
    by design, so there is exactly one place that classification can
    drift from the rubric, and it is auditable by reading `circle.py`.

    NOT wired into `ui_main_loop()`'s default path — opt-in via `--circle`
    on `circling.py`'s own CLI (main(), below). Replacing
    `AgentSimulator` as the unconditional default would silently change
    what `python ui/circling.py` does for anyone running the existing,
    already-self-tested demo; that is a bigger, separate decision than
    this step, so both remain available and the demo stays the default.

    SAFETY, RULED 2026-08-13 (Q3): `--dry-run` (no network, no API key,
    every part passes) is still the DEFAULT — `start()`'s new `live`
    parameter is the one sanctioned way to ask for a real circle, never
    smuggled through `extra_argv` (`--live`/`--dry-run` are stripped
    from it unconditionally, same as before). Every existing caller that
    doesn't pass `live=True` — every test in this repo, the `--circle`
    demo without `--live` — keeps today's forced-sandbox behavior
    byte-for-byte. `self.live` records which mode a running/finished
    engine was actually started in, so `ui_main_loop()` can tell whether
    the extra exit-safety below applies.

    The background thread is `daemon=True` — deliberately, so a hung
    engine can never wedge process exit forever — which means the
    moment this process actually exits, that thread is killed with NO
    `finally` guarantee, wherever it happens to be. Harmless in
    `--dry-run` (nothing real is being written); a genuine risk once
    `live=True` if it happens mid-`/close`. `ui_main_loop()`'s own `finally`
    block is where this is actually guarded — see its comment there —
    not this class, since only the caller knows whether a QUIT is
    genuinely in flight.
    """

    def __init__(self, out_queue: "queue.Queue[tuple[str, str]]"):
        self.out_queue = out_queue
        self.circle_in: "queue.Queue[str]" = queue.Queue()
        self.exit_code: int | None = None
        self.crashed: Exception | None = None
        self.live = False
        self.finished = threading.Event()
        self._thread: threading.Thread | None = None
        self._orig_emit = None
        self._orig_read_line = None
        # True only while the background thread is actually blocked inside
        # `_read_line` below. Surfaced in the render layer (`_circle_prompt`)
        # because `submit_circle` queues unconditionally, with no rejection
        # and no bound -- a line typed and submitted while this is False
        # doesn't error, it just sits on `circle_in` until whatever
        # `read_line()` the engine NEXT reaches, which need not be the
        # question the user thinks they're answering. Suppressing
        # circle.py's own "<CONSOLE_NAME>> " echo (below) removed the one thing
        # that used to make "the engine is listening now" visible at all.
        #
        # ON ITS OWN IT IS STALE IMMEDIATELY AFTER A SUBMIT, which is what
        # `line_taken` below now answers -- see that comment.
        self.waiting_for_input = False
        self.pending_prompt = ""
        # THE CIRCLE CHANNEL'S CONSUMPTION HANDSHAKE, B57(1), 2026-08-19.
        # Until this existed, `submit_circle()` was a bare queue put and
        # NOTHING announced "your line was consumed", so every driver of this
        # engine re-solved the same race privately: `waiting_for_input` can
        # still read True the instant after a submit, because this thread has
        # not yet woken from `circle_in.get()`. Polling it alone returns at
        # once and that step's whole output lands in the NEXT step's drain --
        # output attributed to the wrong step, silently, with everything
        # still passing.
        #
        # CLEARED on submit, SET when a CIRCLE-channel read returns. Channel-scoped
        # deliberately: a circle line can sit queued while this thread
        # completes a COMMAND-channel read, and an unscoped set in the shared
        # `finally` would fire there and mean nothing.
        #
        # SET at rest, not cleared, so the readers that drive this engine by
        # poking `waiting_for_input` directly -- ui/tests/test_circling_selftest.py,
        # ui/tests/test_circling.py -- do not inherit a permanently-cleared event
        # they never knew to wait on.
        #
        # IT IS HALF THE ANSWER, AND THE OTHER HALF CANNOT LIVE HERE. "The
        # engine is parked again with its output drained" needs the out_queue
        # to be quiet, and the out_queue is drained by the CALLER. An engine
        # that waited on it would either steal the caller's items or lie
        # about what it had waited for. So: this event says the line was
        # TAKEN, and quiescence stays the caller's to observe.
        self.line_taken = threading.Event()
        self.line_taken.set()
        # WHICH pane's queue the pending read is draining (R221,
        # 2026-08-17). Only meaningful while `waiting_for_input` is True;
        # its resting value is "circle" rather than None so that the
        # legacy readers which set `waiting_for_input = True` on its own —
        # ui/tests/test_circling_selftest.py, ui/tests/test_circling.py,
        # ui/tests/test_circle_engine.py — keep describing a circle-channel read,
        # which is what they were written against.
        self.waiting_for_channel = "circle"
        # True only for circle.py's OWN speaking prompt, the one turn
        # circling draws its own prompt for. Governs two things: the echo
        # suppression in _read_line (as the CONSOLE_NAME comparison always
        # has), and whether a bare Enter posts or merely catches up — see
        # AppState._answering.
        self.speaking_turn = False
        # HAS THE Self> LOOP BEEN REACHED — 2026-08-21, the lab's second day
        # of findings. Set the first time _read_line sees the speaking turn,
        # never cleared: from then on every circle-channel read this engine
        # makes IS the Self> prompt (the working-set and topic questions
        # come before it, the close and abort confirmations are command
        # channel), so a cmd> line forwarded into circle_in lands in the one
        # reader that DISPATCHES commands. Before it, the same forward
        # landed in working_set_ask()'s read and was consumed as the
        # working set — "not in the graph: /issue-list", re-asked, once per
        # command typed. `_running()` could not tell the two apart: it is
        # True from start() on. See `_phase()`.
        self.loop_reached = False
        # THE CLOSE'S OWN STATE, 2026-08-21 (the lab circle 2026-08-21_1139):
        # what circle.py's /close branch reports over the seam's "state"
        # channel — "" (nothing), "close-confirm-pending" (the unruled
        # proposals are showing and a SECOND /close is awaited),
        # "closing" (the close is proceeding: short_terms, the close
        # report, the commit, dreaming). Read by submit_command (a cmd>
        # line while closing is refused; `/close` at cmd> is FORWARDED
        # while the confirmation is pending — the one exception to the
        # circle-verb refusal there) and by _command_prompt (the row reads
        # a notice while closing). Cleared when main() returns.
        self.close_state = ""
        # Fed by the COMMAND pane, drained by a command-channel read_line.
        # Separate from circle_in because the two panes are disjoint by
        # construction, which is the whole premise this harness tested.
        self.command_in: "queue.Queue[str]" = queue.Queue()
        # Imported HERE, not in start() — help_text() (and, coming next,
        # issue inspection/edit verbs) only need the MODULE, not a running
        # circle, so they must work before start() is ever called.
        # emit()/read_line() are rebound only in start(), right before the
        # background thread runs circle.py's own main() — that's the only
        # part that actually needs a live circle underneath it.
        sys.path.insert(0, str(COORD_DIR))
        sys.path.insert(0, str(COORD_DIR.parent / "memory"))  # issue-graph code (R203)
        import circle as C
        import seam as S       # the rebinding surface (phase 1, 2026-08-16)
        import command_surface as CS   # PANE_OF + dev_mode (phase 2
        self._C = C                    # stage 0, 2026-08-16) — dev_mode
        self._S = S                    # is r/w, always via this handle
        self._CS = CS

    def _emit(self, channel: str, text: str = "", **kwargs) -> None:
        # `end=`/`flush=` (circle.py's one such call, the API-check line)
        # have no meaning for a line-based pane's scrollback and are
        # dropped here — a CircleEngine-specific limitation, NOT a change
        # to `emit`'s default (standalone) behavior, which step 2 already
        # proved forwards them to real `print` unchanged.
        #
        # "state" IS A UI SIGNAL, NOT CONSOLE TEXT (2026-08-21): the
        # attribute is set HERE, on the engine thread, so submit_command and
        # the prompt renderers see it at once; the item ALSO rides the queue
        # so main_loop handles it in order with the output around it (the
        # focus handover on "closing" belongs after the lines the close
        # printed before it, not a tick earlier). main_loop never appends
        # a "state" item to a pane — see its drain, beside "prefill".
        # SOMETHING REACHED A READER — the stamp the progress beat's "still
        # talking is not waiting" guard reads. This method REPLACES seam.emit
        # rather than wrapping it, so the stamp seam.emit sets in its own body
        # is never set here; without this call quiet_since() grows forever and
        # the beat marks every three seconds all circle long, however much the
        # program is saying. Before the "state" early-out below on purpose: a
        # UI signal is still the coordinator having spoken.
        self._S.system_output_mark()
        if channel == "state":
            self.close_state = text
        self.out_queue.put((channel, text))

    def _read_line(self, prompt: str = "", channel: str = "command",
                   prefill: str = "") -> str:
        # The prompt itself is content the circle pane is waiting on —
        # route it exactly like `emit("circle", prompt)` would, so it's
        # visible before the answer arrives. `circle.py` never emits
        # Self's own typed statement back (nothing in main() calls emit()
        # after appending Self's line to the transcript — verified while
        # building step 2's transformation: the original single-terminal
        # design relied on the terminal's own input echo for that,
        # nothing printed it deliberately) — so the LOCAL echo in
        # `AppState._submit` is what makes Self's line visible here, not
        # this method.
        #
        # ONE EXCEPTION, RULED 2026-08-13 (only ever one prompt in the
        # circle pane): circle.py's own speaking prompt, `f"\n{CONSOLE_NAME}>
        # "` (e.g. "\n<configured IFS_USER_NAME>> " — a console-only
        # value, R132, never a literal name in this codebase), is written
        # for a real terminal where it sits on the same line the typed
        # answer's echo appears on. `circling` already draws its OWN
        # dedicated prompt for exactly that turn — the CIRCLE pane's
        # fixed input row, rendered by `_circle_prompt()`, which reads
        # this SAME `CONSOLE_NAME` rather than a separate literal — so
        # echoing circle.py's copy into the pane BODY as well just
        # duplicates it, once per turn, for no informational gain.
        # Reported live: a bare duplicate prompt row landing right above
        # the real input row on every turn. Every OTHER read_line call
        # (the working-set question, the topic question, a yes/no
        # confirmation) carries real content the user needs to read and
        # is still echoed exactly as before.
        # `channel` decides the channel, and it comes from circle.py's own
        # call site — RULED 2026-08-17 (R221), the same single-source-of-
        # truth rule this class already follows for emit(). Nothing here
        # classifies; `speaking_turn` below is a RENDER question ("does
        # circling draw its own prompt for this read"), not a channel one.
        self.speaking_turn = (channel == "circle"
                              and prompt == f"\n{self._C.CONSOLE_NAME}> ")
        if self.speaking_turn:
            self.loop_reached = True         # see __init__ — never cleared
        # PREFILL BEFORE THE PROMPT, always: anything that waits for the
        # QUESTION must already have seen the seed, or it stops one item
        # short and the line comes up empty. Its own channel — it is not
        # content and must never be appended to a pane.
        if prefill:
            self.out_queue.put(("prefill", prefill))
        if channel == "circle":
            # A CIRCLE-CHANNEL QUESTION IS NOT ECHOED INTO SCROLLBACK EITHER —
            # 2026-08-21, the lab circle 2026-08-21_1139, the operator: *"The output
            # line "CIRCLE issues (blank = all, 'none', '?'):" is redundant
            # to the correctly presented prompt -- keep only the prompt."*
            # The question owns the input row (`pending_prompt`, read by
            # _circle_prompt since finding 2); the ANSWER is what the pane
            # echoes — AppState._submit's "[You]: …", a blank one shown as
            # the legend the question itself gave ("(blank = all)") — so the
            # record reads answer-after-answer with no duplicated question.
            # An invalid answer's diagnostic still lands in the command pane
            # and the question simply re-takes the row. The speaking turn
            # was never echoed (RULED 2026-08-13, above); the two opening
            # questions now follow it. The standalone terminal is untouched:
            # seam's own read_line prints the prompt as input() always has.
            q = self.circle_in               # fed by submit_circle()
        else:
            # A COMMAND-CHANNEL QUESTION IS NOT ECHOED INTO SCROLLBACK —
            # 2026-08-21, the lab's finding 1, the operator: *"Overload the prompt
            # INSTEAD ... restore after a valid reply, write diagnostic and
            # repeat upon invalid reply."* Until then "[BP-0039] a)pprove,
            # d)eny, s)kip ?" landed in the command pane's scrollback while
            # the row he typed at still said "cmd> ", and nothing tied the
            # two together. The question rides the input row now
            # (`pending_prompt`, read by _command_prompt); what the question
            # is ABOUT — the proposal header and detail vetting emits above
            # it — is already in scrollback, and vetting's own re-ask
            # diagnostic is the "write diagnostic and repeat".
            q = self.command_in              # fed by submit_command()
        # Channel BEFORE the flag: a reader that sees waiting_for_input
        # True must never see a stale channel beside it.
        self.waiting_for_channel = channel
        # PREFILL FIRST, then the prompt: the render loop drains in order,
        # so the line is already seeded by the time the question appears.
        # Its own channel — it is not content and must never be appended to
        # a pane. main_loop applies it to the circle pane's input buffer.
        # THE QUESTION ITSELF, kept for the input row — finding 2,
        # 2026-08-20. The prompt lands in scrollback like any other line
        # and then scrolls; the ANSWER is typed at a fixed row at the
        # bottom that said only the console name. Two opening questions were
        # therefore asked in one place and answered in another, and on
        # 2026-08-20 both of them silently swallowed a /status. Stripped
        # of the spacer newline circle.py bakes in for a plain terminal.
        # BOTH CHANNELS since 2026-08-21: a command-channel question owns the
        # cmd> row the same way (finding 1, above); _circle_prompt and
        # _command_prompt each read it under their own channel test.
        self.pending_prompt = prompt.strip()
        self.waiting_for_input = True
        try:
            return q.get()
        finally:
            self.waiting_for_input = False
            self.speaking_turn = False
            self.pending_prompt = ""
            self.waiting_for_channel = "circle"
            # AFTER the flag, never before: a waiter released by this event
            # must be guaranteed the stale-True window has already closed,
            # which is the entire point of the handshake. Circle channel only —
            # see `line_taken`'s comment in __init__.
            if channel == "circle":
                self.line_taken.set()

    def submit_circle(self, text: str) -> None:
        """The ONE way a circle-channel line reaches the engine. Every internal
        forward in `submit_command()` goes through here too, rather than
        putting on `circle_in` directly, so the handshake covers every feed
        site by construction instead of by four people remembering."""
        # Cleared BEFORE the put: a waiter that called wait() between the put
        # and the clear would see the previous line's set and return at once.
        self.line_taken.clear()
        self.circle_in.put(text)

    # The question a circle-channel read_line is blocked on, "" when none is.
    # Read by _circle_prompt(); see _read_line for why it exists.
    pending_prompt: str = ""

    def _running(self) -> bool:
        """True only while the background `main()` thread genuinely
        exists and hasn't finished — before `start()`, `self._thread` is
        still None; after `main()` returns (close, abort, or a crash),
        `self.finished` is set. Used to decide whether a command-pane
        verb should forward into circle_in (something is actually
        draining it) or act directly (nothing is, so forwarding would
        silently do nothing).

        NOT SUFFICIENT ON ITS OWN for the forwarding decision since
        2026-08-21 — see `_phase()`: running is true from start() on, and
        for the whole OPEN (API check, vetting, the working-set and topic
        questions, pre-warm) nothing that dispatches a command is
        draining circle_in yet."""
        return self._thread is not None and not self.finished.is_set()

    def _phase(self) -> str:
        """WHERE THE ENGINE IS, for the command pane's routing — the one
        question submit_command() asks before anything else. 2026-08-21,
        from the lab's second day of findings.

        THE DEFECT THIS REPLACES. submit_command() forwarded a command-pane
        verb into circle_in whenever _running() was True. The ONLY reader
        that DISPATCHES commands is circle.py's Self> loop; every other
        circle-channel read (the working set, the topic) is a QUESTION, and a
        command is never its answer. So on 2026-08-21 every line the operator
        typed at cmd> during the open — /issue-list, status, dev, /help
        object_classes — was consumed by working_set_ask() as a working
        set, refused ("not in the graph: /issue-list"), and the question
        was re-asked, its prompt re-echoed into the circle pane once per
        command. Fourteen of the day's findings were this one defect.

            answer      a COMMAND-channel read is pending: the line IS its
                        answer, forwarded verbatim (R221, unchanged)
            loop        the Self> loop has been reached: forward into
                        circle_in — parked at Self> or busy mid-round,
                        either way the next circle-channel read dispatches
            opening-q   running, loop NOT reached, parked on a circle-channel
                        NON-speaking read — the working set or the topic:
                        the no-circle verbs may RUN (help, the listings,
                        a property read), anything else is refused and
                        told what the circle is asking and where
            opening     running, loop NOT reached, BUSY (the API check,
                        the pre-warm): refuse, and DISPATCH NOTHING —
                        _dispatch_no_circle() rebinds seam.read_line to
                        the no-block stub for the call, and an engine
                        thread that wakes inside that window would be
                        handed the stub for a real question
            idle        not running: the always-available path, unchanged
        """
        if self.waiting_for_input and self.waiting_for_channel == "command":
            return "answer"
        if not self._running():
            return "idle"
        if self.loop_reached:
            return "loop"
        if (self.waiting_for_input and self.waiting_for_channel == "circle"
                and not self.speaking_turn):
            return "opening-q"
        return "opening"

    def _opening_refusal(self, what: str) -> str:
        """The one sentence every refused-while-opening path prints — it
        names the question the circle is actually waiting on and the pane
        it is waiting in, which is the piece the operator had no way to see on
        2026-08-21."""
        asking = (f" — it is asking '{self.pending_prompt}' in the circle pane"
                  if self.pending_prompt else "")
        return (f"  the circle is still opening{asking}; {what} needs the "
                f"open circle")

    # The verbs this PANE owns, as opposed to the ones it forwards into
    # circle.py. They are real, they are typed here, and until 2026-08-20
    # no help output named any of them — /help renders circle.py's own
    # COMMANDS table and a pane-local verb cannot be a row in it.
    # status's gloss is the operator's words, verbatim (R347, 2026-08-25)
    # — the session section that used to describe it a second time, above
    # this table, left the reply the same day, so this row is the reply's
    # ONE description of it.
    # abort LEFT THIS TABLE 2026-08-31 (R414): it ends the
    # CIRCLE, so it is a circle-pane verb beside /close now — PANE_OF says
    # so, and the merged surface below refuses it here like /close.
    LOCAL_VERBS = (
        ("quit", "close this window. A circle mid-write finishes first; one "
                 "that is waiting for you to type is left where it is and "
                 "this exits at once"),
        ("resume", "pick up a circle whose close was interrupted; bare "
                   "'resume' takes the one just reported"),
        ("status", "parts, every prompt block's size IN TOKENS as the "
                   "model service counts them, the dialog turn counters, "
                   "and the running cost."),
        # "help" itself left this listing — the operator, 2026-08-25
        # (R347): "leave out the final line of cmd> help".
        # The verb still answers; it is just not a row in its own reply.
    )

    def local_verb_text(self) -> str:
        # ALIGNED LIKE help_system.command_help_rows_render() — the operator, 2026-08-25:
        # *"pad the left column to align the hyphens and line breaks (for
        # all helps)"*. Rendered locally (this dispatcher deliberately
        # imports no help_system — see _junk_help), with the same NBSP
        # trick: padding the wrap cannot break inside, continuation at the
        # description column.
        import textwrap
        pad = max(len(v) for v, _ in self.LOCAL_VERBS)
        rows = []
        for v, d in self.LOCAL_VERBS:
            spec = v + "\xa0" * (pad - len(v))
            body = f"{spec}  —  {' '.join(d.split())}"
            rows.append("\n".join(textwrap.wrap(
                body, width=80, initial_indent="  ",
                subsequent_indent=" " * (2 + pad + 5),
                break_long_words=False,
                break_on_hyphens=False)).replace("\xa0", " "))
        return "\n".join(["", "  THIS WINDOW'S OWN VERBS (not the circle's)"]
                         + rows) + "\n"

    def _junk_help(self, line: str) -> str:
        """JUNK -> help — R285, 2026-08-21, the
        operator: *"COMMAND_TEXT ::= COMMAND | JUNK. JUNK is anything that
        does not parse as a valid COMMAND; input JUNK -> help."* One line
        naming what was typed, then exactly what bare `help` prints: the
        the error and a POINTER to help — two lines, never the listing.
        A typo, speech in the wrong pane, a dev-table verb with dev off —
        all JUNK, all answered the same way, none naming "dev mode"
        (R199).

        IT PRINTED THE WHOLE LISTING UNTIL 2026-08-24, under R285's
        *"input JUNK -> help"*, and the operator measured what that does
        in a pane: the listing is longer than the pane, so the one line
        naming the mistake scrolled out of sight. *"Do not invoke help...
        issue the error, then on the next line 'See help'."* An answer
        that hides its own diagnosis is worse than no answer.

        THE SAME TWO LINES help_system.junk_help() GIVES circle.py's loop,
        composed here rather than called: the command pane's stub harness
        (ui/tests/test_circling.py) carries a `_C` with help_text alone and
        no help_system. `local_verb_text()` is no longer appended here —
        it still backs the pane's own `help` verb, which is where a verb
        list belongs."""
        return f"  not a command: {line.strip()}\n  See help"

    def _open_sandbox_circles(self) -> list[dict]:
        """Open circles under THIS engine's own root — work/
        sandbox/circles/ normally, circles/ once `self.live` is True
        (RULED 2026-08-13, Q3; name kept for now, widened rather than
        renamed, since every existing caller/test already says
        `_open_sandbox_circles`). Reuses circle_state.circle_open_read()
        directly — the same source circle.py's own "N circle(s) may
        still be OPEN" preflight warning is built from, so a bare
        'resume' finds exactly what that warning just reported, not a
        separate guess. Still scoped to ONE root: a live engine should
        never resume into a sandbox transcript, or vice versa — the
        --live/--dry-run mismatch would corrupt WriteGuard's own
        assumptions about where it's allowed to write."""
        import circle_state
        root = circle_state.LIVE if self.live else circle_state.SANDBOX
        return [c for c in circle_state.circle_open_read()
                if c["path"].parent.resolve() == root.resolve()]

    def submit_command(self, text: str) -> str | None:
        """The command-pane verbs hand-wired so far — 'quit', 'help',
        'status', 'resume', 'dev' ('abort' until 2026-08-31, when it moved
        to the circle pane beside /close: R414) — ahead of
        the full merged verb surface (stages 5/6,
        docs/dual_pane_integration.md §3, still deferred). Anything else is
        JUNK and is answered with the help
        listing for the current dev state (R285, 2026-08-21 — it said
        'not understood, see help' until then), decided here now
        instead of unconditionally in AppState._submit.

        Returns "quit" or "help" as signals for AppState._submit to act
        on (mirrors handle_key's own "quit"/"focus" effect convention) —
        this class owns circle-session state, not AppState or the render
        loop, so it has nothing to set state.running or trigger a pane
        resize on directly. Every response TEXT is queued onto out_queue
        with channel "command", same as any real circle.py output, so it
        reaches the pane through the one normal drain path in ui_main_loop().
        """
        # A COMMAND-CHANNEL read_line IS BLOCKED RIGHT NOW: this line is its
        # ANSWER, not a command. Forward it VERBATIM, before any
        # normalization — the slash-strip, head lowercasing and
        # `head + rest_of_line` reconstruction below are correct for a
        # command and wrong for an answer ("/StAtEmEnTs" must not become
        # "/issue-evidence-list" when vetting asked for free text). RULED
        # 2026-08-17 (R221): forward everything, local verbs included —
        # a pending question owns the pane. Vetting re-asks on anything
        # it does not recognize, so nothing is lost, and interception is
        # exactly how 'abort' used to be swallowed.
        # ONE READ OF THE PHASE, used by every branch below — see _phase().
        # Read once so a flag the engine thread flips mid-dispatch cannot
        # route the head one way and its arguments another.
        phase = self._phase()
        if phase == "answer":
            # FIRST, even while closing: the close's own vetting ("at close"
            # a)pprove/d)eny/s)kip) is a command-channel read, and a line typed
            # then is its answer — the one thing a closing circle still
            # asks of the operator.
            self.command_in.put(text)
            return None
        stripped = text.strip()
        # THE CLOSE IS PROCEEDING — 2026-08-21, the lab circle
        # 2026-08-21_1139, the operator: *"Disable cmd> entries while closing,
        # replace the prompt with a notice throughout."* Nothing typed here
        # is dispatched or forwarded: short_terms, the close report, the
        # commit and dreaming are running and nothing is reading a command.
        # 'quit' stays honoured so a hung close can always be escaped
        # (Ctrl-C too — handle_key's own path). The cmd> row itself reads the
        # notice (_command_prompt), so this line is the answer to a typed
        # line, not the only sign.
        if self.close_state == "closing":
            if stripped.lstrip("/").lower() == "quit":
                return "quit"
            self.out_queue.put(("command",
                "  the circle is closing — input is disabled until it "
                "finishes ('quit' still closes this window)"))
            return None
        # THE SECOND /close MAY COME FROM HERE — same finding: the first
        # /close showed the unruled proposals and said "Type /close again to
        # proceed" while the window had ALREADY moved the operator to cmd>,
        # where /close is circle-pane speech and was refused. While the
        # circle is waiting for exactly that confirmation, `close` or
        # `/close` typed here is forwarded into the room — the one
        # exception to the circle-verb refusal below, and it says so.
        if (self.close_state == "close-confirm-pending"
                and stripped.lstrip("/").lower() == "close"):
            self.submit_circle("/close")
            self.out_queue.put(("command",
                "  /close forwarded — the circle asked for it again; the "
                "close proceeds"))
            return None
        # 2026-08-16: "/" is a COMMAND indication ONLY in the circle pane,
        # to distinguish a command from dialog (docs/HELP_DESIGN.md §0) —
        # every line typed HERE already is a command, so a leading slash is
        # optional and normalized away once, before either dispatch path
        # below. Previously only this bare-word block tolerated a bare verb;
        # the merged verb surface further down unconditionally PREPENDED
        # "/", so a user typing "/help" got "//help", which matches no
        # PANE_OF key and fell through to "not understood, see 'help'".
        if stripped.startswith("/"):
            stripped = stripped[1:].lstrip()
        word = stripped.lower()
        if word == "quit":
            return "quit"
        # NAMED IN HELP SINCE 2026-08-20. `quit` has worked from the day
        # this dispatcher was written and appeared in NO help output: it is
        # a pane-local verb, and /help renders circle.py's COMMANDS table,
        # which cannot contain one. the operator ended their first live lab session
        # with Ctrl-C because nothing on screen said this existed.
        # NO 'abort' BRANCH SINCE 2026-08-31 (R414). It sat
        # here from the day this dispatcher was written — forwarding
        # "/abort" onto the circle channel, with idle/opening/dead-engine
        # guards accreted on 2026-08-20 and 2026-08-21 — and the operator
        # then separated the two lifecycles: quit ends the WINDOW and is
        # this pane's; /abort ends the CIRCLE and is the room's, beside
        # /close. PANE_OF classes it "circle" now, so the merged surface
        # below refuses it here exactly as it refuses /close, and the
        # circle pane's own guard lets it through to circle.py's loop,
        # whose R173 two-step confirmation is unchanged.
        if word == "help":
            # Pure function of the (hot-reloaded) TOML tables — no circle
            # needs to have started. Returns "help" (not None) so
            # AppState._submit can trigger the pane resize below.
            # THE PANE'S OWN VERBS RIDE ALONG, since 2026-08-20.
            # help_text() renders circle.py's COMMANDS table, and a verb
            # this dispatcher handles LOCALLY can never be a row in it —
            # so `quit` worked from the day it was written and was named
            # by nothing on screen. the operator ended their first live lab session
            # with Ctrl-C for want of this line.
            self.out_queue.put(("command",
                                self._C.command_help_render("") + self.local_verb_text()))
            return "help"
        if word == "status":
            # /status is a circle-pane command (dispatched inside
            # circle.py's own Self> loop) whose OUTPUT lands on the
            # "command" channel — it was never reachable from THIS pane
            # until now. Same forwarding as 'abort': only lands if the
            # engine is actually parked at a read_line when this runs.
            #
            # THE SAME GUARD SET AS EVERY OTHER cmd> PATH, 2026-08-21. This
            # branch forwarded UNCONDITIONALLY — no _running() check, no
            # phase — so on 2026-08-21 `status` typed during the open
            # became the working set ("not in the graph: /status"), and
            # with no engine at all it sat on circle_in unread. /status
            # needs the sysblocks and the counters a running circle holds,
            # so before the loop and with no circle it is refused with the
            # reason, never queued.
            if phase == "loop":
                self.submit_circle("/status")
            elif phase == "idle":
                self.out_queue.put(("command",
                    "  /status needs a circle open — nothing running to "
                    "act on"))
            else:
                self.out_queue.put(("command", self._opening_refusal("/status")))
            return None
        if word == "dev":
            # RULED 2026-08-13: dev_mode is ONE module-global attribute
            # (command_surface.py since phase 2 stage 0, 2026-08-16;
            # circle.py before that), reachable and toggleable whether or
            # not a circle is running. FLIPPED DIRECTLY IN EVERY PHASE, never
            # forwarded into circle_in (R286: "it is cmd> only and always
            # hidden"): forwarded before the loop, "/dev" becomes the working
            # set. The Self> loop's own /dev is the standalone terminal's
            # (R542) and toggles the same attribute.
            # One attribute, one writer here, nothing to keep in
            # sync. Unlisted: LOCAL_VERBS does not name it (R199).
            self._CS.dev_mode = not self._CS.dev_mode
            self.out_queue.put(("command", "  dev mode: "
                                + ("on" if self._CS.dev_mode else "off")))
            return None
        if word == "resume" or word.startswith("resume "):
            # the operator: "support 'resume' in the command pane, same function
            # as --resume." First cut required the open_time as an
            # explicit argument, matching the CLI flag literally — the operator,
            # immediately after: that requirement "makes no sense" here
            # (unlike the CLI, where you already know which OT you meant
            # to type). BARE 'resume' now means "resume the circle just
            # reported": look up open sandbox circles directly (the same
            # circle_state.circle_open_read() the "N circle(s) may still be
            # OPEN" warning itself is built from) and use its open_time
            # when there's exactly one candidate. An explicit open_time
            # is still accepted and still wins outright, for the case
            # where more than one is open, or the ambiguity has to be
            # broken by hand.
            ot = stripped[len("resume"):].strip()
            if not ot:
                candidates = self._open_sandbox_circles()
                if not candidates:
                    self.out_queue.put(("command", "  no open circle to resume"))
                    return None
                if len(candidates) > 1:
                    listing = "\n".join(
                        f"     {c['ot']}  ({c['why']})" for c in candidates)
                    self.out_queue.put(("command",
                        f"  {len(candidates)} open circles — say which:\n{listing}"))
                    return None
                ot = candidates[0]["ot"]
            elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}", ot):
                self.out_queue.put(("command",
                    "  resume wants an open time like 2026-08-10_2112, or "
                    "bare 'resume' to pick up the one just reported"))
                return None
            # Whatever read_line() the current engine is blocked in — in
            # practice, the "type 'yes' to open a NEW circle" confirmation
            # this command exists to answer — receives a decline, exactly
            # like 'abort' above forwards to whatever is pending. If
            # nothing is actually blocked (the engine already finished, or
            # was never asked), this sits unread on an otherwise-empty
            # queue; harmless.
            # command_in, NOT circle_in: the read this answers is
            # circle.py:690's "type 'yes' to open a NEW circle", which is
            # COMMAND channel (it takes read_line's default). On circle_in it
            # would sit unread, the old engine would never finish, and
            # main_loop's 5s finished.wait() would fail every resume.
            self.command_in.put("no")
            self.out_queue.put(("command", f"  resuming circle_{ot} —"))
            return f"resume:{ot}"

        # --- Merged verb surface, RULED 2026-08-13
        # (docs/dual_pane_integration.md §3, Q1 retirement + Q2
        # precedence). ONE surface, availability-gated, not pane-gated:
        #
        # A circle IS running: forward the whole line into circle_in,
        # reusing circle.py's OWN COMMANDS-table dispatch wholesale —
        # not a second copy of it here. /issue-evidence-list, /tokens,
        # /practice-add, the /issue forms, all just work, with the SAME
        # dev-mode gate
        # and the SAME transcript recording where it applies (R079).
        # "circle.py functions take precedence" (Q2) means exactly this:
        # while one is running, ITS loop is the implementation, never a
        # direct call that would skip what that loop also does.
        #
        # No circle running: only the verbs circle.py's own no-transcript
        # stage-2 functions can answer (_dispatch_no_circle) are
        # reachable — "operate independently of any circle in progress"
        # (Q1). Everything else refuses with a stated reason, never
        # "not understood".
        #
        # /round, /pass and /close are deliberately excluded either way —
        # COMMANDS classifies all three pane="circle" (circling_and_
        # evolving.md §5 reserved round/pass for the circle pane alone;
        # /close joined them 2026-08-14, correcting that section's own
        # overgeneralization from a bare, unslashed "close" typo —
        # work/instrument/LOG.md's 2026-08-06 incident — into also
        # excluding the properly-slashed "/close", which the incident
        # never actually required). PANE_OF.get() below returns "circle"
        # for all three, which the branch below refuses.
        # `word` above is the WHOLE line lowercased (`stripped.lower()`),
        # not just the verb — fine for the exact-word checks above, wrong
        # here where most of these carry arguments. Split fresh: only the
        # first token is case-folded for lookup, the rest keeps its
        # original case (an OC-# id, a file path, a status value...).
        head_word, _, arg_rest = stripped.partition(" ")
        # NORMALISED, not just lower-cased, since 2026-08-20: `_` reads
        # as `-`, so `/topic_close` is a typo rather than a refusal. One
        # function, shared with circle.py and the dev-command door.
        # "/" + word, UNCONDITIONALLY, exactly as before: the caller has
        # already stripped ONE leading slash (R201), so "//help" must stay
        # "//help" and be refused. normalise_head only folds case and
        # reads `_` as `-`; letting it supply the slash would quietly turn
        # a double-slash typo into a resolved verb.
        head = self._CS.command_head_normalise("/" + head_word)
        rest_of_line = (" " + arg_rest) if arg_rest else ""
        pane = self._CS.PANE_OF.get(head)
        # A DEV-TABLE VERB WITH DEV OFF IS JUNK — 2026-08-21, the JUNK rule
        # applied to the CURRENT dev state. Until then this pane never read
        # the tables at all: with no circle, `_dispatch_no_circle` ran a dev
        # verb regardless of dev, and with one it forwarded the line for the
        # loop's gate to refuse. Decided HERE now, where the line is typed,
        # and answered with the listing that does not name the verb (R199).
        # THROUGH command_is_allowed SINCE 2026-09-09, not the DEV table
        # directly. The operator ruled every `-list` verb runnable regardless
        # of dev, and two of them (/topic-list, /issue-relationship-list) were
        # in that table — so read directly, this pane would have gone on
        # calling them junk while Self> had started running them.
        if (pane == "command"
                and not self._CS.command_is_allowed(
                    head, self._CS.dev_mode,
                    surface=self._CS.SURFACE_COMMAND)):
            self.out_queue.put(("command", self._junk_help(text)))
            return None
        if pane == "command":
            # THE PHASE DECIDES, NOT _running() — 2026-08-21, see _phase().
            # `loop` forwards as before. `idle` takes the always-available
            # path as before. The two OPENING phases are new: the circle is
            # running but nothing that dispatches a command is draining
            # circle_in yet, so a forward would be consumed as the working
            # set or the topic — which is exactly what happened, fourteen
            # times, on 2026-08-21.
            if phase == "loop":
                self.submit_circle(head + rest_of_line)
                return None
            if phase == "opening-q":
                # PARKED ON A QUESTION: the engine thread is blocked in
                # circle_in.get() and nothing but this thread can wake it,
                # so the no-circle dispatcher's rebind window is safe. The
                # verbs that need no transcript RUN — the operator typed
                # /issue-list precisely to answer the working-set
                # question in front of him; the rest are refused with the
                # question named.
                if self._dispatch_no_circle(head, rest_of_line.strip()):
                    return None
                self.out_queue.put(("command", self._opening_refusal(head)))
                return None
            if phase == "opening":
                # BUSY BEFORE THE LOOP (the API check, the pre-warm): no
                # dispatch at all. _dispatch_no_circle() rebinds
                # seam.read_line to the no-block stub for the duration of
                # the call; an engine thread that reaches a real question
                # inside that window would be handed "" for an answer.
                self.out_queue.put(("command", self._opening_refusal(head)))
                return None
            if self._dispatch_no_circle(head, rest_of_line.strip()):
                return None
            self.out_queue.put(("command",
                f"  {head} needs a circle open — nothing running to act on"))
            return None
        if pane == "circle":
            # the list is read off PANE_OF, never written here — /abort
            # joined it 2026-08-31 and a hand list would have said three
            room = ", ".join(h for h, p in self._CS.PANE_OF.items()
                             if p == "circle")
            self.out_queue.put(("command",
                f"  {head} is circle-pane speech ({room}) — "
                "not reachable from the command pane"))
            return None
        # JUNK -> help (R285, 2026-08-21). This
        # said "not understood, see 'help'" from 2026-08-10.
        self.out_queue.put(("command", self._junk_help(text)))
        return None

    def _no_block_read_line(self, prompt: str = "", channel: str = "command") -> str:
        """The `read_line` `_dispatch_no_circle` rebinds seam.read_line to.
        Answers "" immediately rather than blocking on a queue nothing is
        draining — see `_dispatch_no_circle`'s docstring for why a real
        block here would freeze the whole UI. A separate method (not a
        closure inside `_dispatch_no_circle`) specifically so it can be
        checked in isolation, decoupled from whatever the live issues/
        graph does or doesn't permit for any particular node/status —
        that's issue_status.py's own concern, tested elsewhere."""
        self.out_queue.put((channel, prompt))
        # Worded for both callers since 2026-08-21: no circle at all, and a
        # circle still parked on its opening questions (_phase "opening-q")
        # — in neither is there a Self> prompt to take a 'yes' from.
        self.out_queue.put((channel,
            "  (no interactive confirmation here — the circle is not at "
            "its Self> prompt; retype with --yes to apply directly)"))
        return ""

    def _dispatch_no_circle(self, head: str, rest_text: str) -> bool:
        """The always-available verb surface (RULED 2026-08-13, Q1) — a
        thin wrapper around circle.py's own `dispatch_dev_cmd()`, the
        SAME dispatcher its `--dev-cmd` CLI flag calls (one dispatch
        table, two doors — not a second copy of the verb list here).
        Temporarily rebinds seam.emit/seam.read_line to THIS engine. It
        runs while `not self._running()` (nothing else has them rebound
        then) and, since 2026-08-21, while the engine is PARKED on one of
        the opening questions (`_phase() == "opening-q"`): there the
        engine's own _emit/_read_line are the bound pair, this method
        captures and restores exactly those, and the engine thread is
        blocked in circle_in.get() for the whole call — only THIS thread
        can wake it, and this thread is in here. It is never called while
        the engine is BUSY before the loop: a thread reaching a real
        question inside the rebind window would be handed the no-block
        stub below for an answer. read_line is rebound to a no-op that
        emits the prompt and answers "" immediately rather than
        blocking: the one verb that could ask for interactive
        confirmation (issue ... status = <value> with no --yes) is
        called from the SAME thread that would have to answer it — a
        real block here would freeze the whole UI, not just this call.
        --yes/-y (already supported by cmd_issue_status_set, ported from
        ic.py) is how this path applies a status change instead.
        Returns False for anything dispatch_dev_cmd() doesn't recognize
        — the attest-class verbs, which genuinely need a running circle
        — so the caller can refuse with its own reason."""
        C, S = self._C, self._S
        orig_emit, orig_read_line = S.emit, S.read_line
        S.emit, S.read_line = self._emit, self._no_block_read_line
        try:
            # interactive=False, 2026-08-23: every read through this door is
            # answered "" at once by the stub above, so a verb that ASKS
            # (/part-context-update's dialog) must know nobody can answer and
            # say where it works, rather than record a row of blanks. The
            # stub's own "(no interactive confirmation ...)" line still
            # covers the yes/no reads that ignore the flag.
            return C.command_dev_dispatch(head, rest_text, interactive=False)
        finally:
            S.emit, S.read_line = orig_emit, orig_read_line

    def start(self, extra_argv: list[str] | None = None, live: bool = False) -> None:
        """`live` is the one sanctioned door to a real circle (RULED
        2026-08-13, Q3) — `--live`/`--dry-run` are stripped from
        `extra_argv` unconditionally below, so a caller cannot smuggle
        either through it; this parameter alone decides."""
        self.live = live
        C, S = self._C, self._S
        self._orig_emit, self._orig_read_line = S.emit, S.read_line
        S.emit, S.read_line = self._emit, self._read_line
        # THIS RUN HAS A COMMAND PANE — set with the seams it belongs to, and
        # restored with them in the `finally` below. help_system's room help
        # reads it to decide whether it may say "the command pane" at all;
        # standalone circle.py leaves it at its False default and is told
        # about no pane it has not got.
        self._orig_command_pane = S.COMMAND_PANE
        S.COMMAND_PANE = True
        # THE PROCESS-WIDE ACCUMULATORS, ZEROED BEFORE EVERY CIRCLE. Ruled by
        # the operator 2026-08-30 — *"support multiple circles in one app
        # context. In fact, assume the ticker will be running permanently"* —
        # until
        # that day one process was one circle and neither of these had a
        # caller. Both aggregate by key and both are reported PER CIRCLE at
        # the close, so a second circle in one window would print the first
        # one's tokens and the first one's phase times added to its own.
        # Neither would look wrong; a cumulative total reads as a large one.
        # Here rather than in the bridge because THIS is the seam that runs
        # main() more than once — the TUI path resets nothing that has
        # anything in it yet, so it is unaffected.
        _reset_process_accumulators()

        argv = ["circle.py"] + (["--live"] if live else ["--dry-run"])
        for a in (extra_argv or []):
            if a in ("--live", "--dry-run"):
                continue                     # refused/redundant — `live` above is the one door
            argv.append(a)

        def run() -> None:
            old_argv, old_cwd = sys.argv, os.getcwd()
            sys.argv = argv
            os.chdir(str(COORD_DIR.parent))  # circle.py resolves paths from ROOT
            try:
                self.exit_code = C.main()
            except SystemExit as e:
                # 2026-08-16: this used to be silent. C.main() only raises
                # SystemExit via argparse itself (bad arguments, or --help/
                # -h slipping through extra_argv) — a legitimate circle run
                # always RETURNS an int instead. So every SystemExit here
                # means the engine never actually started: argparse prints
                # its own error straight to this process's real stderr,
                # before emit() is even rebound above, so it reaches
                # neither pane — the TUI was left drawing a normal-looking
                # "waiting" session with a background thread that had
                # already exited underneath it. Surfaced into COMMAND so
                # the failure is visible somewhere a user is actually
                # looking, alongside the exact argv that failed.
                self.exit_code = e.code if isinstance(e.code, int) else 1
                self.out_queue.put(("command",
                    f"  !! circle.py exited before starting a circle "
                    f"(code {self.exit_code}), argv={argv!r} — bad CLI "
                    f"arguments most likely; see this process's own "
                    f"terminal for argparse's error text, which prints "
                    f"straight to stderr and never reaches either pane."))
            except Exception as e:           # noqa: BLE001 — report, don't hang the UI
                self.crashed = e
                self.out_queue.put(("command", f"  !! CircleEngine crashed: {e!r}"))
            finally:
                sys.argv = old_argv
                os.chdir(old_cwd)
                S.emit, S.read_line = self._orig_emit, self._orig_read_line
                S.COMMAND_PANE = self._orig_command_pane
                # The close is over however main() ended — the cmd> row
                # must not read "closing" over an engine that is gone.
                self.close_state = ""
                self.finished.set()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # No FORCEFUL cancellation hook in circle.py's main() (out of
        # scope for this step — it has none today even for the real
        # terminal). The graceful path — unblocking a thread parked in
        # `_read_line` with a real answer — is submit_command()'s
        # 'abort' verb, not this method. This exists so callers have a
        # symmetrical stop() like AgentSimulator's, and so an
        # ALREADY-finished thread can be observed as done.
        pass


# --------------------------------------------------------------------------
# Renderer. Every function takes `write`, so a test can pass
# `out.append` instead of `sys.stdout.write` and inspect the result.
# --------------------------------------------------------------------------


def _move(row: int, col: int) -> str:
    return f"\x1b[{row};{col}H"


CLR_LINE = "\x1b[2K"

# COLOR — R342 (D64 a), 2026-08-25, the operator's own sketch from
# the install circle: green prompts, red !! errors, cyan chrome (the ===
# headers, the divider, the key legend). OFF here and armed only by main()
# — on a real terminal, with NO_COLOR unset and --no-color absent — so
# every suite, the selftest and any piped run compare plain bytes exactly
# as before. Applied at WRITE time, after width slicing, so no escape code
# ever enters the layout or cursor math.
COLOR = False
# FROM ui/palette.py SINCE 2026-08-30, and STILL 4-BIT — ruled that day,
# "keep 4-bit ansi". These are the same four escape codes this line held
# before, byte for byte; what changed is that green, red and cyan now have
# the same NAMES here as the roles they mean in the Ticker's CSS and in the
# issue-graph drawing. The values stay 4-bit deliberately: a terminal's
# sixteen colours are the theme its owner chose, and emitting 24-bit would
# make this room match the palette file and stop matching them. So this is
# the one surface where the palette shares the meaning and not the number.
C_PROMPT, C_ERR = PALETTE.ui_ansi_read("GREEN"), PALETTE.ui_ansi_read("RED")
C_CHROME, C_OFF = PALETTE.ui_ansi_read("TEAL"), PALETTE.ui_ansi_read("OFF")


def _tint(code: str, s: str) -> str:
    """`s` wrapped in one color, or `s` untouched while COLOR is off."""
    return f"{code}{s}{C_OFF}" if COLOR and s else s


def _layout(state: AppState) -> dict[str, int]:
    """Row numbers, computed fresh each call from the panes' own heights —
    never stored, so there is nothing to fall out of sync."""
    circle_top = 2
    circle_input_row = circle_top + state.circle.height
    # ONE BLANK ROW between the circle input row and the divider — B67,
    # the operator 2026-08-25: *"Add and maintain a blank line here,
    # including across TAB pane reflows."* A LAYOUT row, not a drawing
    # habit: every reflow recomputes it here, and render_chrome clears it
    # on every call, so nothing can leave stale text in it.
    spacer_row = circle_input_row + 1
    divider_row = spacer_row + 1
    command_header_row = divider_row + 1
    command_top = command_header_row + 1
    command_input_row = command_top + state.command.height
    status_row = command_input_row + 2
    return dict(circle_top=circle_top, circle_input_row=circle_input_row,
                spacer_row=spacer_row, divider_row=divider_row,
                command_header_row=command_header_row,
                command_top=command_top, command_input_row=command_input_row,
                status_row=status_row)


def _scroll_tag(pane: Pane) -> str:
    """Shown even while following, if there's scrollback to reach — so the
    pane advertises that it's scrollable before anyone tries. Once
    scrolled, both counts show: how far back you are AND how much you'd
    still cross to catch back up."""
    above = pane.hidden_above()
    if not pane.is_scrolled():
        return f" ({above} above)" if above else ""
    below = pane.hidden_below()
    # "Enter", not "End", since 2026-08-25: the dedicated End now goes to the
    # end of what you are TYPING, and the numpad's is the one that catches up.
    # A bare Enter does it on both clusters and on every platform, so it is the
    # one spelling this line can carry.
    return f" (scrolled, {above} above, {below} below — Enter catches up)"


# DISPLAY NAMES, kept separate from `Pane.label` deliberately — the header
# reads "COMMANDS" (plural) while `state.command.label` is "COMMAND"
# (singular, matching `_header_text`'s callers elsewhere). Not worth
# unifying; nothing else reads `.label`.
_DISPLAY = {"circle": "CIRCLE", "command": "COMMANDS"}


def _header_text(pane: Pane, which: str) -> str:
    """No focus marker here any more — the focused pane is the tall one
    (`_pane_heights`), which says it without a word of text. `focused` was
    a parameter of this function until then; it is gone rather than
    ignored, so nothing can pass one and quietly expect a tag back."""
    return f"=== {_DISPLAY[which]}{_scroll_tag(pane)} ==="


def _pane_rows(state: AppState, which: str) -> dict[str, int]:
    L = _layout(state)
    if which == "circle":
        return dict(header=1, top=L["circle_top"], input=L["circle_input_row"])
    return dict(header=L["command_header_row"], top=L["command_top"],
                input=L["command_input_row"])


def _input_rows(prompt: str, buf: str, width: int | None) -> list[tuple[int, int]]:
    """The display rows the input line occupies — half-open (start, end)
    index ranges into `prompt + buf`, one per row. PURE.

    THE INPUT WRAPS AT A WORD BREAK, 2026-08-21 — the operator: *"the input needs
    to automatically wrap at a word break before leaving the window, it
    currently scrolls the line left when approaching the right bound."*
    Until then the row was a cursor-anchored WINDOW (tier 4 #38): text slid
    left and out of sight, and what he could no longer see he retyped —
    the lab transcript of 2026-08-21_1139 carries the duplicated tail.

    A ROW HOLDS AT MOST width-1 CHARACTERS, so the append cell after a full
    row is always addressable on screen (the same rule the old window kept
    for its one row: col may equal width, never width+1). The one exception
    is a wrap made AT a space: the space stays at the end of its row as the
    width-th cell — a cursor on it is the last column, a cursor after it is
    the next row's first. A word longer than a row is cut at the cap, as
    ui_line_wrap() cuts a body row. width=None (the selftest's no-terminal
    calls) is one row, unwrapped, exactly as before."""
    line = prompt + buf
    n = len(line)
    if width is None or width <= 1 or n < width:
        return [(0, n)]
    cap = width - 1
    rows: list[tuple[int, int]] = []
    start = 0
    while True:
        if n - start <= cap:
            rows.append((start, n))
            return rows
        seg = line[start:start + cap + 1]       # `width` characters
        sp = seg.rfind(" ")
        end = start + sp + 1 if sp >= 1 else start + cap
        rows.append((start, end))
        start = end


def _input_layout(prompt: str, buf: str, cursor: int, width: int | None,
                  max_rows: int | None = None) -> tuple[list[str], int, int]:
    """(row texts, cursor row index, 1-based cursor column) — the ONE
    computation every input-row drawer and the cursor placer share, so the
    text and the cursor can never disagree about what is on screen
    (2026-08-18 review, tier 4 #38 — the windowed single row; the same
    guarantee for the wrapped rows since 2026-08-21).

    The cursor row is the row whose range holds the cursor index, or the
    last row when the cursor sits at the append cell. `max_rows` caps what
    is SHOWN: a paste longer than the pane can hold shows the run of rows
    that contains the cursor row — anchored so the cursor is always on
    screen — and the rest wait off-screen, which is the old window's
    behaviour one row-size up."""
    line = prompt + buf
    ranges = _input_rows(prompt, buf, width)
    cpos = len(prompt) + cursor
    cur = len(ranges) - 1
    for i, (_s, e) in enumerate(ranges):
        if cpos < e:
            cur = i
            break
    s, _e = ranges[cur]
    col = cpos - s + 1
    rows_text = [line[a:b] for a, b in ranges]
    if max_rows is not None and max_rows >= 1 and len(rows_text) > max_rows:
        first = min(max(0, cur - max_rows + 1), len(rows_text) - max_rows)
        rows_text = rows_text[first:first + max_rows]
        cur -= first
    return rows_text, cur, col


def _input_geometry(state: AppState, which: str, prompt: str,
                    width: int | None) -> dict:
    """Where one pane's input rows go and what they hold (2026-08-21). The
    input takes its rows FROM THE BODY, bottom up: k rows of input leave
    `height - (k - 1)` body rows above them, never fewer than none. Keys:
    rows_text, cur_row, cur_col, first_row (screen row of the first input
    row), body_rows, k."""
    pane = state.circle if which == "circle" else state.command
    rows = _pane_rows(state, which)
    rows_text, cur_row, cur_col = _input_layout(
        prompt, pane.input_buf, pane.input_cursor, width,
        max_rows=pane.height + 1)
    k = len(rows_text)
    return dict(rows_text=rows_text, cur_row=cur_row, cur_col=cur_col,
                first_row=rows["input"] - (k - 1),
                body_rows=max(0, pane.height - (k - 1)), k=k)


def ui_pane_header_render(state: AppState, which: str, width: int, write) -> None:
    """Just this pane's own header line. Always safe to call — it's a
    single row that never overlaps the body rows below it, so calling
    this on every relevant event (including ones that don't touch this
    pane's content, like a new arrival moving only the "N below" count)
    can't disturb a selection anyone is mid-dragging in the body."""
    pane = state.circle if which == "circle" else state.command
    row = _pane_rows(state, which)["header"]
    write(_move(row, 1) + CLR_LINE
          + _tint(C_CHROME, _header_text(pane, which)[:width]))


def _waiting_tag(backend) -> str:
    """WHAT the row is waiting ON — R343 (D62 a),
    2026-08-25; the operator, from the install circle: *"Waiting for what
    is unclear; extend a proper 'waiting' prompt to include on what."*

    A pending CIRCLE-channel question never reaches this: the question itself
    owns the row (finding 2, 2026-08-20). These are the states that used
    to say a bare "(waiting)" — a question pending in the OTHER pane, the
    round running, or the circle still opening. `loop_reached` (set at the
    first speaking turn, never cleared) is what separates the last two: it
    is the engine's own "the Self> loop exists now" fact, so before it the
    machinery is opening — the API check, the blocks, the pre-warm — and
    after it whatever runs between reads is the parts' own round (or the
    close, which is also the parts writing). A stub backend without the
    flags reads as opening, which is the truthful default for something
    that never reached a loop."""
    if (getattr(backend, "waiting_for_input", False)
            and getattr(backend, "waiting_for_channel", "") == "command"):
        return " (waiting — a question below in COMMANDS)"
    if getattr(backend, "loop_reached", False):
        return " (waiting — the parts are replying)"
    return " (waiting — opening the circle)"


def _circle_prompt(state: AppState) -> str:
    """RULED 2026-08-13: there is only ever ONE prompt in the circle pane,
    and it reads "N> ", N being circle.py's own `CONSOLE_NAME` (the
    user's configured console name if IFS_USER_NAME is set, else "Self" —
    identity.py's DEFAULT_NAME) — the exact same value circle.py's own
    terminal loop prompts with. Before this, `state.circle.prompt` was a
    SEPARATE hardcoded "Self> " literal — a second, independent naming
    source that silently disagreed with circle.py's own prompt the moment
    IFS_USER_NAME was set to anything else. CONSOLE_NAME is console-only,
    same scope circle.py itself confines it to: never written to a
    transcript, never sent to a part (R132) — reusing it here for a
    render-only prompt carries nothing new across that boundary.

    Falls back to `state.circle.prompt` ("Self> ") only when no real
    backend is attached — the demo/self-test path, which this file's own
    docstring says explicitly is "not circle.py... not connected to any
    part, any LLM, any real transcript" and so has no real CONSOLE_NAME to
    read at all.

    The "(waiting)" suffix — unless a real `CircleEngine` is attached and
    NOT currently blocked in `read_line()`, see
    `CircleEngine.waiting_for_input`'s docstring for why that distinction
    matters. `getattr(..., True)` defaults to "ready" for anything that
    isn't a `CircleEngine`.

    IT READ "(wait)" UNTIL 2026-08-20. the operator asked for "(waiting)" by name,
    and the window it covers was already exactly the one he described: from
    his Enter until circle.py's loop is back at its own read_line, i.e.
    until every part has replied or passed. Typing during it was already
    allowed and still is — `submit_circle` queues unconditionally.

    "(ended)" IS NEW, and it is the half that was missing. After the
    background thread finishes — a close, an abort, or a CRASH — this kept
    rendering whatever wait-state it was last in, forever, looking exactly
    like a live prompt. That is what a crashed session looked like on
    2026-08-20: a healthy-looking prompt in front of an engine that had
    been gone for minutes."""
    backend = state.backend
    name = getattr(getattr(backend, "_C", None), "CONSOLE_NAME", None)
    base = f"{name}> " if name else state.circle.prompt
    # "(waiting)" THE INSTANT A LINE IS SUBMITTED — 2026-08-21, the operator: *"Add
    # '(waiting)' to the circling pane prompt as soon as the user has input."*
    # The flags this function reads are the ENGINE THREAD's, and it has not
    # woken from circle_in.get() yet when the keystroke's redraw runs — so
    # the row kept saying the console name for a tick after Enter, then flipped.
    # `line_taken` is cleared by submit_circle() on THIS thread, before the
    # put, and set only when the circle-channel read that consumed the line
    # returns (B57(1)); between the two the line is in flight and the row
    # says so. It rests SET, so a backend never submitted through is
    # unaffected, and nothing below changes for it.
    # "(ended)" IS TESTED FIRST — 2026-08-25. It used to sit below the three
    # branches under it, and every one of them describes a read that is
    # going to happen: a line in flight, a pending question, a wait. Once
    # the thread is gone none of that can be true, and the first branch was
    # reachable in exactly the case the operator hit — a line submitted
    # after the end clears `line_taken`, nothing is left to set it, and the
    # row said "(waiting — the parts are replying)" in front of a circle
    # that had closed minutes earlier.
    fin = getattr(backend, "finished", None)
    started = getattr(backend, "_thread", None) is not None
    if backend is not None and started and fin is not None and fin.is_set():
        return f"{name} (ended)> " if name else "Self (ended)> "
    taken = getattr(backend, "line_taken", None)
    if taken is not None and hasattr(taken, "is_set") and not taken.is_set():
        tag = _waiting_tag(backend)
        return f"{name}{tag}> " if name else f"Self{tag}> "
    # "(wait)" means "a line typed here is not going to be read now".
    # That is true both when no read is pending AND when the pending one
    # is COMMAND channel (a ratification, a confirmation) — R221. The
    # getattr default is "circle" so a backend without the attribute at
    # all (the self-test's _TogglingBackend) behaves exactly as before.
    # A PENDING QUESTION OWNS THE PROMPT ROW — finding 2, 2026-08-20.
    # circle.py asks the working set and the topic on the CIRCLE channel
    # before the Self> loop exists; both questions used to land in
    # scrollback while the row you type at said only the console name, which is
    # how a /status typed one prompt too early became a working set and
    # then a topic. The question is now the prompt.
    pending = getattr(backend, "pending_prompt", "") if backend else ""
    if pending and getattr(backend, "waiting_for_input", False) \
            and getattr(backend, "waiting_for_channel", "") == "circle" \
            and not getattr(backend, "speaking_turn", False):
        return pending + " "
    if backend is not None and not (
            getattr(backend, "waiting_for_input", True)
            and getattr(backend, "waiting_for_channel", "circle") == "circle"):
        tag = _waiting_tag(backend)
        return f"{name}{tag}> " if name else f"Self{tag}> "
    return base


def _command_prompt(state: AppState) -> str:
    """The command pane's input-row prompt — "cmd> ", or the COMMAND-channel
    question the engine is blocked on. 2026-08-21, the lab's finding 1,
    the operator: *"Overload the prompt instead in this context, restore after a
    valid reply, write diagnostic and repeat upon invalid reply."*

    THE SAME SHAPE AS _circle_prompt's pending-question branch, for the
    other channel. Until this existed "[BP-0039] a)pprove, d)eny, s)kip ?"
    was a scrollback line and the row he typed at said "cmd> " — a
    question asked in one place and answered in another, which is
    finding 2 of the day before, on the other pane. The engine no longer
    echoes a command-channel prompt into scrollback at all (see
    CircleEngine._read_line); the question IS the row while the read is
    pending, and "cmd> " is back the instant it returns — a re-ask after
    an invalid reply is a NEW read, so vetting's own diagnostic lands in
    scrollback and the question returns to the row, which is the
    "repeat". Every command-channel read gets this, not only vetting: "type
    'yes' to apply:", "type 'yes' to open a NEW circle:", "revision text
    (candidates above)>".

    Falls back to `state.command.prompt` with no backend (the demo and
    self-test path) and whenever no command-channel read is pending."""
    backend = state.backend
    pending = getattr(backend, "pending_prompt", "") if backend else ""
    if pending and getattr(backend, "waiting_for_input", False) \
            and getattr(backend, "waiting_for_channel", "") == "command":
        return pending + " "
    # THE CLOSE IS PROCEEDING (2026-08-21): the row is a notice, not a
    # prompt — submit_command refuses every line but 'quit' meanwhile. A
    # command-channel question the close itself asks (vetting at close) still
    # wins, above: that is the one moment a closing circle wants a reply.
    if getattr(backend, "close_state", "") == "closing":
        return "closing the circle — collecting memories, please wait (input disabled) "
    return state.command.prompt


def ui_pane_body_render(state: AppState, which: str, width: int, write,
                      circle_prompt: str | None = None,
                      command_prompt: str | None = None) -> None:
    """This pane's content rows + its input line. Skipped entirely if
    nothing visible has actually changed since the last time this ran —
    see `Pane.body_needs_repaint`. That's also what makes a scrolled-away
    pane frozen: `visible()` stays pinned to the same absolute lines
    regardless of new arrivals, so the diff check is false and this
    returns early without touching the rows. Never touches the OTHER
    pane's rows, and never touches this pane's own header (that's
    `render_pane_header`'s job), so a header-only update elsewhere can
    never accidentally invalidate a frozen body.

    `circle_prompt`, when given, is used verbatim instead of a fresh
    `_circle_prompt(state)` call — see that function's docstring; this is
    the half of the fix that keeps the BODY TEXT in sync with whatever
    `render_cursor` uses for the SAME redraw. `command_prompt` is the
    same contract for the other pane (2026-08-21) — the pending
    command-channel question is read from the engine thread's flags too, and
    a body drawn from one read and a cursor placed from another would
    disagree exactly the way the circle prompt once did."""
    pane = state.circle if which == "circle" else state.command
    # BEFORE the repaint decision, because adopting a new width invalidates
    # the last paint by itself — set_width resets `_painted` when, and only
    # when, the width actually moved.
    pane.set_width(width)
    if which == "circle":
        prompt = circle_prompt if circle_prompt is not None else _circle_prompt(state)
    else:
        prompt = (command_prompt if command_prompt is not None
                  else _command_prompt(state))
    g = _input_geometry(state, which, prompt, width)
    if not pane.body_needs_repaint(g["k"]):
        return
    rows = _pane_rows(state, which)
    vis = pane.visible()
    # THE INPUT TAKES ITS ROWS FROM THE BODY (2026-08-21): while following,
    # the newest body rows stay and the oldest go under the input; while
    # scrolled, the anchored top rows stay and the window's bottom goes.
    br = g["body_rows"]
    shown = ([] if br == 0 else
             (vis[-br:] if pane.scroll_top is None else vis[:br]))
    for i in range(br):
        row = rows["top"] + i
        text = (shown[i] if i < len(shown) else "")[:width]
        if text.lstrip().startswith("!!"):
            text = _tint(C_ERR, text)               # red errors (D64 a)
        write(_move(row, 1) + CLR_LINE + text)
    for j, text in enumerate(g["rows_text"]):
        write(_move(g["first_row"] + j, 1) + CLR_LINE
              + _tint(C_PROMPT, text))              # green prompt row (D64 a)
    pane.mark_painted(g["k"])
    pane.input_rows_drawn = g["k"]
    pane.input_prompt_drawn = prompt               # B66: record what was drawn


def ui_pane_render(state: AppState, which: str, width: int, write,
                 circle_prompt: str | None = None,
                 command_prompt: str | None = None) -> None:
    """Header (always) + body (only if due). The one function most call
    sites want: it always keeps the live "N above/below" count current,
    while leaving unchanged (including scrolled-away-from-live) body
    content completely alone."""
    ui_pane_header_render(state, which, width, write)
    ui_pane_body_render(state, which, width, write, circle_prompt=circle_prompt,
                     command_prompt=command_prompt)


def ui_chrome_render(state: AppState, width: int, write) -> None:
    """The divider and status line — the control legend, and nothing about
    focus. It used to end "focus: CIRCLE/COMMAND"; the split itself now
    carries that (`_pane_heights`), so the text was a second, redundant
    answer to a question the layout already answers. Cheap enough to just
    always redraw when called.

    (`render_focus_tags` lived here — both headers, for a Tab that changed
    a [FOCUS] tag and nothing else. A Tab now changes both pane HEIGHTS,
    which needs `render_full`, so there is nothing left for it to do.)"""
    L = _layout(state)
    write(_move(L["spacer_row"], 1) + CLR_LINE)     # B67: kept blank, always
    write(_move(L["divider_row"], 1) + CLR_LINE
          + _tint(C_CHROME, "-" * min(width, 60)))
    # "(grows to 4/5ths)" LEFT THIS LINE 2026-08-21 at the operator's word — the
    # split itself shows which pane is tall; the legend only has to name
    # the key.
    write(_move(L["status_row"], 1) + CLR_LINE
          + _tint(C_CHROME,
                  ("[Tab] pane   [numpad] scroll (frozen)   "
                   "[arrows] edit   [Enter] catch up   "
                   "[Ctrl-C] quit")[:width]))


def ui_full_render(state: AppState, width: int, write) -> None:
    """Startup only. `Pane._painted` starts as `None`, which already
    differs from any real `visible()` result, so both panes' bodies paint
    on this first call without needing a special-case flag — nothing
    later in the run should call this again."""
    write("\x1b[2J")  # clear screen — once, at startup, defensively
    circle_prompt = _circle_prompt(state)
    command_prompt = _command_prompt(state)
    ui_pane_render(state, "circle", width, write, circle_prompt=circle_prompt)
    ui_pane_render(state, "command", width, write, command_prompt=command_prompt)
    ui_chrome_render(state, width, write)
    ui_cursor_render(state, write, circle_prompt=circle_prompt, width=width,
                  command_prompt=command_prompt)


def _render_input_row(state: AppState, which: str, prompt: str, write,
                      width: int | None = None) -> None:
    """ONE pane's input row, drawn with a prompt the caller already read —
    the shared body of render_input_line and main_loop's prompt-change
    tick (2026-08-21). Places no cursor: the caller does that once, from
    the same reads, after every row it touched."""
    pane = state.circle if which == "circle" else state.command
    g = _input_geometry(state, which, prompt, width)
    if g["k"] != pane.input_rows_drawn:
        # The input grew or shrank by a row: the body's bottom edge moved,
        # so this is a body redraw, not a row redraw. render_pane_body's
        # own gate includes the row count and will repaint.
        ui_pane_body_render(state, which, width, write,
                         circle_prompt=prompt if which == "circle" else None,
                         command_prompt=prompt if which == "command" else None)
        return
    for j, text in enumerate(g["rows_text"]):
        write(_move(g["first_row"] + j, 1) + CLR_LINE
              + _tint(C_PROMPT, text))              # green prompt row (D64 a)
    pane.input_rows_drawn = g["k"]
    pane.input_prompt_drawn = prompt               # B66: record what was drawn


def ui_input_line_render(state: AppState, write, width: int | None = None) -> None:
    """Cheapest redraw: just the focused pane's own input line, for the
    common case of one keystroke. Never touches the other pane's lines.
    `width` threads through to the shared _input_view window (tier 4
    #38); None — the selftest's legacy calls — means no windowing."""
    prompt = (_circle_prompt(state) if state.focus == "circle"
              else _command_prompt(state))
    _render_input_row(state, state.focus, prompt, write, width)
    ui_cursor_render(state, write,
                  circle_prompt=prompt if state.focus == "circle" else None,
                  command_prompt=prompt if state.focus == "command" else None,
                  width=width)


def ui_cursor_render(state: AppState, write, circle_prompt: str | None = None,
                  width: int | None = None,
                  command_prompt: str | None = None) -> None:
    """`circle_prompt`, when given, is used verbatim instead of a fresh
    `_circle_prompt(state)` read. WHY THIS MATTERS: `waiting_for_input` is
    mutated by `CircleEngine`'s background thread — reading it twice (once
    to draw the body's prompt text, once here to place the cursor) is two
    independent, unsynchronized reads of a value that can change between
    them. Reported live: the body showed "Self (waiting)> " (long) while the
    cursor landed at column `len("Self> ")+1` (short) — right before the
    "w", because the flag flipped from busy to ready in the gap between
    the two reads. Every caller that already computed a `circle_prompt`
    for the body text passes the SAME string here so the two can never
    disagree; only a caller with no body text in flight (e.g. after a Tab)
    lets this take its own fresh read, which is safe since nothing else
    read the flag in that same redraw to disagree with.

    NOT THE SAME PROBLEM AS `line_taken` (B57(1)), though they are cousins
    and share a cause. That event answers "was my submitted line consumed";
    this is a TORN READ — one value, read twice in one redraw — and its fix
    is compute-once-pass-it-down, which no handshake would help with. A
    reader here for the flag's staleness after a submit wants the engine's
    event, not this."""
    if state.focus == "circle":
        prompt = circle_prompt if circle_prompt is not None else _circle_prompt(state)
    else:
        prompt = (command_prompt if command_prompt is not None
                  else _command_prompt(state))
    # The SAME layout computation the input-row drawers use (tier 4 #38;
    # the wrapped rows since 2026-08-21), so the row and column always name
    # the cell the input actually shows there.
    g = _input_geometry(state, state.focus, prompt, width)
    write(_move(g["first_row"] + g["cur_row"], g["cur_col"]))


# --------------------------------------------------------------------------
# Input capture — the only OS-specific, TTY-dependent layer.
# --------------------------------------------------------------------------

def _surrogate_pair(hi: str, lo: str) -> str:
    """Two UTF-16 code units -> the one astral character they encode.
    Platform-neutral (and so selftest-able anywhere) though only the
    Windows poll_key needs it: msvcrt.getwch() delivers a non-BMP
    character — an emoji — as a HIGH surrogate then a LOW surrogate,
    each of which fails the isprintable() gates in read_burst and
    handle_key, so astral characters were silently dropped from typed
    and pasted input on this project's primary platform (2026-08-18
    review, tier 4 #39). The combined result is one code point: len 1,
    printable, and both consumers accept it unchanged."""
    return (hi + lo).encode("utf-16", "surrogatepass").decode("utf-16")


# THE POSIX ESCAPE TABLE LIVES OUT HERE, above the platform split, for the same
# reason _surrogate_pair does: everything platform-NEUTRAL is assertable on every
# platform, including the only one this project has. RULED 2026-09-09 by the
# operator ("yes split"), after the 2026-09-08 audit found the POSIX branch below
# structurally unreachable here — sys.platform is win32, so the module never
# defines those functions and no suite can import them. This file is a packaging
# entry point (packaging/required.toml) and the bundle publishes to GitHub, so a
# recipient on Linux or macOS runs that branch and nobody here ever has.
#
# WHAT THE SPLIT BUYS AND WHAT IT DOES NOT. The table and its lookup are pure —
# a sequence in, a token out — and are now covered on Windows. The termios/tty/
# select half below still cannot run here and is NAMED in an exemption rather
# than left implicit, which is the trade R491 made for ui/tests/circle_test.py.
# enable_vt_mode's Windows ctypes body is uncovered for the mirror-image reason
# (legacy conhost only, never Windows Terminal) and is named in the same place.
#
# THE THREE FORMS, and why a Mac needs all of them:
#   CSI    \x1b[A     the normal-cursor-key form, the default state
#   SS3    \x1bOA     the APPLICATION-cursor-key form, left on by whatever ran
#                     before us; several emulators use it for Home/End always
#   tilde  \x1b[5~    what some terminals send for PgUp/PgDn/Home/End instead
POSIX_ESC = {
    "\x1b[A": "UP", "\x1b[B": "DOWN",
    "\x1b[C": "RIGHT", "\x1b[D": "LEFT",
    "\x1bOA": "UP", "\x1bOB": "DOWN",
    "\x1bOC": "RIGHT", "\x1bOD": "LEFT",
    "\x1b[5~": "PGUP", "\x1b[6~": "PGDN",
    "\x1b[H": "HOME", "\x1b[F": "END",
    "\x1bOH": "HOME", "\x1bOF": "END",
    "\x1b[1~": "HOME", "\x1b[4~": "END",
    "\x1b[7~": "HOME", "\x1b[8~": "END",
}


def ui_posix_escape_read(seq: str) -> "str | None":
    """The token a POSIX escape sequence names, or None for anything unmapped.

    PURE: no terminal, no select, no stdin, so it is assertable on every
    platform including this one. A bare ESC and a partial sequence both return
    None, which is what lets _read_escape below keep reading."""
    return POSIX_ESC.get(seq)


if IS_WINDOWS:
    import msvcrt

    def enable_vt_mode() -> None:
        """Legacy conhost needs ENABLE_VIRTUAL_TERMINAL_PROCESSING turned on
        before it honours ANSI escapes; Windows Terminal already has it on,
        so this is a defensive no-op there. Never fatal — if the console
        handle can't be reconfigured, the escapes may just not render, and
        that is a Windows Terminal question, not this script's."""
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            k.GetConsoleMode(h, ctypes.byref(mode))
            k.SetConsoleMode(h, mode.value | 0x0004)
        except Exception:
            pass

    class raw_mode:
        """`msvcrt.getwch` needs no mode change to read one key at a time,
        so this is a no-op context manager kept only so the call site
        reads the same on both platforms."""
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    # Extended-key scan codes, the second `getwch()` after a `\x00`/`\xe0`
    # lead byte. Standard PC scan codes for the arrow/paging cluster —
    # unrelated to the POSIX escape sequences below, hence a separate map.
    #
    # THE LEAD BYTE IS THE ANSWER, AND IT WAS BEING THROWN AWAY until
    # 2026-08-25: one table, keyed on the scan code alone. Windows sends
    # `\xe0` before the DEDICATED cluster's scan code and `\x00` before the
    # NUMPAD's (NumLock OFF) — the same eight codes either way. Measured at
    # the operator's own terminal before any of this was written: numpad
    # 7/8/9/4/6/1/2/3 all lead `\x00`, the arrow cluster all lead `\xe0`.
    #
    # So the two clusters take two jobs, with no mode and no modifier — the
    # operator, 2026-08-25: *"number pad to scroll, dedicated to change
    # line?"* The NUMPAD scrolls the pane; the ARROWS move the cursor
    # through what you are typing, including up and down a WRAPPED line.
    # The rival was making Up/Down mean one thing while the input wrapped
    # and another when it did not, which puts a key's meaning inside the
    # state of the line; two clusters put it in the keyboard instead.
    _WIN_SCAN_NUMPAD = {"H": "UP", "P": "DOWN", "I": "PGUP", "Q": "PGDN",
                        "G": "HOME", "O": "END",
                        # nothing scrolls SIDEWAYS, so 4 and 6 keep the one
                        # meaning they can have
                        "K": "LEFT", "M": "RIGHT"}
    _WIN_SCAN_EXT = {"H": "CUR_UP", "P": "CUR_DOWN",
                     "G": "CUR_HOME", "O": "CUR_END",
                     "K": "LEFT", "M": "RIGHT",
                     # PAGING STAYS ON BOTH CLUSTERS, deliberately. With
                     # NumLock ON the numpad sends digits and the whole
                     # scroll set disappears; on a keyboard with no numpad
                     # it was never there. These two, plus a bare Enter's
                     # catch-up, are what keep a pane readable in both
                     # cases.
                     "I": "PGUP", "Q": "PGDN"}

    def poll_key() -> str | None:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):     # numpad / dedicated lead byte
                ch2 = msvcrt.getwch()       # the actual scan code
                table = _WIN_SCAN_EXT if ch == "\xe0" else _WIN_SCAN_NUMPAD
                return table.get(ch2)       # None for keys we don't bind
            if "\ud800" <= ch <= "\udbff":
                # A high surrogate: getwch() is delivering an astral
                # character (emoji) as two UTF-16 code units, and its low
                # half is already in the console buffer — they arrive
                # together for a keystroke and a paste alike. Pair them
                # here so downstream sees one printable character
                # (_surrogate_pair above; tier 4 #39). A lone high
                # surrogate — corrupted input — degrades instantly: the
                # unpaired unit passes through and the isprintable()
                # gates drop it exactly as they always did, and a
                # non-surrogate follower is pushed back (ungetwch) so
                # nothing is ever consumed out of order. This wiring is
                # Windows-console-only and outside the suite's reach; the
                # pairing math itself is selftest-covered.
                if msvcrt.kbhit():
                    lo = msvcrt.getwch()
                    if "\udc00" <= lo <= "\udfff":
                        return _surrogate_pair(ch, lo)
                    msvcrt.ungetwch(lo)
                return ch
            return ch
        return None

else:
    import select
    import termios
    import tty

    def enable_vt_mode() -> None:
        pass

    class raw_mode:
        def __enter__(self):
            self._is_tty = sys.stdin.isatty()
            if self._is_tty:
                self.fd = sys.stdin.fileno()
                self.old = termios.tcgetattr(self.fd)
                tty.setcbreak(self.fd)
            return self

        def __exit__(self, *exc):
            if self._is_tty:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
            return False

    # xterm/VT100 escape sequences for the arrow/paging cluster. THREE
    # SPELLINGS OF THE SAME KEYS, because terminals disagree and the
    # disagreement is silent — an unmapped sequence returns None and the
    # key simply does nothing, which reads as "this app ignores my arrow
    # keys" rather than as anything diagnosable.
    #
    #   CSI    \x1b[A     the normal-cursor-key form. What a terminal in
    #                     its default state sends, and what this app gets,
    #                     since nothing here ever turns application cursor
    #                     mode on.
    #   SS3    \x1bOA     the APPLICATION-cursor-key form. A terminal left
    #                     in that mode by whatever ran before us sends
    #                     these, and several emulators use the SS3 form for
    #                     Home/End unconditionally. Added 2026-08-24 while
    #                     answering whether this runs on a Mac: everything
    #                     this file PAINTS is universal (CUP, EL, ED, the
    #                     alternate screen buffer, and no colour at all),
    #                     so the input map was the only place a terminal
    #                     could disagree.
    #   tilde  \x1b[5~    what some terminals send for PgUp/PgDn/Home/End
    #                     instead.
    #
    # Not exhaustive across every emulator that exists, and this backend
    # is still less travelled than the Windows one (see README) — but a
    # key that does nothing is now much less likely than it was.
    # THE TABLE MOVED OUT, 2026-09-09 — it and its lookup are module-level now
    # (POSIX_ESC / ui_posix_escape_read, above IS_WINDOWS), so they are asserted
    # on Windows too. What is left in here is the half that genuinely needs a
    # POSIX terminal: select on stdin, and reading a byte at a time.

    def _read_escape() -> str | None:
        """Called after a bare ESC was read. The rest of a real escape
        sequence follows within milliseconds — a stray bare ESC (rare, and
        unbound even if it happens) will just time out and return None."""
        seq = "\x1b"
        for _ in range(4):
            r, _, _ = select.select([sys.stdin], [], [], 0.01)
            if not r:
                break
            seq += sys.stdin.read(1)
            tok = ui_posix_escape_read(seq)
            if tok is not None:
                return tok
        return ui_posix_escape_read(seq)

    def poll_key() -> str | None:
        if not sys.stdin.isatty():
            return None
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if not r:
            return None
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            return _read_escape()
        return ch


# --------------------------------------------------------------------------
# Burst draining — cross-platform, built on `poll_key` rather than part of
# either OS-specific backend above.
# --------------------------------------------------------------------------


def ui_burst_read(first_ch: str, poll=None) -> list[tuple[str, str]]:
    """Drain everything already sitting in the input buffer, starting with
    `first_ch`, and group it into ('text', batched_chars) and
    ('key', single_token) units, in the order they arrived.

    WHY THIS EXISTS. A paste delivers its whole clipboard as a burst of
    characters landing on stdin essentially at once — far faster than any
    human types. Feeding that through the single-keystroke path meant one
    `input_buf` mutation AND one screen redraw PER CHARACTER: correct, but
    visibly slow and flickery for anything beyond a few words — reported
    directly as unusable for long copies. `poll_key()` returning `None`
    means "nothing else is buffered right now", which is true almost
    immediately after a human's own keystroke and only false when
    something delivered a burst — so checking it right after the first
    character is a reliable, protocol-free way to tell the two apart,
    without needing real bracketed-paste support (`\\x1b[200~...\\x1b[201~`).
    That protocol would need `ENABLE_VIRTUAL_TERMINAL_INPUT` turned on for
    the Windows console too, on top of the output flag `enable_vt_mode`
    already sets — a mode change to how Windows delivers ALL input,
    including the arrow/paging keys already working, that can't be
    verified without a real Windows box. This gets the practical result
    (fast, single-redraw pastes) without touching that.

    A CR/LF IS A REAL ENTER ONLY AS THE VERY FIRST CHARACTER READ — a
    genuine, deliberate keypress is never batched, so `state.handle_key`
    still sees it and submits normally. Any CR/LF encountered AFTER that,
    while a batch is already being drained, is treated as paste content
    (a multi-line clipboard paste lands as embedded newlines) and folded
    in as a single space rather than ending the batch. ACCEPTED, NARROW
    EDGE CASE: if a real Enter keypress happens to already be sitting in
    the buffer in the very same burst as characters typed just before it
    — plausible only under unusually fast typing or key-repeat, not a
    paste — it will be folded into the text batch as a space instead of
    submitting. A minimal harness accepts this rather than adding lookahead
    to disambiguate it; a production input stack would want that lookahead."""
    poll = poll or poll_key
    units: list[tuple[str, str]] = []
    if first_ch in ("\r", "\n"):
        return [("key", first_ch)]
    cur = ""
    ch = first_ch
    while ch is not None:
        if len(ch) == 1 and (ch.isprintable() or ch in "\r\n"):
            cur += " " if ch in "\r\n" else ch
        else:
            if cur:
                units.append(("text", cur))
                cur = ""
            units.append(("key", ch))
        ch = poll()
    if cur:
        units.append(("text", cur))
    return units


def _pane_heights(rows: int, focus: str) -> tuple[int, int]:
    """Split the terminal's row count between the two panes: THE FOCUSED
    ONE gets 4/5ths of what's left after the header/divider/status chrome,
    the other 1/5th. `focus` is `AppState.focus` — "circle" or "command"
    — so a Tab reshapes the screen, and the taller pane is what tells you
    where your keystrokes are going, in place of the "[FOCUS]"/"focus: X"
    text this replaced.

    Each side keeps a floor so a short terminal gets a usable pane — but
    the floors YIELD to the screen (2026-08-19, review tier 4 #40): the
    old unconditional 6/4 floors fit only when rows-8 >= 16, so on an
    18-to-23-row terminal the layout quietly needed more rows than
    existed and every absolute write past the bottom clamped onto the
    last row — the command body, its input line, and the status legend
    overwriting one another on every tick. Three bands now: the ruled
    6/4 floors whenever they genuinely fit; a fitted split (focused pane
    gets what can be spared, each side at least one row) down to two
    spare rows; and a 1/1 minimum below that, where SOME overlap is
    unavoidable but it is one row's worth, not four.

    `focus` is REQUIRED, deliberately: there are four call sites (startup,
    terminal resize, the help/revert signal, and Tab) and a default would
    turn a missed one into a silently wrong split rather than a TypeError.
    Returns `(circle_h, command_h)` in that fixed order either way —
    `focus` decides which slot gets the large share, never the ordering.

    Folded in here 2026-08-18: a separate `_pane_heights_help()` used to
    hold the inverse ratio for a help listing, and it is exactly
    `_pane_heights(rows, "command")` now — help is typed in COMMAND,
    which therefore already has focus and already has the 4/5ths."""
    avail = rows - 9                     # the chrome rows around the panes
                                         # (9 since B67's spacer row above
                                         # the divider, 2026-08-25; was 8)
    if avail >= 16:                      # the 6/4 floors genuinely fit
        big = max(6, int(avail * 0.8))
        small = max(4, avail - big)
    elif avail >= 2:                     # short terminal: fit what exists
        small = max(1, avail // 5)
        big = avail - small
    else:                                # pathological (rows <= 9)
        big = small = 1
    return (big, small) if focus == "circle" else (small, big)


def _strip_resume(argv: list[str]) -> list[str]:
    """Remove any existing `--resume OPEN_TIME` pair from an argv list, so
    resuming a SECOND time (or resuming a session that was itself opened
    with --resume) doesn't stack a stale --resume behind the fresh one
    main_loop's 'resume:<OT>' handling is about to add."""
    out: list[str] = []
    skip = False
    for a in argv:
        if skip:
            skip = False
            continue
        if a == "--resume":
            skip = True
            continue
        out.append(a)
    return out


# --------------------------------------------------------------------------
# Interactive main loop.
# --------------------------------------------------------------------------

TICK = 0.05  # seconds between polls — 20Hz, well under perceptible lag


ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"


_PARKED_EXIT = (
    "\n  the circle was WAITING FOR YOU TO TYPE — nothing was in flight, so "
    "this exits at once.\n"
    "  Its transcript is written and intact. The circle is left OPEN: the "
    "next open reports it,\n"
    "  and circle_state.py calls it open until it has been quiet 45 minutes.")


def _parked_on_read(engine) -> bool:
    """Is the engine BLOCKED IN A READ with nothing queued for it?

    Then nothing is in flight — no model call, no file being written, no
    commit. The thread is sitting in `circle_in.get()` (or `command_in`'s)
    waiting for a line only this process's UI can send, so waiting for it
    to finish waits forever by construction.

    THE QUEUES ARE PART OF THE TEST, not decoration. `waiting_for_input`
    still reads True for the instant after a line is submitted — the thread
    has not woken from `get()` yet — and that line is about to become work.
    A queued line means work is coming; a pending read over EMPTY queues
    means the engine is parked.

    getattr throughout: a backend that is not a CircleEngine (the
    self-test's fakes, the demo path) carries none of these attributes
    and must read NOT parked — the conservative answer, and exactly the
    behaviour every caller was written against before this existed."""
    if not getattr(engine, "waiting_for_input", False):
        return False
    for name in ("circle_in", "command_in"):
        q = getattr(engine, name, None)
        if q is not None and not q.empty():
            return False
    return True


def ui_live_engine_wait(engine: "CircleEngine", warn_after: float = 60,
                                     out=print) -> None:
    """RULED 2026-08-13 (Q3 sub-item): quitting must not silently orphan
    a live circle. `CircleEngine`'s background thread is `daemon=True`
    (see its own docstring) — the instant this process actually exits,
    that thread is killed with NO `finally` guarantee, wherever it
    happens to be, which could be mid-/close (short_terms half-written,
    a git commit half-applied). Harmless for --dry-run (nothing real to
    lose, and `ui_main_loop()`'s `finally` only calls this when
    `engine.live` is True to begin with); a genuine risk otherwise.

    IT WAITS FOR WORK, NEVER FOR AN ANSWER — RULED 2026-08-25 by the
    operator: *"Exit at once whenever the circle is waiting for input; keep
    waiting only while a close or an API call is in flight."* Until then it
    waited for the thread to FINISH, and a circle parked at its own prompt
    can only finish if this UI feeds it a line — which it can no longer do,
    having just been quit. The result was a process that could not be
    exited at all: the wait caught Ctrl-C by design, and its own warning
    told the reader not to kill it. Measured 2026-08-25 on the published
    package, 27 minutes into a hang whose transcript had not been touched
    since minute one. `_parked_on_read()` is the test, asked before the
    wait and again inside it — the second is not optional, or the wedge
    simply moves to the engine's next question.

    Otherwise it waits `warn_after` seconds (a normal-speed close/API-call
    just finishes quietly within that), then keeps waiting UNBOUNDED,
    warning every `warn_after` seconds — the alternative is corrupting real
    project data, which is not a tradeoff this process gets to make
    unilaterally. A raw Ctrl-C during the unbounded wait is a real
    `KeyboardInterrupt` at the Python level (this runs after `main_loop`'s
    own `except KeyboardInterrupt`, so nothing else catches it) — caught
    and re-waited on purpose, so the warning's own claim ("Ctrl-C will
    not cut it short") is something the code actually does, not just says.

    Extracted from `ui_main_loop()`'s `finally` block specifically so it is
    callable — and its timing testable, via `warn_after` — without a
    real TTY, which `ui_main_loop()` itself requires and the self-test
    cannot exercise (see this file's own top-of-file docstring)."""
    if not (engine.live and not engine.finished.is_set()):
        return
    if _parked_on_read(engine):
        out(_PARKED_EXIT)
        return
    out(f"\n  a LIVE circle is still running — waiting for it to finish "
        f"before exiting (up to {warn_after:g}s)...")
    # POLLED, so the parked test above is re-asked while we wait. Without
    # it the wedge only moves: an engine mid-call when quit was typed
    # finishes the call, asks its next question, and waits forever for an
    # answer from a UI that has already gone.
    poll = min(0.25, warn_after)
    waited = 0.0
    while not engine.finished.is_set():
        if _parked_on_read(engine):
            out(_PARKED_EXIT)
            return
        try:
            if engine.finished.wait(timeout=poll):
                break
        except KeyboardInterrupt:
            continue
        waited += poll
        if waited >= warn_after:
            waited = 0.0
            out(f"  !! still running past {warn_after:g}s — a model call, a "
                f"write or a commit is in flight, so this keeps waiting, and "
                f"Ctrl-C will not cut it short. It ends by itself the moment "
                f"the circle finishes or comes back asking for input.")
    out("  circle finished — exiting cleanly.")


def ui_main_loop(engine: "CircleEngine | None" = None,
              extra_argv: list[str] | None = None) -> int:
    """`extra_argv` is only meaningful with a real `engine` attached — the
    exact argv `CircleEngine.start()` was given (e.g. `--parts a,b,c`),
    kept around so a 'resume:<OT>' command-pane verb can start a REPLACEMENT
    engine with the same parts/options plus `--resume <OT>`, without the
    caller having to retype the whole invocation."""
    cols, rows = shutil.get_terminal_size(fallback=(80, 24))
    # "circle" is AppState's own opening focus — asserted immediately
    # below rather than assumed, since the split and the focus have to
    # agree from the very first frame or the screen lies about where
    # typing lands.
    state = AppState(*_pane_heights(rows, "circle"), backend=engine)
    assert state.focus == "circle", "opening split must match opening focus"
    # THE REDACTED VIEW'S OWN DEFAULT (2026-08-31) — seeded here, not in
    # AppState.__init__, which the self-test and test_circling.py's stub
    # engine both exercise headless with zero coordinator imports. Only
    # the CIRCLE pane is seeded; state.command's redact_view stays False
    # for the life of the window. COORD_DIR is pushed here (as
    # _command_surface() and CircleEngine.__init__ each already do
    # independently) because the bare demo path (`engine is None`) reaches
    # this line before either of those runs — audit-register.md #5,
    # broken since 95f8b15 2026-09-03.
    sys.path.insert(0, str(COORD_DIR))
    import stream_redaction as SR
    state.circle.set_redact(SR.REDACT_VIEW_DEFAULT)
    extra_argv = list(extra_argv or [])

    # `engine is None` (the default) is byte-for-byte the demo path this
    # function has always run — AgentSimulator, its own queue, the
    # welcome banner below. `engine` given means a real CircleEngine
    # already started (docs/dual_pane_integration.md §1/§5 step 3) whose
    # `out_queue` carries `(channel, text)` pairs instead of bare lines.
    sim = None
    # on_finished() is a ONE-SHOT: the flag, not the Event, is what says
    # whether the banner has been printed, since the Event stays set.
    ended_announced = False
    if engine is not None:
        q = engine.out_queue
    else:
        state.circle.append(
            "*** harness open. Parts speak on their own timers. Type here and "
            "press Enter to post. Tab moves to COMMANDS. ***")
        q: "queue.Queue[str]" = queue.Queue()
        sim = AgentSimulator(q)
        sim.start()

    enable_vt_mode()
    write = sys.stdout.write
    flush = sys.stdout.flush

    # ALTERNATE SCREEN BUFFER — the standard xterm/VT mechanism full-screen
    # terminal apps (vim, less, htop, tmux) use for exactly this reason: it
    # gives the app its own screen that is never appended to the terminal's
    # own scrollback, so there is nothing for the terminal's native
    # scrollbar to represent while this runs. Most terminals (Windows
    # Terminal included) grey out or hide the scrollbar in this mode
    # because it has nothing to scroll — the widget itself is the
    # terminal's, not something this script can reach through ANSI codes,
    # but this removes the reason for it to be live. `ALT_SCREEN_OFF` is in
    # `finally`, wrapping `raw_mode()` too, so a raw Ctrl-C (SIGINT, caught
    # below) or any exception still restores the normal screen exactly as
    # it was rather than leaving the terminal stuck showing this app's
    # last frame.
    write(ALT_SCREEN_ON)
    try:
        with raw_mode():
            ui_full_render(state, cols, write)
            flush()
            # WHAT EACH INPUT ROW LAST SHOWED lives on the pane itself now
            # (`Pane.input_prompt_drawn`, set at the draw sites) — B66,
            # 2026-08-25. This loop kept its own `last_prompts` copy until
            # then, updated only on the paths that remembered to, and the
            # keystroke path did not: a submit drew "(waiting)" without
            # telling the tick, so a prompt that came BACK to the tick's
            # last reading (question -> waiting -> the SAME question,
            # which is every re-asked question) compared equal and was
            # never repainted. The operator watched exactly that in the
            # install circle: the row kept the bare waiting prompt while the
            # cursor sat at the re-asked question's own column, until an
            # arrow key forced a redraw. Comparing against what was DRAWN
            # cannot have that hole, because every drawer updates the
            # record at the moment it writes.
            while state.running:
                # TERMINAL RESIZED mid-run. This app can't lock the actual
                # containing window from inside a Windows Terminal child
                # process — GetConsoleWindow()/SetWindowLong-style tricks
                # only affect classic conhost windows; under ConPTY (what
                # Windows Terminal uses), the child's console window
                # handle is a hidden message-only pseudo-window, not the
                # real one the user sees and drags, so nothing this
                # process does to it has any visible effect (confirmed via
                # microsoft/terminal#12570 — GetConsoleWindow "returns a
                # window handle for message queue purposes only" under
                # ConPTY). What IS reachable from here: detect the new
                # size, recompute both panes' heights, clamp any scroll
                # position to still fit, and do one full clean redraw at
                # the new geometry — the same call used at startup —
                # instead of leaving stale rows on screen that no longer
                # correspond to the new layout.
                new_cols, new_rows = shutil.get_terminal_size(
                    fallback=(cols, rows))
                if (new_cols, new_rows) != (cols, rows):
                    cols, rows = new_cols, new_rows
                    state.resize(*_pane_heights(rows, state.focus))
                    ui_full_render(state, cols, write)
                    flush()

                drained = False
                touched_command = False
                refocus = False
                while True:
                    try:
                        item = q.get_nowait()
                    except queue.Empty:
                        break
                    if engine is not None:
                        # CircleEngine items are (channel, text) —
                        # circle.py's own emit() argument is the single
                        # source of truth for which pane; see
                        # CircleEngine's own docstring.
                        channel, line = item
                        if channel == "prefill":
                            # NOT CONTENT — never appended to a pane. The
                            # coordinator is asking a question again with
                            # part of the previous answer already typed
                            # (finding 2): the invalid ids removed, the
                            # cursor at the end, so a bare Enter submits
                            # the valid remainder.
                            state.circle.input_buf = line
                            state.circle.input_cursor = len(line)
                            drained = True
                            continue
                        if channel == "state":
                            # NOT CONTENT EITHER (2026-08-21): the
                            # coordinator saying where its close is. The
                            # engine already holds the token; this is the
                            # screen's turn — "closing" hands the window
                            # over, in order with the lines around it.
                            if state.on_state(line) == "focus":
                                refocus = True
                            drained = True
                            continue
                        if channel == "redact_view":
                            # NOT CONTENT EITHER (2026-08-31): the
                            # redact_view setting's own live-toggle signal
                            # (cmd_settings_update/_clear, via
                            # coordinator/seam.py). Applies ONLY to the
                            # CIRCLE pane, by name — never state.command,
                            # which is the whole of "never in any lower
                            # tab" at this level. Position matters: this
                            # must be handled before the `target = ...`
                            # line below, or an unhandled item here would
                            # fall into state.command by default and
                            # print the literal word "on"/"off" there.
                            state.circle.set_redact(line == "on")
                            drained = True
                            continue
                        target = state.circle if channel == "circle" else state.command
                        touched_command = touched_command or target is state.command
                    else:
                        line = item
                        target = state.circle
                    target.append(line)
                    drained = True
                    # AN ERROR MUST NOT SCROLL PAST (2026-08-25). Checked
                    # here, AFTER the append, because the anchor is a row
                    # index into what was just appended. Only the engine
                    # path: the demo has no `!!` lines and no command
                    # channel to raise them on.
                    if (engine is not None and channel == "command"
                            and state.on_alert(line) == "focus"):
                        refocus = True
                if refocus:
                    # Both pane heights follow focus: the same full redraw a
                    # Tab gets, and it repaints whatever this drain appended.
                    state.resize(*_pane_heights(rows, state.focus))
                    state.apply_alert_anchor()   # AFTER the resize — resize
                    ui_full_render(state, cols, write)  # clamps, and would eat it
                elif drained:
                    # A NEW LINE IN CIRCLE MUST NEVER MOVE FOCUS, TOUCH THE
                    # COMMAND PANE, OR TOUCH CIRCLE'S OWN BODY IF CIRCLE IS
                    # FROZEN OR SCROLLED AWAY FROM THE LIVE EDGE. Only
                    # circle's own header+body are redrawn in the demo
                    # path (never command's, since nothing there ever
                    # writes to it) — `render_pane_body`'s own guard is
                    # what actually decides whether a given pane's body
                    # paints, so calling it on an unchanged pane is a
                    # cheap no-op, not a correctness risk.
                    circle_prompt = _circle_prompt(state)
                    command_prompt = _command_prompt(state)
                    ui_pane_render(state, "circle", cols, write, circle_prompt=circle_prompt)
                    if touched_command:
                        ui_pane_render(state, "command", cols, write,
                                    command_prompt=command_prompt)
                    ui_cursor_render(state, write, circle_prompt=circle_prompt,
                                  width=cols, command_prompt=command_prompt)

                # THE END OF THE CIRCLE IS ANNOUNCED, ONCE — 2026-08-25, the
                # operator: *"After /close finishes its post-close
                # processing, the UI just sits."* AFTER the drain and only
                # once the queue is empty, so the banner is the last thing on
                # the page rather than landing in front of the close's own
                # final lines. Nothing can add to that queue afterwards: the
                # thread that fed it is gone.
                if (engine is not None and not ended_announced
                        and engine.finished.is_set() and q.empty()):
                    ended_announced = True
                    if state.on_finished() == "focus":
                        state.resize(*_pane_heights(rows, state.focus))
                        ui_full_render(state, cols, write)

                # A PROMPT CAN CHANGE WITH NOTHING ARRIVING — 2026-08-21. A
                # command-channel question takes the cmd> row with NO scrollback
                # line at all now (CircleEngine._read_line), and the engine
                # thread sets the flags that decide BOTH prompts after its
                # last emit, so a drain that lands between the two paints
                # the old row and the next tick has nothing to drain. The
                # same gap already existed for "(waiting)" on the circle
                # row, only never this visibly. So each tick reads both
                # prompts ONCE and redraws only the rows whose text moved —
                # nothing else on screen is touched, which keeps the
                # "a line in one pane never disturbs the other" invariant
                # the drain path above is built around.
                #
                # "MOVED" MEANS moved from WHAT IS ON SCREEN — B66,
                # 2026-08-25: the baseline is each pane's own
                # `input_prompt_drawn`, written at the draw sites, never a
                # loop-local copy a draw path can forget to update.
                circle_prompt = _circle_prompt(state)
                command_prompt = _command_prompt(state)
                if (circle_prompt != state.circle.input_prompt_drawn
                        or command_prompt != state.command.input_prompt_drawn):
                    if circle_prompt != state.circle.input_prompt_drawn:
                        _render_input_row(state, "circle", circle_prompt, write, cols)
                    if command_prompt != state.command.input_prompt_drawn:
                        _render_input_row(state, "command", command_prompt, write, cols)
                    ui_cursor_render(state, write, circle_prompt=circle_prompt,
                                  width=cols, command_prompt=command_prompt)

                ch = poll_key()
                if ch:
                    # A PASTE ARRIVES AS A BURST, not one keystroke — drain
                    # everything already buffered right now and process it
                    # as grouped units instead of one redraw per character.
                    # See `read_burst`. For ordinary typing this is a
                    # single unit, so nothing changes for the common case.
                    for kind, value in ui_burst_read(ch):
                        effect = (state.handle_text(value) if kind == "text"
                                  else state.handle_key(value))
                        reposition = True
                        # Read ONCE per unit and reused below for both the
                        # body text (inside render_pane/render_full) and
                        # the cursor column — two independent reads of
                        # `waiting_for_input` (a flag CircleEngine's
                        # background thread mutates) could disagree with
                        # each other; see render_cursor's docstring.
                        circle_prompt = (_circle_prompt(state)
                                         if state.focus == "circle" else None)
                        command_prompt = (_command_prompt(state)
                                          if state.focus == "command" else None)
                        if effect == "quit":
                            break
                        elif effect in ("submit", "scroll"):
                            # Always the pane that HAD focus at keypress
                            # time — never the other one.
                            ui_pane_render(state, state.focus, cols, write,
                                       circle_prompt=circle_prompt,
                                       command_prompt=command_prompt)
                        elif effect in ("focus", "help_resize", "revert_resize"):
                            # ONE BRANCH, because all three are now the
                            # same event: both pane heights are a function
                            # of focus (`_pane_heights`), so a Tab needs
                            # the same FULL redraw a terminal resize gets,
                            # not the header touch-up it used to get. The
                            # ruled help/revert pair collapses into it —
                            # `AppState._submit` only ever raises those
                            # from the pane that HAS focus, so
                            # `state.focus` already names the pane that
                            # should be tall, and no conditional is left.
                            # `reposition = False` because `render_full`
                            # places the cursor itself, from its own single
                            # `_circle_prompt` read — letting the outer
                            # reposition run would be the second,
                            # unsynchronized read `render_cursor`'s
                            # docstring exists to prevent.
                            state.resize(*_pane_heights(rows, state.focus))
                            ui_full_render(state, cols, write)
                            reposition = False
                        elif effect == "input":
                            ui_input_line_render(state, write, cols)  # repositions itself
                            reposition = False
                        elif effect is not None and effect.startswith("resume:"):
                            # 'resume <open_time>' from the COMMAND pane —
                            # same function as circle.py's own --resume
                            # flag, without quitting and relaunching.
                            ot = effect.split(":", 1)[1]
                            if not engine.finished.wait(timeout=5):
                                # DO NOT start a second engine while the
                                # first may still be running: both would
                                # rebind seam.py's module-level emit()/
                                # read_line() and clobber each other.
                                #
                                # AND TAKE THE DECLINE BACK (tier 4 #36):
                                # submit_command queued "no" on command_in
                                # to answer the "type 'yes' to open a NEW
                                # circle" read this verb exists for. The
                                # engine did not finish, so either it was
                                # parked on a CIRCLE-channel read (the "no"
                                # sits unconsumed and the NEXT command-
                                # channel question — a vetting a/d/s, a
                                # "type 'yes' to apply" — would be
                                # silently answered by it), or it took
                                # the decline and is finishing slowly
                                # (queue already empty; nothing to take).
                                # Flushing ALL of command_in is safe
                                # today because it has exactly two
                                # producers — the pending-command-read
                                # forward in submit_command's first
                                # branch, whose text the blocked read
                                # consumes immediately, and this verb's
                                # own "no" — and this loop is single-
                                # threaded and was blocked in wait()
                                # since the put. A third producer must
                                # reckon with this flush.
                                try:
                                    while True:
                                        engine.command_in.get_nowait()
                                except queue.Empty:
                                    pass
                                state.command.append(
                                    f"  ! resume failed: the current circle "
                                    f"session did not finish within 5s — "
                                    f"try 'abort', then 'resume {ot}' again")
                                ui_pane_render(state, "command", cols, write)
                            else:
                                # `live` MUST carry forward — the OT this
                                # resume targets was itself only offered
                                # by `_open_sandbox_circles()` from the
                                # SAME root this engine is already
                                # scoped to (its own docstring: never
                                # resume live into sandbox or vice
                                # versa). Losing `live` here would send
                                # `--resume <OT>` without `--live`,
                                # which looks for the transcript under
                                # sandbox/circles/ instead of circles/
                                # — wrong file, not just wrong mode.
                                was_live = engine.live
                                engine.stop()      # a documented no-op —
                                                   # it emits nothing, so
                                                   # draining after it
                                                   # loses nothing
                                # DRAIN THE OLD ENGINE'S QUEUE INTO THE
                                # PANES BEFORE REBINDING (tier 4 #37):
                                # the "resuming circle_<ot> —" ack and
                                # everything the old engine emitted since
                                # the last tick — its decline of the "new
                                # circle" prompt, its farewell — sat on
                                # the queue this line used to abandon.
                                # render_full below repaints both panes,
                                # so appending is the whole job.
                                try:
                                    while True:
                                        ch_, ln_ = q.get_nowait()
                                        (state.circle if ch_ == "circle"
                                         else state.command).append(ln_)
                                except queue.Empty:
                                    pass
                                extra_argv = _strip_resume(extra_argv) + ["--resume", ot]
                                engine = CircleEngine(queue.Queue())
                                engine.start(extra_argv=extra_argv, live=was_live)
                                q = engine.out_queue
                                state.backend = engine
                                ended_announced = False   # a NEW circle: the
                                # banner is owed again when this one ends
                                ui_full_render(state, cols, write)
                            reposition = False
                        if reposition:
                            ui_cursor_render(state, write, circle_prompt=circle_prompt,
                                          width=cols, command_prompt=command_prompt)
                    if not state.running:
                        break
                flush()
                time.sleep(TICK)
    except KeyboardInterrupt:
        # A raw Ctrl-C can reach Python as SIGINT rather than as the "\x03"
        # byte `handle_key` looks for, if the terminal's ISIG is still on
        # under cbreak mode. Either path must leave the screen clean.
        pass
    finally:
        write(ALT_SCREEN_OFF)          # leave raw/alt-screen mode FIRST —
        flush()                        # everything below prints plainly
        if sim is not None:
            sim.stop()
        elif engine is not None:
            ui_live_engine_wait(engine)
            engine.stop()
        print("*** harness closed ***")
    return 0


# --------------------------------------------------------------------------
# Headless self-test. No TTY required — this is what a sandbox without a
# real terminal (or a person before they trust the interactive version)
# can run to check the engine's core claim: a line landing in one pane
# never disturbs focus or the in-progress input in the other.
# --------------------------------------------------------------------------


def self_test() -> int:
    """MOVED to ui/tests/test_circling_selftest.py, 2026-09-03 (B99 stage 15; R435: a suite lives
    in tests/). This is the flag's door only: `ui/circling.py --selftest` is what the shipped
    bundle, install.py and the scaffold README say, so the flag stays and runs the file. The suite
    imports THIS module as `circling`; when this file is __main__ the alias below makes that the
    same object, so the tint it arms and the main_loop it fakes are the running program's."""
    import importlib.util
    suite = pathlib.Path(__file__).resolve().parent / "tests" / "test_circling_selftest.py"
    if not suite.is_file():
        print(f"SELF-TEST: not run — the suite is ui/tests/test_circling_selftest.py, absent here "
              f"({suite})", file=sys.stderr)
        return 2
    sys.modules.setdefault("circling", sys.modules[__name__])
    spec = importlib.util.spec_from_file_location("test_circling_selftest", suite)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.self_test()


HELP_TEXT = """usage: python ui/circling.py [--help | --selftest | --circle [ARGS...]]

  (no flags)   interactive TUI demo. Three simulated parts post random
               lines on their own timers; COMMANDS is a stub that logs
               and executes nothing. Not circle.py, no real transcript
               — see this file's own module docstring.

  --selftest   headless self-test, no TTY needed. Exercises AppState,
               Pane and CircleEngine directly (unit-level; no real
               circle.py thread is started). Run this before trusting
               an interactive session.

               A SECOND, separate self-test lives at
               ui/tests/test_circle_engine.py (its own entry point, not a
               flag here) — it runs a REAL headless dry-run
               CircleEngine session end to end and checks the CIRCLE/
               COMMAND channel each emit() call landed on:
                   python ui/tests/test_circle_engine.py

  --circle [ARGS...]
               wire the real CircleEngine/circle.py in. --dry-run is
               forced unless ARGS (or this argv) includes --live: no
               network, no API key, every part returns a canned
               statement, and every write lands under
               work/sandbox/ only. Everything AFTER --circle is
               forwarded to circle.py itself, e.g.:
                   --circle --parts <dir>,<dir> --seed 1
               --live must appear in THIS argv, not only in ARGS —
               see CircleEngine.start()'s own docstring for why.

               --recall-arm off
               is the forwarded ARG worth naming here, because it is
               the one that TURNS SOMETHING OFF:
                   --circle --live --recall-arm off
               `--recall-arm`: lets a part search its own past record,
               a local index read that costs no model call. Default:
               on. R460 (2026-09-06) closed the recall trial and made
               this a plain feature; R526
               (2026-09-10) made it on through every door, so this one
               and the Ticker now agree.

  --no-color   turn color off for this run. Default: off — color is ON
               whenever stdout is a real terminal and the NO_COLOR
               environment variable is unset (R342, D64 a:
               green prompts, red !! errors, cyan chrome).

  --dev[=true|false]
               open with dev mode ON — forwarded to circle.py's own
               --dev (R286; scope widened 2026-09-01 to also cover the
               coalesce/pre-warm/opening-round progress lines, not only
               the DEV-table verbs and the help hierarchy). Default:
               off. Works in EITHER position — before --circle (as a
               top-level flag here, like --live) or after it (as one of
               the forwarded ARGS).

  --help, -h   print this and exit.
"""


def main() -> int:
    global COLOR
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print(HELP_TEXT, end="")
        return 0
    if "--selftest" in argv:
        return self_test()
    # ARMED HERE AND NOWHERE ELSE — R342 (D64 a). The module
    # default is off, so the selftest above and every imported use render
    # plain bytes; only a real interactive run gains color, and both
    # NO_COLOR (the ecosystem convention) and --no-color turn it back off.
    COLOR = (sys.stdout.isatty() and "--no-color" not in argv
             and not os.environ.get("NO_COLOR"))
    if "--circle" in argv:
        # Opt-in real integration (docs/dual_pane_integration.md §1/§5
        # step 3) — everything after --circle is forwarded to circle.py
        # itself (e.g. --parts a,b,c). The demo path (AgentSimulator)
        # stays the unconditional default; this is the only way to reach
        # the real adapter.
        #
        # --live, RULED 2026-08-13 (Q3): must appear in THIS argv
        # (before or after --circle, either position), not after it —
        # everything after --circle is what CircleEngine.start() forwards
        # to circle.py as extra_argv, and --live/--dry-run are stripped
        # from THAT unconditionally (see start()'s own docstring) so
        # there is exactly one door. --dry-run stays the default; you
        # have to ask for --live by name.
        i = argv.index("--circle")
        # --no-color is THIS program's flag, never circle.py's — stripped
        # from the forward exactly as --live/--dry-run are in start().
        extra_argv = [a for a in argv[i + 1:] if a != "--no-color"]
        live = "--live" in argv
        # --dev, added 2026-09-01: unlike --live/--dry-run, nothing filters
        # --dev out of extra_argv, so `--circle ... --dev` already forwards
        # to circle.py on its own. This covers the OTHER position — --dev
        # typed BEFORE --circle, which start() never sees — so --dev works
        # symmetrically with --live rather than being silently dropped
        # there. Forwards whatever form was typed (--dev, --dev=true,
        # --dev=false) verbatim; circle.py's own --dev parses all three.
        dev_arg = next((a for a in argv
                        if a == "--dev" or a.startswith("--dev=")), None)
        if dev_arg and dev_arg not in extra_argv:
            extra_argv.append(dev_arg)
        engine = CircleEngine(queue.Queue())
        engine.start(extra_argv=extra_argv, live=live)
        return ui_main_loop(engine=engine, extra_argv=extra_argv)
    return ui_main_loop()


if __name__ == "__main__":
    raise SystemExit(main())
