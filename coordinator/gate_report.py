#!/usr/bin/env python3
"""
gate_report.py — a check refused; write down what happened, in two registers.

    python coordinator/gate_report.py --code 1 --out <captured> -- <script> [args]

Called by the pre-commit hook's `run`/`quiet` when a check exits non-zero,
BEFORE the hook itself exits. Writes `work/diagnostics/gate_<time>.md` and
prints, to the screen, the plain-language half.

WHY IT EXISTS. Ruled by the operator 2026-08-26. A check refusing is the moment
a person is most stuck and least able to ask anyone: the checkers name their own
repair, but they name it to a developer — *"NOT-FIXED-POINT: does not re-render
byte-identically"* is a diagnosis, and not one this program's reader can act on.
So the technical account goes to a file, and the screen gets ordinary language.

AND THE FILE CARRIES A PROMPT THE PERSON CAN SEND. Not the program sending it —
the person, by hand, after reading it, having deleted anything they would rather
not share. That is the whole design: this project's material is private, so the
disclosure decision is never the program's to make. Nothing here opens a socket.

WHAT THE PROMPT BLOCK CARRIES, and it is a short list on purpose: the check that
refused and its verbatim output, which files were being saved, and the shape of
this installation. NOT the user's name, not a circle's words, not the contents of
any record. If a diagnosis needs one of those, the block tells Claude to ask for
that ONE thing — which is a better disclosure than shipping it all up front,
because by then the person can see what it is for.

STDLIB ONLY, AND IT PARSES NOTHING OF THE USER'S. It is called when the tree may
be damaged — a corrupted TOML is one of the things that brings it here — so a
writer that read a register to describe it could fail in exactly the case it
exists for. It reads the checker's output, the staged path list from git, and a
VERSION file if the packager left one.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import platform
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "work" / "diagnostics"
ISSUES_URL = "https://github.com/Inner-Circler/Inner-Circling/issues"

# WHAT EACH CHECK MEANS, TO A PERSON. The checkers speak to a developer; this is
# the same fact in ordinary language, and it is the only place in this program
# that translation lives. A check with no entry gets the fallback below rather
# than a stack of jargon — and `test_gate_report.py` asserts that every check the
# hook invokes AND ships has an entry here, so a new gate cannot arrive without
# its sentence.
PLAIN: dict[str, str] = {
    "coordinator/practice_verify.py":
        "One of your saved practices didn't read back the way it was written.",
    "coordinator/record_verify.py":
        "A file the program needs looks damaged.",
    "coordinator/file_line_endings_verify.py":
        "A file was saved in a format the rest of the program can't read.",
    "coordinator/circle_audit.py":
        "The program's check of your own records didn't pass.",
    "coordinator/prompt_capture.py":
        "The record of what was sent to the parts didn't match what was kept.",
    "memory/issue_gate.py":
        "The record of what you're working on didn't pass its own check.",
    "memory/issue_prompt_projection.py":
        "What the next circle would be shown couldn't be prepared.",
    # keyed "ui/circling.py" until 2026-09-03: the hook ran `--selftest`; it runs the file now
    "ui/tests/test_circling_selftest.py":
        "The two-pane circle UI's own self-check didn't pass.",   # "window" was ambiguous (R443)
    # v112 (2026-09-02) wired six more checks into the hook without a sentence
    # each; test_gate_report refused every commit touching this file or the
    # hook until 2026-09-03, when stage 7b of the cohesion re-homing met it.
    "coordinator/system_unique_home_verify.py":
        "The same fact is written down in two places in the program, and they could drift apart.",
    "coordinator/system_layer_verify.py":
        "A lower part of the program has started depending on a higher one.",
    "coordinator/system_name_verify.py":
        "A new function was named without saying what kind of thing it works on.",
    "coordinator/system_setting_verify.py":
        "The settings file and the program disagree about which settings exist.",
    "ui/palette.py":
        "The program's list of colours didn't pass its own check.",
    ".claude/skills/install-package/test_install.py":
        "The installer's own rehearsal didn't pass.",
    ".claude/skills/my_commit/test_my_commit.py":
        "The safe-to-save check's own rehearsal didn't pass.",
    ".claude/skills/publish-package/test_publish.py":
        "The publisher's own rehearsal didn't pass.",
}
FALLBACK = "A check called {name} stopped."


def system_gate_plain_read(script: str) -> str:
    return PLAIN.get(script, FALLBACK.format(name=pathlib.PurePath(script).name))


def _git(*args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                           timeout=20)
        return p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else ""
    except Exception:                                        # noqa: BLE001
        return ""


def system_gate_version_read() -> str:
    """What code this is. A delivered copy carries `VERSION`, stamped by the
    packager; a checkout answers with its own commit. Neither is required — an
    unknown version is reported as unknown rather than guessed, because the
    whole point of the line is that an issue report can name what ran."""
    f = ROOT / "VERSION"
    if f.is_file():
        try:
            first = f.read_text(encoding="utf-8", errors="replace").strip()
            if first:
                return first.splitlines()[0]
        except OSError:
            pass
    sha = _git("rev-parse", "--short", "HEAD")
    return f"checkout {sha}" if sha else "unknown"


def system_gate_shape_read() -> str:
    """How much of the program is here. A delivered package ships the product
    and not the probes, so "6 of 72" is the difference between a bundle and a
    development tree — and it is the first thing worth knowing about a failure
    report from someone else's machine."""
    try:
        import gitrepo                                       # noqa: PLC0415
        named = sorted({ln.split()[1] for ln in gitrepo.PRE_COMMIT.splitlines()
                        if ln.strip().startswith(("run ", "quiet "))
                        and len(ln.split()) > 1})
    except Exception:                                        # noqa: BLE001
        return "unknown"
    here = sum(1 for n in named if (ROOT / n).is_file())
    kind = ("a distributed package, not a development tree"
            if here < len(named) else "a development tree")
    return f"{here} of {len(named)} checks present  ({kind})"


