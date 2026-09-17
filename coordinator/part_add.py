#!/usr/bin/env python3
"""
part_add.py — the part-lifecycle register: create, list, view, retire a
`parts/<name>/` directory. A14's creation path, built 2026-08-23 to
`docs/part_commands_design.md (archived)` as `docs/Initialization.md` §8 reconciled it
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

A PART ADDED NOW JOINS THE NEXT CIRCLE — R548 (D127,
2026-09-11): *"D127 - yes, the part must be included next circle."* A plain
circle opens on the group's `roles` (group.toml, B117), so part_add() puts
the new name there after its files are written, and part_retire() takes it
off `roles` and `initialization` before the folder goes; each commits the
folder and the list together. A circle already open keeps the roster it
opened with; circle.main() reads it again at every open, so the next circle
in the same window has it too.

RETIRE KEEPS THE RECORD — B140 (R559-R561, 2026-09-12); /part-delete removed
the directory until then. THE SYSTEM RESPECTS RECORDS AND HISTORY: no verb
removes a part's record. /part-retire renames part.toml to retired.toml (date
and reason appended), takes the part off the group's list, deletes its recall
cache — the one derived index — and commits the rename and the list. The
folder stays where every close report, transcript and issue-graph quote
expects it; the Tag stays taken; the part's old lines still parse and its
quotes stay attributed; nothing it owned is ever searched or sent again.
Reversal is the rename back AND the name back on the group's `roles`, both by
hand — no verb (R561; the list is deliberate, R548). The group's RESERVED
roles (its group.toml, R468 — Soul and Child for the IFS group, docs/BNF.md) are
refused before any dialog; a retire while a circle may be open is refused
outright (circle_state fails closed) — the next round's read of a part that
just left the roster would take the circle down.

Positional numbers, not ids: `view`/`retire` take the number `part_list()`
printed, which shifts when a part is retired — the same contract
/practice-list has always stated.
"""

from __future__ import annotations

import pathlib
import re
from datetime import datetime

import part_roster as R
import record_paths as _RP
import seam
import phase_clock as PC   # stream_timed_read — a prompt is human time, and the
                           # heartbeat must not spin at someone typing
from circle_close_verify import MAX_MEMBERS
from REGISTER_CLASS import register_list_footer, register_row_nth_read

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# The identity seed's shape — the person's words, marked as the person's.
# Bootstrap is the day the part was added: the shape every accepted part file
# carries, and nothing parses it. The header reaches BLOCK 3 whole, so it
# must never hold a placeholder a part would read as its own.
LONG_TERM_TEMPLATE = """# The {tag} — Long-Term Memory
Bootstrap: {date}

## How my human describes me

{identity}

## required end
"""


def part_long_term_seed_render(tag: str, identity: str) -> str:
    """The long_term.md a new part starts from: LONG_TERM_TEMPLATE with the
    Tag, the day it was added, and the person's words. The one place the
    template is filled — part_add() and group_manager's record scaffold both
    call it, so the header cannot drift between the two doors."""
    return LONG_TERM_TEMPLATE.format(tag=tag.strip(),
                                     date=datetime.now().strftime("%Y-%m-%d"),
                                     identity=identity.strip())


def part_name_derive(tag: str) -> str:
    """The directory name, from the Tag: lower-cased, every run of
    characters outside [a-z0-9] collapsed to one underscore, trimmed.
    "" when nothing survives (an all-symbol tag) — the caller asks then."""
    return re.sub(r"[^a-z0-9]+", "_", tag.lower()).strip("_")


