#!/usr/bin/env python3
"""
inter_circle.py — the INTER_CIRCLE_PROCESSOR (R163: "between, not
cross"). DREAMING then SYNTHESIS for one closed circle, run synchronously
as `/close`'s SECOND phase (R167: the circle itself is already committed
before this starts) or by hand:

    python coordinator/inter_circle.py --ot 2026-08-15_1900 --live
    python coordinator/inter_circle.py --ot 2026-08-15_1900          (rehearse)

The bare form is the REHEARSAL: real model calls, real staging, the real
register gate — and then a report instead of a commit, staging kept for
inspection. `--live` commits. The `--ot` form IS R168's manual re-run
entry point: the same code `/close` calls, pointed at a closed circle.

THE SHAPE (docs/REGISTER_GATE_DESIGN.md, approved R188 — phase 2 writes
NOTHING directly):

    1  DREAMING     one model call per part, ALL PARTS IN PARALLEL (R170);
                    each RETURNS a payload — at most one memory — and
                    writes nothing. part_relationships.toml is NOT part
                    of this payload — see "part_relationships is INERT,"
                    below.
    2  SYNTHESIS    one circle-wide call, five inputs (R183 + R179 + R186):
                    transcript, each part's fresh dreaming record,
                    confirmed proposals, current self.md, the prior
                    CIRCLE_HISTORY entry
    3  VALIDATE     every payload against the writer-scope matrix and each
                    register's own rules (caps refuse, headings must hold)
    4  RENDER+STAGE each register module renders baseline + its own tail
                    (render_dreamt/render_new/render_stage — the same code
                    the direct writers use); Transaction stages the bytes
    5  GATE         ifs_model.compare_trees — the register gate judges
                    baseline vs candidate; any FAIL leaves the tree
                    untouched, staging kept
    6  COMMIT       Transaction.commit, then mid_term --refresh for the
                    parts whose hashes the writes flipped (R186/H3 — the
                    one direct-write step, guarded by mid_term's own
                    SUSPECT checks and hash stamp), then ONE git commit

FAILURE (R168): no automated catch-up. A failure writes
work/logs/dream_error_<OT>.json, makes ONE diagnostic model call (its own
failure is survived), prints the diagnosis and the re-run line, and exits
non-zero. All-or-nothing staging means a failed run wrote NOTHING, so the
re-run is clean by construction — no run markers, no author fields.

PRIVACY, mechanical: SYNTHESIS's input carries each part's ONE fresh
dreaming record, handed over in-process from the DREAMING payloads —
SYNTHESIS never reads any remember.toml, and the writer-scope matrix
(steps 3-4 stage only what a row grants) is enforced by construction
here and verified by the gate after.

LIVE-ONLY: non-live circles are skipped by the caller —
SYNTHESIS writes self/, which no sandbox may touch.

part_relationships IS INERT, 2026-08-22 (the operator: "inactivate all
code writing part_relationships.toml. Leave it in place and patch it out;
no LLM call(s)."). Follows R302, which had already removed the BLOCK 3
READ — this removes the WRITE too, so no part of DREAMING's prompt or
output spends any attention on it any more. part_relationships.py, the
seven parts/*/part_relationships.toml files, and ifs_model.REGISTERS'
own entry for the register are UNTOUCHED — a part's LAST converged
record from before this change simply stops updating. See NEXT.md,
"part-relationships-unconsumed," for what becomes of the register
itself.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import self_schema as SS                                       # noqa: E402
import remember as RM                                          # noqa: E402
import topics as TOP                                           # noqa: E402
import circle_history as CH                                    # noqa: E402
import self_observation_log as SO                              # noqa: E402
import check_best_practices as BPX                             # noqa: E402
import mid_term as MT                                          # noqa: E402
import transaction as T                                        # noqa: E402
import roster as R                                             # noqa: E402
import ifs_model as M                                          # noqa: E402  (B54)
import backfill as BF                                          # noqa: E402  (B54)
import command_surface as CS                                   # noqa: E402  dev_mode,
                                                               # attribute access only

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL = "claude-sonnet-5"       # circle.MODEL — the parts' own model
# RAISED 2026-08-21 (the operator: "raise the caps as you suggest"), after the
# lab circle 2026-08-21_1139: child and mourner stopped at max_tokens=4,000 with
# only ~4.5k chars of visible reply. A probe the same day showed why —
# claude-sonnet-5 THINKS ADAPTIVELY BY DEFAULT (a bare messages.create with no
# `thinking` parameter returned content blocks ['thinking', 'text']), and its
# thinking tokens COUNT AGAINST max_tokens. The visible document is the same
# size it always was; the budget it shares is not. 4,000 was "proven
# sufficient, 7/7 parts" only while the thinking stayed small.
DREAM_MAX_TOKENS = 8000         # was 4000 — see above
SYNTH_MAX_TOKENS = 12000        # was 8000: one circle-wide call across five
                                # sections — HISTORY alone is capped at CH.CAP
                                # (8000 chars) — needs more headroom than a
                                # single part's dreaming pass, and now also
                                # the room for the thinking above.
DIAG_MAX_TOKENS = 4000          # the diagnostic call is a few paragraphs

# ---------------------------------------------------------------- prompts
# VERSIONED CODE CONSTANTS (docs/INTER_CIRCLE_DESIGN.md) — the chain and
# format mechanics live here, never in a payload. One conformance against
# the ICD's committed text, flagged to its owner rather than silent: the
# "emit no other text at column 0" line is DROPPED — a self.md replacement
# CONTAINS column-0 `## ` headings, so the parser below splits on the exact
# header lines instead, each required once, in order.
#
# PART_RELATIONSHIP DROPPED, 2026-08-22 — see inter_circle's own module
# docstring, "part_relationships IS INERT." DREAMING asks for, and parses,
# MEMORY alone now.

DREAMING_PROMPT_V1 = """\
You are {part}'s dreaming pass for the circle that just closed ({ot}).

Below: your own identity as the circle sees it (your distillate); the closed circle's
transcript; your own short_term for it, if you spoke; and — if one exists — the most
recent memory in your own chain (a note your dreaming pass left for you last time,
including how charged it was, if you said so).

Write AT MOST ONE memory to carry forward to your own next circle. This is not a
summary of the circle — it is a note from you, to your future self, in your own voice,
about what to hold going into the next one. If a prior memory exists below, either
continue it (reference what it said, extend it) or let it stand and write nothing new
— a memory you choose not to change is not a failure. Keep it under {cap} characters.

OUTPUT FORMAT, exactly. Section headers, each alone on its own line, at column 0,
spelled exactly as shown. Print MEMORY even when it is empty — the header and nothing
under it. Print SALIENCE whenever MEMORY is not empty; omit it entirely (no header at
all) when MEMORY is empty. Print RESOLUTION only when it applies.

MEMORY
    Either one memory as plain prose, or — if you are continuing the prior memory
    rather than starting a new thread — a first line reading exactly "CONTINUES"
    followed by the memory. Empty if you are letting the prior memory stand.

SALIENCE
    Required whenever MEMORY is not empty. Your own sense of how charged this memory
    is — exactly one word: passing, notable, charged, or resolved. "passing" is
    ordinary; "notable" is worth a second look later; "charged" is something live and
    unsettled; "resolved" is a charge that has actually settled. Your own judgment,
    never a score anyone else assigns.

RESOLUTION
    Only if this memory resolves a prior memory you tagged "charged" — a line
    naming what settled. Leave the section entirely absent otherwise.
"""

SYNTHESIS_PROMPT_V2 = """\
You are the circle's synthesis pass for the circle that just closed ({ot}).
{n} parts attended: {roster}.

