#!/usr/bin/env python3
"""
proposal_vetting.py — Self's ruling loop over every pending propose-class
proposal, and the approve/deny executors it dispatches to. Phase 2
stage 4 of the coordinator partitioning (2026-08-16; built sixth —
_propose_approve executes commands through dispatch_dev_cmd and
cmd_issue_object, so the commands stage had to land first, the
dependency the phase-2 plan recorded at delivery). Until then all of
it lived in circle.py. Verbatim move — bodies and comments unchanged,
except console I/O goes through seam.emit/seam.read_line by attribute
access; approve/deny/skip stays Self's alone, read from the console.

_propose_approve NO LONGER CALLS dispatch_dev_cmd(), as of B62
2026-08-23 — the sentence above describes the phase-2 build-order
dependency, not the current call graph. /issue-add (R290), /practice-add
and /better-option-add (B62) each run their own cmd_* directly and read
its (ok, msg); dispatch_dev_cmd()'s only channel was "did I recognise
this head", which could not tell a real register refusal from success.

issue_graph_now_read() moves WITH the vetting loop — Self's explicit ruling on
the phase-2 plan's open decision — because _propose_approve is its one
consumer: a command-shaped proposal is re-classified and re-parsed
fresh at approval time against the live graph, never trusted from a
staging-time snapshot. test_proposal_manager patches proposal_vetting.graph_now (and
IC.issue_precheck/IC.issue_command_apply on their own module) to isolate this loop from
the real tree — module-attribute patching against the OWNER, the same
late-binding contract seam.py documents.
"""

from __future__ import annotations

import issue_commands as IC
import issue_schema as S_
import phase_clock as PC     # timed_read — a ruling prompt is human time
import seam
from annotations import _propose_command_shape
from propose_lifecycle import _wrap58, _normalize_edge   # stage 8, 2026-09-03


def _today() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def issue_graph_now_read() -> dict:
    """The live issue graph, freshly loaded. Module-level (promoted out of
    main()'s own local closure 2026-08-13, #32) because _propose_approve()
    below needs it too, from a context with no access to main()'s locals —
    it is a pure function of issue_schema, nothing closed over."""
    return {d["id"]: d for d in (S_.issue_read(q) for q in S_.issue_nodes_read())}

def _practice_describe(row: dict, PM) -> tuple[str, list[str]]:
    pid, op = row["id"], row.get("op", "?")
    sources = ", ".join(row.get("sources", [])) or "unknown source"
    header = f"[{pid}] {op} — {sources} · {row.get('circle', '?')}"
    target = PM.practice_read_by_id(row.get("target_id", "")) if op != "add" else None
    detail = []
    if op == "add":
        detail.append(row.get("title", ""))
    elif op == "delete":
        detail.append("delete: "
                      f"{target['title'] if target else '(target already gone)'}")
    else:                                                  # revise
        was = target["title"] if target else "(target already gone)"
        now = row.get("title") or "(not unanimous — see below)"
        detail.append(f"revise: {was}")
        detail.append(f"    -> {now}")
    if row.get("record"):
        detail += [f"| {l}" for l in _wrap58(row["record"])]
    return header, detail


def _practice_approve(row: dict, PM) -> tuple[bool, str]:
    """The one propose-class kind whose approval can itself prompt
    further — a non-unanimous revise has no single candidate text, so
    Self authors the final wording here rather than accepting a blank."""
    title = row.get("title", "")
    if row.get("op") == "revise" and not title:
        try:
            title = PC.stream_timed_read(seam.read_line, "        revision text "
                                  "(candidates above)> ").strip()
        except (EOFError, KeyboardInterrupt):
            title = ""
        if not title:
            return False, "no text given — leaving this one pending"
    return PM.practice_approve(row["id"], title=title)


# The circle_/sandbox_ normalization that used to sit here
# (_gate_circle_ref) is the register's own since R243, 2026-08-19 —
# proposals.circle_ref, applied by stage() itself, so new rows carry the
# prefixed transcript ref already. Approval below still runs it as the
# healing guard: rows staged before R243 carried the bare open time, and
# without the prefix the gate's attested-edge basis regex (R061) refused
# every issue-relationship-add approval, leaving the row pending forever.


# The ceiling on a verb's gloss at vetting, for the description whose first sentence is
# itself long. A cap, not a target — most land well under it.
GLOSS_MAX = 220


