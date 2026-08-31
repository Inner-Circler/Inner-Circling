#!/usr/bin/env python3
"""
markers.py — the bracket-annotation system: the grammar (ASK_RE and
kin), per-statement recognition and stripping, REMEMBER's write path,
close-time coalescing across the transcript, and the staging calls
into the propose-class registers. Phase 2 stage 3 of the coordinator
partitioning (2026-08-16); until then all of it lived in circle.py.
Verbatim move - bodies and comments unchanged, except console output
goes through `seam.emit` by attribute access (the seam contract).

GRAMMAR AND COALESCING ONLY, deliberately: the vetting loop that RULES
on what is staged here (vet_pending_proposals and the approve/deny
executors) is a separate concern - it EXECUTES commands at approval
time - and stays in circle.py until its own stage. graph_now() stays
with it: _propose_approve is its one consumer. The shared constants
this grammar reads (PROPOSE_SUBSET_COMMANDS and its subtractions) live in
command_surface.py, stage 0's cycle-breaker, which is exactly what
lets this module and the dispatcher read one copy without reaching
into each other. It read DEV_CMD_HEADS too until R267 replaced it here
with PROPOSE_SUBSET_COMMANDS; that constant is now test_proposals.py's
alone, where it guards dispatch_dev_cmd's head list.
"""

from __future__ import annotations

import re

import issue_commands as IC        # issue-relationship-add's one grammar (R202)
import seam
import command_surface as CS
from command_surface import (PROPOSE_SUBSET_COMMANDS,
                             DEFERRED_PROPOSE_COMMANDS, PROPOSABLE_COMMANDS)


# a part's remember is a private note to its own future self and must
# never reach the room, another part, or a future prompt other than its
# own BLOCK 4 (docs/BNF.md, ruled 2026-08-12).
#
# Self's reflexive record is REMEMBER, surfaced on demand by `/recall`
# (docs/BNF.md's REMEMBER_PROJECTION; built 2026-08-18, R224). A part's
# own "flag my statement for Self's attention, this circle only"
# capability has no replacement — nothing in the annotation family gives
# it, and nothing is designed that would.
# TWO KEYWORDS, RULED 2026-08-20 (B60). The grammar was eight and is now
# this, in the operator's own words: *"detect square bracket open/close
# pairs. ignore unless the first contained token is 'remember:' or
# 'proposed:'; treat other as dialog text, do not capture or remove. No
# whitespace following the opening '[' is allowed. In both cases the ':'
# and exact spelling are required."*
#
# READ THE REGEX AS THAT SENTENCE. `\[` then the keyword IMMEDIATELY — no
# `\s*`, which is what "no whitespace following the opening [" is; then
# `:`, REQUIRED, so it is syntax now rather than R254's optional
# punctuation; then everything up to the FIRST `]`, which is what "open/
# close pairs" means where brackets do not nest.
#
# CASE-INSENSITIVE, RULED THE SAME DAY (R272). Under exact matching a part
# capitalising `[Remember:` at the start of a bracket would have its
# private note silently reclassified as dialog text and sent to every
# other part — the one failure REMEMBER exists to prevent.
#
# THE KEYWORD IS `proposed`; THE CLASS IS STILL `propose`. R202's PROPOSE
# class, self/proposals.toml and PROPOSE_SUBSET_COMMANDS are unchanged —
# only the bracket spelling moved. extract_markers() therefore records
# kind="propose" (the class) and `keyword` (what was actually typed), so
# every reader below keeps its vocabulary and every message echoes the
# writer's.
#
# WHAT THIS RETIRES: the six practice/better_option spellings.
# `[proposed: /practice-add ...]` and `[proposed: /better-option-add ...]` say
# what four of them said; revise and delete have no successor command,
# stated plainly in R270. `propose` WITHOUT THE `d` was retired with them
# (R273) and CAME BACK AS A SYNONYM, 2026-08-21 — the operator typed
# `[propose: practice-add ...]` in circle 2026-08-21_1139, it became speech,
# and he ruled *"accept with or without the d"*. See ASK_SYNONYMS below.
# THE OPENER IS SPELLED ONCE. Three regexes in this file recognise a
# remember bracket — this one, REMEMBER_RE (which STRIPS it) and
# CLOSE_REMEMBER_OPEN_RE (the lenient close form) — and all three needed the
# identical edit when the colon became required. The cost of them drifting
# is asymmetric and severe: if ASK_RE recognises a remember that REMEMBER_RE
# fails to strip, the private note reaches the room, which is the E06
# contamination class this module exists to prevent. So they share a
# fragment rather than agreeing by inspection.
_REMEMBER_OPEN = r"\[remember:"

# THE ALTERNATION IS A CONSTANT, and that is not cosmetic. Two independent
# scrapers read this grammar from SOURCE rather than importing it —
# work/tools/bnf_conformance.py (which never imports coordinator code) and
# ui/tests/test_circling.py (which must not) — and both were parsing the compiled
# PATTERN STRING. When the colon became required syntax on 2026-08-20 the
# terminator moved from `\b` to `:` and both scrapers needed the identical
# edit; both were made to accept EITHER terminator to survive it, which left
# two drift detectors permanently more lenient than they had been, and the
# lockstep edit slipped a stray trailing comma into one of them.
#
# A tuple of literals is what a scraper can read without tracking regex
# syntax at all: bnf_conformance already literal-evals module constants, and
# test_circling's copy becomes one ast.literal_eval.
# "recall" JOINED 2026-08-30 (R400-R402): the parts' private search. Its
# EXECUTION never reaches this grammar's routing — recall_index.apply_recall
# strips every recall bracket before extract_markers runs, exactly as
# apply_remember does for remember — but the ONE parser must still accept
# the form: test_annotation_exemplars holds every process_core.md exemplar
# to ASK_RE, and a taught spelling the parser refuses is the drift that
# suite exists to catch.
ASK_KEYWORDS = ("remember", "proposed", "recall")

# ACCEPTED SPELLINGS THAT ARE NOT TAUGHT, 2026-08-21 — the operator, verbatim:
# *"accept with or without the d"*. `[propose: ...]` is the SAME annotation as
# `[proposed: ...]`: same class, same staging, same vetting; only the echo
# keeps what was typed. It is a SYNONYM, not a second grammar — ASK_KEYWORDS
# above stays the taught set (process_core.md, /help, docs/BNF.md exemplars
# and the two source-scrapers all read it), and the parser alone reads this.
# `proposed` is listed before `propose` in the alternation so the longer
# spelling is tried first; either order would match, this one reads plainly.
ASK_SYNONYMS: dict[str, str] = {"propose": "proposed"}

ASK_RE = re.compile(
    r"\[(" + "|".join(ASK_KEYWORDS + tuple(ASK_SYNONYMS)) + r"):([^\]]*)\]",
    re.I)

# WHOSE KEYWORD IS WHOSE -- RULED 2026-08-30, the operator, verbatim:
# *"refuse it."* A `[recall: ...]` is a PART's own search of its own record;
# Self's read path is the cmd> `remember-list` verb. Nothing enforced that
# until this ruling: circle.py's Self> loop ran apply_self_remember() and
# strip_malformed_markers() and nothing else -- apply_recall() is called from
# rounds.py alone, on the PART path -- so a recall typed at the circle prompt
# was neither executed nor stripped nor refused. withheld() was False for it,
# render_messages() showed it to all seven parts as ordinary Self speech, and
# route_markers() echoed a staging promise nothing keeps. E06's shape.
#
# DECLARED AS A SUBTRACTION, the same way command_surface builds
# PROPOSABLE_COMMANDS: SELF_KEYWORDS is what Self may type, derived, so a
# future keyword joins ASK_KEYWORDS once and both surfaces follow. circle.py
# reads SELF_KEYWORDS for its refusal and for the hint it prints at the two
# opening prompts -- that hint was built from ASK_KEYWORDS and so had been
# teaching the operator that `[recall: ...]` was valid at the circle prompt.
PART_ONLY_KEYWORDS = ("recall",)
SELF_KEYWORDS = tuple(k for k in ASK_KEYWORDS if k not in PART_ONLY_KEYWORDS)

# RULED 2026-08-16 (R202): "the PROPOSE CLASS... subsumes every possible
# future, including request." `[proposed: <command>]` is the ONE marker
# that stages a future for Self to vet.
#
# ITS SECOND CATEGORY IS GONE, 2026-08-20 (R273). R202 split `<text>` into
# COMMAND and ANYTHING_ELSE (free-form; approval a pure record, Self acting
# independently); the free-form half is MALFORMED now. See
# `_propose_command_shape()` below — a body it cannot read is an error.

