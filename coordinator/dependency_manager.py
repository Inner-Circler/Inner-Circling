#!/usr/bin/env python3
"""
dependency_manager.py — the DEPENDENCY map: what still leans on a record when it is about to
be removed, and the plan that removes or preserves each dependent first. REPORT ONLY here;
the removal verbs and the vetting loop are what act on a plan.

    python coordinator/dependency_manager.py --of <id-or-Tag> [--kind <kind>] [--json]
        n0001 · BP-0001 · CO-0001 · TP-0001 · P-12 · Idealist — what removing it would break

    import dependency_manager as DM
    DM.dependency_dependents_read(kind, ident)      one hop, read only
    DM.dependency_plan(kind, ident)                 the transitive plan, cycle-safe
    DM.dependency_plan_render(plan)                 the lines Self reads
    DM.dependency_target_parse(text)                "n0001" -> ("issue", "n0001")

The operator, 2026-09-15: *"What can be predicted where an item (e.g. an issue-relationship)
has a dependency upon some object (e.g. issue) that is proposed for deletion? Can an action
that would break a dependency be determined, and the dependency(s) be staged for explanation,
vetting, and prior removal? And the final action be automatically rejected if its dependencies
are not removed?"* Then: *"build the whole thing, preserve what is requires so as not to break
anything."* (R570).

THE MAP IS DECLARED, NOT DISCOVERED. REFERENCES below names every field in the record that
points at another record's id, what it points at, and what a removal of the target does to
the holder: REMOVE (the holder must go first — an issue-relationship whose end would no longer
be live, the closure rule issue_status.py already refuses on), PRESERVE (the holder stays as
it is, on purpose — a retired part's quotes stay attributed, a practice addressed to it stays
the record, an observation chain keeps its shell), CASCADE (a proposal that depends on a denied
one is denied with it — proposal_vetting's rule), or HANDLED (the removal verb does it itself
— /part-retire takes the name off the group's roles). A reference the map does not declare
does not exist to the walker, which is the point: a self-reference enters only where a record
shape says so.

THE WALKER NEVER LOOPS. dependency_plan() carries a visited set and a stack; a back edge is a
RING, reported as one group to be ruled together, never walked twice. Today every REMOVE
dependent (an issue-relationship) has no dependents of its own, so the walk is one hop deep;
the walker is general anyway, because the map will grow.

READ ONLY. Every register is read through its own reader, fresh, and nothing here writes.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "memory"))

KINDS = ("issue", "issue-relationship", "practice", "better-option", "observation", "part",
         "topic", "proposal")
ACTIONS = ("remove", "preserve", "cascade", "handled")

# holder · field · target · on_removal · why. One row per reference the record carries.
REFERENCES: tuple[dict, ...] = (
    {"holder": "issue-relationship", "field": "source/target", "target": "issue",
     "on_removal": "remove",
     "why": "an issue-relationship is legal only while both ends are live (the closure rule); "
            "it is retired first, its own ruling"},
    {"holder": "issue", "field": "evidence.part", "target": "part", "on_removal": "preserve",
     "why": "a quote stays attributed to the part that spoke it; a retired part's words are "
            "still its own, marked retired"},
    {"holder": "practice", "field": "addressee", "target": "part", "on_removal": "preserve",
     "why": "the row is the record; it reaches no prompt while the part is retired and "
            "reaches it again if the part returns"},
    {"holder": "coalesce-group", "field": "members", "target": "practice",
     "on_removal": "preserve",
     "why": "a ruled group is provenance of what was denied-by-coalesce; a live group is "
            "re-derived from whatever is pending"},
    {"holder": "coalesce-group", "field": "members", "target": "proposal",
     "on_removal": "preserve", "why": "the same: a group is provenance, never a dependency"},
    {"holder": "observation", "field": "chain", "target": "observation",
     "on_removal": "preserve",
     "why": "retire hides and purge keeps the id and chain shell, so a chain onto it never "
            "breaks"},
    {"holder": "proposal", "field": "depends_on", "target": "proposal", "on_removal": "cascade",
     "why": "a proposal that depends on a denied one is denied with it, at vetting"},
    {"holder": "group", "field": "roles", "target": "part", "on_removal": "handled",
     "why": "/part-retire takes the name off the group's roles in the same act"},
)

# THE READERS, swappable by a probe (module attributes): every register through its own
# reader, imported late so this module costs nothing to import.
READERS: dict = {
    "issues": lambda: __import__("issue_index").issue_index_read(),
    "practices": lambda: __import__("practice_manager").practice_read(),
    "observations": lambda: __import__("circle_observation_manager").circle_observation_read(),
    "proposals": lambda: __import__("proposal_manager").proposal_read(),
    "groups": lambda: __import__("proposal_group_manager").proposal_group_read(),
    "parts": lambda: __import__("part_add").part_rows_read(),
}


def _read(name: str) -> list | dict:
    try:
        return READERS[name]()
    except Exception:                                            # noqa: BLE001
        return {} if name == "issues" else []


def _ref(holder: str, target: str) -> dict:
    for r in REFERENCES:
        if r["holder"] == holder and r["target"] == target:
            return r
    raise KeyError(f"no reference {holder} -> {target} in the map")


def _dep(kind: str, ident: str, label: str, ref: dict, line: str = "") -> dict:
    return {"kind": kind, "id": ident, "label": label, "action": ref["on_removal"],
            "line": line, "why": ref["why"], "field": f"{ref['holder']}.{ref['field']}"}


# ------------------------------------------------------------------ one hop
def dependency_dependents_read(kind: str, ident: str) -> list[dict]:
    """Everything that references (kind, ident), one hop, each with the map's action and —
    for a REMOVE dependent — the line that removes it. Read only."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, not {kind!r}")
    out: list[dict] = []
    if kind == "issue":
        g = _read("issues")
        ref = _ref("issue-relationship", "issue")
        for nid in sorted(g):
            for typ, tgt, st in g[nid].get("edges", []):
                if st != "open" or ident not in (nid, tgt):
                    continue
                eid = f"{nid} {typ} {tgt}"
                out.append(_dep("issue-relationship", eid, f"{nid} --{typ}--> {tgt}", ref,
                                line=f'/issue-relationship-status {nid} {typ} {tgt} = retired '
                                     f'"retiring {ident} — its end would no longer be live"'))
    elif kind == "part":
        d, tag = _part_resolve(ident)
        g = _read("issues")
        ref_ev = _ref("issue", "part")
        for nid in sorted(g):
            if d in g[nid].get("held", []):
                out.append(_dep("issue", nid, g[nid].get("label", nid), ref_ev))
        ref_pr = _ref("practice", "part")
        for p in _read("practices"):
            if p.get("addressee") == tag:
                out.append(_dep("practice", p.get("id", "?"),
                                " ".join(str(p.get("title", "")).split())[:60], ref_pr))
        out.append(_dep("group", "roles", f"{d} on the group's roles", _ref("group", "part")))
    elif kind in ("practice", "better-option"):
        ref = _ref("coalesce-group", "practice")
        for grp in _read("groups"):
            if f"practice:{ident}" in grp.get("members", []):
                out.append(_dep("coalesce-group", grp.get("id", "?"),
                                str(grp.get("gloss", ""))[:60], ref))
    elif kind == "proposal":
        ref = _ref("coalesce-group", "proposal")
        for grp in _read("groups"):
            if f"propose:{ident}" in grp.get("members", []):
                out.append(_dep("coalesce-group", grp.get("id", "?"),
                                str(grp.get("gloss", ""))[:60], ref))
        ref_c = _ref("proposal", "proposal")
        for row in _read("proposals"):
            if row.get("state") == "proposed" and ident in dependency_ids_read(row):
                out.append(_dep("proposal", row.get("id", "?"),
                                str(row.get("text", ""))[:60], ref_c))
    elif kind == "observation":
        ref = _ref("observation", "observation")
        for o in _read("observations"):
            if o.get("chain") == ident:
                out.append(_dep("observation", o.get("id", "?"),
                                " ".join(str(o.get("text", "")).split())[:60], ref))
    # topic, issue-relationship: nothing references them
    return out


