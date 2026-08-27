#!/usr/bin/env python3
"""
initialization.py — the first-run dialogs. docs/Initialization.md is the
design; the rulings are R323-R332 (2026-08-23). Built in stages; this file
holds what has landed:

    PART_CONTEXT_DIALOG(part)     ask a part's declared [context] questions
                                  on the COMMAND lane, validate each answer
                                  per its data_type/data_max, record the
                                  answers through roster.write_context().
    /part-context-update <part>   the same dialog, PREFILLED with what is
                                  recorded, so an answer can be taken as-is
                                  or edited on the line. Any dev state, any
                                  recorded values (the operator, 2026-08-23).

NOT HERE YET: the circle-start step (PART_CONTEXT_DIALOG for every part with
no answer recorded, then ISSUE_ADD_DIALOG — design §2, stage 2), the issue
and part dialogs (stages 3, 5-6), /part-context-list and -clear (stage 4).

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
`-` alone (Claude's addition, so the terminal can clear at all; the designed
/part-context-clear is not built yet). At a first-run dialog nothing is
recorded, so empty means skip, as ruled.

NEVER A NAME INTO A PROMPT — R329. This module writes
answers; what renders is prompt_build.identity_tail()'s business, and a
question without a `render` string has no path there.

UNIQUE KEYS ARE REFUSED AT ENTRY — the operator, 2026-08-23: *"Duplicates of
any UNIQUE KEY member (e.g. part name "Soul", issue id "n0001") must be
detected and rejected, echo error and loop at the prompt."* A question
declares `unique_in` (roster.UNIQUE_SPACES) and validate() refuses an answer
already in that space. The Soul's preferred_name declares part_tags: it feeds
identity.user_name(), which roster.verify() treats as Self's reserved name,
so a part's Tag there would refuse every later open.
"""

from __future__ import annotations

import pathlib

try:
    import tomllib
except ModuleNotFoundError:                                  # 3.10 and older
    import tomli as tomllib                                  # type: ignore

import roster as R
import seam

HERE = pathlib.Path(__file__).resolve().parent
STATEMENTS_PATH = HERE / "initialization.toml"

CLEAR_TOKEN = "-"

# Printed by the FIRST dialog of this process, never again in it.
_statements_shown = False


def statements() -> dict[str, str]:
    """The four policy statements, read from initialization.toml at call
    time with {provider}/{model} filled from the transport."""
    import llm_client as LC
    doc = tomllib.loads(STATEMENTS_PATH.read_text(encoding="utf-8"))
    st = dict(doc["statements"])
    st["privacy"] = (st["privacy"].replace("{provider}", LC.PROVIDER)
                     .replace("{model}", LC.MODEL))
    return st


def reset_statements_shown() -> None:
    """For a probe: the next dialog prints the two statements again."""
    global _statements_shown
    _statements_shown = False


# ------------------------------------------------------------------ validation
def validate(question: dict, answer: str, *, part: str = "") -> str | None:
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
    if answer == "":
        return None
    dt, dm = question["data_type"], int(question["data_max"])
    if dt == "NUMERIC_STRING":
        if not answer.isdigit() or not answer.isascii():
            return "  a number is needed here — whole, positive, numerals only"
        if int(answer) > dm:
            return f"  too large — at most {dm}"
    else:
        if len(answer) > dm:
            return f"  too long — {len(answer)} characters; at most {dm}"
        if "[" in answer or "]" in answer:
            return "  no square brackets — they mean something to the circle"
    space = question.get("unique_in")
    if space and answer.strip().lower() in {v.lower() for v in unique_values(space)}:
        return (f"  {answer.strip()!r} is already "
                + {"part_tags": "a part's name", "issue_ids": "an issue's id",
                   "issue_labels": "an issue's name"}[space]
                + " — choose another")
    return None