def system_gate_staged_read() -> list[str]:
    out = _git("diff", "--cached", "--name-only", "--diff-filter=d")
    return [ln for ln in out.splitlines() if ln.strip()]


def system_gate_scrub(text: str) -> str:
    """Take this machine out of the checker's own words.

    CAUGHT BY READING A REAL ONE, 2026-08-26. The file promises the block does
    not contain the reader's name — and the first report written in a real
    bundle opened with `project: C:\\Users\\<name>\\...`, because a checker
    prints the path it is working in and a home directory is very often a
    person's name. A promise the program does not keep is worse than no
    promise, so the two paths that carry identity are replaced before the
    output is written down.

    Longest first: the project folder usually sits INSIDE the home directory,
    and replacing the home first would leave a half-substituted path."""
    home = str(pathlib.Path.home())
    for real, stand_in in ((str(ROOT), "<the project folder>"),
                           (home, "~")):
        for form in (real, real.replace("\\", "/"), real.replace("\\", "\\\\")):
            if form:
                text = text.replace(form, stand_in)
    return text


def system_gate_block_render(script: str, code: int, output: str) -> str:
    """The part the person may send. Written to be read by a Claude with NO
    knowledge of this project — which is why it opens by saying what the program
    is, and why it says how to speak back before it says what went wrong."""
    files = "\n".join(f"    {p}" for p in system_gate_staged_read()) or "    (nothing staged)"
    body = "\n".join(f"    {ln}" for ln in system_gate_scrub(output).strip().splitlines()) \
        or "    (the check printed nothing)"
    return f"""You are helping someone use Inner Circling, a private journaling tool that runs
on their own computer. It keeps their writing as plain text files in a git
repository, and runs a set of checks before saving anything into that history.
One of those checks refused, so the save did not happen.

The person you are talking to is NOT a programmer. Use ordinary language. Do not
name functions, modules or code paths at them. If you need to see something, ask
for ONE thing at a time and say exactly how to get it — for example: "open this
file in Notepad and copy me the last four lines."

If you can name the fix, give it as steps they can follow. Say nothing about how
it happened that sounds like fault.

If you cannot get there in two or three exchanges, say so plainly and point them
to {ISSUES_URL}, telling them to
include the check that stopped, what it printed, and the version line below.

--- the check that stopped -------------------------------------------
check:      {script}
exit code:  {code}
its output, verbatim:
{body}
--- what was being saved ---------------------------------------------
{files}
--- this installation ------------------------------------------------
    Inner Circling {system_gate_version_read()}
    python {platform.python_version()}  ·  {platform.system()}
    {system_gate_shape_read()}
"""


def system_gate_report(script: str, code: int, output: str) -> pathlib.Path:
    now = datetime.datetime.now()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / f"gate_{now:%Y-%m-%d_%H%M%S}.md"
    text = f"""# A check didn't pass — {now:%d %B %Y, %H:%M}

## What happened

{system_gate_plain_read(script)}

Nothing you wrote is lost — it is all still on your computer. What did not
happen is the automatic copy into the project's own history.

## If you would like help

Send the block below to Claude and ask what to do. Read it first, and delete
anything you would rather not share — it is yours, and hand-editing it is fine.

## What the block contains

  · the name of the check that stopped, and exactly what it printed
  · which files were being saved
  · your Python version, your system, and how much of the program you have

## What it does not contain

  · your name
  · anything you or the parts said in a circle
  · the contents of your own records

If Claude needs one of those to help, it will ask you for that one thing.

## The block to send — everything between the lines

----------------------------------------------------------------------
{system_gate_block_render(script, code, output)}----------------------------------------------------------------------
"""
    p.write_text(text, encoding="utf-8", newline="")
    return p


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--code", type=int, required=True)
    ap.add_argument("--out", required=True,
                    help="file holding the check's captured output")
    ap.add_argument("script", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    script = " ".join(x for x in a.script if x != "--").strip() or "(unnamed)"
    name = script.split(" ", 1)[0]
    try:
        captured = pathlib.Path(a.out).read_text(encoding="utf-8", errors="replace")
    except OSError:
        captured = ""
    # NEVER RAISE FROM HERE. This runs while a commit is already failing; a
    # traceback on top of that buries the checker's own message and teaches the
    # reader that the program broke, which is not what happened.
    try:
        p = system_gate_report(name, a.code, captured)
    except Exception as e:                                   # noqa: BLE001
        print(f"\n  (a check didn't pass, and the note about it could not be "
              f"written: {e})")
        return 0
    print("\n  Something didn't pass a check, so this wasn't saved to the "
          "project's history.")
    print("  Nothing you wrote is lost — it is all still on your computer.")
    print("\n  What happened, and a message you can send to Claude if you would "
          "like help, is in:")
    print(f"      {p.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
