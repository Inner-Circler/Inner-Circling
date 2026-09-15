#!/usr/bin/env python3
"""
commands.py — the command-pane verbs' implementations and their one
dispatcher: the statements numbering (/issue-evidence-list and what
`/issue-evidence-add` resolves against), the ic.py-era dev commands
(topic/practice/prompt-show/issue-apply/issue-status), _run_captured
(in issue_commands.py since 2026-09-03, with /issue-add's body),
dispatch_dev_cmd, and cmd_issue_object. Phase 2 stage 6 of the
coordinator partitioning (2026-08-16; built fifth — vetting imports
this dispatcher, so commands precede it, the dependency the phase-2
plan recorded). Until then all of it lived in circle.py. Verbatim
move — bodies and comments unchanged, except console I/O goes through
seam.emit/seam.read_line by attribute access (the confirm prompt in
cmd_issue_status_set included, which is what keeps it scriptable by
the test harness and circling alike).

Reads ISSUE_NODE_RE from command_surface and cmd_help/HELP_WIDTH from
help_system — the verb table itself stays in command_surface, stage
0's cycle-breaker, so the dispatcher and the /help renderer that
documents it share one source without importing each other. The
subprocess argv literals ("memory/issue_status.py",
"memory/issue_commands.py") are unchanged: those files did not
follow-on relocation, 2026-08-16.
"""

from __future__ import annotations

import re

import issue_schema as S_
import issue_commands as IC        # /issue-add's body and _run_captured (2026-09-03)
import seam
import phase_clock as PC   # stream_timed_read — a prompt is human time, and the
                           # heartbeat must not spin at someone typing
import transcript_store as TS      # withheld(): recorded, never in the room
import initialization as INIT   # the dialogs the /part-* verbs open (imports roster, seam)
import part_roster as R
from command_surface import ISSUE_NODE_RE
from help_system import command_help, HELP_WIDTH


# -------------------------------------------------------------- statements
# MARK (Self's ratification of a statement) was RETIRED WHOLESALE 2026-08-14,
# code included — see docs/BNF.md. statement_read()/statement_resolve() below
# survive: they are the generic 1-based statement numbering `/issue
# issue-evidence-add` resolves against, not mark-specific.

def statement_read(transcript: list[dict]) -> list[tuple[int, dict]]:
    """Indexed speakable turns — Coordinator notes are not addressable.

    NOR IS A REMEMBER-ONLY TURN, as of 2026-08-18. `/issue-evidence-add <n>`
    addresses into this list, and a remember is private to whoever wrote it;
    a private note attachable as evidence would leak it into the graph, which
    is the whole thing REMEMBER's blast-radius rule forbids. It reaches the
    transcript FILE and stops there.

    An echoed /issue command is excluded by the same test and is a smaller
    point: it is Self's own already-recorded ruling, so citing one as evidence
    for a node quotes the coordinator rather than the room. That it was
    addressable at all is pre-existing, not something this change introduced."""
    return [(i, e) for i, e in enumerate(transcript)
            if e["speaker"] != "__coordinator__" and not TS.circle_transcript_is_withheld(e)]


def statement_resolve(transcript: list[dict], n: int) -> tuple[dict | None, str]:
    """The SAME 1-based numbering `/issue-evidence-list` prints, resolved to the
    actual transcript entry. `/issue-evidence-add` is the caller — `n` is
    not a stored id, it is a position in the list AS IT WOULD PRINT RIGHT
    NOW, the discipline every `-list <n>` keeps (LIST_RECORD)."""
    stmts = statement_read(transcript)
    if n < 1 or n > len(stmts):
        return None, f"no statement #{n} — /issue-evidence-list shows 1-{len(stmts)}"
    _, e = stmts[n - 1]
    return e, ""


def statement_show(transcript: list[dict], rest: str = "") -> None:
    """`/issue-evidence-list [<n>]`. Bare: the numbered listing `/issue-evidence-add nNNNN
    <stmt#>` addresses into — kept mark-free after MARK's 2026-08-14 retirement (docs/BNF.md);
    issue-evidence-add has no other way to discover a statement's number. `<n>`: that
    statement whole (B133).

    2026-08-16: `e['text']` can carry embedded newlines (a dry-run part's
    canned multi-section statement, e.g.) — whitespace collapsed before
    truncating so this is genuinely ONE line per entry, never several;
    truncation length matched to the fixed prefix so the whole line stays
    within the 80 column max (RULED 2026-08-16). The footer is one line too."""
    import REGISTER_CLASS as SS
    a = rest.strip()
    if a:
        seam.emit("command", statement_record_show(transcript, int(a)) if a.isdecimal()
                  else "  usage: /issue-evidence-list [<n>]  — bare lists them, "
                       "<n> shows one whole")
        return
    stmts = statement_read(transcript)
    prefix_width = len(f"  {'':3}. {'':<12} ")
    budget = HELP_WIDTH - prefix_width
    for n, (i, e) in enumerate(stmts, 1):
        flat = " ".join(e["text"].split())
        seam.emit("command", f"  {n:3}. {e['display']:<12} {flat[:budget]}")
    if stmts:
        seam.emit("command", SS.register_list_footer(len(stmts), "/issue-evidence-list"))


def statement_record_show(transcript: list[dict], n: int) -> str:
    """`/issue-evidence-list <n>`: one statement whole, as the ROOM heard it — who spoke, to
    whom, and every line of what was said (B133).

    WHAT THE ROOM HEARD, NOT EVERY KEY OF THE ENTRY — the one `-list <n>` that does not walk its
    row whole, deliberately. A parsed statement can carry `raw`, its bytes as the file holds
    them, [remember: ...] bracket included, and a remember is private to whoever wrote it
    (docs/BNF.md, REMEMBER's blast radius). `text` is what `/issue-evidence-add` attaches."""
    import REGISTER_CLASS as SS
    rows = [{"speaker": e["display"], "to": e.get("to", ""), "text": e["text"]}
            for _, e in statement_read(transcript)]
    return SS.register_record_show(rows, n, ("speaker", "to"), body="text",
                                   verb="/issue-evidence-list")


# THE ANNOTATION GRAMMAR LIVES IN annotations.py, AND THIS IS ITS HISTORY. The
# block below was written 2026-08-04 and left here when phase 2 moved the
# grammar out from under it; it ends mid-sentence. Every bracket it spells —
# `[propose nNNNN leads-to nMMMM]`, `[request ...]`, `[hold]`, the six
# `[proposed practice ...]` forms — is DIALOG TEXT since R273 (2026-08-20).
# The two annotations that exist are `[remember: <text>]` and
# `[proposed: <command>]`; docs/BNF.md's ANNOTATION production is the record
# and annotations.ASK_KEYWORDS is the code. Kept for WHY annotations exist at all —
# the measurement in the third paragraph — which is still true.
#
# What a part may ASK FOR, in a form that cannot be misread. Ruled 2026-08-04.
#
# Three annotations, one mechanism: the part signals, the coordinator collects, and
# THE OPERATOR RULES. R048 and "no part statement creates or retires an issue" are both
# untouched — an annotation changes who SEES the ask, never who acts on it.
#
#   [propose nNNNN leads-to nMMMM]  a relation, named structurally   (then)
#   [request ...]                   anything else, in the part's own words   (then)
#
# WHY ANNOTATIONS RATHER THAN INFERENCE. Measured on circle_2026-08-04_1243: a
# syntactic scan for the arrow notation would have caught 2 of the 6 actions
# that circle actually produced, and 0 of 60 statements in the two circles
# before it carried an arrow at all. The rename, the retraction, the better
# option and a part's question were all prose. Inference would have to READ
# for intent, which is a machine producing claims about a room — the shape that
# made 8 of 11 nodes still say NOT YET RULED.
#
# An annotation asks the part to say what it means. That is cheaper, exact, and it
# is the same lesson as `this same descent` being ambiguous: when a thing must
# be acted on, prose is the wrong carrier.
#
# FAILS OPEN. A missed annotation costs nothing — Self has the transcript.
#
# THE SIX PRACTICE LIFECYCLE ANNOTATIONS (docs/BNF.md; retired B60, a practice
# is `[proposed: /practice-add ...]` now), added as a
# fourth alternative rather than a second regex — one recognizer, so a
# statement mixing an old-style [hold] and a [proposed practice: ...] was
# still walked in one pass. Order matters: the two-word forms
# ("...revise"/"...delete") must precede their plain "add" prefix, because
# Python's alternation is first-match-not-longest-match — with the plain
# form first, "proposed practice revise: ..." would match "proposed
# practice" and leave " revise: ..." dangling in the argument. VERIFIED
# empirically (test_practice_annotations.py) that `propose\b` still does
# not match `proposed` — the two families do not collide.
#
# REMEMBER, added 2026-08-12, same recognizer (one regex, not a second).
# UNLIKE the other seven kinds, a recognized remember is never left in the
# transcript: remember_apply() strips it at the point every statement is
# appended, before annotation_route() (or anything else) ever sees the text —


# --------------------------------------------------------------------------
# STAGE 2, RULED 2026-08-13: ic.py is a development tool being retired —
# its functions move here, behind the dev=true gate, "able to operate
# independently of any circle in progress." Two halves:
#
#   1. The 7 verbs ic.py duplicated (practice-*, concern-*, prompt-show)
#      already had a circle.py implementation, inline in main()'s loop
#      below. Per the precedence ruling ("where circle.py equivalents
#      exist, circle.py functions take precedence"), THOSE win — ic.py's
#      copies are discarded outright, not merged. Extracted here into
#      standalone functions so a future no-circle caller (the command
#      pane with nothing running) can call the exact same code the Self>
#      loop calls, not a second implementation. The only two with a
#      transcript side effect (/practice-add, /practice-delete — the
#      delete case was a corrected assumption: it falls through to the
#      same recording tail on success, not just add) take an optional
#      `record` callback; the loop passes one, a no-circle caller passes
#      none, since there is no transcript to record into.
#   2. issue-apply and `issue nNNNN status` have NO circle.py equivalent
#      — /issue-label-update and /issue-relationship-add attest against a
#      transcript quote (R079), these two don't, so they were ic.py-only.
#      Ported here near-verbatim from ic.py's own _issue_apply/
#      _issue_status_show/_issue_status_set/_dispatch_issue_object, with
#      one real adaptation: routed through seam.emit()/seam.read_line() instead of
#      print()/input(), so they behave correctly under circling's
#      redirected I/O and not only a real terminal — subprocess output is
#      captured and re-emitted rather than left to inherit the real
#      console, which would print nowhere useful under redirection.
# --------------------------------------------------------------------------


