#!/usr/bin/env python3
"""
circle_state.py — is a circle open right now?

    python coordinator/circle_state.py       exit 0 = safe, 1 = a circle
                                             may be open
    from circle_state import is_circle_in_progress

AMENDED INTO EXISTENCE 2026-08-05. Self: *"Amend the standing caution 'do
not read circles/' in CLAUDE.md to point to a test is_circle_in_progress()
which returns true/false."*

THE PROBLEM IT REPLACES. The transcript is written statement by statement —
that is what makes it crash-safe, and it is exactly what makes a mid-circle
read a silent partial. There is no marker distinguishing one. On 2026-08-03
Claude read `circle_2026-08-03_2208.md` in flight and reported 12 statements
as the finished circle; it closed at 33. The caution that followed asked a
reader to remember. **This asks the tree instead.**

THE TEST, and it is deliberately CONSERVATIVE:

    a transcript with no close report is OPEN,
    unless it has been quiet long enough that
    no live circle could still be writing it.

Both halves are needed. The close report alone would call an aborted circle
open forever; quiet time alone would call a thinking part's pause a close. A
part can take a while to answer, so the quiet threshold is generous — the
cost of waiting is a question to Self, and the cost of being wrong is a
false record.

FAILS CLOSED. Anything it cannot determine — an unreadable directory, a
malformed name, a clock that moved — returns True. The safe answer to "may I
read this?" is no.
"""

from __future__ import annotations

import pathlib
import sys
import time

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import settings as SET                                        # noqa: E402
LIVE = ROOT / "circles"
SANDBOX = ROOT / "work" / "sandbox" / "circles"  # moved, R176, 2026-08-15
LOGS = ROOT / "work" / "logs"

# A part may think for a long time, and a Self prompt waits on a human.
# 45 minutes of silence is not a pause; under 45 minutes might be.
#
# STATED IN MINUTES because that is the unit a person setting it thinks in;
# the seconds below are derived and are what the code compares against. The
# two must never both be settable — one derived value cannot disagree with
# itself.
QUIET_MINUTES = SET.value("quiet_minutes", 45)
QUIET_SECONDS = QUIET_MINUTES * 60


def _closed(ot: str) -> bool:
    """A close report is the coordinator's own statement that it finished."""
    return (LOGS / f"close_{ot}.json").is_file()


def open_circles(now: float | None = None) -> list[dict]:
    """Every transcript that may still be being written. Empty is the good
    answer, and the caller may then read freely."""
    now = time.time() if now is None else now
    out = []
    for d in (LIVE, SANDBOX):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("circle_*.md")):
            ot = p.stem[len("circle_"):]
            try:
                quiet = now - p.stat().st_mtime
            except OSError:
                out.append({"path": p, "ot": ot, "quiet": -1,
                            "why": "cannot stat — failing closed"})
                continue
            if _closed(ot):
                continue                      # the coordinator said it closed
            if quiet >= QUIET_SECONDS:
                continue                      # abandoned or pre-report era
            out.append({"path": p, "ot": ot, "quiet": quiet,
                        "why": f"no close report and last written "
                               f"{max(0, quiet) / 60:.0f} min ago"})
    return out


def is_circle_in_progress() -> bool:
    """True if reading `circles/` might catch a partial. FAILS CLOSED."""
    try:
        return bool(open_circles())
    except Exception:                                        # noqa: BLE001
        return True


def main() -> int:
    try:
        found = open_circles()
    except Exception as e:                                   # noqa: BLE001
        print(f"  COULD NOT TELL — {e}\n  Treat this as a circle in "
              f"progress. Ask Self.")
        return 1
    if not found:
        n = len(list(LIVE.glob("circle_*.md"))) + len(list(SANDBOX.glob("circle_*.md")))
        print(f"  NO CIRCLE IN PROGRESS — {n} transcript(s), all with a "
              f"close report or long quiet.\n  Safe to read.")
        return 0
    print(f"  {len(found)} CIRCLE(S) MAY BE OPEN — do not read, ask Self:")
    for f in found:
        print(f"    {f['path'].relative_to(ROOT)}\n      {f['why']}")
    # B56(3), 2026-08-19: IN A LAB TREE THIS ANSWER IS ALWAYS WRONG, and the
    # verdict is still right to give. Checkout stamps every transcript with
    # the checkout time, so a fresh worktree reports its whole corpus open for
    # 45 minutes. This check FAILS CLOSED, correctly — quiet is the only
    # evidence it has — so the fix is not to soften the verdict but to stop it
    # reading as a mystery. Says WHY, and names the repair.
    # THE TEST IS `.git` AS A FILE, NOT "not a directory". A worktree's
    # `.git` is the `gitdir:` pointer FILE, which is the signature this
    # note is about. `in_main_checkout()` answers is_dir(), and its
    # negation is true of a THIRD case it was never meant to name: a tree
    # with no `.git` at all — which is what a distributed bundle is, and
    # what a Download-ZIP copy is. Those got told they were a worktree and
    # pointed at .claude/skills/run-inner-circling/driver.py, a path that
    # does not ship. Narrowed 2026-08-24, with the tools the note names
    # made conditional on being in a tree that HAS them.
    try:
        if (ROOT / ".git").is_file():
            print("\n    NOTE: this is a WORKTREE. Checkout stamps every "
                  "transcript with the\n    checkout time, so a fresh one "
                  "reports its whole corpus open until\n    those mtimes age "
                  "past 45 minutes. Age them now with:\n"
                  "      .venv/Scripts/python.exe "
                  ".claude/skills/run-inner-circling/driver.py age-transcripts")
    except Exception:
        pass          # a note is never worth failing this check over
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
