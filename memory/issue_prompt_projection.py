#!/usr/bin/env python3
"""
issue_prompt_projection.py — verify the live issue graph is sound to project into a
(issue_projection.py until 2026-09-03 — F5 under R435: a PROMPT projection says so in its name)
prompt, and provide the projections `prompt_build.py` builds Block 2 from.

    python memory/issue_prompt_projection.py    verify SHAPE and PROVENANCE

B9. Was "the same shape as check_better_options.py: one module that both
projects and verifies" — no longer. RETIRED 2026-08-11: self/circle_briefing.md
is gone, and with it the one thing this module used to WRITE. `group_attention.py`'s
`circle_briefing_build()` (moved out of `circle.py` in phase 2 stage 2, 2026-08-16)
calls straight into `issue_block_render()`, `project_working_set()` and
`issue_relationship_brief()` at
prompt-assembly time — `narrative()` RETIRED alongside it, B46, 2026-08-17,
see below — no projection step, no file in between to go stale or
to verify against. What remains here is the gate: does the live graph itself
have the shape those functions need, so that whatever they build is sound.

WHY IT WAITED, AND WHY IT STOPPED WAITING. Until 2026-08-03 this was blocked on
A1 — rewriting each node's description in Self's words — because projecting the
derivation's wording would put a machine's account of him into seven prompts as
though it were his. Two of eleven are done, and waiting for the other nine made
his throughput the system's bottleneck.

Ruled 2026-08-03: **project with provenance.** Every block says whose words it
carries. A node Self has ratified says so; a node still carrying the 2026-07-27
derivation's wording says THAT, in the block, where a part reads it. Parts can
then hold it as provisional rather than as his testimony, which is what it is.

    the goal, CLAUDE.md: greater health by way of better options discovered
    through uncovering and understanding issues. A projection that waits for
    perfect attestation delays every part's access to the graph in order to
    protect an accuracy claim nobody made. Saying "not yet ruled" costs eleven
    words and is true.

WHAT A LIVE-NODE BLOCK CARRIES

    label + id       what it is, and the stable handle
    provenance       ruled in <circle>, or the derivation's wording
    absence clause   what it looks like when this is NOT firing

The absence clause rather than the description, deliberately, for the RICH
blank-working-set case. It is the one field the gate already
requires of every node, so nothing new must be authored; and it is the more
useful half in a room — a part cannot notice a pattern from a definition, but
it can notice that something arrived and was not converted.

WHAT `main()` ASSERTS, over the live graph directly

    SHAPE      every live node has a Label and an absence clause. The gate
               already requires both; this fails loudly rather than letting
               `issue_block_render()` hand a part an empty field.

    PROVENANCE every node's `ruled` field, if set, names a real transcript. A
               block claiming Self's authority without one would be the exact
               failure this projection exists to avoid.

    COVERAGE   reported: how many live nodes carry his wording.

THERE IS NO SECOND SOURCE ANY MORE. This module once left a hand-written
narrative alone deliberately — two disjoint accounts of the same life, where
folding either into the other would silently lose one. That account was
migrated into the graph and retired 2026-08-14, and `narrative()`, which had
concatenated it into Block 2, went at B46 (see its note further down). The
graph is now the whole of what Block 2 projects.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "coordinator"))  # identity/paths et al.
import identity as ID                                          # noqa: E402
import issue_schema as S                                       # noqa: E402
import record_paths as _RP                                         # noqa: E402

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = pathlib.Path(__file__).resolve().parent.parent
ISSUES = _RP.ISSUES_DIR
CIRCLES = _RP.CIRCLES_DIR

# MOVED HERE FROM group_attention.py, 2026-09-02 -- on direct instruction,
# the same move already made for topics.toml (topic_prompt_projection.py) and
# parts/<p>/* (parts_prompt_projection.py): the prologue is issue-graph material,
# same standing as every other issue_prompt_projection.py-owned read, not
# group_attention.py's to hold just because it assembles BLOCK 2's whole
# text. MOVED self/ -> issues/ 2026-08-15 (R198) before that -- the
# prologue to the issue graph, what an issue IS, not Self's own material
# (R195: self/* does not propagate into any prompt Block).
ISSUE_MODEL = ISSUES / "issue_model.md"


@_RP.group_follow
def _issue_dirs_rebind() -> None:
    """BLOCK 2 is built from the CURRENT group's issue graph and prologue — B117 stage 4
    (2026-09-07): record_paths.group_set() runs this after rebinding, so a band circle's
    circle_objectives carry the band's issue_model.md and none of the IFS group's nodes."""
    global ISSUES, CIRCLES, ISSUE_MODEL
    ISSUES = _RP.ISSUES_DIR
    CIRCLES = _RP.CIRCLES_DIR
    ISSUE_MODEL = ISSUES / "issue_model.md"


def record_ro_read(p: pathlib.Path) -> str:
    """Read-only by construction. Fails loudly rather than silently
    degrading. Duplicate of parts_prompt_projection.record_ro_read() and
    process_core_prompt_projection.record_ro_read() -- small enough that importing
    across files to share it would carry more risk (a circular import) than the
    duplication does. (read_ro() was this function's name in prompt_build.py
    before B99; nothing defines it now, so do not go looking.)"""
    return p.read_text(encoding="utf-8")


def issue_prologue_read() -> str:
    """The prologue -- issue_model.md's own text, what an issue IS, the
    one part of BLOCK 2 present unconditionally. FAILS CLOSED on a
    missing file: a briefing assembled without it is a different
    experiment wearing the same name -- the same guarantee group_attention.
    py's circle_briefing_build() enforced directly before this move; the check
    itself moved here with the read, 2026-09-02."""
    if not ISSUE_MODEL.is_file():
        raise RuntimeError(
            f"cannot build a briefing: {ISSUE_MODEL.relative_to(ROOT)} is "
            f"missing. The prologue, the issues and the relations are the "
            f"core of it; assembling without it is a different experiment")
    return record_ro_read(ISSUE_MODEL).rstrip("\n")


SECTION = "## Issues"

PREAMBLE = """\
*Projected from `issues/` by `memory/issue_prompt_projection.py`. **What is OWED.**
Better options — what is AVAILABLE — no longer project here; see
`self/best_practices.toml`, read directly at prompt-assembly time.*

