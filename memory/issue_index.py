#!/usr/bin/env python3
"""
issue_index.py — one scannable document for the whole issue graph.

    python memory/issue_index.py

Writes issues/INDEX.md. GENERATED, never hand-edited: a hand-maintained index is
how self/circle_briefing.md drifted until only 2 of 8 sampled quotes traced back
to source. Regenerate it; do not correct it.

Rewritten 2026-07-31 for the recognition pass. The graph was 35 unreviewed nodes
sorted by depth; it is now 9 nodes Self has ruled live and 26 that record a
ruling already made. So the index leads with the live nine, and everything it
counts — edges, inbound degree, leaves — counts LIVE edges only. Counting
retired edges would report a graph that no longer makes any claim.
"""

from __future__ import annotations

import collections
import sys
import datetime
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "coordinator"))  # atomic_write/identity et al.
import issue_schema as S  # noqa: E402
import record_paths as _RP                                         # noqa: E402
import working_set_manager as WS  # noqa: E402  the parsers and the pull (stage 10)

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = pathlib.Path(__file__).resolve().parent.parent
ISSUES = _RP.ISSUES_DIR


@_RP.group_follow
def _issues_rebind() -> None:
    """The index is the CURRENT group's — B117 stage 4 (2026-09-07)."""
    global ISSUES
    ISSUES = _RP.ISSUES_DIR


CLOSED = ("settled", "declined", "retired")
# A ROOT IS A LIVE NODE (R429, 2026-09-01), not a
# separate bucket beside live/leads/closed. It carries `root = true` in its
# own doc rather than a status of its own — permanent (never retired or
# demoted) and always shown in full at circle open, but counted here as
# part of `live`, the same set it is a member of. Until 2026-09-01 "root"
# was itself a status, counted disjointly from live; see rulings/ R089
# and R429 for the history.


def issue_index_read() -> dict:
    """TOML since 2026-08-03. Every field read through `issue_schema`, so this
    file no longer carries its own five regexes over a format with no grammar."""
    g = {}
    for p in S.issue_nodes_read():
        d = S.issue_read(p)
        nid = d["id"]
        ev = [e["source"] for e in d.get("evidence", [])]
        edges = [(e["type"], e["target"],
                  "retired" if e.get("status") == "retired" else "open")
                 for e in d.get("edges", [])]
        g[nid] = {
            "file": p.name,
            "label": d.get("label", "").strip() or nid,
            "desc": S.issue_unwrap(d.get("description", "")),
            "status": d["status"],
            "root": bool(d.get("root")),
            "held": sorted(set(e["part"] for e in d.get("evidence", []))),
            "n_ev": len(ev),

            "circles": sorted({e for e in ev if e.startswith("circle_")}),
            "edges": edges,
            "live_edges": [(a, b) for a, b, s in edges if s != "retired"],
        }
        # Self's own quotes, INCLUDING ANY HE HAS FORMALLY ADOPTED.
        #
        # Ruled 2026-08-02: "Count a statement formally adopted by me as if it
        # were my own." Until then this counted the `### self` heading alone and
        # reported nNNNN as 2 of 23 — a number used to rank the work queue while
        # 22 of those 23 were his, twenty of them one part's statements he had
        # read individually and taken as representative of himself. `part` says
        # who SPOKE a line; `adopted` says whose testimony it now is.
        adopted = {d["adopted"]["part"]} if d.get("adopted") else set()
        g[nid]["mine"] = sum(1 for e in d.get("evidence", [])
                             if e["part"] == "self" or e["part"] in adopted)
        g[nid]["adopted"] = sorted(adopted)
        g[nid]["ruled"] = bool(d.get("label_ruled"))
    return g


# THE WORKING SET. Ruled 2026-08-03: "Rename the table/graph option
# --working-set and expect a comma separated list of node numbers. Allow nodes
# of any type. Without a --working-set, emit graph and table for all issues/
# regardless of type."
#
# NO DEFAULT SET. Without the flag the whole of issues/ is emitted — every
# status, live and lead and root and closed alike. A view that silently hid
# nodes would be the opposite of what the graph is for.
#
# The set is explicit ids, never a count. A count would make the tool choose
# what Self attends to, and choosing is his.
#
# One addition the set does not ask for: any node an included node has a LIVE
# edge to is pulled in, and said so in the output. A view that cuts an edge in
# half draws a relation pointing at nothing.
# issue_id_normalise() and working_set_argv_parse() MOVED to working_set_manager.py, 2026-09-03
# (stage 10) — read as WS.*.


