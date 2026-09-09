#!/usr/bin/env python3
"""
initialization.py — the first-run dialogs. docs/BNF.md §INITIALIZATION is the
grammar, docs/Initialization.md the design; the rulings are R323-R332
(2026-08-23). Everything the grammar names is here:

    initialization_run()          THE STEP: PART_CONTEXT_DIALOG for every part
                                  with no answer recorded, then
                                  ISSUE_ADD_DIALOG, then one commit of the
                                  paths those writers touched. Holds the four
                                  skips itself (--live, interactive, not
                                  --resume, not --yes).
    PART_CONTEXT_DIALOG(part)     ask a part's declared [context] questions
                                  on the COMMAND channel, validate each answer
                                  per its data_type/data_max, record the
                                  answers through part_roster.part_context_write().
    ISSUE_ADD_DIALOG              the first issue, composed into one
                                  description and written by cmd_issue_add().
    PART_ADD_DIALOG               a new part — NOT an element of the step; it
                                  fires from /part-add typed at cmd>, and
                                  since R483 that is its only trigger (the
                                  CHECKPOINT 2 approval door is shut).
    /part-context-update <part>   the same dialog, PREFILLED with what is
                                  recorded, so an answer can be taken as-is
                                  or edited on the line. Any dev state, any
                                  recorded values (the operator, 2026-08-23).
    /part-context-list [<part>]   the record, read-only.
    /part-context-clear <part>    empty it after "yes", re-arming the trigger.

ONE VALIDATOR FOR EVERY DIALOG — R332, the operator's own
words: *"each member should receive a "data_type" - start with STRING or
NUMERIC_STRING and a "data_max"; ... An empty is always valid, check only
entries. On invalid entry, describe the error and repeat the prompt."* The
caps ride with each question IN THE FILE and are read at call time — *"40
was a starting point and I will hand tune, changed numbers should be
active."*

THE STATEMENTS ONCE PER OPEN — R330: the privacy and
optional statements print with the FIRST dialog of a process and with no
later one. A module flag, not a file; the next process starts fresh.

A QUESTION'S ANSWER IS THE LINE THAT COMES BACK — the dual pane seeds the
cmd> row with the prefill and Enter submits the row (the operator: *"allow
their entry as-is OR their edit on the line"*). A plain terminal cannot seed
a line (seam.read_line's own contract), so the CURRENT VALUE IS ALSO SAID IN
WORDS on the channel and an EMPTY line KEEPS it on both surfaces — which is
what Enter on an untouched prefilled row returns too. To CLEAR an answer type
`-` alone (Claude's addition, so the terminal can clear ONE answer;
/part-context-clear empties a part's whole record). At a first-run dialog
nothing is recorded, so empty means skip, as ruled.

NEVER A NAME INTO A PROMPT — R329. This module writes
answers; what renders is prompt_build.part_identity_tail_render()'s business, and a
question without a `render` string has no path there.

UNIQUE KEYS ARE REFUSED AT ENTRY — the operator, 2026-08-23: *"Duplicates of
any UNIQUE KEY member (e.g. part name "Soul", issue id "n0001") must be
detected and rejected, echo error and loop at the prompt."* A question
declares `unique_in` (part_roster.UNIQUE_SPACES) and initialization_validate() refuses an answer
already in that space. The home role's preferred_name (the IFS group's Soul, group.toml
[identity], R468) declares part_tags: it feeds
identity.user_name_read(), which part_roster.part_verify() treats as Self's reserved name,
so a part's Tag there would refuse every later open.
"""

from __future__ import annotations

import pathlib

try:
    import tomllib
except ModuleNotFoundError:                                  # 3.10 and older
    import tomli as tomllib                                  # type: ignore

import part_roster as R
import seam
import phase_clock as PC   # stream_timed_read — a prompt is human time, and the
                           # heartbeat must not spin at someone typing

HERE = pathlib.Path(__file__).resolve().parent
STATEMENTS_PATH = HERE / "initialization.toml"

CLEAR_TOKEN = "-"

# Printed by the FIRST dialog of this process, never again in it.
_statements_shown = False