**Every block says whose words it carries.** A node Self has ratified in a
circle says so. A node still carrying the 2026-07-27 derivation's wording says
that too — hold those as provisional, not as his testimony. Saying so costs
eleven words and is true.

**Each block gives what its ABSENCE looks like**, not a definition. You cannot
notice a pattern from a definition; you can notice that something arrived and
was not converted, argued down or priced.

**A root renders in full** (description, absence and live edges) even here,
where every other node gets label + provenance + absence only — a root is a
source the live graph descends from, and is always shown whole.
"""


def _transcript(ref: str) -> pathlib.Path:
    """`circle_<OT>` -> circles/. `sandbox_<OT>` -> the sandbox.

    Approved 2026-08-03, mirroring `issue_gate.issue_source_read()` — and since
    2026-08-19 SHARING its mapping (S.circle_transcript, one copy; review
    tier 5 #44: this was the second of three lockstep clones the R176
    sweep had to edit together). A `--minimal` circle (retired R360) was a real circle
    with real parts; only its memory is stripped. The prefix stays
    distinct so a ruling made in a stripped-memory room is visible as
    such wherever it is cited. An unprefixed ref keeps this module's own
    old fallback — a circles/ path that will not exist, so the caller's
    "names no transcript" failure still fires with the ref in it."""
    return S.circle_transcript(ref) or (S.CIRCLES / f"{ref}.md")


# TOML since 2026-08-03. Every read of a node goes through `issue_schema`,
# which is the whole point: one parser, one grammar, one place a field name is
# spelled. The three helpers this file used to carry — field(), absence(),
# issue_live_edges_read() — were three more regexes over a format with no grammar.
live_nodes = S.issue_live_read


def issue_block_render(p: pathlib.Path, d: "dict | None" = None) -> tuple[str, list[str]]:
    """(projected block, failures). `d` reuses an already-parsed doc."""
    d = S.issue_read(p) if d is None else d
    fails = []
    lab = d.get("label", "")
    ruled = d.get("label_ruled", "")
    ab = S.issue_unwrap(d.get("absence", ""))
    if not lab:
        fails.append(f"{p.name}: no Label — nothing to project")
    if not ab:
        fails.append(f"{p.name}: no absence clause — nothing usable in a room")
    if ruled and not _transcript(ruled.split(" ")[0]).is_file():
        fails.append(f"{p.name}: Label ruled names {ruled}, which is not a "
                     f"transcript. A block cannot claim Self's authority on a "
                     f"circle that did not happen")
    prov = (f"*ruled by {ID.DISPLAY} in {ruled}*" if ruled
            else "*the 2026-07-27 derivation's wording — NOT YET RULED*")
    return (f"### {p.stem} — {lab}\n{prov}\n**Absent when:** {ab}", fails)


# narrative() RETIRED — B46, 2026-08-17. self/issues_narrative.md was
# retired 2026-08-14 (its remaining entries migrated into the graph,
# commit 16cd565) and never came back; the function had returned "" on
# every live circle since, a dead call site reading a file that no longer
# exists. See docs/BNF.md's BLOCK 2 note for the retired <issues_narrative>
# production this call site fed.


# --------------------------------------------------------------- working set
# Ruled 2026-08-03. Self names a working set at circle open — one or more node
# ids — and the parts read:
#
#   FOCUS       each named node in full: label, ruling, description, absence,
#               and its live edges.
#   PERIPHERY   every node a focus node shares a LIVE edge with, in EITHER
#               direction: name and description only.
#
# Nothing else projects. Blank means all live nodes, which is the old behaviour.
#
# TWO NODES WITH NO EDGE IS A LEGAL WORKING SET, and it is the interesting one.
# "Two nodes can be named as a working set (shared edge or no) and the circle
# may consider their relationship and I may rule on the creation of a
# relationship edge." So the sparse graph is the REASON to build this, not a
# reason to wait — an edge is born in a circle, not found by a scan. I had that
# backwards and recommended building a scanner first.
#
# LIVE EDGES ONLY, BOTH DIRECTIONS — ruled. nNNNN protects nMMMM, so focusing
# nMMMM brings the protector; a periphery that only followed outbound edges
# would hide the thing holding the focus in place.

# EDGE_RE deleted 2026-08-19 (review, tier 5 #50): a Markdown-era edge
# regex with zero uses in this module — the live copy is in
# issue_to_toml.py, the one-shot migrator. A compiled edge parser sitting
# here read as "projections still regex-scan Markdown edges", the exact
# stale-artifact trap prompt_build.py's own ISSUE_MODEL comment warns
# about; nodes have been TOML (and edges structured) since 2026-08-03.


# issue_id_normalise() and working_set_parse() MOVED to working_set_manager.py,
# 2026-09-03 (stage 10): one id normaliser for the tree instead of three copies.


def issue_live_edges_read(d: dict) -> list[tuple[str, str]]:
    """[(type, target)] — retired edges excluded, by ruling."""
    return [(e["type"], e["target"]) for e in d.get("edges", [])
            if e.get("status") != "retired"]


def issue_graph_read() -> dict:
    g = {}
    for f in S.issue_nodes_read():
        d = S.issue_read(f)
        g[d["id"]] = {"path": f, "doc": d, "status": d["status"],
                      "edges": issue_live_edges_read(d)}
    return g


def issue_resolve(chosen: list[str],
            g: "dict | None" = None) -> tuple[list[str], list[str], list[str]]:
    """(focus, periphery, unknown). Periphery is depth 1, both directions.
    `g` reuses a caller's already-built issue_graph_read() — one parse of issues/
    instead of two per working-set projection (tier 5 #58); omitted, it
    builds its own, so every existing caller is unchanged."""
    g = issue_graph_read() if g is None else g
    unknown = [c for c in chosen if c not in g]
    focus = [c for c in chosen if c in g]
    per = set()
    for nid in focus:
        for _, to in g[nid]["edges"]:
            if to in g:
                per.add(to)
        for other, d in g.items():                     # inbound
            if other in focus:
                continue
            if any(to == nid for _, to in d["edges"]):
                per.add(other)
    return focus, sorted(per - set(focus)), unknown


def issue_full_render(p: pathlib.Path, d: "dict | None" = None) -> str:
    """A focus node, whole — its CLAIMS, not its record.

    Description, absence clause and live edges. NOT the Memo and NOT the
    evidence: those are the record, and a room that needed twenty-three quotes
    read aloud to work on a node would be a room reading a file rather than
    thinking. `d` reuses a doc issue_graph_read() already parsed (tier 5 #58)."""
    d = S.issue_read(p) if d is None else d
    lab, ruled = d.get("label", ""), d.get("label_ruled", "")
    prov = (f"*ruled by {ID.DISPLAY} in {ruled}*" if ruled
            else "*the 2026-07-27 derivation's wording — NOT YET RULED*")
    L = [f"### {p.stem} — {lab}", prov, "",
         S.issue_unwrap(d["description"]), "",
         f"**Absent when:** {S.issue_unwrap(d.get('absence',''))}"]
    e = issue_live_edges_read(d)
    if e:
        L += ["", "**Live edges:** "
              + " · ".join(f"`{ty}` {to}" for ty, to in e)]
    return "\n".join(L)


def issue_brief_render(p: pathlib.Path, d: "dict | None" = None) -> str:
    """A periphery node — name and description only, by ruling.
    `d` reuses a doc issue_graph_read() already parsed (tier 5 #58)."""
    d = S.issue_read(p) if d is None else d
    return f"### {p.stem} — {d.get('label','')}\n{S.issue_unwrap(d['description'])}"


def _working_set_resolve(chosen: list[str], g: dict
                         ) -> tuple[list[str], list[str], list[str], set[str]]:
    """(focus, periphery, unknown, root ids) for a NAMED working set — the one resolution
    project_working_set() renders and issue_shown_read() reports, so the two cannot drift.
    issue_resolve() over chosen UNION roots, not chosen alone: a root's own live
    edges pull their neighbours into periphery exactly as any other focus
    node's would (the graph does not know "focus" and "always-shown" are
    different reasons a node ended up in the set)."""
    root_ids = {nid for nid, d in g.items() if d["doc"].get("root")}
    focus, per, unknown = issue_resolve(sorted(set(chosen) | root_ids), g)
    return focus, per, unknown, root_ids


def issue_shown_read(chosen: "list[str] | None") -> set[str]:
    """The ids this circle's `## Issues` gives a heading — what BLOCK 2 already carries, and so
    what `[recall: issues ...]` leaves out (R549, D128, 2026-09-11: *"D128 -
    c, not shown but not out of reach."*). Every other node is searchable.

        None    "none": the graph was not brought in — nothing is shown
        []      the whole live graph — every live node, roots among them (live_nodes())
        a list  the named set's focus, the roots, and the periphery one live edge away

    Built from the same resolution project_working_set() renders; test_prompt_build.py holds
    the equality against the headings actually rendered."""
    if chosen is None:
        return set()
    if not chosen:
        return {S.issue_read(p)["id"] for p in live_nodes()}
    focus, per, _unknown, _roots = _working_set_resolve(chosen, issue_graph_read())
    return set(focus) | set(per)


def project_working_set(chosen: list[str]) -> tuple[str, list[str]]:
    """The `## Issues` section for one circle's working set — the LIVE
    format: full detail for a focus node, brief for a
    periphery node.

    Blank chosen means the whole live graph, each node shown via `issue_block_render()`
    (label + provenance + absence clause) — the format self/circle_briefing.md
    used to carry whenever no working set replaced its `## Issues` section,
    before that file was retired 2026-08-11. `resolve([])` returns nothing at
    all (by design: a working set of everything is not "focused on nothing"),
    so blank is handled explicitly here rather than falling through empty.

    A ROOT IS ALWAYS SHOWN, IN FULL. R429, 2026-09-01:
    "nodes that ought never be removed and that ought always to be graphed"
    — full detail, ruled, same weight as a chosen focus node
    (`issue_full_render()`), in BOTH branches below, whether or not it was named.
    This is the one case `chosen is None` ("none" — the operator's own
    deliberate "the graph was not brought in") still overrides: that path
    never reaches this function at all (see prompt_build.circle_briefing_build),
    and a root does not force its way past an explicit opt-out for one
    circle. Blank and any named working set both still get it.

    FAILS CLOSED on a SHAPE failure (missing Label or absence clause) — the
    same refusal `--project` used to make before writing self/circle_briefing.md.
    The pre-commit hook runs issue_prompt_projection.py's own main() on every commit
    touching issues/, so this should never fire from committed state; it is
    the defense for a live circle opened against uncommitted, hand-edited
    issues/ — the one path the hook cannot see."""
    if not chosen:
        parts, fails = [SECTION, "", PREAMBLE], []
        for p in live_nodes():
            d = S.issue_read(p)
            if d.get("root"):
                parts += [issue_full_render(p, d), ""]
                continue
            b, f = issue_block_render(p, d)
            fails += f
            parts += [b, ""]
        if fails:
            raise RuntimeError(
                "cannot build circle_objectives — the live graph has SHAPE "
                "failure(s) issue_prompt_projection.py's own gate should have caught:\n"
                + "\n".join(f"  - {x}" for x in fails))
        return "\n".join(parts).rstrip("\n") + "\n", []
    # ONE graph build feeds issue_resolve() and both block renderers (tier 5
    # #58): this used to parse every issues/*.toml twice at the top and
    # once more per rendered node.
    g = issue_graph_read()
    focus, per, unknown, root_ids = _working_set_resolve(chosen, g)
    always = [r for r in sorted(root_ids) if r not in chosen]
    L = [SECTION, "", WS_PREAMBLE]
    note = f"*Working set: {', '.join(chosen) if chosen else '(none chosen)'}"
    if always:
        note += f" · root(s) always shown in full: {', '.join(always)}"
    note += (f" · periphery {', '.join(per)}" if per else " · no periphery — "
             "no live edge reaches these, which is itself worth a circle")
    note += ".*"
    L += [note, ""]
    for nid in focus:
        L += [issue_full_render(g[nid]["path"], g[nid]["doc"]), ""]
    if per:
        L += ["**Related — name and description only:**", ""]
        for nid in per:
            L += [issue_brief_render(g[nid]["path"], g[nid]["doc"]), ""]
    return "\n".join(L).rstrip("\n") + "\n", unknown


# ------------------------------------------------- relations, for a ROOM
# Ruled 2026-08-03. `docs/issue_relationship_types.md (archived)` went into circle_2026-08-03_2208
# whole:
# 1,808 tokens, 31% of a part's entire prompt. Measured use across 27 part
# statements:
#
#     narrower-than 0 · consequence-of 0 · protects 0 · related-to 0 ·
#     polarized-with 0 · attested 0 · proposed 0
#
# Not one edge type named once by any part. The document is written for an
# engineer reading `issues/` — file paths, an edge census, the history of two
# edges written backwards in the derivation, a section called "Where the
# machinery is". A part cannot run the gate and CANNOT CREATE AN EDGE (ruled),
# so 31% of its context was the rules of a game it is forbidden to play.
#
# What a part can actually use is: what the five words MEAN, and which edges
# are live right now. That is this.
#
# DERIVED, NEVER TRANSCRIBED. The type list comes from `issue_schema.
# EDGE_TYPES` — the same authority the gate enforces — and the edge list
# from `issue_live_edges_read()`. The glosses are the one hand-written thing here,
# and the import-time check BELOW the tables asserts their keys equal
# EDGE_TYPES exactly, so a type added to the gate fails this projection
# until somebody says what it means to a part. (That check was CLAIMED
# by this comment from the start and never existed — docs/
# issue_prompt_projection.md admitted as much — and gate_edge_types(), the
# helper seemingly built for it, sat here with zero callers; 2026-08-18
# review, tier 5 #51. Real since 2026-08-19; the dead helper is gone.)

GLOSS = {
    "narrower-than":  "A is a narrower case of B. Same mechanism, "
                      "smaller scope.",
    "leads-to":       "A gives rise to B. B is downstream of A, in time "
                      "or in cause — not merely similar. THE ARROW POINTS "
                      "FORWARD: `nNNNN —leads-to→ nMMMM` reads *nNNNN came "
                      "first and produced nMMMM*.",
    "protects":       "A stands in front of B and keeps something from "
                      "reaching it — usually the evidence that would "
                      "disconfirm B.",
    "related-to":     "Associated, with no stronger claim made. The "
                      "default, and the least committal.",
    "polarized-with": "In opposition — each one's strategy is the "
                      "other's refusal.",
}


# The one-line test that DISTINGUISHES each type from its neighbours. The
# glosses above say what a type means; these say how to choose between them,
# which is the actual work in a room. Ruled 2026-08-04, after Self asked for
# "strictly actionable (and clarifying) statements... they need it for relation
# discussions."
CHOOSE = [
    ("same mechanism, smaller scope", "narrower-than"),
    ("one gave rise to the other", "leads-to"),
    ("one keeps the other from being disconfirmed", "protects"),
    ("each one's strategy is the other's refusal", "polarized-with"),
    ("none of those, honestly", "related-to"),
]

# THE ASSERT THE GLOSS COMMENT ALWAYS CLAIMED (tier 5 #51). Import-time
# and a plain raise (never `assert`, which -O would strip): a sixth edge
# type added to issue_schema.EDGE_TYPES fails every reader of this
# module loudly — the pre-commit hook runs main() on every issues/
# commit — until its meaning and its chooser line are written for the
# room. Before this, the gate and parser would accept edges of a type
# the room had never been told about, while this projection went on
# rendering as if the vocabulary were whole.
if set(GLOSS) != set(S.EDGE_TYPES) or {t for _, t in CHOOSE} != set(S.EDGE_TYPES):
    raise RuntimeError(
        "issue_prompt_projection's GLOSS/CHOOSE vocabulary no longer matches "
        "issue_schema.EDGE_TYPES — a type was added or renamed without "
        "telling the room what it means. Write its gloss and its chooser "
        f"line here. GLOSS={sorted(GLOSS)} CHOOSE={sorted(t for _, t in CHOOSE)} "
        f"EDGE_TYPES={sorted(S.EDGE_TYPES)}")


def issue_relationship_brief(chosen: "list[str] | None" = None) -> str:
    """What a part needs IN ORDER TO DO relation work. Nothing else.
    Named `relations_brief` until R219, 2026-08-17 — same rename family
    as `/help issue-relationship` (R218): "relationship"/"relations"
    alone doesn't say which class of object, and this one is issue-graph
    edges specifically, not the part-to-part concept in
    parts/<p>/part_relationships.toml (renamed from relationships.toml
    2026-08-17, R220).

    `docs/issue_relationship_types.md (archived)` went into circle_2026-08-03_2208 whole — 1,808 tokens,
    31% of a part's prompt — and across 27 part statements not one edge type
    was named once. It is an engineer's document: file paths, an edge census, a
    bug history, a section called "Where the machinery is".

    Ruled 2026-08-04: project it to the ACTIONABLE. Which is not the same as
    the shortest — a part asked to discuss relations needs four things, and the
    first version of this brief carried only the first two:

        what each type MEANS               (the glosses)
        what is true right now             (live edges)
        how to CHOOSE between types        (CHOOSE, above)
        what a proposal or dispute must
          carry to be usable at all

    And one thing that is pure fact and was reaching nobody: every PROPOSED
    edge names, in `ask`, the parts who were to confirm it. Those lists have
    existed since 2026-07-27 and had never been put to a room. A part named in
    one is being asked a question it has never heard.

    `chosen` filters the proposed block and the open questions to what touches
    the working set and the roots — the nodes the Issues section gives whole;
    without it, every proposed edge in the graph."""
    g = issue_graph_read()
    # LIVE NOW reads the node's own edge rows, not d["edges"]: issue_live_edges_read() strips the
    # status, and a proposed edge that touches no named issue reaches the room ONLY through this
    # list — unmarked, it read as attested (another session's 2026-09-11 close-out). The same
    # non-retired filter; `proposed` rides along so the line can say so.
    live = sorted((nid, e["type"], e["target"], e.get("status") == "proposed")
                  for nid, d in g.items() for e in d["doc"].get("edges", [])
                  if e.get("status") != "retired")
    L = ["## Relations between issues", "",
         "An edge is a CLAIM that one locus bears on another, IN A DIRECTION. "
         "It can be wrong. Some were proposed by a derivation and confirmed by "
         "no one — hold those as provisional.", "",
         "**No part statement creates or retires an edge.** You may propose "
         "one or dispute one; Self rules.", "",
         "**To propose, say all four:** source, type, target, and what makes "
         "it true. *\"These are related\"* is not a proposal — without a "
         "direction there is nothing to rule on.", "",
         "**To dispute a live edge**, name it and say which part is wrong: the "
         "direction, the type, or the basis.", ""]
    for ty in sorted(GLOSS):
        L.append(f"- `A` —{ty}→ `B` — {GLOSS[ty]}")
    L += ["", "**Choosing between them:**", ""]
    w = max(len(t) for t, _ in CHOOSE)
    L += [f"    {t:<{w}}  ->  `{ty}`" for t, ty in CHOOSE]
    L += ["",
          "`related-to` is the DEFAULT and the least committal. Reach for it "
          "LAST, not first — an edge that could have been named more exactly "
          "and was not is a relation nobody was willing to characterise.", "",
          "**Two nodes with no edge between them is not an omission.** Whether "
          "they are related is the question.", "",
          "**LIVE NOW**", "",
          # Plain-led on purpose: the suite sections LIVE NOW up to the next blank-line-plus-`**`.
          "A relation marked *(proposed)* was derived and has never been confirmed by anyone; "
          "the ones this room is asked about appear in full under PROPOSED below. An unmarked "
          "relation was attested — spoken by a part in a circle, or ruled by Self.", ""]
    L += [f"- `{a}` —{ty}→ `{b}`" + (" (proposed)" if p else "")
          for a, ty, b, p in live] or ["- none"]

    # THE ROOTS ARE IN FRONT OF THE ROOM TOO (R547): a named working
    # set shows every root whole (R429, project_working_set()), so the filter is the named ids and
    # the roots. By the named ids alone, a root's proposed edges and open questions were left out
    # of every circle that named its issues.
    ws = set(chosen or [])
    if ws:
        ws |= {nid for nid, d in g.items() if d["doc"].get("root")}
    prop = []
    for nid, d in g.items():
        for e in d["doc"].get("edges", []):
            if e.get("status") != "proposed":
                continue
            if ws and nid not in ws and e["target"] not in ws:
                continue
            prop.append((nid, e))

    def _for_room(basis: str) -> str:
        """The claim, without the tool that recorded it.

        45 of 48 bases end in a parenthetical explaining WHY the derivation
        wrote `proposed` and naming `issue_migrate.py`. That is provenance —
        true, useful to an engineer, and noise to a part being asked whether
        the claim holds. It stays in the file; it does not project. The same
        record/projection split as better_options and the issue blocks."""
        return re.sub(r"\s*\((?:proposed by the derivation|the derivation "
                      r"recorded this)[^)]*\)", "", S.issue_unwrap(basis)).strip()

    # M1: OPEN QUESTIONS, ruled 2026-08-04. A deferred question rides the node
    # or the edge it is about and surfaces only when that thing is in the
    # working set — so it returns exactly when it is relevant and never
    # accumulates anywhere a reader has to prune it.
    opens = []
    for nid, d in g.items():
        if ws and nid not in ws:
            continue
        for q in d["doc"].get("proposals", []):
            if q.get("status") == "open":
                opens.append((f"`{nid}`", q))
        for e in d["doc"].get("edges", []):
            if ws and nid not in ws and e["target"] not in ws:
                continue
            for q in e.get("proposals", []):   # edge-level only
                if q.get("status") == "open":
                    opens.append((f"`{nid}` —{e['type']}→ `{e['target']}`", q))
    if opens:
        L += ["", "**OPEN QUESTIONS on what is in front of you.** Asked in an "
              "earlier circle and not yet settled. They appear because this "
              "working set is what it is; they are not a backlog.", ""]
        for what, q in opens:
            L.append(f"- {what} — {S.issue_unwrap(q['question'])}")
            if q.get("type"):
                # The node's NAME, not only its id. Ruled 2026-08-04: a bare
                # id is not something a part can weigh.
                tgt = g.get(q["target"], {}).get("doc", {}).get("label", "")
                L.append(f"  the relation asked about: does it have "
                         f"`{q['type']}` to `{q['target']}`"
                         + (f" ({tgt})?" if tgt else "?"))
            L.append(f"  asked by {q['asked_by']} in {q['source']}")

    if prop:
        L += ["", "**PROPOSED, AND NEVER YET PUT TO A ROOM.** Each names the "
              "parts asked to confirm or dispute it. If you are named, you are "
              "being asked.", ""]
        # key on the pair, never the dict — sorting (nid, {...})
        # tuples compares dicts the moment two nids tie.
        for nid, e in sorted(prop, key=lambda x: (x[0], x[1]['target'])):
            L.append(f"- `{nid}` —{e['type']}→ `{e['target']}`")
            L.append(f"  asked of: {', '.join(e.get('ask', [])) or '—'}")
            L.append(f"  basis: {_for_room(e.get('basis', ''))}")
    return "\n".join(L) + "\n"


WS_PREAMBLE = """\
*Projected from `issues/` for THIS circle's working set. **What is OWED.**
Better options — what is AVAILABLE — no longer project here; see
`self/best_practices.toml`, read directly at prompt-assembly time.*

**Each block says whose words it carries.** A node Self has ratified in a
circle says so; one still carrying the 2026-07-27 derivation's wording says
that, and should be held as provisional rather than as his testimony.

**The focus nodes are given whole. Related nodes are name and description
only** — enough to see what the focus touches, not enough to work them.

**A root is always among the focus nodes**, whether or not it was named —
a source the live graph descends from, shown whole every circle.

**Two focus nodes with no edge between them is deliberate**, not an omission.
Whether they are related is a question for the room; Self rules on whether an
edge is created.
"""


def main() -> int:
    """SHAPE + PROVENANCE over the live graph directly. Run bare by the
    pre-commit hook on any commit touching parts/ or self/ (which holds
    best_practices.toml since 2026-08-16) — this is the gate that keeps
    circle_briefing_build() and project_working_set()
    from ever handing a part a blank Label or an unverifiable ruling claim.

    RETIRED 2026-08-11, alongside self/circle_briefing.md: the PRESENCE check
    (was every block verbatim in the rendered file?) and the COVERAGE-in-chars
    line (the briefing's fixed size). Neither has a referent any more — Block
    2 is built fresh per circle, sized by the working set, with no
    intermediate file to compare bytes against."""
    fails: list[str] = []
    nodes = live_nodes()
    if not nodes:
        # AN EMPTY GRAPH IS A FRESH INSTALL, NOT A FAULT — ruled by the
        # operator 2026-08-26: *"treat an empty issues/ as fine so long as the
        # directory exists, is writable, and the code handles it cleanly."*
        #
        # It refused before, and refusing is what this check is FOR — but the
        # thing it was reporting was the install. "No issues yet" is the
        # correct state of every new copy of this package and of no
        # development tree, so the refusal fired exactly where nothing was
        # wrong and nowhere else. Found 2026-08-26 by running the built
        # bundle's own gates in a fresh clone.
        #
        # THE TWO CONDITIONS ARE CHECKED, NOT ASSUMED, because they are the
        # difference between "nothing here yet" and "nothing can go here":
        # a missing directory means the tree is not one this code can write a
        # node into, and an unwritable one means the first /issue-add will
        # fail at the moment a person is trying to name something.
        if not ISSUES.is_dir():
            print(f"  FAIL  {ISSUES.name}/ does not exist — an issue has "
                  f"nowhere to be written")
            return 1
        if not os.access(ISSUES, os.W_OK):
            print(f"  FAIL  {ISSUES.name}/ is not writable — /issue-add would "
                  f"fail at the moment it is used")
            return 1
        print("  PASS — no issues yet, and issues/ exists and is writable. "
              "A fresh\n         install carries none; they arrive as the "
              "room names them.")
        return 0

    blocks = []
    for p in nodes:
        b, f = issue_block_render(p)
        blocks.append((p.stem, b))
        fails += f

    ruled = [n for n, _ in blocks
             if f"*ruled by {ID.DISPLAY}" in dict(blocks)[n]]

    print(f"  {len(nodes)} live issue(s) · {len(ruled)} carry Self's ruling, "
          f"{len(nodes) - len(ruled)} carry the derivation's wording")

    if fails:
        print(f"\n  {len(fails)} FAILURE(S):")
        for f in fails:
            print(f"    - {f}")
        return 1
    print("  PASS — every live issue has a Label and an absence clause, and "
          "every\n         `ruled` provenance names a real transcript")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
