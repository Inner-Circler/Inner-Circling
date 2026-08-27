#!/usr/bin/env python3
"""
commands.py — the command-pane verbs' implementations and their one
dispatcher: the statements numbering (/issue-evidence-list and what
`/issue-evidence-add` resolves against), the ic.py-era dev commands
(topic/practice/prompt-show/issue-apply/issue-status), _run_captured,
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

import pathlib
import re
import subprocess
import sys

import issue_schema as S_
import seam
import transcript_store as TS      # withheld(): recorded, never in the room
from command_surface import ISSUE_NODE_RE
from help_system import cmd_help, HELP_WIDTH
from paths import ROOT


# -------------------------------------------------------------- statements
# MARK (Self's ratification of a statement) was RETIRED WHOLESALE 2026-08-14,
# code included — see docs/BNF.md. statements()/resolve_statement() below
# survive: they are the generic 1-based statement numbering `/issue
# issue-evidence-add` resolves against, not mark-specific.

def statements(transcript: list[dict]) -> list[tuple[int, dict]]:
    """Indexed speakable turns — scribe notes are not addressable.

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
            if e["speaker"] != "__scribe__" and not TS.withheld(e)]


def resolve_statement(transcript: list[dict], n: int) -> tuple[dict | None, str]:
    """The SAME 1-based numbering `/issue-evidence-list` prints, resolved to the
    actual transcript entry. `/issue-evidence-add` is the caller — `n` is
    not a stored id, it is a position in the list AS IT WOULD PRINT RIGHT
    NOW, same discipline as HELP_DESIGN.md's `/help <class> read #`."""
    stmts = statements(transcript)
    if n < 1 or n > len(stmts):
        return None, f"no statement #{n} — /issue-evidence-list shows 1-{len(stmts)}"
    _, e = stmts[n - 1]
    return e, ""


def show_statements(transcript: list[dict]) -> None:
    """The numbered listing `/issue-evidence-add nNNNN <stmt#>` addresses
    into — kept mark-free after MARK's 2026-08-14 retirement (docs/BNF.md);
    issue-evidence-add has no other way to discover a statement's number.

    2026-08-16: `e['text']` can carry embedded newlines (a dry-run part's
    canned multi-section statement, e.g.) — whitespace collapsed before
    truncating so this is genuinely ONE line per entry, never several;
    truncation length matched to the fixed prefix so the whole line stays
    within the 80 column max (RULED 2026-08-16)."""
    prefix_width = len(f"  {'':3}. {'':<12} ")
    budget = HELP_WIDTH - prefix_width
    for n, (i, e) in enumerate(statements(transcript), 1):
        flat = " ".join(e["text"].split())
        seam.emit("command", f"  {n:3}. {e['display']:<12} {flat[:budget]}")


# THE ANNOTATION GRAMMAR LIVES IN markers.py, AND THIS IS ITS HISTORY. The
# block below was written 2026-08-04 and left here when phase 2 moved the
# grammar out from under it; it ends mid-sentence. Every bracket it spells —
# `[propose nNNNN leads-to nMMMM]`, `[request ...]`, `[hold]`, the six
# `[proposed practice ...]` forms — is DIALOG TEXT since R273 (2026-08-20).
# The two annotations that exist are `[remember: <text>]` and
# `[proposed: <command>]`; docs/BNF.md's ANNOTATION production is the record
# and markers.ASK_KEYWORDS is the code. Kept for WHY markers exist at all —
# the measurement in the third paragraph — which is still true.
#
# What a part may ASK FOR, in a form that cannot be misread. Ruled 2026-08-04.
#
# Three markers, one mechanism: the part signals, the coordinator collects, and
# THE OPERATOR RULES. R048 and "no part statement creates or retires an issue" are both
# untouched — a marker changes who SEES the ask, never who acts on it.
#
#   [propose nNNNN leads-to nMMMM]  a relation, named structurally   (then)
#   [request ...]                   anything else, in the part's own words   (then)
#
# WHY MARKERS RATHER THAN INFERENCE. Measured on circle_2026-08-04_1243: a
# syntactic scan for the arrow notation would have caught 2 of the 6 actions
# that circle actually produced, and 0 of 60 statements in the two circles
# before it carried an arrow at all. The rename, the retraction, the better
# option and a part's question were all prose. Inference would have to READ
# for intent, which is a machine producing claims about a room — the shape that
# made 8 of 11 nodes still say NOT YET RULED.
#
# A marker asks the part to say what it means. That is cheaper, exact, and it
# is the same lesson as `this same descent` being ambiguous: when a thing must
# be acted on, prose is the wrong carrier.
#
# FAILS OPEN. A missed marker costs nothing — Self has the transcript.
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
# transcript: apply_remember() strips it at the point every statement is
# appended, before route_markers() (or anything else) ever sees the text —


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


