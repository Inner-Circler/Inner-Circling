#!/usr/bin/env python3
"""
group_add.py — the GROUP register: a named, reusable roster of `parts/<dir>/`
directory names, so `circle.py --group <name>` can invoke a whole roster by
name instead of retyping `--parts <list>` every time.

WHY THIS EXISTS. `circle.py --parts <list>` already selects an arbitrary
subset of whatever `parts/` holds (roster.py, R123) — the mechanism was
already general, only the ergonomics were missing. It matters more than
convenience the moment a second, differently-purposed roster exists:
MAX_MEMBERS (circle_close_verify.py) is 9 — 8 parts + Self — so an IFS roster (the
current seven) and any future roster of a different character cannot both
live under `parts/` and be invoked together; they can only be invoked
SEPARATELY, by name. GROUPS are how "separately, by name" stays usable.
docs/CIRCLE_TYPES_DESIGN.md is the design this implements.

WHAT A GROUP IS, MECHANICALLY: one row in `self/groups.toml` — `name` and
`members` (a list of `parts/<dir>/` directory names, matching exactly what
`circle.py --parts` already expects). A group is a NAME, not a snapshot:
`--group` resolves the member list fresh at circle-open, so renaming or
removing a member part changes what every group naming it means, the same
way a part's own `long_term.md` can change under an existing name.

MEMBERS ARE NOT REQUIRED TO EXIST YET, mechanically — this module could
write a group naming a part that hasn't been created. It refuses to,
deliberately: `--group` resolving to a directory `roster.part_scan()` doesn't
recognize would fail at circle-open with a confusing "unknown part"
refusal that names a symptom, not the cause. `group_add()` checks every
member against a fresh roster scan (never an import-time copy), so the
register can promise its own members exist, not just promise something
plausible.

NOT MIRRORING part_add.py's long_term.md crash-safety discipline, on
purpose: a group carries no prompt-facing content of its own (nothing
reads "the group's identity" the way `prompt_build.record_ro_read()` reads a
part's), so there is no write-ordering hazard to protect against. It still
writes IMMEDIATELY (no `/abort` undo), matching every other register in
this class (`/practice-add`, `/part-add`).
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import roster as R                                             # noqa: E402
import REGISTER_CLASS as SS                                       # noqa: E402
from circle_close_verify import MAX_MEMBERS                            # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Rebindable for probes — test suites never write the live register.
PATH = ROOT / "self" / "groups.toml"

TABLE = "group"
ORDER = ("name", "members")

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

_PREAMBLE = (
    "GROUPS -- a named, reusable roster of parts/<dir>/ directory names, so "
    "circle.py --group <name> can invoke a whole roster by name. Written by "
    "/group-add; read fresh at every circle-open, never cached. A member "
    "directory removed after the group was written is circle.py's own "
    "\"unknown part(s)\" refusal to catch at open time, the same refusal "
    "--parts already gives — this register does not re-verify itself "
    "after the fact.")


def _doc() -> dict:
    if PATH.is_file():
        return SS.register_read(PATH)
    return {"register": "groups", "doc": {"preamble": _PREAMBLE}, TABLE: []}


def group_read() -> list[dict]:
    return _doc().get(TABLE, [])


def group_rows_read() -> list[tuple[str, list[str]]]:
    """(name, members), file order — groups have no natural "roster order"
    of their own the way parts do (alphabetical by directory), so insertion
    order is the stable, listed order."""
    return [(r["name"], list(r.get("members", []))) for r in group_read()]


def group_list() -> str:
    """Numbered, positional — the same contract /practice-list and
    /part-list already state: the number is a handle into THIS listing and
    shifts when a group is deleted."""
    rs = group_rows_read()
    out = [f"\n  {len(rs)} group(s)"]
    for i, (name, members) in enumerate(rs, 1):
        out.append(f"  {i:>3}  {name}  ({len(members)}: {', '.join(members)})")
    return "\n".join(out)


def _nth(n_text: str) -> "tuple[str, list[str]] | None":
    try:
        n = int(n_text.strip())
    except ValueError:
        return None
    rs = group_rows_read()
    return rs[n - 1] if 1 <= n <= len(rs) else None


def group_precheck(name: str, members: list[str]) -> str:
    """"" when group_add() would proceed, else the one-line refusal. A
    fresh roster.part_scan() every call — never an import-time copy, matching
    part_add.part_precheck()'s own discipline against a tree edited since
    import."""
    name = name.strip()
    if not name:
        return "the group needs a name"
    if not NAME_RE.match(name):
        return ("the name may only use lowercase letters, digits, '_' or "
                "'-', and must start with a letter")
    existing = {n for n, _m in group_rows_read()}
    if name in existing:
        return (f"{name!r} is already a group's name — choose another, or "
                f"delete it first")
    if not members:
        return "a group needs at least one member"
    seen: set[str] = set()
    dupes = [m for m in members if m in seen or seen.add(m)]  # type: ignore[func-returns-value]
    if dupes:
        return (f"duplicate member(s) in the same group: "
                f"{', '.join(sorted(set(dupes)))}")
    live_dirs = {d for d, _t in R.part_scan()[0]}
    unknown = [m for m in members if m not in live_dirs]
    if unknown:
        return (f"not a real part directory (parts/<dir>/): "
                f"{', '.join(unknown)} — /part-list shows what exists")
    if len(members) > MAX_MEMBERS - 1:
        return (f"{len(members)} members exceeds the roster ceiling "
                f"({MAX_MEMBERS - 1} parts; MAX_MEMBERS={MAX_MEMBERS} in "
                f"circle_close_verify.py is that many parts plus Self)")
    return ""


def group_add(name: str, members: list[str]) -> tuple[bool, str]:
    """Write one group row. IMMEDIATE: /abort does not undo it. Returns
    (ok, message)."""
    name = name.strip()
    why = group_precheck(name, members)
    if why:
        return False, why
    doc = _doc()
    doc.setdefault(TABLE, []).append({"name": name, "members": list(members)})
    SS.register_write(PATH, doc, TABLE, ORDER)
    return True, (f"{name!r} is added ({len(members)} member(s)) — "
                  f"circle.py --group {name}")


def group_view(n_text: str) -> tuple[bool, str]:
    """The named group's full member list, by listing number, flagging any
    member that no longer resolves to a real part directory."""
    hit = _nth(n_text)
    if hit is None:
        return False, f"no group #{n_text.strip() or '?'} — /group-list shows them"
    name, members = hit
    live_dirs = {d for d, _t in R.part_scan()[0]}
    lines = [f"\n  {name} — {len(members)} member(s)"]
    for m in members:
        flag = "" if m in live_dirs else "  ! not a real part any more"
        lines.append(f"    {m}{flag}")
    return True, "\n".join(lines)


def group_delete(n_text: str) -> "tuple[bool, str] | None":
    """Look up the group /group-delete <n> names, for the caller to confirm
    against before removing it. Returns None (with nothing emitted here)
    when the number doesn't resolve — the caller reports that."""
    hit = _nth(n_text)
    if hit is None:
        return None
    name, _members = hit
    return True, name


def group_delete_confirmed(name: str) -> tuple[bool, str]:
    """The second half of group_delete(): actually remove the row named `name`,
    once the caller has a typed confirmation in hand. Split so this module
    owns no interactive I/O of its own — a group carries no destructive
    file-removal risk the way a part's directory does, so the confirmation
    prompt belongs with the caller (commands.py), not here."""
    doc = _doc()
    before = len(doc.get(TABLE, []))
    doc[TABLE] = [r for r in doc.get(TABLE, []) if r.get("name") != name]
    if len(doc[TABLE]) == before:
        return False, f"{name!r} is not a group any more"
    SS.register_write(PATH, doc, TABLE, ORDER)
    return True, f"{name!r} removed."


def group_resolve(name: str) -> "list[str] | None":
    """The member list for a named group, fresh from the file — what
    `circle.py --group <name>` calls. None when the name isn't a group."""
    for n, members in group_rows_read():
        if n == name:
            return list(members)
    return None
