#!/usr/bin/env python3
"""
help_system.py — /help's whole surface: the hot-reloaded object-class
table, the issue/issue-relationship read-outs behind `help <class> ...`, the
dev-tiered level 0, help_text and its cmd_help door, and the
dev-restricted refusal text. Phase 2 stage 5 of the coordinator
partitioning (2026-08-16; built fourth — dispatch_dev_cmd imports
cmd_help, so help precedes the commands stage, exactly the dependency
the phase-2 plan recorded). Until then all of it lived in circle.py.
Verbatim move — bodies and comments unchanged, except console output
goes through `seam.emit` by attribute access.

Reads COMMANDS/KNOWN_CMDS and the dev_mode flag from
command_surface.py (DEV_MIN_CMDS is named in prose here and nowhere read) — stage 0's cycle-breaker is what lets the /help
renderer and the dispatcher that calls it live in separate modules
without either importing the other.

ONE ROW SHAPE, 2026-08-21 (the lab findings of that day, S5/S6). Every
verb /help prints — level 0 in either tier, a class's own verbs at level
2, the dual pane's local verbs — goes through `command_help_row_render()`: the full
command spec, an em-dash, the WHOLE description joined to one line, the
row wrapped at HELP_WIDTH with an 8-space hanging indent, and the rows
sorted by verb. Until then level 0 printed the first LINE of a
description with dev off ("attach a PRIOR statement (its number from")
and the verb-then-indented-lines shape with dev on, in table order; and
`/help <class>` printed a SECOND verb table from object_classes.toml that
had drifted to the pre-R261 spelling ("issue status nNNNN"). The class
verbs are DERIVED from COMMANDS now — see `_class_of_head`.
"""

from __future__ import annotations

import pathlib
import re
import textwrap

try:                                          # 3.11+
    import tomllib
except ModuleNotFoundError:                   # 3.7+, the identical parser
    import tomli as tomllib                   # type: ignore

import command_surface as CS       # dev_mode is REBOUND — attribute access
import issue_commands as IC        # the issue read-outs' renderer
import issue_schema as S_
import seam
from command_surface import COMMANDS

HERE = pathlib.Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Help plumbing — docs/dual_pane_integration.md §4, RULED 2026-08-10.
# HOT-RELOADED: every help* call re-stats the table file and reparses only
# if (mtime, size) changed since the last read. No polling, no background
# watcher — the check only runs when a help command actually does.
# `object_classes.toml` uses this for `help object_classes`/`help <class>`;
# its CONTENT is deliberately empty — RULED 2026-08-10: "remains
# forthcoming work that will be undertaken depth-first" (issue complete
# before relationship is begun) — this is the reload mechanism and table
# shape, not the content. MARK_KINDS/MARK_HELP, the mechanism's original
# motivating case, were retired wholesale along with MARK, 2026-08-14
# (docs/BNF.md) — this mechanism now serves object_classes alone.
#
# WHAT THE TABLE HOLDS SHRANK, 2026-08-21: a class's NAME and DESCRIPTION
# only. The `[[class.verb]]` rows it carried from B40 (2026-08-13) were a
# second spelling of COMMANDS and drifted — they still read `issue status
# nNNNN [= <value>]` eight days after R261 made the verb `/issue-status`.
# A class's verbs are derived from COMMANDS by head prefix now
# (`_class_of_head`), and the two productions every class shares — `list`
# and `read #` — are constants below, not TOML.
# --------------------------------------------------------------------------

OBJECT_CLASSES_PATH = HERE / "object_classes.toml"


def _hot_load(path: pathlib.Path, cache: dict, parse) -> object:
    st = path.stat()
    key = (st.st_mtime_ns, st.st_size)
    if cache.get("stat") != key:
        with open(path, "rb") as f:
            doc = tomllib.load(f)
        cache["stat"] = key
        cache["data"] = parse(doc)
    return cache["data"]


def _parse_object_classes(doc: dict) -> dict:
    return {c["name"]: c for c in doc.get("class", [])}


_object_classes_cache: dict = {}


def object_classes() -> dict:
    return _hot_load(OBJECT_CLASSES_PATH, _object_classes_cache, _parse_object_classes)


# ---------------------------------------------------------------- the row
HELP_WIDTH = 80
ROW_HANG = 8          # a wrapped row's continuation indent — the operator, 2026-08-21:
                      # "Indent wrapped help following the first line"


def command_help_row_render(spec: str, desc: str = "", pad: int = 0) -> str:
    """ONE help row: `  <spec>  —  <description>`, wrapped to HELP_WIDTH with
    an ROW_HANG-space hanging indent — 2026-08-21 (lab findings, S5).

    THE DESCRIPTION IS JOINED TO ONE LINE FIRST. COMMANDS' descriptions are
    hard-wrapped at ~50 columns for the layout this replaced; a TOML
    `'''...'''` description may be hard-wrapped for editing. Either way a
    single newline is soft here (issue_schema.issue_unwrap()'s rule for node
    prose, applied to help), so the row is re-flowed to THIS width rather
    than carrying a wrap made for another one. Nothing is truncated: the
    2026-08-20 one-liner tier printed only a description's first line, and
    the operator read "attach a PRIOR statement (its number from" as a bug — it
    was.

    THE SPEC IS NEVER BROKEN. Its internal spaces are protected (NBSP,
    which textwrap does not treat as breakable) for the wrap and restored
    after, so `/issue-status nNNNN [= <value>]` always sits whole at the
    start of its row and the description is what wraps. A spec wider than
    the room overflows its own line rather than being cut (break_long_words
    is off for the same reason).

    PUBLIC ON PURPOSE: ui/circling.py's own-verb block (`quit`, `abort`,
    `resume`, `status`, `help`) renders through this too, so the pane's
    verbs and the circle's read as one listing.

    `pad` ALIGNS A LISTING'S COLUMN — the operator, 2026-08-25: *"pad the
    left column to align the hyphens and line breaks (for all helps)"*. The
    spec is padded to `pad` visible characters (NBSP, so the wrap cannot
    break inside the padding) and a wrapped row's continuation indents to
    the DESCRIPTION column rather than ROW_HANG, so every hyphen and every
    continuation in one listing sits on the same column. command_help_rows_render() below
    computes the pad for a group; a bare help_row keeps the old shape."""
    one = " ".join(desc.split())
    safe_spec = spec.replace(" ", "\xa0")
    if pad > len(spec):
        safe_spec += "\xa0" * (pad - len(spec))
    hang = " " * (2 + pad + 5) if pad else " " * ROW_HANG
    text = f"{safe_spec}  —  {one}" if one else safe_spec
    lines = textwrap.wrap(text, width=HELP_WIDTH, initial_indent="  ",
                          subsequent_indent=hang,
                          break_long_words=False, break_on_hyphens=False)
    return "\n".join(lines).replace("\xa0", " ") if lines else "  " + spec


