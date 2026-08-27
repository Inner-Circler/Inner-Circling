#!/usr/bin/env python3
"""
self_schema.py — the one reader and writer for the `self/` hand-edited
TOML registers. (All under self/ since 2026-08-16 — best_practices.toml
returned there from coordinator/ by Self's memory/ ruling.)

    self/best_practices.toml                how the CIRCLE behaves, AND how
                                            THE OPERATOR moves — merged
                                            2026-08-11 (R133); the operator's
                                            addressee is "Self"
    self/proposals.toml               P-#   a PART's [proposed: <command>] annotation,
                                            staged for Self to approve/deny/
                                            defer — PROPOSE-class. R202,
                                            2026-08-16, replaces self/
                                            requests.toml (R-#, 2026-08-12)
                                            and self/relation_proposals.toml
                                            (RP-#, 2026-08-13, #32) at once —
                                            request and relation folded into
                                            ONE marker; see proposals.py.
                                            An issue-relationship-add-shaped
                                            row is still ADDITIVE alongside
                                            the existing show_unruled_proposals()/
                                            `/issue-relationship-add`
                                            path, not a
                                            replacement for it. Carried to
                                            the next circle's priming same as
                                            practice.

self/marks/<OT>.toml and self/mark_proposals.toml (MARK, and PROPOSE MARK
with it) are GONE — RETIRED WHOLESALE 2026-08-14, code included
(docs/BNF.md). The old marks/ records are in git, at the paths above;
`git log --all -- self/marks/` finds them.

RULED 2026-08-05, after the .md survey. These four were the last hand-edited
structured records outside `parts/`, and each had its own regex parser:

    check_best_practices  ^\\*\\*(Addressee)\\*\\*
    check_better_options  ^## (\\d+)\\. (.+)$
    marks                 ^## (\\d+)\\. (.+?) — \\*\\*([a-z]+)\\*\\*
    concerns              ^### (OC-(\\d+))\\s*·\\s*(.+?)$

Four expressions, four chances to half-match. `project_stats.py` re-derived
two of these counts on the day it was written and got **23 and 0** where the
owners say **17 and 11** — and `concerns.py`'s own parser swallowed a `##
Resolved` heading and turned every resolved concern back into an open one.
Both defects are unwritable in TOML: an array of tables is present or the
file does not load.

WHAT THE FORMAT DOES NOT FIX. Everything these files claim about the world —
that a quote is verbatim, that a projection reached the briefing, that a tally
matches — is still checked by the same verifiers, which now read parsed data
instead of re-parsing prose.

THE PREAMBLE IS KEPT, in `[doc] preamble`. Each of these files opens with
real prose — what a place in it costs, what synthesis may and may not do with
it — and that prose is Self's and mine to read, not decoration. Dropping it
in a format migration would be exactly the "burst the content and lose its
reasoning" failure this project keeps finding.
"""

from __future__ import annotations

import pathlib

try:
    import tomllib
except ModuleNotFoundError:                                  # 3.10 and older
    import tomli as tomllib                                  # type: ignore


# Path constants come from paths.py since 2026-08-16 (phase 1 step 0) —
# BEST was hardcoded here AND in check_best_practices.py, two
# independent derivations of one file's location. The local names are
# kept: they are this module's public surface.
from atomic_write import atomic_write
from paths import SELF_DIR, BEST_PRACTICES

SELF = SELF_DIR
BEST = BEST_PRACTICES
# RULED 2026-08-16 (R202): request and relation folded into ONE
# PROPOSE-class register — "P-N" ids, replacing R-N (never had a real
# row) and RP-N (same) both at once. See coordinator/proposals.py.
PROPOSALS = SELF / "proposals.toml"

WRAP = 76


def load(p: pathlib.Path) -> dict:
    return tomllib.loads(p.read_text(encoding="utf-8"))


def unwrap(s: str) -> str:
    """A hard-wrapped block back to one paragraph per blank-line group.

    Same rule as issue_schema: a single newline is soft, a blank line is a
    real break. Prose is stored wrapped so a diff is readable; it is compared
    and emitted unwrapped."""
    out = []
    for para in s.strip("\n").split("\n\n"):
        out.append(" ".join(l.strip() for l in para.splitlines() if l.strip()))
    return "\n\n".join(out)