def _part_resolve(ident: str) -> tuple[str, str]:
    """(dir, Tag) for a directory name or a Tag, case-insensitive; unknown stays as given."""
    for d, tag in _read("parts"):
        if ident.lower() in (d.lower(), tag.lower()):
            return d, tag
    return ident, ident


# ------------------------------------------------------------------ the plan
def dependency_plan(kind: str, ident: str) -> dict:
    """The transitive plan for removing (kind, ident): `remove` in the order to act (leaves
    first — a dependent's own dependents before it), `preserve`, `handled`, `cascade`, and
    `rings` (each a list of "kind id" that reference one another and must be ruled as one).
    Cycle-safe: a visited set and an on-stack set; a back edge is a ring, never a loop."""
    target = f"{kind} {ident}"
    remove: list[dict] = []
    preserve: list[dict] = []
    handled: list[dict] = []
    cascade: list[dict] = []
    rings: list[list[str]] = []
    visited: set[str] = set()
    on_stack: list[str] = []

    def walk(k: str, i: str) -> None:
        key = f"{k} {i}"
        if key in on_stack:
            ring = on_stack[on_stack.index(key):] + [key]
            if ring not in rings:
                rings.append(ring)
            return
        if key in visited:
            return
        visited.add(key)
        on_stack.append(key)
        for dep in dependency_dependents_read(k, i):
            if dep["action"] == "remove":
                walk(dep["kind"], dep["id"])           # its own dependents first
                # THE TARGET IS NEVER ITS OWN PREREQUISITE: a ring back to it is recorded by
                # walk() above, and the target's removal is the plan's last act, not a step.
                if f"{dep['kind']} {dep['id']}" == target:
                    continue
                if not any(d["kind"] == dep["kind"] and d["id"] == dep["id"] for d in remove):
                    remove.append(dep)
            elif dep["action"] == "preserve":
                preserve.append(dep)
            elif dep["action"] == "handled":
                handled.append(dep)
            else:
                cascade.append(dep)
        on_stack.pop()

    walk(kind, ident)
    return {"target": {"kind": kind, "id": ident}, "remove": remove, "preserve": preserve,
            "handled": handled, "cascade": cascade, "rings": rings}


