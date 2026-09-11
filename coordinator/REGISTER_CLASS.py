#!/usr/bin/env python3
"""
REGISTER_CLASS.py — the one reader and writer for the `self/` hand-edited
(self_schema.py until 2026-09-03 — B99 stage 18b, Q-5 under R435: an entity's file is ALLCAPS_CLASS.py)
TOML registers. (All under self/ since 2026-08-16 — best_practices.toml
returned there from coordinator/ by Self's memory/ ruling.)

    self/best_practices.toml                how the CIRCLE behaves, AND
                                            "how you move" — merged
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
                                            ONE annotation; see proposal_manager.py.
                                            An issue-relationship-add-shaped
                                            row is still ADDITIVE alongside
                                            the existing proposal_unruled_show()/
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
# the file's location used to be hardcoded here AND in
# check_best_practices.py (practice_manager.py since 2026-09-03), two
# independent derivations of one path.
# SELF (below) is kept as a local name because it is genuinely read in
# this module (PROPOSALS, below); a sibling BEST alias for
# paths.BEST_PRACTICES was NOT read anywhere and was deleted 2026-09-01
# (audit-register.md #30), along with the now-unused import — import
# record_paths.BEST_PRACTICES directly if a future caller needs it.
from atomic_write import record_atomic_write
from record_paths import SELF_DIR
import record_paths as _RP

SELF = SELF_DIR
# RULED 2026-08-16 (R202): request and relation folded into ONE
# PROPOSE-class register — "P-N" ids, replacing R-N (never had a real
# row) and RP-N (same) both at once. See coordinator/proposal_manager.py.
PROPOSALS = SELF / "proposals.toml"


@_RP.group_follow
def _self_rebind() -> None:
    """The CURRENT group's self/ — B117 stage 4 (2026-09-07)."""
    global SELF, PROPOSALS
    SELF = _RP.SELF_DIR
    PROPOSALS = SELF / "proposals.toml"

WRAP = 76


def register_read(p: pathlib.Path) -> dict:
    return tomllib.loads(p.read_text(encoding="utf-8"))


def register_unwrap(s: str) -> str:
    """A hard-wrapped block back to one paragraph per blank-line group.

    Same rule as issue_schema: a single newline is soft, a blank line is a
    real break. Prose is stored wrapped so a diff is readable; it is compared
    and emitted unwrapped."""
    out = []
    for para in s.strip("\n").split("\n\n"):
        out.append(" ".join(l.strip() for l in para.splitlines() if l.strip()))
    return "\n\n".join(out)


def register_wrap(s: str, width: int = WRAP) -> str:
    import textwrap
    out = []
    for para in register_unwrap(s).split("\n\n"):
        out.append("\n".join(textwrap.wrap(para, width)) if para else "")
    return "\n" + "\n\n".join(out)


def register_now() -> str:
    """UTC, to the MICROSECOND — sorts correctly against a seconds-precision
    stamp because `.` sorts after `+`. Shared by every register that dates
    its own records; formerly duplicated in asks.py alone."""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat(
        timespec="microseconds")


def _lit(s: str) -> str:
    """A TOML basic string, or a multi-line one when it has newlines.

    NEVER re-wraps and never normalises whitespace: several of these records
    hold verbatim quotes, and four quotes in this project carry a double
    space that a tidy-up would silently remove."""
    if "\n" not in s and len(s) < 90 and '"""' not in s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    body = s.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '"""\n' + body.rstrip("\n") + '"""'