def _suggestion_gloss(line: str) -> str:
    """What the verb DOES, in the person's own words — or "" for a head with no row.

    THE SAME /help DESCRIPTION command_suggest.py's own catalogue is built from, read
    through that module's reader rather than restated, so this cannot drift from the
    text the recogniser was given. The import is function-local for the reason every
    other one in this file is: vetting is reached from the open step, and that module
    reaches the command surface and the class table."""
    import command_suggest as CSG
    head = (line.split() or [""])[0]
    row = next((r for r in CSG.command_suggest_catalogue_read()
                if r["head"] == head), None)
    if not row:
        return ""
    # THE FIRST SENTENCE, NOT THE WHOLE PAGE. A /help description runs to the mechanics —
    # what Enter does, which list numbers it reads, the date it was built — and several
    # pending rows each carrying six wrapped lines is a screen Self has to hunt through
    # at the moment it is deciding. SPLIT ON ". ", NEVER ".": `part.toml declares.` has no
    # space after its first period, and splitting on the bare period cuts that verb's own
    # description in half.
    desc = row["description"]
    head_sentence, sep, _rest = desc.partition(". ")
    desc = head_sentence + "." if sep else desc
    return f"{head} — {desc[:GLOSS_MAX]}"


def _propose_describe(row: dict) -> tuple[str, list[str]]:
    """An evidence offer shows the words it would attach, whole — its `text`
    names only the issue and the why, and Self reads the words before
    approving (R541).

    A SUGGESTION SHOWS WHAT ITS VERB DOES, AND THE WORDS THAT PROMPTED IT.
    The operator, 2026-09-15, answer (a), after a staged /part-context-update read as a bare
    line. A suggestion's `text` is the command line ALONE (R570), which carries its own
    content for /issue-add "<describe>" and says nothing at all for a verb whose form is
    pure verb-plus-target. Both halves come from material already on file — the verb's
    own description, and the quote the recogniser now passes through — so neither adds a
    column to the register."""
    sources = ", ".join(row.get("sources", [])) or "unknown source"
    header = (f"[{row['id']}] propose ({row.get('kind', '?')}) — "
             f"{sources} · {row.get('circle', '?')}")
    detail = _wrap58(row.get("text", "")[:300])
    if row.get("kind") == "suggestion" and (gloss := _suggestion_gloss(row.get("text", ""))):
        detail += _wrap58(gloss)
    if row.get("quote"):
        detail += _wrap58(f'the words: "{row["quote"]}"')
    return header, detail


def _offer_fill(cmd: dict, row: dict) -> str:
    """An evidence offer's statement onto its command — `part` and `quote`
    from the row, `source` its circle — or why it cannot be. The row carries
    them because its `text` names no statement (R541);
    a row without them stays pending rather than raising inside the precheck."""
    if cmd.get("verb") != "issue-evidence-add":
        return ""
    if not (row.get("part") and row.get("quote") and cmd.get("circle")):
        return "this offer carries no statement to attach"
    cmd.update(part=row["part"], quote=row["quote"], source=cmd["circle"])
    return ""


def _proposed_on_file(cmd: dict, graph: dict) -> dict | None:
    """The edge an issue-relationship-add names, when it sits on its source
    node as PROPOSED — R530 — else None. The same match issue_precheck()'s
    duplicate test makes: this node, this type, this target."""
    if cmd.get("verb") != "issue-relationship-add":
        return None
    node = graph.get(cmd.get("node", "")) or {}
    return next((e for e in node.get("edges", [])
                 if e.get("type") == cmd.get("type")
                 and e.get("target") == cmd.get("target")
                 and e.get("status") == "proposed"), None)


def _promote_command(cmd: dict, edge: dict) -> dict:
    """The approved add, recast as the one move R530 rules: that proposed
    edge to `attested`, through issue_commands' own writer. It carries the
    add's comment and line, so the basis and quote are the ones a fresh
    approved add writes; `why` keeps what the promotion replaces — who was
    asked, and on what basis — in the node's description_history."""
    ask = edge.get("ask")
    asked = (", ".join(ask) if isinstance(ask, list) else str(ask or "")) or "nobody named"
    since = f" on {edge['dated']}" if edge.get("dated") else ""
    was = " ".join(str(edge.get("basis", "")).split())
    return {"verb": "issue-relationship-update", "node": cmd["node"],
            "type": cmd["type"], "target": cmd["target"], "value": "attested",
            "comment": cmd.get("comment", ""), "line": cmd.get("line", ""),
            "circle": cmd["circle"],
            "why": (f"Promoted from proposed: Self approved the add (R530). It "
                    f"had been proposed{since}, asked of {asked}; its basis: {was}")}