def initialization_statements_read() -> dict[str, str]:
    """The four policy statements, read from initialization.toml at call
    time with {provider}/{model} filled from the transport."""
    import llm_client as LC
    doc = tomllib.loads(STATEMENTS_PATH.read_text(encoding="utf-8"))
    st = dict(doc["statements"])
    st["privacy"] = (st["privacy"].replace("{provider}", LC.PROVIDER)
                     .replace("{model}", LC.MODEL))
    return st


def initialization_statements_reset() -> None:
    """For a probe: the next dialog prints the two statements again."""
    global _statements_shown
    _statements_shown = False


# ------------------------------------------------------------------ validation
# THE GATE KINDS — ruled 2026-08-28. A field the MECHANISM acts on must say
# HOW it is made valid; a field only a model reads need not, because a model
# reads around a typo and the looseness is part of the point. Where a field is
# both, the mechanism's rule governs.
#
#   ONE_OF        a closed list, checked at entry        `values`
#   BOUNDED       a number in a range, at entry          `minimum` / `maximum`
#   UNIQUE_IN     refused against a LIVE set             `unique_in`
#   CHECK_AT_USE  no local set exists — the first real use IS the check, and
#                 it must fail loudly and name the value
#
# THE FOURTH IS AN IMPERATIVE, AND THE OTHER THREE ARE NOT — the operator,
# 2026-08-28, naming it. The first three say what the value must BE; this one
# says WHEN to look, so it reads as an instruction to the checker rather than
# a description of the value.
#
# IT WAS `AT_USE` FOR A DAY AND THE NAME FAILED ON FIRST CONTACT. Read beside
# the ordinary English "IN_USE", it looks like a STATE — present, not yet
# consumed — which is a different concept entirely from the timing it labels.
# A name whose plain reading is not the thing it names is a name to change
# while changing it is cheap.
#
# CHECK_AT_USE EXISTS TO BE UNCOMFORTABLE. The model id is the case: what is
# valid is whatever that account can reach, which changes without this code
# changing, so a closed list here would refuse a model that works. Declaring
# it makes "we cannot check this here" look different from "nobody checked",
# which is the whole reason to write it down.
#
# AND IT PUTS THE JUDGEMENT WITH THE CONSUMER, which is where it belongs —
# the operator, 2026-08-28: *"when to look = 'at the user's gate' places
# reasonability where it ought to be, with the consumer. Unreasonability is
# conveyed to the command pane."*
#
# So CHECK_AT_USE carries TWO obligations, not one, and the second is the
# half that is easy to skip:
#
#   THE CONSUMER JUDGES.  Only the thing that uses the value can say whether
#                         it is reasonable. Nothing upstream may pretend to.
#   AND SAYS SO, IN THE   A failure reaches the COMMAND PANE as a sentence a
#   COMMAND PANE.         person can act on, naming the value that was
#                         refused — never a traceback, never a silent
#                         fallback to something nobody chose.
#
# The model honours both today: llm_client.stream_api_preflight() makes one real
# call before anything at all is written, and circle.py emits the provider's
# own explanation to "command" and returns 2 — "Nothing was written — no
# transcript, no working-set entry." A CHECK_AT_USE field whose failure
# reached only a log would satisfy the first obligation and fail the one that
# matters to the person sitting there.
# GATES, BOUND_RULES AND resolve_bound LIVE IN part_roster.py, NOT HERE — read as
# R.GATES / R.BOUND_RULES / R.part_bound_resolve at the use. They were briefly
# declared in both files (a few hours on 2026-08-28), then re-exported here
# as module aliases until 2026-09-03; a name in two files is one fact in two
# homes, which is the defect this project records more than any other. roster
# is the leaf this module already imports, so that direction closes no cycle.


