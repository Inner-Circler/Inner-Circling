#!/usr/bin/env python3
"""
propose_lifecycle.py — PROPOSE LIFECYCLE: what happens to a part's `[proposed: ...]`
between the round it was spoken in and the row Self rules on.

MOVED OUT OF annotations.py, 2026-09-03 (cohesion re-homing stage 8, B99; the name is the
BNF's own section, PROPOSE LIFECYCLE). annotations.py keeps the BRACKET GRAMMAR — ASK_RE,
extract_annotations(), the remember paths, route_annotations() — and this module reads it as
MK. Every function below is the verbatim body it had there; only the file moved.

RENAMED AT THE MOVE (R436, R442 — 2026-09-03), the class word first, the bodies untouched:

    capped_propose_keys         -> proposal_capped_keys
    unruled_proposals           -> proposal_unruled_list
    propose_proposals           -> proposal_collect
    coalesce_propose_proposals  -> proposal_coalesce
    stage_propose_proposals     -> proposal_stage           (the operator's spelling)
    convergence_queue           -> proposal_convergence_queue   RETIRED 2026-09-04 (B98): no
                                                               production caller — only its suite
    show_unruled_proposals      -> proposal_unruled_show
    _normalize_edge, _norm_text, _wrap58   private, unchanged

    proposal_capped_keys        R255's one-propose-per-part-per-circle, last wins
    proposal_unruled_list          what Self is shown at /close before ruling (M2)
    proposal_collect          the well-formed [proposed: <command>] records of a transcript
    proposal_coalesce the close-time grouping — same command, one row (R202/R274)
    proposal_stage    the staging writer: proposal_manager.proposal_row_stage() at a LIVE close
    proposal_unruled_show     the command-pane listing
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import seam                                                        # noqa: E402
import annotations as MK                                           # noqa: E402  the bracket grammar


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
#                       remember_manager.AUTHORED_WORD_CAP words.
#     [proposed: ...]   1 per circle. No word cap any more — see above.
#
# THE CEILING IS ON WHAT A PART WRITES, NOT ON THE REGISTER.
# remember_manager.RECORD_CAP (600 chars) still governs a record the COORDINATOR
# mints — dreaming's own memories, quote-as-lands's "lands", anything
# migrated in — so widening what a part may say does not silently widen
# what dreaming may write.
#
# TRUNCATED, NEVER REFUSED, still describes REMEMBER: a part that runs long
# loses its tail, not its record.


def proposal_capped_keys(transcript: list[dict]) -> set:
    """(statement index, annotation span) of the ONE `[proposed: ...]` that
    counts for each PART this circle — its LAST well-formed one. RULED
    2026-08-19 (R255): one propose per part per circle.

    LAST, NOT FIRST, and that is what makes the cap safe to apply at all.
    proposal_coalesce() already reads a part's LAST STANCE, so a part
    that proposed an edge one way and reversed after the reveal is
    counted in its final position (the Learner did exactly that by hand
    in `circle_2026-08-09_1520`). A first-wins cap would have outlawed
    that reversal; a last-wins cap is the rule the code already applied,
    now with the superseded attempts dropped rather than merely outvoted.

    SELF IS NOT CAPPED. The ruling is a PART discipline — Self types at
    the circle prompt and rules on what the room asked, so capping him
    would cap the ruler. `speaker == "self"` is skipped here, the same
    speaker proposal_unruled_list() excluded wholesale until R202.

    MALFORMED DOES NOT COUNT, the rule remember already follows: a
    propose that failed to parse is surfaced by proposal_unruled_show()
    and does not spend the part's one use."""
    last = {}
    for i, e in enumerate(transcript):
        if e["speaker"] in ("__coordinator__", "self"):
            continue
        for rec in MK.annotation_extract(e["text"]):
            if rec["kind"] != "propose" or rec.get("malformed"):
                continue
            last[e["speaker"]] = (i, rec["span"])
    return set(last.values())