# DEV_CMD_HEADS (dispatch_dev_cmd's accepted-heads set, shared with the
# PROPOSE classifier below) MOVED to command_surface.py with its
# comment, 2026-08-16 — phase 2 stage 0; imported at the top of this
# file.


# DEFERRED_PROPOSE_COMMANDS — /issue-evidence-add, ruled into the table and
# refused by the classifier below anyway — MOVED to command_surface.py beside
# PROPOSE_SUBSET_COMMANDS, 2026-08-20 (code review), with PROPOSABLE_COMMANDS
# (the table minus it) defined there too. It was declared here for one
# afternoon, and help_system, which reads command_surface and never this
# module, counted the whole table: "one of the 6 proposable commands" while
# the refusal below listed 5. Both are imported at the top of this file.


def _proposable_list() -> str:
    """The verbs a propose may actually name, in the refusal itself.

    A REFUSAL THAT DOES NOT SAY WHAT IS ALLOWED sends the writer looking for
    a typo in their argument — R231's lesson, and the reason
    strip_malformed_markers() already named the valid spellings when there
    were six of them. Read from command_surface.PROPOSABLE_COMMANDS rather
    than restated — the same set /help counts."""
    return "valid: " + ", ".join(sorted(PROPOSABLE_COMMANDS))


def _propose_command_shape(text: str) -> dict | None:
    """Is a `[proposed: <command>]`'s body shaped like a real command —
    "syntax identical (shared) with valid inputs at the cmd> prompt"
    (RULED 2026-08-16, R202)? Returns a small descriptor, or None for
    ANYTHING_ELSE (free text). A leading "/" is optional here, same rule
    the command pane itself follows (RULED 2026-08-16, R201) — a part
    should not need to remember a slash "cmd>" itself does not require.

    WHAT MAY BE NAMED IS PROPOSE_SUBSET_COMMANDS — R267, 2026-08-20, the operator's own
    words: *"/practice-add is a circle construct, valid for users or
    parts to propose, stage, and vett. *list operations are not valid in
    any ANNOTATION."* A propose asks for a CHANGE; a listing is a
    question, and a question staged for ratification is a category error —
    approving one would "run" a read. That table is a SUBSET of the user
    table, never a third list, and command_surface asserts it.

    THIS SHRANK THE SET. It accepted dispatch_dev_cmd()'s whole
    no-circle-needed head list — /help, /practice-add, /practice-list,
    /practice-delete, /topic-list, /topic-close, /prompt-show,
    /issue-apply — of which only practice-add survives, joined
    2026-08-20 by /better-option-add (R270).

    AND THE VERB IS THE SLASH HEAD NOW (R261): this branched on
    `head == "/issue"` and then re-derived the verb from the FIRST
    ARGUMENT, which is exactly the two-token shape R261 retired.

    Shapes returned, all pure/side-effect-free here — nothing executes at
    classification time, only at approval:

      issue-relationship-add
        parsed with issue_commands.parse() itself, so there is exactly one
        grammar for an edge, not two. Its own shape name, not the generic
        one below, because coalesce_propose_proposals() and the
        convergence queue both key on it: an EDGE is the thing parts
        converge on. dispatch_dev_cmd() itself REFUSES this form (R161:
        direct-typed, it batches at close and needs a circle) — but
        propose-approval has ALWAYS been allowed to write the graph
        without one.
      issue_command
        any other issue ruling that parses whole — today
        issue-label-update. Approval runs the same precheck/apply the edge
        shape does; nothing about that branch is edge-specific.
      dev_cmd
        /practice-add, /better-option-add, /issue-add — each run through
        its own cmd_* directly at approval (vetting.py), not through
        dispatch_dev_cmd(), so a register refusal reports its own reason
        rather than "command dispatch refused". B62, 2026-08-23.

    `circle` is passed "" to the parser here — classification only asks
    "does this parse"; the real OT is stamped in at staging/approval time,
    when it is actually known.

    THERE WAS AN `issue_status` SHAPE HERE UNTIL 2026-08-21 —
    `issue-status-update nNNNN <value>`, handed to cmd_issue_property() at
    approval. The operator removed the verb from annotation visibility that
    day ("remove /issue-status-update from annotation visibility"), so it
    is no longer in PROPOSE_SUBSET_COMMANDS and the table check above
    returns None for it before any shape is built. The branch went with the
    table entry rather than staying as unreachable code.

    /issue-evidence-add IS IN R267's TABLE AND IS REFUSED HERE ANYWAY,
    with `ok: False` and a reason rather than a silent fall-through to
    free text. It addresses a statement BY ITS NUMBER, and the part,
    quote and source are resolved against the LIVE TRANSCRIPT by
    circle.py after parsing — a propose approved at a checkpoint has no
    transcript to resolve against. Recognized, refused, and visibly
    pending is the honest shape of "ruled, not yet buildable"."""
    stripped = text.strip()
    if stripped.startswith("/"):
        stripped = stripped[1:].lstrip()
    if not stripped:
        return None
    # ANY WHITESPACE ENDS THE VERB, 2026-08-20 (code review). This was
    # partition(" "), so a statement that wrapped right after the verb —
    # `[proposed: /practice-add<newline>when a part...]` — read the verb as
    # "/practice-add<newline>when", matched nothing, and the whole bracket
    # was MALFORMED with a refusal that listed the very verb the writer
    # used. process_core.md's own wrapped exemplar passed only because its
    # break falls after the first space; a part's does not have to.
    parts = stripped.split(None, 1)
    head_word, rest = parts[0], (parts[1] if len(parts) > 1 else "")
    # "/" + word, unconditionally — see the same note in circling.py.
    head = CS.normalise_head("/" + head_word)
    if head not in PROPOSE_SUBSET_COMMANDS:
        return None
    if head in DEFERRED_PROPOSE_COMMANDS:
        return {"shape": "issue_command", "ok": False,
                "why": ("issue-evidence-add resolves its quote against the "
                        "live transcript, which a checkpoint has not got — "
                        "rule it at cmd> instead")}
    if head in IC.HEADS:
        parsed, why = IC.parse(head + " " + rest.strip(), "")
        shape = ("issue-relationship-add" if head == "/issue-relationship-add"
                 else "issue_command")
        if parsed is None:
            return {"shape": shape, "ok": False, "why": why}
        return {"shape": shape, "ok": True, "parsed": parsed}
    # AN EMPTY /practice-add OR /better-option-add STOOD HERE UNTIL
    # 2026-08-23 (B62), REFUSED AT CLASSIFICATION rather than staged. The
    # reason was "an add with nothing to add can only fail at approval,
    # with a usage line nobody will be there to read" — true when
    # dispatch_dev_cmd() was the only channel approval had, since it could
    # report only "did I recognise this head", never why a write failed.
    # Approval now calls cmd_practice_add()/cmd_better_option_add()
    # directly and reads their own (ok, msg) — check_best_practices.add()'s
    # own "nothing to add" reaches the pending row's reason, so a special
    # case here duplicating that refusal one layer up is no longer needed.
    if head == "/issue-add":
        # PROPOSABLE SINCE 2026-08-21 (R290). The label is required; the
        # description and absence may ride along as further quoted strings
        # and, when they do not, approval opens a LEAD rather than asking —
        # a bracket staged at one circle is ruled at another, with nobody
        # there to answer a prompt. commands._issue_add_args is the one
        # parser, here as at cmd>.
        from commands import _issue_add_args
        label, _d, _a = _issue_add_args(rest)
        if not label:
            return {"shape": "dev_cmd", "ok": False,
                    "why": '/issue-add needs a label: /issue-add "label" '
                           '["description" ["absence"]]'}
        return {"shape": "dev_cmd", "ok": True, "head": head, "rest": rest}
    return {"shape": "dev_cmd", "ok": True, "head": head, "rest": rest}