def initialization_advice_render(question: dict, answer: str, today=None) -> "str | None":
    """A note to SHOW rather than a refusal — or None. Ruled 2026-08-28:
    someone reporting an age under fifteen is told, gracefully, that circles
    with other people would serve them better, AND IS NOT BLOCKED.

    A LIMIT THAT CAN ONLY BE PASSED BY LYING PROTECTS NOBODY. Refusing here
    would teach a fourteen-year-old to enter a false year and then proceed on
    it — a corrupted record AND the suggestion unheeded. So the advisory bound
    accepts the true answer, says the true thing once, and lets them decide.

    Kept clear of the crisis line in process_core.md on purpose: those are
    different things, and being fourteen is not a crisis."""
    if answer == "" or question.get("data_type") != "NUMERIC_STRING":
        return None
    t = answer.strip()
    if not R.part_context_is_whole_number(t):
        return None
    hi = R.part_bound_resolve(question.get("advisory_maximum"), today)
    if hi is None or int(t) <= hi:
        return None
    return question.get("advisory_note") or ""


def initialization_validate(question: dict, answer: str, *, part: str = "") -> str | None:
    """None when `answer` is acceptable for `question`, else one line saying
    what was wrong — the line the dialog prints before asking again.

    The ruling, exactly: empty is always valid; STRING is at most data_max
    characters; NUMERIC_STRING is numerals only (a positive whole number)
    and at most data_max as a number. UNIQUENESS, the operator's second rule
    the same day — *"Duplicates of any UNIQUE KEY member (e.g. part name
    "Soul", issue id "n0001") must be detected and rejected, echo error and
    loop at the prompt"* — a question declaring `unique_in` is refused an
    answer already in that space (case-insensitive): part_tags is every
    live Tag and alt_tag; issue_ids and issue_labels read issues/. Plus one
    of Claude's, named in docs/Initialization.md §3.6: no square bracket in
    a STRING (the annotation grammar — a part quoting its own BLOCK 3 back
    into the room would stage a bracket nobody wrote)."""
    # THE PURE CHECKS ARE part_roster.part_context_value_verify's — one validator, shared with
    # the settings register and with provider tuning. What stays here is the
    # part that needs LIVE data: uniqueness against the roster or the issue
    # graph, which a leaf module has no business reading.
    why = R.part_context_value_verify(question, answer)
    if why is not None:
        return why
    if answer == "":
        return None
    space = question.get("unique_in")
    if space and answer.strip().lower() in {v.lower() for v in initialization_unique_values_read(space)}:
        return (f"  {answer.strip()!r} is already "
                + {"part_tags": "a part's name", "issue_ids": "an issue's id",
                   "issue_labels": "an issue's name"}[space]
                + " — choose another")
    return None


def initialization_unique_values_read(space: str) -> set[str]:
    """Every value already taken in a unique space, read fresh: part_tags is
    the roster's live Tags and alt_tags (re-scanned, not the import-time
    copy — a part added this process counts); issue_ids / issue_labels read
    issues/ through issue_schema, and read as empty if memory/ is not
    importable (a probe outside the tree)."""
    if space == "part_tags":
        roster, alt, _tails, _probs = R.part_scan()
        return {t for _d, t in roster} | set(alt)
    if space in ("issue_ids", "issue_labels"):
        try:
            import sys
            mem = str(R.ROOT / "memory")
            if mem not in sys.path:
                sys.path.insert(0, mem)
            import issue_schema as S                                 # noqa: E402
            docs = [S.issue_read(f) for f in S.issue_nodes_read()]
        except Exception:                                           # noqa: BLE001
            return set()
        key = "id" if space == "issue_ids" else "label"
        return {str(d.get(key) or "") for d in docs} - {""}
    return set()