def proposal_unruled_list(transcript: list[dict],
                      issue_cmds: list[dict] | tuple = ()) -> list[dict]:
    """M2, ruled 2026-08-04. A part may PROPOSE its own statement for Self's
    attention at close.

    `issue_cmds` — 2026-08-21, the operator (F6: *"yes"*): an edge proposal
    whose IDENTICAL edge Self has already ruled THIS circle by a direct
    command is not unruled, and is left out — the close-time list asks only
    about what is genuinely open. In circle 2026-08-21_1139 he typed both
    rulings and was still asked to "rule with /issue-relationship-add" on
    each. Same normalisation proposal_coalesce() uses (either direction is
    the same question). Default empty: every other caller sees the list
    as before.

    A part asked for exactly this in `sandbox_2026-08-04_1243` and had no
    way to reach it: *"Child said something I want held past the close of this
    circle... I just want to make sure that sentence doesn't get filed under
    'good circle' and forgotten by next week's evidence-gathering. It's not
    evidence. It's the point."*

    FAILS OPEN. The annotation is scanned out of prose, which is the one thing
    this project spent a day escaping — and it is right here, because a missed
    proposal costs nothing: Self has the transcript regardless.

    RULED 2026-08-10: no longer excludes `speaker == "self"` — circling_
    and_evolving.md §2's gap. Self's own annotations count the same as a
    part's now, from either pane.

    RESCOPED 2026-08-16 (R202): `propose` used to mean "an edge attempt,
    valid or malformed" unconditionally — this function's own original
    docstring called it exactly that. Now that `[propose <text>]` covers
    every future (command or free text), keeping ALL of it here would
    mislabel ordinary free-text/other-command content as a relation
    attempt. Scoped back to its documented purpose instead of expanded
    to match the annotation's new breadth: only an ADD-RELATION-shaped
    attempt still appears — successfully parsed (redundant with staging,
    same ADDITIVE choice this project has not resolved either way, see
    relation coalescing below) or genuinely malformed (a real issue-relationship-add
    attempt whose arguments didn't parse). An empty propose, free text, or
    any OTHER command is comprehensively handled by staging now and has
    nothing left to show here. Lost its `marks` parameter 2026-08-14, when
    MARK and PROPOSE MARK were retired wholesale (docs/BNF.md) — the
    parameter had already gone unused in this function's body since
    2026-08-12.

    RENAMED 2026-08-18 (R236): was `nominations()`; `proposal_unruled_show()`
    was `show_nominations()`. "Nomination" was an unwanted synonym for the
    PROPOSE class this has belonged to since R202 — same annotation, same
    grammar, same re-derive-from-the-transcript discipline. The new name
    states the ROLE, which survives either resolution of the ADDITIVE
    TENSION (docs/BNF.md): what the room proposed and Self has not ruled.

    CAPPED AT ONE PER PART, 2026-08-19 (R255), from the SAME
    proposal_capped_keys() call staging uses — computed over the whole
    transcript BEFORE this function's own edge-shape filter, so the
    propose that counts here is the propose that counts there. Deriving
    it from the already-filtered list would let a part whose last
    propose was free text keep an earlier edge attempt alive on this
    surface alone, and the two views would disagree about what the part
    asked for.

    MALFORMED IS NOT SHOWN HERE ANY MORE, 2026-08-20 (code review), because
    it cannot arrive: every live path runs strip_malformed_annotations() before
    a statement is appended — room text and file record alike — so by the
    time a transcript reaches this function a malformed bracket is gone.
    R274 measured it. The "!! MALFORMED" line this used to feed fired only
    in a test that handed the bracket to this function directly."""
    out = []
    kept = proposal_capped_keys(transcript)
    ruled_edges = {_normalize_edge((c["node"], c["type"], c["target"]))
                   for c in issue_cmds
                   if c.get("verb") == "issue-relationship-add"}
    for i, e in enumerate(transcript):
        if e["speaker"] == "__coordinator__":
            continue
        for rec in MK.annotation_extract(e["text"]):
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
# proposal_stage() into self/proposals.toml and RUN at approval by
# dispatch_dev_cmd(). One staging register instead of two.
#
# ONE BEHAVIOUR REALLY DID CHANGE, and it is worth stating rather than
# discovering. A proposed practice used to be staged as a `state="proposed"`
# ROW IN self/best_practices.toml — visible to /practice-list, excluded from
# projection, ruled through practice_manager.practice_approve(). It is now a row
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