def issue_working_set_read(g, chosen):
    """(kept, pulled, unknown). `chosen` may name any node of any status.
    UNDIRECTED: both endpoints of a kept node's live edges are pulled. The
    walk itself is working_set_manager.working_set_pull() since 2026-09-03
    (stage 10) — this and issue_draw.issue_working_set_limit() were one loop
    written twice."""
    return WS.working_set_pull(
        g, chosen, lambda nid: [o for a, b in g[nid]["live_edges"] for o in (a, b)])


def main() -> int:
    chosen = WS.working_set_argv_parse(sys.argv[1:], issue_index_read())
    g = issue_index_read()
    live = [i for i in g if g[i]["status"] == "live"]
    leads = [i for i in g if g[i]["status"] == "lead"]
    roots = [i for i in live if g[i]["root"]]
    closed = [i for i in g if g[i]["status"] in CLOSED]

    inbound = collections.Counter()
    for n in g.values():
        for _, to in n["live_edges"]:
            if to in g:
                inbound[to] += 1
    pulled, unknown = [], []
    if chosen:
        keep, pulled, unknown = issue_working_set_read(g, chosen)
        if unknown:
            print(f"  unknown issue id(s) ignored: {', '.join(unknown)}")
        live = [i for i in keep if g[i]["status"] == "live"]
        leads = [i for i in keep if g[i]["status"] == "lead"]
        roots = [i for i in live if g[i]["root"]]
        closed = [i for i in keep if g[i]["status"] in CLOSED]
    n_live_edges = sum(len(n["live_edges"]) for n in g.values())
    n_retired = sum(len(n["edges"]) for n in g.values()) - n_live_edges
    latest = max((c for i in live for c in g[i]["circles"]), default="")

    order = sorted(live, key=lambda i: (-len(g[i]["circles"]), i))

    L = ["# Issue graph — index",
         "",
         "**GENERATED by `memory/issue_index.py`. Do not hand-edit — regenerate.**",
         f"*{datetime.date.today()} · {len(live)} live ({len(roots)} root) · "
         f"{len(leads)} leads · {len(closed)} closed · {sum(n['n_ev'] for n in g.values())} evidence quotes, "
         f"each machine-verified verbatim · {n_live_edges} live issue-relationships "
         f"({n_retired} retired)*",
         "",
         "## Status",
         "",
         "```",
         "live       Self has ruled it a live locus. Files keep the bare id,",
         "           unless it is also a root (below), which keeps R_.",
         "settled    it WAS an issue; the owing has been met.          S_",
         "declined   seen, chosen against. A completed act of agency.  D_",
         "retired    never was an issue. Miscategorised.               X_",
         "lead       may arrive as a FUTURE concern. Makes no claim,   L_",
         "           holds no issue-relationships, and keeps its evidence and id so",
         "           a circle can revive it with a rename.",
         "```",
         "",
         "**A root is not a status — it is a permanent flag on a live node.** "
         f"`root = true` marks a source the live graph descends from: {len(roots)} "
         "of the live nodes today. It is never retired or demoted, and it is "
         "shown in full at every circle regardless of the chosen working set. "
         "See `## Roots` below.",
         "",
         "The filename prefix repeats Status so that `ls issues/n0*.md` shows exactly "
         "the live issues. **The prefix is presentation; the id is identity** — headings, "
         "wikilinks and issue-relationships never carry it, so a ruling never rewrites a reference in "
         "another file. The gate requires prefix and Status to agree, which makes the "
         "duplication a cross-check rather than a second source of truth.",
         "",
         "**The live graph is closed.** An issue-relationship is legal only when both ends are live; "
         "everything else is retired with its reason and date, and the gate rejects any "
         "new one. Demoting an issue therefore *requires* retiring its issue-relationships.",
         ""]

    # ONE banner. A second, near-identical block used to follow, gated on
    # `len(live) < n_all` — a condition only a --working-set restriction
    # can produce, so it duplicated this banner under it and instructed
    # "Regenerate with `--all`, `--limit N`" — flags this tool has never
    # accepted (working_set_argv_parse knows --working-set and --live alone).
    # A generated document whose own instructions cannot restore the full
    # view is worse than none (2026-08-18 review, tier 2 #24).
    ruled = [n for n in live if g[n].get("ruled")]
    if chosen:
        L += ["", f"> **WORKING-SET VIEW — {len(live) + len(leads) + len(closed)} "
                  f"of {len(g)} issues, chosen by id.** Nothing has been removed "
                  f"from `issues/`; this is a view. "
                  + (f"`{'`, `'.join(pulled)}` "
                     f"{'was' if len(pulled) == 1 else 'were'} pulled in by a "
                     f"live issue-relationship, because a view that cuts one in half "
                     f"shows it pointing at nothing. " if pulled else "")
                  + "Regenerate without `--working-set` for the whole graph.", ""]
    L += ["---", "", f"## The live {len(live)}", "",
          "Deepest first. **`mine`** counts quotes that are Self's testimony — the own, "
          "plus any a part gave that he has FORMALLY ADOPTED, which the issue records in "
          "its `**Adopted:**` field. Ruled 2026-08-02: *\"Count a statement formally "
          "adopted by me as if it were my own.\"* Before that this column counted the "
          "`### self` heading alone and undercounted one issue as 2 of 23 when "
          "it is 22 of 23.",
          "",
          f"**`ruled`** marks a label Self has ratified in a circle — {len(ruled)} of "
          f"{len(live)} so far ({', '.join(f'`{n}`' for n in ruled) or 'none'}). The "
          "remaining rows are the A1 queue, and it is derivable rather than kept by "
          "hand: `grep -L '^\\*\\*Label ruled:\\*\\*' issues/n*.md`.", "",
          "| | id | issue | circles | held | mine / all | in | label |",
          "|-|----|-------|---------|------|------------|----|-------|"]
    for nid in order:
        n = g[nid]
        leaf = "◦" if inbound[nid] == 0 else " "
        label = n["label"][:50] + (" **(root)**" if n["root"] else "")
        L.append(f"| {leaf} | `{nid}` | {label} | {len(n['circles'])} | "
                 f"{len(n['held'])} | {n['mine']} / {n['n_ev']} | {inbound[nid]} | "
                 f"{'ruled' if n.get('ruled') else ''} |")
    L += ["", "◦ = nothing points at it. **(root)** = permanent, always shown "
              "in full at circle open — see `## Roots` below.", ""]

    if roots:
        L += ["---", "", f"## Roots — {len(roots)}", "",
              "A source the live graph descends from. Never retired or "
              "demoted; shown in full detail at every circle regardless of "
              "the chosen working set.", ""]
        for nid in sorted(roots):
            L.append(f"- `{nid}` — {g[nid]['label']}")
        L.append("")

    for nid in order:
        n = g[nid]
        L += [f"**`{nid}`** — {n['label']}", "", f"> {n['desc']}", ""]

    if n_live_edges:
        L += ["---", "", "## Live issue-relationships", ""]
        for nid in sorted(g):
            for etype, to in g[nid]["live_edges"]:
                L.append(f"- `{nid}` —`{etype}`→ `{to}`")
        L.append("")

    quiet = [i for i in live if g[i]["circles"] and g[i]["circles"][-1] < latest]
    if quiet:
        L += ["---", "", "## Gone quiet", "",
              "Live issues into which no part has spoken since. **Silence is not "
              "settlement** — one issue once went quiet for six weeks because no "
              "mechanism existed to raise it.", ""]
        for nid in sorted(quiet, key=lambda i: g[i]["circles"][-1]):
            L.append(f"- `{g[nid]['circles'][-1][7:17]}`  `{nid}`  {g[nid]['label'][:60]}")
        L.append("")

    # THE RULES ARE STATED, NOT QUOTED. Both of these sentences used to be
    # Self's own words, verbatim, written into a GENERATED document — so a
    # recipient's INDEX.md would have carried one person's rulings as if
    # they were theirs. --corpus-scan found the first. The rule is what
    # matters here; whose sentence it was belongs in rulings/.
    L += ["---", "", f"## Leads — {len(leads)}", "",
          "A lead means the thing may arrive as a future concern. It makes no "
          "claim and is not a rejection.", "",
          "**HISTORICAL ONLY — not a queue.** Leads stay under `issues/` but "
          "are not treated as a work queue: no actions are associated with "
          "these files. Nothing here is owed, nothing is pending, and no "
          "review is scheduled. Issues "
          "develop organically in circles; a lead returns only if a circle brings it "
          "back. Each keeps its evidence, its issue-relationships and its id so that return is a "
          "rename.", ""]
    for nid in sorted(leads, key=lambda i: (-len(g[i]["circles"]), i)):
        n = g[nid]
        L.append(f"- **`{nid}`** ({len(n['circles'])}c, {n['mine']} of {n['n_ev']} his) "
                 f"{n['label'][:60]}")

    L += ["", "---", "", f"## Closed — {len(closed)}", ""]
    for st in CLOSED:
        rows = sorted((i for i in closed if g[i]["status"] == st),
                      key=lambda i: -len(g[i]["circles"]))
        if rows:
            L.append(f"**{st}**")
            for nid in rows:
                L.append(f"- `{nid}` {g[nid]['label'][:60]}")
            L.append("")

    L += ["---", "", "## Issue-relationship census", "",
          f"{n_live_edges} live, {n_retired} retired.", ""]
    et = collections.Counter(t for n in g.values() for t, _ in n["live_edges"])
    for t, c in et.most_common():
        L.append(f"- `{t}` {c}")
    L += ["",
          "`polarized-with` at zero was itself a finding, recorded on the issue that "
          "discovered it — the circle converges rather than contests. That issue is "
          "now settled and moved to the engineering register "
          "(`work/instrument/LOG.md`), because it is a defect in "
          "the apparatus rather than a locus in a life. The measurement stands; only "
          "its home changed.",
          "",
          "`parallel_to` — same-root siblinghood — is **not** an issue-relationship type. Three "
          "independent arrivals are held in `work/instrument/LOG.md` E01 without being "
          "adopted.",
          ""]

    # A PLACEHOLDER MUST NEVER REACH THE OUTPUT. On 2026-08-07 the pass that
    # took node ids out of the shipping files (D5) rewrote this module's
    # prose along with its comments — and four of those strings are PAYLOAD,
    # written into issues/INDEX.md. Regenerating would have replaced three
    # real citations with `nNNNN` and `nPPPP` in a document that is private
    # and is supposed to carry real ids. Caught 2026-08-08 by running the
    # tool; nothing had run it since the rewrite.
    #
    # The underlying question — may a SHIPPING generator hold a PRIVATE id
    # in a payload string — is D36 and is Self's, and remains OPEN.
    #
    # SIDESTEPPED, not decided, 2026-08-09: the three sentences were reworded
    # to make their point without citing a specific node at all ("undercounted
    # one node as 2 of 23", "one node once went quiet", "the node that
    # discovered it"). The two original ids the corrupted strings needed were
    # still recoverable from `issues/INDEX.md`'s own last-good output on disk
    # (n0002, n0007, n0036) rather than git, since nothing had regenerated it
    # since the break — but they were not restored. If Self later rules D36
    # in favor of citing real ids in this generator's payload, that is a
    # deliberate re-add, not a revert.
    #
    # This guard stays regardless: a placeholder must never reach the output.
    body = "\n".join(L) + "\n"
    ph = sorted({m for m in ("nNNNN", "nMMMM", "nPPPP") if m in body})
    if ph:
        print(f"  REFUSED  INDEX.md would carry placeholder id(s): "
              f"{', '.join(ph)}")
        print(f"           issues/INDEX.md is UNCHANGED. See D36.")
        return 1
    (ISSUES / "INDEX.md").write_text(body, encoding="utf-8", newline="\n")
    print(f"  issues/INDEX.md — {len(live)} live ({len(roots)} root) · "
          f"{len(leads)} leads · {len(closed)} closed · "
          f"{n_live_edges} live issue-relationships")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