def part_precheck(name: str, tag: str, identity: str) -> str:
    """"" when part_add() would proceed, else the one-line refusal — PART_ADD_VALIDATION,
    live against the tree as it stands right now (a fresh scan, not the import-time copy).

    THE CONTRACT IS WRITTEN HERE NOW, and that is the fix — audit-register.md #7,
    2026-09-08. This docstring cited `docs/part_commands_design.md`'s PART_ADD_VALIDATION
    as the definition, and that document left the tree at 048ccda (2026-09-07) for
    Inner_Circling_Archive. A citation is a fine thing to leave behind; a DEFINITION is not,
    and this one defined the behaviour of a shipped function. Restated in full, in order —
    the order is itself part of the contract, because the first refusal wins and a caller
    sees exactly one reason:

        identity non-empty      long_term.md is read with a bare read_text(); an empty
                                identity crashes prompt assembly rather than refusing
        identity <= 40 words    a description, not a biography
        tag non-empty
        tag free of BAD_IN_TAG  `[Tag]:` IS the transcript grammar (part_roster.BAD_IN_TAG)
        tag not already taken   case-insensitive against the live roster
        tag not Self's          the configured user name, DEFAULT_NAME, or SELF_ID
        name derives usably     NAME_RE, and not one of part_roster.SKIP_DIRS
        parts/<name>/ absent    never write into an existing directory
        roster below ceiling    MAX_MEMBERS - 1 parts (8 + lead); raising it is its own
                                deliberate act

    Kept in step by coordinator/tests/test_part_add.py, which drives each refusal by name."""
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
    # A RETIRED PART'S TAG STAYS TAKEN — R561: an old transcript must never read as a new
    # part's words. Tag and alt_tags, case-insensitive, the same test as the live roster's.
    for _rd, rdoc in R.part_retired_scan().items():
        if tag.strip().lower() in {n.lower() for n in [rdoc["tag"], *rdoc["alt_tags"]]}:
            return (f"{tag.strip()!r} is a RETIRED part's name ({rdoc['tag']}, retired "
                    f"{rdoc['retired'] or 'undated'}) — it stays taken; choose another")
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


# THE TREE'S OWN RECORD IS NEVER WRITTEN FROM A TEST. On 2026-09-16 an audit's tracer ran the
# suites in one process against the main checkout, a suite's isolation (R.PARTS_DIR pointed at
# a temp dir) did not hold across that process, and part_add() wrote a part named after a test
# file into groups/ifs/ and committed it — the roster seated it (audit-register 2026-09-16 #1;
# part_retire's own comment records the same shape on 2026-09-12). Every suite isolates by
# rebinding a module global, and a global is exactly what another suite, a follower or a
# thread can rebind back. So the WRITER checks, at the one moment it matters: when the
# directory it is about to write is under this checkout's own root AND a test suite is on the
# stack (or is the program), it refuses before touching anything. A suite writing its own temp
# tree is untouched (the target is not under LIVE_ROOT); the operator's own /part-add is
# untouched (no suite on the stack). A probe proves the refusal against a temp LIVE_ROOT, so the
# proof itself can never reach the record.
LIVE_ROOT = _RP.ROOT


def _suite_on_stack() -> str | None:
    """The first test suite's filename on the call stack or in sys.argv[0], else None."""
    import sys
    import traceback
    names = []
    if sys.argv:
        names.append(pathlib.Path(sys.argv[0]).name)
    names += [pathlib.Path(f.filename).name for f in traceback.extract_stack()]
    for n in names:
        if n.startswith("test_") and n.endswith(".py"):
            return n
    return None


def part_write_refused(target: pathlib.Path) -> str | None:
    """The one-line refusal when `target` is under LIVE_ROOT and a suite is running, else None.
    Pure: reads the stack and the path, writes nothing — which is what lets a probe call it
    against the real path."""
    try:
        rp = target.resolve()
        live = LIVE_ROOT.resolve()
    except OSError:
        return None
    if live not in rp.parents:
        return None
    suite = _suite_on_stack()
    if suite is None:
        return None
    return (f"refused: {suite} reached this tree's own record ({rp}) — a suite writes a temp "
            f"tree, never this one. Nothing was written.")


