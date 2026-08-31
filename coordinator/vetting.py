#!/usr/bin/env python3
"""
vetting.py — Self's ruling loop over every pending propose-class
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

graph_now() moves WITH the vetting loop — Self's explicit ruling on
the phase-2 plan's open decision — because _propose_approve is its one
consumer: a command-shaped proposal is re-classified and re-parsed
fresh at approval time against the live graph, never trusted from a
staging-time snapshot. test_proposals patches vetting.graph_now (and
IC.precheck/IC.apply on their own module) to isolate this loop from
the real tree — module-attribute patching against the OWNER, the same
late-binding contract seam.py documents.
"""

from __future__ import annotations

import issue_commands as IC
import issue_schema as S_
import phase_clock as PC     # timed_read — a ruling prompt is human time
import seam
from markers import _propose_command_shape, _wrap58, _normalize_edge


def _today() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def graph_now() -> dict:
    """The live issue graph, freshly loaded. Module-level (promoted out of
    main()'s own local closure 2026-08-13, #32) because _propose_approve()
    below needs it too, from a context with no access to main()'s locals —
    it is a pure function of issue_schema, nothing closed over."""
    return {d["id"]: d for d in (S_.load(q) for q in S_.nodes())}

def _practice_describe(row: dict, BPX) -> tuple[str, list[str]]:
    pid, op = row["id"], row.get("op", "?")
    sources = ", ".join(row.get("sources", [])) or "unknown source"
    header = f"[{pid}] {op} — {sources} · {row.get('circle', '?')}"
    target = BPX.by_id(row.get("target_id", "")) if op != "add" else None
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


def _practice_approve(row: dict, BPX) -> tuple[bool, str]:
    """The one propose-class kind whose approval can itself prompt
    further — a non-unanimous revise has no single candidate text, so
    Self authors the final wording here rather than accepting a blank."""
    title = row.get("title", "")
    if row.get("op") == "revise" and not title:
        try:
            title = PC.timed_read(seam.read_line, "        revision text "
                                  "(candidates above)> ").strip()
        except (EOFError, KeyboardInterrupt):
            title = ""
        if not title:
            return False, "no text given — leaving this one pending"
    return BPX.approve(row["id"], title=title)


# The circle_/sandbox_ normalization that used to sit here
# (_gate_circle_ref) is the register's own since R243, 2026-08-19 —
# proposals.circle_ref, applied by stage() itself, so new rows carry the
# prefixed transcript ref already. Approval below still runs it as the
# healing guard: rows staged before R243 carried the bare open time, and
# without the prefix the gate's attested-edge basis regex (R061) refused
# every issue-relationship-add approval, leaving the row pending forever.