def cmd_prompt_show(who: str) -> None:
    import prompt_show as PS
    seam.emit("command", PS.render(who))


def cmd_remember_list(rest: str) -> None:
    """/remember-list — the Self half of docs/BNF.md's REMEMBER_PROJECTION,
    built 2026-08-18 (R224) as /recall, designed 2026-08-14. RENAMED
    2026-08-21 when the operator named the register's verbs (/remember writes,
    /remember-list reads; "\"recall\" is a synonym") — /recall still
    arrives here, through command_surface.normalise_head()'s SYNONYMS.

    READ-ONLY, AND SELF'S OWN REGISTER ONLY. `remember.SELF` is passed
    explicitly and no argument can change it: a part's remember is private
    to that part, so the one thing this command must never grow is a
    `<part>` form. The argument is a record number and nothing else.

    NO CIRCLE NEEDED — it reads self/remember.toml off disk, which is why
    it sits in dispatch_dev_cmd() with the rest of the always-available
    verbs rather than in the Self> loop."""
    import remember as RM
    a = rest.strip()
    if not a:
        seam.emit("command", RM.recall_listing(RM.SELF))
        return
    if not a.isdigit():
        seam.emit("command", "  usage: /remember-list [<n>]  (also /recall) "
                             "— bare lists them")
        return
    seam.emit("command", RM.recall_record(int(a), RM.SELF))


# The name the verb carried from R224 to 2026-08-21; kept callable so the
# probes written against it (test_remember) and any reader of the BNF's own
# RECALL production find the function where they were told it lives.
cmd_recall = cmd_remember_list


class _NoCircleGuard:
    """The write guard a no-circle /remember uses: Self's own register, the
    real tree, and no open time — which is what makes the one-per-circle
    rule not apply (there is no circle to be one of). Duck-typed to what
    remember.path_for()/has_remembered() read: `.live`, `.ot`, `.check()`.
    WriteGuard itself admits self/remember.toml by exact path, so this
    delegates the check to it rather than re-stating the allow-list."""
    live = True
    ot = ""

    def check(self, p):
        from write_guard import WriteGuard
        return WriteGuard(live=True, open_time="").check(p)


def cmd_remember(text: str, guard=None) -> None:
    """/remember <text> — Self's own private note, from the COMMAND pane.
    2026-08-21, B64: the same record `[remember: ...]`
    typed at the circle prompt writes (markers.apply_self_remember ->
    remember.add(remember.SELF, ...)), reachable without a circle.

    THE CAP FOLLOWS THE CIRCLE. Inside one (`guard` is the loop's own, with
    an open time) the one-per-circle rule applies exactly as it does to the
    annotation — has_remembered() reads the register back off disk, so a
    bracket and a command in the same circle share the one use. With no
    circle there is nothing to be one of: _NoCircleGuard carries no open
    time and the cap is not consulted. Empty text is a usage line, never a
    record — apply_self_remember's "malformed costs nothing" rule."""
    import remember as RM
    body = " ".join(text.split())
    if not body:
        seam.emit("command", "  usage: /remember <text>")
        return
    g = guard if guard is not None else _NoCircleGuard()
    if g.ot and RM.has_remembered(RM.SELF, g):
        seam.emit("command", "  second REMEMBER this circle — not written "
                             "(one per circle, the same rule the annotation "
                             "keeps)")
        return
    rec = RM.add(RM.SELF, g, body)
    where = RM.path_for(RM.SELF, g)
    seam.emit("command", f"  remembered — {rec['text'][:56]}"
                         f"{'…' if len(rec['text']) > 56 else ''}")
    seam.emit("command", f"  ({where.name} under {where.parent.name}/"
                         + (", this circle" if g.ot else ", no circle open")
                         + ")")