def dependency_plan_is_blocked(plan: dict) -> bool:
    """True when something must be removed first — the final act is refused until then."""
    return bool(plan.get("remove")) or bool(plan.get("rings"))


def dependency_plan_render(plan: dict) -> str:
    t = plan["target"]
    n_rm, n_pv = len(plan["remove"]), len(plan["preserve"])
    lines = [f"  dependency plan for {t['kind']} {t['id']} — "
             + (f"{n_rm} must be removed first" if n_rm else "nothing must be removed first")
             + (f", {n_pv} preserved" if n_pv else "")
             + (f", {len(plan['rings'])} ring(s)" if plan["rings"] else "")]
    for n, d in enumerate(plan["remove"], 1):
        lines.append(f"  REMOVE {n}. {d['kind']} {d['label']}")
        lines.append(f"         {d['line']}")
        lines.append(f"         {d['why']}")
    for d in plan["preserve"]:
        lines.append(f"  PRESERVE  {d['kind']} {d['id']} — {d['label']}")
        lines.append(f"         {d['why']}")
    for d in plan["handled"]:
        lines.append(f"  HANDLED   {d['label']} — {d['why']}")
    for d in plan["cascade"]:
        lines.append(f"  CASCADE   {d['kind']} {d['id']} — {d['why']}")
    for ring in plan["rings"]:
        lines.append("  RING      " + " -> ".join(ring) + " — ruled as one, or not at all")
    if n_rm:
        lines.append(f"  then: the removal of {t['kind']} {t['id']} itself")
    return "\n".join(lines)


# ------------------------------------------------------------------ proposal rows
# THE ROW'S OWN GRAMMAR LIVES WITH THE ROW'S ONE WRITER, proposal_manager.py — a register — so
# the register can refuse a ring at staging without importing this orchestration module. These
# three read it through that owner.
def dependency_ids_read(row: dict) -> list[str]:
    """The proposal ids a row depends on ("P-7" or "P-7:nMMMM" entries)."""
    import proposal_manager as PR
    return PR.proposal_dependency_ids_read(row)


def dependency_placeholders_read(row: dict) -> dict[str, str]:
    """{proposal id: placeholder token} for the depends_on entries that name a token."""
    import proposal_manager as PR
    return PR.proposal_dependency_placeholders_read(row)


def dependency_ring_find(rows: list[dict], new_id: str, new_deps: list[str]) -> list[str]:
    """Would a row `new_id` depending on `new_deps` close a ring among `rows`? The ring as
    ids, or []."""
    import proposal_manager as PR
    return PR.proposal_dependency_ring_find(rows, new_id, new_deps)


def dependency_plan_stage(plan: dict, final_line: str, *, sources: tuple[str, ...] = ("Self",),
                          circle: str = "") -> tuple[list[str], str]:
    """A BLOCKED plan staged for vetting: each REMOVE step as a suggestion row, in plan order,
    then `final_line` depending on every step — so the steps are explained, vetted and acted on
    first, and denying any one of them denies the final act by cascade. A pending row with the
    same text is reused, never doubled. A ring is refused: it has no order to stage in, and is
    ruled by hand. Returns (step ids, final id)."""
    import proposal_manager as PR
    if plan.get("rings"):
        raise ValueError("the plan holds a ring — " + "; ".join(" -> ".join(r) for r in
                                                                 plan["rings"])
                         + " — it has no order to stage, and is ruled by hand")
    steps: list[str] = []
    for d in plan.get("remove", []):
        pid, _new = PR.proposal_row_stage_once("suggestion", d["line"], list(sources), circle)
        steps.append(pid)
    final, _new = PR.proposal_row_stage_once("suggestion", final_line, list(sources), circle,
                                             depends_on=steps)
    return steps, final


# ------------------------------------------------------------------ main
_PREFIX_KIND = (("n", "issue"), ("BP-", "practice"), ("CO-", "observation"), ("SO-", "observation"),
                ("TP-", "topic"), ("P-", "proposal"))


def dependency_target_parse(text: str, kind: str | None = None) -> tuple[str, str]:
    """"n0001" -> ("issue", "n0001"); a Tag or directory -> ("part", ...); `kind` overrides."""
    t = text.strip()
    if kind:
        return kind, t
    for prefix, k in _PREFIX_KIND:
        if t.startswith(prefix) and (prefix != "n" or t[1:].isdigit()):
            return k, t
    return "part", t


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--of", help="the record: an id by its prefix (n, BP-, CO-, TP-, P-) or "
                                 "a part's Tag or directory name")
    ap.add_argument("--kind", choices=KINDS, help="say the kind instead of inferring it")
    ap.add_argument("--json", action="store_true", help="print the plan as JSON too")
    args = ap.parse_args()
    if not args.of:
        ap.print_help()
        return 2
    kind, ident = dependency_target_parse(args.of, args.kind)
    plan = dependency_plan(kind, ident)
    print(dependency_plan_render(plan))
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