# THE COLUMN STOPS AT 33 so a wide group cannot starve its own text: the
# description column is 2 + pad + 5, and an uncapped pad (the widest spec in
# `issue-relationship`'s group is 60+ characters) put continuations at column
# 71 of an 80-column page — every word wider than nine columns overflowed. A
# spec longer than the cap keeps its separator immediately after itself,
# unaligned, and its description wraps to the group's column like every
# other row's — the classic definition-list shape.
PAD_MAX = 33


def command_help_pad(pairs) -> int:
    """The column ONE listing aligns on: its widest spec, capped at PAD_MAX.

    SEPARATE FROM command_help_rows_render() SINCE 2026-08-25, because a PANE is not
    always one listing. `/help issue` prints its own verbs, then a child
    class, then that child's verbs — three groups, and a pad per group put
    three different hyphen columns and three different continuation
    indents on one page. The operator: *"align the left edge and hyphen
    description of all detailed help panes."* A caller that renders several
    groups computes the pad ACROSS ALL OF THEM once, here, and passes it
    down."""
    return min(max((len(s) for s, _ in pairs), default=0), PAD_MAX)


def command_help_rows_render(pairs, pad: int | None = None) -> list[str]:
    """One LISTING of (spec, description) rows, the column aligned across
    the group — each row through command_help_row_render() with the group's own pad, which
    is its widest spec, capped at PAD_MAX. The pad is computed here and
    nowhere else, so a listing cannot half-align.

    `pad`, when given, is a WIDER page's column — see command_help_pad()."""
    pairs = list(pairs)
    return [command_help_row_render(s, d, command_help_pad(pairs) if pad is None else pad)
            for s, d in pairs]


def _head(spec: str) -> str:
    return spec.split(" ", 1)[0]


def _command_specs() -> dict[str, tuple[str, str]]:
    """head -> (spec, description), first row per head, from COMMANDS.
    Re-read on every call — COMMANDS is a constant, but reading it here
    rather than at import keeps this module's view identical to the
    dispatcher's, including under a test that swaps it."""
    out: dict[str, tuple[str, str]] = {}
    for spec, desc, _pane in COMMANDS:
        if spec.startswith("/"):
            out.setdefault(_head(spec), (spec, desc))
    return out