# ------------------------------------------------------------------ the dialog
def part_context_dialog(part: str, *, prefill: bool = False,
                        base: pathlib.Path | None = None) -> str:
    """PART_CONTEXT_DIALOG(part). Returns "completed" (something written),
    "skipped" (nothing was, and nothing had been), "unchanged" (prefilled
    and every answer kept), or "none" (the part declares no usable
    [context] — said on the channel).

    `prefill` is the /part-context-update form: each question opens with
    its recorded answer already on the line (dual pane) and said in words
    (every surface); an empty line keeps it, `-` clears it. Without
    prefill — the first-run form — an empty line skips the question.

    Every read is one seam.read_line() on the COMMAND channel, the prompt
    being the numbered question, so in the dual pane it rides the cmd>
    input row and in a terminal input() prints it. An INVALID line is
    answered with one line saying why and the SAME question, until valid
    or empty — no limit, as ruled."""
    global _statements_shown
    ctx = R.part_context_read(part, base)
    tag = R.TAG_BY_DIR.get(part, part)
    if ctx is None or not ctx["questions"]:
        seam.emit("command", f"  {tag} ({part}) declares no context questions — "
                             f"nothing to ask. (parts/{part}/part.toml [context])")
        return "none"
    st = initialization_statements_read()
    seam.emit("command", "")
    if ctx["purpose"]:
        seam.emit("command", ctx["purpose"])
    if not _statements_shown:
        seam.emit("command", st["privacy"])
        seam.emit("command", st["optional"])
        _statements_shown = True
    if prefill:
        seam.emit("command", f"  (Enter keeps what is recorded; type {CLEAR_TOKEN} "
                             f"alone to clear an answer)")
    qs, recorded = ctx["questions"], ctx["answers"]
    new: dict[str, str] = {}
    for i, q in enumerate(qs, 1):
        current = recorded.get(q["key"], "") if prefill else ""
        prompt = f"{i}/{len(qs)} {q['ask']}? "
        if prefill and current:
            seam.emit("command", f"  {i}/{len(qs)} current: {current}")
        while True:
            try:
                raw = PC.stream_timed_read(seam.read_line, prompt, channel="command",
                                     prefill=current).strip()
            except (EOFError, KeyboardInterrupt):
                seam.emit("command", "  (cancelled — nothing recorded)")
                return "skipped"
            if prefill and raw == "":
                raw = current                   # Enter keeps — both surfaces
            elif raw == CLEAR_TOKEN:
                raw = ""
            why = initialization_validate(q, raw, part=part)
            if why is None:
                # ACCEPTED, AND THE THRESHOLD MAY STILL SPEAK — ruled
                # 2026-08-28. An advisory bound does not refuse; it says the
                # true thing once and the person decides. Shown AFTER the
                # answer is accepted, so it reads as a suggestion rather than
                # an error, which is the whole difference.
                note = initialization_advice_render(q, raw)
                if note:
                    seam.emit("command", "")
                    for _ln in note.splitlines():
                        seam.emit("command", "  " + _ln)
                    seam.emit("command", "")
                break
            seam.emit("command", why)
        new[q["key"]] = raw
    if prefill:
        if new == {k: recorded.get(k, "") for k in new}:
            seam.emit("command", "  unchanged.")
            return "unchanged"
    elif not any(new.values()):
        seam.emit("command", st["skipped"])
        return "skipped"
    # THE SAVE IS ANNOUNCED, AND IT IS NOT WHERE THE TIME GOES — the operator,
    # 2026-09-09, reading a live open: *"there is a lengthy delay between these
    # lines '6/6 Did you make much music or art? drawing, singing / Your answers
    # have been recorded.'"* Nothing between the last answer and the completion
    # said anything, so the wait read as a hang at the moment a first-time user
    # has just given the most personal answers in the dialog.
    #
    # MEASURED AFTERWARDS, n=20: part_context_write is 0.0000s median — this
    # notice renders and closes inside a millisecond. The minutes are in
    # _commit() at the tail of initialization_run(), where the pre-commit hook
    # fires 52 subprocesses (57s measured, one suite 24.8s of it), and THAT is
    # announced separately at its own site. The line stays because a save that
    # says nothing is still wrong when it is fast, and because a slow disk would
    # make it earn its place; it is no longer described as the lengthy part.
    #
    # SAME LINE, BY HIS OWN SHAPE: the notice, then "done." appended to it. A
    # standalone terminal honours `end=""`; the two-pane UI drops end= and
    # flush= by design (CircleEngine._emit — they have no meaning for a
    # line-based pane's scrollback), so there it reads as two lines. Both are
    # true, neither is silent, and that is the whole requirement here.
    # NO HELPER YET, DELIBERATELY. His second sentence rules a GENERAL rule —
    # any gap over three seconds gets a progress indication where there is a
    # clock to watch it — and that mechanism belongs at the seam, where all
    # three windows can interpret it, with a BNF production to name it. The
    # grammar has no `progress` production today, so naming a public helper for
    # it now would be a spelling ahead of a term (R441). Two plain emits close
    # the case he actually hit; the general mechanism replaces both when it
    # lands, and this comment is how it finds them.
    # AND IT IS THE OUTCOME, NOT AN EXTRA LINE. The completion statement used
    # to follow — "Your answers are being processed... done." then "Your
    # answers have been recorded." — and the operator read the pair as one
    # thing said twice: *"do not emit redundant statements... Just the first
    # one."* So `st["completion"]` is no longer printed here; "done." IS the
    # dialog's completion, and the grammar says so (OUTCOME, docs/BNF.md).
    # The SKIPPED path is untouched: nothing is saved there, so it has no
    # progress line to end and its own statement is still the only thing that
    # tells a reader the dialog closed.
    seam.emit("command", "  Your answers are being processed... ",
              end="", flush=True)
    R.part_context_write(part, new, base)
    seam.emit("command", "done.")
    return "completed"