def _propose_approve(row: dict) -> tuple[bool, str]:
    """RULED 2026-08-16 (R202), replacing `_relation_approve()` with a
    general version for the whole PROPOSE-class: a "text" row's
    approval is a PURE record — nothing to run, the same contract
    request always had. A "command" row's approval is the one that can
    fire code — `row["text"]` is RE-CLASSIFIED AND RE-PARSED fresh
    here, at approval time, never trusted from a stale staging-time
    snapshot: a proposal can sit pending across circles, and the graph
    an issue-relationship-add targets may have moved (an endpoint retired,
    settled, declined) in the meantime — exactly the reason
    `_relation_approve()` always re-derived against `issue_graph_now_read()`
    rather than a cached edge, generalized here to every command shape.
    A precheck/apply/dispatch failure — or the shape no longer
    classifying as a command at all — leaves the row pending with a
    clear reason; it is never silently dropped, and proposal_manager.proposal_approve()
    (the register's own state-flip) is only ever called after whatever
    the row actually needed to succeed already has.

    A "suggestion" row (R570, 2026-09-15) is the coordinator's own staging —
    a recognised line or a dependency plan's step — and runs through proposal_suggestion.py,
    which reports ok only when the verb's own writer did. It is never approved as a text row:
    that would record an act that did not happen, the defect this function's history names."""
    import proposal_manager as PR
    if row.get("kind") == "suggestion":
        import proposal_suggestion as PS
        ok, msg = PS.proposal_suggestion_execute(row)
        if not ok:
            return False, msg
        PR.proposal_approve(row["id"])
        return True, msg
    if row.get("kind") != "command":
        return PR.proposal_approve(row["id"])
    shape = _propose_command_shape(row.get("text", ""))
    if shape is None:
        return False, "not applied — no longer classifies as a command (stays pending)"
    if not shape.get("ok"):
        return False, f"not applied — {shape['why']} (stays pending)"
    if shape["shape"] in ("issue-relationship-add", "issue_command"):
        # ONE BRANCH FOR EVERY PARSED ISSUE RULING, 2026-08-20 (R267).
        # `issue_command` is the generic shape annotations gives an issue verb
        # that parses whole and is not the edge add — today
        # issue-label-update. Nothing below is edge-specific: it prechecks
        # and applies whatever issue_commands.issue_command_parse() produced, which is
        # the same code path a direct-typed ruling takes.
        #
        # Normalized (PR.circle_ref — the pre-R243 bare-row guard), not
        # verified: whether the ref names a real transcript is the GATE's
        # question (issue_gate checks the file before the quote), asked
        # when IC.issue_command_apply runs the batch. Checking it here too would couple
        # this deliberately tree-isolated loop to the live circles/
        # directory — the isolation test_proposal_manager' fixtures (placeholder
        # circle values, everything mocked) exist to keep.
        cmd = dict(shape["parsed"], circle=PR.circle_ref(row.get("circle", "")))
        if why := _offer_fill(cmd, row):
            return False, f"not applied — {why} (stays pending)"
        graph = issue_graph_now_read()
        # R530: a relation already on file as PROPOSED is the one the room
        # asked about, and approving the add confirms it. Decided HERE, not in
        # issue_precheck(): that precheck is shared with the typed cmd> path,
        # where Self typing the same add is an act the ruling did not address.
        on_file = _proposed_on_file(cmd, graph)
        if on_file is not None:
            cmd = _promote_command(cmd, on_file)
        why = IC.issue_precheck(cmd, graph)
        if why:
            return False, f"not applied — {why} (stays pending)"
        ok, msg = IC.issue_command_apply([cmd])
        if not ok:
            return False, f"not applied — {msg} (stays pending)"
        PR.proposal_approve(row["id"])
        if on_file is not None:
            msg = f"on file as proposed — promoted to attested; {msg}"
        return True, msg
    # AN `issue_status` BRANCH STOOD HERE UNTIL 2026-08-21. It ran
    # cmd_issue_property() and approved the row only when the command
    # actually executed (the 2026-08-19 fix: before that a cancelled
    # confirmation flipped the row to accepted). The operator removed
    # /issue-status-update from annotation visibility that day, so
    # _propose_command_shape() returns None for it and a legacy row with
    # that text now reads "no longer classifies as a command (stays
    # pending)" above — the honest outcome for a verb that may no longer
    # be proposed. The branch is gone rather than left unreachable.
    if shape["shape"] == "dev_cmd":
        if shape["head"] == "/issue-add":
            # APPROVAL FIRES THE DIALOG, PREFILLED — R323, 2026-08-23,
            # superseding R290's "approval opens it, asking nothing": the
            # checkpoint IS interactive (Self just typed the a)pprove), so
            # the bracket's strings arrive on the line and what it did not
            # carry — the absence clause a part never writes — is asked for
            # while the person is there, and the issue opens LIVE instead
            # of as an invisible lead. A dialog left entirely empty leaves
            # the row PENDING; a written issue approves it. /issue-add's
            # bool contract (R290) is unchanged underneath, via the
            # dialog's default writer.
            from commands import _issue_add_args
            import initialization as INIT
            label, desc, absence = _issue_add_args(shape["rest"])
            out = INIT.issue_add_dialog(seeds={"describe": desc,
                                               "label": label,
                                               "absence": absence})
            if out != "completed":
                return False, ("not applied — the issue dialog recorded "
                               "nothing (stays pending)")
            PR.proposal_approve(row["id"])
            return True, "/issue-add executed"
        if shape["head"] == "/part-add":
            # UNREACHABLE SINCE R483, 2026-09-07, AND
            # KEPT. /part-add left PROPOSE_SUBSET_COMMANDS on the operator's
            # word (*"part-add should also not be told to or available to
            # parts"*), so annotations._propose_command_shape() returns None
            # for the verb and no row of this shape can ever be staged again.
            # The ruling shut the door; it did not retire R323's dialog, and
            # deleting the branch would decide a question nobody asked. If the
            # door is ever reopened this is what is behind it — unchanged.
            #
            # THE SAME RULING'S OTHER HALF — a part proposing a part is the
            # room noticing someone not yet at the table; the bracket's two
            # strings ([proposed: /part-add "<describe>" "<Tag>"]) arrive
            # prefilled and PART_ADD_DIALOG completes the add (it joins from
            # the next circle). Empty at approval -> the row stays pending.
            from commands import _issue_add_args
            import initialization as INIT
            describe, tag, _extra = _issue_add_args(shape["rest"])
            seeds = {}
            if describe:
                seeds["describe"] = describe
            if tag:
                seeds["part_name"] = tag
            out = INIT.part_add_dialog(seeds=seeds or None)
            if out != "completed":
                return False, ("not applied — the part dialog recorded "
                               "nothing (stays pending)")
            PR.proposal_approve(row["id"])
            return True, "/part-add executed"
        # /practice-add, /better-option-add — the only other dev_cmd heads
        # PROPOSE_SUBSET_COMMANDS admits (annotations._propose_command_shape).
        # B62, 2026-08-23: this used to run dispatch_dev_cmd(shape["head"],
        # shape["rest"]) and read only whether the HEAD was recognised —
        # the same "did I recognise this head" channel the retired
        # issue_status branch above paid to get past. command_practice_add()/
        # command_better_option_add() now return their own (ok, msg) straight
        # from practice_manager.practice_add(), the same contract /issue-add got
        # at R290, so a register refusal (e.g. an empty add, no longer
        # caught at classification — see annotations.py) reports its own
        # reason and the row stays pending instead of resolving on a no-op.
        from commands import command_practice_add, command_better_option_add
        fn = (command_practice_add if shape["head"] == "/practice-add"
              else command_better_option_add)
        ok, msg = fn(shape["rest"])
        if not ok:
            return False, f"not applied — {msg} (stays pending)"
        PR.proposal_approve(row["id"])
        return True, msg
    return False, "not applied — unrecognized command shape (stays pending)"