Below, in order: the closed circle's full transcript; the most recent dreaming record
for each part that produced one, written moments ago by that part's own dreaming pass;
every proposal Self confirmed during this circle; the CURRENT self.md, the standing
account of Self this circle may or may not have moved; the PREVIOUS circle's HISTORY
entry, so what you write continues an account rather than restarting one; and — if one
exists — the most recent observation in your own chain, a note your synthesis pass left
for Self last time, including how charged it was, if you said so.

Your job is to find what is TRUE OF THE CIRCLE — not of any one part. A thing only one
part said, that no other part took up and Self did not confirm, is that part's own
material and belongs to that part alone. Leave it there.

Condense syntactically. Coalesce semantically. Where several parts said one thing in
different words, say it once, in words none of them used. Where they genuinely disagreed,
that disagreement IS the finding — record it as a live tension, not as a split you resolve
on their behalf.

Emit only what is ACTIONABLE: something that changes what a future circle does, attends
to, or holds as settled. Observation with no consequence is not actionable. Say nothing
rather than pad.

OUTPUT FORMAT, exactly. Seven section headers, each alone on its own line, at column 0,
spelled exactly as shown, in this order. EVERY header must be printed even when that
section is empty — print the header and nothing under it.

HISTORY
    One durable entry for the circle record: what this circle was, and what moved. Prose,
    a part's-eye view of the whole rather than a summary of turns. Under {history_cap}
    characters.

OBSERVATION
    Appended to Self's own observation log. What you noticed about the CIRCLE as a
    working body — its pace, what it avoided, where it went easily. Addressed to Self,
    about the room, never about Self. If a prior observation exists below, either
    continue it — a first line reading exactly "CONTINUES" followed by the observation —
    or let it stand and leave this section EMPTY; an observation you choose not to
    change is not a failure. A new thread simply starts as plain prose.

SALIENCE
    Required whenever OBSERVATION is not empty — your own sense of how charged the
    observation is, exactly one word: passing, notable, charged, or resolved. "passing"
    is ordinary; "notable" is worth a second look later; "charged" is live and
    unsettled; "resolved" is a charge that has actually settled. Print the header with
    nothing under it when OBSERVATION is empty.

RESOLUTION
    Only filled if this observation resolves a prior observation you tagged "charged" —
    a line naming what settled. Print the header with nothing under it otherwise.

SELF
    A REPLACEMENT for self.md, in full, only if this circle genuinely moved the standing
    account of Self given below. Reproduce its section headings exactly; carry forward
    every section this circle did not touch, unchanged and verbatim. If nothing moved,
    leave this section EMPTY — that is the ordinary case, and an unnecessary rewrite of a
    standing document is a loss, not an update.

BLOCK 2 CANDIDATE
    Cross-part, part-agnostic material for the NEXT circle's working surface: an open
    question the room did not close, a tension worth naming aloud, an unconfirmed proposal
    worth discussing. This is what the next room will WORK ON. Each item one short
    paragraph, opening with "- ". It is a topic, never an instruction.

BLOCK 1 CANDIDATE
    Only for something that has genuinely SETTLED and should become how the circle
    behaves from now on — a practice, in the same register as the practices already in
    the prompt. Self must ratify each one before it lands, so propose sparingly: an item
    here asserts "this is now identity", and most circles will have none. Each item one
    short paragraph, opening with "- ".

BLOCK 2 CANDIDATE items reach the next circle's room UNVETTED, as topics for it to
examine (R184). BLOCK 1 CANDIDATE items reach no part until Self has ratified each one.
"""

DIAGNOSIS_PROMPT = """\
A between-circles processing run (DREAMING/SYNTHESIS) failed. Below is its error
report. Give a plain-English DIAGNOSIS (what most likely went wrong) and a REPAIR
RECOMMENDATION (what to check or try). Diagnostic only — you repair nothing.
"""


# Module-level, rebindable — test_inter_circle.py points this at a temp dir
# so exercising the R168 failure path cannot overwrite or delete a REAL
# dream_error_<OT>.json. It writes under a real circle's OT by necessity (the
# driver reads the transcript by that OT), so redirecting the WRITE is the
# only separation available. Same convention as topics.PATH.
SYN_HEADERS = ("HISTORY", "OBSERVATION", "SALIENCE", "RESOLUTION", "SELF",
               "BLOCK 2 CANDIDATE", "BLOCK 1 CANDIDATE")

# Appended to the SYNTHESIS system prompt for the ONE re-ask a cap breach
# earns (R192). Names the ACTUAL overshoot rather than repeating the original
# instruction louder: the first ask already said "under {history_cap}", so
# saying it again unchanged is the same request, and the model has no way to
# know by how much it missed.
_INSIST = """

--- THIS IS A SECOND ASK. YOUR PREVIOUS ANSWER WAS REFUSED. ---

Your HISTORY section was {got:,} characters. The register refuses anything
over {cap:,} and it does not truncate — an over-length answer is DISCARDED
whole and the previous circle's entry stands instead, so the account of this
circle is simply lost.