# -------------------------------------------------------- OPTIONAL PUNCTUATION
# RULED 2026-08-19 (R254): the form the parts are TAUGHT is the form Self
# wrote when he ruled it — `[remember: "<memory>"]` and
# `[propose: "<proposal>"]`. HALF OF THAT RULING IS SUPERSEDED, 2026-08-20
# (R273): the COLON IS REQUIRED SYNTAX now, consumed by ASK_RE, so none of
# the spellings R254 equated survive except the quoted one:
#
#     [proposed: x]   [proposed: "x"]
#
# both carry the same x; `[proposed x]` is not an annotation at all. THE
# QUOTE HALF STANDS, and is what this section is still for.
#
# Until R254 `propose` stripped neither, so the newly-taught form would
# have staged a proposal whose text began with a colon and ended in a
# quote. That is the taught-form-diverges-from-the-parsed-form defect this
# project keeps re-finding (E09) — `test_annotation_exemplars.py` parses
# process_core.md's own examples so it cannot recur silently.
#
# Curly quotes fold with straight ones for the reason quote_as_mark.py
# folds them: parts type curly, Self types straight.
_QUOTE_PAIRS = (('"', '"'), ("\u201c", "\u201d"),
                ("\u201c", "\u201c"), ("\u201d", "\u201d"))


def _strip_quotes(body: str) -> str:
    """One pair of surrounding double quotes removed, straight or curly.
    A body that is nothing BUT the quotes empties to "" and is malformed
    by the same rule an empty bracket already was."""
    for lq, rq in _QUOTE_PAIRS:
        if len(body) >= 2 and body.startswith(lq) and body.endswith(rq):
            return body[1:-1].strip()
    return body


def _unwrap(arg: str) -> str:
    """ASK_RE's group 2, with its optional surrounding quotes removed.

    THE COLON IS NO LONGER STRIPPED HERE — the 2026-08-20 grammar REQUIRES
    it, so ASK_RE consumes it and a colon reaching this function is content
    the writer typed. R254 made the colon optional punctuation; that half of
    it is superseded. The quote half stands: a part types curly quotes and
    Self types straight, and neither pair is content."""
    return _strip_quotes(arg.strip())


# --------------------------------------------------------------------- caps
# THE WORD CAP IS GONE, 2026-08-20, because the thing it capped is gone.
# R255 set PROPOSE_WORD_CAP = 100 for a FREE-TEXT propose; a command was
# already exempt ("its grammar is fixed and far under 100 words already,
# and truncating one would turn a well-formed edge into a malformed one").
# Every propose is a command now, so the cap would apply to nothing.
#
# THE ONE-PER-PART-PER-CIRCLE HALF OF R255 STANDS, and is below.
# RULED 2026-08-19 (R255). Both annotations a PART authors are ONE PER
# PART PER CIRCLE, with a ceiling stated in WORDS because words are the
# unit process_core.md already teaches a part to think in:
#
#     [remember: ...]   1 per circle, written AT CLOSE, up to
#                       remember.AUTHORED_WORD_CAP words.
#     [proposed: ...]   1 per circle. No word cap any more — see above.
#
# THE CEILING IS ON WHAT A PART WRITES, NOT ON THE REGISTER.
# remember.RECORD_CAP (600 chars) still governs a record the COORDINATOR
# mints — dreaming's own memories, quote-as-mark's "lands", anything
# migrated in — so widening what a part may say does not silently widen
# what dreaming may write.
#
# TRUNCATED, NEVER REFUSED, still describes REMEMBER: a part that runs long
# loses its tail, not its record.


def capped_propose_keys(transcript: list[dict]) -> set:
    """(statement index, marker span) of the ONE `[proposed: ...]` that
    counts for each PART this circle — its LAST well-formed one. RULED
    2026-08-19 (R255): one propose per part per circle.

    LAST, NOT FIRST, and that is what makes the cap safe to apply at all.
    convergence_queue() already reads a part's LAST STANCE, so a part
    that proposed an edge one way and reversed after the reveal is
    counted in its final position (the Learner did exactly that by hand
    in `circle_2026-08-09_1520`). A first-wins cap would have outlawed
    that reversal; a last-wins cap is the rule the code already applied,
    now with the superseded attempts dropped rather than merely outvoted.

    SELF IS NOT CAPPED. The ruling is a PART discipline — Self types at
    the circle prompt and rules on what the room asked, so capping him
    would cap the ruler. `speaker == "self"` is skipped here, the same
    speaker unruled_proposals() excluded wholesale until R202.

    MALFORMED DOES NOT COUNT, the rule remember already follows: a
    propose that failed to parse is surfaced by show_unruled_proposals()
    and does not spend the part's one use."""
    last = {}
    for i, e in enumerate(transcript):
        if e["speaker"] in ("__scribe__", "self"):
            continue
        for rec in extract_markers(e["text"]):
            if rec["kind"] != "propose" or rec.get("malformed"):
                continue
            last[e["speaker"]] = (i, rec["span"])
    return set(last.values())


def extract_markers(text: str) -> list[dict]:
    """Every `[propose]`/`[remember]` marker in ONE statement's text,
    structured. Factored out of `unruled_proposals()` (RULED 2026-08-10) so
    the same parsing serves two call sites without drift: the
    whole-transcript batch below (still what a standalone, non-dual-pane
    run shows at `/close`), and `route_markers()`'s live, per-statement
    copy into the command pane (circling_and_evolving.md §5.2) — a
    marker is recognized and copied the instant it's spoken, not just
    scanned for once at close.

    `[request ...]` is PLAIN DIALOG TEXT as of 2026-08-20 — ruled, verbatim:
    *"Do not re-litigate retired terms; that construct is plain dialog text
    under the prior rules in this statement."* It matches nothing here, it is
    no longer stripped, and RETIRED_REQUEST_RE is gone with it. Same for a
    near-miss `[Proposed ...]` that omits the colon: under a grammar this
    narrow, everything that is not one of the two keywords is speech."""
    out = []
    for m in ASK_RE.finditer(text):
        keyword, arg = m.group(1), m.group(2).strip()
        # THE KEYWORD IS `proposed`, THE KIND IS `propose`. See ASK_RE: the
        # class did not move, only the bracket spelling. Every reader below
        # keys on the CLASS; the two emit sites echo `keyword`.
        #
        # `keyword` IS NOT LOWERED, and that is the point of keeping it as a
        # field at all: the grammar is case-insensitive (R272), so a part may
        # type `[Proposed:`, and a refusal that answers with `[proposed]` is
        # a refusal quoting a string the writer did not write. It was lowered
        # here for one afternoon and the field earned nothing.
        # A SYNONYM FOLDS TO ITS TAUGHT SPELLING FIRST (ASK_SYNONYMS,
        # 2026-08-21): `[propose:` is `[proposed:` — one class, one path.
        canon = ASK_SYNONYMS.get(keyword.lower(), keyword.lower())
        kind = "propose" if canon == "proposed" else canon
        # span: this match's exact (start, end) offset into `text` — added
        # for strip_malformed_markers() below, which needs to remove a
        # SPECIFIC malformed occurrence rather than every bracket of that
        # kind. Purely additive: no existing caller reads this key, and
        # none iterate the dict's keys rather than naming one.
        rec = {"kind": kind, "keyword": keyword, "arg": arg,
               "span": m.span()}
        if kind == "propose":
            # TWO OUTCOMES, RULED 2026-08-20, verbatim: *"For proposed,
            # validation is: COMMAND, parses: staged, approval RUNS it, OR
            # not command-shaped, malformed -> error to the command pane."*
            #
            # THE FREE-TEXT CLASS IS GONE. R202's ANYTHING_ELSE — a propose
            # whose text was ordinary prose, staged as a pure record — WAS
            # `shape is None`, and that is now an error. A part with
            # something to say says it in the room; the bracket stages a
            # COMMAND, and a bracket naming no command is a mistake worth
            # telling the writer about rather than filing.
            #
            # `kind_detail` IS GONE. R202 set it to "command" or "text" and
            # every reader asked which; with free text malformed there is one
            # value left, so the question it answered is now exactly "is this
            # well-formed", which `malformed` already answers. A field with
            # one value is a second name for something else.
            #
            # THE JUSTIFICATION IT CARRIED FOR ONE AFTERNOON WAS FALSE —
            # "self/proposals.toml holds historic rows whose kind is 'text'".
            # That file does not exist and never has (no working copy, no git
            # history); the register is created by the first live staging.
            # `proposals.stage()` still ACCEPTS a "text" kind, and
            # test_proposals.py fixtures still pass one, so the ROW schema is
            # unchanged — only this intermediate is.
            body = _unwrap(arg)      # R254's quote half — the colon is syntax
            if not body:
                rec["malformed"] = True
                rec["why"] = "nothing to propose"
            else:
                shape = _propose_command_shape(body)
                if shape is None:
                    rec["malformed"] = True
                    # THE ROOT OF THE DIAGNOSIS (the operator, 2026-08-30,
                    # from his journal: "note the root of the diagnosis is
                    # missing"). The Child wrote `[proposed: "/practice-add
                    # ... never [pass], which ..."]` and ASK_RE, which
                    # cannot nest, closed the proposal at [pass]'s own `]`
                    # — leaving a body that opens a quote it never closes,
                    # so the head token is `"/practice-add` and "not a
                    # command" was true but useless. Name the cause when
                    # the body shows it.
                    nested = "[" in body or arg.count('"') % 2 == 1
                    rec["why"] = ((
                        "a bracket inside the annotation ended it early — "
                        "`[pass]` inside `[proposed: ...]` closes the "
                        "proposal at its own `]`; write the word bare. "
                        if nested else "")
                        + "not a command that may be proposed. "
                        + _proposable_list())
                elif shape["ok"]:
                    rec["cmd_shape"] = shape
                    rec["text"] = body
                else:
                    rec["malformed"] = True
                    rec["why"] = shape["why"]
                    # NO `cmd_shape` ON A MALFORMED RECORD, 2026-08-20 (code
                    # review). It was kept for one afternoon so that
                    # unruled_proposals() could surface a failed EDGE attempt
                    # at /close — but every live path runs
                    # strip_malformed_markers() BEFORE transcript.append
                    # (rounds.py for a part, circle.py for Self, and the
                    # file record too), so no close-time scan can see a
                    # malformed bracket; R274 measured exactly that. The
                    # error fires at utterance and nowhere else; a field
                    # only a synthetic transcript could read is not kept.
        elif kind == "remember":
            body = _unwrap(arg)
            rec["text"] = body
            if not body:
                rec["malformed"] = True
        out.append(rec)
    return out