def cmd_topic_list() -> None:
    """The TOPIC register (coordinator/topics.py) — open TP- topics with
    their window, and the tombstone tally."""
    import topics as TOP
    seam.emit("command", TOP.listing())


def cmd_topic_close(rest: str) -> None:
    """Self's disposition on one topic. IMMEDIATE, /practice-add's own
    contract: written the moment it is ruled, /abort does not undo it,
    and a SANDBOX circle's /topic-close still writes the LIVE register —
    the ruling is Self's own, whichever tree the circle writes to."""
    import topics as TOP
    tid = rest.split()[0] if rest.split() else ""
    if not tid:
        seam.emit("command", "  usage: /topic-close TP-nnnn")
        return
    _ok, msg = TOP.close(tid)
    seam.emit("command", f"  {msg}")


def cmd_practice_list() -> None:
    """The CIRCLE's practices — every row not addressed to Self. Until
    2026-08-21 this printed the whole register; the rows addressed to Self
    are /better-option-list's now (the operator: "add a path for
    /better-option-list and make it always visible"), each list numbered on
    its own. A row addressed to ONE part (narrowcast) is still the circle's,
    and stays here."""
    import check_best_practices as BPX
    seam.emit("command", BPX.listing(better_options=False))


def cmd_better_option_list() -> None:
    """/better-option-list — how SELF moves: the rows of the one register
    (R133) addressed to Self, numbered on their own. Minted 2026-08-21; a
    USER verb, always visible, while /better-option-add is DEV for now."""
    import check_best_practices as BPX
    seam.emit("command", BPX.listing(better_options=True))


def cmd_propose_add(rest: str, *, record=None, guard=None) -> None:
    """/propose-add <command> — stage a proposal YOURSELF, from the command
    pane: the same register, vetting and checkpoint ruling a part's
    [proposed: <command>] reaches (R350, the operator,
    2026-08-25). Bare `propose` is an alias (SYNONYMS). The body meets the
    IDENTICAL test the annotation meets — markers' _propose_command_shape —
    so there is one grammar, not two, the same argument _add_practice_row
    makes one register over.

    A SANDBOX CIRCLE REFUSES IT: stage_propose_proposals() already rules
    that "a sandbox circle's proposal is a draft, not something to stage
    into the live self/proposals.toml" (R202), and this door writes the
    same live register. No circle at all is fine — the row is ruled at the
    next checkpoint, wherever that falls; `circle` is then "" and the
    author credit is plain "Self"."""
    import markers as MK
    import proposals as PR
    text = rest.strip()
    if not text:
        seam.emit("command", "  usage: /propose-add <command>   (also bare "
                             "propose)")
        seam.emit("command", "  " + MK._proposable_list())
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
            seam.emit("command", "  a dry-run circle's proposal is a draft — "
                                 "not staged into the live register (R202). "
                                 "Type it with no circle open, or in a live "
                                 "circle.")
            return
        ot = getattr(guard, "open_time", "") or ""
    pid = PR.stage("command", text, ["Self"], ot)
    seam.emit("command", f"  staged {pid} — pending your ruling at the next "
                         f"checkpoint (/propose-list shows it)")
    if record is not None:
        record()


