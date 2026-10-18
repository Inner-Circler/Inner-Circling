#!/usr/bin/env python3
"""
initialization_form.py — THE INITIALIZATION FORMS: a group's descriptor and a part's record, each
as one form on a page, served by the ordering tool's server (ui/remember_ordering.py) beside its
other two pages.

    /initialization#group/<group>           the GROUP form: every key of groups/<group>/group.toml,
                                            the files the group was born holding stubs for, and
                                            its best practices
    /initialization#part/<group>/<part>     the PART form: a part's part.toml — its Tag, historical
                                            Tags and identity tail shown, and every question its
                                            [context] declares, answerable

WHAT EACH FORM WRITES, AND THROUGH WHOM. Nothing here holds a rule or a writer of its own:

    a group's descriptor        group_manager.group_descriptor_edit() — the keys that changed,
                                each in place; its checks (group_precheck(), _members_precheck(),
                                _layer_precheck()) word every refusal
    THE default group           group_manager.group_default_write() — the one `default` line, in
                                the group made the default and in the one that was
    a new group                 group_manager.group_add(), then the descriptor's other keys
    what the group is told      group_manager.group_record_text_write() — issue_model.md whole,
                                self.md and each role's long_term.md section by section, every
                                result held to the record's own rules first (B151)
    a best practice             practice_manager.practice_add() — a row of the group's register
    a part's context answers    part_roster.part_context_write() — the bytes between the
                                `context.answers` markers only; every answer checked first by
                                initialization.initialization_validate(), the first-run dialog's
                                own check
    a new part                  part_add.part_add() — the /part-add verb's own act
    a retired part              part_add.part_retire_refusal_read() and part_retire_apply() —
                                /part-retire's own checks and act

A PART'S NAME NEVER CHANGES (R608): its Tag, historical Tags and identity tail
are SHOWN AND NOT EDITED. What the operator ruled instead is that a part may be RETIRED — "sunset"
in his word: kept, its marker renamed retired.toml with the date and a reason, and never seated
again, so a circle opening on the group does not show it.

A GROUP SAVE CHANGES ONLY THE KEYS THAT CHANGED, each in place, so a comment written into
group.toml by hand keeps its bytes — the default group's carries one mid-file. THE DEFAULT IS
MOVED, NEVER CLEARED: there is one default group, so making this group the default makes the old
one not, and a group stops being the default only when another becomes it.

The caller holds the server's lock and has bound the group (record_paths.group_set) for every
function here but the new-group save, whose group does not exist yet. Each save returns the paths
it wrote, which the caller files in git (remember_ordering_file).
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "coordinator"))

import record_paths as RP                                # noqa: E402
import part_roster as R                                  # noqa: E402
import group_manager as GM                               # noqa: E402

PAGE = HERE / "initialization_form.html"
TEXT_MAX = 60            # a display name, and a member word — a label, not a sentence
_BAD_TEXT = ("[", "]", "\n", "\r", '"')


class InitializationRefusal(Exception):
    """A save this module will not carry out: the HTTP status, a message, and `errors` — the
    refusal per field, keyed as the page keys its inputs — when one field is the cause."""

    def __init__(self, status: int, message: str, errors: "dict[str, str] | None" = None):
        super().__init__(message)
        self.status = status
        self.extra = {"errors": errors or {}}


def _toml_read(p: pathlib.Path) -> dict:
    try:
        import tomllib
    except ModuleNotFoundError:                                 # py < 3.11
        import tomli as tomllib                                 # type: ignore
    return tomllib.loads(p.read_text(encoding="utf-8"))


def _proposable() -> list[str]:
    """The commands a group may let its parts propose, as group.toml spells them — no slash."""
    from command_surface import PROPOSE_SUBSET_COMMANDS
    return [c.lstrip("/") for c in PROPOSE_SUBSET_COMMANDS]


def _text_fault(value: str, what: str, limit: int = TEXT_MAX) -> str:
    """"" when `value` is a usable one-line label, else why not."""
    if len(value) > limit:
        return f"{what} is {len(value)} characters; at most {limit}"
    if any(c in value for c in _BAD_TEXT):
        return f"{what} may not carry a square bracket, a quote or a line break"
    return ""


# ------------------------------------------------------------------ the group form
def _part_questions(parts: pathlib.Path, role: str) -> list[str]:
    """The context question keys a role's part.toml declares — what `[identity] key` may name."""
    try:
        doc = _toml_read(parts / role / R.MARKER)
    except Exception:                                           # noqa: BLE001
        return []
    qs = (doc.get("context") or {}).get("questions") or []
    return [str(q.get("key")) for q in qs if isinstance(q, dict) and q.get("key")]