def command_prompt_show(who: str) -> None:
    import prompt_show as PS
    seam.emit("command", PS.prompt_show_render(who))


def command_remember_list(rest: str) -> None:
    """/remember-list — the Self half of docs/BNF.md's REMEMBER_PROJECTION,
    built 2026-08-18 (R224) as /recall, designed 2026-08-14. RENAMED
    2026-08-21 when the operator named the register's verbs (/remember writes,
    /remember-list reads; "\"recall\" is a synonym"); the synonym was RETIRED
    2026-09-11 (R557) — "recall" is a part's own search
    of its record, the [recall: ...] annotation, and nothing else.

    READ-ONLY, AND SELF'S OWN REGISTER ONLY. `remember_manager.SELF` is passed
    explicitly and no argument can change it: a part's remember is private
    to that part, so the one thing this command must never grow is a
    `<part>` form. The argument is a record number and nothing else.

    NO CIRCLE NEEDED — it reads self/remember.toml off disk, which is why
    it sits in command_dev_dispatch() with the rest of the always-available
    verbs rather than in the Self> loop."""
    import remember_manager as RM
    import remember_list_projection as RLP
    a = rest.strip()
    if not a:
        seam.emit("command", RLP.remember_list(RM.SELF))
        return
    if not a.isdigit():
        seam.emit("command", "  usage: /remember-list [<n>] — bare lists them")
        return
    seam.emit("command", RLP.remember_record_show(int(a), RM.SELF))


# `cmd_recall = command_remember_list` — the name the verb carried from R224 to
# 2026-08-21, kept callable for the probes — was here until 2026-09-11
# (R557). Nothing spells it now.


class _NoCircleGuard:
    """The write guard a no-circle /remember uses: Self's own register, the
    real tree, and no open time — which is what makes the one-per-circle
    rule not apply (there is no circle to be one of). Duck-typed to what
    remember_manager.remember_locate()/remember_has_written() read: `.live`, `.ot`, `.check()`.
    WriteGuard itself admits self/remember.toml by exact path, so this
    delegates the check to it rather than re-stating the allow-list."""
    live = True
    ot = ""

    def check(self, p):
        from write_guard import WriteGuard
        return WriteGuard(live=True, open_time="").check(p)


def command_remember(text: str, guard=None) -> None:
    """/remember <text> — Self's own private note, from the COMMAND pane.
    2026-08-21, B64: the same record `[remember: ...]`
    typed at the circle prompt writes (annotations.remember_self_apply ->
    remember_manager.remember_add(remember_manager.SELF, ...)), reachable without a circle.

    THE CAP FOLLOWS THE CIRCLE. Inside one (`guard` is the loop's own, with
    an open time) the one-per-circle rule applies exactly as it does to the
    annotation — remember_has_written() reads the register back off disk, so a
    bracket and a command in the same circle share the one use. With no
    circle there is nothing to be one of: _NoCircleGuard carries no open
    time and the cap is not consulted. Empty text is a usage line, never a
    record — apply_self_remember's "malformed costs nothing" rule."""
    import remember_manager as RM
    body = " ".join(text.split())
    if not body:
        seam.emit("command", "  usage: /remember <text>")
        return
    g = guard if guard is not None else _NoCircleGuard()
    if g.ot and RM.remember_has_written(RM.SELF, g):
        seam.emit("command", "  second REMEMBER this circle — not written "
                             "(one per circle, the same rule the annotation "
                             "keeps)")
        return
    rec = RM.remember_add(RM.SELF, g, body)
    where = RM.remember_locate(RM.SELF, g)
    seam.emit("command", f"  remembered — {rec['text'][:56]}"
                         f"{'…' if len(rec['text']) > 56 else ''}")
    seam.emit("command", f"  ({where.name} under {where.parent.name}/"
                         + (", this circle" if g.ot else ", no circle open")
                         + ")")


# ---------------------------------------------------- CIRCLE_OBSERVATION CRUD
# circles/circle_observation_log.toml — SYNTHESIS's own note to Self about the
# CIRCLE as a working body, explicitly private (never projected into any
# part's prompt) and explicitly allowed to hold personal material. These
# five verbs were built 2026-09-01 on the operator's ask ("first class object with
# CRUD operations and a help entry"). No `record`/`guard` on any of them —
# same reasoning as /remember-list: nothing here is ever spoken, so there
# is no transcript step and no live/sandbox split (this register has none).

def command_observation_add(text: str) -> None:
    """/observation-add <text> — Self's own manual entry, `source="self"`."""
    import circle_observation_manager as CO
    body = " ".join(text.split())
    if not body:
        seam.emit("command", "  usage: /observation-add <text>")
        return
    rec = CO.circle_observation_manual_add(body)
    seam.emit("command", f"  added {rec['id']} — {rec['text'][:56]}"
                         f"{'…' if len(rec['text']) > 56 else ''}")


def command_observation_list(rest: str) -> None:
    """/observation-list [<n>] — bare lists (retired hidden unless --all);
    `<n>` shows one whole record. `--all` may appear with or without `<n>`."""
    import circle_observation_manager as CO
    a = rest.split()
    include_all = "--all" in a
    a = [x for x in a if x != "--all"]
    if not a:
        seam.emit("command", CO.circle_observation_list(include_retired=include_all))
        return
    if len(a) != 1 or not a[0].isdigit():
        seam.emit("command", "  usage: /observation-list [<n>] [--all]")
        return
    seam.emit("command", CO.circle_observation_show(int(a[0]), include_retired=include_all))


def command_observation_continue(rest: str) -> None:
    """/observation-continue <id> <text> — a NEW record chained onto <id>;
    <id>'s own record is never touched."""
    import circle_observation_manager as CO
    parts_ = rest.split(None, 1)
    if len(parts_) != 2 or not parts_[1].strip():
        seam.emit("command", "  usage: /observation-continue <id> <text>")
        return
    target, body = parts_[0], " ".join(parts_[1].split())
    try:
        rec = CO.circle_observation_continue_add(target, body)
    except ValueError as e:
        seam.emit("command", f"  {e}")
        return
    seam.emit("command", f"  added {rec['id']}, continuing {target}")


def _dependency_note(kind: str, ident: str) -> None:
    """Name what a removal PRESERVES before it happens — R570, 2026-09-15.
    Read only, and quiet when nothing leans on the record; a plan that cannot be read says
    nothing, and the verb goes on as it always did."""
    try:
        import dependency_manager as DM
        p = DM.dependency_plan(kind, ident)
    except Exception:                                           # noqa: BLE001
        return
    if p["preserve"] or p["handled"] or p["remove"] or p["rings"]:
        seam.emit("command", DM.dependency_plan_render(p))


def command_observation_retire(rest: str) -> None:
    """/observation-retire <id> — soft delete: hides from the default
    listing, stays in the file and in git history."""
    import circle_observation_manager as CO
    target = rest.strip()
    if not target:
        seam.emit("command", "  usage: /observation-retire <id>")
        return
    _dependency_note("observation", target)
    try:
        CO.circle_observation_retire_now(target)
    except ValueError as e:
        seam.emit("command", f"  {e}")
        return
    seam.emit("command", f"  {target} retired — `/observation-list --all` "
                         f"still shows it")


def command_observation_purge(rest: str) -> None:
    """/observation-purge <id> <id> — true delete of the TEXT only (the
    record shell survives so nothing else's `chain` breaks). The id must
    be typed twice, matching, as the one deliberate confirmation step —
    irreversible in the live file, recoverable only from git history at
    the commit before the purge, same as any other mistaken edit here."""
    import circle_observation_manager as CO
    a = rest.split()
    if len(a) != 2 or a[0] != a[1]:
        seam.emit("command", "  usage: /observation-purge <id> <id>  "
                             "— type the SAME id twice, to confirm")
        return
    _dependency_note("observation", a[0])      # the chain onto it keeps its shell
    try:
        CO.circle_observation_purge_now(a[0])
    except ValueError as e:
        seam.emit("command", f"  {e}")
        return
    seam.emit("command", f"  {a[0]} purged — text is gone from the live "
                         f"file; the pre-purge commit still has it")


def command_topic_list() -> None:
    """The TOPIC register (coordinator/topic_manager.py) — open TP- topics with
    their window, and the tombstone tally."""
    import topic_manager as TOP
    seam.emit("command", TOP.topic_list())


def command_topic_close(rest: str) -> None:
    """Self's disposition on one topic. IMMEDIATE, /practice-add's own
    contract: written the moment it is ruled, /abort does not undo it,
    and a SANDBOX circle's /topic-close still writes the LIVE register —
    the ruling is Self's own, whichever tree the circle writes to."""
    import topic_manager as TOP
    tid = rest.split()[0] if rest.split() else ""
    if not tid:
        seam.emit("command", "  usage: /topic-close TP-nnnn")
        return
    _ok, msg = TOP.topic_close(tid)
    seam.emit("command", f"  {msg}")


def _list_or_record(rest: str, verb: str, listing, record) -> None:
    """A `-list` verb's one argument (B133). Bare: `listing()`, which returns its text or emits
    it itself. A number: `record(n)`, that row whole. Anything else: the usage line — never the
    listing, which would read as the argument having been honoured."""
    a = rest.strip()
    if not a:
        out = listing()
        if out is not None:
            seam.emit("command", out)
    elif a.isdecimal():
        seam.emit("command", record(int(a)))
    else:
        seam.emit("command", f"  usage: {verb} [<n>]  — bare lists them, <n> shows one whole")


def command_practice_list(rest: str = "") -> None:
    """The CIRCLE's practices — every row not addressed to Self. Until
    2026-08-21 this printed the whole register; the rows addressed to Self
    are /better-option-list's now (the operator: "add a path for
    /better-option-list and make it always visible"), each list numbered on
    its own. A row addressed to ONE part (narrowcast) is still the circle's,
    and stays here. `<n>` shows one row whole (B133)."""
    import practice_manager as PM
    _list_or_record(rest, "/practice-list", lambda: PM.practice_list(better_options=False),
                    lambda n: PM.practice_record_show(n, better_options=False))


