#!/usr/bin/env python3
"""
part_add.py — the part-lifecycle register: create, list, view, delete a
`parts/<name>/` directory. A14's creation path, built 2026-08-23 to
`docs/part_commands_design.md` as `docs/Initialization.md` §8 reconciled it
(describe before name; the directory NAME derived from the Tag — an end user
is never asked for a directory name).

WHAT A PART IS, MECHANICALLY: a directory under `parts/` whose `part.toml`
names its Tag (part_roster.py — the marker's presence IS membership) and whose
`long_term.md` is its identity. `prompt_build.record_ro_read()` reads long_term.md
with a bare read_text() and fails loudly, so an empty identity is the one
thing that crashes prompt assembly — `part_add()` refuses it, and writes
long_term.md FIRST, part.toml LAST: a crash between the two leaves a
non-part directory `part_roster.part_verify()` reports, never a part with no identity
that takes a circle down.

THE SEED IS THE PERSON'S OWN WORDS, VERBATIM, under a heading that says so —
not a model rewrite. The record's first entry is theirs; dreaming exists to
evolve the identity from there.

A PART ADDED NOW JOINS THE NEXT CIRCLE. Six modules copy the roster at
import (`circle.DEFAULT_PARTS`, `record_paths.PART_TAGS`, ...), so a directory
created mid-process is invisible to this process — safe, and said.

DELETE IS GIT-RECOVERABLE, NEVER ARCHIVED (the 2026-08-19 ruling that
removed the archiving mechanism): the directory is removed and the deletion
committed; `git log --all -- parts/<name>/` finds the record and
`git checkout <rev> -- parts/<name>/` restores it whole. The group's RESERVED
roles (its group.toml, R468 — Soul and Child for the IFS group, docs/BNF.md) are
refused before any dialog; a delete while a
circle may be open is refused outright (circle_state fails closed) — the
next round's read of a vanished long_term.md would take the circle down.

Positional numbers, not ids: `view`/`delete` take the number `part_list()`
printed, which shifts when a part is removed — the same contract
/practice-list has always stated.
"""

from __future__ import annotations

import re

import part_roster as R
import seam
from circle_close_verify import MAX_MEMBERS

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# The identity seed's shape — the person's words, marked as the person's.
LONG_TERM_TEMPLATE = """# The {tag} — Long-Term Memory
Bootstrap: (set at first circle)

## How my human describes me

{identity}

## required end
"""


def part_name_derive(tag: str) -> str:
    """The directory name, from the Tag: lower-cased, every run of
    characters outside [a-z0-9] collapsed to one underscore, trimmed.
    "" when nothing survives (an all-symbol tag) — the caller asks then."""
    return re.sub(r"[^a-z0-9]+", "_", tag.lower()).strip("_")


def part_precheck(name: str, tag: str, identity: str) -> str:
    """"" when part_add() would proceed, else the one-line refusal —
    docs/part_commands_design.md's PART_ADD_VALIDATION, live against the
    tree as it stands right now (a fresh scan, not the import-time copy)."""
    roster, alt, _tails, _probs = R.part_scan()
    if not identity.strip():
        return ("the description is required — long_term.md is read with a "
                "bare read_text() and an empty identity crashes prompt "
                "assembly")
    if len(identity.split()) > 40:
        return f"the description is {len(identity.split())} words; at most 40"
    if not tag.strip():
        return "the part needs a name"
    bad = [c for c in R.BAD_IN_TAG if c in tag]
    if bad:
        return (f"the name may not contain {', '.join(repr(c) for c in bad)}"
                f" — `[Tag]:` is the transcript grammar")
    taken = {t.lower() for _d, t in roster}
    if tag.strip().lower() in taken:
        return f"{tag.strip()!r} is already a part's name — choose another"
    try:
        import identity as ID
        reserved = {ID.user_name_read().lower(), ID.DEFAULT_NAME.lower(),
                    ID.SELF_ID.lower()}
    except Exception:                                           # noqa: BLE001
        reserved = {"self"}
    if tag.strip().lower() in reserved:
        return f"{tag.strip()!r} is Self's name — a part cannot share it"
    if not name or not NAME_RE.match(name) or name in R.SKIP_DIRS:
        return (f"no usable directory name derives from {tag.strip()!r} — "
                f"give one (letters, digits, underscore, starting with a "
                f"letter)")
    if (R.PARTS_DIR / name).exists():
        return f"parts/{name}/ already exists"
    if len(roster) + 1 > MAX_MEMBERS - 1:      # 9 = 8 parts + lead
        return (f"the roster is at its ceiling ({MAX_MEMBERS - 1} parts; "
                f"MAX_MEMBERS={MAX_MEMBERS} in circle_close_verify.py is 8 parts + "
                f"lead) — raising it is its own deliberate act")
    return ""