# ------------------------------------------------------------------ the issue dialog
def issue_questions() -> dict:
    """The [issue] table of initialization.toml — purpose and questions,
    read at call time (R332: a hand-tuned cap is active at once)."""
    doc = tomllib.loads(STATEMENTS_PATH.read_text(encoding="utf-8"))
    return doc.get("issue", {"purpose": "", "questions": []})


def issue_dialog_due() -> bool:
    """R324: ISSUE_ADD_DIALOG fires at a circle start while issues/ holds no
    node OF ANY STATUS — once one exists, first-run's invitation has done
    its job and /issue-add and a part's proposal are the ongoing paths."""
    import sys
    mem = str(R.ROOT / "memory")
    if mem not in sys.path:
        sys.path.insert(0, mem)
    import issue_schema as S
    return not S.issue_nodes_read()


def _ask(qs: list[dict], *, seeds: "dict[str, str] | None" = None,
         part: str = "") -> "dict[str, str] | None":
    """The one asking loop every dialog shares: the numbered question on the
    COMMAND channel, validated per its own row, described-and-re-asked on
    invalid, until valid or empty. `seeds` are prefilled values (R323 — a
    bracket's strings arrive on the line): Enter keeps a seed, `-` clears
    it; with no seed, Enter skips. None = cancelled (Ctrl-C/EOF), said."""
    seeds = seeds or {}
    answers: dict[str, str] = {}
    for i, q in enumerate(qs, 1):
        seed = (seeds.get(q["key"]) or "").strip()
        prompt = f"{i}/{len(qs)} {q['ask']}? "
        if seed:
            seam.emit("command", f"  {i}/{len(qs)} proposed: {seed}")
        while True:
            try:
                raw = PC.stream_timed_read(seam.read_line, prompt, channel="command",
                                     prefill=seed).strip()
            except (EOFError, KeyboardInterrupt):
                seam.emit("command", "  (cancelled — nothing recorded)")
                return None
            if seed and raw == "":
                raw = seed
            elif raw == CLEAR_TOKEN:
                raw = ""
            why = initialization_validate(q, raw, part=part)
            if why is None:
                # ACCEPTED, AND THE THRESHOLD MAY STILL SPEAK — ruled
                # 2026-08-28. An advisory bound does not refuse; it says the
                # true thing once and the person decides. Shown AFTER the
                # answer is accepted, so it reads as a suggestion rather than
                # an error, which is the whole difference.
                note = initialization_advice_render(q, raw)
                if note:
                    seam.emit("command", "")
                    for _ln in note.splitlines():
                        seam.emit("command", "  " + _ln)
                    seam.emit("command", "")
                break
            seam.emit("command", why)
        answers[q["key"]] = raw
    return answers