Write HISTORY again, under {target:,} characters. Every other section stays as
you judged it. Do not pad the shortfall elsewhere; cut HISTORY itself — decide
what this circle was ABOUT and say that, rather than covering everything that
happened in it."""


def _truncate_at(text: str, cap: int) -> str:
    """Cut `text` to at most `cap` characters at the LAST WHITESPACE before
    the cap — never mid-word — and strip the ragged end. The operator,
    2026-08-21: *"a cap-crunch must not cause a fail; report, but truncate
    at the cap and allow."* A text already within the cap comes back
    unchanged, byte for byte. A text with no whitespace before the cap is
    hard-cut at it rather than refused — the rule is truncate-and-allow."""
    if len(text) <= cap:
        return text
    cut = text[:cap]
    sp = max(cut.rfind(" "), cut.rfind("\n"), cut.rfind("\t"))
    if sp > 0:
        cut = cut[:sp]
    return cut.rstrip()


def _norm_len(s: str) -> int:
    """Length as circle_history.render_new() will measure it — it collapses
    whitespace before checking the cap, so measuring the raw section would
    over-count and trigger a re-ask that the register would have accepted."""
    return len(" ".join(s.split()))


def _usage_dict(u):
    """Token counts as a plain dict. anthropic's Usage is a pydantic model
    — no .get(), and iterating it yields (name, value) pairs, not keys —
    so the old dict-style merge below ALWAYS raised AttributeError on two
    real Usage objects and fell back to dropping the second one."""
    if u is None or isinstance(u, dict):
        return u
    dump = getattr(u, "model_dump", None)
    items = dump() if callable(dump) else vars(u)
    return {k: v for k, v in items.items() if isinstance(v, int)}


def _merge_usage(a, b):
    """Two calls' usage, summed where both are present. The re-ask is a REAL
    cost and must appear in the run's total; dropping it would under-report
    exactly the case worth watching. Returns a plain dict when it actually
    merged — _out_tokens() reads both shapes."""
    if a is None:
        return b
    if b is None:
        return a
    da, db = _usage_dict(a), _usage_dict(b)
    return {k: (da.get(k, 0) or 0) + (db.get(k, 0) or 0)
            for k in set(da) | set(db)}


def _out_tokens(u):
    """output_tokens off a Usage object OR a _merge_usage() dict."""
    if isinstance(u, dict):
        return u.get("output_tokens")
    return getattr(u, "output_tokens", None)


def _block_stats(blocks: list[str]) -> list[tuple[str, int]]:
    """(label, char count) for each block in a prompt built from '# label'
    sections — DREAMING's and SYNTHESIS's user messages, each a list of
    such blocks joined with blank lines. The label is the block's own
    heading line; the count is the block's FULL length including it, i.e.
    exactly what reaches the model, not just the body under the heading."""
    out = []
    for b in blocks:
        label = b.splitlines()[0].lstrip("#").strip() if b else "(empty)"
        out.append((label, len(b)))
    return out


def _report_chars(say, who: str, chars: dict) -> None:
    """Every LLM call in this module reports its own footprint through
    here: prompt chars (system + user) and reply chars; per-block chars too
    when the prompt was built from named '# ' sections rather than one blob
    (DREAMING, SYNTHESIS — not DIAGNOSIS, whose user message is a single
    JSON report with no block structure).

    DEV-ON DETAIL, 2026-08-21 — the operator, on the close he watched: dev
    OFF prints the headers and the errors only; dev ON prints this per-call
    footprint as well. "<part>: done — …", "FAILED —", "SUSPECT —",
    "TRUNCATED —", the phase lines and the diagnosis are never gated — those
    are what a person waiting on a close needs to read. CS.dev_mode is read
    by attribute, as every reader of that flag must (command_surface.py)."""
    if not CS.dev_mode:
        return
    system, user, reply = chars["system"], chars["user"], chars["reply"]
    say(f"  {who}: prompt {len(system) + len(user):,} chars "
        f"(system {len(system):,} + user {len(user):,}) — "
        f"reply {len(reply):,} chars")
    stats = _block_stats(chars.get("blocks") or [])
    if stats:
        w = max(len(label) for label, _ in stats)
        for label, n in stats:
            say(f"      {label:<{w}}  {n:,} chars")


LOGS = ROOT / "work" / "logs"


def _shown(p: pathlib.Path) -> str:
    """Tree-relative when it is, absolute when it is not. LOGS is rebindable
    (probes point it at a temp dir), and a bare relative_to() raises there —
    which turned a clean probe run into a traceback inside the very error
    path it was exercising."""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


class _Unparseable(RuntimeError):
    """A parse failure that CARRIES THE MODEL'S ACTUAL OUTPUT.

    The first rehearsal (2026-08-09_1520) failed on SYNTHESIS and the sample
    was discarded at the error return, so R168's diagnostic call was asked to
    explain an output it could not see. Its own first repair recommendation
    was "pull the raw synthesis output and inspect it" — which nothing had
    kept, and re-seeing it would have cost another 8 model calls.

    The raw text is written BESIDE the report as .txt rather than embedded in
    the JSON: it runs to tens of KB, and a report you must un-escape to read
    is a report nobody reads."""

    def __init__(self, msg: str, raw: str | None = None,
                 stop_reason: str | None = None,
                 output_tokens: int | None = None):
        super().__init__(msg)
        self.raw = raw
        self.stop_reason = stop_reason
        self.output_tokens = output_tokens


class _PostCommitFailed(RuntimeError):
    """The git commit failed AFTER Transaction.commit() already succeeded.

    DISTINCT from every other R168 failure in this module, which all happen
    BEFORE any live-tree write — their report's "the live tree is untouched"
    line is true for them and would be a LIE here. 2026-08-16: a live run
    against 2026-08-09_1520 hit exactly this (project_stats.py --check
    refused the commit) and `process_circle()` never checked
    `gitrepo.commit_paths()`'s return value at all — it printed "phase 2
    complete" and exited 0 on a run whose git commit never landed, while 25
    files sat modified and uncommitted in the live tree."""


# ----------------------------------------------------------------- parsing
def parse_sections(text: str, headers: tuple[str, ...],
                   optional: frozenset[str] = frozenset()
                   ) -> tuple[dict | None, str | None]:
    """Split model output on EXACT header lines, in order. A header NOT in
    `optional` is required exactly once — a missing, duplicated, or
    out-of-order required header refuses the whole output: fail loud,
    never guess (R168 hands it back). A header IN `optional` may appear
    zero or one times; absent, it is simply missing from the returned dict
    rather than a refusal — DESIGN_V2's SALIENCE/RESOLUTION lines, which
    "coerce ... never refuse the whole DREAMING call over one bad tag."
    Section bodies may contain anything — including column-0 `## `
    headings, which is why 'no other text at column 0' cannot be the
    rule."""
    lines = text.splitlines()
    pos: list[tuple[str, int]] = []
    for h in headers:
        hits = [i for i, l in enumerate(lines) if l.strip() == h and l == l.lstrip()]
        if h in optional:
            if len(hits) > 1:
                return None, (f"optional header {h!r} appears {len(hits)} "
                              f"times; expected at most once")
            if hits:
                pos.append((h, hits[0]))
            continue
        if len(hits) != 1:
            return None, (f"header {h!r} appears {len(hits)} time(s); "
                          f"expected exactly once")
        pos.append((h, hits[0]))
    if [i for _h, i in pos] != sorted(i for _h, i in pos):
        return None, "headers out of order"
    out = {}
    for k, (h, i) in enumerate(pos):
        end = pos[k + 1][1] if k + 1 < len(pos) else len(lines)
        out[h] = "\n".join(lines[i + 1:end]).strip("\n").strip()
    return out, None


def items_of(section: str) -> list[str]:
    """'- ' items, each possibly wrapping onto following lines."""
    out, cur = [], []
    for l in section.splitlines():
        if l.lstrip().startswith("- "):
            if cur:
                out.append(" ".join(cur))
            cur = [l.lstrip()[2:].strip()]
        elif cur and l.strip():
            cur.append(l.strip())
    if cur:
        out.append(" ".join(cur))
    return [x for x in out if x]


def _headings(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if l.startswith("## ")]


# ------------------------------------------------------------------- model
def _client():
    import os
    from anthropic import Anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except ImportError:
            pass
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("set ANTHROPIC_API_KEY (env var or project .env)")
    return Anthropic()


def _call(system: str, user: str, max_tokens: int) -> tuple[str, object, str]:
    """One call, its own client — a client per worker costs nothing and
    removes every thread-safety question (R170: the seven run in parallel).

    Returns (text, usage, stop_reason). stop_reason lives on the Message
    response itself, NOT on usage — Usage carries only token counts. An
    earlier version of the SYNTHESIS failure path read
    `usage._stop_reason`, an attribute that does not exist on either object,
    and so silently reported no stop_reason on every failure ever seen,
    including 2026-08-09_1520 — the one case that most needed it, to tell a
    genuine max_tokens truncation apart from the model stopping on its own."""
    resp = _client().messages.create(
        model=MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}])
    return ("".join(b.text for b in resp.content if b.type == "text").strip(),
            resp.usage, resp.stop_reason)


# ---------------------------------------------------------------- dreaming
def dream_one(part: str, ot: str, transcript: str) -> dict:
    """ONE part's dreaming pass — returns a PAYLOAD, writes nothing.
    A silent part (no short_term, maybe no statements) still dreams: the
    designed outcome for it is an unchanged document and an empty MEMORY,
    which is legal and non-SUSPECT."""
    tag = R.TAG_BY_DIR[part]
    distillate, _why = MT.block(part)
    st_path = ROOT / "parts" / part / f"short_term_{ot}.md"
    prior = RM.newest_dreamt(part)
    user = [f"# Your identity distillate\n{distillate or '(none on file)'}",
            f"# Transcript of circle {ot}\n{transcript}"]
    if st_path.is_file():
        st_text = st_path.read_text(encoding="utf-8")
        # R248, 2026-08-19: "Do mark reconstructions." The mark is only worth
        # writing if the reader that matters acts on it, and this is that
        # reader — a reconstruction was written from the transcript AFTER the
        # fact, and dreaming taking it for the part's own contemporaneous
        # record is exactly the blur the ruling refuses.
        head = "# Your short_term for this circle"
        if M.is_reconstructed(st_text):
            head += (" — RECONSTRUCTED from the transcript after the fact, "
                     "NOT what you wrote in the moment")
        user.append(f"{head}\n{st_text}")
    if prior:
        sal_note = f" (tagged {prior['salience']})" if prior.get("salience") else ""
        user.append(f"# The most recent memory in your chain{sal_note}\n"
                    f"{prior['text']}")
    system = DREAMING_PROMPT_V1.format(part=tag, ot=ot, cap=RM.RECORD_CAP)
    user_text = "\n\n".join(user)
    text, usage, stop_reason = _call(system, user_text, DREAM_MAX_TOKENS)
    chars = {"system": system, "user": user_text, "reply": text,
             "blocks": user}
    sections, err = parse_sections(
        text, ("MEMORY", "SALIENCE", "RESOLUTION"),
        optional=frozenset({"SALIENCE", "RESOLUTION"}))
    # output_tokens AND stop_reason RIDE EVERY PAYLOAD, 2026-08-21 — the two
    # numbers that told the 2026-08-21_1139 failure apart from a header
    # mismatch, and that the report did not carry at the time.
    if sections is None:
        # RAW OUTPUT KEPT. R168 promises a diagnosis, and an unparseable
        # output cannot be diagnosed from the error string alone — the first
        # rehearsal (2026-08-09_1520) failed here and the sample was gone,
        # so re-seeing it would have cost another 8 model calls.
        return {"part": part, "error": f"unparseable output: {err}",
                "raw": text, "usage": usage, "stop_reason": stop_reason,
                "output_tokens": _out_tokens(usage), "chars": chars}
    out: dict = {"part": part, "usage": usage, "suspect": [], "truncated": [],
                 "chars": chars, "stop_reason": stop_reason,
                 "output_tokens": _out_tokens(usage)}
    mem = sections["MEMORY"].strip()
    if mem:
        continues = mem.splitlines()[0].strip() == "CONTINUES"
        body = "\n".join(mem.splitlines()[1:]).strip() if continues else mem
        if not body:
            pass                        # bare CONTINUES = let it stand
        else:
            # Same rule for the memory: over the tolerance (1.5 x
            # RECORD_CAP, the most the register ever accepted whole) it is
            # TRUNCATED there and kept, not refused. render_dreamt() then
            # applies RECORD_CAP itself, as it always has.
            limit = int(RM.RECORD_CAP * 1.5)
            if len(body) > limit:
                was = len(body)
                body = _truncate_at(" ".join(body.split()), limit)
                out["truncated"].append(
                    f"memory TRUNCATED at {len(body):,} chars (was {was:,}; "
                    f"the {RM.RECORD_CAP}-char cap's tolerance is {limit})")
            out["memory"] = body
            # SALIENCE (DESIGN_V2), 2026-08-22: required whenever MEMORY is
            # non-empty, but an absent or unparseable answer COERCES rather
            # than refuses the call (RM.coerce_salience's own rule).
            sal_raw = sections.get("SALIENCE")
            out["salience"] = RM.coerce_salience(sal_raw)
            if sal_raw is None or sal_raw.strip().lower() not in RM.SALIENCE_VALUES:
                out["suspect"].append(
                    f"SALIENCE absent or unparseable ({sal_raw!r}) — "
                    f"coerced to 'passing'")
            # RESOLUTION also chains onto the prior memory, same mechanism
            # as a MEMORY-level "CONTINUES" — either one is sufficient.
            resolution = sections.get("RESOLUTION")
            resolved = bool(resolution and resolution.strip())
            if resolved and prior and prior.get("salience") != "charged":
                out["suspect"].append(
                    "RESOLUTION claimed but the prior memory in this "
                    f"chain was not tagged 'charged' (was "
                    f"{prior.get('salience')!r})")
            out["continues"] = continues or resolved
    return out


# --------------------------------------------------------------- synthesis
def synthesise(ot: str, transcript: str, payloads: list[dict],
               confirmed: list[dict], say=lambda _s: None) -> dict:
    dreams = []
    for p in payloads:
        if p.get("memory"):
            dreams.append(f"[{R.TAG_BY_DIR[p['part']]}] {p['memory']}")
    conf = [f"- {c['kind']} {c['id']}: {c['line']}" for c in confirmed]
    self_md = (ROOT / "self" / "self.md")
    self_now = self_md.read_text(encoding="utf-8") if self_md.is_file() else ""
    prior = CH.most_recent()
    prior_obs = SO.most_recent()          # R358: the chain the OBSERVATION
    user = [f"# Transcript of circle {ot}\n{transcript}",
            "# Each part's fresh dreaming record\n"
            + ("\n".join(dreams) if dreams else "(none produced one)"),
            "# Proposals Self confirmed this circle\n"
            + ("\n".join(conf) if conf else "(none)"),
            f"# The CURRENT self.md\n{self_now or '(absent)'}",
            "# The previous circle's HISTORY entry\n"
            + (f"{prior['id']} ({prior['circle']}): {prior['text']}"
               if prior else "(none — this is the first)"),
            "# The previous observation in your own chain\n"
            + ((f"{prior_obs['id']} ({prior_obs['circle']}"
                + (f", {prior_obs['salience']}"
                   if prior_obs.get("salience") else "")
                + f"): {prior_obs['text']}")
               if prior_obs else "(none — this is the first)")]
    # ASK FOR TARGET, REFUSE AT CAP (R192). The prompt names CH.TARGET
    # (7200); render_new() refuses at CH.CAP (8000). A model asked for
    # exactly its hard limit has no room to run slightly long without being
    # refused — and the whole run, seven DREAMING calls included, is lost to
    # a few dozen characters.
    system = SYNTHESIS_PROMPT_V2.format(
        ot=ot, n=len(R.DIR_NAMES), roster=", ".join(R.TAGS),
        history_cap=CH.TARGET)
    body = "\n\n".join(user)
    text, usage, stop_reason = _call(system, body, SYNTH_MAX_TOKENS)
    _report_chars(say, "synthesis", {"system": system, "user": body,
                                     "reply": text, "blocks": user})
    sections, err = parse_sections(text, SYN_HEADERS)

    # ONE INSISTENT RE-ASK ON A CAP BREACH (R192: "ask the LLM again and
    # insist"). Only when the overshoot would actually be REFUSED — an answer
    # between TARGET and CAP is within the headroom the target exists to
    # provide, and re-billing it would waste a call to buy nothing.
    #
    # Bounded at ONE retry: a model that ignores an explicit character count
    # twice will not comply on a third, and R168's hand-back is the honest
    # outcome there rather than a loop that spends money to reach it slowly.
    if sections is not None:
        n_hist = _norm_len(sections["HISTORY"])
        if n_hist > CH.CAP:
            say(f"  HISTORY {n_hist:,} chars — over the {CH.CAP:,} cap; "
                f"re-asking once, insisting")
            insisted_system = system + _INSIST.format(
                got=n_hist, cap=CH.CAP, target=CH.TARGET)
            text2, usage2, stop_reason2 = _call(insisted_system, body,
                                                SYNTH_MAX_TOKENS)
            _report_chars(say, "synthesis re-ask",
                         {"system": insisted_system, "user": body,
                          "reply": text2, "blocks": user})
            usage = _merge_usage(usage, usage2)
            s2, e2 = parse_sections(text2, SYN_HEADERS)
            if s2 is None:
                say(f"  the re-ask did not parse ({e2}) — keeping the first "
                    f"answer, which the cap will refuse")
            else:
                n2 = _norm_len(s2["HISTORY"])
                say(f"  re-ask returned {n2:,} chars"
                    + ("" if n2 <= CH.CAP
                       else " — still over; truncating at the cap"))
                sections, err, text, stop_reason = s2, e2, text2, stop_reason2

    if sections is None:
        return {"error": f"unparseable output: {err}", "raw": text,
                "usage": usage, "stop_reason": stop_reason,
                "output_tokens": _out_tokens(usage)}
    out = {"usage": usage, "suspect": [], "truncated": [], "sections": sections,
           "stop_reason": stop_reason, "output_tokens": _out_tokens(usage)}
    # A CAP CRUNCH IS TRUNCATED AND ALLOWED, 2026-08-21 (the operator's rule,
    # see dream_one). CH.render_new() still REFUSES over CH.CAP — that is the
    # register's own guard and does not move — so the HISTORY it is handed
    # is already cut to the cap, whitespace-aware, on the same normalized
    # text render_new measures. Reported, never silent.
    n_hist = _norm_len(sections["HISTORY"])
    if n_hist > CH.CAP:
        norm = " ".join(sections["HISTORY"].split())
        cut = _truncate_at(norm, CH.CAP)
        sections = dict(sections, HISTORY=cut)
        out["sections"] = sections
        out["truncated"].append(
            f"HISTORY TRUNCATED at {len(cut):,} chars (was {n_hist:,}; cap "
            f"{CH.CAP:,}) — the insistent re-ask did not bring it under")
    # THE OBSERVATION FOLLOWS THE DREAMING MODEL (R358): CONTINUES chains
    # onto the prior observation, SALIENCE coerces rather than refuses, a
    # RESOLUTION also chains, and a bare CONTINUES lets the prior stand —
    # dream_one's own rules, applied to the circle's reflexive record.
    obs = sections["OBSERVATION"].strip()
    if obs:
        o_cont = obs.splitlines()[0].strip() == "CONTINUES"
        o_body = "\n".join(obs.splitlines()[1:]).strip() if o_cont else obs
        if o_body:
            out["observation"] = o_body
            sal_raw = sections.get("SALIENCE")
            out["obs_salience"] = RM.coerce_salience(sal_raw)
            if (sal_raw is None
                    or sal_raw.strip().lower() not in RM.SALIENCE_VALUES):
                out["suspect"].append(
                    f"OBSERVATION SALIENCE absent or unparseable "
                    f"({sal_raw!r}) — coerced to 'passing'")
            resolution = sections.get("RESOLUTION")
            resolved = bool(resolution and resolution.strip())
            if resolved and prior_obs and prior_obs.get("salience") != "charged":
                out["suspect"].append(
                    "OBSERVATION RESOLUTION claimed but the prior "
                    f"observation was not tagged 'charged' (was "
                    f"{prior_obs.get('salience')!r})")
            out["obs_continues"] = o_cont or resolved
        # a bare CONTINUES lets the prior observation stand — nothing staged

    self_new = sections["SELF"].strip()
    if self_new:
        if set(_headings(self_new)) != set(_headings(self_now)):
            out["suspect"].append(
                "SELF replacement changes self.md's heading set — a dropped "
                "section is silent loss; refused, self.md stands")
        else:
            out["self_md"] = self_new
    return out


# ------------------------------------------------------------------ driver
def _stage_toml(tx: T.Transaction, rel: str, doc: dict, table: str,
                order: tuple[str, ...]) -> None:
    tx.stage(rel, SS.dumps(doc, table, order).encode("utf-8"))


def _load_or(p: pathlib.Path, empty: dict) -> dict:
    return SS.load(p) if p.is_file() else empty


def already_processed(ot: str) -> bool:
    """Has phase 2 ALREADY run to completion for this circle? The second
    commit's own `dream/<OT>` tag is the durable marker — all-or-nothing
    staging makes a FAILED run leave nothing, so the tag exists exactly
    when a run succeeded. This is the run-marker H6 deliberately did not
    build into the records themselves; the tag carries it instead.

    Through gitrepo.run() since 2026-08-19 (review tier 2): the raw
    subprocess call had no timeout (git hung by AV = phase 2 blocked
    forever, before touching anything) and let a missing git binary raise
    a bare FileNotFoundError. And this guard must NEVER answer "not
    processed" because git itself failed — that answer double-dreams —
    so a nonzero rc raises rather than reading as False.

    TWO MARKERS SINCE 2026-08-24, EITHER OF WHICH REFUSES A RE-RUN. The
    operator ruled git OPTIONAL that day, so the tag can no longer be the
    only place this answer lives — a tree with no git history has nowhere
    to keep one. `work/logs/dream_<OT>.json` is the file form, written
    last by a successful run.

        marker file present         -> processed. No git consulted.
        no .git in the tree at all  -> the file is the WHOLE record, and it
                                       said no. A tree that never had a
                                       history cannot be hiding a tag.
        .git present, git answers   -> the tag, exactly as before.
        .git present, git does NOT
          answer                    -> RAISE, exactly as before.

    THE RAISE IS NOT WEAKENED, IT IS SCOPED. It was unconditional, and
    that is what broke: `git tag -l` exits 128 outside a repository, so a
    freshly installed bundle met this guard as an uncaught GitError and
    CRASHED every live /close after the transcript was already safely
    written (measured 2026-08-24 in a built bundle). The invariant the
    raise protects — never answer "not processed" because git FAILED —
    only has meaning where a tag could exist. Where `.git` is absent no
    tag can exist, so there is nothing to be wrong about; where `.git` is
    present and git still cannot answer, something is wrong and this
    refuses to guess, as it always did."""
    import gitrepo as G
    if dream_marker(ot).is_file():
        return True
    if not git_history_here():
        return False
    # THE READER USES THE SAME NAMER AS THE WRITER (B56(5), R245): in a
    # lab tree this asks about `dream/lab/<OT>`, which is what a lab run
    # writes. Asking about the plain name there would never find the
    # marker and would re-dream every run — the guard dead in exactly the
    # venue meant to rehearse it.
    tag = G.tag_name("dream", ot)
    rc, out = G.run("tag", "-l", tag, read_only=True)
    if rc != 0:
        raise G.GitError(f"git tag -l {tag} -> {rc}: {out} — cannot "
                         f"tell whether this circle was already dreamt")
    return bool(out.strip())


def backfill_step(ot: str, say) -> int:
    """STEP 0 of every live close: a part that SPOKE never reaches dreaming as
    if it had been silent. B54, 2026-08-19.

    THE GAP THIS CLOSES. Detection and repair both existed, in circle_audit's
    phases 2 and 3, and NOTHING CALLED EITHER on this path — the one that runs
    synchronously at every live /close since B3/R189, with dreaming as the
    first thing it does. dream_one() guards the short_term on a bare
    `is_file()`, and a silent part is a designed, legal, non-SUSPECT outcome,
    so a part that spoke and lost its record simply did not move that circle.
    No error anywhere.

    HERE, NOT IN circle.py's /close, and B54 named the trade: a step 0 inside
    process_circle keeps the manual `--ot` re-run covered by the same guard,
    where a call from /close would leave that path bare. It costs
    inter_circle a second responsibility, which is the price.

    WARN-REPAIR-RECORD, not refuse. Refusing to process would lose the circle
    over a record that can be rebuilt. Every reconstruction is MARKED (R248,
    "Do mark reconstructions") and dreaming is told which kind of record it
    has — see dream_one.

    THE ORDERING IS THE WHOLE POINT and was already written down in
    circle_audit's own failure text: *backfill from the transcript before
    dreaming*. A repair that runs after dreaming fixes the file and not the
    dream, which is the part that mattered.

    Returns 0 to continue. Non-zero only if a repair was needed and could not
    be made — dreaming on a record known to be missing would bake the loss in."""
    todo = BF.needs_backfill(ot)
    if not todo:
        return 0
    say(f"\n  transcript safety net — {len(todo)} part(s) spoke with no usable "
        f"record. Reconstructing before dreaming; this adds {len(todo)} model "
        f"call(s) to this close.")
    import prompt_build as C
    core = C.load_shared()
    briefing, _ = C.build_briefing([], False)
    failed: list[str] = []
    for part, n, why in todo:
        say(f"    {part}: spoke {n}x — {why}")
        shared, _ = C.shared_block(part, briefing, False)
        system = C.system_blocks(part, core, shared)
        text, err = BF.reconstruct(part, ot, R.TAG_BY_DIR[part], system, _call)
        if err:
            failed.append(f"{part}: {err}")
            say(f"    {part}: RECONSTRUCTION FAILED — {err}")
            continue
        (ROOT / "parts" / part / f"short_term_{ot}.md").write_text(
            text, encoding="utf-8", newline="\n")
        say(f"    {part}: reconstructed and MARKED ({len(text.split())} words)")
    if failed:
        say(f"\n  {len(failed)} record(s) could not be reconstructed. Dreaming "
            f"on a record known to be missing would bake the loss into the "
            f"part's identity, so this close's processing stops here.")
        return 1
    return 0


def first_synthesis_here() -> bool:
    """Has phase 2 EVER completed in this tree? The shrink waiver's own
    test — R348, the operator's "(a)"
    (2026-08-25): the FIRST synthesis replaces the shipped seed self.md,
    not a record, so compare_trees waives its shrink tolerance for that
    one run. Evidence mirrors already_processed()'s two markers: any
    `dream_<OT>.json` run marker (the [0-9] glob keeps the
    `dream_error_*` reports beside them from counting as runs), else any
    `dream/*` tag where there is a git history.

    WRONG-ANSWER ASYMMETRY, deliberate: git UNABLE to answer reads as NOT
    first — a waiver granted on a mature tree strips the very protection
    the gate exists for, while one withheld on a fresh tree merely
    reproduces today's refusal, loudly."""
    if any(LOGS.glob("dream_[0-9]*.json")):
        return False
    if not git_history_here():
        return True
    try:
        import gitrepo as G
        rc, out = G.run("tag", "-l", "dream/*", read_only=True)
    except Exception:                                       # noqa: BLE001
        return False
    if rc != 0:
        return False
    return not out.strip()


