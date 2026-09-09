#!/usr/bin/env python3
"""
record_paths.py — the one home for the RECORD's path constants and the roster
projection every writer shares (paths.py until 2026-09-03 — R8/Q-A under R435:
the constants are mostly record locations, so RECORD is the class). Phase 1 of the coordinator
partitioning
(reviewed 2026-08-16); step 0, the module everything later extracted
reads its locations from.

WHY ONE HOME. Before this module, relocating a single register file
meant finding every module that had independently derived its path —
coordinator/best_practices.toml alone was hardcoded in BOTH
REGISTER_CLASS.py and check_best_practices.py (practice_manager.py since
2026-09-03). A later placement ruling
(the memory/ question, unruled) becomes one edit here instead of a
sweep.

A RECORD IS A GROUP'S TREE — R466/R467, B117 (2026-09-07): groups/<name>/{parts,issues,self,
circles}/, the IFS group's at groups/ifs/ since stage 2 (the move, "move the IFS family now").
`group_tree(name)` is the one lookup, and every constant below is the DEFAULT group's tree. Every
literal `ROOT / "parts"`-style path in the tree asks this module instead, absolute
(`PARTS_DIR / part`) or ROOT-relative (`record_rel("self/topics.toml")`) — the relative form is
what git, the hook and the close transaction address as strings.

CONSTANTS, bound at import for the default group; `from record_paths import X` is safe because no
caller reassigns them. `group_set(name)` — for the process that opens a circle on another group,
later stages — rebinds this module's attributes; a reader that must follow it reads them as
attributes (`RP.PARTS_DIR`), never by from-import. PART_TAGS is read lazily (module __getattr__)
because part_roster.py reads PARTS_DIR from here, so this module cannot import part_roster at load.
Note for future writers: several functions in this tree use a LOCAL variable named `paths` —
prefer `from record_paths import X` over `import paths` so a local can never shadow the module
inside a function body.
"""

from __future__ import annotations

import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent                      # this tree's own root, e.g. <checkout>/
SANDBOX = ROOT / "work" / "sandbox"     # moved from coordinator/sandbox, R176, 2026-08-15
GROUPS_DIR = ROOT / "groups"            # every group's tree (B117 stage 1; the default's too, stage 2)
SHIPPED_GROUP = "ifs"                   # IFS_CIRCLE — the GROUP a fresh bundle carries (packaging/groups.toml)
# A GROUP DESCRIBES ITSELF — R468, B120 (2026-09-07): groups/<name>/group.toml, whose presence is
# what makes a folder a group (R123's part.toml rule one level up). It carries what shipped code
# must not hardcode about ONE group: its roles, its reserved roles, the head of its initialization
# order, which role's answer names the console, its BLOCK 1 layer, its [proposed:] command list.
# group_manager.py is the one WRITER; this module READS it (tomllib, dependency-light), because
# identity.py, initialization.py and part_add.py read the descriptor and sit below the registers.
# groups/groups.toml — the register OF groups (B117 stage 3) — is retired: the list of groups is
# the scan of these files, as the roster is the scan of parts/*/part.toml.
GROUP_MARKER = "group.toml"


def group_descriptor_locate(name: str) -> pathlib.Path:
    return GROUPS_DIR / name / GROUP_MARKER


def group_descriptor_read(name: str) -> dict:
    """The group's own group.toml as a dict; {} when the file, the folder or the parse is absent —
    every failure degrades to "not a group", never raises (the reader identity.py's discipline)."""
    p = group_descriptor_locate(name)
    if not p.is_file():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:                                 # py < 3.11
        try:
            import tomli as tomllib                             # type: ignore
        except ModuleNotFoundError:
            return {}
    try:
        return tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return {}


def _group_names_read() -> list[str]:
    """Every folder under groups/ carrying a group.toml, by name."""
    if not GROUPS_DIR.is_dir():
        return []
    return sorted(p.name for p in GROUPS_DIR.iterdir()
                  if p.is_dir() and (p / GROUP_MARKER).is_file())


def group_default_read() -> "str | None":
    """THE GROUP A BARE OPEN RUNS — R468, B120 stage 4 (2026-09-07), the rule that replaced the
    literal "ifs": exactly one group installed -> it; several -> the one whose group.toml says
    `default = true`, if exactly one does; otherwise None, and circle.py asks for --group. A
    bundle carrying only a band is a working install; a bundle carrying no group is not."""
    names = _group_names_read()
    if len(names) == 1:
        return names[0]
    defaults = [n for n in names if group_descriptor_read(n).get("default") is True]
    return defaults[0] if len(defaults) == 1 else None