def issue_add_dialog(*, guard=None, write=None,
                     seeds: "dict[str, str] | None" = None) -> str:
    """ISSUE_ADD_DIALOG — R324 (once, no loop), R328 (six questions: the
    ask's four compose the description; a short name and an absence clause
    make the issue LIVE rather than a LEAD no circle projects), R330 (the
    statements print only if no dialog printed them this open), R332 (the
    validator). Returns "completed" or "skipped".

    An empty label with a non-empty description is DERIVED — its first six
    words — because a lead with a good description is better than a skipped
    issue; an empty absence opens a LEAD and cmd_issue_add() says so. Every
    answer empty: nothing written, the skipped statement, ask again next
    open.

    `write` is the writer, (label, desc, absence) -> bool; the default is
    commands.command_issue_add(values=...) — the same gate-before-write path
    the verb has. A probe passes a capture."""
    global _statements_shown
    spec = issue_questions()
    qs = spec.get("questions", [])
    if not qs:
        seam.emit("command", "  (initialization.toml declares no issue "
                             "questions — nothing to ask)")
        return "skipped"
    st = initialization_statements_read()
    seam.emit("command", "")
    if spec.get("purpose"):
        seam.emit("command", spec["purpose"])
    if not _statements_shown:
        seam.emit("command", st["privacy"])
        seam.emit("command", st["optional"])
        _statements_shown = True
    answers = _ask(qs, seeds=seeds)
    if answers is None:
        return "skipped"
    if not any(answers.values()):
        seam.emit("command", st["skipped"])
        return "skipped"
    label = answers.get("label", "")
    desc = _compose_description(answers)
    if not label and desc:
        label = " ".join(desc.split()[:6])
    if write is None:
        def write(lab, d, a):
            import commands as CMD
            return CMD.command_issue_add("", guard=guard, values=(lab, d, a))
    ok = write(label, desc, answers.get("absence", ""))
    if ok and not answers.get("absence", ""):
        seam.emit("command", "  (it reaches a circle once its absence clause "
                             "is written — /issue-add, or a hand edit)")
    return "completed" if ok else "skipped"


def _compose_description(answers: dict[str, str]) -> str:
    """The ask's four answers, in the fixed shape docs/Initialization.md
    §3.4 rules — nothing typed is lost and no schema field is invented.
    Unanswered lines are simply absent."""
    parts = []
    if answers.get("describe"):
        parts.append(answers["describe"])
    facts = []
    if answers.get("triggers"):
        facts.append(f"Triggers: {answers['triggers']}")
    if answers.get("body_place"):
        facts.append(f"Felt in the body: {answers['body_place']}")
    if answers.get("recovery_hours"):
        facts.append(f"At its worst, about {answers['recovery_hours']} hours "
                     f"to get over it.")
    if facts:
        parts.append("\n".join(facts))
    return "\n\n".join(parts)


# ------------------------------------------------------------------ the part dialog
def part_questions() -> dict:
    """The [part] table of initialization.toml — purpose and two questions,
    read at call time."""
    doc = tomllib.loads(STATEMENTS_PATH.read_text(encoding="utf-8"))
    return doc.get("part", {"purpose": "", "questions": []})


