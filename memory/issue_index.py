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

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = pathlib.Path(__file__).resolve().parent.parent
ISSUES = ROOT / "issues"
CLOSED = ("settled", "declined", "retired")
# ROOT is neither open nor closed: a source the live graph descends from,
# carrying no claim and owed nothing (R038, B23). Counted on its own so it
# cannot be read as either.
ROOTS = ("root",)


def load() -> dict:
    """TOML since 2026-08-03. Every field read through `issue_schema`, so this
    file no longer carries its own five regexes over a format with no grammar."""
    g = {}
    for p in S.nodes():
        d = S.load(p)
        nid = d["id"]
        ev = [e["source"] for e in d.get("evidence", [])]
        edges = [(e["type"], e["target"],
                  "retired" if e.get("status") == "retired" else "open")
                 for e in d.get("edges", [])]
        g[nid] = {
            "file": p.name,
            "label": d.get("label", "").strip() or nid,
            "desc": S.unwrap(d.get("description", "")),
            "status": d["status"],
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
def normalise_id(x):
    """Any of `2`, `nNNNN`, `L_n9999`, `S_n0099` -> the bare id.

    THE PREFIX IS PRESENTATION; THE ID IS IDENTITY — the project's own rule, and
    the reason this exists. Naming `L_n9999` and getting nothing back would be
    the tool disagreeing with its own filenames."""
    x = x.strip()
    if len(x) > 1 and x[1] == "_":
        x = x[2:]
    x = x.lstrip("nN")
    return f"n{int(x):04d}" if x.isdigit() else x


def parse_working_set(argv, g=None):
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
    return [normalise_id(x) for x in ids]


def working_set(g, chosen):
    """(kept, pulled). `chosen` may name any node of any status."""
    unknown = [c for c in chosen if c not in g]
    keep = [c for c in chosen if c in g]
    pulled = []
    for nid in list(keep):
        for a, b in g[nid]["live_edges"]:
            for other in (a, b):
                if other in g and other not in keep:
                    keep.append(other)
                    pulled.append(other)
    return keep, pulled, unknown


def main() -> int:
    chosen = parse_working_set(sys.argv[1:], load())
    g = load()
    live = [i for i in g if g[i]["status"] == "live"]
    leads = [i for i in g if g[i]["status"] == "lead"]
    roots = [i for i in g if g[i]["status"] in ROOTS]
    closed = [i for i in g if g[i]["status"] in CLOSED]

    inbound = collections.Counter()
    for n in g.values():
        for _, to in n["live_edges"]:
            if to in g:
                inbound[to] += 1
    pulled, unknown = [], []
    if chosen:
        keep, pulled, unknown = working_set(g, chosen)
        if unknown:
            print(f"  unknown issue id(s) ignored: {', '.join(unknown)}")
        live = [i for i in keep if g[i]["status"] == "live"]
        leads = [i for i in keep if g[i]["status"] == "lead"]
        roots = [i for i in keep if g[i]["status"] in ROOTS]
        closed = [i for i in keep if g[i]["status"] in CLOSED]
    n_live_edges = sum(len(n["live_edges"]) for n in g.values())
    n_retired = sum(len(n["edges"]) for n in g.values()) - n_live_edges
    latest = max((c for i in live for c in g[i]["circles"]), default="")

    order = sorted(live, key=lambda i: (-len(g[i]["circles"]), i))

    L = ["# Issue graph — index",
         "",
         "**GENERATED by `memory/issue_index.py`. Do not hand-edit — regenerate.**",
         f"*{datetime.date.today()} · {len(live)} live · {len(leads)} leads · "
         f"{len(roots)} root(s) · {len(closed)} closed · {sum(n['n_ev'] for n in g.values())} evidence quotes, "
         f"each machine-verified verbatim · {n_live_edges} live issue-relationships "
         f"({n_retired} retired)*",
         "",
         "## Status",
         "",
         "```",
         "live       Self has ruled it a live locus. Files keep the bare id.",
         "settled    it WAS an issue; the owing has been met.          S_",
         "declined   seen, chosen against. A completed act of agency.  D_",
         "retired    never was an issue. Miscategorised.               R_",
         "lead       may arrive as a FUTURE concern. Makes no claim,   L_",
         "           holds no issue-relationships, and keeps its evidence and id so",
         "           a circle can revive it with a rename.",
         "```",
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
    # accepted (parse_working_set knows --working-set and --live alone).
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
        L.append(f"| {leaf} | `{nid}` | {n['label'][:50]} | {len(n['circles'])} | "
                 f"{len(n['held'])} | {n['mine']} / {n['n_ev']} | {inbound[nid]} | "
                 f"{'ruled' if n.get('ruled') else ''} |")
    L += ["", "◦ = nothing points at it.", ""]

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
    # matters here; whose sentence it was belongs in RULINGS.md.
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
    print(f"  issues/INDEX.md — {len(live)} live · {len(leads)} leads · "
          f"{len(roots)} root(s) · {len(closed)} closed · "
          f"{n_live_edges} live issue-relationships")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