# Strips a remember bracket wholesale, valid or malformed alike — a
# malformed one still must not reach the room, the same as a valid one that
# lost the cap race. THE COLON now does what `\b` used to: neither
# "[remembering ...]" nor a bare "[remember]" matches, because neither has a
# colon in that position.
REMEMBER_RE = re.compile(_REMEMBER_OPEN + r"[^\]]*\]", re.I)


def strip_remember(text: str) -> str:
    """Remove every remember bracket, valid or malformed alike, and tidy the
    whitespace the removal left behind.

    THE ONE PLACE THIS IS SPELLED. Three callers need byte-identical output
    from the same input — apply_remember() and apply_self_remember() on the
    live path, and transcript_store.parse_transcript() on the resume path —
    because a resumed circle's in-memory statement is compared, hashed and
    cached against a live one's. Two copies of "sub, then collapse runs of
    spaces, then collapse blank lines, then strip" drift on the first edit
    to either; one function cannot.

    THIS IS THE ROOM BOUNDARY, NOT THE RECORD BOUNDARY. Ruled 2026-08-14,
    built 2026-08-18: the bracket is removed from the LIVE CIRCLE_DIALOG —
    render_messages(), the circle pane, every other entity's view — and
    RETAINED, unredacted, in the transcript file. So this runs on what goes
    to the room, and never on what goes to disk. docs/BNF.md, REMEMBER."""
    cleaned = REMEMBER_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def apply_remember(guard, part: str, display: str, text: str) -> tuple[str, bool]:
    """Recognize, cap, and silently remove every REMEMBER annotation in ONE
    statement before it can reach the ROOM. Returns (stripped_text,
    recorded) — `recorded` is True iff this call actually wrote a new
    remember.toml entry, so the caller can tell a genuine remember-only
    turn from one where the part's whole statement was a dropped duplicate.

    THE RETURNED TEXT IS THE ROOM'S, NOT THE RECORD'S — changed 2026-08-18,
    building the 2026-08-14 ruling. What this returns still goes to
    transcript.append(), render_messages(), the circle pane and
    route_markers(), all with the bracket gone. What goes to the TRANSCRIPT
    FILE no longer comes from here at all: the caller keeps its own raw text
    and writes THAT, bracket intact, so Coordinator's durable record is
    complete. See docs/BNF.md's REMEMBER and REMEMBER LIFECYCLE.

    ORDER OF OPERATIONS STILL MATTERS. This runs BEFORE transcript.append()
    and BEFORE route_markers() ever sees the text — by the time either runs,
    a remember marker is gone from the text they are given, the same as if
    it had never been typed. route_markers()'s own extract_markers() call
    therefore never finds a "remember" kind; nothing special-cases it there.
    Only the file-line write, which now takes the raw text, sits outside
    that guarantee, and by construction that string reaches no entity.

    THE CAP IS PER PART PER CIRCLE, resume-safe: has_remembered() reads
    remember.toml back off disk rather than the transcript. That was
    originally forced — the marker survived nowhere else — and since
    2026-08-18 it survives in the transcript FILE, so the choice is now
    merely the simpler one: one file to read, and no dependence on whether
    this circle was resumed. A second marker in the SAME statement is
    caught the same way, via the local `used` flag below.

    A malformed remember (empty text) is silently dropped — not written,
    not counted against the cap, not warned about. Nothing to remember
    costs the part nothing."""
    import remember as RM
    used = RM.has_remembered(part, guard)
    recorded = False
    for rec in extract_markers(text):
        if rec["kind"] != "remember":
            continue
        if rec.get("malformed"):
            continue
        if used:
            seam.emit("command",
                 f"  {display}: second REMEMBER this circle — dropped")
            continue
        RM.add(part, guard, rec["text"])
        used = True
        recorded = True
    return strip_remember(text), recorded


# ------------------------------------------------------ the CLOSE remember
# RULED 2026-08-19 (R255): a part writes its one remember AT CLOSE, in the
# same reply that carries its four short_term sections, and it may run to
# 1000 words.
#
# WHY THIS NEEDS ITS OWN PARSER AND NOT ASK_RE. ASK_RE's argument is
# `[^\]]*` — it stops at the FIRST "]". That is right for a marker
# embedded in a 150-word statement and wrong for a 1000-word memory, where
# a single "]" anywhere in the prose would silently truncate the record
# mid-sentence. Silent mid-record truncation is the E09 class of defect:
# nothing fails, and the loss is invisible until someone reads the file.
# So the close form is deliberately LENIENT — the memory runs from the
# opener to the end of the reply, less one optional trailing "]".
#
# THE PRICE OF LENIENCE IS AN ORDERING RULE, and it is stated in
# process_core.md, in both the annotation and the standing guidance
# beside it (R-NEW 2026-08-22): the remember goes LAST,
# after the four sections. collect_short_terms() re-checks the four
# headings AFTER the split and falls back to the strict ASK_RE parse if
# any went missing, so a part that puts it in the middle loses the
# lenience, not a section.
# THE COLON IS REQUIRED HERE TOO, 2026-08-20 — it was `\s*:?\s*`, optional,
# and an optional colon in this position would now accept an opener the
# grammar itself refuses.
CLOSE_REMEMBER_OPEN_RE = re.compile(_REMEMBER_OPEN + r"\s*", re.I)


def split_close_remember(text: str) -> tuple[str, str | None]:
    """(short_term, memory) — the memory is None when the reply carries no
    remember at all, which is the ordinary case and costs the part
    nothing. PURE: no cap, no write, no I/O. The caller decides whether
    this part has a use left."""
    m = CLOSE_REMEMBER_OPEN_RE.search(text)
    if not m:
        return text, None
    head = text[:m.start()].rstrip()
    body = text[m.end():].rstrip()
    if body.endswith("]"):
        body = body[:-1]
    return head, _strip_quotes(body.strip())


def apply_close_remember(guard, part: str, display: str,
                         text: str) -> tuple[str, bool]:
    """Recognize, cap and remove the ONE close-time remember from a part's
    short_term reply. Returns (short_term_text, recorded).

    SAME CAP, SAME REGISTER, SAME PRIVACY as the in-round path above —
    has_remembered() is the single answer to "has this part already used
    its one this circle", so a part that spent it in a round has none
    left at close, and the close bracket is dropped with a note. Written
    with remember.AUTHORED_WORD_CAP rather than RECORD_CAP: this is the
    part's own authored memory, not a coordinator-minted record.

    THE BRACKET NEVER REACHES THE SHORT_TERM FILE. A short_term is read
    by dreaming and by the audit; a remember reaches only this part's own
    BLOCK 4. Leaving it in the .md would put a private note into the one
    document another process reads on the part's behalf — the same
    boundary strip_remember() draws for the room, drawn here for the
    record."""
    import remember as RM
    short_term, memory = split_close_remember(text)
    if memory is None:
        return text, False
    if not memory:
        # An empty remember costs nothing and is not counted — the rule
        # apply_remember() already follows for a malformed one.
        return short_term, False
    if RM.has_remembered(part, guard):
        seam.emit("command",
                  f"  {display}: remember already used this circle — "
                  f"close remember dropped")
        return short_term, False
    RM.add(part, guard, memory, word_cap=RM.AUTHORED_WORD_CAP)
    return short_term, True