def part_add_dialog(*, seeds: "dict[str, str] | None" = None,
                    write=None) -> str:
    """PART_ADD_DIALOG — R324 (never at a circle start; /part-add typed bare is
    the only trigger since R483 took the verb out of PROPOSE_SUBSET_COMMANDS,
    so no `[proposed: /part-add ...]` can be staged to approve),
    R323 (the bracket's strings arrive prefilled — Enter keeps, typing
    edits; kept for the shut door, see proposal_vetting.py), R332 (the validator;
    part_add.part_precheck() then holds the roster
    rules). Returns "completed" or "skipped" — skipped at approval leaves
    the proposal PENDING (vetting reads the outcome).

    The directory name DERIVES from the part's name; only when the
    derivation collides or empties is one asked for — an end user is never
    asked for a directory name unprompted (§8). `write` is
    part_add.part_add by default; a probe passes a capture."""
    global _statements_shown
    spec = part_questions()
    qs = spec.get("questions", [])
    if not qs:
        seam.emit("command", "  (initialization.toml declares no part "
                             "questions — nothing to ask)")
        return "skipped"
    st = initialization_statements_read()
    seam.emit("command", "")
    if spec.get("purpose"):
        seam.emit("command", spec["purpose"])
    if not _statements_shown:
        seam.emit("command", st["privacy"])
        seam.emit("command", st["optional"])
        _statements_shown = True
    answers = _ask(qs, seeds=seeds)
    if answers is None:
        return "skipped"
    describe = answers.get("describe", "")
    tag = answers.get("part_name", "")
    if not describe and not tag:
        seam.emit("command", st["skipped"])
        return "skipped"
    import part_add as PA
    if write is None:
        write = PA.part_add
    while True:
        name = PA.part_name_derive(tag) if tag else ""
        # THE MISSING HALF IS ASKED FOR, not refused — the same move the
        # context dialog makes; empty twice running abandons the add.
        if not tag:
            try:
                tag = PC.stream_timed_read(seam.read_line, "  the part needs a name — what should "
                                     "it be called? ", channel="command").strip()
            except (EOFError, KeyboardInterrupt):
                tag = ""
            if not tag:
                seam.emit("command", st["skipped"])
                return "skipped"
            continue
        if not describe:
            try:
                describe = PC.stream_timed_read(seam.read_line, 
                    f"  describe {tag} (up to 40 words): ",
                    channel="command").strip()
            except (EOFError, KeyboardInterrupt):
                describe = ""
            if not describe:
                seam.emit("command", st["skipped"])
                return "skipped"
        if name and not (R.PARTS_DIR / name).exists():
            pass
        else:
            try:
                name = PC.stream_timed_read(seam.read_line, 
                    f"  directory name for {tag} (letters, digits, "
                    f"underscore): ", channel="command").strip()
            except (EOFError, KeyboardInterrupt):
                seam.emit("command", st["skipped"])
                return "skipped"
        ok, msg = write(name, tag, describe)
        seam.emit("command", f"  {msg}")
        if ok:
            return "completed"
        # described, and the SAME questions again with what was typed kept —
        # the ruled echo-and-loop, one level up (the refusal may be about
        # the tag, the name or the description; ask the pair again seeded).
        answers = _ask(qs, seeds={"describe": describe, "part_name": tag})
        if answers is None or not any(answers.values()):
            seam.emit("command", st["skipped"])
            return "skipped"
        describe, tag = answers.get("describe", ""), answers.get("part_name", "")


# ------------------------------------------------------------------ the step
def initialization_pending_dialogs_read(base: pathlib.Path | None = None) -> list[str]:
    """The parts whose PART_CONTEXT_DIALOG is due: a declared [context]
    with at least one question and EVERY answer empty (R331 — the trigger
    is "no particulars recorded yet", read from the record). Ordered: the group's own
    initialization head first (group.toml `initialization`, R468 — for the IFS group that is
    Soul, then Child, the order R324 spoke them in), then any other declaring part in roster
    order."""
    due = []
    roster, _alt, _tails, _probs = R.part_scan(base)
    for d, _t in roster:
        ctx = R.part_context_read(d, base)
        if ctx and ctx["questions"] and not any(ctx["answers"].values()):
            due.append(d)
    head = [d for d in initialization_head_read() if d in due]
    return head + [d for d in due if d not in head]


def initialization_head_read() -> list[str]:
    """The roles whose first-run dialogs come first — the bound group's group.toml
    `initialization` list (R468, B120). Empty for a group that declares none; the dialogs then
    run in roster order."""
    import record_paths as _RP
    return [str(d) for d in _RP.group_descriptor_read(_RP.group_read()).get("initialization", [])]


