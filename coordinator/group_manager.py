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
    reserved           the roles /part-retire refuses
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

/GROUP-ADD SCAFFOLDS THE RECORD THE DESCRIPTOR PROMISES (2026-09-11, another session's close-out
of that day). A descriptor naming a role with no part directory under the group's tree fails at
circle-open with an "unknown part" refusal that names a symptom, not the cause, and nothing else
can make that directory first: part_add.py writes into the BOUND group's parts/ and the only binder
is `circle.py --group`, which refuses a name that is not yet a group. So group_add() writes what a
circle on the new group needs to open, round and close, RECORD FIRST and the descriptor LAST
(part_add.part_add()'s own order, one level up): for every role with no part directory,
parts/<role>/long_term.md (a stub identity the
operator rewrites) then parts/<role>/part.toml; issues/issue_model.md (a stub prologue — BLOCK 2
fails closed without it); self/self.md seeded with the two headings synthesis holds a SELF
replacement to (circle_synthesis.py; an absent file reads as no headings, so the refusal would fire
at every live close); circles/README.md so git keeps the folder; then group.toml. A crash midway
leaves a folder with a record and no descriptor — a stray memory/record_verify.py REPORTS, never a
group with a hole; running the verb again finishes it, since a role that already exists is left
alone and still counts. Every role is re-scanned (part_roster.part_scan(), fresh) before the
descriptor is written. group_update() still requires its roles to exist: an update names parts, it
does not make them. A group so made holds a record, so group_delete_confirmed() refuses it until
the record is moved out by hand.

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
from REGISTER_CLASS import register_list_footer, register_record_show, register_row_nth_read  # noqa: E402

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
    "# ONE group: its roles, the roles /part-retire refuses, which roles' first-run dialogs\n"
    "# come first, which role's answer names the console, its BLOCK 1 layer, the commands its\n"
    "# parts may propose. The folder's name is the group's name.\n")