def _propose_deny(row: dict) -> tuple[bool, str]:
    import proposal_manager as PR
    return PR.proposal_deny(row["id"])


def _superseded_by(row: dict, ruled: list[dict]) -> str:
    """The direct ruling (its typed line) that makes this pending propose row
    MOOT — or "". 2026-08-21 (F6, the operator: *"yes"*): a proposal whose
    command Self already ruled in the room by a direct command is shown as
    superseded and Enter drops it, instead of being asked again and, if
    approved, RE-RUN — which is how n0033 got three label entries for one
    ruling in circle 2026-08-21_1139. Same edge (either direction, the
    convergence normalisation) or the same label on the same issue; other
    commands have no direct-ruling twin to compare against."""
    if not ruled or row.get("kind") != "command":
        return ""
    shape = _propose_command_shape(row.get("text", ""))
    if not shape or not shape.get("ok") or "parsed" not in shape:
        return ""
    p = shape["parsed"]
    for c in ruled:
        if (p.get("verb") == c.get("verb") == "issue-relationship-add"
                and _normalize_edge((p["node"], p["type"], p["target"]))
                == _normalize_edge((c["node"], c["type"], c["target"]))):
            return c.get("line", "/issue-relationship-add …")
        if (p.get("verb") == c.get("verb") == "issue-label-update"
                and p.get("node") == c.get("node")
                and " ".join(p.get("label", "").split()).lower()
                == " ".join(c.get("label", "").split()).lower()):
            return c.get("line", "/issue-label-update …")
    return ""