def part_add(name: str, tag: str, identity: str) -> tuple[bool, str]:
    """Create parts/<name>/ — long_term.md first, part.toml last (the marker
    makes it a part, so the identity must exist before membership does) —
    then put <name> on the group's `roles` and commit both (D127).
    IMMEDIATE: /abort does not undo it. Returns (ok, message)."""
    why = part_precheck(name, tag, identity)
    if why:
        return False, why
    why = part_write_refused(R.PARTS_DIR / name)
    if why:
        return False, why
    from atomic_write import record_atomic_write
    d = R.PARTS_DIR / name
    d.mkdir(parents=True)
    record_atomic_write(d / "long_term.md", part_long_term_seed_render(tag, identity))
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
    try:
        desc = _group_roles_edit(add=name)
    except Exception as e:                                      # noqa: BLE001
        _part_commit([d], f"part-add: {name}")
        return True, (f"{tag.strip()} is added (parts/{name}/), but it is NOT on the "
                      f"group's list, so it will not join a circle yet ({e}). Add "
                      f"\"{name}\" to roles in {_descriptor_shown()}.")
    # COMMITTED, as part_retire() commits: the group.toml edit is a change to a tracked file,
    # and a record left dirty is what stops a later merge into this tree.
    _part_commit([d] + ([desc] if desc else []), f"part-add: {name}")
    return True, (f"{tag.strip()} is added (parts/{name}/). It joins from "
                  f"the next circle.")


def _part_commit(paths: list, message: str) -> None:
    """Commit this module's own writes, and say so on the command pane — never raises."""
    try:
        import gitrepo as G
        G.system_git_paths_commit(paths, message,
                                  lambda kind, msg: seam.emit("command", f"  {msg}"))
    except Exception as e:                                      # noqa: BLE001
        seam.emit("command", f"  (not committed — {e}; commit it by hand)")


def _group_roles_edit(**kw) -> "pathlib.Path | None":
    """The bound group's list, one role on or off (group_manager.group_roles_edit()) — the
    group whose parts/ this module writes, so a probe's temp tree is the one edited."""
    import group_manager as GM
    return GM.group_roles_edit(R.PARTS_DIR.parent, **kw)


def _descriptor_shown() -> str:
    """The group.toml beside parts/, as a person would find it from the tree's root."""
    import record_paths as _RP
    p = R.PARTS_DIR.parent / _RP.GROUP_MARKER
    try:
        return p.relative_to(_RP.ROOT).as_posix()
    except ValueError:
        return str(p)


def part_rows_read() -> list[tuple[str, str]]:
    """(dir, Tag), roster order, from a fresh scan."""
    roster, _a, _t, _p = R.part_scan()
    return roster


def part_list() -> str:
    """Numbered, positional — /practice-list's contract: the number is a
    handle into THIS listing and shifts when a part is removed. It ends naming
    `/part-list <n>`, which answers with part_view()'s view (R534, B133)."""
    rows = part_rows_read()
    out = [f"\n  {len(rows)} part(s)"]
    for i, (d, t) in enumerate(rows, 1):
        out.append(f"  {i:>3}  {t}  (parts/{d}/)")
    out.append("\n" + register_list_footer(len(rows), "/part-list"))
    return "\n".join(out)


def part_view(n_text: str) -> tuple[bool, str]:
    """parts/<name>/long_term.md, verbatim, by listing number."""
    hit = register_row_nth_read(part_rows_read(), n_text)
    if hit is None:
        return False, f"no part #{n_text.strip() or '?'} — /part-list shows them"
    d, t = hit
    p = R.PARTS_DIR / d / "long_term.md"
    if not p.is_file():
        return False, f"parts/{d}/long_term.md is MISSING — that part cannot speak"
    return True, f"\n  {t} — parts/{d}/long_term.md\n\n" + p.read_text(encoding="utf-8")


def part_reserved_read() -> tuple[str, ...]:
    """The roles /part-retire refuses — the bound group's group.toml `reserved` list (R468,
    B120; RESERVED_DIRS = ("soul", "child") was the literal until then, and is the IFS group's
    own value of it)."""
    import record_paths as _RP
    return tuple(str(d) for d in _RP.group_descriptor_read(_RP.group_read()).get("reserved", []))