def command_better_option_list(rest: str = "") -> None:
    """/better-option-list — "how you move": the rows of the one register
    (R133) addressed to Self, numbered on their own. Minted 2026-08-21; a
    USER verb, always visible, while /better-option-add is DEV for now.
    `<n>` shows one row whole (B133)."""
    import practice_manager as PM
    _list_or_record(rest, "/better-option-list", lambda: PM.practice_list(better_options=True),
                    lambda n: PM.practice_record_show(n, better_options=True))


def command_propose_add(rest: str, *, record=None, guard=None) -> None:
    """/propose-add <command> — stage a proposal YOURSELF, from the command
    pane: the same register, vetting and checkpoint ruling a part's
    [proposed: <command>] reaches (R350, the operator,
    2026-08-25). Bare `propose` is an alias (SYNONYMS). The body meets the
    IDENTICAL test the annotation meets — annotations' _propose_command_shape —
    so there is one grammar, not two, the same argument _add_practice_row
    makes one register over. The one exception is a verb whose bracket offers
    the statement it rides in (command_surface.OWN_STATEMENT_COMMANDS): this
    door has no statement, so it refuses those.

    A SANDBOX CIRCLE REFUSES IT: proposal_stage() already rules
    that "a sandbox circle's proposal is a draft, not something to stage
    into the live self/proposals.toml" (R202), and this door writes the
    same live register. No circle at all is fine — the row is ruled at the
    next checkpoint, wherever that falls; `circle` is then "" and the
    author credit is plain "Self"."""
    import annotations as MK
    import proposal_manager as PR
    text = rest.strip()
    if not text:
        seam.emit("command", "  usage: /propose-add <command>   (also bare "
                             "propose)")
        seam.emit("command", "  " + MK._proposable_list())
        return
    import command_surface as CS
    words = text.lstrip("/").split(None, 1)
    head = CS.command_head_normalise("/" + words[0]) if words else ""
    if head in CS.OWN_STATEMENT_COMMANDS:
        # R541: this verb's bracket offers the statement it
        # rides in, and the command pane has no statement for it to ride in.
        typed = next((row[0] for row in CS.COMMANDS if row[0].split()[0] == head), head)
        seam.emit("command", f"  refused — {head} offers the statement a part's "
                             f"bracket rides in, and /propose-add has none. "
                             f"Attach one yourself, in a circle: {typed}")
        return
    shape = MK._propose_command_shape(text)
    if shape is None:
        seam.emit("command", "  not a proposable command — nothing staged. "
                             + MK._proposable_list())
        return
    if not shape.get("ok", False):
        seam.emit("command", f"  refused — {shape['why']}")
        return
    ot = ""
    if guard is not None:
        if not getattr(guard, "live", True):
            # R202 is the ruling; not emitted, since this line ships. 2026-09-09.
            seam.emit("command", "  a dry-run circle's proposal is a draft — "
                                 "not staged into the live register. "
                                 "Type it with no circle open, or in a live "
                                 "circle.")
            return
        ot = getattr(guard, "open_time", "") or ""
    pid = PR.proposal_row_stage("command", text, ["Self"], ot)
    seam.emit("command", f"  staged {pid} — pending your ruling at the next "
                         f"checkpoint (/propose-list shows it)")
    if record is not None:
        record()


def _propose_rows() -> list[tuple[str, str, dict, tuple, str]]:
    """/propose-list's rows in the order it numbers them — (heading, tag, row, ORDER, body):
    self/proposals.toml's pending rows, then any practice row still staged the pre-R273 way,
    then the settled. ONE sequence, so the listing and `/propose-list <n>` cannot number
    differently (B133)."""
    import proposal_manager as PR
    import practice_manager as PM
    rows = PR.proposal_read()
    out = [("PENDING", f"({r.get('kind', '?')})", r, PR.ORDER, "text")
           for r in rows if r.get("state") == "proposed"]
    out += [("PENDING, staged as a practice row", f"({r.get('op', '?')})", r, PM.ORDER, "title")
            for r in PM.practice_pending_list()]
    out += [("SETTLED", f"({r.get('state', '?')})", r, PR.ORDER, "text")
            for r in rows if r.get("state") != "proposed"]
    return out


def command_propose_list(rest: str = "") -> None:
    """/propose-list [<n>] — what is staged: self/proposals.toml's pending rows
    first (what awaits a ruling at the next checkpoint), then any practice row
    still staged the pre-R273 way (the register vetting still reads), then the
    settled. Numbered across the whole listing; no circle needed. 2026-08-21.
    `<n>` shows that row whole, by its own register's ORDER (B133)."""
    import REGISTER_CLASS as SS
    seq = _propose_rows()

    def listing() -> None:
        if not seq:
            seam.emit("command", "  no proposals on file")
            return
        for n, (head, tag, r, _order, _body) in enumerate(seq, 1):
            if n == 1 or seq[n - 2][0] != head:
                seam.emit("command", f"\n  {head} ({sum(1 for s in seq if s[0] == head)})")
            src = ", ".join(r.get("sources", [])) or "?"
            text = " ".join((r.get("text") or r.get("title") or "").split())
            prefix = f"  {n:>3}  [{r['id']}] {tag} {src} · {r.get('circle', '?')}  "
            seam.emit("command", prefix + text[:max(10, HELP_WIDTH - len(prefix))])
        seam.emit("command", "\n" + SS.register_list_footer(len(seq), "/propose-list"))

    def record(n: int) -> str:
        order, body = seq[n - 1][3:] if 1 <= n <= len(seq) else ((), "")
        return SS.register_record_show([s[2] for s in seq], n, order, body=body,
                                       verb="/propose-list")

    _list_or_record(rest, "/propose-list", listing, record)


PRACTICE_UPDATE_USAGE = "/practice-update <n> <text>  — the number /practice-list showed"
TOPIC_UPDATE_USAGE = "/topic-update TP-nnnn <text>"


def command_practice_update(text: str, record=None) -> tuple[bool, str]:
    """/practice-update <n> <text> — replace the title of the practice at /practice-list's
    number <n>, in place; id and origin stay, `amended` takes today's date (R465, B116,
    2026-09-07). Written immediately, like /practice-add."""
    import practice_manager as PM
    parts = text.split(None, 1)
    if len(parts) < 2 or not parts[0].strip().isdigit():
        msg = f"usage: {PRACTICE_UPDATE_USAGE}"
        seam.emit("command", f"  {msg}")
        return False, msg
    ok, msg = PM.practice_update(int(parts[0]), parts[1])
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()
    return ok, msg


def command_topic_update(text: str) -> tuple[bool, str]:
    """/topic-update TP-nnnn <text> — replace one open topic's text in place; id, circle
    and date stay, `amended` takes today's date (R465, B116, 2026-09-07). IMMEDIATE, the
    contract /topic-close keeps: written the moment it is typed, /abort does not undo it,
    and a sandbox circle's /topic-update still writes the LIVE register."""
    import topic_manager as TOP
    parts = text.split(None, 1)
    if len(parts) < 2 or not parts[0].strip().upper().startswith("TP-"):
        msg = f"usage: {TOPIC_UPDATE_USAGE}"
        seam.emit("command", f"  {msg}")
        return False, msg
    ok, msg = TOP.topic_update(parts[0].strip().upper(), parts[1])
    seam.emit("command", f"  {msg}")
    return ok, msg


def command_practice_delete(arg: str, record=None) -> None:
    import practice_manager as PM
    a = arg.strip()
    if not a.isdigit():
        seam.emit("command", "  usage: /practice-delete <n>  — the number "
                             "/practice-list showed (not /better-option-list's)")
        return
    shown = [p for p in PM.practice_read() if p.get("addressee") != PM.BETTER_OPTION_ADDRESSEE]
    if 1 <= int(a) <= len(shown) and shown[int(a) - 1].get("id"):
        _dependency_note("practice", shown[int(a) - 1]["id"])      # R570
    ok, msg = PM.practice_delete(int(a))
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()


def _add_practice_row(text: str, addressee: str, usage: str,
                       record=None) -> tuple[bool, str]:
    """The write behind /practice-add and /better-option-add.

    ONE REGISTER, TWO ADDRESSEES (R133): both write
    self/best_practices.toml and differ in `addressee` alone — "All parts"
    is how the CIRCLE behaves, "Self" is "how you move". They are two VERBS
    rather than one verb with a flag because the two read entirely
    differently to whoever is addressed, and because a proposal names a
    verb; they are ONE BODY because practice_manager.practice_add()'s own
    docstring makes exactly this argument one layer down, and a near-copy
    here would be the second place for the shape to drift.

    THE USAGE LINE IS THE VERB'S, NOT THE REGISTER'S. add() refuses an
    empty body neutrally; naming the command is a decision this module
    owns, the same way cmd_practice_delete and cmd_topic_close own
    theirs.

    RETURNS (ok, msg), B62 2026-08-23 — until then this returned nothing
    and a caller could only ever know the head was recognised, never
    whether the write actually happened. `_propose_approve()`'s dev_cmd
    branch is the one that needed it: see proposal_vetting.py."""
    import practice_manager as PM
    if not " ".join(text.split()).strip():
        msg = f"usage: {usage}"
        seam.emit("command", f"  {msg}")
        return False, msg
    ok, msg = PM.practice_add(text, addressee=addressee)
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()
    return ok, msg


def command_better_option_add(text: str, record=None) -> tuple[bool, str]:
    """A row addressed to Self — "how you move", not how the CIRCLE behaves.

    IT EXISTS SO THE ANNOTATION GRAMMAR COULD SHRINK (R270). Until it did,
    the only way to propose one was `[proposed better_option: ...]`, one of
    six bracket spellings; with a command behind it, `[proposed:
    /better-option-add ...]` says the same thing through the one form the
    grammar collapsed to."""
    import practice_manager as PM
    return _add_practice_row(text, PM.BETTER_OPTION_ADDRESSEE,
                      "/better-option-add <how you move>", record)


def command_practice_add(text: str, record=None) -> tuple[bool, str]:
    import practice_manager as PM
    return _add_practice_row(text, PM.PRACTICE_ADDRESSEE,
                      "/practice-add <your practice statement>", record)


# ISSUE_NODE_RE MOVED to command_surface.py, 2026-08-16 (phase 2 stage
# 0) — shared by the annotation grammar's issue_status classification and
# the /issue command forms; imported at the top of this file.