def apply_self_remember(guard, display: str, text: str) -> tuple[str, bool]:
    """Self's own counterpart to apply_remember() above — SAME ordering
    guarantee (strip BEFORE transcript.append(), BEFORE route_markers() ever
    sees the text) and, since 2026-08-18, the same room/record split: the
    text returned here is the ROOM's, and Self's own raw line — bracket
    intact — is what circle.py writes to the transcript FILE. This function
    fixed a latent leak: until it existed, a `[remember: ...]` typed at
    the Self> prompt went straight into the transcript (every part would
    read it next round) and was ALSO echoed to the command pane by
    route_markers()'s generic fallback branch — neither of which is
    'private', which is the entire point of a remember.

    WRITES, as of 2026-08-17 (B48) — RULED 2026-08-17 (R206): the
    destination is self/remember.toml, mirroring a part's own file.
    remember.py's part-parametrized add()/has_remembered() ALREADY
    generalize to Self (remember.SELF = "self", added 2026-08-15 with the
    R193 self.md migration — this function is the first LIVE caller of
    that path, not a second implementation of it). Same cap discipline a
    part gets: has_remembered(SELF, guard) reads self/remember.toml back
    off disk, resume-safe, same as a part's; a second use this circle
    warns and is dropped, same message shape apply_remember() gives a
    part.

    Mirrors apply_remember()'s own "malformed costs nothing" default:
    empty text is stripped, never written, never counted against the cap.

    Returns (stripped_text, recorded) — `recorded` is True iff this call
    actually wrote a new self/remember.toml entry, mirroring
    apply_remember()'s own return contract exactly (not `found`, which
    used to mean "recognized" regardless of whether anywhere existed to
    write it — now that somewhere exists, the two collapse into one)."""
    import remember as RM
    used = RM.has_remembered(RM.SELF, guard)
    recorded = False
    for rec in extract_markers(text):
        if rec["kind"] != "remember":
            continue
        if rec.get("malformed"):
            continue
        if used:
            seam.emit("command",
                 f"  {display}: second REMEMBER this circle — dropped")
            continue
        RM.add(RM.SELF, guard, rec["text"])
        used = True
        recorded = True
    return strip_remember(text), recorded


# BOTH BRACKET GUARDS ARE GONE, 2026-08-20 — RETIRED_REQUEST_RE and
# NEAR_MISS_PROPOSED_RE — and it is the ruling that removed them, not
# neglect.
#
# `[request ...]`: *"Do not re-litigate retired terms; that construct is
# plain dialog text under the prior rules in this statement."* Under those
# rules the only recognised brackets are `[remember:` and `[proposed:`; a
# `[request ...]` is neither, so it is dialog text, and dialog text is
# neither captured nor removed.
#
# THE NEAR MISS (B51(1), R231) is answered by the grammar instead of by a
# guard. It existed because `[Proposed: ...]` matched nothing: ASK_RE had
# `propose` and four `proposed <object>` sub-kinds, and the word boundary
# failed between `propose` and its `d`. `proposed:` IS the keyword now, so
# the spelling that raised R231 is the valid one, and the near miss it was
# built to catch cannot occur.
#
# WHAT R231 ACTUALLY ASKED FOR IS STILL HONOURED, and by a wider path than
# before: *"a malformed proposal... is an error, report in the command
# pane."* A `[proposed: ...]` naming anything that is not a proposable
# command is now MALFORMED — reported and stripped — where before it would
# have been staged as free text.


def strip_malformed_markers(text: str, display: str,
                            quiet: bool = False) -> str:
    """The bracket-annotation half of E06 (work/instrument/LOG.md) — the
    half that had no fix until now. An unrecognized SLASH command is
    already refused and never sent to the room (see the "UNKNOWN COMMAND
    ... not sent to the room" branch in main()'s Self> loop below). A
    malformed ANNOTATION had no equivalent: `[proposed: fix the thing]`,
    naming no command, is recognized as kind="propose", malformed=True —
    route_markers() used to flag that to the command pane, but the bracket
    stayed in the transcript regardless, which every other part then read
    next round. Same contamination E06 was written to stop, reached through
    the annotation door instead of the slash-command one.

    A RETIRED KEYWORD IS NO LONGER TREATED AT ALL, 2026-08-20. `[request
    ...]` had its own literal regex here and was stripped alongside a
    malformed marker; the ruling made it, and the six retired practice
    spellings, DIALOG TEXT — not captured, not removed. Retiring a keyword
    by keeping a guard for it would strip it forever.

    ONLY malformed spans are removed — a well-formed propose/remember
    marker is untouched and stays visible in the room, exactly as before
    this function existed; this closes the leak for the broken case only,
    never changes the working one.

    Emits its OWN warning here, inline, rather than leaving it to
    route_markers() — the same shape apply_remember() already uses for its
    "second REMEMBER — dropped" notice. route_markers() runs AFTER this
    (same ordering as apply_remember/apply_self_remember: strip first,
    THEN append, THEN route), so by the time it sees the text a malformed
    marker is simply gone — which is why its own malformed-detail branches
    are removed in the same change, not left as dead code that can no
    longer fire.

    REMEMBER IS EXEMPT, EXPLICITLY — changed 2026-08-18. On the ROOM path
    the exemption is invisible: apply_remember()/apply_self_remember() have
    already removed every remember bracket, valid or malformed alike, so
    extract_markers() finds no "remember" kind to skip. On the RECORD path
    it is load-bearing: the caller now runs this function a second time,
    `quiet`, over its own RAW text to build the transcript-file line, and
    there the brackets are still present. Stripping a malformed one there
    would delete from the durable record exactly what the 2026-08-14 ruling
    says to retain ("valid or malformed alike"). It would ALSO have crashed
    until 2026-08-20: a remember record carries no `word`/`op`, which the
    per-kind detail branch below read unguarded. That branch went with the
    six practice kinds, so only the first reason is load-bearing now.

    `quiet` suppresses the warnings only, never changes what is stripped.
    The record pass must not re-warn about a marker the room pass already
    reported; two notices for one bracket would read as two brackets."""
    recs = extract_markers(text)
    malformed = [rec for rec in recs
                 if rec.get("malformed") and rec["kind"] != "remember"]
    if not malformed:
        return text
    # ONE KIND REACHES HERE NOW — `propose`. REMEMBER is exempt above and
    # the six practice/better_option kinds no longer exist, so the branch
    # that read `rec["word"]`/`rec["op"]` for them is gone with them.
    for rec in malformed:
        # EVERY malformed branch sets `why` since 2026-08-20; the fallback
        # this line carried is unreachable and would only hide a new branch
        # that forgot to.
        if not quiet:
            seam.emit("command",
                      f"  [{rec['keyword']}] from {display}: MALFORMED: "
                      f"{rec['arg']!r} — {rec['why']} — dropped, not sent "
                      f"to the room")
    cleaned = text
    spans = sorted([rec["span"] for rec in malformed], reverse=True)
    for start, end in spans:
        cleaned = cleaned[:start] + cleaned[end:]
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# RULED 2026-08-18 (R225): "a [remember: ...] or [propose ...] is valid ONLY
# at the circle pane self> (aka user_name>) prompt; typing any annotation
# into the topic (or the active issues set selection) is invalid, say so and
# return to the prompt."
#
# THE DETECTOR ONLY. What to DO about a hit is the caller's — circle.py
# rejects the whole line and re-asks, which is a prompt loop, not grammar,
# and this module is grammar (see the module docstring).
#
# WHY IT IS NOT strip_malformed_markers(). That function strips the BROKEN
# span and lets the rest of the line through, because on a speech path the
# statement is still a statement once the bad bracket is gone. Here there is
# no such remainder to save: a topic is not speech, and an annotation typed
# into one is not a statement with a defect in it — it is the right input at
# the wrong prompt. Silently stripping it would open the circle with a topic
# the typist did not write, and record nothing of what they meant.
#
# VALID AND MALFORMED ALIKE. The ruling says "any annotation", and the
# reason it must is that malformed is exactly the case a typist most needs
# told about: `[proposed:]` with an empty arg is still an attempt to
# annotate, and answering it with silence would teach that the topic prompt
# accepts annotations that simply do not work.
#
# NARROWED WITH THE GRAMMAR, 2026-08-20. This used to sweep
# RETIRED_REQUEST_RE and NEAR_MISS_PROPOSED_RE as well, because both named
# bracket text that was an annotation ATTEMPT while matching no kind. Under
# a two-keyword grammar there is no such category: a bracket either opens
# `[remember:` / `[proposed:` or it is dialog text, and dialog text typed
# into a topic is a topic.
#
# An UNCLOSED bracket (`[proposed:` with no `]`) is not detected, here or
# anywhere else in this module — ASK_RE requires the `]`. That is the whole
# system's behaviour, not a gap opened by this function.
def annotations_in(text: str) -> list[str]:
    """Every annotation-shaped bracket in `text`, verbatim, in the order
    they appear. Empty list means the text carries no annotation at all,
    which is the only thing a caller needs to decide whether to accept it.

    Returns the SOURCE SPANS, not parsed records: the caller's job is to
    quote back what was typed, and a reconstructed bracket would differ
    from it in whitespace at exactly the moment a typist is trying to see
    what went wrong."""
    spans = [rec["span"] for rec in extract_markers(text)]
    return [text[a:b] for a, b in sorted(spans)]