def part_retire_marker_render(part_toml: str, why: str, today: str) -> str:
    """retired.toml's text: part.toml's own bytes, with `retired` and `retired_why` appended.
    The document is kept whole — Tag, alt_tags, identity_tail, [context] and its answers —
    because reversal is the rename back (R561), and a part that returns should return as it
    was. AN EARLIER RETIREMENT'S LINES ARE DROPPED FIRST: a part retired, brought back by hand
    with the appended lines left in place, and retired again would otherwise carry `retired`
    twice — and tomllib refuses a duplicate key, which would make the marker unreadable and
    the directory a problem the open refuses on. The file's history is git's."""
    kept = [ln for ln in part_toml.splitlines()
            if not ln.startswith(("retired = ", "retired_why = ", "# RETIRED — ",
                                  "# the system respects records and history.",
                                  "# file to part.toml", "# group.toml (R561"))]
    body = "\n".join(kept).rstrip("\n") + "\n"
    why_q = why.strip().replace("\\", "\\\\").replace('"', '\\"')
    return (f"{body}\n# RETIRED — /part-retire, {today}. The marker is renamed, the record stays:"
            f"\n# the system respects records and history. To bring the part back, rename this"
            f"\n# file to part.toml AND put the directory name back on `roles` in the group's"
            f"\n# group.toml (R561; R548 made the list deliberate).\nretired = \"{today}\"\n"
            f"retired_why = \"{why_q}\"\n")