def _lit(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _list_render(k: str, v: list) -> str:
    """One list key in the descriptor's own form — what group_descriptor_dumps() writes, and
    what group_roles_edit() puts back in place of the list it changes."""
    if not v:
        return f"{k} = []"
    return "\n".join([f"{k} = ["] + [f"    {_lit(x)}," for x in v] + ["]"])


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
            out.append(_list_render(k, v))
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


def group_roles_edit(tree: pathlib.Path, *, add: str = "", drop: str = "") -> "pathlib.Path | None":
    """One role onto, or off, a group's list — the parts commands' half of the descriptor
    (R548, D127: *"D127 - yes, the part must be included next circle."*).
    /part-add puts `add` on `roles`; /part-retire takes `drop` off `roles` and `initialization`.

    `tree` is the group's folder, the parent of the parts/ the command acts on, so a probe's temp
    tree is the one edited. ONLY THE CHANGED LISTS ARE REWRITTEN, in place and in the form
    group_descriptor_dumps() gives them, so the rest of the file — its comments included — keeps
    its bytes; the result must parse to the same document with only those lists changed, or
    nothing is written. An empty or absent `roles` is left alone: a group with none opens on the
    scan of its parts/ (circle._default_parts_read()), which already holds the new folder.

    Returns the descriptor's path when it was rewritten; None when the folder has no descriptor
    or nothing needed to change. Raises when the descriptor does not parse or the edit does not
    verify — the caller says the part's folder and the list now disagree."""
    try:
        import tomllib
    except ModuleNotFoundError:                                 # py < 3.11
        import tomli as tomllib                                 # type: ignore
    from atomic_write import record_atomic_write
    p = pathlib.Path(tree) / _RP.GROUP_MARKER
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8")
    doc = tomllib.loads(text)
    want = dict(doc)
    roles = doc.get("roles")
    if add and isinstance(roles, list) and roles and add not in roles:
        want["roles"] = roles + [add]
    if drop:
        for k in ("roles", "initialization"):
            if isinstance(doc.get(k), list) and drop in doc[k]:
                want[k] = [r for r in doc[k] if r != drop]
    changed = [k for k in ("roles", "initialization") if want.get(k) != doc.get(k)]
    if not changed:
        return None
    for k in changed:
        pat = re.compile(rf"^{k} = \[[^\]]*\]", re.M)
        if len(pat.findall(text)) != 1:
            raise ValueError(f"{p.name}: `{k}` is not one list in the form this module writes")
        text = pat.sub(lambda _m, k=k: _list_render(k, want[k]), text)
    if tomllib.loads(text) != want:
        raise ValueError(f"{p.name}: the edit does not parse back to the list it meant")
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
    out.append("\n" + register_list_footer(len(rs), "/group-list"))
    return "\n".join(out)


def _parts_base(name: str) -> pathlib.Path:
    """The parts/ directory a group's roles live in — under the group's own tree (R467)."""
    return _RP.group_tree(name) / "parts"


def group_precheck(name: str, roles: list[str]) -> str:
    """"" when group_add() would proceed, else the one-line refusal. A
    fresh part_roster.part_scan() of the group's own parts/ every call — never an import-time copy,
    matching part_add.part_precheck()'s own discipline against a tree edited since import. A role
    with no part directory yet is NOT a refusal here: group_add() scaffolds it."""
    name = name.strip()
    if not name:
        return "the group needs a name"
    if not NAME_RE.match(name):
        return ("the name may only use lowercase letters, digits, '_' or "
                "'-', and must start with a letter")
    if name in _RP.group_present_read():
        return (f"{name!r} is already a group's name — choose another, or "
                f"delete it first")
    return _members_precheck(roles, name, must_exist=False)


def _role_tag_derive(role: str) -> str:
    """The stub Tag for a scaffolded role: `lead_guitar` -> "Lead Guitar". part_add's own
    derivation runs Tag -> directory and cannot be reversed exactly, so this is the operator's
    to edit in part.toml."""
    return role.replace("_", " ").title()


def _members_precheck(roles: list[str], name: str, *, must_exist: bool = True) -> str:
    """The role half of group_precheck() — what group_update() re-runs on
    a replacement list, where the name half does not apply (the name is
    the descriptor's own and stays). Split out at B112 (2026-09-06); since B120 the scan is
    the group's own groups/<name>/parts/.

    `must_exist` True (group_update): every role is a live part directory. False (group_add,
    2026-09-11): a role with no directory is scaffolded, so it needs a usable directory name
    and a Tag that is not Self's; a directory that exists but does not scan as a part is
    refused, naming the scan's own problem — never written into."""
    if not roles:
        return "a group needs at least one role"
    seen: set[str] = set()
    dupes = [m for m in roles if m in seen or seen.add(m)]  # type: ignore[func-returns-value]
    if dupes:
        return (f"duplicate role(s) in the same group: "
                f"{', '.join(sorted(set(dupes)))}")
    base = _parts_base(name)
    roster, _alt, _tails, probs = R.part_scan(base)
    live_dirs = {d for d, _t in roster}
    unknown = [m for m in roles if m not in live_dirs]
    if unknown and must_exist:
        return (f"not a real part directory (groups/{name}/parts/<dir>/): "
                f"{', '.join(unknown)} — /part-list shows what exists")
    if unknown:
        from part_add import NAME_RE as PART_NAME_RE
        bad = [m for m in unknown if not PART_NAME_RE.match(m) or m in R.SKIP_DIRS]
        if bad:
            return (f"not a usable directory name for a role (letters, digits, underscore, "
                    f"starting with a letter): {', '.join(bad)}")
        try:
            import identity as ID
            reserved = {ID.user_name_read().lower(), ID.DEFAULT_NAME.lower(), ID.SELF_ID.lower()}
        except Exception:                                           # noqa: BLE001
            reserved = {"self"}
        taken = [m for m in unknown if _role_tag_derive(m).lower() in reserved]
        if taken:
            return f"{', '.join(taken)}: that is Self's name — a role cannot share it"
        held = [m for m in unknown if (base / m).exists()]
        if held:
            why = next((p for p in probs if f"parts/{held[0]}/" in p), "not a part")
            return (f"groups/{name}/parts/{held[0]}/ exists but is not a part ({why}) — "
                    f"fix it or move it out of parts/ first")
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


# The stub files group_add() scaffolds when absent — each the run-proven minimum for a circle on
# the new group to open, round and close (2026-09-11), and each the operator's to rewrite.
_ROLE_IDENTITY = "A role of the {name} group — describe this member here."
_ISSUE_MODEL_STUB = """## What is here

An **issue**, for the {name} group, is a piece of work left open — something owed, seen and
recorded so the group can choose knowingly what to take up next, not so a failure can be scored.
This file opens what every circle the group holds is shown about its issues; /group-add wrote
this paragraph as a stub, and the operator replaces it with what is owed, to whom, and what does
not count as an issue for this group.
"""
_SELF_PLACEHOLDER = ("(not yet written — /group-add made this file; the operator writes who Self "
                     "is for this group here)")
_SELF_STUB = f"""# Self — System Overview
Last updated: never — no code sets this line; synthesis replaces the whole file
when a circle moves the account of Self, and whatever it writes here stands

## Who Self is

{_SELF_PLACEHOLDER}

## Psychological context

{_SELF_PLACEHOLDER}
"""
_CIRCLES_README = """# groups/{name}/circles/

The {name} group's own transcript series — one file per circle the group holds, written by the
coordinator, never by a member (R467: circles are per group). Empty until the group's first
circle; this README is what keeps the directory present in a clone, since git does not track
an empty directory.
"""


def _record_scaffold(name: str, roles: list[str]) -> list[str]:
    """Write what groups/<name>/ lacks for a circle to open, round and close — parts first (each
    role's long_term.md THEN its part.toml, part_add.part_add()'s order), then the three stub
    files, each only if absent. Returns what was written, tree-relative, in order."""
    from atomic_write import record_atomic_write
    from part_add import part_long_term_seed_render
    tree = _RP.group_tree(name)
    base = _parts_base(name)
    live = {d for d, _t in R.part_scan(base)[0]} if base.is_dir() else set()
    wrote: list[str] = []
    for role in roles:
        if role in live:
            continue
        d = base / role
        d.mkdir(parents=True, exist_ok=False)
        tag = _role_tag_derive(role)
        record_atomic_write(d / "long_term.md",
                            part_long_term_seed_render(tag, _ROLE_IDENTITY.format(name=name)))
        record_atomic_write(d / R.MARKER,
                            "# part.toml — the presence of THIS FILE is what makes this "
                            "directory a part.\n# Created by /group-add (coordinator/"
                            "group_manager.py). part_roster.py reads it; the Tag is the\n"
                            "# display name the directory name cannot give — a stub derived "
                            "from the role, yours to edit.\n\n"
                            f'tag = "{tag}"\n\nalt_tags = []\n')
        wrote.append(f"parts/{role}/")
    for rel, text in (("issues/issue_model.md", _ISSUE_MODEL_STUB.format(name=name)),
                      ("self/self.md", _SELF_STUB),
                      ("circles/README.md", _CIRCLES_README.format(name=name))):
        p = tree / rel
        if p.is_file():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        record_atomic_write(p, text)
        wrote.append(rel)
    return wrote


def group_add(name: str, roles: list[str], layer: "str | None" = None) -> tuple[bool, str]:
    """Make one group: the RECORD its descriptor promises first, the descriptor LAST (the head
    docstring). IMMEDIATE: /abort does not undo it. Returns (ok, message). `layer` (B115) is
    optional; without one the group runs on the IFS layer with the product's own words
    (process_core_prompt_projection.DEFAULT_LAYER / DEFAULT_WORDS), and the message says so."""
    name = name.strip()
    why = group_precheck(name, roles) or _layer_precheck(layer)
    if why:
        return False, why
    wrote = _record_scaffold(name, roles)
    roster, _a, _t, probs = R.part_scan(_parts_base(name))
    missing = [r for r in roles if r not in {d for d, _t in roster}]
    if missing:
        return False, (f"groups/{name}/parts/ written but {', '.join(missing)} does not scan as a "
                       f"part ({probs[0] if probs else 'no tag'}) — the folder is a stray "
                       f"record_verify reports; fix it and run /group-add again")
    doc: dict = {"name": name, "display": name, "default": False, "roles": list(roles),
                 "reserved": [], "initialization": [], "proposed_commands": []}
    if layer:
        doc["layer"] = layer.strip()
    try:
        group_descriptor_write(name, doc)
    except Exception as e:                                          # noqa: BLE001
        return False, (f"the record is written but not the descriptor ({e}) — groups/{name}/ "
                       f"is a stray record_verify reports until /group-add \"{name}\" runs again")
    parts_made = [w for w in wrote if w.startswith("parts/")]
    stubs = [w for w in wrote if not w.startswith("parts/")]
    lines = [f"{name!r} is added ({len(roles)} role(s)) — circle.py --group {name}"]
    if parts_made:
        lines.append(f"  scaffolded {len(parts_made)} part(s) under groups/{name}/parts/ "
                     f"({', '.join(w[len('parts/'):-1] for w in parts_made)}): a stub "
                     f"long_term.md and part.toml each, yours to write")
    kept = len(roles) - len(parts_made)
    if kept:
        lines.append(f"  {kept} role(s) already a part, left as they are")
    if stubs:
        lines.append(f"  stub files: {', '.join(stubs)} — the operator writes them; the folders "
                     f"issues/, self/ and circles/ are the group's record")
    if not layer:
        lines.append(f"  no layer given: the group runs on the IFS rulebook with \"role\" "
                     f"substituted for \"part\" until group.toml names a layer file")
    return True, "\n".join(lines)


def group_view(n_text: str) -> tuple[bool, str]:
    """The group's DESCRIPTOR, whole, by listing number — every key its group.toml carries,
    through REGISTER_CLASS.register_record_show() (B133) — then its roles checked against the
    group's own parts/, flagging any that no longer resolves to a real part directory.
    `/group-list <n>` answers with this view at any dev state (R534); `/group-view <n>` is the
    second door to it."""
    docs = group_read()
    hit = register_row_nth_read(docs, n_text)
    if hit is None:
        return False, f"no group #{n_text.strip() or '?'} — /group-list shows them"
    name, roles = hit["name"], list(hit.get("roles", []))
    live_dirs = {d for d, _t in R.part_scan(_parts_base(name))[0]}
    lines = ["", register_record_show(docs, int(n_text.strip()), ORDER, verb="/group-list"),
             "", f"  {name} — {len(roles)} role(s), checked against groups/{name}/parts/"]
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
    hit = register_row_nth_read(group_rows_read(), n_text)
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
    hit = register_row_nth_read(group_rows_read(), n_text)
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