def register_dumps(doc: dict, table: str, order: tuple[str, ...]) -> str:
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
    # emits nothing at all, the reload has no `table` key, and `register_write()`
    # refuses the write — correctly, but for a case that is legitimate: a
    # register can empty out. Found 2026-08-07 when the last open ask was
    # rejected and the whole file became unwritable.
    #
    # EMITTED BEFORE `[doc]`, NOT AFTER — B35, fixed 2026-08-15. TOML has no
    # "back to root": a bare key after a table header belongs to THAT table,
    # so `table = []` written below `[doc]` reloads as doc["doc"][table] and
    # the next register_write() calls _lit() on a list and raises AttributeError. Every
    # register carrying both a [doc] preamble and zero entries hit this.
    if not doc.get(table):
        out.append(f"{table} = []")
    if doc.get("doc"):
        out.append("\n[doc]")
        for k, v in doc["doc"].items():
            # NO TRANSFORM HERE. The first version called register_wrap() on the way
            # out, so the text written back differed from the text loaded and
            # register_write()'s round-trip guard refused every write — correctly, on
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


def register_row_update(doc: dict, table: str, *, locate, fields: dict,
                        immutable: tuple[str, ...] = ("id",), precheck=None,
                        listed: "list[dict] | None" = None) -> "tuple[bool, str, dict | None]":
    """ONE row of `doc[table]` changed in place — the shared discipline every register's
    update verb follows (R465, B116, 2026-09-07), written once here rather than once per
    manager (redaction_manager.alias_update() and setting_manager were the two hand-rolled
    precedents; they agreed on every rule below).

        locate     an int — the 1-based number a listing printed, indexing `listed` (the rows
                   that listing showed; default: every row of the table) — or a str id
                   matched against the table's `id` field
        fields     the keys to replace and their new values; nothing else on the row moves
        immutable  keys that may never be in `fields` — refused, never silently kept. An id
                   names a row for its whole life (never reused, never renumbered); a kind
                   or a prefix names it at creation
        precheck   precheck(fields, row) -> "" or the refusal text; the manager's own rule
                   (a protected name, a cap, a state that forbids an update) runs before
                   anything moves

    Returns (ok, message, row). On a refusal nothing in `doc` has changed and `row` is None.
    On success `row` is the mutated row, still inside `doc`, and `message` is "" — the
    caller words its own success line and does its own save. THE SAVE STAYS WITH THE
    MANAGER, deliberately: every manager already writes through register_write() (validate,
    then atomic replace) and some carry a post-mutate hook a shared save would skip —
    practice_manager's tally, for one. What is shared is the part that was being re-invented:
    locating the row, refusing the immutable, running the precheck, touching only `fields`.

    The prior value is NOT recorded here. Git is the journal (R465): a register carries at
    most an `amended` date, which the caller passes in `fields` like any other key."""
    rows = doc.get(table, [])
    listed = rows if listed is None else listed
    if not fields:
        return False, "nothing to update", None
    bad = [k for k in fields if k in immutable]
    if bad:
        return False, (f"{', '.join(bad)} is not editable — an id names its row for life; "
                       f"delete and re-add if it was wrong"), None
    if isinstance(locate, bool) or not isinstance(locate, (int, str)):
        return False, f"locate must be a list number or an id, not {locate!r}", None
    if isinstance(locate, int):
        if not 1 <= locate <= len(listed):
            return False, f"{locate} is not in 1..{len(listed)}", None
        row = listed[locate - 1]
    else:
        row = next((r for r in rows if r.get("id") == locate), None)
        if row is None:
            return False, f"{locate} not found", None
    if precheck is not None:
        why = precheck(fields, row)
        if why:
            return False, why, None
    row.update(fields)
    return True, "", row


def register_row_nth_read(rows: list, n_text) -> "object | None":
    """The row a numbered listing printed as `n_text`, or None — not a number, or outside
    1..len(rows). The READING twin of register_row_update(..., locate=<int>) (B133): the same
    positional number, resolved against the rows that listing showed."""
    s = str(n_text).strip()
    if not s.isdecimal():
        return None
    n = int(s)
    return rows[n - 1] if 1 <= n <= len(rows) else None


def register_list_footer(count: int, verb: str) -> str:
    """The line a numbered listing ends on: its count, and how to open one row whole (B133). A
    `<n>` the listing does not name is a feature nobody finds, so every listing that takes one
    ends here."""
    return f"  {count} on file · `{verb} <n>` for one whole"