def _propose_validate(row: dict) -> str:
    """Read-only mirror of _propose_approve()'s own classification —
    NEXT.md D14, 2026-08-17: report what a command-shaped proposal WOULD
    do, without calling approve()/apply()/dispatch — for SANDBOX
    reporting. `issue-relationship-add` is the one shape that reaches
    IC.issue_command_apply(), which writes issues/*.toml directly (never sandboxed,
    unlike remember.toml/short_term_*.toml — see issue_schema.ISSUES);
    running that for real from a sandbox circle would mutate the one
    real graph exactly the way COMMANDS' own sandbox path (`commands_
    <ot>.toml`, never auto-applied) is built not to."""
    if row.get("kind") == "suggestion":
        import proposal_suggestion as PS
        return PS.proposal_suggestion_validate(row)
    if row.get("kind") != "command":
        return "text proposal — a pure record, applies cleanly if approved"
    shape = _propose_command_shape(row.get("text", ""))
    if shape is None:
        return "would fail — no longer classifies as a command"
    if not shape.get("ok"):
        return f"would fail — {shape['why']}"
    if shape["shape"] in ("issue-relationship-add", "issue_command"):
        import proposal_manager as PR
        cmd = dict(shape["parsed"], circle=PR.circle_ref(row.get("circle", "")))
        if why := _offer_fill(cmd, row):
            return f"would fail — {why}"
        graph = issue_graph_now_read()
        on_file = _proposed_on_file(cmd, graph)
        if on_file is not None:
            cmd = _promote_command(cmd, on_file)
        why = IC.issue_precheck(cmd, graph)
        if why:
            return f"would fail — {why}"
        return ("would promote the relation on file as proposed to attested"
                if on_file is not None
                else f"would apply cleanly ({cmd['verb']})")
    return f"would apply cleanly ({shape['shape']})"


def _dependency_order(rows: list[dict]) -> list[dict]:
    """Pending proposal rows, each after every pending row it depends on, otherwise in the
    order given (R570). A hand-edited ring is left in the order found: the
    visiting set stops the walk, so nothing loops."""
    import proposal_manager as PR
    by_id = {r["id"]: r for r in rows}
    out: list[dict] = []
    done: set[str] = set()
    visiting: set[str] = set()

    def visit(r: dict) -> None:
        if r["id"] in done or r["id"] in visiting:
            return
        visiting.add(r["id"])
        for d in PR.proposal_dependency_ids_read(r):
            if d in by_id:
                visit(by_id[d])
        visiting.discard(r["id"])
        done.add(r["id"])
        out.append(r)

    for r in rows:
        visit(r)
    return out


def _mint_snapshot_read() -> set[str]:
    """Every issue id and practice id on file. Read before and after an approval, the one new
    id between them is what that approval minted. Module level, so a probe can swap it."""
    ids: set[str] = set()
    try:
        import issue_schema as S_
        ids |= {p.stem.split("_")[-1] for p in S_.issue_nodes_read()}
    except Exception:                                           # noqa: BLE001
        pass
    try:
        import practice_manager as PM
        ids |= {str(p["id"]) for p in PM.practice_read() if p.get("id")}
    except Exception:                                           # noqa: BLE001
        pass
    return ids


def _approved_dependents_fill(pid: str, before: set[str] | None) -> None:
    """After P-n is approved: record the one id it minted and fill every dependent's
    placeholder with it — the creation unblocks the dependent. More than one new id, or none,
    mints nothing: a dependent's token stays unfilled and it is not asked."""
    import proposal_manager as PR
    if before is None:
        return
    new = sorted(_mint_snapshot_read() - before)
    if len(new) != 1:
        if len(new) > 1 and any(pid in PR.proposal_dependency_placeholders_read(r)
                                for r in PR.proposal_dependents_read(pid)):
            seam.emit("command", f"        {pid} produced {len(new)} new ids — what waits on "
                                 f"it keeps its placeholder")
        return
    PR.proposal_minted_write(pid, new[0])
    for dep in PR.proposal_placeholder_substitute(pid, new[0]):
        seam.emit("command", f"        {dep} now reads {new[0]} where it waited on {pid}")