def group_default_refusal_read() -> str:
    """"" when a bare open may proceed, else the one sentence circle.py prints instead."""
    if group_default_read():
        return ""
    names = _group_names_read()
    if not names:
        return ("no group is installed under groups/ — a group is a folder carrying group.toml "
                "(R468); nothing to open on")
    marked = [n for n in names if group_descriptor_read(n).get("default") is True]
    if len(marked) > 1:
        return (f"{len(marked)} groups say `default = true` ({', '.join(marked)}) — mark exactly "
                f"one in its group.toml, or open with --group <name>")
    return (f"{len(names)} groups are installed ({', '.join(names)}) and none says "
            f"`default = true` in its group.toml — open with --group <name>, or mark one")


# THE BOUND GROUP AT IMPORT: the ruled default when there is one; else the first group present
# (so every path constant resolves and --group can still rebind); else the shipped group's name,
# which is only a placeholder in a tree that holds no group at all. Never a literal a working
# install depends on: circle.py refuses a bare open unless group_default_read() answers.
DEFAULT_GROUP = group_default_read() or (_group_names_read() or [SHIPPED_GROUP])[0]


def group_present_read() -> list[str]:
    """Every group on disk — groups/<name>/ carrying a group.toml (R468) — the bound group first.
    What the corruption gate and the hook walk (B117 stage 6). A folder under groups/ with a
    record but no descriptor is NOT a group: group_stray_read() names it, and record_verify
    reports it."""
    names = _group_names_read()
    if DEFAULT_GROUP in names:
        names.remove(DEFAULT_GROUP)
        names.insert(0, DEFAULT_GROUP)
    return names


def group_stray_read() -> list[str]:
    """Folders under groups/ that hold a RECORD kind but no group.toml — reported, never
    silently a group (R468)."""
    if not GROUPS_DIR.is_dir():
        return []
    return sorted(p.name for p in GROUPS_DIR.iterdir()
                  if p.is_dir() and not (p / GROUP_MARKER).is_file()
                  and any((p / k).is_dir() for k in RECORD_KINDS))


def group_tree(name: str) -> pathlib.Path:
    """The tree a group's RECORD lives in: groups/<name>/ — every group the same shape, the IFS
    group's at groups/ifs/ (B117 stage 2, R467: "move the IFS family now"). Through GROUPS_DIR,
    so a probe that rebinds it sees every group under its temp tree."""
    return GROUPS_DIR / name


def group_rel(name: str) -> str:
    """group_tree(name) relative to ROOT, posix ("groups/ifs")."""
    t = group_tree(name)
    return "" if t == ROOT else t.relative_to(ROOT).as_posix()


_GROUP = DEFAULT_GROUP                  # the group this process's record constants are bound to


def group_read() -> str:
    return _GROUP


def record_rel(rel: str, name: "str | None" = None) -> str:
    """A record-relative path ("self/topics.toml", "parts/<p>/remember.toml") as a
    ROOT-relative posix string for the group — the shape git, the hook's globs and the
    transaction's stage() take ("groups/ifs/self/topics.toml")."""
    base = group_rel(_GROUP if name is None else name)
    return f"{base}/{rel}" if base else rel


RECORD_KINDS = ("parts", "self", "issues", "circles")   # what a group's tree holds (R467)
_REAL_ROOT = ROOT                       # never rebound — a probe may rebind ROOT itself


def record_dir(base: pathlib.Path, kind: str) -> pathlib.Path:
    """The record directory `kind` ("parts", "self", "issues", "circles") under `base`: the
    group's tree when `base` is this tree's ROOT, else `base / kind` — the sandbox
    (work/sandbox/), a probe's temp tree and a snapshot keep the flat shape."""
    if pathlib.Path(base).resolve() == _REAL_ROOT:
        return RECORD / kind
    return pathlib.Path(base) / kind


def record_path(base: pathlib.Path, rel: str) -> pathlib.Path:
    """A record-relative path ("parts/<p>/remember.toml", "self/topics.toml") under `base`,
    through record_dir() — the group's tree under the real ROOT, flat anywhere else.

    ONE CALLER, AND IT IS A SUITE THE HOOK DOES NOT RUN — audit-register.md #16, 2026-09-08.
    `ui/tests/circle_test.py:251` is the only use in the tree, and that suite is the single
    ALLOW entry in test_hook_template.py (see gitrepo.py for the measured reason it stays
    unwired: it does not terminate). So this is public API on the most-imported module in
    the tree — 80 importers — exercised by nothing that runs.

    KEPT, NOT DELETED, and the reason is the pair above it. record_dir() answers "which
    directory" and this answers "which file", against the same base-vs-ROOT rule; deleting
    the second would leave every caller needing a file to re-derive the split by hand, which
    is exactly the duplication record_dir() was introduced to end. It is one line of logic
    with no branch of its own. Revisit if circle_test.py is ever retired outright."""
    top, _sep, rest = rel.partition("/")
    d = record_dir(base, top)
    return d / rest if rest else d