def cmd_propose_list() -> None:
    """/propose-list — what is staged: self/proposals.toml's pending rows
    first (what awaits a ruling at the next checkpoint), then the settled,
    then any practice row still staged the pre-R273 way (the register
    vetting still reads). Numbered across the whole listing; no circle
    needed. 2026-08-21."""
    import proposals as PR
    import check_best_practices as BPX
    rows = PR.entries()
    pend = [r for r in rows if r.get("state") == "proposed"]
    settled = [r for r in rows if r.get("state") != "proposed"]
    legacy = BPX.pending()
    if not pend and not settled and not legacy:
        seam.emit("command", "  no proposals on file")
        return
    n = 0

    def row(r: dict, tag: str) -> str:
        nonlocal n
        n += 1
        src = ", ".join(r.get("sources", [])) or "?"
        text = " ".join((r.get("text") or r.get("title") or "").split())
        prefix = f"  {n:>3}  [{r['id']}] {tag} {src} · {r.get('circle', '?')}  "
        return prefix + text[:max(10, HELP_WIDTH - len(prefix))]

    if pend:
        seam.emit("command", f"\n  PENDING ({len(pend)})")
        for r in pend:
            seam.emit("command", row(r, f"({r.get('kind', '?')})"))
    if legacy:
        seam.emit("command", f"\n  PENDING, staged as a practice row ({len(legacy)})")
        for r in legacy:
            seam.emit("command", row(r, f"({r.get('op', '?')})"))
    if settled:
        seam.emit("command", f"\n  SETTLED ({len(settled)})")
        for r in settled:
            seam.emit("command", row(r, f"({r.get('state', '?')})"))


def cmd_practice_delete(arg: str, record=None) -> None:
    import check_best_practices as BPX
    a = arg.strip()
    if not a.isdigit():
        seam.emit("command", "  usage: /practice-delete <n>  — the number "
                             "/practice-list showed (not /better-option-list's)")
        return
    ok, msg = BPX.delete(int(a))
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()


def _add_practice_row(text: str, addressee: str, usage: str,
                       record=None) -> tuple[bool, str]:
    """The write behind /practice-add and /better-option-add.

    ONE REGISTER, TWO ADDRESSEES (R133): both write
    self/best_practices.toml and differ in `addressee` alone — "All parts"
    is how the CIRCLE behaves, "Self" is how SELF moves. They are two VERBS
    rather than one verb with a flag because the two read entirely
    differently to whoever is addressed, and because a proposal names a
    verb; they are ONE BODY because check_best_practices.add()'s own
    docstring makes exactly this argument one layer down, and a near-copy
    here would be the second place for the shape to drift.

    THE USAGE LINE IS THE VERB'S, NOT THE REGISTER'S. add() refuses an
    empty body neutrally; naming the command is a decision this module
    owns, the same way cmd_practice_delete and cmd_topic_close own
    theirs.

    RETURNS (ok, msg), B62 2026-08-23 — until then this returned nothing
    and a caller could only ever know the head was recognised, never
    whether the write actually happened. `_propose_approve()`'s dev_cmd
    branch is the one that needed it: see vetting.py."""
    import check_best_practices as BPX
    if not " ".join(text.split()).strip():
        msg = f"usage: {usage}"
        seam.emit("command", f"  {msg}")
        return False, msg
    ok, msg = BPX.add(text, addressee=addressee)
    seam.emit("command", f"  {msg}")
    if ok and record is not None:
        record()
    return ok, msg


def cmd_better_option_add(text: str, record=None) -> tuple[bool, str]:
    """A row addressed to Self — how SELF moves, not how the circle behaves.

    IT EXISTS SO THE ANNOTATION GRAMMAR COULD SHRINK (R270). Until it did,
    the only way to propose one was `[proposed better_option: ...]`, one of
    six bracket spellings; with a command behind it, `[proposed:
    /better-option-add ...]` says the same thing through the one form the
    grammar collapsed to."""
    import check_best_practices as BPX
    return _add_practice_row(text, BPX.BETTER_OPTION_ADDRESSEE,
                      "/better-option-add <how Self moves>", record)