def part_retire(n_text: str) -> None:
    """/part-retire <n> — B140 (R559-R561, 2026-09-12); /part-delete until then, which removed
    parts/<d>/ whole. THE RECORD STAYS: long_term, mid_term, every short_term the close reports
    hash, remember, dreams. What changes is the marker — part.toml is renamed retired.toml with
    the date and a reason appended — so the roster knows the part and never seats it, its Tag
    stays taken, and its old lines still parse. The part's recall cache (derived, never the
    record) is deleted; a retired part is never armed again, so nothing rebuilds it.

    Confirmation is TYPING THE DIRECTORY NAME, then the part comes off the group's `roles` and
    `initialization` (D127), the marker is renamed, and both are COMMITTED together. Refused
    for the group's RESERVED roles, and while a circle may be open (circle_state fails closed).
    Reversal is by hand — rename retired.toml back AND put the name back on the group's
    `roles` (R548 made the list deliberate) — and there is no verb for it (R561)."""
    hit = register_row_nth_read(part_rows_read(), n_text)
    if hit is None:
        seam.emit("command", f"  no part #{n_text.strip() or '?'} — "
                             f"/part-list shows them")
        return
    d, t = hit
    if d in part_reserved_read():
        import record_paths as _RP
        seam.emit("command", f"  {t} is a RESERVED role of this group "
                             f"(groups/{_RP.group_read()}/group.toml) — never retired")
        return
    try:
        import circle_state
        open_now = bool(circle_state.circle_open_read())
    except Exception:                                           # noqa: BLE001
        open_now = True                                          # fails closed
    if open_now:
        seam.emit("command", "  a circle may be open — close it first: a "
                             "live round reading a retired part is a crash")
        return
    # WHAT LEANS ON THIS PART — R570, 2026-09-15. Today only PRESERVED and
    # HANDLED dependents exist (its quotes, the practices addressed to it, the group's roles),
    # so the retire keeps its own contract and names them first. A plan that must remove
    # something first stops the retire here, naming it. Read only; a plan that cannot be read
    # is no plan, and the retire goes on as it always did.
    try:
        import dependency_manager as DM
        dplan = DM.dependency_plan("part", d)
    except Exception:                                           # noqa: BLE001
        DM, dplan = None, None
    if dplan is not None and DM.dependency_plan_is_blocked(dplan):
        seam.emit("command", DM.dependency_plan_render(dplan))
        seam.emit("command", f"  {t} is not retired — what must be removed first is named above.")
        return
    if dplan is not None and (dplan["preserve"] or dplan["handled"]):
        seam.emit("command", DM.dependency_plan_render(dplan))
    files = [f for f in sorted((R.PARTS_DIR / d).rglob("*")) if f.is_file()]
    seam.emit("command", f"\n  retiring {t} keeps parts/{d}/ and its {len(files)} file(s) — "
                         f"the system respects records and history. From now on:")
    seam.emit("command", "    it attends no circle, reaches no prompt, and none of its own record "
                         "is ever searched;\n    its past statements stay in the circles' "
                         "transcripts, marked retired;\n    its name stays taken — no new part "
                         "may use it;\n    to bring it back, rename parts/"
                         f"{d}/{R.RETIRED_MARKER} to {R.MARKER} AND put \"{d}\" back on roles in "
                         f"{_descriptor_shown()}, both by hand (no command does it).")
    ans = PC.stream_timed_read(seam.read_line, f"  type the directory name ({d}) to retire: ",
                         channel="command").strip()
    if ans != d:
        seam.emit("command", "  cancelled — nothing changed.")
        return
    why = PC.stream_timed_read(seam.read_line, "  why (one line, may be blank): ",
                               channel="command").strip()
    refused = part_write_refused(R.PARTS_DIR / d)       # the same guard part_add() has
    if refused:
        seam.emit("command", f"  cancelled — {refused}")
        return
    # OFF THE GROUP'S LIST FIRST (D127): a role left on `roles` with no seat makes every plain
    # open refuse ("unknown part"), so a list that cannot be edited stops the retire here.
    try:
        desc = _group_roles_edit(drop=d)
    except Exception as e:                                      # noqa: BLE001
        seam.emit("command", f"  cancelled — nothing changed: {t} could not be taken off the "
                             f"group's list ({e}). Take \"{d}\" off roles in "
                             f"{_descriptor_shown()}, then retire again.")
        return
    import datetime
    from atomic_write import record_atomic_write
    marker = R.PARTS_DIR / d / R.MARKER
    retired = R.PARTS_DIR / d / R.RETIRED_MARKER
    record_atomic_write(retired, part_retire_marker_render(
        marker.read_text(encoding="utf-8"), why, datetime.date.today().isoformat()))
    marker.unlink()
    # THE ONE INDEX — work/recall_index/<group>/<part>.ndjson, the embeddings of the part's own
    # record. Derived, gitignored, never pruned by anything else; a retired part is never armed
    # again (recall_index_arm_start takes the circle's parts), so nothing rebuilds it.
    try:
        import recall_index as RI
        cache = RI.recall_cache_locate(d)
        if cache.is_file():
            cache.unlink()
    except Exception:                                           # noqa: BLE001
        pass
    # THE TABLES FOLLOW AT THE NEXT OPEN, as R548 already has them: circle.main() rescans parts/
    # first thing and re-binds the group when the scan moved, which runs every follower —
    # transcript_store's TAG_TO_PART among them. Nothing in this process reads an old transcript
    # between here and there without an open circle. (A record_paths.group_set() HERE would
    # rebind to the real tree under a probe that pointed R.PARTS_DIR elsewhere — measured
    # 2026-09-12, when it wrote a probe's part into groups/ifs/.)
    seam.emit("command", f"  {t} is retired — parts/{d}/{R.MARKER} is now {R.RETIRED_MARKER}"
                         + (", and it is off the group's list." if desc else "."))
    try:
        import gitrepo as G
        G.system_git_paths_commit([marker, retired] + ([desc] if desc else []),
                       f"part-retire: {d}",
                       lambda kind, msg: seam.emit("command", f"  {msg}"))
    except Exception as e:                                      # noqa: BLE001
        seam.emit("command", f"  (the retirement is not committed — {e}; "
                             f"commit it by hand)")