def _bind(name: str) -> None:
    """Bind every record constant to group_tree(name). Called once at import for the default
    group; group_set() calls it again for another group."""
    global _GROUP, RECORD, SELF_DIR, PARTS_DIR, ISSUES_DIR, CIRCLES_DIR
    global BEST_PRACTICES, REDACTION, REDACTION_MAP
    _GROUP = name
    RECORD = group_tree(name)
    SELF_DIR = RECORD / "self"
    PARTS_DIR = RECORD / "parts"
    ISSUES_DIR = RECORD / "issues"
    CIRCLES_DIR = RECORD / "circles"
    BEST_PRACTICES = SELF_DIR / "best_practices.toml"
    REDACTION = SELF_DIR / "redaction.toml"
    REDACTION_MAP = SELF_DIR / "redaction_map.toml"


# FOLLOWERS — B117 stage 3 (2026-09-07). A module whose own constant is derived from one of
# this module's at import (part_roster.PARTS_DIR, a manager's PATH = SELF_DIR / "x") registers a
# callable that re-derives it; group_set() runs them all after rebinding, so the whole process
# follows the group a circle opens on. A probe that rebinds a manager's PATH to a temp file is
# untouched until something calls group_set().
_FOLLOWERS: list = []


def group_follow(fn):
    """Register `fn` to run after every group_set(); returns it, so it can decorate."""
    if fn not in _FOLLOWERS:
        _FOLLOWERS.append(fn)
    return fn


def group_set(name: str) -> pathlib.Path:
    """Rebind this module's record constants to another group's tree, run every follower, and
    return the tree. Readers that from-imported a constant keep the default group's; attribute
    readers and followers' constants follow. roster's tables are mutated IN PLACE by its
    follower, so `from record_paths import PART_TAGS` — the same dict object — follows too."""
    _bind(name)
    for fn in list(_FOLLOWERS):
        fn()
    return RECORD


# The data-directory roots — where the user-owned record lives: the default group's tree at
# import (B117 stage 1; one home since the 2026-08-16 phase-1 review).
RECORD = group_tree(DEFAULT_GROUP)
SELF_DIR = RECORD / "self"
PARTS_DIR = RECORD / "parts"
ISSUES_DIR = RECORD / "issues"
CIRCLES_DIR = RECORD / "circles"
# THE SANDBOX TWIN of CIRCLES_DIR (R176, 2026-08-15) — issue_schema.py carried its own copy
# of this and of ROOT/CIRCLES, and issue_gate/issue_commands/issue_status/project_stats/
# check_budget re-exported those; since 2026-09-03 (stage 14, R8) they read here.
SANDBOX_CIRCLES = SANDBOX / "circles"
TICKING_DIR = ROOT / "ticking"          # the JOURNAL (R391/R396) — user
                                        # record; pull-main keeps the lab's

# self/best_practices.toml — RETURNED to self/ 2026-08-16 by Self's
# ruling on the memory/ decomposition ("out of coordinator and into
# self/"), reversing the 2026-08-11 circle-scoped move and putting the
# register — which physically carries the R133-merged better_options
# rows, Self's own content — back with the user-owned record. Was
# hardcoded independently by REGISTER_CLASS.py (BEST) and
# practice_manager.py (BP; check_best_practices.py until 2026-09-03); both read this constant, which is what
# made the move one edit here instead of a sweep.
BEST_PRACTICES = SELF_DIR / "best_practices.toml"

# self/redaction.toml — the user-curated alias registry (canonical name,
# kind, extra forms, a stable opaque id) circling.py's redacted CIRCLE-pane
# view matches against. self/redaction_map.toml — the reverse map for
# auto-detected structured identifiers (email/url/phone/handle), keeping
# their opaque ids stable across restarts. The map's own `literal` field is
# raw PII and the file never ships — packaging/runtime_only.txt names it.
REDACTION = SELF_DIR / "redaction.toml"
REDACTION_MAP = SELF_DIR / "redaction_map.toml"

# parts/<dir> -> transcript tag. B29: derived from part_roster.py, the one
# roster every reader shares — was a hand-typed copy, kept in sync with
# circle_close_verify.py's own tag map (and the other seven) only by discipline.
# READ LAZILY (B117 stage 1): part_roster.py reads PARTS_DIR from this module, so importing roster
# here at load would be a cycle. `from record_paths import PART_TAGS` still works — Python asks
# a module's __getattr__ for a name it does not carry (PEP 562).
def __getattr__(name: str):
    if name == "PART_TAGS":
        import part_roster as _R
        return _R.TAG_BY_DIR
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