def _layers(name: str) -> list[str]:
    """The .md files at the top of the group's folder, as the tree-relative paths `layer` takes."""
    tree = RP.group_tree(name)
    out = []
    for p in sorted(tree.glob("*.md")) if tree.is_dir() else []:
        try:
            out.append(p.resolve().relative_to(ROOT).as_posix())
        except ValueError:
            pass
    return out


def group_initialization_read(name: str) -> dict:
    """Everything the group form shows for `name` — or, with `name` empty, for a new group.

    record     the descriptor's keys, every one present (an absent key as its empty value)
    parts      the group's seated parts: {name, tag, questions} — the roles it may list
    layers     candidate layer files; proposable, the commands a group may let its parts propose
    default_now  THE default group's name, "" when there is none"""
    groups = [{"name": n, "display": str(RP.group_descriptor_read(n).get("display") or n)}
              for n in RP.group_present_read()]
    base = {"groups": groups, "proposable": _proposable(), "roles_max": GM.MAX_MEMBERS - 1,
            "default_now": RP.group_default_read() or ""}
    if not name:
        return {**base, "group": "", "new": True, "parts": [], "layers": [],
                "record": {"name": "", "display": "", "default": False, "roles": [],
                           "reserved": [], "initialization": [], "layer": "", "member": "",
                           "members": "", "proposed_commands": [],
                           "identity": {"role": "", "key": ""}}}
    doc = RP.group_descriptor_read(name)
    if not doc:
        raise InitializationRefusal(404, f"no group named {name!r}")
    parts_dir = RP.group_tree(name) / "parts"
    roster = R.part_scan(parts_dir)[0] if parts_dir.is_dir() else []
    parts = [{"name": d, "tag": t, "questions": _part_questions(parts_dir, d)} for d, t in roster]
    ident = doc.get("identity") or {}
    record = {"name": name, "display": str(doc.get("display", "")),
              "default": doc.get("default") is True,
              "roles": list(doc.get("roles", [])), "reserved": list(doc.get("reserved", [])),
              "initialization": list(doc.get("initialization", [])),
              "layer": str(doc.get("layer", "")), "member": str(doc.get("member", "")),
              "members": str(doc.get("members", "")),
              "proposed_commands": list(doc.get("proposed_commands", [])),
              "identity": {"role": str(ident.get("role", "")), "key": str(ident.get("key", ""))}}
    return {**base, "group": name, "new": False, "parts": parts, "layers": _layers(name),
            "record": record, "texts": GM.group_record_text_read(name),
            "practices": _practices_read(), "addressees": _addressees()}


# ------------------------------------------------------------------ what the group is told
# B151: the stubs a group is born holding, written here and checked by group_manager (its
# group_record_text_render()), and best practices added through practice_manager — both against
# the BOUND group, which the caller has set.
PRACTICE_MAX = 600       # one practice — a sentence or two a part carries in every prompt


def _addressees() -> list[str]:
    import practice_manager as PM
    return list(PM.ADDRESSEES)


def _practices_read() -> list[dict]:
    """The bound group's best practices as the form lists them: {id, addressee, title, pending}."""
    import practice_manager as PM
    return [{"id": p["id"], "addressee": p["addressee"], "title": p["title"],
             "pending": not PM.practice_is_eligible(p)} for p in PM.practice_read()]


def _practice_new_check(value) -> "tuple[str, str] | None":
    """(title, addressee) the form asks to add, None when it asks nothing; refused otherwise."""
    if not value:
        return None
    if not isinstance(value, dict):
        raise InitializationRefusal(400, "`practice_new` must be an object")
    title = " ".join(str(value.get("title", "")).split())
    addressee = str(value.get("addressee", "")).strip() or "All parts"
    if not title:
        return None
    errors = {}
    if len(title) > PRACTICE_MAX:
        errors["practice_new"] = f"{len(title)} characters; at most {PRACTICE_MAX}"
    if addressee not in _addressees():
        errors["practice_addressee"] = f"{addressee!r} is not this group's — All parts, Self or a part"
    if errors:
        raise InitializationRefusal(422, "the form has a field to correct", errors)
    return title, addressee