def part_only_in(text: str) -> list[str]:
    """Every bracket in `text` whose keyword belongs to a PART alone --
    today that is `[recall: ...]` and nothing else (PART_ONLY_KEYWORDS).
    Verbatim source spans, in order, exactly as annotations_in() returns
    them and for the same reason: the caller quotes back what was typed.

    RULED 2026-08-30, the operator: *"refuse it."* This is the detector
    behind circle.py's refusal at the Self> prompt, and it is deliberately
    the SAME parser annotations_in() uses rather than recall_index's
    RECALL_RE. Two reasons. The refusal must fire on what a TYPIST wrote,
    which is what ASK_RE recognizes and what the hint at the two opening
    prompts already quotes; and RECALL_RE is the EXECUTION seam, whose job
    is to strip a bracket on the part path. Pointing the refusal at the
    execution regex would have made the two drift apart in exactly the
    direction markers.py's own header warns about for REMEMBER_RE.

    EMPTY LIST IS THE ONLY THING A CALLER NEEDS: a line with no part-only
    bracket is a line Self may speak."""
    return [text[rec["span"][0]:rec["span"][1]]
            for rec in sorted(extract_markers(text), key=lambda r: r["span"])
            if rec["kind"] in PART_ONLY_KEYWORDS]


def _checkpoint(live: bool) -> str:
    """What actually happens to this row, said at the moment it is uttered.

    B51(3), and it is a CORRECTION rather than an addition. The notice used
    to end "see /close" unconditionally, and in a sandbox circle that is
    false: stage_propose_proposals() `return []`s when not live (R202), so
    nothing is staged and the row cannot survive its own run. (It said
    "Both notices" while stage_practice_proposals() existed beside it,
    until 2026-08-20.) Telling a part
    its proposal is pending when it will vanish at the end of the hour is the
    one thing an utterance-time notice must not do.

    LIVE NAMES ITS CHECKPOINT, per R222, which kept BOTH rather than firing
    at utterance — firing here would stop the round up to seven times while
    parts wait, since this runs inside run_round() between statements."""
    if live:
        return "staged at /close; ruled there, or at the next circle's open (R222)"
    return ("SANDBOX — nothing is staged, and this row cannot survive the run "
            "(R202); say it again in a live circle for it to count")


def route_markers(display: str, text: str, *, live: bool) -> None:
    """RULED 2026-08-10, circling_and_evolving.md §5.2. The moment a
    marker is recognized in a statement — a part's, or Self's own, since
    §2's exclusion below is removed — its structured form is COPIED to
    the command pane as a pending question. Never executed here,
    regardless of source: this function only calls `emit`, never `IC.*`
    or anything that writes to the record. Call sites are every place a
    statement — part or Self — is appended to the transcript.

    NO MALFORMED BRANCH HERE. Every call site runs strip_malformed_markers()
    on `text` before appending it and before calling this function — a
    malformed marker is warned about and removed there, at the same point
    apply_remember() handles its own dropped duplicates, so by the time
    this function ever sees `text` a malformed record cannot appear.
    extract_markers() can still, in principle, return one (this function
    doesn't re-derive the ordering guarantee, it relies on it) — if that
    invariant is ever broken upstream, a malformed record here falls
    through the `else` branch below rather than crashing, but it should
    never actually happen; test_practice_annotations.py covers the
    ordering, not this function re-checking it."""
    for rec in extract_markers(text):
        # A RECALL NEVER BELONGS HERE, AND SAYING SO IS CHEAPER THAN THE LIE.
        # Two upstream conventions already keep it away: a PART's recall is
        # stripped by recall_index.apply_recall() before this is called, and
        # since 2026-08-30 Self's is refused at the prompt (SELF_KEYWORDS).
        # If either ever breaks, the `else` below would announce the recall
        # to the command pane with this function's own checkpoint suffix —
        # "staged at /close; ruled there" — a promise nothing keeps, since a
        # recall stages nothing and is never ruled. Silence is the honest
        # fallthrough for an invariant this function does not itself enforce.
        if rec["kind"] in PART_ONLY_KEYWORDS:
            continue
        # THE PRACTICE BRANCH IS GONE WITH ITS SIX KINDS, 2026-08-20. What
        # `[proposed practice: ...]` said is now `[proposed: /practice-add
        # ...]`, which is a command like any other and needs no branch of
        # its own here.
        if rec["kind"] == "propose" and not rec.get("malformed"):
            # THE "[command]" TAG IS GONE. It discriminated against "[text]"
            # while free text was a class; on every line it would now be the
            # same word.
            detail = rec["text"][:80]
        else:
            detail = rec["arg"] or "(no argument)"
        seam.emit("command",
                  f"  [{rec['keyword']}] from {display}: {detail} — "
                  f"{_checkpoint(live)}")