def initialization_run(*, live: bool, resume: bool, yes: bool) -> list[str]:
    """The INITIALIZATION step of a circle open — R330: between CHECKPOINT 2
    and the working-set question, COMMAND channel, focus handed to the command
    pane for its duration and back after "Starting your circle...". Returns
    the paths it wrote (for the caller's record); [] when nothing fired.

    THE FOUR SKIPS (docs/Initialization.md §2): not --live (sandbox writes
    nothing under parts/ or issues/, and every headless harness runs there);
    --resume (the circle's prompts are already warmed); --yes (an unattended
    run has nobody to answer); and no interactive surface — seam.read_line
    still the plain-terminal default with stdin not a TTY. Silent skips,
    all four: the open looks exactly as it did before this step existed.

    THE COMMIT — §4.4: nothing at cmd> commits, but this is the one
    open-time step that writes the record, so it commits what it wrote,
    once, its own paths only, non-fatal, the circle_commit() manner."""
    import sys
    if not live or resume or yes:
        return []
    if seam.read_line.__module__ == "seam" and not sys.stdin.isatty():
        return []
    due_parts = initialization_pending_dialogs_read()
    due_issue = issue_dialog_due()
    if not due_parts and not due_issue:
        return []
    seam.emit("state", "initializing")
    written: list[str] = []
    for part in due_parts:
        if part_context_dialog(part) == "completed":
            written.append(str(R.PARTS_DIR / part / R.MARKER))
    if due_issue:
        import issue_schema as S     # issue_dialog_due() put memory/ on the path
        before = set(S.issue_nodes_read())
        issue_add_dialog()
        new_nodes = sorted(set(S.issue_nodes_read()) - before)
        written += [str(p) for p in new_nodes]
        if new_nodes and (S.ISSUES / "INDEX.md").is_file():
            written.append(str(S.ISSUES / "INDEX.md"))   # regenerated with the write
    seam.emit("command", "")
    # THE COMMIT COMES FIRST NOW, AND IT SAYS SO. Measured 2026-09-09: this
    # commit takes 57 SECONDS on a first-run open — one path written, but that
    # path matches five PRE_COMMIT case arms and fires 52 subprocesses, of which
    # test_inter_circle.py alone is 24.8s. It ran AFTER "Starting your circle..."
    # and in silence, so the operator was told the circle was starting and then
    # watched a blank screen for a minute. Saying "Starting your circle..." over
    # a minute of work that is not the circle starting is the wrong order as
    # well as the wrong silence, so the handover line now follows the work it
    # was covering.
    if written:
        seam.emit("command", "  saving your answers to the record — this runs "
                             "the project's own checks and can take a minute:")
        _commit(written)
    seam.emit("command", "")
    seam.emit("command", "Starting your circle...")
    seam.emit("state", "initialized")
    seam.emit("state", "")          # the engine keeps the last token; clear it
    return written


def _commit(paths: list[str]) -> None:
    """One commit for the step's own writes, own paths only, non-fatal —
    git is the rollback target, not part of the open (circle_commit()'s
    words). The message names what moved, never the answers."""
    try:
        import gitrepo as G
    except ImportError:
        return
    import datetime
    import pathlib as _pl
    names = []
    for p in paths:
        rel = _pl.Path(p)
        if rel.name == "INDEX.md":
            continue                       # regenerated alongside a node write
        if rel.parent.parent.name == "parts":
            names.append(f"{rel.parent.name} context")
        else:
            names.append("+" + rel.stem.removeprefix("L_"))
    marks = {"ok": "  ", "did": "  ", "warn": "  ", "note": "  ", "fail": "  !! "}

    def log(kind, msg):
        seam.emit("command", f"{marks.get(kind, '  ')}{msg}")

    try:
        G.system_git_paths_commit([_pl.Path(p) for p in paths],
                       f"initialization {datetime.date.today().isoformat()}: "
                       + ", ".join(names), log)
    except Exception as e:                                      # noqa: BLE001
        seam.emit("command", f"  (initialization commit failed — {e}; the "
                             f"answers are safe on disk, commit by hand)")


# ------------------------------------------------------------------ the verbs
# cmd_part_context_update / _list / _clear and cmd_part_add MOVED to
# commands.py, 2026-09-03 (cohesion re-homing, stage 5): every cmd> verb
# lives there (the stage-0 rule) and delegates to the dialogs above.
# _resolve_part stays — the dialogs' own <part> resolver, which the verbs
# reach as INIT._resolve_part.

def _resolve_part(word: str) -> "str | None":
    """A typed <part> — directory name or Tag, case-insensitive — to the
    directory, or None."""
    part = R.DIR_BY_TAG.get(word) or R.DIR_BY_TAG_ALL.get(word)
    if part is None:
        by_lower = {d.lower(): d for d in R.DIR_NAMES}
        by_lower.update({t.lower(): d for d, t in R.TAG_BY_DIR.items()})
        part = by_lower.get(word.lower())
    return part