def unique_values(space: str) -> set[str]:
    """Every value already taken in a unique space, read fresh: part_tags is
    the roster's live Tags and alt_tags (re-scanned, not the import-time
    copy — a part added this process counts); issue_ids / issue_labels read
    issues/ through issue_schema, and read as empty if memory/ is not
    importable (a probe outside the tree)."""
    if space == "part_tags":
        roster, alt, _tails, _probs = R.scan()
        return {t for _d, t in roster} | set(alt)
    if space in ("issue_ids", "issue_labels"):
        try:
            import sys
            mem = str(R.ROOT / "memory")
            if mem not in sys.path:
                sys.path.insert(0, mem)
            import issue_schema as S                                 # noqa: E402
            docs = [S.load(f) for f in S.nodes()]
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

    Every read is one seam.read_line() on the COMMAND lane, the prompt
    being the numbered question, so in the dual pane it rides the cmd>
    input row and in a terminal input() prints it. An INVALID line is
    answered with one line saying why and the SAME question, until valid
    or empty — no limit, as ruled."""
    global _statements_shown
    ctx = R.read_context(part, base)
    tag = R.TAG_BY_DIR.get(part, part)
    if ctx is None or not ctx["questions"]:
        seam.emit("command", f"  {tag} ({part}) declares no context questions — "
                             f"nothing to ask. (parts/{part}/part.toml [context])")
        return "none"
    st = statements()
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
                raw = seam.read_line(prompt, channel="command",
                                     prefill=current).strip()
            except (EOFError, KeyboardInterrupt):
                seam.emit("command", "  (cancelled — nothing recorded)")
                return "skipped"
            if prefill and raw == "":
                raw = current                   # Enter keeps — both surfaces
            elif raw == CLEAR_TOKEN:
                raw = ""
            why = validate(q, raw, part=part)
            if why is None:
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
    R.write_context(part, new, base)
    seam.emit("command", st["completion"])
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
    return not S.nodes()


def _ask(qs: list[dict], *, seeds: "dict[str, str] | None" = None,
         part: str = "") -> "dict[str, str] | None":
    """The one asking loop every dialog shares: the numbered question on the
    COMMAND lane, validated per its own row, described-and-re-asked on
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
                raw = seam.read_line(prompt, channel="command",
                                     prefill=seed).strip()
            except (EOFError, KeyboardInterrupt):
                seam.emit("command", "  (cancelled — nothing recorded)")
                return None
            if seed and raw == "":
                raw = seed
            elif raw == CLEAR_TOKEN:
                raw = ""
            why = validate(q, raw, part=part)
            if why is None:
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
    commands.cmd_issue_add(values=...) — the same gate-before-write path
    the verb has. A probe passes a capture."""
    global _statements_shown
    spec = issue_questions()
    qs = spec.get("questions", [])
    if not qs:
        seam.emit("command", "  (initialization.toml declares no issue "
                             "questions — nothing to ask)")
        return "skipped"
    st = statements()
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
            return CMD.cmd_issue_add("", guard=guard, values=(lab, d, a))
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
    """PART_ADD_DIALOG — R324 (never at a circle start: approval of a part's
    `[proposed: /part-add "<describe>" "<Tag>"]`, or /part-add typed bare),
    R323 (the bracket's strings arrive prefilled — Enter keeps, typing
    edits), R332 (the validator; part_add.precheck() then holds the roster
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
    st = statements()
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
        name = PA.derive_name(tag) if tag else ""
        # THE MISSING HALF IS ASKED FOR, not refused — the same move the
        # context dialog makes; empty twice running abandons the add.
        if not tag:
            try:
                tag = seam.read_line("  the part needs a name — what should "
                                     "it be called? ", channel="command").strip()
            except (EOFError, KeyboardInterrupt):
                tag = ""
            if not tag:
                seam.emit("command", st["skipped"])
                return "skipped"
            continue
        if not describe:
            try:
                describe = seam.read_line(
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
                name = seam.read_line(
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
def pending_part_dialogs(base: pathlib.Path | None = None) -> list[str]:
    """The parts whose PART_CONTEXT_DIALOG is due: a declared [context]
    with at least one question and EVERY answer empty (R331 — the trigger
    is "no particulars recorded yet", read from the record). Ordered as
    R324 speaks them — Soul, then Child, then any other declaring part in
    roster order."""
    due = []
    roster, _alt, _tails, _probs = R.scan(base)
    for d, _t in roster:
        ctx = R.read_context(d, base)
        if ctx and ctx["questions"] and not any(ctx["answers"].values()):
            due.append(d)
    head = [d for d in ("soul", "child") if d in due]
    return head + [d for d in due if d not in head]


def run_initialization(*, live: bool, resume: bool, yes: bool) -> list[str]:
    """The INITIALIZATION step of a circle open — R330: between CHECKPOINT 2
    and the working-set question, COMMAND lane, focus handed to the command
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
    once, its own paths only, non-fatal, the commit_circle() manner."""
    import sys
    if not live or resume or yes:
        return []
    if seam.read_line.__module__ == "seam" and not sys.stdin.isatty():
        return []
    due_parts = pending_part_dialogs()
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
        before = set(S.nodes())
        issue_add_dialog()
        new_nodes = sorted(set(S.nodes()) - before)
        written += [str(p) for p in new_nodes]
        if new_nodes and (S.ISSUES / "INDEX.md").is_file():
            written.append(str(S.ISSUES / "INDEX.md"))   # regenerated with the write
    seam.emit("command", "")
    seam.emit("command", "Starting your circle...")
    seam.emit("state", "initialized")
    seam.emit("state", "")          # the engine keeps the last token; clear it
    if written:
        _commit(written)
    return written


def _commit(paths: list[str]) -> None:
    """One commit for the step's own writes, own paths only, non-fatal —
    git is the rollback target, not part of the open (commit_circle()'s
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
        G.commit_paths([_pl.Path(p) for p in paths],
                       f"initialization {datetime.date.today().isoformat()}: "
                       + ", ".join(names), log)
    except Exception as e:                                      # noqa: BLE001
        seam.emit("command", f"  (initialization commit failed — {e}; the "
                             f"answers are safe on disk, commit by hand)")


# ------------------------------------------------------------------ the verb
USAGE = "/part-context-update <part>   — ask that part's context questions again, prefilled"


def cmd_part_context_update(rest: str, *, guard=None, interactive: bool = True) -> None:
    """`/part-context-update <part>` — PART_CONTEXT_DIALOG(part) with the
    recorded answers prefilled; the edit path for what the first-run
    dialog recorded (docs/Initialization.md §6). USER table: the data is
    the person's own. `<part>` is a directory name (`soul`) or a Tag
    (`Soul`), case-insensitive.

    `interactive` is False where no one can answer a question — the
    dual pane's no-circle dispatch hands every read an immediate "" — and
    the dialog would then silently keep everything and report it; better
    to say where it does work. `guard` present means a circle is open,
    whose BLOCK 3 was built before this write: said, effective next circle."""
    word = rest.strip().split()[0] if rest.strip() else ""
    if not word:
        seam.emit("command", f"  usage: {USAGE}")
        declared = [d for d in R.DIR_NAMES if R.read_context(d)]
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
    outcome = part_context_dialog(part, prefill=True)
    if outcome == "completed" and guard is not None:
        seam.emit("command", "  (this circle's prompts were built before this — "
                             "the change reaches the next circle)")


def _resolve_part(word: str) -> "str | None":
    """A typed <part> — directory name or Tag, case-insensitive — to the
    directory, or None."""
    part = R.DIR_BY_TAG.get(word) or R.DIR_BY_TAG_ALL.get(word)
    if part is None:
        by_lower = {d.lower(): d for d in R.DIR_NAMES}
        by_lower.update({t.lower(): d for d, t in R.TAG_BY_DIR.items()})
        part = by_lower.get(word.lower())
    return part


def cmd_part_context_list(rest: str) -> None:
    """`/part-context-list [<part>]` — every part that declares context, its
    questions with the recorded answer beside each ("" shown as —); one
    part when named. Read-only; console-only (the answers never reach a
    transcript or a model except through their own render strings)."""
    word = rest.strip().split()[0] if rest.strip() else ""
    if word:
        part = _resolve_part(word)
        if part is None:
            seam.emit("command", f"  no part named {word!r}")
            return
        targets = [part]
    else:
        targets = [d for d in R.DIR_NAMES if R.read_context(d)]
    if not targets:
        seam.emit("command", "  no part declares context questions")
        return
    for d in targets:
        ctx = R.read_context(d)
        tag = R.TAG_BY_DIR.get(d, d)
        if not ctx:
            seam.emit("command", f"\n  {tag} ({d}) declares no context questions")
            continue
        seam.emit("command", f"\n  {tag} ({d}) — {ctx['purpose'] or '(no purpose)'}")
        for q in ctx["questions"]:
            a = ctx["answers"].get(q["key"], "")
            seam.emit("command", f"    {q['ask']}?  {a if a else '—'}")


def cmd_part_context_clear(rest: str, *, interactive: bool = True) -> None:
    """`/part-context-clear <part>` — empties every recorded answer, after
    "type 'yes'", re-arming the first-run dialog for the next open (R327's
    repeat rule works from the record, so clearing the record is what asks
    again)."""
    word = rest.strip().split()[0] if rest.strip() else ""
    if not word:
        seam.emit("command", "  usage: /part-context-clear <part>")
        return
    part = _resolve_part(word)
    if part is None or not R.read_context(part):
        seam.emit("command", f"  no part named {word!r} with context questions")
        return
    ctx = R.read_context(part)
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
    ans = seam.read_line(f"  erase {n} recorded answer(s) for "
                         f"{R.TAG_BY_DIR.get(part, part)} — type 'yes': ",
                         channel="command").strip().lower()
    if ans != "yes":
        seam.emit("command", "  cancelled — nothing erased.")
        return
    R.write_context(part, {k: "" for k in ctx["answers"]})
    seam.emit("command", "  cleared. The first-run dialog asks again at the "
                         "next open.")


def cmd_part_add(rest: str, *, guard=None, interactive: bool = True) -> None:
    """`/part-add ["<describe>" "<Tag>"]` — PART_ADD_DIALOG, the strings (the
    same two the taught bracket carries, in the same order) prefilled when
    given. The typed twin of approval's path (R323/R326's shape)."""
    if not interactive:
        seam.emit("command", "  /part-add asks questions and needs a command "
                             "pane that can answer them: open a circle first, "
                             "or run  python coordinator/circle.py --dev-cmd "
                             "part-add")
        return
    from commands import _issue_add_args
    describe, tag, _ = _issue_add_args(rest)
    seeds = {}
    if describe:
        seeds["describe"] = describe
    if tag:
        seeds["part_name"] = tag
    part_add_dialog(seeds=seeds or None)