def _empty(v) -> bool:
    return v is None or (isinstance(v, (str, list, tuple, dict)) and not v)


def _scalar(v) -> str:
    return str(v).lower() if isinstance(v, bool) else str(v)


def _field_lines(d: dict, keys: list, indent: str) -> list[str]:
    """`keys` of `d` as labelled lines; a table, or an array of tables, nests one level in."""
    width = max((len(str(k)) for k in keys), default=0)
    out: list[str] = []
    for k in keys:
        v = d[k]
        if isinstance(v, dict):
            out.append(f"{indent}{k}")
            out += _field_lines(v, [x for x in v if not _empty(v[x])], indent + "   ")
        elif isinstance(v, (list, tuple)) and any(isinstance(x, dict) for x in v):
            out.append(f"{indent}{k}")
            for i, x in enumerate(v, 1):
                if isinstance(x, dict):
                    out.append(f"{indent}   {i}.")
                    out += _field_lines(x, [y for y in x if not _empty(x[y])], indent + "      ")
                else:
                    out.append(f"{indent}   {i}. {_scalar(x)}")
        elif isinstance(v, (list, tuple)):
            out.append(f"{indent}{k:<{width}}  {', '.join(_scalar(x) for x in v)}")
        elif isinstance(v, str) and "\n" in v.strip("\n"):
            out.append(f"{indent}{k}")
            out += [f"{indent}   {line}" for line in v.strip("\n").splitlines()]
        else:
            out.append(f"{indent}{k:<{width}}  {_scalar(v)}")
    return out


def register_record_show(rows: list, n: int, order: tuple = (), *, body: str = "",
                         verb: str = "") -> str:
    """ONE ROW OF A NUMBERED LISTING, WHOLE — what a `-list` verb answers when it is given one of
    its own numbers (B133; docs/BNF.md LIST_RECORD). The operator, 2026-09-09: *"remember-list accepts a
    line number and displays the full record for the selected line; I want all -list functions
    to support that same capability."*

        rows   the rows the listing numbered, in its order — `n` indexes these, not the table
        n      the 1-based number the listing printed
        order  the register's own ORDER: the keys it names come first, in that order
        body   the free-text key, where the register has one — last, unlabelled, after a blank
               line; "" when every key is a labelled field
        verb   the listing's own verb, named when `n` is out of range

    EVERY FIELD, BY CONSTRUCTION. The walk is `order`, then every key the row carries that
    `order` does not name, in the row's own order — never a hand-named tuple, so a register that
    grows a field before its show learns the name still shows the field. Absent and empty values
    are skipped; `false` and 0 are values, and shown."""
    if not rows:
        return "  nothing on file"
    if not 1 <= n <= len(rows):
        return f"  {n} is not in 1..{len(rows)}" + (f" — `{verb}` lists them" if verb else "")
    r = rows[n - 1]
    keys = [k for k in order if k in r] + [k for k in r if k not in order]
    out = [f"  {n}. of {len(rows)}"]
    out += _field_lines(r, [k for k in keys if k != body and not _empty(r[k])], "     ")
    if body:
        out.append("")
        out += [f"     {line}" for line in (str(r.get(body) or "") or "(empty)").splitlines()]
    return "\n".join(out)


def register_write(p: pathlib.Path, doc: dict, table: str,
         order: tuple[str, ...]) -> None:
    # Validate, THEN atomically commit (docs/HELP_DESIGN.md §6, built
    # 2026-08-16): the round-trip guard protects against writing text
    # that does not parse; atomic_write protects what was there before
    # against a crash mid-write. Same order §6 specified.
    text = register_dumps(doc, table, order)
    back = tomllib.loads(text)
    if back != doc:
        raise ValueError(f"{p.name}: does not round-trip — refusing to write")
    record_atomic_write(p, text)