def proposal_collect(transcript: list[dict]) -> list[dict]:
    """Every well-formed `[proposed: ...]` annotation across the whole
    transcript, re-derived fresh on every call, same discipline every
    other `*_proposals()` function here has always used. RULED
    2026-08-16 (R202): replaces request_proposals() and
    relation_proposals() at once — `[proposed: <command>]` is the ONE
    annotation. R202's second category, free text, is MALFORMED as of
    2026-08-20 (R273), so everything this yields is a command. Malformed
    ones (a command ATTEMPT that failed to parse) are excluded — and since
    the same day they cannot arrive at all: strip_malformed_annotations() runs
    before any statement is appended, so a transcript never holds one
    (R274).

    CAPPED AT ONE PER PART, 2026-08-19 (R255) — see proposal_capped_keys()
    for why it is the LAST rather than the first, and why Self is exempt.
    A part's superseded earlier proposes are dropped here, before
    coalescing, so a part cannot occupy two staged rows."""
    out = []
    kept = proposal_capped_keys(transcript)
    for i, e in enumerate(transcript):
        if e["speaker"] == "__coordinator__":
            continue
        for rec in MK.annotation_extract(e["text"]):
            if rec["kind"] != "propose" or rec.get("malformed"):
                continue
            if e["speaker"] != "self" and (i, rec["span"]) not in kept:
                continue          # R255 — superseded by this part's later one
            out.append({"index": i, "display": e["display"],
                        "text": e["text"], **rec})
    return out


def proposal_coalesce(transcript: list[dict],
                               issue_cmds: list[dict]) -> list[dict]:
    """Groups proposal_collect() into rows to stage. RULED 2026-08-16
    (R202): replaces coalesce_relation_proposals() and coalesce_request_
    proposals() at once, branching internally on WHICH coalescing rule
    a row needs:

    ADD-RELATION-shaped COMMAND: the SAME rule #32 already ruled for a
    relation, preserved exactly — group by normalized edge, using each
    speaker's LAST STANCE (the one definition of that rule since B98 retired
    proposal_convergence_queue(), 2026-09-04), and stage ONLY when the group is unanimous — every
    speaker who proposed this edge, either direction, converged on the
    same direction this circle. Dedups against `issue_cmds` — commands
    already queued THIS circle — same as before. A split group is left
    unstaged; Self still sees it via proposal_unruled_show() and rules with
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

    for p in proposal_collect(transcript):
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
                                               # proposal_unruled_show()
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


def proposal_stage(ot: str, transcript: list[dict],
                            issue_cmds: list[dict], live: bool) -> list[str]:
    """Written once, at /close — never mid-circle, sandbox writes nothing (a
    sandbox circle's proposal is a draft, not something to stage into
    the live self/proposals.toml). RULED 2026-08-16 (R202): replaces
    stage_request_proposals() and stage_relation_proposals() at once.
    Returns the new ids for the caller to report."""
    if not live:
        return []
    rows = proposal_coalesce(transcript, issue_cmds)
    if not rows:
        return []
    import proposal_manager as PR
    return [PR.proposal_row_stage(row["kind"], row["text"], row["sources"], ot)
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


def proposal_unruled_show(props: list[dict]) -> None:
    """`props` is always `proposal_unruled_list()`'s own output — "propose" is the
    ONLY kind it can contain as of 2026-08-14 (practice/better_option
    kinds excluded 2026-08-12, then request, retired into its own
    staged/vetted register; hold retired into propose-mark, itself
    retired wholesale 2026-08-14, docs/BNF.md) — RESCOPED 2026-08-16
    (R202) to only an ADD-RELATION-shaped attempt — well-formed only, since
    2026-08-20: a malformed one is stripped at utterance and never reaches
    this list (R274) — (see proposal_unruled_list()'s own docstring for why:
    `propose` covers every future now, and everything else is
    comprehensively staged). Written
    to read `n["kind"]` rather than assume "propose" outright, so a
    future kind added back to proposal_unruled_list() fails loud (KeyError on the
    `head` lookup) instead of silently mislabeled."""
    if not props:
        return
    seam.emit("command", f"\n  {len(props)} ASK(S) from the room, unruled:")
    for n in props:
        body = MK.ASK_RE.sub("", n["text"]).strip()
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