def cmd_practice_add(text: str, record=None) -> tuple[bool, str]:
    import check_best_practices as BPX
    return _add_practice_row(text, BPX.PRACTICE_ADDRESSEE,
                      "/practice-add <your practice statement>", record)


# ISSUE_NODE_RE MOVED to command_surface.py, 2026-08-16 (phase 2 stage
# 0) — shared by the marker grammar's issue_status classification and
# the /issue command forms; imported at the top of this file.


def _run_captured(argv: list[str]) -> tuple[str, int]:
    r = subprocess.run([sys.executable] + argv, cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout + r.stderr).rstrip("\n"), r.returncode


def cmd_issue_apply(rest: list[str]) -> None:
    if not rest:
        seam.emit("command", "  usage: /issue-apply <commands.toml>")
        return
    out, _ = _run_captured(["memory/issue_commands.py"] + rest)
    if out:
        seam.emit("command", out)


def cmd_issue_status_show(node_id: str) -> None:
    for p in S_.nodes():
        doc = S_.load(p)
        if doc["id"] == node_id:
            seam.emit("command", f"  {node_id}: {doc['status']}")
            return
    seam.emit("command", f"  no such issue: {node_id}")


def cmd_issue_status_set(node_id: str, val: str, trailing: list[str]) -> bool:
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

    out, rc = _run_captured(["memory/issue_status.py", node_id,
                             "--to", val, "--dry-run"] + trailing)
    if out:
        seam.emit("command", out)
    if rc != 0:
        return False                    # refused — no effect, nothing to confirm

    if not yes:
        answer = seam.read_line("  type 'yes' to apply: ").strip().lower()
        if answer != "yes":
            seam.emit("command", "  cancelled — no change made")
            return False

    # rc2 was DISCARDED until 2026-08-19 (`out2, _ = ...`), so a real
    # apply that failed after a clean dry-run — the exact window the
    # issue_status regen-chain bug lived in — fell through as success.
    out2, rc2 = _run_captured(["memory/issue_status.py", node_id,
                               "--to", val] + trailing)
    if out2:
        seam.emit("command", out2)
    if rc2 != 0:
        seam.emit("command", f"  the apply itself FAILED (exit {rc2}) — "
                             f"see the output above")
        return False
    return True


def cmd_issue_status_op(node_id: str, op_raw: str, trailing: list[str]) -> bool:
    """True when the operation ran: a show always did; a set only when
    cmd_issue_status_set() reports the real apply succeeded."""
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
        return cmd_issue_status_set(node_id, val, trailing)
    cmd_issue_status_show(node_id)
    return True