def _gloss(head: str, specs: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """(spec, description) for one verb at level 0. The hand-written
    one-liner wins where one exists — the four it still covers are the room's
    three verbs and /help, whose COMMANDS text is written relative to the
    table's own order ("/pass (below)", "/round, above") and reads wrong once
    the rows are sorted. Everything else is the COMMANDS description, whole.
    A head in neither says so rather than raising: a KeyError inside /help
    would take the whole listing down over one missing gloss."""
    spec, desc = specs.get(head, (head, ""))
    if head in _HELP_ONE_LINERS:
        return spec, _HELP_ONE_LINERS[head]
    return spec, desc or "(no description)"


def _verb_pairs(heads, specs: dict[str, tuple[str, str]]) -> list[tuple[str, str]]:
    """(spec, description) per head, SORTED by head — the operator,
    2026-08-21: "order output lines alphabetically". Duplicates collapse (a
    head may be named twice between the circle-pane three and a table).

    SPLIT OUT FROM _verb_rows 2026-08-25 so a pane can measure every group
    it is about to print before printing any of them — see command_help_pad()."""
    return [_gloss(h, specs) for h in sorted(dict.fromkeys(heads))]


# _verb_rows() (rendered _verb_pairs() output) DELETED 2026-09-01 --
# audit-register.md #30 found it a zero-reference symbol: nothing called
# it after the 2026-08-25 split, only comments named it.

# THE SPEECH ROW IS GONE, 2026-08-21 (R285). COMMANDS
# carried a `<text>` row — "speak as <name>" — and level 0 printed it first,
# unsorted. The operator: "<text> ::= <circle_dialog> | <command_text> ... The
# list you have are commands, remove <text> from the list." At cmd> typing
# speech is JUNK and is answered with this listing; the room's own help
# (circle_pane_help) is where "you speak" is said.


# ------------------------------------------------------- class derivation
def _class_of_head(head: str, classes) -> str | None:
    """Which object class a COMMAND head belongs to — the LONGEST class name
    that is the head's prefix, so `/issue-relationship-add` is
    issue-relationship and every other `/issue-*` is issue. A head no class
    name prefixes (practices, topics, /status) belongs to none. This is the
    derivation that replaced object_classes.toml's own verb rows,
    2026-08-21: one spelling of a verb, in COMMANDS, and the help hierarchy
    reads it rather than restating it."""
    best = None
    for cname in classes:
        if head == f"/{cname}" or head.startswith(f"/{cname}-"):
            if best is None or len(cname) > len(best):
                best = cname
    return best


def _parent_of(cls: str, classes) -> str | None:
    """The longest OTHER declared class name that prefixes this one.

    DERIVED, NOT DECLARED — a class whose name is prefixed by another class
    name is that class's child. `issue-evidence` and `issue-relationship`
    are children of `issue`; `part-context` of `part`; `better-option` has
    no parent, because there is no class `better`. Nothing to keep in sync,
    and the same longest-match rule _class_of_head already uses.

    R336, 2026-08-24. The prototype's first cut made every class top-level,
    so level 0 listed `issue`, `issue-evidence` and `issue-relationship` as
    three peers — three rows for one subject, which is the flattening this
    model exists to undo, reintroduced one level up. The operator caught it
    by reading the output."""
    best = None
    for other in classes:
        if other != cls and cls.startswith(f"{other}-"):
            if best is None or len(other) > len(best):
                best = other
    return best


def _children_of(cls: str, classes) -> list[str]:
    return sorted(c for c in classes if _parent_of(c, classes) == cls)


def _root_classes(classes) -> list[str]:
    return sorted(c for c in classes if _parent_of(c, classes) is None)


def _subtree(cls: str, classes) -> list[str]:
    """A class and every class beneath it — what `/help <class>` covers."""
    out = [cls]
    for child in _children_of(cls, classes):
        out += _subtree(child, classes)
    return out


def _class_verb_rows(name: str) -> list[str]:
    """The class's COMMANDS, sorted, each a full command_help_row_render(). A DEV-table verb
    (/issue-apply rides `issue` by name) prints only while dev is on — read
    from the tables as module attributes, never a copied set."""
    classes = object_classes()
    specs = _command_specs()
    return command_help_rows_render(specs[head] for head in sorted(specs)
                     if _class_of_head(head, classes) == name
                     and not (head in CS.DEV_SUBSET_COMMANDS
                              and not CS.dev_mode))


# The two productions EVERY populated class prints at level 2 — levels 3 and
# 4 of docs/HELP_DESIGN.md §2, R160. Constants here, not rows in the TOML:
# they are the same for every class, and the TOML's copies were the rows
# that drifted.
LEVEL_ROWS: tuple[tuple[str, str], ...] = (
    ("list", "a numbered list of the live entries — id and human key, "
             "re-derived fresh on every call, never cached"),
    ("read #", "the full record at list position # — the position as `list` "
               "would print it RIGHT NOW, not a stored id — then this listing"),
)


def object_class_help_text(name: str = "") -> str:
    """Level 1 (`name == ""`): every class as `/help <class>  —  <description>`.
    Level 2 (`name`): the class's description, its `/help <class> list` and
    `/help <class> read #` rows, then its COMMANDS — each level advertising
    the next, the operator 2026-08-21. Both hot-reloaded from object_classes.toml;
    the verbs come from COMMANDS (see `_class_of_head`)."""
    classes = object_classes()
    if not name:
        if not classes:
            # NO PATH IN THE MESSAGE — audit-register.md #30, 2026-09-08. This ended "See
            # docs/dual_pane_integration.md §4." and help_system.py SHIPS
            # (packaging/required.toml), while docs/ is in packaging/ignore.txt and the
            # bundle's docs/ holds only overview.md. So a recipient reaching this line was
            # sent to a file their install does not contain — a shipping gap, not a dangling
            # reference: the document is real and present in the source tree. Naming the
            # ruling is what a reader here can actually use.
            return ("  no object classes populated yet — content is "
                    "deliberately deferred (RULED 2026-08-10, undertaken "
                    "depth-first when this work starts).")
        out = ["  OBJECT CLASSES"] + command_help_rows_render(
            (f"/help {cname}", c.get("description", ""))
            for cname, c in classes.items())
        return "\n".join(out)
    c = classes.get(name)
    if c is None:
        known = ", ".join(classes) or "(none populated yet)"
        return f"  unknown object class {name!r} — known: {known}"
    out = [f"  {name}"]
    if c.get("description"):
        # A TOML `'''...'''` description may be hard-wrapped for editing —
        # a single newline is soft, same rule issue_schema.issue_unwrap() uses
        # for node prose. Collapse it back to one line for display.
        out.append(f"      {' '.join(c['description'].split())}")
    out += command_help_rows_render((f"/help {name} {sub}", desc)
                     for sub, desc in LEVEL_ROWS)
    out += _class_verb_rows(name)
    return "\n".join(out)


# ------------------------------------------------------------- level 3/4
# `/help <class> list` and `/help <class> read #` — docs/HELP_DESIGN.md
# §2 levels 3-4, R160, 2026-08-13. One provider per populated class: a
# LIST function returning ordered (id, human_key) pairs, and a READ
# function returning one id's full record. `#` in `read #` is always a
# position in the list AS IT WOULD PRINT RIGHT NOW, re-derived fresh on
# every call — never a stored id, never cached (HELP_DESIGN.md §2 names
# this a limitation to accept, not a bug: the register is small enough
# that a fresh read costs nothing).
def _issue_entries() -> list[tuple[str, str]]:
    docs = (S_.issue_read(p) for p in S_.issue_live_read())
    return [(d["id"], d.get("label", "")) for d in docs]


def _issue_read(nid: str) -> str:
    p = next(q for q in S_.issue_live_read() if S_.issue_id_read(q.stem) == nid)
    return S_.issue_render(S_.issue_read(p))


def _issue_relationship_entries() -> list[tuple[str, str]]:
    return [(f"{e['src']} {e['type']} {e['target']}", e["type"])
            for e in IC.issue_edges_read()]


def _issue_relationship_read(id_: str) -> str:
    # (src, type, target) is the closest thing an edge has to an id
    # (docs/HELP_DESIGN.md §3) — it carries no id of its own. Split on
    # a single space, twice: neither a node id nor an edge type ever
    # contains one, so this can't misparse.
    src, typ, tgt = id_.split(" ", 2)
    e = next(x for x in IC.issue_edges_read()
             if x["src"] == src and x["type"] == typ and x["target"] == tgt)
    L = [f"# {src} {typ} {tgt}", "",
         f"**Status:** {e['status']}"
         + (f" ({e['dated']})" if e.get("dated") else "")
         + (f" — {e['status_note']}" if e.get("status_note") else ""), "",
         f"**Basis:** {S_.issue_unwrap(e['basis'])}", ""]
    if e.get("why"):
        L += [f"**Why:** {S_.issue_unwrap(e['why'])}", ""]
    for extra in e.get("notes", []):
        L += [S_.issue_unwrap(extra), ""]
    if e.get("ask"):
        L += ["**Ask:** " + ", ".join(e["ask"]), ""]
    if e.get("quote"):
        L += ["> " + S_.issue_unwrap(e["quote"]), ""]
    if e.get("retired"):
        L += [f"**Retired:** {S_.issue_unwrap(e['retired'])}", ""]
    return "\n".join(L)


OBJECT_CLASS_PROVIDERS: dict[str, tuple] = {
    "issue": (_issue_entries, _issue_read),
    "issue-relationship": (_issue_relationship_entries, _issue_relationship_read),
}


def object_class_list_text(name: str) -> str:
    provider = OBJECT_CLASS_PROVIDERS.get(name)
    if provider is None:
        return f"  {name}: list not built yet"
    entries = provider[0]()
    if not entries:
        return f"  {name}: no live entries"
    out = [f"  {name} — {len(entries)} live"]
    for i, (id_, key) in enumerate(entries, start=1):
        # Truncated to the line's own remaining budget, not wrapped — a
        # numbered list stays one row per entry (80 column max, RULED
        # 2026-08-16); id_'s own width varies (an issue id is short, an
        # edge's "<src> <type> <tgt>" is not), so the budget is computed
        # per row rather than assumed fixed.
        prefix = f"  {i:>3}  {id_}  "
        budget = max(10, HELP_WIDTH - len(prefix))
        out.append(prefix + key[:budget])
    return "\n".join(out)


def object_class_read_text(name: str, pos_raw: str) -> str:
    provider = OBJECT_CLASS_PROVIDERS.get(name)
    if provider is None:
        return f"  {name}: read not built yet"
    entries_fn, read_fn = provider
    entries = entries_fn()
    try:
        pos = int(pos_raw)
    except ValueError:
        return f"  read # must be a number — try /help {name} list first"
    if not entries:
        return f"  {name}: no live entries"
    if pos < 1 or pos > len(entries):
        return f"  {name} has {len(entries)} live entries — # must be 1-{len(entries)}"
    id_, _ = entries[pos - 1]
    return read_fn(id_) + "\n\n" + object_class_help_text(name)


# THE HAND-WRITTEN GLOSSES — the room's three verbs and /help, and nothing
# else since 2026-08-21. Level 0 used to lean on this table for the whole
# not-dev tier (docs/HELP_DESIGN.md §2), falling back to a description's
# FIRST LINE for every verb it did not cover; the rows carry the whole
# COMMANDS description now (`help_row`), so the only verbs that still want a
# hand-written line are the four whose COMMANDS text is written relative to
# the table's own order ("/pass (below)", "/round, above") and would read
# wrong in a sorted listing. circle_pane_help() reads these too.
# `/dev` is never a key here — same "stays deliberately absent" reasoning as
# COMMANDS never carrying it. test_help_system.py asserts the key set stays
# exactly these, so a stale or missing gloss breaks loudly.
# /abort JOINED 2026-08-31 with its move to the circle pane
# (R414): its COMMANDS text is two lines, and _one_liner's
# first-line fallback would have cut it mid-sentence in the room's listing.
_HELP_ONE_LINERS = {
    "/round": "let the parts continue without a Self statement",
    "/pass": "alias for /round",
    "/close": "collect short_terms, verify, apply rulings, report",
    "/abort": "end the circle without a close; a second /abort confirms",
    "/help": "this list",
}


def _one_liner(cmd: str) -> str:
    """The short gloss for one verb — circle_pane_help()'s reader.

    _HELP_ONE_LINERS is HAND-WRITTEN and covers the room's three verbs and
    /help. For anything else the first line of the verb's own COMMANDS
    description is used, which is where that text already lives. A verb in
    neither says so rather than raising: a KeyError inside /help would take
    the whole listing down over one missing gloss."""
    if cmd in _HELP_ONE_LINERS:
        return _HELP_ONE_LINERS[cmd]
    for spec, desc, _pane in COMMANDS:
        if spec.split(" ", 1)[0] == cmd:
            return desc.split("\n")[0].strip()
    return "(no description)"


def circle_pane_help() -> str:
    """WHAT THE ROOM ITSELF ACCEPTS — finding 10, and docs/HELP_DESIGN.md's
    own lines: *"Support /help in the dialog window. Always report only
    statements allowed in the dialog window, including /help (never report
    any command-pan only actions), /round, /pass, /close, and a brief on
    [remember: <text>] and [propose: <text> | <command>]."*

    A SEPARATE RENDERER BECAUSE IT ANSWERS A DIFFERENT QUESTION. Every
    other help path renders COMMANDS, which is the command-PANE's surface;
    the circle pane recognizes speech, the circle-class verbs and two
    annotations, and nothing else. Handing the room the command table would
    list verbs that are refused there — which is the opposite of help.

    THE VERBS ARE READ OFF PANE_OF, NOT LISTED BY HAND, since 2026-08-31
    (R414): the operator ruled that each pane's help shows
    only what that pane operates, and /abort joined the room the same day.
    A hand list here was the second copy that drifts; the class is the
    one source, and the command pane's renderers exclude the same class.

    THE ANNOTATION GRAMMAR IS QUOTED FROM THE ONE PLACE THAT PARSES IT.
    The propose subset is read live rather than restated, so this cannot
    drift from what the parser accepts — E09's shape, and the reason
    test_annotation_exemplars.py exists.

    THE WORD CAP IS NO LONGER MENTIONED because there is no longer one:
    R255 capped a FREE-TEXT propose at 100 words, a command was always
    exempt, and 2026-08-20 made every propose a command."""
    return "\n".join([
        "",
        "  IN THE ROOM you speak. Type and press Enter — that IS your turn.",
        "",
        "\n".join(command_help_rows_render((c, _one_liner(c))
                            for c in circle_verbs() + ("/help",))),
        "",
        "  INSIDE what you say, two annotations ride along:",
        "",
        "    [remember: <text>]     a private note to your own future self.",
        "                           Never shown to a part or to the room.",
        "                           The command pane can read them back.",
        "    [proposed: <command>]  staged for a ruling later, and RUN when",
        "                           you approve it.",
        # NO COUNT ANY MORE — the operator's wording, 2026-08-25 (the same
        # session as R347), wrapped to the 80-column pane
        # invariant. The count line was already once wrong in kind: the
        # table held a verb the classifier refused, so "6" was printed
        # while the refusal a part actually met listed 5 (2026-08-20 code
        # review). Pointing at 'help propose' names the LIVE list instead.
        "                           It must contain a proposable command",
        "                           ('help propose' at the cmd> prompt);",
        "                           anything else is an error, reported here.",
        "",
        "  THE COLON AND THE SPELLING ARE REQUIRED, and no space may follow",
        "  the opening bracket. Any other bracket is ordinary speech — it is",
        "  neither captured nor removed.",
        "",
        "  Everything else — the issue verbs, practices, topics, prompts —",
        "  belongs to the command pane. Its own /help lists them.",
        "",
    ])


# The level-1 production, advertised at the foot of level 0 — the operator,
# 2026-08-21: "Update help at level 0 to report all help level 1." ONLY
# while dev is on: the hierarchy is behind the gate (D-C, same day —
# "/help object_classes is itself behind the gate - invisible while
# dev==false - as is the entire hierarchy"), and naming a gated verb with
# dev off would itself reveal that a gate exists (R199).
_LEVEL1_ROW = ("/help object_classes",
               "the object classes; /help <class> for each one's verbs")


def _help_level0() -> str:
    """docs/HELP_DESIGN.md §2 Level 0 — content tiers by dev_mode, never
    refuses outright (unlike levels 1-4 below, which do while dev is off).

    RULED 2026-08-16: "dev is meant to require being told, permanently" —
    the not-dev listing below used to head itself "dev mode is off — only
    these are available:", which is itself the tell that a bigger, gated
    tier exists. Reads as an ordinary COMMANDS listing instead — the same
    heading the dev-on branch uses — so there is nothing here for a reader
    to notice is incomplete.

    ONE ROW SHAPE IN BOTH TIERS, SORTED, 2026-08-21 — `help_row` / `_verb_rows`.
    No speech row any more (same day, later: speech is not a command, see
    the note above _class_of_head). Both tiers are the CLASS rows alone
    since R347 (2026-08-25); dev on adds the level-1 row."""
    specs = _command_specs()
    classes = object_classes()
    visible = [h for h in specs if _visible_head(h)]

    # ONE ROW PER ROOT CLASS, not one per verb. R336, 2026-08-24, after the
    # operator read a real listing in a real pane: "the diagnostic prints
    # properly, followed by a long help that rolls the error out of sight"
    # was the JUNK half of it (R335); this is the other half. Nineteen
    # verbs and fifty-seven lines do not fit a pane, and a reader cannot
    # scan what does not fit.
    #
    # R266 IS NARROWED, NOT REVERSED, and this is the line worth reading
    # twice. R266 ruled that dev mode ADDS and never takes away and that
    # the issue verbs are the USER'S — both still hold exactly: every verb
    # a non-dev reader could type before is still reachable, still theirs,
    # one question further in (`/help issue`). What changed is that level 0
    # names the SUBJECT rather than enumerating the verbs under it.
    out = ["", "  COMMANDS — type  /help <name>  for any of these"]
    class_pairs = []
    for cname in _root_classes(classes):
        heads = [h for h in visible
                 if _class_of_head(h, classes) in _subtree(cname, classes)]
        if not heads:
            continue
        first = " ".join(classes[cname].get("description", "").split())
        first = first.split(". ")[0].rstrip(".")
        n = f"   ({len(heads)})" if len(heads) > 1 else ""
        # ONE LEFT EDGE FOR EVERY PANE, 2026-08-25. A class row carried two
        # extra spaces in its own spec, so level 0 sat one indent right of
        # `/help <class>`'s rows and of its own level-1 row below.
        class_pairs.append((cname, f"{first}{n}"))

    # THE SESSION SECTION AND THE ROOM POINTER ARE GONE — the operator,
    # 2026-08-25 (R347), the same day R341 had already pulled
    # the room's verbs down to one pointer line: level 0 is the class rows
    # alone. /help, /status and /abort still answer individually; the
    # room's own verbs are listed by the circle prompt's /help. What this
    # gives up, named: the section was the unclassed-verb COMPLEMENT (the
    # v45 failure mode), so a new unclassed verb now appears in NO listing
    # until it is classed — both tiers held exactly /abort, /help and
    # /status when this was cut.

    # THE LEVEL-1 ROW SHARES THE CLASS ROWS' COLUMN, 2026-08-25 — it was a
    # bare command_help_row_render(), so its wrapped text hung at ROW_HANG under a listing
    # whose own continuations sat at the description column.
    level1 = [_LEVEL1_ROW] if (CS.dev_mode and classes) else []
    pad = command_help_pad(class_pairs + level1)
    out += command_help_rows_render(class_pairs, pad)
    if level1:
        out += [""] + command_help_rows_render(level1, pad)
    return "\n".join(out) + "\n"


def circle_verbs() -> tuple[str, ...]:
    """The room's own verbs, in COMMANDS order — PANE_OF's circle class.
    /round, /pass, /close, and /abort since 2026-08-31."""
    return tuple(h for h, p in CS.PANE_OF.items() if p == "circle")


def _visible_head(head: str) -> bool:
    """The whole gate for the COMMAND PANE's listings, as ONE test.

    PANE-SCOPED SINCE 2026-08-31 (R414) — the operator:
    *"help in the two panes properly show only the commands operable in
    their panes."* A circle-class verb is never a row here, dev on or off:
    it is refused at cmd>, and a listing that names a verb the pane refuses
    is the opposite of help. Until then the room's three were ADDED by
    hand for the non-dev tier, so cmd> help listed /close beside the verbs
    it could run. circle_pane_help() is the room's own listing.

    Then the dev gate, unchanged: DEV_MIN_CMDS and USER_SUBSET_COMMANDS
    are what a non-dev reader sees."""
    if CS.PANE_OF.get(head) == "circle":
        return False
    if CS.dev_mode:
        return True
    return head in CS.DEV_MIN_CMDS or head in CS.USER_SUBSET_COMMANDS


def _class_tree_text(cls: str) -> str:
    """`/help <class>` — the class's OWN commands, then every child class
    as its own labelled group. R336, 2026-08-24.

    THE WHOLE SUBTREE, which is what the operator expected and did not get
    from the first prototype: `/help issue` answers with every `/issue*`
    command, its children grouped rather than hidden behind a second
    question — and each child still has its own page for the same rows read
    on their own. Filtered by _visible_head, so a dev verb does not leak
    into a non-dev reader's listing and the gate stays one test.

    `list` and `read #` are advertised only with dev on: they are the
    RECORD inspector, which R280 gates and this does not change."""
    classes = object_classes()
    specs = _command_specs()
    mine = [h for h in specs
            if _class_of_head(h, classes) == cls and _visible_head(h)]
    desc = " ".join(classes[cls].get("description", "").split())

    # EVERY ROW THIS PANE WILL PRINT, MEASURED BEFORE ANY OF IT IS PRINTED —
    # the operator, 2026-08-25: *"align the left edge and hyphen description
    # of all detailed help panes."* A pane is not one listing: the class's
    # own verbs, each child class's label, and that child's verbs were three
    # groups with three pads, so one page carried three hyphen columns and
    # three continuation indents. `blocks` holds either a run of
    # (spec, description) pairs or literal lines; every pair is pooled for
    # ONE command_help_pad() below.
    blocks: list[tuple[str, list]] = [
        ("text", [f"  {cls.upper()}", f"    {desc}", ""]),
        ("rows", _verb_pairs(mine, specs)),
    ]
    if cls == "propose":
        # WHAT MAY BE PROPOSED, live from the classifier's own table — the
        # operator, 2026-08-25 (R350): the circle pane's
        # [proposed: ...] help points here, so this page must answer with
        # the list, each verb with its arguments (the COMMANDS spec).
        # PROPOSABLE_COMMANDS, not the raw subset — the deferred verb is
        # refused at classification, and listing it as proposable would
        # repeat the 6-vs-5 defect this page's pointer replaced.
        # THROUGH command_proposable_read() SINCE B122 (2026-09-07): the current
        # group's descriptor narrows what the classifier admits, and a page that
        # counted the constant would advertise verbs this group's own refusal
        # rejects — the same disagreement one group over.
        proposable = sorted(CS.command_proposable_read())
        blocks.append(("text",
                       ["", "    a /propose-add — or a part's "
                            "[proposed: ...] — may name:"]
                       + ([f"      {specs[h][0] if h in specs else h}"
                           for h in proposable] or
                          ["      nothing — this group proposes no command"])))
    for child in _children_of(cls, classes):
        kids = [h for h in specs
                if _class_of_head(h, classes) in _subtree(child, classes)
                and _visible_head(h)]
        if not kids:
            continue
        cdesc = " ".join(classes[child].get("description", "").split())
        # THE CHILD'S LABEL IS A ROW LIKE ANY OTHER, at the same left edge
        # since 2026-08-25 — it used to carry two extra spaces in its own
        # spec, which indented it past every verb around it and, having no
        # pad, hung its wrapped text at ROW_HANG instead of the column.
        # It still reads as a class rather than a verb: no leading slash.
        blocks.append(("text", [""]))
        blocks.append(("rows",
                       [(child, f"{cdesc.split('. ')[0].rstrip('.')} "
                                f"— /help {child}")]
                       + _verb_pairs(kids, specs)))
    if CS.dev_mode:
        blocks.append(("text", [""]))
        blocks.append(("rows", [(f"/help {cls} {name}", why)
                                for name, why in LEVEL_ROWS]))

    pad = command_help_pad([p for kind, block in blocks if kind == "rows"
                   for p in block])
    out: list[str] = []
    for kind, block in blocks:
        out += block if kind == "text" else command_help_rows_render(block, pad)
    return "\n".join(out)


# THE VERBS THAT ASK THEIR OWN QUESTIONS — the operator, 2026-08-25:
# *"Include a note where a dialog is available: '/part-add' alone runs a
# dialog to define the new part."* Each entry is (the form that reaches the
# dialog, what the dialog asks, the initialization.py function that IS it).
# The function name is never printed; it is there so
# coordinator/tests/test_help_system.py can assert every dialog named here
# still exists — the same drift guard the edge-type gloss carries, and the
# only thing that can keep this table honest, since a dialog is reached
# through a command's own branch rather than through a registry.
_DIALOG_VERBS: dict[str, tuple[str, str, str]] = {
    "/part-add": ("/part-add",
                  "typed alone, runs a dialog: it asks for the description, "
                  "then the name",
                  "part_add_dialog"),
    "/issue-add": ("/issue-add",
                   "typed alone, runs a dialog: any of the three answers you "
                   "leave out is asked for",
                   "issue_add_dialog"),
    "/part-context-update": ("/part-context-update <part>",
                             "runs a dialog: that part's context questions, "
                             "each answer prefilled — Enter keeps it, type to "
                             "change it, `-` clears it",
                             "part_context_dialog"),
}


def _verb_help_text(head: str) -> str:
    """`/help <verb>` — ONE verb's own page, 2026-08-25. The operator typed
    `help recall`, `help part-add`, `help issue-add`, `help propose-add`,
    `help practice-add`, `help better-option-add` and
    `help issue-relationship-add`, and every one of them answered "not
    understood, see 'help'": this function's argument resolved a CLASS or
    nothing at all, and a verb is what a reader has in hand after any
    listing names one.

    The shape is the class page's, one level down — the name, the form, the
    whole description — then rows for what is left to say: the dialog form
    where there is one, and the way back to the rest of the class.

    NOT GATED BY dev_mode, and that is a deliberate narrowing of R280 in
    the same direction R336 already took it ("gating it would show them a
    door and lock it"): three of the verbs above are dev-table verbs whose
    names the UNGATED `/help propose` page already prints, with their
    arguments, because they are proposable. A reader who can read the name
    there can ask what it means."""
    specs = _command_specs()
    spec, desc = specs.get(head, (head, ""))
    out = [f"  {head.upper()}", f"    {spec}", "",
           f"    {' '.join(desc.split())}"]
    pairs: list[tuple[str, str]] = []
    if head in _DIALOG_VERBS:
        form, asks, _fn = _DIALOG_VERBS[head]
        pairs.append((form, asks))
    cls = _class_of_head(head, object_classes())
    if cls:
        pairs.append((f"/help {cls}",
                      f"the other verbs in the {cls.upper()} class"))
    if pairs:
        out += [""] + command_help_rows_render(pairs)
    return "\n".join(out)


def _wrap80(text: str, width: int = HELP_WIDTH) -> str:
    """Re-wrap any line over `width` columns — RULED 2026-08-16, "change
    all help output to 80 column max window." Line-at-a-time, not
    paragraph-at-a-time: a line that already fits (a table row, a blank
    line, a short heading) is left untouched, so this never reflows
    content that was already laid out on purpose. A line that overflows
    (unwrapped TOML prose, collapsed via issue_schema.issue_unwrap() to one
    line per paragraph for DISPLAY — its own separate, correct
    convention, not a bug) hard-wraps here instead, with its continuation
    hanging past the original indent and any leading `-`/`*`/`#`/`N.`
    marker, so a wrapped bullet's second line still reads as the same
    item."""
    out = []
    for line in text.split("\n"):
        if len(line) <= width:
            out.append(line)
            continue
        stripped = line.lstrip(" ")
        indent = line[:len(line) - len(stripped)]
        m = re.match(r"(-\s+|\*\s+|#+\s+|\d+\.\s+)", stripped)
        hang = indent + (" " * len(m.group(1)) if m else "")
        wrapped = textwrap.wrap(stripped, width=width, initial_indent=indent,
                                subsequent_indent=hang,
                                break_long_words=False, break_on_hyphens=False)
        out.extend(wrapped or [indent])
    return "\n".join(out)


def command_help_render(arg: str = "") -> str:
    """RULED 2026-08-10: `/help`, `/help object_classes`, `/help <class>`
    — one function, dispatched by argument, everything hot-reloaded fresh
    on every call. `/help <class> list` and `/help <class> read #` are
    levels 3-4, R160. `/help annotate` (mark kinds) retired with MARK,
    2026-08-14.

    docs/HELP_DESIGN.md §2, wired 2026-08-16 — designed and marked
    "(dev-gated)" for every level but never actually gated until now:
    level 0 (`arg == ""`) TIERS by dev_mode via `_help_level0()`, never
    refusing outright; levels 1-4 (`object_classes` and every `<class>`
    form) REFUSE while dev is off, reusing `command_dev_restricted_render()` — the
    same refusal a command-pane verb typed with dev off already gets, so
    this doesn't invent a third phrasing. RULED 2026-08-16: "dev is meant
    to require being told, permanently" — that refusal, and level 0's own
    not-dev branch, name nothing about dev mode; a gated request now reads
    exactly like a nonexistent one. RE-RULED THE SAME WAY 2026-08-21 (D-C):
    "/help object_classes is itself behind the gate - invisible while
    dev==false - as is the entire hierarchy." `--dev-cmd`'s own contract
    ("Bypasses dev_mode entirely") is honored at its one call site in
    main(), not here — this function has no caller identity to bypass for.

    ONE wrap point, not one per branch: `_help_text_raw()` below carries
    every branch unchanged, and this function's only job is `_wrap80()`
    on its way out — RULED 2026-08-16, "80 column max window", after a
    node's rendered markdown (level 4, `/help <class> read #`) showed
    lines past 900 characters. `object_class_help_text()`'s own paragraph
    text is collapsed to one line per paragraph by `issue_schema.issue_unwrap()`
    — a separate, correct DISPLAY convention (CLAUDE.md, `issues/` TOML) —
    so wrapping belongs here, at the point text actually reaches a human,
    not inside that convention."""
    return _wrap80(_help_text_raw(arg))


def _help_text_raw(arg: str = "") -> str:
    if arg == "":
        return _help_level0()
    if arg == "object_classes":
        if not CS.dev_mode:
            return command_dev_restricted_render()
        return "\n" + object_class_help_text("") + "\n"
    words = arg.split(None, 2)
    # A LEADING SLASH IS ACCEPTED EVERYWHERE, 2026-08-25 — the operator
    # typed `help /recall` after `help recall` and got the same refusal
    # twice. The pane does not require a slash (R201) and never refused one
    # at the prompt; only this resolver did.
    cls = words[0].lstrip("/") if words else ""
    if cls in object_classes():
        # THE COMMAND LISTING IS NOT GATED; THE RECORD INSPECTION STILL IS.
        # R336, 2026-08-24, and this is the seam worth naming. R280 gated
        # "the entire hierarchy" when the hierarchy WAS the object-class
        # inspector — `list` and `read #` walking real issue records. Level
        # 0 now names classes instead of verbs, so `/help issue` is the only
        # way a non-dev reader reaches verbs that R266 already ruled are
        # THEIRS. Gating it would show them a door and lock it.
        #
        # So the split is by WHAT IS BEING SHOWN, not by which level:
        #   /help <class>            the class's own COMMANDS — ungated,
        #                            and filtered to what this dev state
        #                            would let you type anyway
        #   /help <class> list       the live RECORDS — dev only, unchanged
        #   /help <class> read #     one record, whole — dev only, unchanged
        #   /help object_classes     the inspector's own index — dev only
        if len(words) == 1:
            return "\n" + _class_tree_text(cls) + "\n"
        if not CS.dev_mode:
            return command_dev_restricted_render()
        if len(words) >= 2 and words[1] == "list":
            return "\n" + object_class_list_text(cls) + "\n"
        if len(words) >= 3 and words[1] == "read":
            return "\n" + object_class_read_text(cls, words[2]) + "\n"
        return (f"\n  unrecognized: help {arg!r} — try `/help {cls}`, "
                f"`/help {cls} list`, or `/help {cls} read #`\n")
    # `/help <verb>` — AFTER the class branch, never before it. `propose`
    # is both a class and (through SYNONYMS) a verb head, and the class is
    # the larger answer: /help propose keeps printing the class page, and
    # /help propose-add the verb's own.
    head = CS.command_head_normalise(words[0]) if words else ""
    if len(words) == 1 and head in _command_specs():
        return "\n" + _verb_help_text(head) + "\n"
    # R199/R280, MEASURED AND CLOSED 2026-08-24. This branch answered a
    # word that means nothing DIFFERENTLY from a word the gate is hiding,
    # and named the hidden level while doing it:
    #
    #     dev off, help object_classes  ->  "not understood, see 'help'"
    #     dev off, help issue           ->  "not understood, see 'help'"
    #     dev off, help frobnicate      ->  "unrecognized: help
    #                                        'frobnicate' — try /help or
    #                                        /help object_classes"
    #
    # Two failures in one line. The DIFFERENCE is itself the tell that a
    # gated tier exists, which is the thing R199 forbids — "dev is meant
    # to require being told, permanently" — and this function's own
    # docstring claimed "a gated request now reads exactly like a
    # nonexistent one", which was not true and had not been. And the
    # advice names `/help object_classes`, which R280 requires be
    # "invisible while dev==false", so any garbage typed after `help`
    # announced the level-1 form to a reader who may not have it.
    #
    # With dev off both answer with command_dev_restricted_render() and are
    # indistinguishable. With dev on the pointer is useful and stays.
    if not CS.dev_mode:
        return command_dev_restricted_render()
    return f"\n  unrecognized: help {arg!r} — try /help or /help object_classes\n"


def command_help(arg: str) -> None:
    """`/help`'s always-available door. `command_help_render()` is a pure read of
    COMMANDS and object_classes.toml — no transcript, no running circle
    needed — but until 2026-08-16 `dispatch_dev_cmd()` had no case for it,
    so `--dev-cmd help` wrongly refused with "needs a live circle" even
    though circling.py's command pane special-cases bare `help` itself and
    never hit the gap. `.strip()`: `--dev-cmd help object_classes` arrives
    here as `" object_classes"` (main()'s own `rest_text` construction),
    and command_help_render()'s `arg == "object_classes"` check is exact-equality."""
    seam.emit("command", command_help_render(arg.strip()))


def junk_help(line: str) -> str:
    """JUNK -> the error, and a POINTER to help. Two lines, never the
    listing.

    R285 (2026-08-21) ruled *"input JUNK -> help"* and this printed the
    whole level-0 listing under the error. Corrected 2026-08-24 by the
    operator, on a measurement R285 did not have: *"the diagnostic prints
    properly, followed by a long help that rolls the error out of sight.
    Do not invoke help... issue the error, then on the next line 'See
    help'."* The listing is longer than a pane, so the one line that says
    what went wrong scrolled away — an answer that hides the diagnosis is
    worse than no answer, because the reader saw something happen and
    cannot tell what.

    THE RULING'S SUBSTANCE IS UNCHANGED and only its rendering moved: JUNK
    is still answered, still uniformly, and still without naming "dev
    mode" (R199 — a gated verb reads as nonexistent, and gets exactly what
    a nonexistent one gets). What changed is that the reader now types
    `help` when they want the listing, instead of being given it.

    circle.py's Self> loop uses this for a forwarded or standalone-terminal
    line the dev state does not accept; ui/circling.py's command pane
    composes the same two lines itself (its stub harness carries no
    help_system)."""
    return f"  not a command: {line.strip()}\n  See help"


def command_dev_restricted_render() -> str:
    """What the dev-gated HELP HIERARCHY prints back while dev is off —
    `/help object_classes`, `/help <class>`, `list`, `read #`
    (R280, 2026-08-21).

    RULED 2026-08-16: "dev is meant to require being told, permanently" —
    no output anywhere may name "dev mode" as a concept, since doing so
    is itself the hint that a gated tier exists to go looking for. A
    gated request is indistinguishable from a nonexistent one.

    NO LONGER THE COMMAND PANE'S REFUSAL, 2026-08-21: a dev-table VERB typed
    with dev off is JUNK and is answered with junk_help() — the listing —
    by the pane and by circle.py's loop alike. This one-liner survives only
    for the hierarchy's own levels, which are read through command_help_render()
    itself and so cannot sensibly answer with command_help_render()."""
    return "  not understood, see 'help'\n"