# --------------------------------------------------------------- /group-*
GROUP_ADD_USAGE = '/group-add "<name>" <member1>,<member2>,... [layer=<path>]'


def _group_layer_split(members_text: str) -> tuple[str, "str | None"]:
    """`<m1>,<m2>,... [layer=<path>]` -> (the member text, the layer path or None). The
    trailing token is the only place a layer is given (B115, R464): a path relative to the
    tree naming the group's BLOCK 1 layer file."""
    toks = members_text.split()
    if toks and toks[-1].startswith("layer="):
        return " ".join(toks[:-1]), toks[-1][len("layer="):].strip() or None
    return members_text, None


def _group_add_args(rest: str) -> tuple[str, list[str], "str | None"]:
    """`"<name>" <m1>,<m2>,... [layer=<path>]` -> (name, members, layer). The name must be
    quoted (straight or curly, matching every other quoted-arg parser in
    this file) so a multi-word name stays one token; members follow as a
    bare comma-separated list, matching how --parts already reads its
    own list on the command line."""
    s = " ".join(rest.split()).strip()
    if not s or s[0] not in ('"', "“"):
        return "", [], None
    m = _ISSUE_ADD_ARG_RE.match(s)
    if not m:
        return "", [], None
    name = (m.group(1) if m.group(1) is not None
            else m.group(2) or "").replace('\\"', '"').strip()
    members_text, layer = _group_layer_split(s[m.end():].strip())
    members = [p.strip() for p in members_text.split(",") if p.strip()]
    return name, members, layer


def command_group_add(text: str, record=None) -> tuple[bool, str]:
    import group_manager as GA
    name, members, layer = _group_add_args(text)
    if not name:
        msg = f"usage: {GROUP_ADD_USAGE}"
        seam.emit("command", f"  {msg}")
        return False, msg
    ok, msg = GA.group_add(name, members, layer)
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()
    return ok, msg


def _view_text(result: "tuple[bool, str]") -> str:
    ok, text = result
    return text if ok else f"  {text}"


def command_part_list(rest: str = "") -> None:
    """/part-list [<n>] — `<n>` is that part's long_term.md, /part-view's view, at any dev
    state (R534, B133)."""
    import part_add as PA
    _list_or_record(rest, "/part-list", PA.part_list,
                    lambda n: _view_text(PA.part_view(str(n))))


def command_group_list(rest: str = "") -> None:
    """/group-list [<n>] — `<n>` is that group's descriptor, /group-view's view, at any dev
    state (R534, B133)."""
    import group_manager as GA
    _list_or_record(rest, "/group-list", GA.group_list,
                    lambda n: _view_text(GA.group_view(str(n))))


def command_group_view(n_text: str) -> None:
    import group_manager as GA
    ok, text = GA.group_view(n_text)
    seam.emit("command", text if ok else f"  {text}")


GROUP_UPDATE_USAGE = "/group-update <n> <member1>,<member2>,..."   # layer= accepted, unadvertised (R562)


def command_group_update(text: str, record=None) -> tuple[bool, str]:
    """/group-update <n> <m1>,<m2>,... — replace the members of the group at
    /group-list's number <n>, in place; the name stays (B112, 2026-09-06).
    Members are the same bare comma-separated list /group-add takes. A trailing layer=<path>
    is still accepted and replaces the group's BLOCK 1 layer file (B115), but no help names it
    — R562 (2026-09-12): a layer is set at /group-add or by editing group.toml."""
    import group_manager as GA
    parts = text.split(None, 1)
    if len(parts) < 2 or not parts[0].strip().isdigit():
        msg = f"usage: {GROUP_UPDATE_USAGE}"
        seam.emit("command", f"  {msg}")
        return False, msg
    n_text = parts[0].strip()
    members_text, layer = _group_layer_split(parts[1])
    members = [p.strip() for p in members_text.split(",") if p.strip()]
    ok, msg = GA.group_update(n_text, members, layer)
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()
    return ok, msg


def command_group_delete(n_text: str, interactive: bool = True) -> None:
    """/group-delete <n> — confirmation is typing the group's NAME back,
    the same friction part_add.part_retire() uses for a part: a mistaken
    deletion would silently invalidate a real `circle.py --group <name>`
    invocation someone may already depend on, even though a group carries
    no file-removal risk of its own."""
    import group_manager as GA
    hit = GA.group_delete(n_text)
    if hit is None:
        seam.emit("command", f"  no group #{n_text.strip() or '?'} — "
                             f"/group-list shows them")
        return
    _ok, name = hit
    if not interactive:
        seam.emit("command", "  /group-delete needs the command line — "
                             "not available here")
        return
    ans = PC.stream_timed_read(seam.read_line, f"  type the group name ({name}) to delete: ",
                         channel="command").strip()
    if ans != name:
        seam.emit("command", "  cancelled — nothing removed.")
        return
    _ok, msg = GA.group_delete_confirmed(name)
    seam.emit("command", f"  {msg}")


# --------------------------------------------------------- /redact-alias-*
REDACT_ADD_USAGE = '/redact-alias-add "<canonical>" [<kind>] ["<form>" ...]'
REDACT_UPDATE_USAGE = ('/redact-alias-update <n> "<canonical>" '
                       '["<form>" ...]  — kind is not editable; delete and '
                       're-add to change it')


def _redact_alias_args(rest: str) -> tuple[str, str, list[str]]:
    """`"<canonical>" [<kind>] ["<form>" ...]` -> (canonical, kind, forms).
    kind defaults to "" (caller decides "other") when no bare word sits
    between the first quoted string and the next. THE FIRST CHARACTER
    DECIDES, the same rule _issue_add_args uses: a canonical must be
    quoted, or nothing here parses. Straight or curly quotes, same as
    that parser — Self types straight, a part (if it ever reaches this
    grammar) would type curly."""
    s = " ".join(rest.split()).strip()
    if not s or s[0] not in ('"', "“"):
        return "", "", []
    matches = list(_ISSUE_ADD_ARG_RE.finditer(s))
    if not matches:
        return "", "", []

    def _text(m) -> str:
        return (m.group(1) if m.group(1) is not None
                else m.group(2) or "").replace('\\"', '"').strip()

    canonical = _text(matches[0])
    between_end = matches[1].start() if len(matches) > 1 else len(s)
    between = s[matches[0].end():between_end].strip()
    kind = between.split()[0].lower() if between else ""
    forms = [_text(m) for m in matches[1:]]
    return canonical, kind, forms


def command_redact_alias_add(text: str, record=None) -> tuple[bool, str]:
    import redaction_manager as RDX
    canonical, kind, forms = _redact_alias_args(text)
    if not canonical:
        msg = f"usage: {REDACT_ADD_USAGE}"
        seam.emit("command", f"  {msg}")
        return False, msg
    ok, msg = RDX.alias_add(canonical, kind or "other", forms)
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()
    return ok, msg


def command_redact_alias_update(text: str, record=None) -> tuple[bool, str]:
    import redaction_manager as RDX
    toks = (text or "").split(None, 1)
    n_str = toks[0] if toks else ""
    rest = toks[1] if len(toks) > 1 else ""
    if not n_str.isdigit():
        msg = f"usage: {REDACT_UPDATE_USAGE}"
        seam.emit("command", f"  {msg}")
        return False, msg
    # kind (the second return value) is discarded here on purpose — kind
    # is not editable via update, so a bare word after the canonical is
    # silently ignored rather than mistaken for a form.
    canonical, _kind, forms = _redact_alias_args(rest)
    if not canonical:
        msg = f"usage: {REDACT_UPDATE_USAGE}"
        seam.emit("command", f"  {msg}")
        return False, msg
    ok, msg = RDX.alias_update(int(n_str), canonical, forms)
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()
    return ok, msg


def command_redact_alias_delete(arg: str, record=None) -> None:
    import redaction_manager as RDX
    a = arg.strip()
    if not a.isdigit():
        seam.emit("command", "  usage: /redact-alias-delete <n>  — the "
                             "number /redact-alias-list showed")
        return
    ok, msg = RDX.alias_delete(int(a))
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()


def command_redact_alias_list(rest: str = "") -> None:
    import redaction_manager as RDX
    _list_or_record(rest, "/redact-alias-list", RDX.alias_list, RDX.alias_record_show)


def command_issue_apply(rest: list[str]) -> None:
    if not rest:
        seam.emit("command", "  usage: /issue-apply <commands.toml>")
        return
    out, _ = IC._run_captured(["memory/issue_commands.py"] + rest)
    if out:
        seam.emit("command", out)


def command_issue_status_show(node_id: str) -> None:
    for p in S_.issue_nodes_read():
        doc = S_.issue_read(p)
        if doc["id"] == node_id:
            # `root` is a flag on `live`, not its own status (RNEW-
            # root-subset-of-live) — said here explicitly, or a root would
            # print identically to any other live node and the one thing
            # that made it distinct (never retired, always shown in full)
            # would be invisible to the person asking.
            tag = " (root)" if doc.get("root") else ""
            seam.emit("command", f"  {node_id}: {doc['status']}{tag}")
            return
    seam.emit("command", f"  no such issue: {node_id}")


def _issue_status_plan_stage(node_id: str, val: str) -> None:
    """The closure refusal's plan, staged — R570, 2026-09-15: each open
    issue-relationship's retirement as a suggestion, then this status change depending on all
    of them, so denying any one denies the change. Says what it staged; a failure says so."""
    try:
        import dependency_manager as DM
        p = DM.dependency_plan("issue", node_id)
        if not DM.dependency_plan_is_blocked(p):
            return
        seam.emit("command", DM.dependency_plan_render(p))
        steps, final = DM.dependency_plan_stage(p, f"/issue-status {node_id} = {val}")
    except Exception as e:                                      # noqa: BLE001
        seam.emit("command", f"  the plan was not staged ({type(e).__name__}: {e}) — retire the "
                             f"issue-relationships named above first, then set it again")
        return
    seam.emit("command", f"  staged for your ruling at the next checkpoint: {', '.join(steps)} "
                         f"first, then {final}. Denying any of them denies {final}. "
                         f"/propose-list shows them.")


