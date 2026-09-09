#!/usr/bin/env python3
"""
group_manager.py — the GROUP register: every group's own `groups/<name>/group.toml`, the
descriptor whose presence is what makes a folder a group (R468, 2026-09-07 — R123's part.toml
rule one level up), so `circle.py --group <name>` can open on a whole roster by name instead of
retyping `--parts <list>` every time. (group_add.py until 2026-09-05 — the module standard's
`<CLASS>_manager.py` naming, R435/R436/R442, A23/R449.)

WHY THIS EXISTS. `circle.py --parts <list>` already selects an arbitrary
subset of whatever `parts/` holds (part_roster.py, R123) — the mechanism was
already general, only the ergonomics were missing. It matters more than
convenience the moment a second, differently-purposed roster exists:
MAX_MEMBERS (circle_close_verify.py) is 9 — 8 parts + Self — so an IFS roster (the
current seven) and any future roster of a different character cannot both
live under `parts/` and be invoked together; they can only be invoked
SEPARATELY, by name. GROUPS are how "separately, by name" stays usable.
docs/CIRCLE_TYPES_DESIGN.md is the design this implements.

WHAT A GROUP IS, MECHANICALLY (R468, B120): a folder groups/<name>/ carrying `group.toml` — the
list of groups is the SCAN of those files, as the roster is the scan of parts/*/part.toml. The
descriptor carries what shipped code must not hardcode about ONE group (the operator, R468: "the
initialization sequence, reserved dirs, and user identity will become group specific"):

    name               the folder's name, what --group resolves
    display            what a person reads ("IFS Circle")
    default            true on the one group a bare open runs (at most one)
    roles              the parts/<dir>/ names under the group's own tree — the roster
    reserved           the roles /part-delete refuses
    initialization     which roles' first-run dialogs come first; the rest in roster order
    layer              the group's BLOCK 1 layer file, a path relative to the tree (B115)
    member/members     what this group calls one of its own, singular and plural — the
                       {member}/{members} tokens process_core.md carries (D104). Optional:
                       a group declaring neither gets the product's own word, "role"/"roles"
                       (process_core_prompt_projection.DEFAULT_WORDS)
    proposed_commands  the [proposed:] command list the group's parts may ask for (D95, q3)
    [identity]         role, key — which role's context answer names the console

(groups/groups.toml — one register of rows, B117 stage 3 — was the shape for four days; git keeps
it. A folder under groups/ with a record but no descriptor is REPORTED by record_verify, never
silently a group.)

A group is a NAME, not a snapshot: `--group` resolves the role list fresh at circle-open, so
renaming or removing a member part changes what every group naming it means, the same way a
part's own `long_term.md` can change under an existing name.

ROLES ARE NOT REQUIRED TO EXIST YET, mechanically — this module could write a descriptor naming
a part that hasn't been created under the group's tree. It refuses to, deliberately: `--group`
resolving to a directory `part_roster.part_scan()` doesn't recognize would fail at circle-open with a
confusing "unknown part" refusal that names a symptom, not the cause. `group_add()` checks
every role against a fresh scan of groups/<name>/parts/ (never an import-time copy), so the
descriptor can promise its own roles exist, not just promise something plausible.

THE VERBS: /group-add, /group-list, /group-view <n>, /group-update <n> (B112,
2026-09-06 — replace the roles in place, name unchanged), /group-delete <n>.
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import part_roster as R                                             # noqa: E402
from circle_close_verify import MAX_MEMBERS                            # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import record_paths as _RP                                          # noqa: E402

DEFAULT_GROUP = _RP.DEFAULT_GROUP       # the group circle.DEFAULT_PARTS reads (B117 stage 1)

# The descriptor's keys, in the order group_descriptor_dumps() writes them. `identity` is the one
# table (`[identity]`, written last so every scalar above it stays at the root — the TOML rule
# REGISTER_CLASS.register_dumps() learned at B35).
# `member`/`members` (D104, f8aaac8) landed in groups/ifs/group.toml and in the reader
# (group_member_words_read below) without reaching this tuple, and group_descriptor_dumps()
# raises on any key outside it — so /group-update could not complete for the DEFAULT group.
# Invisible to bnf_conformance.py because the nine-field list was copied three times (here,
# docs/PRODUCT_BNF.md's <group>, and the checker's own SITES row) and the checker compares
# doc against constant without opening a real group.toml. Three agreeing copies read as PASS.
ORDER = ("name", "display", "default", "roles", "reserved", "initialization", "layer",
         "member", "members", "proposed_commands", "identity")

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

_HEADER = (
    "# group.toml — the presence of THIS FILE is what makes this folder a GROUP (R468,\n"
    "# 2026-09-07; R123's part.toml rule one level up). coordinator/group_manager.py writes\n"
    "# it; record_paths.py reads it. It carries what shipped code must not hardcode about\n"
    "# ONE group: its roles, the roles /part-delete refuses, which roles' first-run dialogs\n"
    "# come first, which role's answer names the console, its BLOCK 1 layer, the commands its\n"
    "# parts may propose. The folder's name is the group's name.\n")


def _lit(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def group_descriptor_dumps(doc: dict) -> str:
    """The descriptor's text — deterministic, keys in ORDER, `[identity]` last."""
    out = [_HEADER]
    for k in ORDER:
        if k == "identity":
            continue
        if k not in doc:
            continue
        v = doc[k]
        if isinstance(v, bool):
            out.append(f"{k} = {str(v).lower()}")
        elif isinstance(v, list):
            if not v:
                out.append(f"{k} = []")
            else:
                out.append(f"{k} = [")
                out += [f"    {_lit(x)}," for x in v]
                out.append("]")
        else:
            out.append(f"{k} = {_lit(v)}")
    for k in doc:
        if k not in ORDER:
            raise ValueError(f"group.toml has unknown key {k!r}")
    ident = doc.get("identity") or {}
    if ident:
        out.append("\n[identity]")
        for k in ("role", "key"):
            if k in ident:
                out.append(f"{k} = {_lit(ident[k])}")
    return "\n".join(out).rstrip("\n") + "\n"