def dispatch_dev_cmd(head: str, rest_text: str, *, record=None,
                     guard=None,
                     interactive: bool = True) -> bool:
    """The always-available verb surface (RULED 2026-08-13, Q1) — ONE
    dispatcher, THREE doors since B61 (2026-08-21): circle.py's own
    `--dev-cmd` CLI flag (the direct ic.py replacement — a bare shell
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
    if head == "/help":
        cmd_help(rest_text)
    elif head == "/practice-add":
        cmd_practice_add(rest_text, record=record)
    elif head == "/practice-list":
        cmd_practice_list()
    elif head == "/practice-delete":
        cmd_practice_delete(rest_text, record=record)
    elif head == "/better-option-add":
        cmd_better_option_add(rest_text, record=record)
    elif head == "/remember-list":
        # READ-ONLY, and Self's OWN register only (R224). Nothing is
        # written and nothing reaches the room, so there is no record
        # step and no live/sandbox split to make. /recall arrives here
        # too — normalise_head() maps the old name (2026-08-21).
        cmd_remember_list(rest_text)
    elif head == "/remember":
        # WRITES Self's own register — the command-pane twin of the
        # [remember: ...] annotation, 2026-08-21. No transcript step: a
        # remember is private by definition (REMEMBER's blast-radius rule).
        cmd_remember(rest_text, guard=guard)
    elif head == "/better-option-list":
        cmd_better_option_list()
    elif head == "/propose-list":
        cmd_propose_list()
    elif head == "/propose-add":
        # WRITES the live proposals register (a pending row, ruled at the
        # next checkpoint) — bare `propose` arrives here too, via SYNONYMS.
        cmd_propose_add(rest_text, record=record, guard=guard)
    elif head == "/issue-relationship-list":
        cmd_issue_relationship_list()
    elif head == "/issue-add":
        cmd_issue_add(rest_text, guard=guard, interactive=interactive)
    elif head == "/part-context-update":
        # PART_CONTEXT_DIALOG, prefilled — docs/Initialization.md §6,
        # 2026-08-23. Asks on the COMMAND lane, so it needs a surface that
        # can answer: `interactive` False (the dual pane's no-circle door)
        # is refused with where it works. A circle open (`guard`) means its
        # BLOCK 3 was built before this write — said, effective next circle.
        import initialization as INIT
        INIT.cmd_part_context_update(rest_text, guard=guard,
                                     interactive=interactive)
    elif head == "/part-context-list":
        import initialization as INIT
        INIT.cmd_part_context_list(rest_text)
    elif head == "/part-context-clear":
        import initialization as INIT
        INIT.cmd_part_context_clear(rest_text, interactive=interactive)
    elif head == "/part-add":
        # PART_ADD_DIALOG, the typed door — stage 5, 2026-08-23. The two
        # quoted strings (describe, Tag — the taught bracket's own order)
        # arrive prefilled when given; bare opens the dialog cold.
        import initialization as INIT
        INIT.cmd_part_add(rest_text, guard=guard, interactive=interactive)
    elif head == "/part-list":
        import part_add as PA
        seam.emit("command", PA.listing())
    elif head == "/part-view":
        import part_add as PA
        _ok, text = PA.view(rest_text)
        seam.emit("command", text if _ok else f"  {text}")
    elif head == "/part-delete":
        import part_add as PA
        PA.delete(rest_text)
    elif head == "/topic-list":
        cmd_topic_list()
    elif head == "/topic-close":
        # IMMEDIATE, same contract as /practice-add — the docstring on
        # cmd_topic_close() carries the sandbox note.
        cmd_topic_close(rest_text)
    elif head == "/prompt-show":
        who = rest_text.split()[0] if rest_text.split() else "circle"
        cmd_prompt_show(who)
    elif head == "/issue-apply":
        cmd_issue_apply(rest_text.split())
    elif head == "/issue-list":
        cmd_issue_list()
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
                cmd_issue_status_all()
            else:
                seam.emit("command", f"  usage: {head} nNNNN <value>")
            return True
        rest = tok[1:]
        if head == "/issue-status-update":
            # The synonym's argument IS the value; hand the reader the
            # `=` form it already knows rather than a second parser.
            rest = ["="] + rest
        cmd_issue_property(tok[0], "status", rest)
    else:
        return False
    return True


def cmd_issue_list() -> None:
    """`/issue-list` — the issues, numbered. R261/B59, 2026-08-20.

    NEW WITH THE REGRAMMAR, and it is not a rename of anything: there was
    no command that answered "what is in the graph" at all. `/help issue
    list` answered it from the help hierarchy, which is a different
    surface with a different audience.

    "issue", never "node", in what it prints — R279,
    2026-08-21; and it counts what it lists: EVERY issue on file, with the
    live ones counted beside, where it used to say "live node(s)" over a
    listing that included the leads, roots and the settled."""
    docs = [S_.load(f) for f in S_.nodes()]
    rows = [(d["id"], d.get("label") or "(no label)") for d in docs]
    if not rows:
        seam.emit("command", "  no issues on file")
        return
    n_live = sum(1 for d in docs if d.get("status") == "live")
    seam.emit("command", f"\n  {len(rows)} issue(s), {n_live} live")
    for i, (nid, label) in enumerate(sorted(rows), start=1):
        prefix = f"  {i:>3}  {nid}  "
        seam.emit("command", prefix + label[:max(10, HELP_WIDTH - len(prefix))])


def cmd_issue_status_all() -> None:
    """`/issue-status` with NO issue named — the property construct (R261)
    read over every issue on file: "nNNNN  <status>  <label>", sorted.
    2026-08-21 (B64); until then the bare form printed a
    usage line. Every issue, not only the live ones: a listing of live issues
    that all read "live" would answer nothing."""
    docs = sorted((S_.load(f) for f in S_.nodes()), key=lambda d: d["id"])
    if not docs:
        seam.emit("command", "  no issues on file")
        return
    seam.emit("command", f"\n  {len(docs)} issue(s)")
    for i, d in enumerate(docs, start=1):
        prefix = f"  {i:>3}  {d['id']}  {d.get('status', '?'):<8} "
        label = d.get("label") or "(no label)"
        seam.emit("command", prefix + label[:max(10, HELP_WIDTH - len(prefix))])


def cmd_issue_relationship_list() -> None:
    """`/issue-relationship-list` — every LIVE issue, and under each its
    LIVE relations: "<type> nMMMM  (<status>)  <target label>". Retired
    relations are not listed — issue_projection.live_edges() drops them
    from BLOCK 2 for the same reason, so a listing that showed them would
    show the room something the room cannot see. 2026-08-21
    (B64); "issue"/"issue-relationship", never "node"/
    "edge"/"relation", in what it prints (R279; D60 ruled
    2026-08-21, "edge" becomes "issue-relationship")."""
    by_id = {d["id"]: d for d in (S_.load(f) for f in S_.nodes())}
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


def _next_issue_id() -> str:
    """The next nNNNN — one past the largest on file, every status counted
    (a retired or settled issue keeps its id; R143's never-reuse rule, which
    the graph has always followed by filename)."""
    top = 0
    for p in S_.nodes():
        try:
            top = max(top, int(S_.nid_of(p.stem)[1:]))
        except ValueError:
            continue
    return f"n{top + 1:04d}"


_ISSUE_ADD_ARG_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|\u201c([^\u201d]*)\u201d')


def _issue_add_args(rest: str) -> tuple[str, str, str]:
    """`"label" ["description" ["absence"]]` -> the three strings, "" where
    not given. THE FIRST CHARACTER DECIDES: a line that opens with a quote
    is up to three quoted strings (straight or curly — a part types curly,
    Self types straight, the same fold markers._strip_quotes makes); a line
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


