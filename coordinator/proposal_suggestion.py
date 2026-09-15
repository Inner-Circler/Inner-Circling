#!/usr/bin/env python3
"""
proposal_suggestion.py — run a staged SUGGESTION when Self approves it, and report the truth.

    import proposal_suggestion as PS
    PS.proposal_suggestion_execute(row)          (ok, msg) — ok only when the act really ran
    PS.proposal_suggestion_validate(row)         what approval would do, for a sandbox
    PS.proposal_suggestion_placeholders_read(text)
    PS.proposal_suggestion_is_runnable(head)
    PS.SUGGESTION_HEADS

A SUGGESTION is a <proposal> row of kind "suggestion": a line the coordinator itself staged —
a recognised action from the close-time report (R569), or a step of a dependency plan a removal
verb could not take yet (R570, 2026-09-15). It is NOT a part's proposal: the
classifier that decides what a part may name (annotations._propose_command_shape, R483) is not
asked, because no part asked. Its approval runs the verb through that verb's own writer.

TRUTHFUL EXECUTION IS THE WHOLE CONTRACT. The vetting loop's own history is the reason: until
2026-08-19 a row flipped to accepted when its command had not run. So each verb here returns ok
only on its writer's own success signal — an (ok, msg) where the writer gives one, the bool the
issue status write returns, a record returned, or, where a handler returns nothing, the state
read back after (a part's retired.toml present, its context answers empty). Anything else, and
anything raised, is (False, why) and the row stays pending. A line still holding a placeholder
(nNNNN, TP-nnnn, <n> ...) is never run: its prior has not filled it.

R483 STANDS HERE TOO: a /part-add suggestion runs only when Self is among its sources.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "memory"))

import command_surface as CS                                        # noqa: E402
import phase_clock as PC                                            # noqa: E402
import seam                                                         # noqa: E402

# A placeholder the recogniser or a plan leaves for a prior to fill: nNNNN / nMMMM (an issue id
# not yet known), TP-nnnn, BP-nnnn, CO-nnnn, and <n> / <id> style tokens. A real id — n0042 —
# never matches.
PLACEHOLDER_RE = re.compile(r"(?<![\w-])(n[A-Z]{4}|TP-n{4}|BP-n{4}|CO-n{4}|<[a-z_]+>)(?![\w-])")


def _fail(why: str) -> tuple[bool, str]:
    return False, f"not applied — {why} (stays pending)"


# ------------------------------------------------------------------ the issue graph
def _run_issue_ruling(head: str, rest: str, row: dict) -> tuple[bool, str]:
    """The four issue rulings: parse, precheck against the graph as it stands, apply — the
    path a typed ruling takes at close. A typed /issue-evidence-add names a statement of the
    circle the row was staged in, resolved against that transcript as circle.py resolves it."""
    import issue_commands as IC
    import proposal_manager as PR
    import proposal_vetting as VT
    circle = PR.circle_ref(row.get("circle", ""))
    cmd, why = IC.issue_command_parse(f"{head} {rest}", circle)
    if cmd is None:
        return _fail(why)
    if cmd["verb"] == "issue-evidence-add":
        if not circle:
            return _fail("an evidence-add names a statement, and this row records no circle")
        import commands as CMD
        import record_paths as _RP
        import transcript_store as TS
        path = _RP.record_dir(_RP.ROOT, "circles") / f"{circle}.md"
        if not path.is_file():
            return _fail(f"the circle it names, {circle}, has no transcript here")
        _ot, _topic, transcript = TS.circle_transcript_parse(path.read_text(encoding="utf-8"))
        entry, why3 = CMD.statement_resolve(transcript, cmd["stmt"])
        if entry is None:
            return _fail(why3)
        cmd.update(part=entry["speaker"], quote=entry["text"], source=circle)
    why2 = IC.issue_precheck(cmd, VT.issue_graph_now_read())
    if why2:
        return _fail(why2)
    ok, msg = IC.issue_command_apply([cmd])
    return (True, msg) if ok else _fail(msg)


def _run_issue_status(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import commands as CMD
    tok = rest.replace("=", " = ").split()
    if not tok:
        return _fail("no issue named")
    node, vals = tok[0], [t for t in tok[1:] if t != "="]
    if not vals:
        return _fail(f"no status value for {node}")
    # plan=False: this approval is itself a plan's final step; it never stages again.
    if CMD.command_issue_status_set(node, vals[0], ["--yes"], plan=False):
        return True, f"{node} is now {vals[0]}"
    return _fail(f"the status write for {node} did not run")


def _run_issue_add(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import commands as CMD
    label, desc, absence = CMD._issue_add_args(rest)
    if not label:
        return _fail("an issue-add needs a label")
    if CMD.command_issue_add("", values=(label, desc, absence)):
        return True, f"issue \"{label}\" opened"
    return _fail("the issue was not written")


# ------------------------------------------------------------------ practices
def _run_practice_add(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import commands as CMD
    fn = CMD.command_practice_add if head == "/practice-add" else CMD.command_better_option_add
    ok, msg = fn(rest)
    return (True, msg) if ok else _fail(msg)


def _practice_position(tok: str) -> tuple[int | None, str]:
    """A practice named by its stable BP- id (what staging writes) or a list number (a hand
    edit), resolved to /practice-list's position NOW — positions shift, ids do not."""
    import practice_manager as PM
    rows = [p for p in PM.practice_read() if p.get("addressee") != PM.BETTER_OPTION_ADDRESSEE]
    if tok.upper().startswith("BP-"):
        for n, p in enumerate(rows, 1):
            if p.get("id") == tok.upper():
                return n, p["id"]
        return None, f"{tok} is not on /practice-list"
    if tok.isdecimal() and 1 <= int(tok) <= len(rows):
        return int(tok), rows[int(tok) - 1].get("id", "")
    return None, f"{tok} is not a practice id or list number"