def command_issue_status_set(node_id: str, val: str, trailing: list[str], *,
                             plan: bool = True) -> bool:
    """True only when the REAL apply ran and exited 0 — the bool the
    vetting loop's issue_status approval rests on since 2026-08-19
    (review tier 2 #13): before it, every exit from here looked the same
    to a caller, so a cancelled confirmation or a refused dry-run still
    flipped the proposal to 'accepted... executed'."""
    if val not in S_.STATUSES:
        seam.emit("command", f"  {val!r} is not a status. Known: "
              f"{', '.join(sorted(S_.STATUSES))}")
        return False
    yes = "--yes" in trailing or "-y" in trailing
    # --dry-run stripped too, not just --yes/-y: the real apply call below
    # already runs unconditionally AFTER this function's own dry-run
    # preview — a caller-supplied --dry-run surviving into it would make
    # the "real" apply itself a no-op, reporting success with nothing
    # written.
    trailing = [t for t in trailing if t not in ("--yes", "-y", "--dry-run")]

    out, rc = IC._run_captured(["memory/issue_status.py", node_id,
                             "--to", val, "--dry-run"] + trailing)
    if out:
        seam.emit("command", out)
    if rc != 0:
        # A CLOSURE REFUSAL STAGES THE PLAN — R570, 2026-09-15. Exit 1 in a
        # dry run is issue_status.py's closure refusal and nothing else, and its own words are
        # matched too, so a probe's mocked refusal (no output) stages nothing. `plan` False is
        # a staged suggestion's own approval, which must never stage itself again.
        if plan and rc == 1:
            import issue_status as IS
            if IS.CLOSURE_REFUSED_MARK in (out or ""):
                _issue_status_plan_stage(node_id, val)
        return False                    # refused — no effect, nothing to confirm

    if not yes:
        answer = PC.stream_timed_read(seam.read_line, "  type 'yes' to apply: ").strip().lower()
        if answer != "yes":
            seam.emit("command", "  cancelled — no change made")
            return False

    # rc2 was DISCARDED until 2026-08-19 (`out2, _ = ...`), so a real
    # apply that failed after a clean dry-run — the exact window the
    # issue_status regen-chain bug lived in — fell through as success.
    out2, rc2 = IC._run_captured(["memory/issue_status.py", node_id,
                               "--to", val] + trailing)
    if out2:
        seam.emit("command", out2)
    if rc2 != 0:
        seam.emit("command", f"  the apply itself FAILED (exit {rc2}) — "
                             f"see the output above")
        return False
    return True


def command_issue_status_op(node_id: str, op_raw: str, trailing: list[str]) -> bool:
    """True when the operation ran: a show always did; a set only when
    command_issue_status_set() reports the real apply succeeded."""
    val = None
    if "=" in op_raw:
        _, _, val = op_raw.partition("=")
        val = val.strip()
    elif trailing and trailing[0] == "=":
        val = trailing[1] if len(trailing) > 1 else ""
        trailing = trailing[2:]
    elif trailing and trailing[0] == "show":
        trailing = trailing[1:]
    if val:
        return command_issue_status_set(node_id, val, trailing)
    command_issue_status_show(node_id)
    return True


# ------------------------------------------------------------- the settings
# THE CONFIGURATION EDITOR, 2026-08-28 (R379). Three verbs
# over coordinator/setting_manager.py, on the COMMAND pane only.
#
# NOTHING HERE RECORDS TO THE TRANSCRIPT, and that is not an omission: a
# settings verb has no Self> surface at all (command_surface classifies all
# three as "command"), so there is no line for a part to see and nothing to
# withhold. Contrast /practice-add, which takes `record=` for exactly that
# reason.


def _settings_rows():
    """What this person may see. dev ADDS fields; it never takes one away."""
    import command_surface as CS
    import setting_manager as SET
    return SET.setting_visible_read(dev=bool(getattr(CS, "dev_mode", False)))


def _emit_wrapped(indent: str, text: str) -> None:
    """Description lines wrap at 80 COLUMNS — the operator's ruling,
    2026-08-29, reviewing the settings listing in the Ticker flavor."""
    import textwrap
    for line in textwrap.wrap(text, width=80, initial_indent=indent,
                              subsequent_indent=indent) or [indent.rstrip()]:
        seam.emit("command", line)


def _settings_seq() -> list:
    """/settings-list's rows in the order it numbers them — (heading, declaration, provider):
    every setting this person may see, then the active provider's own knobs, whose provider is
    set. ONE sequence, so the listing and `/settings-list <n>` cannot number differently — the
    rule /propose-list keeps across its three headings (B133)."""
    import llm_client as LC
    prov = LC.PROVIDER_IMPL
    seq: list = [("SETTINGS", s, None) for s in _settings_rows()]
    seq += [(prov.name.upper(), k, prov) for k in getattr(prov, "TUNING", ())]
    return seq


def _record_fit(rec: dict, room: int = 64) -> dict:
    """A record's longer sentences broken into lines, so register_record_show() prints each as a
    block under its label and the record keeps the 80 columns the listing keeps (the operator,
    2026-08-29). `room` is what fits beside the widest label."""
    import textwrap
    return {k: ("\n".join(textwrap.wrap(v, 72)) if isinstance(v, str) and len(v) > room else v)
            for k, v in rec.items()}


def command_settings_list(rest: str = "") -> None:
    """/settings-list [<n>] — every setting this person may see, then the active provider's own
    knobs, numbered across both. `<n>` shows that one whole: the value the program uses when
    nothing is changed, what it accepts, and — for a setting — why that value
    (R543, answering D122 (c)). A knob carries no reason; its provider
    declared none."""
    import REGISTER_CLASS as SS
    import command_surface as CS
    import setting_manager as SET
    seq = _settings_seq()

    def listing() -> None:
        act, pend = SET.setting_active_read(), SET.setting_pending_read()
        if not SET.REGISTER.is_file():
            seam.emit("command", "  nothing has been changed — every setting is "
                                 "what the program decides")
        for n, (head, s, prov) in enumerate(seq, 1):
            if n == 1 or seq[n - 2][0] != head:
                seam.emit("command", f"\n  {head} ({sum(1 for x in seq if x[0] == head)})")
            if prov is None:
                _settings_row_emit(n, s, act, pend)
            else:
                _settings_tuning_row_emit(n, s, prov)
        seam.emit("command", "\n  /settings-update <name> to change one, "
                             "/settings-clear <name> to undo it")
        seam.emit("command", SS.register_list_footer(len(seq), "/settings-list"))

    def record(n: int) -> str:
        dev = bool(getattr(CS, "dev_mode", False))
        rows = [_record_fit(SET.setting_record_read(s, dev=dev) if prov is None
                            else SET.setting_tuning_record_read(prov, s, dev=dev))
                for _head, s, prov in seq]
        order = ((SET.RECORD_ORDER if seq[n - 1][2] is None else SET.TUNING_RECORD_ORDER)
                 if 1 <= n <= len(seq) else ())
        return SS.register_record_show(rows, n, order, verb="/settings-list")

    _list_or_record(rest, "/settings-list", listing, record)


def _settings_row_emit(n: int, s, act: dict, pend: dict) -> None:
    import setting_manager as SET
    lit, _why = SET.setting_source_default_read(s.owner, s.key)
    chosen = s.key in act
    # RENDERED IN THE PERSON'S OWN WORDS — settings.setting_show(), 2026-08-29.
    # Without it the first BOOL setting reports `True` in a list whose
    # dialog asks a yes/no question.
    cur = SET.setting_show(s.key, act[s.key] if chosen else lit)
    tail = "" if chosen else "   (unchanged)"
    unit = f" {s.unit}" if s.unit else ""
    seam.emit("command", f"  {n:>3}  {s.key:<24} {cur}{unit}{tail}")
    _emit_wrapped("         ", s.ask)
    if s.key in pend:
        seam.emit("command", f"         waiting: {pend[s.key]}{unit} — "
                             f"from the next circle")


def _settings_tuning_row_emit(n: int, k, prov) -> None:
    """One of the ACTIVE PROVIDER's own knobs — stage 4 (R382). Listed under
    their own heading because they are that service's, not this program's:
    they appear and disappear with the provider, and what they accept is its
    business."""
    import setting_manager as SET
    set_now = SET.setting_tuning_read(prov)
    chosen = k.key in set_now
    cur = set_now.get(k.key, k.default)
    seam.emit("command", f"  {n:>3}  {k.key:<24} {cur}"
                         f"{'' if chosen else '   (unchanged)'}")
    _emit_wrapped("         ", k.ask)
    _emit_wrapped("         ", "one of: " + ", ".join(k.values))


