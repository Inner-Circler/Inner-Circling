#!/usr/bin/env python3
"""
issue_commands.py — parse, record and apply Self's in-circle graph rulings.

    /issue-label-update  nNNNN "new name" ["comment"]
    /issue-relationship-add  nNNNN leads-to nMMMM ["comment"]
    /issue-evidence-add  nNNNN <stmt#> "why"
    /issue-relationship-status nNNNN <type> nMMMM = retired "reason"   (issue-relationship-update)

`issue-evidence-add` differs from the first two in one way that matters: its quote
is NOT Self's own words, typed fresh into the command line — it is a PRIOR
statement, by any part or Self, already in this circle's transcript. `parse()`
stays pure (it only knows the statement NUMBER); circle.py resolves `<stmt#>`
against the live transcript (same numbering `/issue-evidence-list` shows) and fills in
`part`/`quote`/`source` before this module ever sees the command, exactly the
way it already resolves `precheck()` against the live graph. R160/B40,
2026-08-13, docs/HELP_DESIGN.md §4 item 2 — docs/operations.md row 10 named
this gap 2026-08-04 and it was done by hand 8 times since.

The fourth form (internally `verb == "issue-relationship-update"`) reads
OBJECT-CLASS shaped, R161, 2026-08-13 — a node id right after `/issue`,
matching how `/issue-status nNNNN = <value>` already reads for a node —
but a NODE id right after `/issue` is also exactly what `circle.py`'s
bare node-status form starts with. `parse()` tells the two apart the only
way it can: the THIRD token. A node op (`status`) is never an edge type,
so `a[1] ==` a node id `and a[2] in S.EDGE_TYPES` is unambiguous. Scoped
to `status = retired` only for now — moving an edge TO
`attested`/`proposed` needs a quote/an ask the same way
`issue-relationship-add`/`issue-evidence-add` do, not yet built.

THREE RULINGS, 2026-08-04, and each one is load-bearing:

1.  A COMMAND IS ECHOED INTO THE TRANSCRIPT AS AN OPERATOR STATEMENT, and is NOT
    sent to the parts. That single decision solves the problem that blocked
    the whole design: an edge cannot be `attested` without a verbatim quote
    from a real circle, and Self typing a command was not, until now, saying
    anything. Now the command line IS his words, on the record, in a real
    transcript — so the gate can verify the edge it produced by exactly the
    same rule it applies to everything else. No exemption was needed.

    Not sending it to the parts is the other half. On 2026-08-01 a command
    that did not yet exist fell through to the room and became content — the
    One part called the mark "the ember-tending act" (LOG.md E06). A ruling
    about the graph is not a statement to the room, and the room reacting to
    it would contaminate the record it is being written from.

2.  `issue-label-update` (named `update-label` until R209, 2026-08-17),
    not `update`. The verb names what it changes.

3.  A LIVE circle applies its commands automatically at close. A SANDBOX
    circle records them and applies nothing — which is what finally lets a
    sandbox circle propose to the live tree without touching it.

WHY AT CLOSE AND NOT IMMEDIATELY. Each part's briefing is compiled into its
system prompt when the circle OPENS. A mid-circle graph write either never
reaches the room, or reaches it by rebuilding seven prompts and discarding
the cache for all of them. Immediate costs real money and shows the room
nothing.

VALIDATION IS ALL-OR-NOTHING. `apply()` copies `issues/` to a temp graph,
applies every command there, and runs the real gate over the copy. The live
tree is written only if the whole batch passes. `issue_gate.py` has taken a
directory argument for exactly this since it was written.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "coordinator"))  # paths/atomic_write et al.
import issue_schema as S
from atomic_write import atomic_write                                       # noqa: E402

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = S.ROOT
NODE_RE = re.compile(r"^n\d{4}$")
# "quoted, with \" escapes" | bare-word
ARG_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|(\S+)')


def _args(rest: str) -> list[str]:
    return [(m.group(1).replace('\\"', '"') if m.group(1) is not None
             else m.group(2)) for m in ARG_RE.finditer(rest)]


def _parse_update_relation(a: list[str], circle: str,
                           line: str) -> tuple[dict | None, str]:
    """R161, respelled by R261 (2026-08-20):
    `/issue-relationship-status nNNNN <type> nMMMM ["="] retired "why"`.

    `a` IS THE ARGUMENT LIST, starting at the node — the verb is the slash
    head now and parse() has already consumed it. It read `/issue nNNNN
    <type> ...`, a two-token verb whose first argument was the object, until
    R261 made the whole verb the head.

    THE PROPERTY IS `status` AND IT IS NOW IN THE VERB, which is the
    construct R261 ruled: `<object>-<property>-<method>`, and a trailing
    `= <value>` writes it. The bare `status` keyword is still ACCEPTED
    before the `=` so a line typed the old way still parses — it is
    redundant, not wrong, and refusing it would buy nothing.

    Scoped to `retired` only for now — the one gap actually named
    (HELP_DESIGN.md §4 item 5: "the only way to mark an edge no longer live
    is `retired` prose... not a real status transition"). Moving an edge TO
    `attested`/`proposed` needs a quote/an ask the same way
    issue-relationship-add/issue-evidence-add do, which this command does not
    yet solicit — refused explicitly, not silently mis-applied."""
    if not a:
        return None, ('usage: /issue-relationship-status nNNNN <type> nMMMM '
                      '= retired "why"')
    src = a[0]
    usage = (f'usage: /issue-relationship-status {src} <type> nMMMM '
             f'= <value> ["why"]')
    if not NODE_RE.match(src):
        return None, f"{src} is not an issue id (nNNNN)"
    if len(a) < 3:
        return None, usage
    typ, tgt = a[1], a[2]
    if not NODE_RE.match(tgt):
        return None, f"{tgt} is not an issue id (nNNNN)"
    if typ not in S.EDGE_TYPES:
        return None, (f"{typ!r} is not an issue-relationship type. "
                      f"Known: {', '.join(sorted(S.EDGE_TYPES))}")
    rest = a[3:]
    # The redundant `status` keyword, kept accepted — see the docstring.
    if rest and rest[0] == "status":
        rest = rest[1:]
    elif rest and rest[0].startswith("status="):
        rest = [rest[0].split("=", 1)[1]] + rest[1:]
    if not rest:
        return None, usage
    if rest[0] == "=":
        rest = rest[1:]
    elif rest[0].startswith("="):
        rest = [rest[0][1:]] + rest[1:]
    if not rest or not rest[0].strip():
        return None, "status value is required"
    val = rest[0]
    if val != "retired":
        return None, (f"{val!r} not supported yet — issue-relationship-"
                      f"update only retires an issue-relationship today (status = "
                      f"retired). attested/proposed need a quote/an ask, "
                      f"same as issue-relationship-add, not yet built")
    if len(rest) < 2 or not rest[1].strip():
        return None, 'a reason is required — status = retired "reason"'
    if len(rest) > 2:
        return None, f"too many arguments ({len(rest) - 2} extra)"
    return {"verb": "issue-relationship-update", "node": src, "type": typ,
            "target": tgt, "value": val, "why": rest[1],
            "circle": circle, "line": line.strip()}, ""


# THE VERB IS THE SLASH HEAD — R261, 2026-08-20. Every one of these was
# `/issue <verb> ...`, a two-token form whose first argument happened to name
# the verb, while docs/BNF.md had ruled the NAME as a single hyphenated
# `<object>-<property>-<method>` token since 2026-08-15 (B16). The line now
# matches the name.
#
# THIS TABLE IS THE ONE PLACE THE HEADS ARE SPELLED for this module. The
# command table in coordinator/command_surface.py is the surface; this is the
# parser; test_issue_commands.py asserts they agree.
HEADS: dict[str, str] = {
    "/issue-label-update": "issue-label-update",
    "/issue-relationship-add": "issue-relationship-add",
    "/issue-evidence-add": "issue-evidence-add",
    "/issue-relationship-status": "issue-relationship-update",
}


def parse(line: str, circle: str) -> tuple[dict | None, str]:
    """(command, "") or (None, why not). Pure — touches no file.

    Refuses on anything it does not fully understand. A command that half
    parses is the failure mode `/mark` had: `/mark 5 platitude test` silently
    read `test` as a note.

    THE HEAD DECIDES, since R261. Before that this gated on `a[0] ==
    "/issue"` and branched on whether `a[1]` looked like a node id — which
    is how one verb name came to mean two different commands depending on
    the shape of its own first argument."""
    a = _args(line.strip())
    if not a:
        return None, "not an issue command"
    verb = HEADS.get(a[0])
    if verb is None:
        return None, (f"not an issue command: {a[0]!r}. "
                      f"Known: {', '.join(sorted(HEADS))}")
    args = a[1:]

    if verb == "issue-relationship-update":
        return _parse_update_relation(args, circle, line)

    if verb == "issue-label-update":
        if len(args) < 2:
            return None, ('usage: /issue-label-update nNNNN "new name" '
                          '["comment"]')
        node, label = args[0], args[1]
        if not NODE_RE.match(node):
            return None, f"{node} is not an issue id (nNNNN)"
        if not label.strip():
            return None, "the new label is empty"
        if len(args) > 3:
            return None, f"too many arguments ({len(args) - 3} extra)"
        return {"verb": verb, "node": node, "label": label,
                "comment": args[2] if len(args) > 2 else "",
                "circle": circle, "line": line.strip()}, ""

    if verb == "issue-relationship-add":
        if len(args) < 3:
            return None, ('usage: /issue-relationship-add nNNNN <type> '
                          'nMMMM ["comment"]')
        src, typ, tgt = args[0], args[1], args[2]
        for n in (src, tgt):
            if not NODE_RE.match(n):
                return None, f"{n} is not an issue id (nNNNN)"
        if typ not in S.EDGE_TYPES:
            return None, (f"{typ!r} is not an issue-relationship type. "
                          f"Known: {', '.join(sorted(S.EDGE_TYPES))}")
        if src == tgt:
            return None, "an issue-relationship cannot point at itself"
        if len(args) > 4:
            return None, f"too many arguments ({len(args) - 4} extra)"
        return {"verb": verb, "node": src, "type": typ, "target": tgt,
                "comment": args[3] if len(args) > 3 else "",
                "circle": circle, "line": line.strip()}, ""

    if verb == "issue-evidence-add":
        if len(args) < 2:
            return None, 'usage: /issue-evidence-add nNNNN <stmt#> "why"'
        node, stmt_raw = args[0], args[1]
        if not NODE_RE.match(node):
            return None, f"{node} is not an issue id (nNNNN)"
        try:
            stmt = int(stmt_raw)
        except ValueError:
            return None, f"{stmt_raw!r} is not a statement number"
        if stmt < 1:
            return None, "statement number must be 1 or greater"
        if len(args) < 3 or not args[2].strip():
            return None, ('why is required — usage: /issue-evidence-add '
                          'nNNNN <stmt#> "why"')
        if len(args) > 3:
            return None, f"too many arguments ({len(args) - 3} extra)"
        # part/quote/source are NOT set here — circle.py resolves them
        # against the live transcript right after this call, and adds
        # them to this same dict before precheck()/apply() ever see it.
        return {"verb": verb, "node": node, "stmt": stmt, "why": args[2],
                "circle": circle, "line": line.strip()}, ""

    return None, f"unknown issue verb {verb!r}"


def all_edges(graph: dict[str, dict] | None = None) -> list[dict]:
    """Every edge on a live node, flattened out — HELP_DESIGN.md §4 item
    3. Before this, "list all edges" meant "read every issue node and
    collect its edges array" inline wherever it was needed; this is
    that operation, named once. Each entry is the edge's own dict plus
    `src`, the node it hangs off — an edge carries no id of its own, so
    (src, type, target) is the closest thing to one (docs/HELP_DESIGN.md
    §3: relationship's id is `<src> <type> <tgt>`)."""
    if graph is None:
        graph = {d["id"]: d for d in (S.load(p) for p in S.live_nodes())}
    return [{"src": nid, **e}
            for nid in sorted(graph)
            for e in graph[nid].get("edges", [])]


def precheck(cmd: dict, graph: dict[str, dict]) -> str:
    """What can be known before the circle ends. Returns "" or a reason.

    Deliberately partial: the authoritative answer is the gate, run over the
    whole batch at close. This exists so Self learns at the prompt that he
    named a node that does not exist, rather than at close."""
    for key in ("node", "target"):
        n = cmd.get(key)
        if n and n not in graph:
            return f"no such issue {n}"
    if cmd["verb"] == "issue-relationship-add":
        for n in (cmd["node"], cmd["target"]):
            if graph[n]["status"] != "live":
                return (f"{n} is `{graph[n]['status']}`, not live — an "
                        f"issue-relationship is legal only when both ends "
                        f"are live")
        for e in graph[cmd["node"]].get("edges", []):
            if (e.get("target") == cmd["target"]
                    and e.get("type") == cmd["type"]
                    and e.get("status") != "retired"):
                return f"{cmd['node']} already has this issue-relationship ({e['status']})"
    if cmd["verb"] == "issue-label-update":
        if graph[cmd["node"]]["label"] == cmd["label"]:
            return "that is already the label"
    if cmd["verb"] == "issue-evidence-add":
        node = graph[cmd["node"]]
        if node["status"] != "live":
            return f"{cmd['node']} is `{node['status']}`, not live"
        if any(e.get("quote") == cmd["quote"]
               for e in node.get("evidence", [])):
            return "that statement is already attached as evidence to this issue"
    if cmd["verb"] == "issue-relationship-update":
        e = next((x for x in graph[cmd["node"]].get("edges", [])
                  if x.get("type") == cmd["type"]
                  and x.get("target") == cmd["target"]
                  and x.get("status") != "retired"), None)
        if e is None:
            return (f"no live issue-relationship {cmd['node']} --{cmd['type']}--> "
                    f"{cmd['target']} to update")
        if e["status"] == cmd["value"]:
            return "that is already the status"
    return ""


def describe(cmd: dict) -> str:
    if cmd["verb"] == "issue-label-update":
        return f'{cmd["node"]} label -> "{cmd["label"]}"'
    if cmd["verb"] == "issue-evidence-add":
        q = cmd["quote"]
        q = q if len(q) <= 40 else q[:40] + "..."
        return f'{cmd["node"]} evidence <- {cmd["part"]}: "{q}"'
    if cmd["verb"] == "issue-relationship-update":
        return (f'{cmd["node"]} --{cmd["type"]}--> {cmd["target"]} '
                f'status -> {cmd["value"]}')
    return f'{cmd["node"]} --{cmd["type"]}--> {cmd["target"]}'


# --------------------------------------------------------------- the record
def _q(s: str) -> str:
    """A TOML basic string, escaped for real — not just the backslash case
    the pre-`issue-evidence-add` version handled. A verbatim transcript quote is
    exactly the field likely to carry a `"` or an embedded newline (someone
    quoting someone, a multi-line statement); unescaped either one produced
    a commands.toml `tomllib` cannot parse back."""
    return ('"' + s.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("\r", "\\r") + '"')


def dump(cmds: list[dict], circle: str) -> str:
    out = [f'circle = "{circle}"',
           f'written = "{_dt.datetime.now().isoformat(timespec="seconds")}"',
           ""]
    for c in cmds:
        out.append("[[command]]")
        for k in ("verb", "node", "label", "type", "target", "value",
                  "comment", "line", "stmt", "part", "quote", "why",
                  "source"):
            if c.get(k):
                out.append(f'{k} = {_q(str(c[k]))}')
        out.append("")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------- applying
def _history(cmd: dict, today: str) -> str:
    if cmd["verb"] == "issue-evidence-add":
        q = cmd["quote"]
        q = q if len(q) <= 60 else q[:60] + "..."
        return (f'- **{today}** — Evidence added by Self in '
                f'`{cmd["circle"]}`, from {cmd["part"]}: "{q}". '
                f'Why: {cmd["why"]}')
    if cmd["verb"] == "issue-relationship-update":
        return (f'- **{today}** — Relation `{cmd["type"]}` -> {cmd["target"]} '
                f'status set to **{cmd["value"]}** by Self in '
                f'`{cmd["circle"]}`. {cmd["why"]}')
    c = f' *"{cmd["comment"]}"*' if cmd.get("comment") else ""
    if cmd["verb"] == "issue-label-update":
        return (f'- **{today}** — Label ruled by Self in `{cmd["circle"]}`: '
                f'**{cmd["label"]}**.{c}')
    return (f'- **{today}** — Relation `{cmd["type"]}` -> {cmd["target"]} '
            f'added by Self in `{cmd["circle"]}`.{c}')


def apply_one(cmd: dict, issues: pathlib.Path, today: str) -> None:
    """Mutate ONE node file inside `issues`, which may be a temp copy."""
    path = next(p for p in issues.glob("*.toml")
                if p.name.endswith(f"{cmd['node']}.toml"))
    doc = S.load(path)

    if cmd["verb"] == "issue-label-update":
        old = doc["label"]
        doc["label"] = cmd["label"]
        doc["label_ruled"] = cmd["circle"]
        al = list(doc.get("aliases", []))
        if old not in al:
            al.append(old)                    # R007: the old name is kept
        doc["aliases"] = al
    elif cmd["verb"] == "issue-evidence-add":
        # part/quote/source were resolved by circle.py against the live
        # transcript at parse time (see module docstring) — this function
        # never touches a transcript, only the cmd dict it was handed.
        doc.setdefault("evidence", []).append({
            "part": cmd["part"], "source": cmd["source"],
            "quote": cmd["quote"], "why": cmd["why"]})
        hb = list(doc.get("held_by", []))
        if cmd["part"] not in hb:
            hb.append(cmd["part"])
        doc["held_by"] = hb
    elif cmd["verb"] == "issue-relationship-update":
        # precheck() already found exactly this edge and confirmed the
        # value differs from its current status — re-finding it here
        # (rather than passing an index through) keeps apply_one()'s
        # only input the cmd dict, same as every other verb.
        e = next(x for x in doc.get("edges", [])
                 if x.get("type") == cmd["type"]
                 and x.get("target") == cmd["target"]
                 and x.get("status") != "retired")
        e["status"] = cmd["value"]
        if cmd["value"] == "retired":
            e["retired"] = f"{today} — {cmd['why']}"
    else:
        # The quote is the COMMENT if he gave one, else the whole command
        # line. Either is verbatim in the transcript, because the coordinator
        # wrote both — the comment is a substring of the line it sits in.
        # .get, not [ ]: dump() omits empty fields and the __main__ TOML
        # loader restores no defaults, so a comment-less ruling re-applied
        # from its commands_<ot>.toml arrives with no `comment` key at all
        # — bare indexing broke the documented sandbox-promotion path for
        # every such ruling (2026-08-18 review, tier 2 #16).
        quote = cmd.get("comment") or cmd.get("line") or ""
        doc.setdefault("edges", []).append({
            "type": cmd["type"], "target": cmd["target"],
            "status": "attested", "dated": today,
            # The gate finds the circle by regex IN THE BASIS. Naming it here
            # is not decoration; an attested edge whose basis omits it fails.
            "basis": f"Ruled by Self in the room, {cmd['circle']}.",
            "quote": quote})

    hist = doc.get("description_history", "").rstrip("\n")
    doc["description_history"] = f"{hist}\n\n{_history(cmd, today)}\n"
    S.save(path, doc)


def apply(cmds: list[dict], issues: pathlib.Path | None = None,
          dry_run: bool = False) -> tuple[bool, str]:
    """Validate the WHOLE batch against a copy, then promote it or nothing."""
    issues = issues or S.ISSUES
    if not cmds:
        return True, "no commands"
    today = _dt.date.today().isoformat()

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "issues"
        shutil.copytree(issues, tmp)
        cur = cmds[0]
        try:
            for cur in cmds:
                apply_one(cur, tmp, today)
        except Exception as e:                          # noqa: BLE001
            # `cur`, not cmds[0] — the error used to always describe the
            # FIRST command, sending the operator to debug the wrong ruling
            # whenever a later one raised.
            return False, f"could not apply {describe(cur)}: {e}"
        r = subprocess.run([sys.executable, "memory/issue_gate.py",
                            str(tmp)], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            body = (r.stdout + r.stderr).strip()
            return False, ("the batch does not pass the gate — NOTHING was "
                           "written:\n" + "\n".join(
                               "    " + l for l in body.splitlines()[-12:]))
        if dry_run:
            return True, f"{len(cmds)} command(s) would apply cleanly"
        # PROMOTE BY MOVE, NOT BY RE-RUNNING — docs/HELP_DESIGN.md §6.2,
        # built 2026-08-20. This used to leave the `with` block (destroying
        # the validated copy) and then run `apply_one` a SECOND time against
        # the real tree. Two consequences, and the doc named both:
        #
        #   a crash between file 1 and file 2 of a multi-command batch left
        #     a HALF-APPLIED batch on the real tree — even though the gate
        #     had just said the WHOLE batch was fine
        #   the mutation ran TWICE per command, so anything not perfectly
        #     idempotent between the two runs could diverge from what was
        #     validated. Nothing today is non-idempotent; nothing prevented
        #     it either
        #
        # What is promoted is the BYTES the gate approved. A status change
        # RENAMES a node's file (the prefix IS the status), so the sync is
        # three-way: written, replaced, and removed.
        #
        # atomic_write PER FILE, not os.replace from the temp dir: the
        # temp directory can be on another volume (it usually is on this
        # machine — %TEMP% is C:, the tree is D:), and os.replace across
        # volumes fails. atomic_write writes a sibling of the DESTINATION
        # and replaces in place, which is the atomicity that matters.
        return True, _promote(tmp, issues, len(cmds))


def _promote(tmp: pathlib.Path, issues: pathlib.Path, n: int) -> str:
    """Copy the VALIDATED tree over the real one. See apply()'s own note."""
    src = {f.name: f for f in tmp.iterdir() if f.is_file()}
    dst = {f.name: f for f in issues.iterdir() if f.is_file()}
    written = 0
    for name, f in src.items():
        data = f.read_bytes()
        if name in dst and dst[name].read_bytes() == data:
            continue
        atomic_write(issues / name, data.decode("utf-8"))
        written += 1
    removed = 0
    for name, f in dst.items():
        if name not in src:
            # A RENAME, not a deletion: apply_one renames a node's file when
            # its status changes, so the old name is gone from the validated
            # copy and the new one is already written above.
            f.unlink()
            removed += 1
    return (f"{n} command(s) applied — {written} file(s) written"
            + (f", {removed} renamed away" if removed else ""))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="apply a circle's commands.toml")
    ap.add_argument("record", help="path to a circle's commands.toml")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib                      # 3.10 and older
    rec = tomllib.loads(pathlib.Path(a.record).read_text(encoding="utf-8"))
    cmds = [dict(c, circle=rec["circle"]) for c in rec.get("command", [])]
    print(f"  {rec['circle']} — {len(cmds)} command(s)")
    for c in cmds:
        print(f"    {describe(c)}")
    ok, msg = apply(cmds, dry_run=a.dry_run)
    print(f"  {msg}")
    raise SystemExit(0 if ok else 1)