ISSUE_ADD_USAGE = ('/issue-add "label" ["description" ["absence"]]')


def cmd_issue_add(rest: str, guard=None, *, interactive: bool = True,
                  values: "tuple[str, str, str] | None" = None) -> bool:
    """`/issue-add "label" ["description" ["absence"]]` — open a NEW issue by
    hand. The syntax is the operator's, ruled 2026-08-21 (D58, his
    recommendation approved): three quoted strings, the first required,
    the same quoting /issue-label-update uses.

    COMPLETE -> LIVE, INCOMPLETE -> LEAD. An issue the room can be shown
    needs all three — issue_projection refuses a live issue without its
    absence clause — so one written with all three is LIVE from the start;
    one missing a description or an absence is a LEAD (L_nNNNN) until it is
    completed. R290 (2026-08-21) retired R001's "evidence is the only thing
    that opens an issue": the gate now admits a live issue with no evidence
    when nobody holds it yet (held_by empty), which is exactly what a
    Self-opened issue is.

    `interactive` — at cmd> a missing string is PROMPTED for on the command
    lane (an empty answer leaves it missing); at PROPOSAL APPROVAL nothing
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
    approval rests on, the same contract cmd_issue_property keeps."""
    import datetime
    import shutil
    import tempfile

    label, desc, absence = values if values is not None else _issue_add_args(rest)
    if values is not None:
        interactive = False
    if not label:
        seam.emit("command", f"  usage: {ISSUE_ADD_USAGE}  — the label is "
                             f"required; a missing description or absence is "
                             f"asked for at cmd>, and an issue missing either "
                             f"is written as a LEAD")
        return False
    if interactive and not desc:
        desc = seam.read_line("  description (what the issue IS; Enter to "
                              "leave it for later): ").strip()
    if interactive and not absence:
        absence = seam.read_line("  absence (what its ABSENCE looks like; Enter "
                                 "to leave it for later): ").strip()
    complete = bool(desc and absence)
    status = "live" if complete else "lead"
    nid = _next_issue_id()
    today = datetime.date.today().isoformat()
    if guard is not None and getattr(guard, "ot", ""):
        ref = f"{'circle' if guard.live else 'sandbox'}_{guard.ot}"
        opened = f"{ref} (Self, /issue-add)"
        where = f"in {ref}"
    else:
        opened, where = today, f"on {today} (no circle open)"
    missing = [k for k, v in (("description", desc), ("absence", absence)) if not v]
    doc = {
        "id": nid, "label": label, "status": status, "opened": opened,
        "held_by": [], "description": desc, "absence": absence,
        "description_history": (
            f"- **{today}** — opened by Self via /issue-add {where}; "
            + ("first formulation, above. Live from the start (R290): nobody "
               "holds it yet, and a circle may attach evidence."
               if complete else
               f"a LEAD until its {' and '.join(missing)} "
               f"{'is' if len(missing) == 1 else 'are'} written.")),
    }
    target = S_.path_for(nid, status)
    fails = S_.check(doc, target)
    if fails:
        seam.emit("command", "  refused — the schema: " + "; ".join(fails))
        return False
    # THE GATE, ON A COPY. issue_gate.py takes the issues directory as its
    # one argument (argv[1]); the candidate is written beside a copy of the
    # graph and the gate reads both. Nothing touches issues/ until it says
    # PASS.
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="issue_add_"))
    try:
        for p in S_.ISSUES.glob("*.toml"):
            shutil.copy2(p, tmp / p.name)
        S_.save(tmp / target.name, doc)
        out, rc = _run_captured(["memory/issue_gate.py", str(tmp)])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if rc != 0:
        bad = [l for l in out.splitlines() if "FAIL" in l or target.name in l]
        seam.emit("command", "  refused by the gate — nothing written:")
        for l in bad[:12]:
            seam.emit("command", f"    {l.strip()}")
        return False
    S_.save(target, doc)
    if complete:
        seam.emit("command", f"  wrote issues/{target.name} — {nid} is LIVE "
                             f"(nobody holds it yet)")
    else:
        seam.emit("command", f"  wrote issues/{target.name} — {nid} is a LEAD: "
                             f"its {' and '.join(missing)} "
                             f"{'is' if len(missing) == 1 else 'are'} still "
                             f"to be written. The complete form: "
                             f"{ISSUE_ADD_USAGE}")
    # The index, as issue_status.py's own regen chain does after a write —
    # ONLY against the real issues/: issue_index.py reads the schema's own
    # ISSUES, not an argument, so with S_.ISSUES re-pointed (a probe on a
    # temp copy) it would rebuild the real index over a copy's write.
    if S_.ISSUES.resolve() != (ROOT / "issues").resolve():
        return True
    out2, rc2 = _run_captured(["memory/issue_index.py"])
    tail = out2.strip().splitlines()[-1:] if out2.strip() else []
    for l in tail:
        seam.emit("command", f"  {l.strip()}")
    if rc2 != 0:
        seam.emit("command", "  (issue_index.py FAILED — the issue is on disk; "
                             "`git checkout issues/INDEX.md` reverts the index)")
    return True


def cmd_issue_property(node_id: str, prop: str, rest: list[str]) -> bool:
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
        return cmd_issue_status_show(node_id) or True
    return cmd_issue_status_op(node_id, "status", rest)
