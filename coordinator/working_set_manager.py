#!/usr/bin/env python3
"""
working_set_manager.py — the WORKING SET: which issues a circle is shown.

    the question at open      WORKING_SET_PROMPT, working_set_ask()   (was circle.py's)
    the register              self/working_sets.toml — WORKING_SETS, working_set_record(),
                              _withdraw_working_set()               (was transcript_store.py's)
    the id parsers            issue_id_normalise(), working_set_argv_parse() (argv), working_set_parse()
                              (a typed line)                         (three copies, now one)
    the neighbour pull        working_set_pull() — the one-hop closure issue_index.issue_working_set_read()
                              and issue_draw.issue_working_set_limit() each wrote for themselves

CONVERGED 2026-09-03 (cohesion re-homing stage 10, NEXT.md B99; WORKING_SET became a BNF class
by Q-C, and this module is its manager under R435). Everything here was characterized FIRST by
coordinator/tests/test_working_set_manager.py against its old homes, and the same probe holds
after the move — the proof for the two functions that changed shape: working_set_ask() takes its
reader as a parameter (circle.py passes read_line_no_annotation, so R225's refusal of an
annotation at this prompt stays the driver's), and the pull takes a `neighbours` callback
(issue_index's is undirected over live_edges, issue_draw's directed over edges). The rest is the
verbatim body each function had before.

RENAMED AT THE MOVE (R436, R442 — 2026-09-03), the class word first, the bodies untouched:

    ask_working_set          -> working_set_ask
    record_working_set       -> working_set_record
    parse_working_set_pairs  -> working_set_parse         a typed line
    parse_working_set        -> working_set_argv_parse    a tool's argv
    normalise_id             -> issue_id_normalise        an ISSUE id, whichever tool holds it
    working_set_pull, WORKING_SET_PROMPT, _withdraw_working_set   already in shape, or private

Read directly by circle.py at every open (the question, then the row), by transcript_store's
discard_empty_open() (the withdrawal), by issue_prompt_projection/issue_index/issue_draw (the parsers).
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import seam                                                    # noqa: E402
import REGISTER_CLASS as SS                                       # noqa: E402
from record_paths import SELF_DIR                                     # noqa: E402


# ------------------------------------------------------------------ the question
# THE WORDS ARE THE OPERATOR'S — R330, 2026-08-23: *"Ensure
# the working set question is presented in terms of "Do you have specific
# issues you would like to focus on today ('?' to review) ? ""*. It was
# `CIRCLE issues (blank = none, 'all', '?'): ` — a legend, not a question. The
# GRAMMAR below is unchanged: blank is still no issues, `none` and `all` are
# still accepted; `all` is simply no longer advertised. `?` lists and re-asks,
# as it always did. The dual pane's blank-answer echo read its legend out of
# the old prompt's "blank = ..." and now takes its "(blank)" fallback.
#
# THE LEGEND RETURNED, IN HIS WORDS — R344,
# 2026-08-25 (D61 a): *"blank for no, 'all', or a comma separated list of
# line numbers"* — added after he typed "16" at a numbered-in-his-head
# listing that carried no numbers and no hint of what an answer looks like.
# The `?` listing is numbered now and digits-only tokens ARE line numbers;
# issue ids keep their `n` prefix and still work.
WORKING_SET_PROMPT = ("\nDo you have specific issues you would like to focus "
                      "on today ('?' to review) ? (blank for no, 'all', or a "
                      "comma separated list of line numbers) ")


def working_set_ask(IP, prompt: str = WORKING_SET_PROMPT, *, read_line):
    """The working set, asked until it is answerable. FINDING 2, 2026-08-20.

    `read_line` IS A PARAMETER (2026-09-03, stage 10): circle.py passes its own
    read_line_no_annotation, which refuses an annotation at this prompt (R225)
    and reads on the CIRCLE channel. Required, not defaulted — a default of
    seam.read_line would silently drop that refusal.

        (blank)   NO issues at all — the prologue and nothing else
        none      the same, said out loud
        all       the whole live graph
        ?         the live issues, NUMBERED, then ask again
        1, 3...   line numbers into that listing (R344, D61 a: a
                  digits-only token is a line number, the order the
                  id order `?` prints)
        nNNNN...  those issues, validated

    NOT ASKED AT ALL WHEN THERE IS NOTHING TO CHOOSE FROM — R330,
    2026-08-23: *"If there are no issues[], do not ask the working
    set question."* main() tests `IP.live_nodes()` first and takes the blank
    answer (None) silently; a fresh installation that recorded no issue reaches
    the topic question directly. This function is unchanged by that — the
    decision is the caller's, so a driver that wants the question can still
    call it.

    THE DEFAULT FLIPPED — R-NEW, 2026-08-22, Self ruled: *"issues are important to
    include only when specifically discussing some set of issue and
    issue-relations — so the default ought to be to NOT include them,
    issues=none, rather than issues=all."* Blank used to mean the whole graph.
    Nothing about the GRAMMAR changed — `none`, `all` and an id list all mean
    exactly what they meant, and `chosen is None` was already the ruled
    spelling for "no issues" (finding 2, 2026-08-20). Only which answer blank
    maps to changed.

    Measured, and the reason it is not merely a preference: with the whole
    graph in block 2, the Child was identified by a blind reader 44% of the
    time; with the `## Issues` section removed, 72% (n=25, p=0.045). The graph
    costs the parts their own distinctness, so it should be paid for when the
    circle is about those issues and not otherwise.

    "ISSUE", NEVER "NODE", IN ANYTHING THIS PROMPTS OR PRINTS — RULED
    2026-08-21, after the lab's second day: *"'node' is graph speak, can be
    applied to all of our graphed anything, it is ambiguous. 'issue ids'
    are what a user must see, specific to this application. Ruling: do not
    surface 'node'. Replace it with the class of node being referenced."*
    The code below still says node where it means the graph; the operator
    reads "issue".

    Returns a list of ids, `[]` for the whole graph (`all`), or None for no
    issues (blank or `none`). THE THREE ANSWERS ARE STILL DIFFERENT and the
    types still say so: `[]` means "no FOCUS, project everything", None means
    "no issues in this circle at all". What changed in R-NEW is only which of
    them BLANK selects — `none` is now the synonym for blank, and `all` is the
    word that must be typed.

    AN INVALID ID DOES NOT OPEN A CIRCLE. It printed `unknown node(s)
    ignored:` and carried on — so on 2026-08-20 a `/status` typed one
    prompt too early became the working set, was "ignored", and the circle
    opened anyway with no focus at all. Nothing is ignored now: the invalid
    ones are named and the question is asked again.

    THE VALID ONES COME BACK ALREADY TYPED, which is the ruled behaviour —
    "position the cursor at the end so that the user can correct the
    entries; an enter alone would submit the list of just those that are
    valid". `prefill` is an affordance the dual pane honours and a plain
    terminal cannot, so the same subset is ALSO printed in words: the
    coordinator never depends on the reader having a cursor.

    `?` RESETS THE LINE rather than prefilling it — you asked what exists,
    you did not offer an answer."""
    prefill = ""
    while True:
        try:
            raw = read_line(prompt, "working set",
                                          channel="circle", prefill=prefill)
        except (EOFError, KeyboardInterrupt):
            seam.emit("command", "\n  (no working set — this circle carries no issues)")
            return None
        word = raw.strip().lower()
        if word in ("", "none"):
            seam.emit("command", "  none — this circle carries no issues at all.")
            return None
        if word == "all":
            seam.emit("command", "  all — the whole live graph.")
            return []
        if word == "?":
            try:
                g = IP.issue_graph_read()
            except Exception as e:                             # noqa: BLE001
                seam.emit("command", f"  (the graph will not load: {e})")
                g = {}
            seam.emit("circle", f"\n  {len(g)} live issue(s)")
            for i, nid in enumerate(sorted(g), 1):
                label = (g[nid]["doc"].get("label") or "(no label)")
                seam.emit("circle", f"    {i:>2}  {nid}  {label[:64]}")
            prefill = ""
            continue
        pairs = working_set_parse(raw)
        # A DIGITS-ONLY TOKEN IS A LINE NUMBER — R344
        # (D61 a), 2026-08-25. The order is the `?` listing's own: the live
        # graph in id order, so "1, 3" means the first and third rows whether
        # or not `?` was actually typed this time. An id keeps its `n` prefix
        # — before this, a bare "16" normalised to id 0016 and the refusal
        # named an issue id at someone answering with a line number.
        if any(t.isdigit() for t, _ in pairs):
            try:
                order = sorted(IP.issue_graph_read())
            except Exception as e:                             # noqa: BLE001
                seam.emit("command", f"  (the graph will not load: {e})")
                return []
            bad = [t for t, _ in pairs
                   if t.isdigit() and not 1 <= int(t) <= len(order)]
            if bad:
                seam.emit("command", "  not on the listing: " + ", ".join(bad)
                     + f" — {len(order)} issue(s); ? lists them numbered")
                keep = [t for t, _ in pairs if t not in bad]
                prefill = " ".join(keep)
                seam.emit("command", "     asking again"
                     + (f" — keeping: {prefill}" if prefill else ""))
                continue
            pairs = [(t, order[int(t) - 1]) if t.isdigit() else (t, nid)
                     for t, nid in pairs]
        ids = [nid for _, nid in pairs]
        try:
            focus, _, unknown = IP.issue_resolve(ids)
        except Exception as e:                                 # noqa: BLE001
            seam.emit("command", f"  (the graph will not load: {e})")
            return []
        if not unknown:
            return ids
        # ECHO WHAT WAS TYPED, not what it normalised to. issue_id_normalise()
        # strips a leading `n` and any `X_` status prefix, so `nZZZZ` comes
        # back as `ZZZZ` — and a refusal naming a string the operator never
        # typed is a refusal they have to decode before they can act on it.
        # First-wins: two spellings of one id are one id, and the first is
        # the one they read.
        as_typed: dict[str, str] = {}
        for tok, nid in pairs:
            as_typed.setdefault(nid, tok)
        # "not issue ids", and what one looks like — 2026-08-21. This said
        # "not in the graph: ..." / "none of those were node ids." and the
        # operator's own words were *"I do not know what 'node ids' refers
        # to"*: the refusal named the graph's concept, not the thing he was
        # being asked for. He was being asked for ISSUE ids.
        seam.emit("command", "  not issue ids: "
             + ", ".join(as_typed.get(u, u) for u in unknown))
        # ...and the line comes back in their spelling too. It re-parses to
        # the same ids, so nothing is lost by keeping it theirs.
        prefill = " ".join(as_typed.get(f, f) for f in focus)
        seam.emit("command", "     asking again"
             + (f" — the valid ones are: {prefill}" if prefill
                else " — an issue id looks like n0010; ? lists them, Enter "
                     "alone (or none) is no issues, all is the whole graph."))


# ------------------------------------------------------------------ the register
WORKING_SETS = SELF_DIR / "working_sets.toml"

# NEXT.md B14, R210 (2026-08-17): working_sets.md -> .toml, the same
# REGISTER_CLASS.py registers under self/ already use. No id, no next_id —
# nothing cites an entry by id, only by its own `circle` field, and the
# register-intake gate (bnf_conformance.py) binds only next_id-bearers.
#
# ONE PREAMBLE, defined once, used by both the lazy-create path below and
# the one-off migration driver that moved the .md file's one row across
# (not checked in — REGISTER_CLASS.py's own docstring names dropping a
# preamble in a format migration as the failure this project keeps
# finding). Wrapped via SS.register_wrap() at import time, same as every other
# self/*.toml register's preamble — an unwrapped single line would be
# unreadable in a diff and would trip the 116-char line limit.
WORKING_SETS_PREAMBLE = SS.register_wrap(
    "Which issues each circle was shown, chosen by Self at open. "
    "chosen is \"none\" for no issues at all (the blank answer's meaning "
    "since the default flipped, R301), [] for the whole live graph (all), "
    "or the issue ids. Ruled 2026-08-03. Withdrawn in "
    "the one case ruled 2026-08-09: a circle that died before its first "
    "statement leaves no trace, so its transcript is removed and this "
    "entry with it. An entry naming a transcript that does not exist is "
    "a dangling reference, not a record of what a room was shown. "
    "Nothing else is ever removed, and nothing is ever edited in place.")

ORDER = ("circle", "chosen", "topic")   # WORKING_SET_ORDER until 10d: the register
                                         # convention docs/BNF.md's <working_set> pins


def _working_sets_doc() -> dict:
    if WORKING_SETS.is_file():
        return SS.register_read(WORKING_SETS)
    return {"register": "working_sets",
            "doc": {"preamble": WORKING_SETS_PREAMBLE}, "working_set": []}


def working_set_record(ot: str, chosen: "list[str] | None", topic: str,
                       live: bool) -> None:
    """Append to self/working_sets.toml. A history, so a later reading of a
    transcript can ask what the room was shown, not only what it said.

    `chosen` carries the working set's three states (working_set_ask):
    None — no issues at all, recorded as the grammar's own word, "none",
    because TOML has no null; [] — the whole live graph; a list — those
    issues. `list(chosen)` unconditionally raised TypeError on None, which
    was every live open whose blank answer took the default — the suites
    never saw it because the sandbox returns before the append.

    topic is stored whole — the truncate-to-100-chars-plus-ellipsis rule
    the .md form used was a display convention for a flat file, not a
    property of the data; the transcript always held the whole thing."""
    if not live:
        return
    WORKING_SETS.parent.mkdir(parents=True, exist_ok=True)
    doc = _working_sets_doc()
    doc["working_set"].append(
        {"circle": ot,
         "chosen": "none" if chosen is None else list(chosen),
         "topic": topic})
    SS.register_write(WORKING_SETS, doc, "working_set", ORDER)


def _withdraw_working_set(ot: str, live: bool) -> None:
    """Remove this circle's working-set entry. The register's own preamble
    says appended-and-withdrawn: an entry naming a transcript that does not
    exist is not a record of what a room was shown, it is a dangling
    reference. Nothing else reads this file.

    Removes every row matching `ot` rather than only the last (the .md form's
    `rfind` found the LAST occurrence because entries were appended in file
    order and never reordered) — `circle` is unique per open, so the two are
    equivalent in practice; this is the simpler statement of the invariant,
    not a behavior change. atomic_write is LF-only regardless of what wrote
    the bytes it replaces — see its own docstring."""
    if not live or not WORKING_SETS.is_file():
        return
    doc = _working_sets_doc()
    rows = doc.get("working_set", [])
    kept = [row for row in rows if row.get("circle") != ot]
    if len(kept) == len(rows):
        return
    doc["working_set"] = kept
    SS.register_write(WORKING_SETS, doc, "working_set", ORDER)


# ------------------------------------------------------------------ the id parsers
def issue_id_normalise(x):
    """Any of `2`, `nNNNN`, `L_n9999`, `S_n0099` -> the bare id.

    THE PREFIX IS PRESENTATION; THE ID IS IDENTITY — the project's own rule, and
    the reason this exists. Naming `L_n9999` and getting nothing back would be
    the tool disagreeing with its own filenames."""
    x = x.strip()
    if len(x) > 1 and x[1] == "_":
        x = x[2:]
    x = x.lstrip("nN")
    return f"n{int(x):04d}" if x.isdigit() else x


def working_set_argv_parse(argv, g=None):
    """['--working-set', 'nNNNN,nMMMM'] -> ['nNNNN','nMMMM']. Bare ids after the
    flag are accepted too, since a comma is easy to forget."""
    ids = []
    # `--live` = every node whose status is live, as a working set. Ruled
    # 2026-08-04. The default is EVERY node — the picture shows what is there —
    # and that is right for reading history, wrong for reading the graph as it
    # currently claims anything. A lead makes no claim (R002) and a settled node
    # is concluded, so a live-only view is the graph AS AN ASSERTION.
    if "--live" in argv:
        ids += [nid for nid, n in (g or {}).items() if n.get("status") == "live"]
    for i, a in enumerate(argv):
        if a == "--working-set" and i + 1 < len(argv):
            ids += [x.strip() for x in argv[i + 1].split(",") if x.strip()]
        elif a.startswith("--working-set="):
            ids += [x.strip() for x in a.split("=", 1)[1].split(",") if x.strip()]
    return [issue_id_normalise(x) for x in ids]


def working_set_parse(s: str) -> list[tuple[str, str]]:
    """[(as typed, normalised)] — the split done ONCE, both views returned.

    A REFUSAL MUST ECHO WHAT WAS TYPED, 2026-08-20. issue_id_normalise() strips a
    leading `n` and any `X_` status prefix, so `nZZZZ` normalises to `ZZZZ`
    — and the working-set prompt reported the NORMALISED form, telling the
    operator that something they had not typed was not in the graph. The
    id the graph is searched by and the id a person recognises are not the
    same string, and both are needed.

    The alternative was for the caller to re-split the line itself, which
    would put this regex in two places — a second source of truth for the
    one thing this function IS."""
    return [(x, issue_id_normalise(x))
            for x in re.split(r"[,\s]+", s or "") if x.strip()]


# ------------------------------------------------------------------ the neighbour pull
def working_set_pull(g: dict, chosen: list, neighbours) -> tuple[list, list, list]:
    """(keep, pulled, unknown) — the chosen ids that exist, in the order chosen,
    followed by every neighbour of THOSE (one hop, never transitive) that was
    not already kept, in the order found; `unknown` is what named nothing.

    `neighbours(nid)` is the caller's: issue_index hands back both endpoints of
    a node's live edges (undirected), issue_draw only what its edges point at
    (directed). The loop was written twice, once each way, until 2026-09-03."""
    unknown = [c for c in chosen if c not in g]
    keep = [c for c in chosen if c in g]
    pulled = []
    for nid in list(keep):
        for other in neighbours(nid):
            if other in g and other not in keep:
                keep.append(other)
                pulled.append(other)
    return keep, pulled, unknown