def command_settings_update(rest_text: str, *, interactive: bool = True) -> None:
    """`/settings-update <name> <value>` applies directly, on ANY surface;
    `/settings-update <name>` alone asks, where a surface can ask.

    THE VALUE-ON-THE-LINE FORM IS THE OPERATOR'S RULING (2026-08-29), after
    the Ticker flavor's cmd> pane — a real interactive surface — was told
    "(no interactive surface — nothing changed)" and had its typed value
    ignored. The verb read only the first token by design; now a second
    token is the new value, validated by the same writers the question-form
    uses, so no surface needs a blocking read to change a setting. Where a
    bare-key ask lands on a surface that cannot block, the tail line says
    HOW to change it instead of falsely describing the surface.

    Output shape, same ruling: the blank line follows the output; nothing
    is emitted before it.

    A BARE `/settings-update` PRINTS USAGE AND READS NOTHING. That is a real
    contract, not a nicety: test_dispatch_partition.py discovers which verbs
    this dispatcher answers by CALLING each one with no argument, so a verb
    that blocked on input there would hang the suite rather than fail it."""
    import setting_manager as SET
    toks = (rest_text or "").split()
    key = toks[0] if toks else ""
    value = " ".join(toks[1:]).strip()
    rows = _settings_rows()
    if not key:
        seam.emit("command", "  usage: /settings-update <name> [<new value>]")
        seam.emit("command", "  " + ", ".join(s.key for s in rows))
        seam.emit("command", "")
        return
    # A PROVIDER'S OWN KNOB, tried first — settings --check refuses a knob
    # whose name collides with a plain setting, so the two namespaces cannot
    # overlap and the order here cannot make a name ambiguous.
    import llm_client as LC
    prov = LC.PROVIDER_IMPL
    knob = next((k for k in getattr(prov, "TUNING", ()) if k.key == key), None)
    if knob is not None:
        cur = SET.setting_tuning_read(prov).get(key, knob.default)
        seam.emit("command", f"  {knob.ask}?")
        seam.emit("command", f"  it is {cur} now; {prov.name} accepts "
                             f"{', '.join(knob.values)}")
        if value:
            ok, msg = SET.setting_tuning_write(prov, key, value)
            seam.emit("command", ("  " + msg) if ok
                      else f"  not changed — {msg}")
            seam.emit("command", "")
            return
        if not interactive:
            seam.emit("command",
                      f"  to change it: /settings-update {key} <value>")
            seam.emit("command", "")
            return
        answer = PC.stream_timed_read(seam.read_line, "  new value (Enter keeps it): ").strip()
        if not answer:
            seam.emit("command", "  kept")
            seam.emit("command", "")
            return
        ok, msg = SET.setting_tuning_write(prov, key, answer)
        seam.emit("command", ("  " + msg) if ok else f"  not changed — {msg}")
        seam.emit("command", "")
        return
    spec = next((s for s in rows if s.key == key), None)
    if spec is None:
        # A REAL SETTING THIS PERSON MAY NOT SEE IS NOT "NO SUCH SETTING" —
        # but it is not named either, because naming it would leak the
        # dev-only surface that dev=false exists to keep back.
        seam.emit("command", f"  {key} is not a setting you can change here")
        seam.emit("command", "")
        return
    lit, _why = SET.setting_source_default_read(spec.owner, spec.key)
    # MERGED 2026-08-29: master's SET.setting_show display formatting AND the
    # branch's value-on-the-line form + blank-line-after shape, together.
    cur = SET.setting_show(spec.key, SET.setting_active_read().get(spec.key, lit))
    seam.emit("command", f"  {spec.ask}?")
    seam.emit("command", f"  it is {cur} now"
                         + (f" ({spec.unit})" if spec.unit else ""))
    seam.emit("command", f"  the program's own value is "
                         f"{SET.setting_show(spec.key, lit)}, set in {spec.owner}")
    if value:
        ok, msg = SET.setting_write(spec.key, value, now=_no_circle_open())
        seam.emit("command", ("  " + msg) if ok else f"  not changed — {msg}")
        if ok:
            _signal_redact_view_write(spec, value)
        seam.emit("command", "")
        return
    if not interactive:
        seam.emit("command", f"  to change it: /settings-update {key} <value>")
        seam.emit("command", "")
        return
    answer = PC.stream_timed_read(seam.read_line, "  new value (Enter keeps it): ").strip()
    if not answer:
        seam.emit("command", "  kept")
        seam.emit("command", "")
        return
    ok, msg = SET.setting_write(spec.key, answer, now=_no_circle_open())
    seam.emit("command", ("  " + msg) if ok else f"  not changed — {msg}")
    if ok:
        _signal_redact_view_write(spec, answer)
    seam.emit("command", "")


def _signal_redact_view_write(spec, raw) -> None:
    """redact_view's own live-toggle wiring (2026-08-31): the one setting
    a Pane already on screen needs told about directly, because a running
    circle never re-reads its saved setting on its own. Fires only while
    a circle IS open — with none running there is no pane to flip, and
    SET.setting_write()'s own "takes effect now" is already the whole truth in
    that case. seam.py silences the "redact_view" channel for a headless
    run, so this costs nothing there."""
    if spec.key != "redact_view" or _no_circle_open():
        return
    import setting_manager as SET
    ok, parsed, _why = SET.setting_coerce(spec, raw)
    if not ok:
        return
    seam.emit("redact_view", "on" if parsed else "off")
    seam.emit("command", "  the view has changed now; the saved default "
                        "takes effect from the next circle")


def _signal_redact_view_clear() -> None:
    """clear()'s own counterpart: back to REDACT_VIEW_DEFAULT, same
    live-while-a-circle-runs rule as the write path above."""
    if _no_circle_open():
        return
    import stream_redaction as SR
    seam.emit("redact_view", "on" if SR.REDACT_VIEW_DEFAULT else "off")
    seam.emit("command", "  the view has changed now; the saved default "
                        "takes effect from the next circle")


def command_settings_clear(rest_text: str) -> None:
    import setting_manager as SET
    key = (rest_text or "").strip().split(" ")[0]
    if not key:
        seam.emit("command", "  usage: /settings-clear <name>")
        return
    if key not in {s.key for s in _settings_rows()}:
        seam.emit("command", f"  {key} is not a setting you can change here")
        return
    ok, msg = SET.setting_clear(key)
    seam.emit("command", "  " + msg)
    if ok and key == "redact_view":
        _signal_redact_view_clear()


def _no_circle_open() -> bool:
    """May an immediate change take effect right now? THIS MODULE ASKS;
    setting_manager.py never does — the one component that knows whether a circle
    is running is the one that decides, and circle_state fails closed, so an
    unanswerable question becomes "wait for the next circle" rather than
    "change it under a transcript in flight"."""
    try:
        import circle_state
        return not circle_state.circle_is_in_progress()
    except Exception:                                          # noqa: BLE001
        return False


# ------------------------------------------ /part-context-update, -list, -clear, /part-add
# MOVED FROM initialization.py, 2026-09-03 (cohesion re-homing, stage 5): the
# verbs live with every other cmd> verb; the dialogs they open stay in
# initialization — INIT.part_context_dialog, INIT.part_add_dialog and
# INIT._resolve_part. Verbatim bodies; USAGE became PART_CONTEXT_UPDATE_USAGE
# (this file names each verb's usage line for the verb) and cmd_part_add's
# `from commands import _issue_add_args` is a local name now.
PART_CONTEXT_UPDATE_USAGE = "/part-context-update <part>   — ask that part's context questions again, prefilled"


def command_part_context_update(rest: str, *, guard=None, interactive: bool = True) -> None:
    """`/part-context-update <part>` — PART_CONTEXT_DIALOG(part) with the
    recorded answers prefilled; the edit path for what the first-run
    dialog recorded (docs/Initialization.md §6). USER table: the data is
    the person's own. `<part>` is a directory name or a Tag,
    case-insensitive.

    `interactive` is False where no one can answer a question — the
    dual pane's no-circle dispatch hands every read an immediate "" — and
    the dialog would then silently keep everything and report it; better
    to say where it does work. `guard` present means a circle is open,
    whose BLOCK 3 was built before this write: said, effective next circle."""
    word = rest.strip().split()[0] if rest.strip() else ""
    if not word:
        seam.emit("command", f"  usage: {PART_CONTEXT_UPDATE_USAGE}")
        declared = [d for d in R.DIR_NAMES if R.part_context_read(d)]
        seam.emit("command", "  parts with context questions: "
                  + (", ".join(declared) if declared else "(none)"))
        return
    part = R.DIR_BY_TAG.get(word) or R.DIR_BY_TAG_ALL.get(word)
    if part is None:
        by_lower = {d.lower(): d for d in R.DIR_NAMES}
        by_lower.update({t.lower(): d for d, t in R.TAG_BY_DIR.items()})
        part = by_lower.get(word.lower())
    if part is None:
        seam.emit("command", f"  no part named {word!r} — parts: "
                             f"{', '.join(R.DIR_NAMES) or '(none)'}")
        return
    if not interactive:
        seam.emit("command", "  /part-context-update asks questions and needs a "
                             "command pane that can answer them: open a circle "
                             "first, or run  python coordinator/circle.py "
                             f"--dev-cmd part-context-update {part}")
        return
    outcome = INIT.part_context_dialog(part, prefill=True)
    if outcome == "completed" and guard is not None:
        seam.emit("command", "  (this circle's prompts were built before this — "
                             "the change reaches the next circle)")


def command_part_context_list(rest: str) -> None:
    """`/part-context-list [<part>]` — every part that declares context, its
    questions with the recorded answer beside each ("" shown as —); one
    part when named. Read-only; console-only (the answers never reach a
    transcript or a model except through their own render strings)."""
    word = rest.strip().split()[0] if rest.strip() else ""
    if word:
        part = INIT._resolve_part(word)
        if part is None:
            seam.emit("command", f"  no part named {word!r}")
            return
        targets = [part]
    else:
        targets = [d for d in R.DIR_NAMES if R.part_context_read(d)]
    if not targets:
        seam.emit("command", "  no part declares context questions")
        return
    for d in targets:
        ctx = R.part_context_read(d)
        tag = R.TAG_BY_DIR.get(d, d)
        if not ctx:
            seam.emit("command", f"\n  {tag} ({d}) declares no context questions")
            continue
        seam.emit("command", f"\n  {tag} ({d}) — {ctx['purpose'] or '(no purpose)'}")
        for q in ctx["questions"]:
            a = ctx["answers"].get(q["key"], "")
            seam.emit("command", f"    {q['ask']}?  {a if a else '—'}")


def command_part_context_clear(rest: str, *, interactive: bool = True) -> None:
    """`/part-context-clear <part>` — empties every recorded answer, after
    "type 'yes'", re-arming the first-run dialog for the next open (R327's
    repeat rule works from the record, so clearing the record is what asks
    again)."""
    word = rest.strip().split()[0] if rest.strip() else ""
    if not word:
        seam.emit("command", "  usage: /part-context-clear <part>")
        return
    part = INIT._resolve_part(word)
    if part is None or not R.part_context_read(part):
        seam.emit("command", f"  no part named {word!r} with context questions")
        return
    ctx = R.part_context_read(part)
    if not any(ctx["answers"].values()):
        seam.emit("command", f"  {R.TAG_BY_DIR.get(part, part)} has no recorded "
                             f"answers — nothing to clear")
        return
    if not interactive:
        seam.emit("command", "  /part-context-clear confirms before erasing and "
                             "needs a command pane that can answer: open a "
                             "circle first, or run  python coordinator/circle.py "
                             f"--dev-cmd part-context-clear {part}")
        return
    n = sum(1 for v in ctx["answers"].values() if v)
    ans = PC.stream_timed_read(seam.read_line, f"  erase {n} recorded answer(s) for "
                         f"{R.TAG_BY_DIR.get(part, part)} — type 'yes': ",
                         channel="command").strip().lower()
    if ans != "yes":
        seam.emit("command", "  cancelled — nothing erased.")
        return
    R.part_context_write(part, {k: "" for k in ctx["answers"]})
    seam.emit("command", "  cleared. The first-run dialog asks again at the "
                         "next open.")