def _run_practice_delete(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import practice_manager as PM
    tok = rest.split()[0] if rest.split() else ""
    n, why = _practice_position(tok)
    if n is None:
        return _fail(why)
    ok, msg = PM.practice_delete(n)
    return (True, msg) if ok else _fail(msg)


def _run_practice_update(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import practice_manager as PM
    parts = rest.split(None, 1)
    if len(parts) < 2:
        return _fail("a practice-update needs the practice and its new wording")
    n, why = _practice_position(parts[0])
    if n is None:
        return _fail(why)
    ok, msg = PM.practice_update(n, parts[1])
    return (True, msg) if ok else _fail(msg)


# ------------------------------------------------------------------ Self's own registers
def _run_remember(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import commands as CMD
    import remember_manager as RM
    body = " ".join(rest.split())
    if not body:
        return _fail("nothing to remember")
    rec = RM.remember_add(RM.SELF, CMD._NoCircleGuard(), body)
    return True, f"remembered — {rec['text'][:56]}"


def _run_observation_add(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import circle_observation_manager as CO
    rec = CO.circle_observation_manual_add(rest)
    return True, f"{rec.get('id', 'observation')} added"


def _run_observation_continue(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import circle_observation_manager as CO
    parts = rest.split(None, 1)
    if len(parts) < 2:
        return _fail("an observation-continue needs the id and the text")
    rec = CO.circle_observation_continue_add(parts[0].upper(), parts[1])
    return True, f"{rec.get('id', 'observation')} added, continuing {parts[0].upper()}"


def _run_observation_retire(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import circle_observation_manager as CO
    tid = rest.split()[0].upper() if rest.split() else ""
    if not tid:
        return _fail("no observation named")
    CO.circle_observation_retire_now(tid)
    return True, f"{tid} retired — hidden, kept"


def _run_observation_purge(head: str, rest: str, row: dict) -> tuple[bool, str]:
    """Irreversible in the live file, so the verb's own confirmation is kept at approval:
    the id typed again. The approval alone is not enough for this one."""
    import circle_observation_manager as CO
    a = rest.split()
    if len(a) != 2 or a[0].upper() != a[1].upper():
        return _fail("an observation-purge names the same id twice")
    tid = a[0].upper()
    got = PC.stream_timed_read(seam.read_line, f"        purging {tid}'s text cannot be undone in "
                                               f"the live file — type {tid} to purge it now: ",
                               channel="command").strip().upper()
    if got != tid:
        return _fail("the purge was not confirmed")
    CO.circle_observation_purge_now(tid)
    return True, f"{tid} purged — its text is gone from the live file"


def _run_topic_close(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import topic_manager as TOP
    tid = rest.split()[0].upper() if rest.split() else ""
    ok, msg = TOP.topic_close(tid)
    return (True, msg) if ok else _fail(msg)


def _run_topic_update(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import topic_manager as TOP
    parts = rest.split(None, 1)
    if len(parts) < 2:
        return _fail("a topic-update needs the id and the new text")
    ok, msg = TOP.topic_update(parts[0].upper(), parts[1])
    return (True, msg) if ok else _fail(msg)


# ------------------------------------------------------------------ parts
def _run_part_context_update(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import initialization as INIT
    word = rest.split()[0] if rest.split() else ""
    part = INIT._resolve_part(word) if word else None
    if part is None:
        return _fail(f"no part named {word!r}")
    out = INIT.part_context_dialog(part, prefill=True)
    if out in ("completed", "unchanged"):
        return True, f"{part}'s context questions asked again ({out})"
    return _fail(f"the context dialog recorded nothing ({out})")


def _run_part_context_clear(head: str, rest: str, row: dict) -> tuple[bool, str]:
    import commands as CMD
    import initialization as INIT
    import part_roster as R
    word = rest.split()[0] if rest.split() else ""
    part = INIT._resolve_part(word) if word else None
    ctx = R.part_context_read(part) if part else None
    if not ctx or not any(ctx["answers"].values()):
        return _fail(f"{word or 'that part'} has no recorded answers to clear")
    CMD.command_part_context_clear(part)
    after = R.part_context_read(part)
    if after and not any(after["answers"].values()):
        return True, f"{part}'s recorded answers cleared"
    return _fail("the answers were not cleared")


def _run_part_add(head: str, rest: str, row: dict) -> tuple[bool, str]:
    if "Self" not in row.get("sources", []):
        return _fail("adding a part is Self's alone (R483), and Self did not say this")
    import commands as CMD
    import initialization as INIT
    describe, tag, _extra = CMD._issue_add_args(rest)
    seeds = {k: v for k, v in (("describe", describe), ("part_name", tag)) if v}
    if INIT.part_add_dialog(seeds=seeds or None) == "completed":
        return True, f"{tag or 'the part'} added — it joins from the next circle"
    return _fail("the part dialog recorded nothing")


def _run_part_retire(head: str, rest: str, row: dict) -> tuple[bool, str]:
    """By directory or Tag (what staging writes) or list number, resolved to /part-list's
    number now; ok when retired.toml is there afterwards — part_retire() returns nothing, and
    refuses while a circle may be open, which leaves the row pending for the next open."""
    import part_add as PA
    import part_roster as R
    tok = rest.split()[0] if rest.split() else ""
    rows = PA.part_rows_read()
    hit = None
    for n, (d, t) in enumerate(rows, 1):
        if tok.lower() in (d.lower(), t.lower()) or (tok.isdecimal() and int(tok) == n):
            hit = (n, d, t)
            break
    if hit is None:
        return _fail(f"no seated part {tok!r}")
    n, d, t = hit
    PA.part_retire(str(n))
    if (R.PARTS_DIR / d / R.RETIRED_MARKER).is_file():
        return True, f"{t} retired — its record stays"
    return _fail(f"{t} was not retired")


_EXECUTORS = {
    "/issue-label-update": _run_issue_ruling,
    "/issue-relationship-add": _run_issue_ruling,
    "/issue-evidence-add": _run_issue_ruling,
    "/issue-relationship-status": _run_issue_ruling,
    "/issue-status": _run_issue_status,
    "/issue-add": _run_issue_add,
    "/practice-add": _run_practice_add,
    "/better-option-add": _run_practice_add,
    "/practice-delete": _run_practice_delete,
    "/practice-update": _run_practice_update,
    "/remember": _run_remember,
    "/observation-add": _run_observation_add,
    "/observation-continue": _run_observation_continue,
    "/observation-retire": _run_observation_retire,
    "/observation-purge": _run_observation_purge,
    "/part-context-update": _run_part_context_update,
    "/part-context-clear": _run_part_context_clear,
    "/part-add": _run_part_add,
    "/part-retire": _run_part_retire,
    "/topic-close": _run_topic_close,
    "/topic-update": _run_topic_update,
}
SUGGESTION_HEADS: tuple[str, ...] = tuple(_EXECUTORS)


# ------------------------------------------------------------------ the doors
def _split(text: str) -> tuple[str, str]:
    t = text.strip()
    word, _sep, rest = t.partition(" ")
    return CS.command_head_normalise("/" + word.lstrip("/")), rest.strip()


def proposal_suggestion_placeholders_read(text: str) -> list[str]:
    return PLACEHOLDER_RE.findall(text or "")


def proposal_suggestion_is_runnable(head: str) -> bool:
    return CS.command_head_normalise(head) in _EXECUTORS


def proposal_suggestion_execute(row: dict) -> tuple[bool, str]:
    """(ok, msg). ok only when the verb's own writer reports the act done; the caller flips
    the row to accepted only then. Never raises."""
    head, rest = _split(str(row.get("text", "")))
    unfilled = proposal_suggestion_placeholders_read(row.get("text", ""))
    if unfilled:
        return _fail(f"{', '.join(unfilled)} still unfilled — its prior has not produced it")
    fn = _EXECUTORS.get(head)
    if fn is None:
        return _fail(f"{head} is not a verb a staged suggestion runs")
    try:
        return fn(head, rest, row)
    except Exception as e:                                       # noqa: BLE001
        return _fail(f"{type(e).__name__}: {e}")


def proposal_suggestion_validate(row: dict) -> str:
    """What approval would do — for a sandbox checkpoint, which rules nothing."""
    head, _rest = _split(str(row.get("text", "")))
    unfilled = proposal_suggestion_placeholders_read(row.get("text", ""))
    if unfilled:
        return f"would wait — {', '.join(unfilled)} still unfilled"
    if head not in _EXECUTORS:
        return f"would fail — {head} is not a verb a staged suggestion runs"
    return f"would run {head} at approval, reporting whether it really ran"