def part_add(name: str, tag: str, identity: str) -> tuple[bool, str]:
    """Create parts/<name>/ — long_term.md first, part.toml last (the marker
    makes it a part, so the identity must exist before membership does).
    IMMEDIATE: /abort does not undo it. Returns (ok, message)."""
    why = part_precheck(name, tag, identity)
    if why:
        return False, why
    from atomic_write import record_atomic_write
    d = R.PARTS_DIR / name
    d.mkdir(parents=True)
    record_atomic_write(d / "long_term.md",
                 LONG_TERM_TEMPLATE.format(tag=tag.strip(),
                                           identity=identity.strip()))
    record_atomic_write(d / R.MARKER,
                 "# part.toml — the presence of THIS FILE is what makes this "
                 "directory a part.\n# Created by /part-add (docs/"
                 "Initialization.md). part_roster.py reads it; the Tag is the\n"
                 "# display name the directory name cannot give.\n\n"
                 f'tag = "{tag.strip()}"\n\nalt_tags = []\n')
    _r, _a, _t, probs = R.part_scan()
    mine = [p for p in probs if f"parts/{name}/" in p]
    if mine:
        return False, f"written but does not scan clean: {mine[0]}"
    return True, (f"{tag.strip()} is added (parts/{name}/). It joins from "
                  f"the next circle.")


def part_rows_read() -> list[tuple[str, str]]:
    """(dir, Tag), roster order, from a fresh scan."""
    roster, _a, _t, _p = R.part_scan()
    return roster


def part_list() -> str:
    """Numbered, positional — /practice-list's contract: the number is a
    handle into THIS listing and shifts when a part is removed."""
    out = [f"\n  {len(part_rows_read())} part(s)"]
    for i, (d, t) in enumerate(part_rows_read(), 1):
        out.append(f"  {i:>3}  {t}  (parts/{d}/)")
    return "\n".join(out)


def _nth(n_text: str) -> "tuple[str, str] | None":
    try:
        n = int(n_text.strip())
    except ValueError:
        return None
    r = part_rows_read()
    return r[n - 1] if 1 <= n <= len(r) else None


def part_view(n_text: str) -> tuple[bool, str]:
    """parts/<name>/long_term.md, verbatim, by listing number."""
    hit = _nth(n_text)
    if hit is None:
        return False, f"no part #{n_text.strip() or '?'} — /part-list shows them"
    d, t = hit
    p = R.PARTS_DIR / d / "long_term.md"
    if not p.is_file():
        return False, f"parts/{d}/long_term.md is MISSING — that part cannot speak"
    return True, f"\n  {t} — parts/{d}/long_term.md\n\n" + p.read_text(encoding="utf-8")


def part_reserved_read() -> tuple[str, ...]:
    """The roles /part-delete refuses — the bound group's group.toml `reserved` list (R468,
    B120; RESERVED_DIRS = ("soul", "child") was the literal until then, and is the IFS group's
    own value of it)."""
    import record_paths as _RP
    return tuple(str(d) for d in _RP.group_descriptor_read(_RP.group_read()).get("reserved", []))


def part_delete(n_text: str) -> None:
    """/part-delete <n> — confirmation is TYPING THE DIRECTORY NAME (a
    destructive act gets a harder yes than 'yes'), then the directory is
    removed and the deletion COMMITTED — git is the record. Refused for the
    group's RESERVED roles, and while a circle may be open (circle_state fails
    closed; a live round reading a vanished long_term.md is a crash, not an
    absence)."""
    import shutil
    hit = _nth(n_text)
    if hit is None:
        seam.emit("command", f"  no part #{n_text.strip() or '?'} — "
                             f"/part-list shows them")
        return
    d, t = hit
    if d in part_reserved_read():
        import record_paths as _RP
        seam.emit("command", f"  {t} is a RESERVED role of this group "
                             f"(groups/{_RP.group_read()}/group.toml) — never deleted")
        return
    try:
        import circle_state
        open_now = bool(circle_state.circle_open_read())
    except Exception:                                           # noqa: BLE001
        open_now = True                                          # fails closed
    if open_now:
        seam.emit("command", "  a circle may be open — close it first: a "
                             "live round reading a deleted part is a crash")
        return
    files = sorted((R.PARTS_DIR / d).rglob("*"))
    seam.emit("command", f"\n  deleting {t} removes parts/{d}/ — "
                         f"{len([f for f in files if f.is_file()])} file(s):")
    for f in files:
        if f.is_file():
            # relative to PARTS_DIR's parent, not a fixed ROOT — a probe
            # rebinds PARTS_DIR to a temp tree and the listing must follow.
            seam.emit("command", f"    parts/{f.relative_to(R.PARTS_DIR)}")
    seam.emit("command", "  git keeps every version (git log --all -- "
                         f"parts/{d}/); /abort does NOT undo this, and a "
                         f"restored part re-enters with a memory gap.")
    ans = seam.read_line(f"  type the directory name ({d}) to delete: ",
                         channel="command").strip()
    if ans != d:
        seam.emit("command", "  cancelled — nothing removed.")
        return
    shutil.rmtree(R.PARTS_DIR / d)
    seam.emit("command", f"  parts/{d}/ removed.")
    try:
        import gitrepo as G
        G.system_git_paths_commit([R.PARTS_DIR / d],
                       f"part-delete: {d}",
                       lambda kind, msg: seam.emit("command", f"  {msg}"))
    except Exception as e:                                      # noqa: BLE001
        seam.emit("command", f"  (the deletion is not committed — {e}; "
                             f"commit it by hand)")