def _strs(value, what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InitializationRefusal(400, f"`{what}` must be a list of names", {what: "not a list"})
    return [v.strip() for v in value]


def _group_record_check(name: str, rec: dict) -> dict:
    """The descriptor `rec` would write, every key checked — refused, per field, otherwise. The
    role list itself is group_manager's to judge (the caller runs its precheck)."""
    if not isinstance(rec, dict):
        raise InitializationRefusal(400, "`record` must be an object")
    errors: dict[str, str] = {}
    display = str(rec.get("display", "")).strip()
    if not display:
        errors["display"] = "the group needs a display name — what a person reads"
    elif _text_fault(display, "the display name"):
        errors["display"] = _text_fault(display, "the display name")
    roles = _strs(rec.get("roles", []), "roles")
    reserved = _strs(rec.get("reserved", []), "reserved")
    init = _strs(rec.get("initialization", []), "initialization")
    proposed = _strs(rec.get("proposed_commands", []), "proposed_commands")
    for key, vals in (("reserved", reserved), ("initialization", init)):
        stray = [v for v in vals if v not in roles]
        if stray:
            errors[key] = f"not one of this group's roles: {', '.join(stray)}"
        elif len(set(vals)) != len(vals):
            errors[key] = "a role is listed twice"
    known = set(_proposable())
    stray = [v for v in proposed if v not in known]
    if stray:
        errors["proposed_commands"] = f"not a command a part may propose: {', '.join(stray)}"
    layer = str(rec.get("layer", "")).strip()
    why = GM._layer_precheck(layer) if layer else ""
    if why:
        errors["layer"] = why
    member, members = str(rec.get("member", "")).strip(), str(rec.get("members", "")).strip()
    if bool(member) != bool(members):
        errors["members" if member else "member"] = ("give the word for one AND for many, or "
                                                     "neither — the group then says \"role\"")
    for key, val in (("member", member), ("members", members)):
        if val and key not in errors:
            fault = _text_fault(val, "the word")
            if fault or " " in val:
                errors[key] = fault or "one word, no spaces"
    ident = rec.get("identity") or {}
    role, ikey = str(ident.get("role", "")).strip(), str(ident.get("key", "")).strip()
    if bool(role) != bool(ikey):
        errors["identity.key" if role else "identity.role"] = (
            "name the role AND its question, or neither")
    elif role:
        if role not in roles:
            errors["identity.role"] = f"{role!r} is not one of this group's roles"
        elif ikey not in _part_questions(RP.group_tree(name) / "parts", role):
            errors["identity.key"] = f"{role} asks no question {ikey!r}"
    default = rec.get("default") is True
    if not default and RP.group_descriptor_read(name).get("default") is True:
        errors["default"] = ("this is the default group — it stops being the default when "
                             "another group is made the default")
    if errors:
        raise InitializationRefusal(422, "the form has a field to correct", errors)
    doc: dict = {"name": name, "display": display, "default": default, "roles": roles,
                 "reserved": reserved, "initialization": init}
    if layer:
        doc["layer"] = layer
    if member:
        doc["member"], doc["members"] = member, members
    doc["proposed_commands"] = proposed
    if role:
        doc["identity"] = {"role": role, "key": ikey}
    return doc


def group_initialization_save(name: str, rec: dict, *, new: bool) -> dict:
    """Write one group's descriptor from the form. An existing group: every key checked, the
    roles by group_manager's own precheck, then group_descriptor_edit() — the changed keys in
    place. A new group: its name and roles by group_add() — which scaffolds a part for each role
    with none — and then, when the form set more than group_add() writes, the descriptor again
    with the rest. Either way, a group the form makes the default becomes it through
    group_default_write(), which also writes `false` into the group that was.

    Returns {group, wrote: [paths], message}. Nothing is written when anything is refused."""
    if new:
        name = str(rec.get("name", "")).strip()
        roles = _strs(rec.get("roles", []), "roles")
        why = GM.group_precheck(name, roles)
        if why:
            field = "name" if (not name or not GM.NAME_RE.match(name)
                               or name in RP.group_present_read()) else "roles"
            raise InitializationRefusal(422, why, {field: why})
        # identity needs a role whose part asks something, and a new group's parts ask nothing
        rec = {**rec, "identity": {"role": "", "key": ""}}
        doc = _group_record_check(name, rec)
        make_default, doc["default"] = doc["default"], False
        ok, msg = GM.group_add(name, roles, doc.get("layer"))
        if not ok:
            raise InitializationRefusal(422, msg, {"roles": msg})
        if RP.group_descriptor_read(name) != doc:
            GM.group_descriptor_write(name, doc)
        moved = GM.group_default_write(name) if make_default else []
        return {"group": name, "wrote": [RP.group_tree(name)] + moved,
                "message": msg + ("\n  it is the default group now" if moved else "")}
    on_file = RP.group_descriptor_read(name)
    if not on_file:
        raise InitializationRefusal(404, f"no group named {name!r}")
    doc = _group_record_check(name, rec)
    why = GM._members_precheck(doc["roles"], name)
    if why:
        raise InitializationRefusal(422, why, {"roles": why})
    # what the group is told (B151) — every check before any write, so a refusal writes nothing
    texts, text_errors = GM.group_record_text_render(name, rec.get("texts") or {})
    if text_errors:
        raise InitializationRefusal(422, "the form has a text to correct",
                                    {f"texts.{k}": v for k, v in text_errors.items()})
    practice = _practice_new_check(rec.get("practice_new"))
    make_default = doc.pop("default") and on_file.get("default") is not True
    if "default" in on_file:                # the default moves below, across files, or not at all
        doc["default"] = on_file["default"]
    for k, v in on_file.items():            # a key this form does not know stays as it is
        if k not in GM.ORDER:
            doc[k] = v
    taught: list = []           # (layer path, note) when proposed_commands moved (2026-10-17)
    try:
        p = GM.group_descriptor_edit(name, doc, report=taught)
    except ValueError as e:
        raise InitializationRefusal(409, f"group.toml could not be edited in place ({e}) — "
                                         f"nothing written") from e
    moved = GM.group_default_write(name) if make_default else []
    wrote = ([p] if p else []) + [lp for lp, _n in taught if lp] + [m for m in moved if m != p]
    told = GM.group_record_text_write(name, rec.get("texts") or {}) if texts else []
    added = ""
    if practice:
        import practice_manager as PM
        ok, added = PM.practice_add(*practice)
        if not ok:
            raise InitializationRefusal(422, added, {"practice_new": added})
        told.append(PM.BP)
    wrote += told
    if not wrote:
        return {"group": name, "wrote": [], "message": "nothing changed — nothing written"}
    return {"group": name, "wrote": wrote,
            "message": f"{name!r} is saved" + (" and is the default group now" if moved else "")
                       + (f" — {len(texts)} text(s) written" if texts else "")
                       + (f" — practice {added}" if added else "")
                       + "".join(f" — {n}" for _lp, n in taught if n)
                       + " — it applies from the next circle on the group"}


# ------------------------------------------------------------------ the part form
_QUESTION_KEYS = ("key", "ask", "data_type", "data_max", "gate", "values", "unique_in",
                  "advisory_note", "render")


def part_initialization_read(group: str, part: str) -> dict:
    """Everything the part form shows for `part` of the bound `group` — or, with `part` empty,
    for a new part.

    record     name, tag, alt_tags, identity_tail, purpose, questions, answers
    questions  read WHOLE from part.toml (part_roster.part_context_read() keeps only what the
               dialog asks with), each bound resolved to a number for today: minimum, maximum,
               advisory_maximum
    problems   what part_roster says is wrong with its [context]; the answers are not editable
               while there is one
    retire     {refusal, plan, files}: why the part cannot be retired now ("" when it can), the
               dependency plan's own text, and how many files its folder keeps"""
    parts = [{"name": d, "tag": t} for d, t in R.part_scan()[0]]
    base = {"group": group, "parts": parts}
    if not part:
        return {**base, "part": "", "new": True, "problems": [],
                "record": {"name": "", "tag": "", "identity": "", "alt_tags": [],
                           "identity_tail": "", "purpose": "", "questions": [], "answers": {}}}
    if part not in {p["name"] for p in parts}:
        raise InitializationRefusal(404, f"no part named {part!r} in group {group!r}")
    doc = _toml_read(R.PARTS_DIR / part / R.MARKER)
    problems = R.part_context_problems_read(part, doc)
    ctx = doc.get("context") or {}
    qs = []
    for q in (ctx.get("questions") or []) if not problems else []:
        row = {k: q[k] for k in _QUESTION_KEYS if k in q}
        for bound in ("minimum", "maximum", "advisory_maximum"):
            if bound in q:
                row[bound] = R.part_bound_resolve(q[bound])
        qs.append(row)
    recorded = ctx.get("answers") or {}
    import part_add as PA
    refusal, plan = PA.part_retire_refusal_read(part)
    files = sum(1 for f in (R.PARTS_DIR / part).rglob("*") if f.is_file())
    return {**base, "part": part, "new": False, "problems": problems,
            "retire": {"refusal": refusal, "plan": plan, "files": files},
            "record": {"name": part, "tag": str(doc.get("tag", "")),
                       "alt_tags": [str(t) for t in doc.get("alt_tags", [])],
                       "identity_tail": str(doc.get("identity_tail", "")),
                       "purpose": str(ctx.get("purpose", "")), "questions": qs,
                       "answers": {q["key"]: str(recorded.get(q["key"], "")) for q in qs}}}


def part_initialization_save(group: str, part: str, body: dict) -> dict:
    """Write one part's record from the form.

    An existing part: `answers`, {key: text}, every one checked by the first-run dialog's own
    check (uniqueness included) and stored in its canonical spelling, then
    part_roster.part_context_write() — the answers block, nothing else in the file.
    A new part (`part` empty): `tag` and `identity`, by part_add.part_add(), which writes the part,
    puts it on the group's roles and commits both itself.

    Returns {part, wrote: [paths], message, advice: {key: text}}."""
    if not part:
        import part_add as PA
        tag, identity = str(body.get("tag", "")).strip(), str(body.get("identity", "")).strip()
        name = PA.part_name_derive(tag)
        ok, msg = PA.part_add(name, tag, identity)
        if not ok:
            field = "identity" if "description" in msg else "tag"
            raise InitializationRefusal(422, msg, {field: msg})
        return {"part": name, "wrote": [], "message": msg, "advice": {}}
    view = part_initialization_read(group, part)
    if view["problems"]:
        raise InitializationRefusal(409, f"parts/{part}/part.toml has a problem to repair by "
                                         f"hand first: {view['problems'][0]}")
    answers = body.get("answers")
    if not isinstance(answers, dict) or not all(isinstance(v, str) for v in answers.values()):
        raise InitializationRefusal(400, "`answers` must be an object of texts")
    import initialization as INIT
    declared = (_toml_read(R.PARTS_DIR / part / R.MARKER).get("context") or {}).get("questions") or []
    questions = {q["key"]: q for q in declared}
    errors: dict[str, str] = {}
    clean: dict[str, str] = {}
    advice: dict[str, str] = {}
    for key, text in answers.items():
        q = questions.get(key)
        if q is None:
            errors[key] = "this part asks no such question"
            continue
        text = text.strip()
        why = INIT.initialization_validate(q, text, part=part)
        if why:
            errors[key] = why.strip()
            continue
        clean[key] = R.part_canonical_read(q, text)
        note = INIT.initialization_advice_render(q, clean[key])
        if note:
            advice[key] = note.strip()
    if errors:
        raise InitializationRefusal(422, "the form has an answer to correct", errors)
    if clean == {k: v for k, v in view["record"]["answers"].items() if k in clean}:
        return {"part": part, "wrote": [], "message": "nothing changed — nothing written",
                "advice": advice}
    R.part_context_write(part, clean, base=R.PARTS_DIR)
    return {"part": part, "wrote": [R.PARTS_DIR / part / R.MARKER], "advice": advice,
            "message": f"{view['record']['tag']}'s answers are saved — they reach its prompt "
                       f"from the next circle"}


def part_initialization_retire(group: str, part: str, confirm: str, why: str) -> dict:
    """Retire one part of the bound `group` — /part-retire's own checks and act, the confirmation
    the folder's name typed back, as the verb asks for it. Returns {part, wrote: [paths],
    message}; the caller commits the paths. Nothing changes when anything is refused."""
    if part not in {d for d, _t in R.part_scan()[0]}:
        raise InitializationRefusal(404, f"no part named {part!r} in group {group!r}")
    if str(confirm).strip() != part:
        raise InitializationRefusal(422, f"type the folder name, {part}, to retire it",
                                    {"retire-confirm": f"type {part} exactly"})
    why = str(why).strip()
    if "\n" in why or "\r" in why or len(why) > 200:
        raise InitializationRefusal(422, "the reason is one line, at most 200 characters",
                                    {"retire-why": "one line, at most 200 characters"})
    import part_add as PA
    refusal, _plan = PA.part_retire_refusal_read(part)
    if refusal:
        raise InitializationRefusal(409, refusal, {"retire-confirm": refusal})
    try:
        said, paths = PA.part_retire_apply(part, why)
    except ValueError as e:
        raise InitializationRefusal(409, str(e), {"retire-confirm": str(e)}) from e
    return {"part": part, "wrote": paths, "message": said}