def dream_marker(ot: str) -> pathlib.Path:
    """`work/logs/dream_<OT>.json` — the run marker's FILE form, and the
    twin of the `dream_error_<OT>.json` that has always sat beside it.
    Written as the last act of a successful run; see write_dream_marker()."""
    return LOGS / f"dream_{ot}.json"


def git_history_here() -> bool:
    """Does this tree keep a git history at all? A FILESYSTEM test, no
    subprocess — so it answers the same on a machine with no git binary
    installed as on one that has it.

    `.git` is a directory in a main checkout and a FILE (the `gitdir:`
    pointer) in a worktree, so `.exists()` and not `.is_dir()` — the same
    distinction gitrepo.in_main_checkout() turns the other way."""
    return (ROOT / ".git").exists()


def write_dream_marker(ot: str, *, committed: bool, tag: str | None) -> None:
    """Record that phase 2 ran to completion for this circle. Called ONCE,
    last, after the commit step — so a run that died earlier leaves no
    marker and its re-run is clean, the same property the tag has.

    THE TAG REMAINS AUTHORITATIVE WHEREVER THERE IS ONE. This file does
    not replace it; already_processed() reads either, and in a tree with a
    git history the tag is what a failed commit still guarantees. The file
    exists for the tree that has no history to hold a tag."""
    LOGS.mkdir(parents=True, exist_ok=True)
    rec = {"ot": ot, "processed_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "committed": committed, "tag": tag,
           "note": "phase 2 (dreaming + synthesis) completed for this circle. "
                   "already_processed() reads this file OR the git tag; either "
                   "one refuses a re-run. Delete it only if you mean to dream "
                   "this circle again."}
    dream_marker(ot).write_text(json.dumps(rec, indent=2) + "\n",
                                encoding="utf-8", newline="\n")


