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
MAX_MEMBERS (circle_close_verify.py) is 9 — 8 parts + Self — so the default group's roster
(the current seven) and any future roster of a different character cannot both
live under `parts/` and be invoked together; they can only be invoked
SEPARATELY, by name. GROUPS are how "separately, by name" stays usable.
docs/CIRCLE_TYPES_DESIGN.md is the design this implements.

WHAT A GROUP IS, MECHANICALLY (R468, B120): a folder groups/<name>/ carrying `group.toml` — the
list of groups is the SCAN of those files, as the roster is the scan of parts/*/part.toml. The
descriptor carries what shipped code must not hardcode about ONE group (the operator, R468: "the
initialization sequence, reserved dirs, and user identity will become group specific"):

    name               the folder's name, what --group resolves
    display            what a person reads ("Band")
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
at every live close); circles/README.md so git keeps the folder; the ten EMPTY REGISTERS under
self/ and circles/, each rendered by its owner (2026-10-16 — the gates over them refused a group
born without them); then group.toml. group_record_survey() names what a group lacks and what is
still a stub; group_record_fill() writes what it lacks; group_record_verify.py runs both over
every group. A crash midway
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
# `member`/`members` (D104, f8aaac8) landed in the default group's group.toml and in the reader
# (group_member_words_read below) without reaching this tuple, and group_descriptor_dumps()
# raises on any key outside it — so /group-update could not complete for the DEFAULT group.
# Invisible to bnf_conformance.py because the nine-field list was copied three times (here,
# docs/PRODUCT_BNF.md's <group>, and the checker's own SITES row) and the checker compares
# doc against constant without opening a real group.toml. Three agreeing copies read as PASS.
ORDER = ("name", "display", "default", "roles", "reserved", "initialization", "layer",
         "member", "members", "proposed_commands", "identity")

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

_HEADER = (
    "# group.toml — the presence of THIS FILE is what makes this folder a GROUP, as\n"
    "# part.toml's presence makes a directory a part. coordinator/group_manager.py writes\n"
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
            return (f"not a usable directory name for a role (lowercase letters, digits, "
                    f"underscore, starting with a letter): {', '.join(bad)}")
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
    and `members`, or None when it declares neither. D104, on D99: PART is the default group's word for
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
        return "the layer is a path relative to the tree (groups/<name>/process_<name>.md), not absolute"
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
# The shipped seed (packaging/scaffold/groups/<g>/self/self.md) is a placeholder too: guidance in
# each section, not an account of anyone. Its sections' opening words, which a recipient's own
# writing — by hand, on the initialization form, or by synthesis — replaces.
_SELF_SHIPPED_MARKS = ("Who Self is *for this installation*.",
                       "Whatever context helps synthesis keep the account of Self true.")
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
    return wrote + group_record_fill(name)


def _group_register_renders() -> "list[tuple[str, object]]":
    """THE EMPTY REGISTERS A GROUP IS BORN WITH (2026-10-16): tree-relative path, and the OWNER's
    renderer of the bytes its own reader builds when the file is absent — so the format has one
    copy, and it is the owner's. packaging/scaffold/groups/<g>/ ships the same ten. Every reader
    tolerates an absent file; the gates over them do not all (practice_verify refused the comedy
    group's first close for want of self/best_practices.toml), so a group carries every one."""
    import circle_history_manager as CHM
    import circle_journal_manager as CJM
    import circle_observation_manager as COM
    import practice_manager as PM
    import proposal_group_manager as PGM
    import proposal_manager as PRM
    import redaction_manager as RDM
    import remember_manager as RMM
    import topic_manager as TM
    import working_set_manager as WSM
    return [("self/best_practices.toml", PM.practice_empty_render),
            ("self/coalesce.toml", PGM.proposal_group_empty_render),
            ("self/proposals.toml", PRM.proposal_empty_render),
            ("self/redaction.toml", RDM.redaction_empty_render),
            ("self/remember.toml", RMM.remember_empty_render),
            ("self/topics.toml", TM.topic_empty_render),
            ("circles/circle_history.toml", CHM.circle_history_empty_render),
            ("circles/circle_journal.toml", CJM.circle_journal_empty_render),
            ("circles/circle_observation_log.toml", COM.circle_observation_empty_render),
            ("circles/working_sets.toml", WSM.working_set_empty_render)]


def _group_stub_texts(name: str) -> "list[tuple[str, str]]":
    """The three stub files a group is born with — the operator's to rewrite."""
    return [("issues/issue_model.md", _ISSUE_MODEL_STUB.format(name=name)),
            ("self/self.md", _SELF_STUB),
            ("circles/README.md", _CIRCLES_README.format(name=name))]


def group_record_survey(name: str) -> "tuple[list[str], list[str]]":
    """WHAT THE GROUP'S RECORD LACKS, AND WHAT IS STILL A STUB (2026-10-16). Returns (missing,
    placeholders), tree-relative. MISSING is a file a group depends on and does not have — the ten
    empty registers, issues/issue_model.md and self/self.md; group_record_fill() writes each.
    PLACEHOLDERS are files still holding the stub /group-add wrote — advice only, never a failure:
    the group runs on them, and the operator is told what is theirs to write."""
    tree = _RP.group_tree(name)
    needed = [rel for rel, _r in _group_register_renders()] + ["issues/issue_model.md", "self/self.md"]
    missing = [rel for rel in needed if not (tree / rel).is_file()]

    def text(rel: str) -> str:
        p = tree / rel
        return p.read_text(encoding="utf-8") if p.is_file() else ""
    placeholders: list[str] = []
    if text("issues/issue_model.md") == _ISSUE_MODEL_STUB.format(name=name):
        placeholders.append("issues/issue_model.md")
    if any(m in text("self/self.md") for m in (_SELF_PLACEHOLDER,) + _SELF_SHIPPED_MARKS):
        placeholders.append("self/self.md")
    for role in _RP.group_descriptor_read(name).get("roles", []):
        if _ROLE_IDENTITY.format(name=name) in text(f"parts/{role}/long_term.md"):
            placeholders.append(f"parts/{role}/long_term.md")
    return missing, placeholders


def group_record_fill(name: str) -> list[str]:
    """Write every file group_record_survey() would call missing — each empty register as its
    owner renders it, each stub as /group-add writes it — and circles/README.md; never touch a file
    that exists. Returns what was written, tree-relative, in order."""
    from atomic_write import record_atomic_write
    tree = _RP.group_tree(name)
    wrote: list[str] = []
    for rel, make in ([(r, (lambda t=t: t)) for r, t in _group_stub_texts(name)]
                      + _group_register_renders()):
        p = tree / rel
        if p.is_file():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        record_atomic_write(p, make())
        wrote.append(rel)
    return wrote


# THE STUBS, WRITTEN BY THE OPERATOR THROUGH A FORM (B151, 2026-10-16). The three files a group is
# born holding a stub — issues/issue_model.md, self/self.md, each role's long_term.md — read for the
# initialization form and written back from it, compliant by construction: issue_model.md whole,
# the other two SECTION BY SECTION, so a heading can neither go nor arrive (synthesis holds self.md
# to its heading set; long_term.md's `## required end` and everything below it are history, kept
# byte for byte). A body may not open a line with `## `, so no edit makes a section heading.
_TEXT_MAX = 20_000                          # one field — the server's own body limit is the floor


def _record_sections_cut(text: str, end: str = "") -> "tuple[str, list[list[str]], str]":
    """(head, [[heading, raw chunk]], tail): the text before the first `## ` line, each `## `
    section whole (its heading line included), and — when `end` is given — that heading's line and
    everything after it, never a section. "".join of the three is the text, byte for byte."""
    lines = text.splitlines(keepends=True)
    stop = next((i for i, ln in enumerate(lines) if end and ln.rstrip("\r\n") == end), len(lines))
    head, secs = [], []
    for ln in lines[:stop]:
        if ln.startswith("## "):
            secs.append([ln[3:].strip(), ln])
        elif secs:
            secs[-1][1] += ln
        else:
            head.append(ln)
    return "".join(head), secs, "".join(lines[stop:])


def _record_section_body(chunk: str) -> str:
    return chunk.split("\n", 1)[1].strip("\n") if "\n" in chunk else ""


def _group_text_files(name: str) -> "list[tuple[str, str, str]]":
    """(tree-relative path, shape, display) for every file the form edits: issue_model.md whole,
    self.md by section, each role's long_term.md by section above `## required end`."""
    from record_model import IDENTITY_END
    roster = dict(R.part_scan(_parts_base(name))[0]) if _parts_base(name).is_dir() else {}
    out = [("issues/issue_model.md", "", "What an issue is, for this group"),
           ("self/self.md", "sections", "Who Self is")]
    for role in _RP.group_descriptor_read(name).get("roles", []):
        if role in roster:
            out.append((f"parts/{role}/long_term.md", IDENTITY_END, roster[role]))
    return out


def group_record_text_read(name: str) -> list[dict]:
    """The stub files of group `name` as the initialization form shows them, one row each:
    {path, title, stub, text} for issue_model.md, {path, title, stub, sections: [{heading, body}]}
    for self.md and each role's long_term.md. `stub` is group_record_survey()'s own verdict. A file
    that is absent, or has a heading twice, is shown with `problem` and no editor."""
    tree = _RP.group_tree(name)
    _missing, stubs = group_record_survey(name)
    rows = []
    for rel, shape, title in _group_text_files(name):
        row: dict = {"path": rel, "title": title, "stub": rel in stubs}
        p = tree / rel
        if not p.is_file():
            row["problem"] = f"{rel} is missing — group_record_verify.py --fill writes it"
        elif not shape:
            row["text"] = p.read_text(encoding="utf-8")
        else:
            _h, secs, _t = _record_sections_cut(p.read_text(encoding="utf-8"),
                                                "" if shape == "sections" else shape)
            heads = [h for h, _c in secs]
            if len(set(heads)) != len(heads) or not heads:
                row["problem"] = (f"{rel} has {'a heading twice' if heads else 'no ## heading'} — "
                                  f"edit it by hand")
            else:
                row["sections"] = [{"heading": h, "body": _record_section_body(c)} for h, c in secs]
        rows.append(row)
    return rows


def _record_body_fault(body: str) -> str:
    if not body.strip():
        return "write something here — an empty section is refused"
    if len(body) > _TEXT_MAX:
        return f"{len(body):,} characters; at most {_TEXT_MAX:,}"
    if "\r" in body or "\x00" in body:
        return "a carriage return or NUL is not allowed"
    if any(re.match(r"##(\s|$)", ln) for ln in body.split("\n")):
        return "a line may not start with ## — the section headings are fixed"
    return ""


def group_record_text_render(name: str, edits: dict) -> "tuple[list[tuple[str, str]], dict]":
    """The files `edits` would write, CHECKED, and nothing written: ([(rel, text)] for every file
    that changes, {field: why} for every refusal). `edits` is {rel: text} for issue_model.md and
    {rel: [{heading, body}]} for a sectioned file, its headings exactly those on file and in order.
    A field is `rel` for a whole file, `rel#heading` for a section.

    Each result is held to the rules the record already keeps: record_model.record_file_verify (not
    empty, one closing newline, no stray script character), self.md to synthesis's heading set
    (record_headed_compare), long_term.md to its `## required end` boundary with the history below it
    unchanged — so what the form writes always passes the gates over it."""
    import record_model as RM
    tree = _RP.group_tree(name)
    files = {rel: shape for rel, shape, _t in _group_text_files(name)}
    errors: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    if not isinstance(edits, dict):
        return [], {"texts": "`texts` must be an object"}
    for rel, want in edits.items():
        if rel not in files:
            errors[rel] = "not a file this form edits"
            continue
        p = tree / rel
        if not p.is_file():
            errors[rel] = f"{rel} is missing — nothing to edit"
            continue
        old = p.read_text(encoding="utf-8")
        shape = files[rel]
        if not shape:
            if not isinstance(want, str):
                errors[rel] = "the text must be a string"
                continue
            body = want.strip("\n")
            why = ("write something here — BLOCK 2 opens with this file" if not body.strip()
                   else _record_body_fault(body) if "\r" in body or "\x00" in body
                   or len(body) > _TEXT_MAX else "")       # its own headings are its author's
            if why:
                errors[rel] = why
                continue
            new = body + "\n"
        else:
            head, secs, tail = _record_sections_cut(old, "" if shape == "sections" else shape)
            if (not isinstance(want, list)
                    or [str((s or {}).get("heading", "")) for s in want] != [h for h, _c in secs]):
                errors[rel] = f"{rel}'s headings changed since the page read it — reload"
                continue
            parts = [head]
            bad = False
            for i, (s, (h, chunk)) in enumerate(zip(want, secs)):
                body = str(s.get("body", "")).strip("\n")
                if body == _record_section_body(chunk):
                    parts.append(chunk)
                    continue
                why = _record_body_fault(body)
                if why:
                    errors[f"{rel}#{h}"] = why
                    bad = True
                    continue
                last = i == len(secs) - 1 and not tail
                parts.append(f"## {h}\n\n{body}\n" + ("" if last else "\n"))
            if bad:
                continue
            new = "".join(parts) + tail
        if new == old:
            continue
        _t, found = RM.record_file_verify(rel, new.encode("utf-8"))
        if shape == "sections":
            found += RM.record_headed_compare(rel, old, new)
        elif shape:
            lt = RM.LongTerm(new)
            if lt.preamble is None or not new.endswith(tail):
                found.append(RM._f("FAIL", "BOUNDARY", rel, f"'{shape}' or what follows it moved"))
        fails = [f.message for f in found if f.level == "FAIL"]
        if fails:
            errors[rel] = "; ".join(fails)
            continue
        out.append((rel, new))
    return out, errors


def group_record_text_write(name: str, edits: dict) -> list[pathlib.Path]:
    """Write what group_record_text_render() returns, every file or none: ValueError carrying the
    {field: why} refusals when any. Returns the paths written."""
    from atomic_write import record_atomic_write
    files, errors = group_record_text_render(name, edits)
    if errors:
        raise ValueError(errors)
    tree = _RP.group_tree(name)
    for rel, text in files:
        record_atomic_write(tree / rel, text)
    return [tree / rel for rel, _t in files]


def group_add(name: str, roles: list[str], layer: "str | None" = None) -> tuple[bool, str]:
    """Make one group: the RECORD its descriptor promises first, the descriptor LAST (the head
    docstring). IMMEDIATE: /abort does not undo it. Returns (ok, message). `layer` (B115) is
    optional; without one the group runs on the universal layer alone with the product's own words
    (process_core_prompt_projection.DEFAULT_WORDS), and the message says so."""
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
    registers = {rel for rel, _r in _group_register_renders()}
    stubs = [w for w in wrote if not w.startswith("parts/") and w not in registers]
    empties = [w for w in wrote if w in registers]
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
    if empties:
        lines.append(f"  {len(empties)} empty register(s) under self/ and circles/ — circles fill "
                     f"them; the stubs above are yours to write")
    if not layer:
        lines.append(f"  no layer given: the group runs on the universal rulebook alone, with "
                     f"\"role\" for its members, until group.toml names a layer file")
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


_DEFAULT_LINE = re.compile(r"^default = (true|false)[ \t]*$", re.M)


def group_default_write(name: str) -> list[pathlib.Path]:
    """Make `name` THE DEFAULT GROUP — `default = true` in its group.toml, `false` in every other
    that says true (the operator, 2026-10-15: changing the group in the Ticker "set[s] the default
    on the target group"). Returns the files written, which the caller files in git; [] when
    `name` was already the one default. Raises ValueError for a name that is not a group.

    THE ONE LINE, NOT THE DOCUMENT. group_descriptor_write() re-renders the whole file from ORDER,
    and the default group's group.toml carries a comment block mid-file it would drop; so only
    the `default = ...` line changes, the rest byte for byte, and the result must parse to the
    same document with `default` alone moved. A file with no such line gains one under `display`
    when it must say true; one that must say false and has none already does (absent is false)."""
    try:
        import tomllib
    except ModuleNotFoundError:                                 # py < 3.11
        import tomli as tomllib                                 # type: ignore
    from atomic_write import record_atomic_write
    names = _RP.group_present_read()
    if name not in names:
        raise ValueError(f"no group named {name!r}")
    plan: list[tuple[pathlib.Path, str]] = []
    for n in names:
        want = n == name
        p = _RP.group_descriptor_locate(n)
        text = p.read_text(encoding="utf-8")
        doc = tomllib.loads(text)
        if (doc.get("default") is True) == want:
            continue
        line = f"default = {'true' if want else 'false'}"
        if _DEFAULT_LINE.search(text):
            new = _DEFAULT_LINE.sub(line, text, count=1)
        else:
            new, k = re.subn(r"^(display = .*)$", rf"\1\n{line}", text, count=1, flags=re.M)
            if not k:
                raise ValueError(f"{p}: no `display` line to set `default` under")
        back = tomllib.loads(new)
        if back.get("default") is not want or {**back, "default": None} != {**doc, "default": None}:
            raise ValueError(f"{p}: setting `default` would change more than `default`")
        plan.append((p, new))
    for p, new in plan:             # every file checked before any is written
        record_atomic_write(p, new)
    return [p for p, _new in plan]


def _descriptor_line_render(k: str, v) -> str:
    """One root key in the form group_descriptor_dumps() writes it."""
    if isinstance(v, bool):
        return f"{k} = {str(v).lower()}"
    if isinstance(v, list):
        return _list_render(k, v)
    return f"{k} = {_lit(v)}"


def _descriptor_key_re(k: str) -> "re.Pattern[str]":
    """A root key's whole entry — a one-line scalar, or a list however many lines it spans."""
    return re.compile(rf"^{re.escape(k)} = (?:\[[^\]]*\]|[^\n]*)[ \t]*(?:\n|\Z)", re.M)


def group_descriptor_edit(name: str, want: dict) -> "pathlib.Path | None":
    """Make groups/<name>/group.toml say `want`, changing ONLY the keys that differ — each in
    place, in the form group_descriptor_dumps() gives it — so every other line, its comments
    included, keeps its bytes. group_roles_edit()'s rule, for every key: the default group's
    file carries a comment block mid-file that group_descriptor_write()'s re-render would drop
    (the reason group_default_write() edits one line, 2026-10-15). The initialization form's
    save (ui/initialization_form.py) is the caller.

    A key `want` holds and the file lacks goes in after the nearest key before it in ORDER; a key
    the file holds and `want` lacks is taken out, its line or list; `[identity]`'s `role` and
    `key` are set in their table, which is added at the end or removed whole. `default` is not
    this function's to move — group_default_write() moves THE default across files.

    Returns the path when it was rewritten, None when nothing differs. Raises ValueError, writing
    nothing, when the edit does not parse back to exactly `want`."""
    try:
        import tomllib
    except ModuleNotFoundError:                                 # py < 3.11
        import tomli as tomllib                                 # type: ignore
    from atomic_write import record_atomic_write
    p = _RP.group_descriptor_locate(name)
    text = p.read_text(encoding="utf-8")
    doc = tomllib.loads(text)
    if doc == want:
        return None
    for k in set(doc) | set(want):
        if k not in ORDER and doc.get(k) != want.get(k):
            raise ValueError(f"group.toml key {k!r} is not one this module writes")
    head = re.search(r"^\[identity\][ \t]*$", text, re.M)
    root, table = (text[:head.start()], text[head.start():]) if head else (text, "")
    if root and not root.endswith("\n"):
        root += "\n"
    for k in ORDER:
        if k == "identity" or ((k in want) == (k in doc) and want.get(k) == doc.get(k)):
            continue
        pat = _descriptor_key_re(k)
        hits = list(pat.finditer(root))
        if len(hits) > 1:
            raise ValueError(f"{p.name}: `{k}` is written more than once")
        line = _descriptor_line_render(k, want[k]) + "\n" if k in want else ""
        if hits:
            root = root[:hits[0].start()] + line + root[hits[0].end():]
            continue
        at = None
        for prev in reversed(ORDER[:ORDER.index(k)]):
            m = _descriptor_key_re(prev).search(root)
            if m:
                at = m.end()
                break
        if at is None:
            root = root.rstrip("\n") + "\n" + line
        else:
            root = root[:at] + line + root[at:]
    wi, di = want.get("identity") or {}, doc.get("identity") or {}
    if wi != di:
        if not wi:
            table = ""
            root = root.rstrip("\n") + "\n"
        elif not table:
            root = root.rstrip("\n") + "\n\n"
            table = "[identity]\n" + "".join(f"{k} = {_lit(wi[k])}\n" for k in ("role", "key") if k in wi)
        else:
            for k in ("role", "key"):
                kp = re.compile(rf"^{k} = [^\n]*(?:\n|\Z)", re.M)
                line = f"{k} = {_lit(wi[k])}\n" if k in wi else ""
                if kp.search(table):
                    table = kp.sub(lambda _m, line=line: line, table, count=1)
                else:
                    table = table.rstrip("\n") + "\n" + line
    new = root + table
    if tomllib.loads(new) != want:
        raise ValueError(f"{p.name}: the edit does not parse back to the descriptor it meant — "
                         f"nothing written")
    record_atomic_write(p, new)
    return p