def _propose_describe(row: dict) -> tuple[str, list[str]]:
    sources = ", ".join(row.get("sources", [])) or "unknown source"
    header = (f"[{row['id']}] propose ({row.get('kind', '?')}) — "
             f"{sources} · {row.get('circle', '?')}")
    return header, _wrap58(row.get("text", "")[:300])


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
    `_relation_approve()` always re-derived against `graph_now()`
    rather than a cached edge, generalized here to every command shape.
    A precheck/apply/dispatch failure — or the shape no longer
    classifying as a command at all — leaves the row pending with a
    clear reason; it is never silently dropped, and proposals.approve()
    (the register's own state-flip) is only ever called after whatever
    the row actually needed to succeed already has."""
    import proposals as PR
    if row.get("kind") != "command":
        return PR.approve(row["id"])
    shape = _propose_command_shape(row.get("text", ""))
    if shape is None:
        return False, "not applied — no longer classifies as a command (stays pending)"
    if not shape.get("ok"):
        return False, f"not applied — {shape['why']} (stays pending)"
    if shape["shape"] in ("issue-relationship-add", "issue_command"):
        # ONE BRANCH FOR EVERY PARSED ISSUE RULING, 2026-08-20 (R267).
        # `issue_command` is the generic shape markers gives an issue verb
        # that parses whole and is not the edge add — today
        # issue-label-update. Nothing below is edge-specific: it prechecks
        # and applies whatever issue_commands.parse() produced, which is
        # the same code path a direct-typed ruling takes.
        #
        # Normalized (PR.circle_ref — the pre-R243 bare-row guard), not
        # verified: whether the ref names a real transcript is the GATE's
        # question (issue_gate checks the file before the quote), asked
        # when IC.apply runs the batch. Checking it here too would couple
        # this deliberately tree-isolated loop to the live circles/
        # directory — the isolation test_proposals' fixtures (placeholder
        # circle values, everything mocked) exist to keep.
        cmd = dict(shape["parsed"], circle=PR.circle_ref(row.get("circle", "")))
        why = IC.precheck(cmd, graph_now())
        if why:
            return False, f"not applied — {why} (stays pending)"
        ok, msg = IC.apply([cmd])
        if not ok:
            return False, f"not applied — {msg} (stays pending)"
        PR.approve(row["id"])
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
            PR.approve(row["id"])
            return True, "/issue-add executed"
        if shape["head"] == "/part-add":
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
            PR.approve(row["id"])
            return True, "/part-add executed"
        # /practice-add, /better-option-add — the only other dev_cmd heads
        # PROPOSE_SUBSET_COMMANDS admits (markers._propose_command_shape).
        # B62, 2026-08-23: this used to run dispatch_dev_cmd(shape["head"],
        # shape["rest"]) and read only whether the HEAD was recognised —
        # the same "did I recognise this head" channel the retired
        # issue_status branch above paid to get past. cmd_practice_add()/
        # cmd_better_option_add() now return their own (ok, msg) straight
        # from check_best_practices.add(), the same contract /issue-add got
        # at R290, so a register refusal (e.g. an empty add, no longer
        # caught at classification — see markers.py) reports its own
        # reason and the row stays pending instead of resolving on a no-op.
        from commands import cmd_practice_add, cmd_better_option_add
        fn = (cmd_practice_add if shape["head"] == "/practice-add"
              else cmd_better_option_add)
        ok, msg = fn(shape["rest"])
        if not ok:
            return False, f"not applied — {msg} (stays pending)"
        PR.approve(row["id"])
        return True, msg
    return False, "not applied — unrecognized command shape (stays pending)"


def _propose_deny(row: dict) -> tuple[bool, str]:
    import proposals as PR
    return PR.deny(row["id"])


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
    IC.apply(), which writes issues/*.toml directly (never sandboxed,
    unlike remember.toml/short_term_*.md — see issue_schema.ISSUES);
    running that for real from a sandbox circle would mutate the one
    real graph exactly the way COMMANDS' own sandbox path (`commands_
    <ot>.toml`, never auto-applied) is built not to."""
    if row.get("kind") != "command":
        return "text proposal — a pure record, applies cleanly if approved"
    shape = _propose_command_shape(row.get("text", ""))
    if shape is None:
        return "would fail — no longer classifies as a command"
    if not shape.get("ok"):
        return f"would fail — {shape['why']}"
    if shape["shape"] in ("issue-relationship-add", "issue_command"):
        import proposals as PR
        cmd = dict(shape["parsed"], circle=PR.circle_ref(row.get("circle", "")))
        why = IC.precheck(cmd, graph_now())
        return (f"would fail — {why}" if why
                else f"would apply cleanly ({cmd['verb']})")
    return f"would apply cleanly ({shape['shape']})"


def vet_pending_proposals(where: str, live: bool,
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
    at all — asymmetric with COMMANDS, whose own IC.precheck() already
    ran unconditionally in both modes (only IC.apply() was live-gated).
    `live=False` still DESCRIBES every pending row and, for a
    command-shaped propose, VALIDATES it via `_propose_validate()` — but
    never approves, denies, or applies anything. Every row stays
    pending, no console prompt is read. Deliberately blanket rather than
    per-branch-safe: `_practice_approve()`/`PR.approve()`/`PR.deny()`
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
    SS.save() as it happens, one row at a time. Neither
    self/best_practices.toml nor self/proposals.toml is ever in
    commit_circle()'s path list — nothing here commits either, at any
    checkpoint — so a ruling made here is a real, valid file on disk the
    moment it is made, sitting uncommitted until a human commits it,
    same as any direct /practice-add. A COMMAND-kind propose IS NOT AN
    EXCEPTION TO THIS, though its approve_fn may ALSO write issues/*.toml
    (via issue_commands.apply(), for an issue-relationship-add shape) or run some
    other command's own effect — issues/ is not in commit_circle()'s path
    list either, the same as every other register here, and neither is a
    direct-typed `/issue-relationship-add`'s own edge write: a graph ruling
    has always sat uncommitted after /close, by the same design
    CLAUDE.md's own close-report description names (transcript,
    short_terms, close report — never issues/). See _propose_approve().

    CHECKPOINT 2 HAS A SECOND EFFECT beyond ruling on a proposal: it
    runs BEFORE build_briefing() reads issues/ for the new circle's
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
    # reach no synthesis — recorded in docs/INTER_CIRCLE_DESIGN.md.
    import check_best_practices as BPX
    import proposals as PR
    import coalesce as CG

    approved: list[dict] = []

    # THE COALESCE, R356 (B69) — PRESENTATION ONLY. This function never
    # makes the model call: the hash-guarded refresh lives at circle.py's
    # two checkpoints, the only places a real circle vets. It CANNOT live
    # here — coordinator/tests/test_proposals.py drives this loop live=True
    # against temp registers ("no mocks below circle.py"), and a refresh
    # here sent a REAL model call from a test suite and wrote
    # self/coalesce.toml into the main tree (E22, 2026-08-26, the day this
    # was built). Whatever fresh groups exist are presented, live or
    # sandbox; a stale or absent doc presents nothing. FAILS OPEN — vetting
    # is how circles open, and a suggestion layer must never block it.
    try:
        cg_groups, cg_refs = CG.live_groups()
    except Exception as e:
        seam.emit("command", f"  coalesce: unreadable ({e}) — vetting "
                             f"ungrouped")
        cg_groups, cg_refs = [], set()

    if cg_groups:
        rows_by_ref: dict[str, dict] = {}
        for r in BPX.pending():
            rows_by_ref[f"practice:{r['id']}"] = r
        for r in PR.pending():
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
                ans = PC.timed_read(seam.read_line, gprompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                seam.emit("command", "\n  (stopping here — the rest stay "
                          "pending, same as a skip)")
                return approved
            if ans in ("a", "accept", "approve"):
                kind = primary_ref.split(":", 1)[0]
                if kind == "practice":
                    ok, msg = _practice_approve(primary_row, BPX)
                else:
                    ok, msg = _propose_approve(primary_row)
                seam.emit("command", f"        {msg}")
                if not ok:
                    seam.emit("command", "        primary did not land — the "
                                         "group stays as it is")
                    break
                approved.append({"kind": kind, "id": primary_row["id"],
                                 "line": f"[{g['id']}] {g['gloss']}"})
                resolved = []
                for m in others:
                    row = rows_by_ref.get(m)
                    if row is None:
                        continue
                    mk = m.split(":", 1)[0]
                    ok2, msg2 = (BPX.deny(row["id"]) if mk == "practice"
                                 else _propose_deny(row))
                    seam.emit("command", f"        {m}: {msg2}")
                    if ok2:
                        resolved.append(m)
                CG.mark(g["id"], f"accepted {primary_ref} {_today()}"
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
                    _ok, msg2 = (BPX.deny(row["id"]) if mk == "practice"
                                 else _propose_deny(row))
                    seam.emit("command", f"        {m}: {msg2}")
                CG.mark(g["id"], f"denied {_today()}")
                cg_refs -= set(g["members"])
                break
            if ans in ("s", "split"):
                CG.mark(g["id"], f"split {_today()}")
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
        ("practice", BPX.pending,
         lambda row: _practice_describe(row, BPX),
         lambda row: _practice_approve(row, BPX),
         lambda row: BPX.deny(row["id"])),
        ("propose", PR.pending, _propose_describe, _propose_approve,
         _propose_deny),
    )

    for kind_name, pending_fn, describe_fn, approve_fn, deny_fn in kinds:
        # a member of a live coalesced group was presented above, as the
        # group — it is not asked again on its own unless the group split
        pend = [r for r in pending_fn()
                if f"{kind_name}:{r['id']}" not in cg_refs]
        if not pend:
            continue
        seam.emit("command", f"\n  {len(pend)} {kind_name} proposal(s) awaiting "
              f"a ruling ({where}):")
        for row in pend:
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
                    ans = PC.timed_read(seam.read_line, prompt).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    seam.emit("command", "\n  (stopping here — the rest stay "
                          "pending, same as a skip)")
                    return approved
                if sup and ans in ("", "s", "skip", "drop"):
                    import proposals as PR
                    by = next((c.get("circle", "") for c in (ruled or [])
                               if c.get("circle")), "this circle")
                    ok, msg = PR.supersede(pid, by)
                    seam.emit("command", f"        {msg}")
                    break
                if sup and ans in ("k", "keep"):
                    seam.emit("command", "        kept — stays pending")
                    break
                if ans in ("a", "approve"):
                    ok, msg = approve_fn(row)
                    seam.emit("command", f"        {msg}")
                    if ok:
                        approved.append({"kind": kind_name, "id": pid,
                                         "line": header})
                    break
                if ans in ("d", "deny"):
                    ok, msg = deny_fn(row)
                    seam.emit("command", f"        {msg}")
                    break
                if ans in ("s", "skip", ""):
                    seam.emit("command", "        skipped — stays pending")
                    break
                seam.emit("command", "        " + prompt.strip()
                          + ("" if sup else " (or Enter to skip)"))
    return approved