def process_circle(ot: str, live: bool, confirmed: list[dict] | None = None,
                   say=print) -> int:
    """Phase 2, whole. Returns 0 on success; non-zero means the circle's
    own record is UNTOUCHED and work/logs/dream_error_<OT>.json says why."""
    confirmed = confirmed or []
    if already_processed(ot):
        say(f"  circle {ot} is already processed (git tag dream/{ot}) — "
            f"re-running would double-dream it. Delete the tag first if "
            f"you mean it.")
        return 1
    tpath = ROOT / "circles" / f"circle_{ot}.md"
    try:
        transcript = tpath.read_text(encoding="utf-8")
    except FileNotFoundError:
        say(f"  no transcript at {tpath.relative_to(ROOT)} — is {ot!r} a "
            f"closed LIVE circle?")
        return 1
    if live:
        rc0 = backfill_step(ot, say)
        if rc0:
            return rc0
    parts = R.DIR_NAMES
    say(f"\ndreaming — {len(parts)} parts, in parallel ({MODEL}):")
    payloads: list[dict] = []
    errors: list[str] = []
    try:
        for p in parts:
            say(f"  {p}: started")
        with concurrent.futures.ThreadPoolExecutor(len(parts)) as ex:
            futs = {ex.submit(dream_one, p, ot, transcript): p for p in parts}
            for f in concurrent.futures.as_completed(futs):
                pay = f.result()
                payloads.append(pay)
                if pay.get("chars"):
                    _report_chars(say, pay["part"], pay["chars"])
                what = []
                if pay.get("memory"):
                    what.append("memory"
                                + (f" ({pay['salience']})" if pay.get("salience")
                                   else "")
                                + (" (continues)" if pay.get("continues")
                                   else ""))
                for s in pay.get("truncated", []):
                    say(f"  {pay['part']}: TRUNCATED — {s}")
                for s in pay.get("suspect", []):
                    say(f"  {pay['part']}: SUSPECT — {s}")
                # THE TWO NUMBERS THAT EXPLAIN A TRUNCATION, on every line
                # since 2026-08-21: how many output tokens the call spent
                # (thinking included — see DREAM_MAX_TOKENS) and why it
                # stopped.
                tok = pay.get("output_tokens")
                sr = pay.get("stop_reason")
                spent = (f" [{tok:,} output tokens" if tok is not None else "")
                spent += (f"{', ' if spent else ' ['}{sr}" if sr else "")
                spent += "]" if spent else ""
                if pay.get("error"):
                    errors.append(f"{pay['part']}: {pay['error']}"
                                  + (f" (stop_reason={sr})" if sr else "")
                                  + (f" (output_tokens={tok})"
                                     if tok is not None else ""))
                    say(f"  {pay['part']}: FAILED — {pay['error']}{spent}")
                else:
                    say(f"  {pay['part']}: done"
                        + (f" — {', '.join(what)}" if what
                           else " — nothing to carry") + spent)
        if errors:
            raise _Unparseable(
                "DREAMING: " + "; ".join(errors),
                "\n\n".join(f"--- {p.get('part', '?')} ---\n{p['raw']}"
                            for p in payloads if p.get("raw")))

        say("\nsynthesis — one circle-wide call:")
        syn = synthesise(ot, transcript, payloads, confirmed, say)
        if syn.get("error"):
            raise _Unparseable(f"SYNTHESIS: {syn['error']}", syn.get("raw"),
                               syn.get("stop_reason"), syn.get("output_tokens"))
        for s in syn.get("truncated", []):
            say(f"  TRUNCATED — {s}")
        for s in syn.get("suspect", []):
            say(f"  SUSPECT — {s}")

        say("\nstaging + gate:")
        tx = T.Transaction(ROOT, f"dream_{ot}")
        # DESIGN_V2 LONG_TERM_CANDIDATE (2026-08-22): a qualifying chain
        # (3+ records, this run's own terminal record "resolved", a prior
        # link notable/charged) surfaces ONE topics.toml row per part —
        # never an auto-write to long_term.md itself. Collected here, over
        # THIS run's own new record only, so a chain that already
        # qualified in a PRIOR run is never re-surfaced on every run after.
        lt_candidates: list[tuple[str, dict]] = []
        for pay in sorted(payloads, key=lambda x: x["part"]):
            part = pay["part"]
            if pay.get("memory"):
                doc, rec = RM.render_dreamt(
                    _load_or(RM._real_path(part), {RM.TABLE: []}),
                    pay["memory"], ot, pay.get("continues", False),
                    salience=pay.get("salience"))
                _stage_toml(tx, f"parts/{part}/remember.toml", doc,
                            RM.TABLE, RM.ORDER)
                if RM.qualifying_chain(doc, rec):
                    lt_candidates.append((part, rec))
            # part_relationships.toml: NOT staged, 2026-08-22 — see
            # inter_circle's own module docstring, "part_relationships IS
            # INERT." DREAMING no longer produces a rel_doc at all.
        for part, rec in lt_candidates:
            say(f"  {part}: LONG_TERM CANDIDATE — a resolved chain of 3+ "
                f"reached self/topics.toml for review, never auto-written "
                f"to long_term.md")
        secs = syn["sections"]
        if secs["HISTORY"].strip():
            doc, _rec = CH.render_new(CH._doc(), ot, secs["HISTORY"])
            _stage_toml(tx, "self/circle_history.toml", doc, CH.TABLE,
                        CH.ORDER)
        if syn.get("observation"):
            # A REGISTER since 2026-08-19 (R256) — was a raw
            # append to self/self_observation_log.md, whose "## Circle <OT>
            # — synthesis" heading carried the only structure it had.
            # R358: the parsed body (CONTINUES prefix stripped), with the
            # dreaming-model fields; a bare CONTINUES staged nothing above.
            doc, _rec = SO.render_new(SO._doc(), ot, syn["observation"],
                                      salience=syn.get("obs_salience"),
                                      continues=bool(syn.get("obs_continues")))
            _stage_toml(tx, "self/self_observation_log.toml", doc,
                        SO.TABLE, SO.ORDER)
        if syn.get("self_md"):
            tx.stage("self/self.md", (syn["self_md"] + "\n").encode("utf-8"))
        tdoc = TOP._doc()
        for item in items_of(secs["BLOCK 2 CANDIDATE"]):
            tdoc, _rec = TOP.render_new(tdoc, ot, item)
        # LONG_TERM_CANDIDATE rows ride the SAME register SYNTHESIS's own
        # BLOCK 2 CANDIDATE already uses (DESIGN_V2's own words) — no new
        # field, a human-legible prefix distinguishes them in the listing.
        for part, rec in lt_candidates:
            tag = R.TAG_BY_DIR[part]
            tdoc, _rec2 = TOP.render_new(
                tdoc, ot, f"LONG_TERM CANDIDATE [{tag}]: {rec['text']}")
        bdoc = BPX._doc()
        for item in items_of(secs["BLOCK 1 CANDIDATE"]):
            bdoc, _pid = BPX.render_stage(bdoc, "add", addressee="All parts",
                                          title=item, sources=["synthesis"],
                                          circle=f"circle_{ot}")
        if items_of(secs["BLOCK 2 CANDIDATE"]) or lt_candidates:
            _stage_toml(tx, "self/topics.toml", tdoc, TOP.TABLE, TOP.ORDER)
        if items_of(secs["BLOCK 1 CANDIDATE"]):
            _stage_toml(tx, "self/best_practices.toml", bdoc,
                        "practice", BPX.ORDER)
        staged = tx.changed()
        say(f"  {len(staged)} file(s) staged: "
            + (", ".join(staged) if staged else "nothing to write"))
        first = first_synthesis_here()
        if first:
            say("  first synthesis of this tree — self.md's shrink "
                "tolerance is waived this once: the seed is not yet a "
                "record (R348)")
        findings = tx.validate(first_synthesis=first)
        fails = [f for f in findings if f.level == "FAIL"]
        for f in fails:
            say(f"  GATE FAIL  {f.path}: {f.message}")
        if fails:
            raise RuntimeError(
                f"register gate refused {len(fails)} finding(s) — the live "
                f"tree is untouched; staging kept at {tx.staging}")
        if not live:
            say("\nREHEARSAL — gate green, nothing committed. Staging kept "
                "for inspection; rerun with --live to commit.")
            return 0
        if staged and not tx.commit(lambda lvl, msg: say(f"  {lvl}  {msg}")):
            raise RuntimeError("Transaction.commit refused — see above")

        # PAST tx.commit(), THE LIVE TREE IS ALREADY UPDATED (whenever
        # anything was staged). Anything that RAISES from here on —
        # MT.refresh()'s raw messages.create (no retry ladder; one
        # transient 529 does it), the gitrepo import, commit_paths raising
        # GitError or TimeoutExpired instead of returning False — used to
        # fall through to the generic R168 handler, whose report claims
        # "the live tree is untouched; the re-run below starts clean" and
        # prints the re-run command. Both halves were lies in this window:
        # no dream/<OT> tag exists yet, so already_processed() reads False
        # and the advised re-run would DREAM AGAIN on top of the committed
        # content. Since 2026-08-19 every raise in this window is wrapped
        # into _PostCommitFailed, whose report shape tells the truth. When
        # nothing was staged the tree really is untouched (mid_term.md is
        # a re-derivable cache, not part of the record), so the generic
        # handler stays correct there and the raise passes through.
        try:
            say("\nmid_term refresh — stale parts only (R186/H3):")
            mt_fails = MT.refresh(say=say)
            if mt_fails:
                say(f"  {mt_fails} SUSPECT derivation(s) NOT written — rerun "
                    f"mid_term --refresh by hand; everything else committed")

            import gitrepo as G
            paths = [ROOT / rel for rel in staged]
            paths += [MT.path(p) for p in parts if MT.path(p).is_file()]
            committed, tag = False, None
            # NO GIT HISTORY IS A SUPPORTED TREE SINCE 2026-08-24, ruled by
            # the operator ("Tier 1"): a distributed bundle that was never
            # `git init`ed dreams and synthesises like any other, and
            # records the run in work/logs/dream_<OT>.json instead of a
            # tag. The commit is SKIPPED there rather than attempted and
            # failed — commit_paths() would warn "not a git repository" and
            # return False, which the branch below reads as a REFUSED
            # commit and escalates to _PostCommitFailed. Absent is not
            # refused, and telling a recipient their record is "REAL and
            # UNCOMMITTED" in a tree that commits nothing would be a
            # warning about the design working.
            if staged and not git_history_here():
                say("  no git history in this tree — the run's output is "
                    "written but not committed. "
                    f"work/logs/dream_{ot}.json records that this circle "
                    f"was processed; that file is what refuses a re-run "
                    f"here, in place of the dream/{ot} tag.")
            elif staged and not G.identity_known():
                # git is HERE but unconfigured — the fresh-install case,
                # R349 (2026-08-25): the same
                # skip as the tier above, never a refusal escalated to
                # _PostCommitFailed. The marker below still refuses a
                # re-run; this circle's record stays uncommitted until a
                # hand `git add` after git learns an identity.
                G.report_unconfigured(lambda lvl, msg: say(f"  {lvl}  {msg}"))
                say("  git is not configured — the run's output is written "
                    "but not committed. "
                    f"work/logs/dream_{ot}.json records that this circle "
                    f"was processed; that file is what refuses a re-run "
                    f"here, in place of the dream/{ot} tag.")
            elif staged:
                tag = G.tag_name("dream", ot)
                committed = G.commit_paths(
                    paths, f"dream/synthesis for circle {ot}",
                    lambda lvl, msg: say(f"  {lvl}  {msg}"),
                    tag=tag)
                if not committed:
                    raise _PostCommitFailed(
                        f"the live tree was already updated ({len(staged)} "
                        f"file(s), via Transaction.commit) before the git "
                        f"commit failed — see the 'fail' line above for why. "
                        f"These changes are REAL and UNCOMMITTED, not "
                        f"discarded. Do NOT re-run inter_circle.py for {ot} — "
                        f"already_processed() still reads False (no "
                        f"dream/{ot} tag), so a re-run would DREAM AGAIN on "
                        f"top of this uncommitted content. Fix whatever the "
                        f"commit gate refused, then `git add` and `git commit` "
                        f"the pending paths by hand.")
            else:
                say("  nothing changed — no second commit for this circle")
            # THE LAST ACT, DELIBERATELY. A run that died anywhere above
            # leaves no marker, so its re-run is clean — the same property
            # all-or-nothing staging gives the tag, kept by writing this
            # only once everything else has succeeded.
            write_dream_marker(ot, committed=committed, tag=tag)
            say(f"\nphase 2 complete for {ot}.")
            return 0
        except _PostCommitFailed:
            raise
        except Exception as e:
            if not staged:
                raise                  # tree untouched — R168's report is true
            raise _PostCommitFailed(
                f"the live tree was already updated ({len(staged)} file(s), "
                f"via Transaction.commit) when this failed: "
                f"{type(e).__name__}: {e}. The committed changes are REAL. "
                f"Do NOT re-run inter_circle.py for {ot} — "
                f"already_processed() still reads False (no dream/{ot} tag), "
                f"so a re-run would DREAM AGAIN on top of them. Fix the "
                f"cause, then `git add` and `git commit` the pending paths "
                f"by hand (a mid_term refresh that died mid-way can be "
                f"re-run safely: mid_term.py --refresh).") from e

    except _PostCommitFailed as e:
        # See the class docstring: the live tree IS modified here, so this
        # gets its own report shape rather than R168's generic one, which
        # would falsely claim "the live tree is untouched" and suggest a
        # re-run that would double-dream on top of the uncommitted content.
        report = {"ot": ot, "error": str(e),
                 "note": "PARTIAL SUCCESS, NOT a clean failure: dreaming and "
                         "synthesis both completed and Transaction.commit "
                         "already wrote their output into the live tree — "
                         "only the git commit itself failed. Do not re-run "
                         "this OT; fix the commit gate and commit by hand."}
        rp = LOGS / f"dream_error_{ot}.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, indent=2), encoding="utf-8",
                      newline="\n")
        say(f"\n!! phase 2 committed the live tree but NOT git — "
            f"report: {_shown(rp)}")
        say(f"\n{e}")
        return 1

    except Exception as e:                                     # R168
        report = {
            "ot": ot, "error": f"{type(e).__name__}: {e}",
            "payload_errors": errors,
            "parts_done": sorted(p.get("part", "?") for p in payloads),
            # PER PART, 2026-08-21: what each call spent and why it stopped —
            # the two facts the 2026-08-21_1139 report lacked, and the ones
            # that tell "the model thought the budget away" from "the model
            # renamed a header".
            "parts": [{"part": p.get("part", "?"),
                       "output_tokens": p.get("output_tokens"),
                       "stop_reason": p.get("stop_reason"),
                       **({"error": p["error"]} if p.get("error") else {})}
                      for p in sorted(payloads, key=lambda x: x.get("part", ""))],
            "dream_max_tokens": DREAM_MAX_TOKENS,
            "synth_max_tokens": SYNTH_MAX_TOKENS,
            "note": "all-or-nothing staging: the live tree is untouched; "
                    "the re-run below starts clean",
        }
        sr = getattr(e, "stop_reason", None)
        if sr:
            report["stop_reason"] = sr
        ot_used = getattr(e, "output_tokens", None)
        if ot_used is not None:
            report["output_tokens"] = ot_used
        rp = LOGS / f"dream_error_{ot}.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        raw = getattr(e, "raw", None)
        # `is not None`, NOT truthiness. _call() returns "" when the response
        # carries no text block at all, and an empty answer is precisely the
        # case worth seeing — the first two capture attempts wrote nothing
        # here for exactly that reason, and the report said raw_output: null
        # while looking like the capture had simply not run.
        if raw is not None:
            xp = rp.with_name(f"dream_error_{ot}_raw.txt")
            xp.write_text(raw, encoding="utf-8", newline="\n")
            report["raw_output"] = _shown(xp)
            # The diagnostic call gets a SAMPLE inline, head AND tail: the two
            # failure modes it must tell apart are a decorated/renamed header
            # (visible at the top) and truncation (visible only at the end).
            report["raw_len"] = len(raw)
            report["raw_head"] = raw[:1500]
            report["raw_tail"] = raw[-800:] if len(raw) > 2300 else ""
            if not raw:
                report["raw_note"] = (
                    "THE MODEL RETURNED NO TEXT AT ALL — not a header "
                    "mismatch. Check stop_reason below: 'max_tokens' means "
                    "the answer was truncated to nothing useful; anything "
                    "else means the response carried no text block.")
        rp.write_text(json.dumps(report, indent=2), encoding="utf-8",
                      newline="\n")
        say(f"\n!! phase 2 FAILED — report: {_shown(rp)}")
        try:
            diag_user = json.dumps(report, indent=2)
            diag, _u, _sr = _call(DIAGNOSIS_PROMPT, diag_user, DIAG_MAX_TOKENS)
            _report_chars(say, "diagnosis", {"system": DIAGNOSIS_PROMPT,
                                             "user": diag_user, "reply": diag})
            say(f"\ndiagnosis (one model call, diagnostic only):\n{diag}")
        except Exception as e2:
            say(f"  (diagnosis call itself failed: {e2} — the report above "
                f"stands on its own)")
        # The "circle already committed" line is only true on the /close path.
        # A --ot run is a re-run or a rehearsal against a circle committed long
        # ago, and telling the operator his circle "closed and committed
        # BEFORE this phase" reads as news about THIS run when it is not.
        # Caught on the first rehearsal, 2026-08-09_1520.
        if raw:
            say(f"\nThe model's actual output is kept at "
                f"{report['raw_output']} — read it before changing anything.")
        say(f"\nDreaming/synthesis did not run to completion, and NOTHING was "
            f"written: the live tree is byte-identical to before this run.\n"
            f"Re-run by hand — note this re-runs every DREAMING call too, "
            f"not only the step that failed:\n"
            f"    python coordinator/inter_circle.py --ot {ot} --live")
        return 1


def main() -> int:
    a = sys.argv[1:]
    if "--ot" not in a:
        print("usage: inter_circle.py --ot <OT> [--live]")
        return 1
    ot = a[a.index("--ot") + 1]
    return process_circle(ot, live="--live" in a)


if __name__ == "__main__":
    raise SystemExit(main())