def command_part_add(rest: str, *, guard=None, interactive: bool = True) -> None:
    """`/part-add ["<describe>" "<Tag>"]` — PART_ADD_DIALOG, the two strings
    (describe, then Tag) prefilled when given. This is the ONLY way in since
    R483: the verb left PROPOSE_SUBSET_COMMANDS, so approval's path (R323/R326's
    shape) can no longer be reached — the bracket it approved cannot be staged."""
    if not interactive:
        seam.emit("command", "  /part-add asks questions and needs a command "
                             "pane that can answer them: open a circle first, "
                             "or run  python coordinator/circle.py --dev-cmd "
                             "part-add")
        return
    describe, tag, _ = _issue_add_args(rest)
    seeds = {}
    if describe:
        seeds["describe"] = describe
    if tag:
        seeds["part_name"] = tag
    INIT.part_add_dialog(seeds=seeds or None)


def command_dev_dispatch(head: str, rest_text: str, *, record=None,
                     guard=None,
                     interactive: bool = True) -> bool:
    """The always-available verb surface (RULED 2026-08-13, Q1) — ONE
    dispatcher, THREE doors since B61 (2026-08-21): circle.py's own
    `--dev-cmd` CLI flag (a bare shell
    invocation, no circle, no circling, nothing to rebind, default
    seam.emit()/seam.read_line() = real print()/input() work as-is),
    ui/circling.py's command pane when no circle is running
    (CircleEngine._dispatch_no_circle, which rebinds seam.emit()/
    seam.read_line() to its own queue BEFORE calling this), and — B61 —
    circle.py's Self> LOOP itself, for every verb that is not genuinely
    circle-dependent. This function is agnostic to which caller it's
    reached through, by design, so there is exactly one place this
    dispatch logic lives. Returns False for anything not in this set —
    the attest-class verbs, which genuinely need a running circle — so
    each caller can refuse with its own appropriately-worded reason.

    B61, 2026-08-21 (the operator: "tidy now"). Until then circle.py's Self>
    loop DUPLICATED this chain across ten verbs (/prompt-show
    /practice-list /topic-list /recall /topic-close /practice-add
    /better-option-add /practice-delete /issue-apply /issue-list
    /issue-status(-update)), and nothing asserted the two agreed. The
    divergence had already shipped once: /recall was a row in COMMANDS
    and in KNOWN_CMDS, handled here, and had NO branch in the loop — so
    it worked at the command pane with no circle running and via
    --dev-cmd, and fell through to UNKNOWN COMMAND everywhere a circle
    was actually open (found by the 2026-08-19 audit, not by a gate).
    Adding /better-option-add (2026-08-20) had to edit both lists by
    hand. The two keyword-only parameters are the ONLY two things that
    ever stopped delegation, and their defaults keep every existing
    caller's call unchanged:

      record   the loop's transcript-recording callback, fired by the
               three WRITE verbs (/practice-add, /better-option-add,
               /practice-delete) on success only. RECORDED, NOT SENT —
               the same rule as /issue (R079): a practice is about how
               the room behaves; telling the room it just gained one
               would be the room reacting to its own rulebook
               mid-circle. These three are IMMEDIATE, not at close
               (ruled per command, 2026-08-05): the text is Self's own,
               not lifted from a statement, so there is nothing to
               validate against the room; the cost is that /abort does
               not undo them, which /help states rather than leaving to
               be discovered. NO PROJECTION STEP (R134): the register is
               read directly at the next prompt assembly. A no-circle
               caller passes nothing — there is no transcript to record
               into.
      guard    the circle's own WriteGuard (2026-08-21, with the verbs
               minted that day): /remember reads its open time to apply
               the one-per-circle rule and its live/sandbox split to find
               the register; /issue-add reads it to name the open circle
               in `opened`. A no-circle caller passes nothing — /remember
               then writes the real register uncapped, /issue-add leaves
               `opened` empty.

    coordinator/tests/test_dispatch_partition.py is the assertion the entry
    said was missing: the loop branches exactly the circle-dependent
    verbs and this chain handles the rest, with /help the one deliberate
    overlap (the loop answers the ROOM's /help; this door answers the
    command pane's)."""
    # THE SECOND FLUSH POINT — 2026-08-28. A settings correction found at
    # import must reach a surface, and this dispatcher is the other one: the
    # command pane with no circle running, and `--dev-cmd` from a shell.
    # Flushing here rather than in each verb means it cannot be forgotten by
    # a verb added later, and flush_corrections() is a no-op when the queue
    # is empty, so it costs nothing on every other call.
    import setting_manager as _SET
    _SET.setting_corrections_flush(lambda t: seam.emit("command", t))

    if head == "/help":
        command_help(rest_text)
    elif head == "/settings-list":
        # READ-ONLY. Nothing reaches the room from any of these three —
        # they are command-pane verbs, so there is no transcript step to
        # make and no live/sandbox split to draw.
        command_settings_list(rest_text)
    elif head == "/settings-update":
        command_settings_update(rest_text, interactive=interactive)
    elif head == "/settings-clear":
        command_settings_clear(rest_text)
    elif head == "/redact-alias-add":
        # No `record`/`guard` — same reasoning as /settings-*: this writes
        # self/redaction.toml directly, never the transcript, and needs no
        # live/sandbox split.
        command_redact_alias_add(rest_text)
    elif head == "/redact-alias-list":
        command_redact_alias_list(rest_text)
    elif head == "/redact-alias-update":
        command_redact_alias_update(rest_text)
    elif head == "/redact-alias-delete":
        command_redact_alias_delete(rest_text)
    elif head == "/practice-add":
        command_practice_add(rest_text, record=record)
    elif head == "/practice-list":
        command_practice_list(rest_text)
    elif head == "/practice-delete":
        command_practice_delete(rest_text, record=record)
    elif head == "/practice-update":
        command_practice_update(rest_text, record=record)
    elif head == "/better-option-add":
        command_better_option_add(rest_text, record=record)
    elif head == "/remember-list":
        # READ-ONLY, and Self's OWN register only (R224). Nothing is
        # written and nothing reaches the room, so there is no record
        # step and no live/sandbox split to make. (/recall arrived here
        # too, through the synonym table, until 2026-09-11.)
        command_remember_list(rest_text)
    elif head == "/remember":
        # WRITES Self's own register — the command-pane twin of the
        # [remember: ...] annotation, 2026-08-21. No transcript step: a
        # remember is private by definition (REMEMBER's blast-radius rule).
        command_remember(rest_text, guard=guard)
    elif head == "/observation-add":
        command_observation_add(rest_text)
    elif head == "/observation-list":
        command_observation_list(rest_text)
    elif head == "/observation-continue":
        command_observation_continue(rest_text)
    elif head == "/observation-retire":
        command_observation_retire(rest_text)
    elif head == "/observation-purge":
        command_observation_purge(rest_text)
    elif head == "/better-option-list":
        command_better_option_list(rest_text)
    elif head == "/propose-list":
        command_propose_list(rest_text)
    elif head == "/propose-add":
        # WRITES the live proposals register (a pending row, ruled at the
        # next checkpoint) — bare `propose` arrives here too, via SYNONYMS.
        command_propose_add(rest_text, record=record, guard=guard)
    elif head == "/issue-relationship-list":
        command_issue_relationship_list()
    elif head == "/issue-add":
        command_issue_add(rest_text, guard=guard, interactive=interactive)
    elif head == "/part-context-update":
        # PART_CONTEXT_DIALOG, prefilled — docs/Initialization.md §6,
        # 2026-08-23. Asks on the COMMAND channel, so it needs a surface that
        # can answer: `interactive` False (the dual pane's no-circle door)
        # is refused with where it works. A circle open (`guard`) means its
        # BLOCK 3 was built before this write — said, effective next circle.
        command_part_context_update(rest_text, guard=guard, interactive=interactive)
    elif head == "/part-context-list":
        command_part_context_list(rest_text)
    elif head == "/part-context-clear":
        command_part_context_clear(rest_text, interactive=interactive)
    elif head == "/part-add":
        # PART_ADD_DIALOG, the typed door — stage 5, 2026-08-23. The two
        # quoted strings (describe, Tag — the taught bracket's own order)
        # arrive prefilled when given; bare opens the dialog cold.
        command_part_add(rest_text, guard=guard, interactive=interactive)
    elif head == "/part-list":
        command_part_list(rest_text)
    elif head == "/part-view":
        import part_add as PA
        _ok, text = PA.part_view(rest_text)
        seam.emit("command", text if _ok else f"  {text}")
    elif head == "/part-retire":
        import part_add as PA
        PA.part_retire(rest_text)
    elif head == "/group-add":
        command_group_add(rest_text, record=record)
    elif head == "/group-list":
        command_group_list(rest_text)
    elif head == "/group-view":
        command_group_view(rest_text)
    elif head == "/group-update":
        command_group_update(rest_text, record=record)
    elif head == "/group-delete":
        command_group_delete(rest_text, interactive=interactive)
    elif head == "/topic-list":
        command_topic_list()
    elif head == "/topic-close":
        # IMMEDIATE, same contract as /practice-add — the docstring on
        # command_topic_close() carries the sandbox note.
        command_topic_close(rest_text)
    elif head == "/topic-update":
        command_topic_update(rest_text)
    elif head == "/prompt-show":
        who = rest_text.split()[0] if rest_text.split() else "circle"
        command_prompt_show(who)
    elif head == "/issue-apply":
        command_issue_apply(rest_text.split())
    elif head == "/issue-list":
        command_issue_list(rest_text)
    elif head in ("/issue-status", "/issue-status-update"):
        # THE PROPERTY CONSTRUCT, R261. A bare property READS; `= <value>`
        # WRITES; and `<object>-<property>-update <id> <value>` is the same
        # write spelled as a verb. This branched on `/issue` and then
        # re-derived everything from whether the first argument looked like
        # a node id — the shape R261 retired.
        #
        # IMMEDIATE, not batch-at-close, and that is unchanged by B61: a
        # NODE's status runs issue_status.py's own dry-run/confirm/apply
        # there and then, while every RULING form (the IC.HEADS verbs the
        # Self> loop keeps for itself) batches at close (R079).
        tok = rest_text.split()
        if not tok:
            if head == "/issue-status":
                # THE BARE PROPERTY OVER EVERY ISSUE, 2026-08-21: no id
                # names no issue, so the read is of all of them.
                command_issue_status_all()
            else:
                seam.emit("command", f"  usage: {head} nNNNN <value>")
            return True
        rest = tok[1:]
        if head == "/issue-status-update":
            # The synonym's argument IS the value; hand the reader the
            # `=` form it already knows rather than a second parser.
            rest = ["="] + rest
        command_issue_property(tok[0], "status", rest)
    else:
        return False
    return True