def proposal_vet(where: str, live: bool,
                          ruled: list[dict] | None = None) -> list[dict]:
    """a)pprove / d)eny / s)kip over EVERY currently pending propose-class
    proposal, across every register — practice/better_option and (RULED
    2026-08-16, R202) propose, which now subsumes request and relation
    both. Generalized 2026-08-12 from the practice-only
    vet_pending_practices() (docs/BNF.md PRACTICE LIFECYCLE,
    Vetting) into ONE loop reused per kind via a small table, the same
    "ONE TABLE" reasoning circle.py's own COMMANDS/KNOWN_CMDS already
    apply to dispatch — a second, hand-duplicated vetting loop per
    register is exactly the kind of drift that discipline exists to
    prevent. `where` names the checkpoint in the header line, for a
    reader scrolling back through the transcript log to tell them apart.

    `live` — NEXT.md D14, 2026-08-17: this used to run ONLY when
    `args.live`, so a sandbox circle never validated a pending proposal
    at all — asymmetric with COMMANDS, whose own IC.issue_precheck() already
    ran unconditionally in both modes (only IC.issue_command_apply() was live-gated).
    `live=False` still DESCRIBES every pending row and, for a
    command-shaped propose, VALIDATES it via `_propose_validate()` — but
    never approves, denies, or applies anything. Every row stays
    pending, no console prompt is read. Deliberately blanket rather than
    per-branch-safe: `_practice_approve()`/`PR.proposal_approve()`/`PR.proposal_deny()`
    are themselves safe to call in sandbox (self/best_practices.toml and
    self/proposals.toml were never sandboxed to begin with — see this
    function's own WRITTEN IMMEDIATELY note below), but `dispatch_dev_cmd()`
    reaches verbs (`/issue-apply`, `/issue <node> status`) that are not,
    and auditing its whole surface case-by-case is a bigger, separately-
    scoped change than this ruling asked for. A sandbox row this run
    reports "would apply cleanly" for is confirmed at the NEXT live
    checkpoint, same as any other still-pending row.

    Each kind supplies (name, pending(), describe(row), approve(row),
    deny(row)) — `pending()` read FRESH every call, never cached, so
    this sees rows staged earlier THIS call as well as anything skipped
    before, at BOTH checkpoints (`main()` calls this at /close and again
    at the next circle's priming). `describe()` returns (header, detail
    lines); `approve()` may itself prompt further (practice's revise
    case) and returns (ok, msg) same as `deny()`.

    Approve/deny/skip are Self's alone — a part may propose, never
    rule — which is why this reads from the console via `seam.read_line()`
    directly, an interactive prompt of its own, never from anything a
    part said.

    WRITTEN IMMEDIATELY: each approve/deny calls its own register's
    SS.register_write() as it happens, one row at a time. Neither
    self/best_practices.toml nor self/proposals.toml is ever in
    circle_commit()'s path list — nothing here commits either, at any
    checkpoint — so a ruling made here is a real, valid file on disk the
    moment it is made, sitting uncommitted until a human commits it,
    same as any direct /practice-add. A COMMAND-kind propose IS NOT AN
    EXCEPTION TO THIS, though its approve_fn may ALSO write issues/*.toml
    (via issue_commands.issue_command_apply(), for an issue-relationship-add shape) or run some
    other command's own effect — issues/ is not in circle_commit()'s path
    list either, the same as every other register here, and neither is a
    direct-typed `/issue-relationship-add`'s own edge write: a graph ruling
    has always sat uncommitted after /close, by the same design
    CLAUDE.md's own close-report description names (transcript,
    short_terms, close report — never issues/). See _propose_approve().

    CHECKPOINT 2 HAS A SECOND EFFECT beyond ruling on a proposal: it
    runs BEFORE circle_briefing_build() reads issues/ for the new circle's
    BLOCK 2 (main(), prewarm). Approving an issue-relationship-add propose there is
    the one ruling in this loop that can change what the room is about
    to be told — the new edge lands in that circle's own issue_relationship_brief.
    Approving the same proposal at the PRIOR circle's /close instead
    has no such effect: nothing rebuilds prompts mid-circle, so a graph
    write there is invisible to every part until whichever circle opens
    next."""
    # RETURNS THE APPROVALS IT MADE, this call only — [{kind, id, line}].
    # Added 2026-08-15 for SYNTHESIS's "any confirmed proposals" input
    # (R183): approve() drops the `circle` staging field on acceptance, so
    # in-process capture at the checkpoint is the ONLY clean record of
    # what was confirmed this run. Checkpoint-2 approvals (next priming)
    # reach no synthesis — recorded in docs/INTER_CIRCLE_DESIGN_V2.md.
    import practice_manager as PM
    import proposal_manager as PR
    import proposal_group_manager as CG

    approved: list[dict] = []

    # THE COALESCE, R356 (B69) — PRESENTATION ONLY. This function never
    # makes the model call: the hash-guarded refresh lives at circle.py's
    # two checkpoints, the only places a real circle vets. It CANNOT live
    # here — coordinator/tests/test_proposal_manager.py drives this loop live=True
    # against temp registers ("no mocks below circle.py"), and a refresh
    # here sent a REAL model call from a test suite and wrote
    # self/coalesce.toml into the main tree (E22, 2026-08-26, the day this
    # was built). Whatever fresh groups exist are presented, live or
    # sandbox; a stale or absent doc presents nothing. FAILS OPEN — vetting
    # is how circles open, and a suggestion layer must never block it.
    try:
        cg_groups, cg_refs = CG.proposal_group_live_read()
    except Exception as e:
        seam.emit("command", f"  coalesce: unreadable ({e}) — vetting "
                             f"ungrouped")
        cg_groups, cg_refs = [], set()

    if cg_groups:
        rows_by_ref: dict[str, dict] = {}
        for r in PM.practice_pending_list():
            rows_by_ref[f"practice:{r['id']}"] = r
        for r in PR.proposal_pending_list():
            rows_by_ref[f"propose:{r['id']}"] = r
        seam.emit("command", f"\n  {len(cg_groups)} coalesced group(s) — one "
                             f"ask in several wordings ({where}). Accepting "
                             f"enacts the PRIMARY member's own words and "
                             f"resolves the rest; the mapping is kept in "
                             f"self/coalesce.toml:")
    for g in cg_groups:
        primary_ref = g["primary"]
        others = [m for m in g["members"] if m != primary_ref]
        seam.emit("command", f"\n  [{g['id']}] {g['gloss']}")
        seam.emit("command", f"        {len(g['members'])} proposal(s) "
                             f"across: {', '.join(g['sources']) or '?'}")
        for m in g["members"]:
            row = rows_by_ref.get(m)
            text = (row.get("title") or row.get("text", "")) if row \
                else "(no longer pending)"
            star = " <- PRIMARY" if m == primary_ref else ""
            seam.emit("command", f"        {m}{star}: {text[:90]}")
        if not live:
            seam.emit("command", "        SANDBOX — not ruled here, stays "
                                 "grouped")
            continue
        primary_row = rows_by_ref.get(primary_ref)
        if primary_row is None:
            seam.emit("command", "        the primary is no longer pending — "
                                 "group left as it is")
            continue
        gprompt = (f"  [{g['id']}] a)ccept primary, d)eny all, s)plit into "
                   f"single asks, or Enter to keep pending ? ")
        while True:
            try:
                ans = PC.stream_timed_read(seam.read_line, gprompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                seam.emit("command", "\n  (stopping here — the rest stay "
                          "pending, same as a skip)")
                return approved
            if ans in ("a", "accept", "approve"):
                kind = primary_ref.split(":", 1)[0]
                minted_before = _mint_snapshot_read() if kind == "propose" else None
                if kind == "practice":
                    ok, msg = _practice_approve(primary_row, PM)
                else:
                    ok, msg = _propose_approve(primary_row)
                seam.emit("command", f"        {msg}")
                if not ok:
                    seam.emit("command", "        primary did not land — the "
                                         "group stays as it is")
                    break
                approved.append({"kind": kind, "id": primary_row["id"],
                                 "line": f"[{g['id']}] {g['gloss']}"})
                if kind == "propose":
                    _approved_dependents_fill(primary_row["id"], minted_before)
                resolved = []
                for m in others:
                    row = rows_by_ref.get(m)
                    if row is None:
                        continue
                    mk = m.split(":", 1)[0]
                    ok2, msg2 = (PM.practice_deny(row["id"]) if mk == "practice"
                                 else _propose_deny(row))
                    seam.emit("command", f"        {m}: {msg2}")
                    if ok2:
                        resolved.append(m)
                    if ok2 and mk == "propose":
                        # A DUPLICATE, NOT A REFUSAL (R570): what waited on
                        # this member now waits on the accepted primary — or, when the primary
                        # is a practice row, simply stops waiting. Never a cascade.
                        new = primary_row["id"] if kind == "propose" else None
                        for moved in PR.proposal_dependency_repoint(row["id"], new):
                            seam.emit("command", f"        {moved} now waits on "
                                                 f"{new or 'nothing'} instead of {row['id']}")
                CG.proposal_group_mark(g["id"], f"accepted {primary_ref} {_today()}"
                                 + (f"; denied: {', '.join(resolved)}"
                                    if resolved else ""))
                cg_refs -= {primary_ref, *others}
                break
            if ans in ("d", "deny"):
                for m in g["members"]:
                    row = rows_by_ref.get(m)
                    if row is None:
                        continue
                    mk = m.split(":", 1)[0]
                    _ok, msg2 = (PM.practice_deny(row["id"]) if mk == "practice"
                                 else _propose_deny(row))
                    seam.emit("command", f"        {m}: {msg2}")
                CG.proposal_group_mark(g["id"], f"denied {_today()}")
                cg_refs -= set(g["members"])
                break
            if ans in ("s", "split"):
                CG.proposal_group_mark(g["id"], f"split {_today()}")
                cg_refs -= set(g["members"])
                seam.emit("command", "        split — each member is asked on "
                                     "its own below")
                break
            if ans in ("", "k", "keep", "skip"):
                seam.emit("command", "        kept — the group stands, its "
                                     "members stay pending")
                break
            seam.emit("command", "        " + gprompt.strip())

    kinds = (
        ("practice", PM.practice_pending_list,
         lambda row: _practice_describe(row, PM),
         lambda row: _practice_approve(row, PM),
         lambda row: PM.practice_deny(row["id"])),
        ("propose", PR.proposal_pending_list, _propose_describe, _propose_approve,
         _propose_deny),
    )

    for kind_name, pending_fn, describe_fn, approve_fn, deny_fn in kinds:
        # a member of a live coalesced group was presented above, as the
        # group — it is not asked again on its own unless the group split
        pend = [r for r in pending_fn()
                if f"{kind_name}:{r['id']}" not in cg_refs]
        if kind_name == "propose":
            # DEPENDENCY ORDER — R570, 2026-09-15: a row is asked only after
            # every pending row it depends on, so the prior's ruling is known when it is.
            pend = _dependency_order(pend)
        if not pend:
            continue
        seam.emit("command", f"\n  {len(pend)} {kind_name} proposal(s) awaiting "
              f"a ruling ({where}):")
        for row in pend:
            if kind_name == "propose" and row.get("depends_on"):
                # THE ROW AS IT STANDS NOW: an earlier ruling in this same pass may have filled
                # its placeholder or denied it by cascade.
                row = PR.proposal_dependency_resolve(row)
                if row.get("state") != "proposed":
                    continue
                dstate, dwhy = PR.proposal_dependency_state_read(row)
                if dstate != "ready":
                    header, _detail = describe_fn(row)
                    seam.emit("command", f"\n  {header}")
                    if dstate == "cascade" and live:
                        for gone in PR.proposal_cascade_deny(dwhy):
                            seam.emit("command", f"        {gone} denied — cascade: it "
                                                 f"depended on {dwhy}, which was not accepted")
                    elif dstate == "cascade":
                        seam.emit("command", f"        SANDBOX — would be denied: it depends "
                                             f"on {dwhy}, which was not accepted")
                    else:
                        seam.emit("command", f"        not asked — {dwhy}; stays pending")
                    continue
            header, detail = describe_fn(row)
            seam.emit("command", f"\n  {header}")
            for line in detail:
                seam.emit("command", f"        {line}")
            pid = row["id"]
            if not live:
                note = (f" — {_propose_validate(row)}" if kind_name == "propose"
                        else "")
                seam.emit("command", f"        SANDBOX — not ruled here"
                          f"{note}, stays pending")
                continue
            # SUPERSEDED — ALREADY RULED IN THE ROOM, 2026-08-21 (F6). `ruled`
            # is the circle's own issue_cmds at the /close checkpoint (the
            # next-open checkpoint passes none). Enter DROPS such a row
            # (proposals.supersede — a tombstone naming the circle); 'k'
            # keeps it pending; a)pprove and d)eny still mean what they say.
            sup = (_superseded_by(row, ruled or []) if kind_name == "propose"
                   else "")
            if sup:
                seam.emit("command", f"        superseded — already ruled in "
                                     f"the room: {sup}")
                prompt = (f"  [{pid}] a)pprove, d)eny, k)eep pending, or Enter "
                          f"to drop (superseded) ? ")
            else:
                prompt = f"  [{pid}] a)pprove, d)eny, s)kip ? "
            while True:
                try:
                    ans = PC.stream_timed_read(seam.read_line, prompt).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    seam.emit("command", "\n  (stopping here — the rest stay "
                          "pending, same as a skip)")
                    return approved
                if sup and ans in ("", "s", "skip", "drop"):
                    import proposal_manager as PR
                    by = next((c.get("circle", "") for c in (ruled or [])
                               if c.get("circle")), "this circle")
                    ok, msg = PR.proposal_supersede(pid, by)
                    seam.emit("command", f"        {msg}")
                    break
                if sup and ans in ("k", "keep"):
                    seam.emit("command", "        kept — stays pending")
                    break
                if ans in ("a", "approve"):
                    minted_before = _mint_snapshot_read() if kind_name == "propose" else None
                    ok, msg = approve_fn(row)
                    seam.emit("command", f"        {msg}")
                    if ok:
                        approved.append({"kind": kind_name, "id": pid,
                                         "line": header})
                        if kind_name == "propose":
                            # THE CREATION UNBLOCKS THE DEPENDENT: the id this approval
                            # minted fills every dependent's placeholder, now.
                            _approved_dependents_fill(pid, minted_before)
                    break
                if ans in ("d", "deny"):
                    ok, msg = deny_fn(row)
                    seam.emit("command", f"        {msg}")
                    if ok and kind_name == "propose":
                        for gone in PR.proposal_cascade_deny(pid):
                            seam.emit("command", f"        {gone} denied — cascade: it "
                                                 f"depended on {pid}")
                    break
                if ans in ("s", "skip", ""):
                    seam.emit("command", "        skipped — stays pending")
                    if kind_name == "propose" and PR.proposal_dependents_read(pid):
                        seam.emit("command", f"        (what depends on {pid} waits with it)")
                    break
                seam.emit("command", "        " + prompt.strip()
                          + ("" if sup else " (or Enter to skip)"))
    return approved