def group_descriptor_write(name: str, doc: dict) -> pathlib.Path:
    """Write groups/<name>/group.toml — validate it reloads to the same document, then the
    atomic replace (REGISTER_CLASS.register_write()'s own order)."""
    try:
        import tomllib
    except ModuleNotFoundError:                                 # py < 3.11
        import tomli as tomllib                                 # type: ignore
    from atomic_write import record_atomic_write
    text = group_descriptor_dumps(doc)
    back = tomllib.loads(text)
    if back != doc:
        raise ValueError("group.toml does not round-trip — refusing to write")
    p = _RP.group_descriptor_locate(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    record_atomic_write(p, text)
    return p


def group_read() -> list[dict]:
    """Every group's descriptor, the default group first (record_paths.group_present_read()'s
    order) — the listing /group-list numbers."""
    out = []
    for name in _RP.group_present_read():
        doc = _RP.group_descriptor_read(name)
        if doc:
            doc.setdefault("name", name)
            out.append(doc)
    return out


def group_rows_read() -> list[tuple[str, list[str]]]:
    """(name, roles) in listing order — the default group first, the rest by folder name."""
    return [(d["name"], list(d.get("roles", []))) for d in group_read()]


def group_list() -> str:
    """Numbered, positional — the same contract /practice-list and
    /part-list already state: the number is a handle into THIS listing and
    shifts when a group is deleted."""
    rs = group_rows_read()
    out = [f"\n  {len(rs)} group(s)"]
    for i, (name, roles) in enumerate(rs, 1):
        out.append(f"  {i:>3}  {name}  ({len(roles)}: {', '.join(roles)})")
    return "\n".join(out)


def _nth(n_text: str) -> "tuple[str, list[str]] | None":
    try:
        n = int(n_text.strip())
    except ValueError:
        return None
    rs = group_rows_read()
    return rs[n - 1] if 1 <= n <= len(rs) else None


def _parts_base(name: str) -> pathlib.Path:
    """The parts/ directory a group's roles live in — under the group's own tree (R467)."""
    return _RP.group_tree(name) / "parts"


def group_precheck(name: str, roles: list[str]) -> str:
    """"" when group_add() would proceed, else the one-line refusal. A
    fresh part_roster.part_scan() of the group's own parts/ every call — never an import-time copy,
    matching part_add.part_precheck()'s own discipline against a tree edited since import."""
    name = name.strip()
    if not name:
        return "the group needs a name"
    if not NAME_RE.match(name):
        return ("the name may only use lowercase letters, digits, '_' or "
                "'-', and must start with a letter")
    if name in _RP.group_present_read():
        return (f"{name!r} is already a group's name — choose another, or "
                f"delete it first")
    return _members_precheck(roles, name)


def _members_precheck(roles: list[str], name: str) -> str:
    """The role half of group_precheck() — what group_update() re-runs on
    a replacement list, where the name half does not apply (the name is
    the descriptor's own and stays). Split out at B112 (2026-09-06); since B120 the scan is
    the group's own groups/<name>/parts/."""
    if not roles:
        return "a group needs at least one role"
    seen: set[str] = set()
    dupes = [m for m in roles if m in seen or seen.add(m)]  # type: ignore[func-returns-value]
    if dupes:
        return (f"duplicate role(s) in the same group: "
                f"{', '.join(sorted(set(dupes)))}")
    live_dirs = {d for d, _t in R.part_scan(_parts_base(name))[0]}
    unknown = [m for m in roles if m not in live_dirs]
    if unknown:
        return (f"not a real part directory (groups/{name}/parts/<dir>/): "
                f"{', '.join(unknown)} — /part-list shows what exists")
    if len(roles) > MAX_MEMBERS - 1:
        return (f"{len(roles)} roles exceeds the roster ceiling "
                f"({MAX_MEMBERS - 1} parts; MAX_MEMBERS={MAX_MEMBERS} in "
                f"circle_close_verify.py is that many parts plus Self)")
    return ""


def group_layer_read(name: str) -> "str | None":
    """The `layer` path a group's descriptor names, or None — none declared, or `name` is not
    a group. B115: what circle.py hands process_core_prompt_projection.circle_identity_layer_set()."""
    layer = _RP.group_descriptor_read(name).get("layer")
    return str(layer).strip() or None if layer else None


def group_member_words_read(name: str) -> "tuple[str, str] | None":
    """A group's own word for one of its members, singular and plural — its descriptor's `member`
    and `members`, or None when it declares neither. D104, on D99: PART is the IFS group's word for
    a ROLE, so the universal rulebook carries a token and each group fills it. A group that declares
    nothing gets process_core_prompt_projection.DEFAULT_WORDS, the product's own."""
    d = _RP.group_descriptor_read(name)
    one, many = str(d.get("member", "")).strip(), str(d.get("members", "")).strip()
    return (one, many) if one and many else None


def _layer_precheck(layer: "str | None") -> str:
    """"" when the layer path is absent or names a real file under the tree, else the refusal."""
    if not layer:
        return ""
    p = pathlib.Path(layer)
    if p.is_absolute() or ".." in p.parts:
        return "the layer is a path relative to the tree (coordinator/process_ifs.md), not absolute"
    if not (ROOT / p).is_file():
        return f"no such layer file: {layer}"
    return ""


def group_add(name: str, roles: list[str], layer: "str | None" = None) -> tuple[bool, str]:
    """Write one group's descriptor. IMMEDIATE: /abort does not undo it. Returns
    (ok, message). `layer` (B115) is optional. The roles must already exist under
    groups/<name>/parts/ — the folder is the group's, made first."""
    name = name.strip()
    why = group_precheck(name, roles) or _layer_precheck(layer)
    if why:
        return False, why
    doc: dict = {"name": name, "display": name, "default": False, "roles": list(roles),
                 "reserved": [], "initialization": [], "proposed_commands": []}
    if layer:
        doc["layer"] = layer.strip()
    group_descriptor_write(name, doc)
    return True, (f"{name!r} is added ({len(roles)} role(s)) — "
                  f"circle.py --group {name}")


def group_view(n_text: str) -> tuple[bool, str]:
    """The named group's full role list, by listing number, flagging any
    role that no longer resolves to a real part directory."""
    hit = _nth(n_text)
    if hit is None:
        return False, f"no group #{n_text.strip() or '?'} — /group-list shows them"
    name, roles = hit
    live_dirs = {d for d, _t in R.part_scan(_parts_base(name))[0]}
    lines = [f"\n  {name} — {len(roles)} role(s)"]
    for m in roles:
        flag = "" if m in live_dirs else "  ! not a real part any more"
        lines.append(f"    {m}{flag}")
    return True, "\n".join(lines)


def group_update(n_text: str, roles: list[str],
                 layer: "str | None" = None) -> tuple[bool, str]:
    """Replace one group's role list in place — same descriptor, same position
    in /group-list, the NAME unchanged. B112, 2026-09-06 (the operator:
    "Desirable, to be sized"); the shape is redaction_manager.alias_update()'s.

    THE NAME IS NOT EDITABLE HERE, on purpose. A name is what
    `circle.py --group <name>` resolves — and since R468 it is the folder's name — so a
    renamed group would silently invalidate an invocation someone already depends on, the
    same reason group_delete() asks for the name typed back. Renaming is delete + add.
    The replacement list passes every role rule group_add() applies
    (real directories, no duplicates, the roster ceiling), and IMMEDIATELY:
    /abort does not undo it."""
    hit = _nth(n_text)
    if hit is None:
        return False, f"no group #{n_text.strip() or '?'} — /group-list shows them"
    name, _old = hit
    why = _members_precheck(roles, name) or _layer_precheck(layer)
    if why:
        return False, why
    doc = _RP.group_descriptor_read(name)
    doc["roles"] = list(roles)
    if layer:                               # given: replaced; omitted: the descriptor's own stays
        doc["layer"] = layer.strip()
    group_descriptor_write(name, doc)
    return True, (f"{name!r} is updated ({len(roles)} role(s)) — "
                  f"circle.py --group {name}")


def group_delete(n_text: str) -> "tuple[bool, str] | None":
    """Look up the group /group-delete <n> names, for the caller to confirm
    against before removing it. Returns None (with nothing emitted here)
    when the number doesn't resolve — the caller reports that."""
    hit = _nth(n_text)
    if hit is None:
        return None
    name, _roles = hit
    return True, name


def group_delete_confirmed(name: str) -> tuple[bool, str]:
    """The second half of group_delete(): remove the descriptor named `name`, once the caller
    has a typed confirmation in hand. Split so this module owns no interactive I/O of its own.
    REFUSED while the group's folder holds a record (parts, self, issues, circles): a folder
    with a record and no descriptor is a stray record_verify reports, so the record leaves
    first — by hand, git keeping every version — and the descriptor after."""
    p = _RP.group_descriptor_locate(name)
    if not p.is_file():
        return False, f"{name!r} is not a group any more"
    tree = _RP.group_tree(name)
    held = [k for k in _RP.RECORD_KINDS if (tree / k).is_dir()]
    if held:
        return False, (f"{name!r} still holds a record ({', '.join(held)}/ under "
                       f"groups/{name}/) — a group with a record is not deleted from here; "
                       f"remove the folder's record first, git keeping every version")
    p.unlink()
    try:
        tree.rmdir()                        # the folder held only the descriptor
    except OSError:
        pass
    return True, f"{name!r} removed."


def group_resolve(name: str) -> "list[str] | None":
    """The role list for a named group, fresh from its descriptor — what
    `circle.py --group <name>` calls. None when the name isn't a group."""
    doc = _RP.group_descriptor_read(name)
    if not doc:
        return None
    return list(doc.get("roles", []))