def wrap(s: str, width: int = WRAP) -> str:
    import textwrap
    out = []
    for para in unwrap(s).split("\n\n"):
        out.append("\n".join(textwrap.wrap(para, width)) if para else "")
    return "\n" + "\n\n".join(out)


def now() -> str:
    """UTC, to the MICROSECOND — sorts correctly against a seconds-precision
    stamp because `.` sorts after `+`. Shared by every register that dates
    its own records; formerly duplicated in asks.py alone."""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat(
        timespec="microseconds")


def wrapn(s: str, n: int) -> list[str]:
    """`s` wrapped to `n` columns, as a list of lines — the 58-hard-wrap
    convention every register's `listing()` uses beneath a label."""
    import textwrap
    return textwrap.wrap(s, n) or [""]


def _lit(s: str) -> str:
    """A TOML basic string, or a multi-line one when it has newlines.

    NEVER re-wraps and never normalises whitespace: several of these records
    hold verbatim quotes, and four quotes in this project carry a double
    space that a tidy-up would silently remove."""
    if "\n" not in s and len(s) < 90 and '"""' not in s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    body = s.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '"""\n' + body.rstrip("\n") + '"""'


def dumps(doc: dict, table: str, order: tuple[str, ...]) -> str:
    """Render deterministically: scalars, then `[doc]`, then the entries.

    Written by hand rather than by tomli_w so multi-line prose stays readable
    as prose. tomli_w escapes every newline into one long line, which is the
    thing that made JSON unusable here (R062)."""
    out = []
    for k, v in doc.items():
        if k in (table, "doc"):
            continue
        if isinstance(v, bool):
            rendered = str(v).lower()
        elif isinstance(v, str):
            rendered = _lit(v)
        else:
            rendered = str(v)
        out.append(f"{k} = {rendered}")
    # AN EMPTY REGISTER MUST STILL ROUND-TRIP. With no entries, `[[table]]`
    # emits nothing at all, the reload has no `table` key, and `save()`
    # refuses the write — correctly, but for a case that is legitimate: a
    # register can empty out. Found 2026-08-07 when the last open ask was
    # rejected and the whole file became unwritable.
    #
    # EMITTED BEFORE `[doc]`, NOT AFTER — B35, fixed 2026-08-15. TOML has no
    # "back to root": a bare key after a table header belongs to THAT table,
    # so `table = []` written below `[doc]` reloads as doc["doc"][table] and
    # the next save() calls _lit() on a list and raises AttributeError. Every
    # register carrying both a [doc] preamble and zero entries hit this.
    if not doc.get(table):
        out.append(f"{table} = []")
    if doc.get("doc"):
        out.append("\n[doc]")
        for k, v in doc["doc"].items():
            # NO TRANSFORM HERE. The first version called wrap() on the way
            # out, so the text written back differed from the text loaded and
            # save()'s round-trip guard refused every write — correctly, on
            # its first run. Wrapping is the CONVERTER's job, done once; a
            # writer that reformats cannot be idempotent.
            out.append(f"{k} = {_lit(v)}")
    for e in doc.get(table, []):
        out.append(f"\n[[{table}]]")
        for k in order:
            if k not in e:
                continue
            v = e[k]
            if isinstance(v, list):
                out.append(f"{k} = [")
                out += [f'    {_lit(x)},' for x in v]
                out.append("]")
            elif isinstance(v, bool):
                out.append(f"{k} = {str(v).lower()}")
            elif isinstance(v, int):
                out.append(f"{k} = {v}")
            else:
                out.append(f"{k} = {_lit(v)}")
        for k in e:
            if k not in order:
                raise ValueError(f"[[{table}]] has unknown key {k!r}")
    return "\n".join(out).strip() + "\n"


def save(p: pathlib.Path, doc: dict, table: str,
         order: tuple[str, ...]) -> None:
    # Validate, THEN atomically commit (docs/HELP_DESIGN.md §6, built
    # 2026-08-16): the round-trip guard protects against writing text
    # that does not parse; atomic_write protects what was there before
    # against a crash mid-write. Same order §6 specified.
    text = dumps(doc, table, order)
    back = tomllib.loads(text)
    if back != doc:
        raise ValueError(f"{p.name}: does not round-trip — refusing to write")
    atomic_write(p, text)