def command_issue_list(rest: str = "") -> None:
    """`/issue-list [<n>]` — the issues, numbered. R261/B59, 2026-08-20.

    NEW WITH THE REGRAMMAR, and it is not a rename of anything: there was
    no command that answered "what is in the graph" at all. `/help issue
    list` answered it from the help hierarchy, which is a different
    surface with a different audience.

    "issue", never "node", in what it prints — R279,
    2026-08-21; and it counts what it lists: EVERY issue on file, with the
    live ones counted beside, where it used to say "live node(s)" over a
    listing that included the leads, roots and the settled.

    `<n>` shows that issue whole — every field its node carries (B133). A convenience beside
    the id, never instead of it: `nNNNN` never moves, and the number shifts as issues arrive."""
    import REGISTER_CLASS as SS
    docs = sorted((S_.issue_read(f) for f in S_.issue_nodes_read()), key=lambda d: d["id"])

    def listing() -> None:
        if not docs:
            seam.emit("command", "  no issues on file")
            return
        n_live = sum(1 for d in docs if d.get("status") == "live")
        seam.emit("command", f"\n  {len(docs)} issue(s), {n_live} live")
        for i, d in enumerate(docs, start=1):
            prefix = f"  {i:>3}  {d['id']}  "
            label = d.get("label") or "(no label)"
            seam.emit("command", prefix + label[:max(10, HELP_WIDTH - len(prefix))])
        seam.emit("command", "\n" + SS.register_list_footer(len(docs), "/issue-list"))

    _list_or_record(rest, "/issue-list", listing,
                    lambda n: SS.register_record_show(docs, n, S_.ORDER, verb="/issue-list"))


def command_issue_status_all() -> None:
    """`/issue-status` with NO issue named — the property construct (R261)
    read over every issue on file: "nNNNN  <status>  <label>", sorted.
    2026-08-21 (B64); until then the bare form printed a
    usage line. Every issue, not only the live ones: a listing of live issues
    that all read "live" would answer nothing."""
    docs = sorted((S_.issue_read(f) for f in S_.issue_nodes_read()), key=lambda d: d["id"])
    if not docs:
        seam.emit("command", "  no issues on file")
        return
    seam.emit("command", f"\n  {len(docs)} issue(s)")
    for i, d in enumerate(docs, start=1):
        prefix = f"  {i:>3}  {d['id']}  {d.get('status', '?'):<8} "
        label = d.get("label") or "(no label)"
        seam.emit("command", prefix + label[:max(10, HELP_WIDTH - len(prefix))])


def command_issue_relationship_list() -> None:
    """`/issue-relationship-list` — every LIVE issue, and under each its
    LIVE relations: "<type> nMMMM  (<status>)  <target label>". Retired
    relations are not listed — issue_prompt_projection.issue_live_edges_read() drops them
    from BLOCK 2 for the same reason, so a listing that showed them would
    show the room something the room cannot see. 2026-08-21
    (B64); "issue"/"issue-relationship", never "node"/
    "edge"/"relation", in what it prints (R279; D60 ruled
    2026-08-21, "edge" becomes "issue-relationship")."""
    by_id = {d["id"]: d for d in (S_.issue_read(f) for f in S_.issue_nodes_read())}
    live = [d for d in by_id.values() if d.get("status") == "live"]
    if not live:
        seam.emit("command", "  no live issues")
        return
    n_rel = 0
    out = [""]
    for d in sorted(live, key=lambda d: d["id"]):
        label = d.get("label") or "(no label)"
        prefix = f"  {d['id']}  "
        out.append(prefix + label[:max(10, HELP_WIDTH - len(prefix))])
        rels = [e for e in d.get("edges", []) if e.get("status") != "retired"]
        if not rels:
            out.append("         (no live issue-relationships)")
        for e in rels:
            n_rel += 1
            tgt = e.get("target", "?")
            tlabel = (by_id.get(tgt, {}).get("label") or "(no label)")
            prefix = f"         {e.get('type', '?')} {tgt}  ({e.get('status', '?')})  "
            out.append(prefix + tlabel[:max(10, HELP_WIDTH - len(prefix))])
    out.insert(1, f"  {len(live)} live issue(s), {n_rel} live issue-relationship(s)")
    seam.emit("command", "\n".join(out))


_ISSUE_ADD_ARG_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|\u201c([^\u201d]*)\u201d')

# THE VERBS WHOSE LINE IS QUOTED STRINGS \u2014 the two _issue_add_args() readers a
# person can reach. A shell consumes the quotes it was given, so `--dev-cmd`
# arrives as bare words; command_args_quote() puts the boundaries back for
# exactly these verbs and no other (`--dev-cmd issue n0002 status` stays bare).
QUOTED_ARG_COMMANDS = frozenset({"/issue-add", "/part-add"})


def command_args_quote(argv: list[str]) -> str:
    """One argv element per quoted string, `"` inside escaped as `\\"` \u2014 the
    line _issue_add_args() reads. The operator, 2026-09-15, after
    `--dev-cmd part-add "<describe>" "<name>"` reached the dialog with the
    name folded into the describe: *"A --dev-cmd should flow through."*"""
    return " ".join('"' + a.replace('"', '\\"') + '"' for a in argv)


def _issue_add_args(rest: str) -> tuple[str, str, str]:
    """`"label" ["description" ["absence"]]` -> the three strings, "" where
    not given. THE FIRST CHARACTER DECIDES: a line that opens with a quote
    is up to three quoted strings (straight or curly — a part types curly,
    Self types straight, the same fold annotations._strip_quotes makes); a line
    that does not is ONE bare label, whole, so a part writing
    `[proposed: /issue-add fear of asking]` is understood. A fourth quoted
    string is ignored rather than refused: the schema has three fields to
    fill and nothing to do with a fourth."""
    s = " ".join(rest.split()).strip()
    if not s:
        return "", "", ""
    if s[0] not in ('"', "\u201c"):
        return s, "", ""
    got = []
    for m in _ISSUE_ADD_ARG_RE.finditer(s):
        got.append((m.group(1) if m.group(1) is not None else m.group(2) or "")
                   .replace('\\"', '"').strip())
        if len(got) == 3:
            break
    got += [""] * (3 - len(got))
    return got[0], got[1], got[2]


def command_issue_add(rest: str, guard=None, *, interactive: bool = True,
                  values: "tuple[str, str, str] | None" = None) -> bool:
    """`/issue-add "label" ["description" ["absence"]]` — open a NEW issue by
    hand. The syntax is the operator's, ruled 2026-08-21 (D58, his
    recommendation approved): three quoted strings, the first required,
    the same quoting /issue-label-update uses.

    COMPLETE -> LIVE, INCOMPLETE -> LEAD. An issue the room can be shown
    needs all three — issue_prompt_projection refuses a live issue without its
    absence clause — so one written with all three is LIVE from the start;
    one missing a description or an absence is a LEAD (L_nNNNN) until it is
    completed. R290 (2026-08-21) retired R001's "evidence is the only thing
    that opens an issue": the gate now admits a live issue with no evidence
    when nobody holds it yet (held_by empty), which is exactly what a
    Self-opened issue is.

    `interactive` — at cmd> a missing string is PROMPTED for on the command
    channel (an empty answer leaves it missing); at PROPOSAL APPROVAL nothing
    is asked — a `[proposed: /issue-add …]` is staged at one circle and ruled
    at another, so what the bracket did not carry stays missing and the row
    opens a lead. vetting passes interactive=False.

    `opened` names the OPEN circle when there is one (`guard` is the loop's,
    with an open time) and TODAY'S DATE otherwise — the gate admits a bare
    ISO date there since R290 (a hand-opened issue has no transcript to
    name). The description_history line records where it came from either
    way.

    UNDER THE DUAL PANE WITH NO CIRCLE the prompts cannot be answered:
    _no_block_read_line() returns "" at once, so the missing strings stay
    missing and a lead is written; the answer says so and names the
    complete form.

    `values` — the three strings ALREADY PARSED, from a caller that asked
    its own questions (initialization.issue_add_dialog(), 2026-08-23, stage
    3): the quoted-string grammar collapses whitespace (`_issue_add_args`
    joins on split), and the dialog composes a multi-paragraph description
    whose paragraph breaks are content. With `values` given, `rest` and the
    interactive prompts are both bypassed — the dialog already asked.

    Returns True only when a file was written — the bool vetting's
    approval rests on, the same contract cmd_issue_property keeps.

    The BODY — the prompts for what is missing, the gate on a copy, the write
    through issue_schema.issue_write, the index regen — is issue_commands.issue_add()
    since 2026-09-03 (cohesion re-homing, stage 6): the issue graph's own code
    opens its own node, and this verb parses and delegates."""
    label, desc, absence = values if values is not None else _issue_add_args(rest)
    if values is not None:
        interactive = False
    return IC.issue_add(label, desc, absence, guard=guard, interactive=interactive)


def command_issue_property(node_id: str, prop: str, rest: list[str]) -> bool:
    """THE PROPERTY CONSTRUCT'S ONE IMPLEMENTATION — R261, 2026-08-20.

    Was `cmd_issue_object(node_id, rest)`, which took the property name as
    `rest[0]` because the verb was `/issue` and the property was an
    argument. The property is IN THE VERB now, so it arrives named.

    True when the named operation actually ran (see cmd_issue_status_op) —
    vetting's issue_status approval flips a proposal to accepted only on
    that answer. The interactive callers ignore it: their user already
    read the refusal on the seam.

    `status` IS STILL THE ONLY PROPERTY, and this refuses any other by
    name rather than pretending to a generality it has not got. What the
    construct buys today is one spelling and one place to add the second
    property to."""
    if not ISSUE_NODE_RE.match(node_id):
        seam.emit("command", f"  {node_id!r} is not an issue id (nNNNN)")
        return False
    if prop != "status":
        seam.emit("command", f"  unknown property {prop!r} for object class "
                  f"'issue'. Known: status")
        return False
    if not rest:
        return command_issue_status_show(node_id) or True
    return command_issue_status_op(node_id, "status", rest)