def unruled_proposals(transcript: list[dict],
                      issue_cmds: list[dict] | tuple = ()) -> list[dict]:
    """M2, ruled 2026-08-04. A part may PROPOSE its own statement for Self's
    attention at close.

    `issue_cmds` — 2026-08-21, the operator (F6: *"yes"*): an edge proposal
    whose IDENTICAL edge Self has already ruled THIS circle by a direct
    command is not unruled, and is left out — the close-time list asks only
    about what is genuinely open. In circle 2026-08-21_1139 he typed both
    rulings and was still asked to "rule with /issue-relationship-add" on
    each. Same normalisation convergence_queue() uses (either direction is
    the same question). Default empty: every other caller sees the list
    as before.

    A part asked for exactly this in `sandbox_2026-08-04_1243` and had no
    way to reach it: *"Child said something I want held past the close of this
    circle... I just want to make sure that sentence doesn't get filed under
    'good circle' and forgotten by next week's evidence-gathering. It's not
    evidence. It's the point."*

    FAILS OPEN. The marker is scanned out of prose, which is the one thing
    this project spent a day escaping — and it is right here, because a missed
    proposal costs nothing: Self has the transcript regardless.

    RULED 2026-08-10: no longer excludes `speaker == "self"` — circling_
    and_evolving.md §2's gap. Self's own markers count the same as a
    part's now, from either pane.

    RESCOPED 2026-08-16 (R202): `propose` used to mean "an edge attempt,
    valid or malformed" unconditionally — this function's own original
    docstring called it exactly that. Now that `[propose <text>]` covers
    every future (command or free text), keeping ALL of it here would
    mislabel ordinary free-text/other-command content as a relation
    attempt. Scoped back to its documented purpose instead of expanded
    to match the marker's new breadth: only an ADD-RELATION-shaped
    attempt still appears — successfully parsed (redundant with staging,
    same ADDITIVE choice this project has not resolved either way, see
    relation coalescing below) or genuinely malformed (a real issue-relationship-add
    attempt whose arguments didn't parse). An empty propose, free text, or
    any OTHER command is comprehensively handled by staging now and has
    nothing left to show here. Lost its `marks` parameter 2026-08-14, when
    MARK and PROPOSE MARK were retired wholesale (docs/BNF.md) — the
    parameter had already gone unused in this function's body since
    2026-08-12.

    RENAMED 2026-08-18 (R236): was `nominations()`; `show_unruled_proposals()`
    was `show_nominations()`. "Nomination" was an unwanted synonym for the
    PROPOSE class this has belonged to since R202 — same marker, same
    grammar, same re-derive-from-the-transcript discipline. The new name
    states the ROLE, which survives either resolution of the ADDITIVE
    TENSION (docs/BNF.md): what the room proposed and Self has not ruled.

    CAPPED AT ONE PER PART, 2026-08-19 (R255), from the SAME
    capped_propose_keys() call staging uses — computed over the whole
    transcript BEFORE this function's own edge-shape filter, so the
    propose that counts here is the propose that counts there. Deriving
    it from the already-filtered list would let a part whose last
    propose was free text keep an earlier edge attempt alive on this
    surface alone, and the two views would disagree about what the part
    asked for.

    MALFORMED IS NOT SHOWN HERE ANY MORE, 2026-08-20 (code review), because
    it cannot arrive: every live path runs strip_malformed_markers() before
    a statement is appended — room text and file record alike — so by the
    time a transcript reaches this function a malformed bracket is gone.
    R274 measured it. The "!! MALFORMED" line this used to feed fired only
    in a test that handed the bracket to this function directly."""
    out = []
    kept = capped_propose_keys(transcript)
    ruled_edges = {_normalize_edge((c["node"], c["type"], c["target"]))
                   for c in issue_cmds
                   if c.get("verb") == "issue-relationship-add"}
    for i, e in enumerate(transcript):
        if e["speaker"] == "__scribe__":
            continue
        for rec in extract_markers(e["text"]):
            # THE PRACTICE_KINDS EXCLUSION IS GONE because the kinds are.
            # It read "PRACTICE LIFECYCLE, not M2 — see practice_proposals()",
            # and practice_proposals() is gone too: a practice is proposed as
            # a COMMAND now and rides the same path as every other one.
            if rec["kind"] == "propose":
                # `cmd_shape` ALONE discriminates, and only a well-formed
                # record carries one. This also tested kind_detail ==
                # "command" until 2026-08-20, which was redundant then and
                # single-valued after; and it admitted a MALFORMED edge
                # attempt until the same day — see the docstring.
                is_edge_command = (not rec.get("malformed")
                    and rec.get("cmd_shape", {}).get("shape") == "issue-relationship-add")
                if not is_edge_command:
                    continue                  # malformed, or a non-edge
                                               # command — fully staged,
                                               # nothing more to show
                if (e["speaker"] != "self"
                        and (i, rec["span"]) not in kept):
                    continue                  # R255 — superseded by this
                                               # part's later propose
                pe = rec["cmd_shape"]["parsed"]
                if _normalize_edge((pe["node"], pe["type"], pe["target"])) \
                        in ruled_edges:
                    continue                  # 2026-08-21 — Self already
                                               # ruled this edge in the room
            if rec["kind"] == "remember":
                continue                      # never M2 material — a
                                               # remember is a private note,
                                               # never Self-facing. In
                                               # practice this never fires:
                                               # apply_remember() strips a
                                               # remember before the
                                               # transcript ever stores it,
                                               # so none survives to reach
                                               # this scan — this guards the
                                               # M2 vocabulary itself. It
                                               # sat beside a PRACTICE_KINDS
                                               # exclusion until 2026-08-20;
                                               # that one went with its six
                                               # kinds, this one did not.
            out.append({"index": i, "display": e["display"], "text": e["text"], **rec})
    return out


# PRACTICE ANNOTATIONS ARE GONE — practice_proposals(),
# coalesce_practice_proposals() and stage_practice_proposals() were removed
# 2026-08-20 with the six bracket kinds they were the only readers of.
#
# WHAT REPLACES THEM IS NOT A REWRITE, IT IS THE PROPOSE PATH. A practice is
# proposed as `[proposed: /practice-add ...]` and a better option as
# `[proposed: /better-option-add ...]`, so both are staged by
# stage_propose_proposals() into self/proposals.toml and RUN at approval by
# dispatch_dev_cmd(). One staging register instead of two.
#
# ONE BEHAVIOUR REALLY DID CHANGE, and it is worth stating rather than
# discovering. A proposed practice used to be staged as a `state="proposed"`
# ROW IN self/best_practices.toml — visible to /practice-list, excluded from
# projection, ruled through check_best_practices.approve(). It is now a row
# in self/proposals.toml, and best_practices.toml gains a row only once the
# proposal is approved and the command runs. approve()/pending() there are
# NOT removed: rows staged before this change are still pending and still
# have to be rulable, and inter_circle's SYNTHESIS still stages through
# render_stage().
#
# What has no successor at all: revise and delete. R270 says so.


def _norm_text(s: str) -> str:
    """Collapse whitespace and case for GROUPING purposes only — never
    touches what actually gets staged, just what counts as 'the same
    proposal' when two speakers word it slightly differently."""
    return " ".join(s.split()).lower()


def propose_proposals(transcript: list[dict]) -> list[dict]:
    """Every well-formed `[proposed: ...]` marker across the whole
    transcript, re-derived fresh on every call, same discipline every
    other `*_proposals()` function here has always used. RULED
    2026-08-16 (R202): replaces request_proposals() and
    relation_proposals() at once — `[proposed: <command>]` is the ONE
    marker. R202's second category, free text, is MALFORMED as of
    2026-08-20 (R273), so everything this yields is a command. Malformed
    ones (a command ATTEMPT that failed to parse) are excluded — and since
    the same day they cannot arrive at all: strip_malformed_markers() runs
    before any statement is appended, so a transcript never holds one
    (R274).

    CAPPED AT ONE PER PART, 2026-08-19 (R255) — see capped_propose_keys()
    for why it is the LAST rather than the first, and why Self is exempt.
    A part's superseded earlier proposes are dropped here, before
    coalescing, so a part cannot occupy two staged rows."""
    out = []
    kept = capped_propose_keys(transcript)
    for i, e in enumerate(transcript):
        if e["speaker"] == "__scribe__":
            continue
        for rec in extract_markers(e["text"]):
            if rec["kind"] != "propose" or rec.get("malformed"):
                continue
            if e["speaker"] != "self" and (i, rec["span"]) not in kept:
                continue          # R255 — superseded by this part's later one
            out.append({"index": i, "display": e["display"],
                        "text": e["text"], **rec})
    return out


def coalesce_propose_proposals(transcript: list[dict],
                               issue_cmds: list[dict]) -> list[dict]:
    """Groups propose_proposals() into rows to stage. RULED 2026-08-16
    (R202): replaces coalesce_relation_proposals() and coalesce_request_
    proposals() at once, branching internally on WHICH coalescing rule
    a row needs:

    ADD-RELATION-shaped COMMAND: the SAME rule #32 already ruled for a
    relation, preserved exactly — group by normalized edge, using each
    speaker's LAST STANCE (the rule convergence_queue() also applies to
    its own bucket), and stage ONLY when the group is unanimous — every
    speaker who proposed this edge, either direction, converged on the
    same direction this circle. Dedups against `issue_cmds` — commands
    already queued THIS circle — same as before. A split group is left
    unstaged; Self still sees it via show_unruled_proposals() and rules with
    `/issue-relationship-add` directly, same as always.

    EVERY OTHER COMMAND (practice-add, better-option-add, issue status,
    ...): the SAME rule request always had, preserved exactly — group by
    normalized TEXT, NO unanimity required. A part repeating the same ask
    verbatim (or near enough) does not stage twice; several parts
    converging on the same wording coalesce into ONE row with every
    speaker under `sources`. A part proposing two GENUINELY DIFFERENT
    things gets two rows, not one.

    THIS BRANCH READ "free text, or any OTHER command" until 2026-08-20,
    and carried the row's `kind` through from whichever record it was
    grouped from because that kind could be either. Free text is malformed
    now, so every row this mints is a command and the branch says so
    directly rather than deriving a constant.

    Neither branch checks for an equivalent row already pending from an
    EARLIER circle — the same known limitation every coalesce_*_
    proposals() function here has always carried, not solved here
    either."""
    queued_edges: set[tuple[str, str, str]] = set()
    for c in issue_cmds:
        if c.get("verb") == "issue-relationship-add":
            queued_edges.add(_normalize_edge((c["node"], c["type"], c["target"])))

    edge_groups: dict[tuple, dict[str, dict]] = {}
    other_groups: dict[str, dict[str, str]] = {}

    for p in propose_proposals(transcript):
        shape = p.get("cmd_shape")
        if shape and shape.get("shape") == "issue-relationship-add":
            parsed = shape["parsed"]
            edge = (parsed["node"], parsed["type"], parsed["target"])
            key = _normalize_edge(edge)
            if key in queued_edges:
                continue
            g = edge_groups.setdefault(key, {})
            g[p["display"]] = {"edge": edge, "text": p["text"]}
            continue
        arg = p["text"].strip()
        if not arg:
            continue
        key = _norm_text(arg)
        g = other_groups.setdefault(key, {})
        g[p["display"]] = arg

    rows: list[dict] = []
    for by_speaker in edge_groups.values():
        stances = list(by_speaker.values())
        directions = sorted({s["edge"] for s in stances})
        if len(directions) != 1:
            continue                          # not unanimous — left to
                                               # show_unruled_proposals()
        # FIRST PROPOSER FIRST, 2026-08-21 — the operator: *"coalesce
        # identical proposed commands, first proposer gets credit."* A dict
        # keeps insertion order, and a speaker's LATER stance overwrites
        # the value without moving the key — so list(by_speaker) is the
        # order in which each speaker FIRST proposed this. stage() credits
        # sources[0]. It was sorted(by_speaker) — alphabetical — until then.
        rows.append({"kind": "command", "text": stances[0]["text"],
                     "sources": list(by_speaker)})
    for by_speaker in other_groups.values():
        rows.append({"kind": "command", "text": next(iter(by_speaker.values())),
                     "sources": list(by_speaker)})
    return rows


def stage_propose_proposals(ot: str, transcript: list[dict],
                            issue_cmds: list[dict], live: bool) -> list[str]:
    """Written once, at /close — never mid-circle, sandbox writes nothing (a
    sandbox circle's proposal is a draft, not something to stage into
    the live self/proposals.toml). RULED 2026-08-16 (R202): replaces
    stage_request_proposals() and stage_relation_proposals() at once.
    Returns the new ids for the caller to report."""
    if not live:
        return []
    rows = coalesce_propose_proposals(transcript, issue_cmds)
    if not rows:
        return []
    import proposals as PR
    return [PR.stage(row["kind"], row["text"], row["sources"], ot)
            for row in rows]


def _normalize_edge(edge: tuple[str, str, str]) -> tuple[str, str, str]:
    """`n0001 leads-to n0002` and `n0002 leads-to n0001` are the same
    QUESTION, answered in either direction (circling_and_evolving.md
    §3) — sort the endpoints so both hash to one group key. The
    direction each speaker actually said is kept separately (each
    group's `stances`), never lost — this only decides what counts as
    "the same thing being converged on," not what anyone actually
    said."""
    a, ty, b = edge
    lo, hi = sorted((a, b))
    return (lo, ty, hi)


def convergence_queue(transcript: list[dict],
                       issue_cmds: list[dict]) -> dict[str, list[dict]]:
    """circling_and_evolving.md §3, RULED 2026-08-10. Composes
    `unruled_proposals()` — does not replace or cache it. Recomputed fresh
    from the transcript on every call, the same discipline
    `unruled_proposals()` already has, because that is what makes reading it
    safe regardless of whether the transcript came from a live circle or
    `--resume`: nothing here depends on `route_markers()`'s live event
    stream (step 4), which has no memory across a resume by construction
    (its call sites are deliberately absent from the `--resume`
    transcript-parsing path — see that step's log). A view that read
    from the event stream instead would show an empty queue after every
    resume; this one cannot, because it always re-derives from
    `transcript` itself.

    Takes `issue_cmds` as a second input, beyond `unruled_proposals()`'s own
    (`transcript`, alone since 2026-08-14's MARK retirement dropped
    `marks`) — the gap this section names: `issue_commands.precheck()` checks a
    proposed edge only against the live, ALREADY-APPLIED graph, never
    against `issue_cmds` (what this circle has already queued but not
    yet applied at close). Without this, ruling on the same converged
    edge twice in one circle — because nothing crossed it off — would
    silently queue two identical commands. A group whose edge (either
    direction) already appears in `issue_cmds` is dropped from the
    result entirely, not just marked.

    `[propose]` groups by normalized edge, using each speaker's LAST
    STANCE in the transcript, not raw occurrence — a part that proposed
    one direction and reversed after the reveal is counted once, in its
    final position (mirroring what the Learner did by hand in
    `circle_2026-08-09_1520`, circling_and_evolving.md §13). A malformed
    `[proposed: ...]` does not reach this function at all — it is reported
    and stripped at utterance, before the statement is appended (R274), so
    the `malformed_propose` key this used to return went 2026-08-20 (code
    review): nothing but a synthetic transcript could ever fill it.

    `[request]` never reaches this function at all — retired wholesale
    2026-08-16 (R202), folded into `[propose]`. RESCOPED the same day:
    `unruled_proposals()` now yields only issue-relationship-add-shaped propose records
    (see its own docstring) — every non-malformed one carries a real
    parsed edge at `n["cmd_shape"]["parsed"]` (issue_commands.parse()'s
    own cmd dict), not the old bespoke `n["edge"]` triple. Lost its
    `marks` parameter 2026-08-14 along with `unruled_proposals()`'s own, when
    MARK and PROPOSE MARK were retired wholesale (docs/BNF.md)."""
    props = unruled_proposals(transcript)

    queued_edges: set[tuple[str, str, str]] = set()
    for c in issue_cmds:
        if c.get("verb") == "issue-relationship-add":
            queued_edges.add(_normalize_edge((c["node"], c["type"], c["target"])))

    propose_groups: dict[tuple[str, str, str], dict] = {}

    for n in props:
        kind = n["kind"]
        if kind == "propose":
            p = n["cmd_shape"]["parsed"]
            edge = (p["node"], p["type"], p["target"])
            key = _normalize_edge(edge)
            if key in queued_edges:
                continue                      # already queued this circle
            g = propose_groups.setdefault(key, {})
            # LAST STANCE PER PART: transcript order is ascending by
            # index, so a later occurrence for the same display simply
            # overwrites an earlier one in this dict.
            g[n["display"]] = {"index": n["index"], "edge": edge, "text": n["text"]}

    propose = []
    for key, stances_by_speaker in propose_groups.items():
        stances = list(stances_by_speaker.values())
        directions = sorted({s["edge"] for s in stances})
        propose.append({
            "key": key,
            "speakers": sorted(stances_by_speaker),
            "unanimous": len(directions) == 1,
            "directions": directions,
            "stances": stances,
        })
    return {"propose": propose}


def show_unruled_proposals(props: list[dict]) -> None:
    """`props` is always `unruled_proposals()`'s own output — "propose" is the
    ONLY kind it can contain as of 2026-08-14 (practice/better_option
    kinds excluded 2026-08-12, then request, retired into its own
    staged/vetted register; hold retired into propose-mark, itself
    retired wholesale 2026-08-14, docs/BNF.md) — RESCOPED 2026-08-16
    (R202) to only an ADD-RELATION-shaped attempt — well-formed only, since
    2026-08-20: a malformed one is stripped at utterance and never reaches
    this list (R274) — (see unruled_proposals()'s own docstring for why:
    `propose` covers every future now, and everything else is
    comprehensively staged). Written
    to read `n["kind"]` rather than assume "propose" outright, so a
    future kind added back to unruled_proposals() fails loud (KeyError on the
    `head` lookup) instead of silently mislabeled."""
    if not props:
        return
    seam.emit("command", f"\n  {len(props)} ASK(S) from the room, unruled:")
    for n in props:
        body = ASK_RE.sub("", n["text"]).strip()
        head = {"propose": "PROPOSE an issue-relationship"}[n["kind"]]
        seam.emit("command", f"\n  [{n['index']}] {n['display']} — {head}")
        p = n["cmd_shape"]["parsed"]      # every row here parsed — see above
        seam.emit("command", f"        {p['node']} —{p['type']}→ {p['target']}")
        for line in _wrap58(body[:320]):
            seam.emit("command", f"        | {line}")
    seam.emit("command", "\n  Rule with /issue-relationship-add, or say nothing to "
          "leave it pending.")
    # "Close again" — Self read that and typed `close`, twice, and both went
    # to the room as Self statements because they had no leading slash. The
    # instruction named the act instead of the command, at the one moment the
    # reader is being asked to type a command. 2026-08-06.
    seam.emit("command", "  Type  /close  again to proceed.")


def _wrap58(s: str, w: int = 58):
    out, line = [], ""
    for word in s.split():
        if len(line) + len(word) + 1 > w:
            out.append(line); line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out
