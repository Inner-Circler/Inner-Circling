#!/usr/bin/env python3
"""
issue_draw.py — render the issue graph as a large SVG plus a self-contained page.

    python ui/issue_draw.py issues/            <- the LIVE graph
    python ui/issue_draw.py issues/ --if-stale <- only if the picture is behind
    python ui/issue_draw.py work/issue_derive/<RUN>/graph.json

Writes work/graph/issue_graph.svg and work/graph/issue_graph.html — a FIXED
output directory, never inside issues/ and no longer "beside this script".
The HTML inlines the SVG, so the page is one file with no network dependency
— it opens from disk and keeps working when the sandbox is deleted. A
graph.json snapshot still renders beside itself: that picture belongs to the
run that produced it, not to the live tree.

A PICTURE FOR THE PERSON WHOSE ISSUES THEY ARE — nothing a part or a gate
reads back. It moved coordinator/ -> work/graph/ 2026-08-13 as a development
tool beside its output, and work/graph/ -> ui/ 2026-08-27 (R365) when it
stopped being one: it SHIPS now, and a live /close redraws it. Its siblings
(command_flow_draw.py, prompt_grammar_draw.py, coordinator_draw.py,
system_architecture_draw.py) stayed in work/graph/ — they draw the CODE, for
whoever is building it. This one draws the RECORD, for whoever is living it.

RUN AT EVERY LIVE /close, coordinator/circle.py, just after the vetting
checkpoint and before short_terms are collected — the moment the graph is
final for that circle. Both routes a circle can move the graph are behind
that point: a ruling typed at cmd> (or into the transcript as an
annotation), applied by issue_commands.issue_command_apply(); and a [proposed: ...] row
accepted at the checkpoint, applied by the same function through
proposal_vetting.py. WHAT IT ACTUALLY TESTS IS STALENESS, not either route —
issue_draw_is_stale() below compares issues/*.toml against the picture's own mtime, so
a hand edit, an aborted circle whose cmd> rulings already landed, and a
brand-new install with no picture at all are all caught by the same test,
and a close that changed nothing costs nothing. Nothing there can fail the
close: circle.py wraps the call and reports a skip.

NEITHER OUTPUT FILE IS TRACKED (.gitignore, R365, the operator's ruling:
"local only"). It is rebuilt at the end of every circle and committed by
nothing, so a tracked copy would sit permanently dirty — the shape that
already bit closing_<OT>.json and dream_<OT>.json and deadlocked a lab
refresh. It ships as an EMPTY directory: packaging/scaffold/work/graph/
carries a README and nothing else, so a recipient gets the folder and their
own first circle fills it.

LAYOUT
    Force-directed (Fruchterman-Reingold), deterministic seed, with one bias: a
    node's evidence depth pulls it toward the centre. So the spine sits in the
    middle and the thin single-circle nodes fall to the rim, which is the shape
    the review actually needs — depth is the thing you cannot see in a list.

    The "all" view is TWO ROWS (the operator, 2026-08-17): communities of more than
    one member shelf-pack into a top row; single-node communities — nothing
    in THIS view relates them to anything else — shelf-pack into their own
    row underneath. A node can still carry edges across the two rows (a
    retired edge from a top-row live node to a bottom-row non-live one,
    typically); the split is purely about where community detection placed
    a node, never about hiding what connects to what. The "live" view and
    a --working-set view stay one row, unchanged.

ENCODING
    label        at the node itself — what it MEANS, read first
    n#### · Nc   beneath: the stable id, and depth in distinct circles
    radius       evidence count
    fill         tier: spine (>=8 circles) / thread (3-7) / thin (<3)
    ring         LEAF — nothing depends on it, so it can settle without
                 unblocking anything else. The tractable front.
    edge colour  relation type
    dashed edge  proposed rather than attested — the model's inference, not a
                 part's testimony.
    faint dotted retired — legal no longer (an edge is legal only when both
    edge          ends are live — a root counts, it is live). "all" view
                 only, 2026-08-17: drawn to show where a live node's history
                 reaches a lead/settled/declined node, never in the
                 live view or a --working-set view — see main()'s own strip
                 before each of those.
"""

from __future__ import annotations

import itertools
import json
import math
import pathlib
import random
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ui/ is not on sys.path when this is imported rather than run — circle.py
# spawns it at a live close, and the probe imports it.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "coordinator"))   # working_set_manager (stage 10)
import palette as P                                            # noqa: E402
import working_set_manager as WS                               # noqa: E402
import record_paths as _RP                                         # noqa: E402
ISSUES_DIR = _RP.ISSUES_DIR

# THE OUTPUT DIRECTORY IS NAMED, not derived from __file__. It was
# `__file__.parent` while this script lived in work/graph/, which is exactly
# the kind of derivation a move breaks silently — this one would have
# started writing the picture into ui/. Ruled R365: ONE folder,
# work/graph/, the same one the other picture tools already use.
OUT_DIR = ROOT / "work" / "graph"
OUT_SVG = OUT_DIR / "issue_graph.svg"
OUT_HTML = OUT_DIR / "issue_graph.html"


def issue_draw_out_bind(issues_dir: pathlib.Path) -> None:
    """Point OUT_SVG/OUT_HTML at the picture belonging to the group whose issues/ this is —
    audit-register.md #6, 2026-09-08.

    ONE FOLDER, TWO CONSEQUENCES, AND THE SECOND IS THE BAD ONE. R365 ruled ONE output
    folder and that is unchanged; what was missing is that the FILENAMES were group-blind
    while circle.py:1977 runs the redraw at every live close OF ANY GROUP, handing over that
    group's own issues/ (group-aware since 60af4de). So a band close overwrote the IFS
    group's picture — and worse, issue_draw_is_stale() compared THIS group's newest source
    mtime against the SHARED picture's mtime, so after an IFS close wrote a fresh picture a
    band close would decide "not stale", print nothing, and never draw at all. Silent, and
    the reverse of what the staleness test exists to guarantee.

    THE DEFAULT GROUP KEEPS THE PLAIN NAME. Its picture is the one a person has open, the
    one .gitignore names literally, and the one every doc points at; renaming it to buy
    symmetry would cost all three for nothing. Another group gets `issue_graph_<name>.*`
    beside it.

    A DIRECTORY THAT IS NO GROUP'S issues/ CHANGES NOTHING — a hand-run against an arbitrary
    directory, or a graph.json snapshot, keeps the default names, exactly as before."""
    global OUT_SVG, OUT_HTML
    try:
        resolved = issues_dir.resolve()
    except OSError:                                    # pragma: no cover — a vanished path
        return
    for name in _RP.group_present_read():
        if resolved != (_RP.group_tree(name) / "issues").resolve():
            continue
        stem = "issue_graph" if name == _RP.DEFAULT_GROUP else f"issue_graph_{name}"
        OUT_SVG = OUT_DIR / f"{stem}.svg"
        OUT_HTML = OUT_DIR / f"{stem}.html"
        return

# issue_schema.py lives in memory/, not beside this script — it moved here
# 2026-08-13 (coordinator/ -> work/graph/, alongside its own output), so
# unlike before, Python's automatic script-directory sys.path entry no
# longer finds it. It moved AGAIN 2026-08-16 (coordinator/ -> memory/, the
# R203 follow-on that relocated the whole issue-graph code family) — this
# path was never updated for that second move, and _check_vocabulary()
# below has been a hard crash since, since nothing regenerates this picture
# automatically to have caught it sooner. Inserted once, at import time,
# since _check_vocabulary() needs it before main() ever runs.
#
# ROOT-RELATIVE SINCE 2026-08-27, and that is the whole fix for a THIRD
# instance of the same defect: the hop was `.parent.parent.parent`, correct
# from work/graph/ and one directory too far from ui/. A path written as a
# count of hops is a path that breaks every time its file moves, and this
# file has now moved twice.
sys.path.insert(0, str(ROOT / "memory"))

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def issue_draw_read(d: pathlib.Path) -> dict:
    """Read the graph out of issues/*.toml — every node, every status.

    graph.json is the derivation's sandbox output and stops being the truth the
    moment a node is hand-edited, renamed, merged or added. Since 2026-07-28 it is
    three nodes short and one rename behind. The drawing must render what the
    parts will actually be shown, so it reads the files."""
    # EVERY NODE, since 2026-08-03: "Allow nodes of any type." Live only was
    # right while the drawing was the whole graph; it is wrong now that
    # `--working-set` names the view, because naming a lead and being told it
    # does not exist is the tool disagreeing with its own filenames.
    #
    # Without --working-set the default is still every node — the picture shows
    # what is there. THE PREFIX IS PRESENTATION; THE ID IS IDENTITY, so a file
    # named L_n9999.toml is keyed nNNNN and its status comes from the field.
    g = {}
    import issue_schema as S
    for f in sorted(d.glob("*n[0-9][0-9][0-9][0-9].toml")):
        doc = S.issue_read(f)
        nid = doc["id"]
        ev = [{"circle": e["source"], "quote": e["quote"], "part": e["part"]}
              for e in doc.get("evidence", [])
              if e["source"].startswith("circle_")]
        # RETIRED EDGES LOADED, DRAWN ONLY IN "all" — reversed 2026-08-17
        # (the operator: "DO add edges to/from non-live nodes to live nodes, only
        # in the 'all' graph"). Found 2026-08-04: excluding them here
        # entirely, once, meant the drawing rendered all 50 edges — 44 of
        # them retired — with the same stroke as a proposed one and the
        # label "(proposed)" in the panel, and it was ALSO what pulled
        # eight dead nodes into `--live`. Both defects are still real
        # constraints, just satisfied downstream now instead of by
        # dropping the data at the source: main() strips retired edges
        # before building the live view and before --working-set
        # selection (neither asked to change), and issue_svg_build() gives a
        # retired edge its own visual treatment, distinct from proposed —
        # see the "retired" key below and its use at the dash site.
        edges = [{"type": e["type"], "to": e["target"],
                  "attested": e.get("status") == "attested",
                  "retired": e.get("status") == "retired",
                  "basis": S.issue_unwrap(e.get("basis", ""))}
                 for e in doc.get("edges", [])]
        g[nid] = {"label": doc.get("label", "").strip() or nid,
                  "description": S.issue_unwrap(doc.get("description", "")),
                  # `absence` was hardcoded to "" and had been since the
                  # drawing was written — so the panel printed "Absence:" with
                  # nothing after it for every node, on every render, while the
                  # schema REQUIRES the field of every node. Found 2026-08-04
                  # by Self reading the table and asking whether it was
                  # "mostly null". It was always null.
                  "absence": S.issue_unwrap(doc.get("absence", "")),
                  "evidence": ev, "edges": edges, "actions": [],
                  "held": sorted({e["part"] for e in doc.get("evidence", [])}),
                  "opened": doc.get("opened", "").replace("circle_", ""),
                  "status": doc["status"],
                  # `root` — R429, 2026-09-01. Missed on
                  # the first pass: issue_draw_describe()'s root count and any future
                  # root-aware drawing both read this dict, not the TOML
                  # directly, so a field this loader does not copy is
                  # invisible everywhere downstream, silently.
                  "root": bool(doc.get("root"))}
    return g


W, H = 2400, 1250
# THE KEY IS A PROJECTION OF THE VOCABULARY, and it had fallen out of sync in
# BOTH directions by 2026-08-04, when Self read it:
#
#   consequence-of  RETIRED that morning, still in the key, still glossed
#                   "arose from" — the backward reading the rename existed to
#                   remove, printed under a drawing that no longer contains it.
#   leads-to        THE REPLACEMENT, and never added. Line ~426 falls back to
#                   ("#999", ""), so the descent chain — the graph's only
#                   attested movement, and the reason those circles were run —
#                   was drawn in a grey one hex step from `related-to`'s and
#                   named nowhere in the key.
#
# Glosses are the one-line form of the vocabulary issue_prompt_projection.issue_relationship_brief()
# generates for BLOCK 2; docs/issue_relationship_types.md (archived) was its long form.
# `_check_vocabulary()` below now fails if this table and issue_schema ever
# disagree again; nothing checked it before, which is why it drifted silently
# through ten edge migrations.
# THE COLOURS COME FROM ui/palette.py SINCE 2026-08-30. They were the same
# four hex strings work/graph/palette.py holds — this tool left that directory
# for ui/ at R365 and carried them out by hand, so a fifth drawing agreed with
# the other four by luck. The roles line up exactly with what the edges mean:
# laddering is the settled green, cause-and-effect the gold of what is owed,
# protection the coordinator's purple, opposition red. `related-to` keeps its
# own grey — the weakest claim has no role in the palette, and #8a8a8a is not
# MUTED's {P.MUTED}, so importing one for the other would move the picture.
EDGE_STYLE = {
    "narrower-than":  (P.GREEN, "laddering — up for meaning, down for the concrete"),
    "leads-to":       (P.GOLD, "gives rise to — cause first, forward in time"),
    "protects":       (P.PURPLE, "stands in front of"),
    "related-to":     ("#8a8a8a", "associative — the weakest claim"),
    "polarized-with": (P.RED, "opposed strategies escalating against each other"),
}


def _check_vocabulary() -> None:
    """The key must name every legal type and no illegal one."""
    import issue_schema as _S
    missing = _S.EDGE_TYPES - set(EDGE_STYLE)
    extra = set(EDGE_STYLE) - _S.EDGE_TYPES
    if missing or extra:
        raise SystemExit(
            f"  EDGE_STYLE disagrees with issue_schema.EDGE_TYPES\n"
            f"    missing from the key (drawn grey, unnamed): "
            f"{sorted(missing) or 'none'}\n"
            f"    obsolete, still printed: {sorted(extra) or 'none'}")


_check_vocabulary()
TIERS = [("spine", 8, P.GREEN), ("thread", 3, P.PURPLE), ("thin", 0, "#9a9a9a")]


def issue_tier_read(depth: int):
    for name, lo, col in TIERS:
        if depth >= lo:
            return name, col
    return "thin", "#9a9a9a"


def issue_communities_read(g: dict) -> dict:
    """Greedy modularity (Clauset-Newman-Moore agglomeration).

    Label propagation was tried first and collapsed 29 of 32 nodes into one
    community — a hub of degree 10 absorbs everything, which is exactly the shape
    that made the first drawing unreadable. Modularity asks a better question:
    not "who is connected" but "who is connected MORE than chance would predict",
    so a hub does not swallow its neighbourhood.

    Deterministic: merges are evaluated in sorted order and ties broken by id.

    RETIRED EDGES EXCLUDED, 2026-08-17 — they're loaded and drawn now (the
    "all" view only), but a retired edge is a dead claim, not a live
    relationship, and letting it count here re-merged the very singletons
    the two-row split exists to isolate: 8 became 0 the moment retired
    edges joined this adjacency, since most of them ARE a non-live node
    connected to the graph by nothing but a retired edge."""
    adj = {i: Counter() for i in g}
    for nid, n in g.items():
        for e in n["edges"]:
            if e["to"] in g and e["to"] != nid and not e.get("retired"):
                w = 2.0 if e["attested"] else 1.0
                adj[nid][e["to"]] += w
                adj[e["to"]][nid] += w
    m2 = sum(sum(c.values()) for c in adj.values())
    if m2 == 0:
        return {i: i for i in g}
    members = {i: {i} for i in g}
    a = {i: sum(adj[i].values()) / m2 for i in g}
    e = {i: Counter({j: w / m2 for j, w in adj[i].items()}) for i in g}
    live = set(g)
    while True:
        best, bq = None, 1e-9
        for i in sorted(live):
            for j in sorted(e[i]):
                if j <= i or j not in live:
                    continue
                dq = 2 * (e[i][j] - a[i] * a[j])
                if dq > bq:
                    best, bq = (i, j), dq
        if not best:
            break
        i, j = best
        members[i] |= members[j]
        for k, w in e[j].items():
            if k != i:
                e[i][k] += w
                e[k][i] += w
            e[k].pop(j, None)
        e[i].pop(j, None)
        a[i] += a[j]
        live.discard(j)
        del members[j]
    out = {}
    for c, mem in members.items():
        for i in mem:
            out[i] = c
    return out


def _fr(ids, adj, pos, iters, k, temp, anchor=None, pull=0.0):
    t = temp
    for _ in range(iters):
        disp = {i: [0.0, 0.0] for i in ids}
        for a in ids:
            for b in ids:
                if a == b:
                    continue
                dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
                d2 = dx * dx + dy * dy + 1e-9
                f = k * k / d2
                disp[a][0] += dx * f
                disp[a][1] += dy * f
        for a in ids:
            for b in adj.get(a, ()):
                if b not in pos:
                    continue
                dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
                d = math.hypot(dx, dy) + 1e-9
                f = d / k * 0.05
                disp[a][0] -= dx / d * f
                disp[a][1] -= dy / d * f
        for i in ids:
            if anchor and pull:
                disp[i][0] -= (pos[i][0] - anchor[0]) * pull
                disp[i][1] -= (pos[i][1] - anchor[1]) * pull
            d = math.hypot(*disp[i]) + 1e-9
            pos[i][0] += disp[i][0] / d * min(d, t)
            pos[i][1] += disp[i][1] / d * min(d, t)
        t *= 0.97


def issue_draw_box(g, nid):
    """Footprint including the label, which is what actually collides."""
    r = 18 + math.sqrt(len(g[nid]["evidence"])) * 6
    lab = g[nid]["label"]
    wrapped = max(len(x) for x in issue_label_wrap(lab)) if lab else 8
    # Deliberately conservative: the label is centred on the node now, so the
    # true vertical extent is smaller than this. Over-reserving costs whitespace;
    # under-reserving costs a collision.
    return max(2 * r + 14, wrapped * 6.1 + 10), 2 * r + 34


def issue_label_wrap(lab: str, width: int = 30, lines: int = 3) -> list[str]:
    """30x3 = 90 characters. Labels run to 103, median 53.

    At the previous 24x2 = 48, twenty-two of thirty-two labels truncated \u2014 which
    defeats putting the label at the node in the first place. Widening costs
    canvas (content grew 1503x811 -> 1691x910, still inside 2400x1250) and cuts
    truncation from twenty-two labels to one."""
    out, cur = [], ""
    for w in lab.split():
        if len(cur) + len(w) + 1 > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
        if len(out) == lines:
            break
    if cur and len(out) < lines:
        out.append(cur)
    if not out:
        out = [lab[:width]]
    if len(lab) > sum(len(x) for x in out) + len(out) - 1:
        out[-1] = out[-1][:width - 1] + "\u2026"
    return out


def issue_draw_separate(g, pos, rounds=600):
    """Hard overlap removal. Force-directed gets the shape right and the spacing
    wrong; this guarantees no two footprints overlap, which is the difference
    between a picture and a diagram. Runs after layout so it cannot distort the
    clustering, only relieve it."""
    ids = list(pos)
    bx = {i: issue_draw_box(g, i) for i in ids}
    for _ in range(rounds):
        moved = False
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                i, j = ids[a], ids[b]
                dx = pos[j][0] - pos[i][0]
                dy = pos[j][1] - pos[i][1]
                ox = (bx[i][0] + bx[j][0]) / 2 - abs(dx)
                oy = (bx[i][1] + bx[j][1]) / 2 - abs(dy)
                if ox > 0 and oy > 0:
                    moved = True
                    if ox < oy:
                        s = (ox / 2 + 0.6) * (1 if dx >= 0 else -1)
                        pos[i][0] -= s
                        pos[j][0] += s
                    else:
                        s = (oy / 2 + 0.6) * (1 if dy >= 0 else -1)
                        pos[i][1] -= s
                        pos[j][1] += s
        if not moved:
            break
    return pos


def issue_draw_layout(g: dict, seed: int = 7, two_row: bool = False) -> tuple[dict, dict]:
    """Cluster, lay each cluster out on its own, then PACK the clusters as rigid
    blocks.

    Two earlier attempts failed in instructive ways. A single global
    force-directed pass let the degree-10 hub collapse everything around it. A
    per-cluster pass followed by a global pass fixed node overlap but scattered
    members across cluster boundaries, so all five cluster regions
    interpenetrated — worse than no clustering, because it implied groupings that
    the drawing then contradicted.

    So the clusters never move relative to their own members. Each is laid out
    and separated internally, its bounding box measured, and the boxes are
    shelf-packed. Cluster regions cannot overlap because they are placed as
    units.

    two_row — the operator, 2026-08-17, the "all" view only (the "live" view keeps
    the plain one-row pack; its own call site passes two_row=False, the
    default, so this is additive, not a behavior change for it). A
    single-node community carries no relation to anything ELSE IN THE SAME
    VIEW — that's what "ungrouped" means here, not "no edges at all";
    plenty of these singletons have a live<->non-live edge drawn separately
    below, per-edge, once positions exist. Multi-node communities
    shelf-pack into a TOP row exactly as before; singletons shelf-pack into
    their OWN row underneath, positioned after the top row's own height is
    known. Edges between the two rows are untouched by this split — the
    edge-drawing pass in issue_svg_build() reads every node's position out of the
    same flat `pos` dict this function returns either way, live or
    non-live, top row or bottom, and was never filtered by row or status to
    begin with."""
    rnd = random.Random(seed)
    comm = issue_communities_read(g)
    groups = {}
    for i, c in comm.items():
        groups.setdefault(c, []).append(i)

    adj = {i: set() for i in g}
    for nid, n in g.items():
        for e in n["edges"]:
            if e["to"] in g:
                adj[nid].add(e["to"])
                adj[e["to"]].add(nid)

    blocks = []
    for c, mem in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        mem = sorted(mem)
        sub = {i: set(adj[i]) & set(mem) for i in mem}
        local = {i: [rnd.uniform(-1, 1), rnd.uniform(-1, 1)] for i in mem}
        _fr(mem, sub, local, 320, 0.55, 0.30)
        span = 150 + 42 * math.sqrt(len(mem))
        xs = [p[0] for p in local.values()]
        ys = [p[1] for p in local.values()]
        rx = (max(xs) - min(xs)) or 1
        ry = (max(ys) - min(ys)) or 1
        for i in mem:
            local[i] = [(local[i][0] - min(xs)) / rx * span,
                        (local[i][1] - min(ys)) / ry * span * 0.78]
        local = issue_draw_separate(g, local)
        xs = [p[0] for p in local.values()]
        ys = [p[1] for p in local.values()]
        bw = max(xs) - min(xs) + max(issue_draw_box(g, i)[0] for i in mem) + 64
        bh = max(ys) - min(ys) + max(issue_draw_box(g, i)[1] for i in mem) + 74
        for i in mem:
            local[i][0] -= min(xs)
            local[i][1] -= min(ys)
        blocks.append({"c": c, "mem": mem, "local": local, "w": bw, "h": bh})

    # shelf-pack the blocks, tallest first, into the canvas width. ONE ROW,
    # always, per-call — the operator, 2026-08-16: lay the groups out horizontally.
    # avail set to the sum of a row's own block widths (plus their gaps)
    # can never be exceeded by any running total, so the wrap condition
    # below never fires within a row; the fitted viewBox scales the
    # resulting wide strip up to the frame the same way the old 1.7:1
    # target did for a squarer one.
    m, gap = 48, 30

    def _pack_row(row_blocks, y0, presorted=False):
        row_blocks = row_blocks if presorted else sorted(row_blocks, key=lambda b: -b["h"])
        avail = sum(b["w"] for b in row_blocks) + gap * max(1, len(row_blocks))
        x, y, shelf = m, y0, 0
        for b in row_blocks:
            if x > m and x + b["w"] > m + avail:
                x, y, shelf = m, y + shelf + gap, 0
            b["x"], b["y"] = x, y
            x += b["w"] + gap
            shelf = max(shelf, b["h"])
        return y + shelf

    if two_row:
        # "ungrouped" = a singleton community — has no edge to anything ELSE
        # IN THIS VIEW, which is the only sense "grouped" can mean once
        # community detection has already run. The operator, 2026-08-17.
        top = [b for b in blocks if len(b["mem"]) > 1]
        bottom = [b for b in blocks if len(b["mem"]) == 1]
        bottom_y0 = _pack_row(top, m) + gap if top else m

        # ORDERING THE BOTTOM ROW, the operator 2026-08-17: "minimize edge length
        # and crossings." `adj` above already includes retired edges —
        # exactly what connects this row to the rest of the graph (a
        # singleton with no retired edge has no other edge either, or it
        # would not be a singleton). The top row is packed and fixed
        # first; only the bottom row's LEFT-TO-RIGHT ORDER is chosen here.
        if bottom:
            top_pos = {}
            for b in top:
                ox = b["x"] + (b["w"] - (max(p[0] for p in b["local"].values()) or 1)) / 2
                oy = b["y"] + (b["h"] - (max(p[1] for p in b["local"].values()) or 1)) / 2
                for i in b["mem"]:
                    top_pos[i] = (b["local"][i][0] + ox, b["local"][i][1] + oy)
            by_id = {b["mem"][0]: b for b in bottom}
            bottom_ids = set(by_id)

            # EVERY EDGE THE PICTURE ACTUALLY DRAWS, split into what a
            # bottom-row reorder can move (touches a bottom node) and what
            # it cannot (both ends inside the already-packed top row). The
            # first version of this scored the moving set against itself
            # only — a real 1-crossing minimum, but over that narrow
            # subset alone. The operator, 2026-08-17, reading the rendered SVG:
            # the winning order sent n0015's edges clear across the
            # canvas, through the top-row clusters and the edges inside
            # them, none of which the old score ever looked at. Fixed
            # segments are computed once, since neither endpoint moves.
            moving_edges, fixed_segs = [], []
            for nid, n in g.items():
                for e in n["edges"]:
                    b = e["to"]
                    if b not in g:
                        continue
                    if nid in bottom_ids or b in bottom_ids:
                        moving_edges.append((nid, b))
                    else:
                        fixed_segs.append((top_pos[nid], top_pos[b]))

            def _orient(px, py, qx, qy, rx, ry):
                v = (qx - px) * (ry - py) - (qy - py) * (rx - px)
                return 0 if -1e-9 < v < 1e-9 else (1 if v > 0 else -1)

            def _cross(s1, s2):
                """True line-segment intersection, not an x-interval proxy —
                the top row's own members don't share one y, so two edges can
                have overlapping x-spans and never actually cross, or the
                reverse. Two edges meeting at a shared node are not a
                crossing."""
                p1, p2 = s1
                p3, p4 = s2
                if p1 in (p3, p4) or p2 in (p3, p4):
                    return False
                d1 = _orient(*p3, *p4, *p1)
                d2 = _orient(*p3, *p4, *p2)
                d3 = _orient(*p1, *p2, *p3)
                d4 = _orient(*p1, *p2, *p4)
                return bool(d1 and d2 and d3 and d4 and d1 != d2 and d3 != d4)

            def _score(order_ids):
                trial = [by_id[i] for i in order_ids]
                _pack_row(trial, bottom_y0, presorted=True)
                xy = dict(top_pos)
                for b in trial:
                    xy[b["mem"][0]] = (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
                segs = [(xy[a], xy[c]) for a, c in moving_edges]
                total_len = sum(math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1])
                                for p in segs)
                crossings = 0
                for i in range(len(segs)):
                    for j in range(i + 1, len(segs)):
                        if _cross(segs[i], segs[j]):
                            crossings += 1
                    for fs in fixed_segs:
                        if _cross(segs[i], fs):
                            crossings += 1
                return crossings, total_len

            ids = sorted(by_id)
            if len(ids) <= 8:
                # EXACT. 8! = 40320 orderings, each a cheap re-pack (box
                # width varies by label length, so the x-SLOTS themselves
                # move depending on who's in them — a permutation of node
                # IDENTITIES has to be re-packed per candidate, not just
                # reassigned to a fixed set of slots). (crossings, length)
                # ranks crossings first — the sharper visual defect — and
                # length only breaks a tie. Tried every one and kept the
                # best; nothing here is a heuristic.
                best_order, best_score = ids, _score(ids)
                for perm in itertools.permutations(ids):
                    s = _score(perm)
                    if s < best_score:
                        best_score, best_order = s, perm
                _score(best_order)   # leaves _pack_row at the winner
            else:
                # FALLBACK past 8: exact search is 9! = 362880+ candidates,
                # too slow for a by-hand tool. Barycenter (Sugiyama et
                # al.'s standard two-layer crossing heuristic) instead —
                # each node's target x is the mean x of its neighbors,
                # re-sorted and re-packed for a few rounds to let
                # bottom-bottom edges (not just the cross-row ones) settle.
                _pack_row(bottom, bottom_y0)
                cx = {i: b["x"] + b["w"] / 2 for i, b in by_id.items()}
                for _ in range(4):
                    bary = {}
                    for nid in by_id:
                        xs = [top_pos[j][0] if j in top_pos else cx[j]
                             for j in adj[nid] if j in top_pos or j in cx]
                        bary[nid] = sum(xs) / len(xs) if xs else cx[nid]
                    order = sorted(by_id, key=lambda i: (bary[i], i))
                    _pack_row([by_id[i] for i in order], bottom_y0, presorted=True)
                    cx = {i: b["x"] + b["w"] / 2 for i, b in by_id.items()}
    else:
        _pack_row(blocks, m)

    pos = {}
    for b in blocks:
        ox = b["x"] + (b["w"] - (max(p[0] for p in b["local"].values()) or 1)) / 2
        oy = b["y"] + (b["h"] - (max(p[1] for p in b["local"].values()) or 1)) / 2
        for i in b["mem"]:
            pos[i] = (b["local"][i][0] + ox, b["local"][i][1] + oy)
    return pos, comm


def issue_draw_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


CLUSTER_FILL = ["#eef4f0", "#f2eef6", "#f6f1e8", "#eef1f6", "#f6eeee", "#eff5f5"]


def issue_svg_build(g: dict, pos: dict, inbound: Counter, comm: dict) -> str:
    depth = {i: len({e["circle"] for e in g[i]["evidence"]}) for i in g}
    # THE VIEWBOX IS FITTED TO THE CONTENT, not to the canvas.
    # The layout was tuned for 32 nodes on a 2400x1250 field. After the
    # recognition pass of 2026-07-31 there are 9, and they occupied about a
    # sixth of the frame at a size no one could read. Fitting the viewBox to
    # the drawn extent scales everything — node circles, labels, legend, all of
    # which are in user units — so the picture fills the frame at any node
    # count, and gets larger as the graph gets smaller.
    xs = [pos[i][0] for i in pos] or [0]
    ys = [pos[i][1] for i in pos] or [0]
    rr = max((18 + math.sqrt(len(g[i]["evidence"])) * 6) for i in pos) if pos else 30
    m = rr + 66                      # node radius, its two label lines, breathing room
    vx0, vx1 = min(xs) - m, max(xs) + m
    vy0, vy1 = min(ys) - m, max(ys) + m
    LEGEND_H = 168
    vy1 += LEGEND_H
    vw, vh = vx1 - vx0, vy1 - vy0
    # Keep the frame from going extreme when the graph is a thin line of
    # nodes. The upper bound was 2.8 until issue_draw_layout()'s single-row shelf-pack
    # (the operator, 2026-08-16: lay the groups out horizontally) made a wide
    # frame the NORMAL case rather than an edge case — 2.8 was squashing
    # every run back toward square, undoing the point of the change. Raised
    # to 6; still a real ceiling for a pathological case (many singleton
    # groups in one row could in principle run wider than that), not
    # removed outright.
    if vw / vh < 0.95:
        grow = vh * 0.95 - vw
        vx0 -= grow / 2; vx1 += grow / 2; vw = vx1 - vx0
    elif vw / vh > 6:
        grow = vw / 6 - vh
        vy0 -= grow / 2; vy1 += grow / 2; vh = vy1 - vy0
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'viewBox="{vx0:.0f} {vy0:.0f} {vw:.0f} {vh:.0f}" '
           f'width="{W}" height="{W * vh / vw:.0f}" '
           f'font-family="system-ui,sans-serif">',
           '<defs>']
    for t, (c, _) in EDGE_STYLE.items():
        out.append(f'<marker id="a-{t}" markerWidth="10" markerHeight="8" refX="9" '
                   f'refY="4" orient="auto"><polygon points="0 0,10 4,0 8" '
                   f'fill="{c}"/></marker>')
    out.append('</defs>')
    out.append(f'<rect x="{vx0:.0f}" y="{vy0:.0f}" width="{vw:.0f}" '
               f'height="{vh:.0f}" fill="{P.GROUND}"/>')

    # cluster regions, drawn under everything: a rounded box around each
    # community, named for its highest-degree member. Relational clustering made
    # visible — these groups came out of the edges, not out of a category list.
    deg = Counter()
    for nid, n in g.items():
        for e in n["edges"]:
            if e["to"] in g:
                deg[nid] += 1
                deg[e["to"]] += 1
    groups = {}
    for i, c in comm.items():
        groups.setdefault(c, []).append(i)
    for gi, (c, mem) in enumerate(sorted(groups.items(),
                                         key=lambda kv: -len(kv[1]))):
        if len(mem) < 2:
            continue
        xs = [pos[i][0] for i in mem]
        ys = [pos[i][1] for i in mem]
        pad = 52
        x0, x1 = min(xs) - pad, max(xs) + pad
        y0, y1 = min(ys) - pad - 8, max(ys) + pad + 22
        hub = max(mem, key=lambda i: (deg[i], len(g[i]["evidence"])))
        name = g[hub]["label"][:40]
        out.append(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{x1-x0:.0f}" '
                   f'height="{y1-y0:.0f}" rx="26" fill="'
                   f'{CLUSTER_FILL[gi % len(CLUSTER_FILL)]}" stroke="#dcdcd6" '
                   f'stroke-dasharray="7 6"/>')
        out.append(f'<text x="{x0+18:.0f}" y="{y0+24:.0f}" font-size="13" '
                   f'font-weight="700" fill="#9a9a92">{len(mem)} · '
                   f'{issue_draw_escape(name)}</text>')

    for nid, n in g.items():                                     # edges first
        for e in n["edges"]:
            if e["to"] not in pos:
                continue
            c, _ = EDGE_STYLE.get(e["type"], ("#999", ""))
            x1, y1 = pos[nid]
            x2, y2 = pos[e["to"]]
            dx, dy = x2 - x1, y2 - y1
            d = math.hypot(dx, dy) + 1e-9
            r2 = 18 + math.sqrt(len(g[e["to"]]["evidence"])) * 6
            x2 -= dx / d * r2
            y2 -= dy / d * r2
            # RETIRED gets its own dash + opacity, distinct from PROPOSED —
            # conflating the two (both just "not attested") was the
            # 2026-08-04 defect: a dead claim and a pending one read
            # identically. Retired edges only ever reach here in the "all"
            # view; main() strips them before building the live view and
            # before --working-set selection.
            if e["retired"]:
                dash, op = ' stroke-dasharray="2 4"', ".35"
            elif not e["attested"]:
                dash, op = ' stroke-dasharray="6 5"', ".7"
            else:
                dash, op = '', ".7"
            out.append(f'<line class="ed" data-a="{nid}" data-b="{e["to"]}" '
                       f'x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                       f'stroke="{c}" stroke-width="{2.2 if e["attested"] else 1.6}"'
                       f'{dash} marker-end="url(#a-{e["type"]})" opacity="{op}"/>')

    for nid, n in g.items():
        x, y = pos[nid]
        d = depth[nid]
        name, col = issue_tier_read(d)
        r = 18 + math.sqrt(len(n["evidence"])) * 6
        leaf = inbound[nid] == 0
        out.append(f'<g class="nd" data-id="{nid}" style="cursor:pointer">')
        if leaf:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r+5:.0f}" fill="none" '
                       f'stroke="{col}" stroke-width="1.2" stroke-dasharray="3 3" '
                       f'opacity=".55"/>')
        out.append(f'<circle class="sr" cx="{x:.0f}" cy="{y:.0f}" r="{r+11:.0f}" '
                   f'fill="none" stroke="{col}" stroke-width="2" opacity="0"/>')
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{col}" '
                   f'fill-opacity=".16" stroke="{col}" stroke-width="2.4"/>')
        # The LABEL takes the node position; the id is the annotation beneath it.
        # The id is the stable name and the label is the volatile one, but the
        # reader is human: what a node MEANS has to be legible at a glance, and
        # the id only has to be findable when citing it. Stability decides which
        # name is canonical, not which name is prominent.
        #
        # The label overruns the circle, so it is stroked white underneath
        # (paint-order) to stay readable where it crosses the rim.
        lines = issue_label_wrap(n["label"])
        y0 = y + 4 - (len(lines) - 1) * 7.5
        for li, ln in enumerate(lines):
            yy = y0 + li * 15
            out.append(f'<text x="{x:.0f}" y="{yy:.0f}" text-anchor="middle" '
                       f'font-size="13" font-weight="600" fill="none" '
                       f'stroke="{P.GROUND}" stroke-width="4" '
                       f'stroke-linejoin="round">{issue_draw_escape(ln)}</text>')
            out.append(f'<text x="{x:.0f}" y="{yy:.0f}" text-anchor="middle" '
                       f'font-size="13" font-weight="600" '
                       f'fill="#1a1a1a">{issue_draw_escape(ln)}</text>')
        # id and depth on one line — a rank sorted by depth was not stable
        # (26 of 32 nodes sit in a depth tie; one further circle renumbered 13),
        # so prose referring to "node 11" decayed silently. One name per node.
        out.append(f'<text x="{x:.0f}" y="{y+r+15:.0f}" text-anchor="middle" '
                   f'font-size="10.5" fill="#8a8a8a">{nid} · {d} circles</text>')
        out.append('</g>')

    lx, ly = vx0 + 46, vy1 - LEGEND_H + 34
    out.append(f'<g font-size="12" fill="#3a3a3a">')
    out.append(f'<text x="{lx}" y="{ly}" font-size="13" font-weight="700">'
               f'RELATION</text>')
    for i, (t, (c, desc)) in enumerate(EDGE_STYLE.items()):
        yy = ly + 20 + i * 19
        out.append(f'<line x1="{lx}" y1="{yy-4}" x2="{lx+30}" y2="{yy-4}" '
                   f'stroke="{c}" stroke-width="2.4"/>')
        out.append(f'<text x="{lx+38}" y="{yy}">{t} — {desc}</text>')
    yy = ly + 20 + len(EDGE_STYLE) * 19 + 8
    out.append(f'<line x1="{lx}" y1="{yy-4}" x2="{lx+30}" y2="{yy-4}" stroke="#8a8a8a" '
               f'stroke-width="1.6" stroke-dasharray="6 5"/>')
    out.append(f'<text x="{lx+38}" y="{yy}">dashed = proposed, not yet attested by a '
               f'part</text>')
    yy2 = yy + 19
    out.append(f'<line x1="{lx}" y1="{yy2-4}" x2="{lx+30}" y2="{yy2-4}" stroke="#8a8a8a" '
               f'stroke-width="1.6" stroke-dasharray="2 4" opacity=".35"/>')
    out.append(f'<text x="{lx+38}" y="{yy2}">faint dotted = retired — legal no '
               f'longer, "all" view only</text>')
    out.append(f'<text x="{lx}" y="{yy2+22}">circle size = evidence · dotted ring = '
               f'LEAF, nothing depends on it · centre = depth</text>')
    out.append('</g>')
    out.append('</svg>')
    return "\n".join(out)


def _estat(e: dict) -> str:
    """The table panel's one-word gloss for an edge, matching issue_svg_build()'s
    own three-way dash/opacity split — retired distinct from proposed,
    2026-08-17."""
    if e["retired"]:
        return "retired"
    return "attested" if e["attested"] else "proposed"


def issue_html_build(g: dict, svg: str, order: list, inbound: Counter,
               g_live: dict | None = None, svg_live: str = "") -> str:
    """One page, two views. Ruled 2026-08-05: *"Add a live/all selector at the
    top of the page, switching the graph and table between live and all
    issues."*

    BOTH SVGs are embedded and one is hidden, rather than filtering one. The
    two layouts are genuinely different — the live view is laid out for ten
    nodes and the full one for thirty-five, and a filtered full layout would
    put the live nodes wherever the other twenty-five had pushed them. The
    cost is one extra SVG in the file; the alternative is a picture that
    lies about proximity."""
    depth = {i: len({e["circle"] for e in g[i]["evidence"]}) for i in g}
    rows = []
    live_ids = set(g_live or {})
    for nid, n in sorted(g.items(), key=lambda x: -depth[x[0]]):
        cs = sorted({e["circle"] for e in n["evidence"]})
        ev = "".join(
            f'<div class="q"><span class="c">{e["circle"]} · {e.get("part") or "?"}'
            f'</span><br>{issue_draw_escape(e.get("quote",""))}</div>' for e in n["evidence"][:6])
        eg = "".join(
            f'<li><code>{e["type"]}</code> → <b>{e["to"]}</b> '
            f'{issue_draw_escape(g.get(e["to"],{}).get("label","?"))} '
            f'<i>({_estat(e)})</i></li>'
            for e in n["edges"])
        # INBOUND too. A node's relationships run both ways and the panel
        # showed only outbound, so nMMMM read as having one relationship when
        # three edges touch it. `protects` in particular is a claim ABOUT the
        # target, and nPPPP could not see it.
        ib = "".join(
            f'<li><code>{e["type"]}</code> ← <b>{src}</b> '
            f'{issue_draw_escape(g[src]["label"])} '
            f'<i>({_estat(e)})</i></li>'
            for src, sn in sorted(g.items())
            for e in sn["edges"] if e["to"] == nid)
        ac = "".join(f"<li>{issue_draw_escape(a['what'])}</li>" for a in n["actions"])
        rows.append(f'''<tr id="r-{nid}" data-id="{nid}" \
data-live="{1 if nid in live_ids else 0}">
<td class="n">{nid}</td>
<td><b>{issue_draw_escape(n["label"])}</b><div class="m">{len(cs)} circles
 · {f"{cs[0][:10]}..{cs[-1][:10]}" if cs else "no evidence yet"} · {", ".join(sorted(n["held"])) or "—"}
 {"· <b>LEAF</b>" if inbound[nid]==0 else ""}</div>
<div class="d">{issue_draw_escape(n["description"])}</div>
<div class="a"><b>Absent when:</b> {issue_draw_escape(n["absence"])}</div>
{"<div class=rel><b>Relationships</b> (this node as source):<ul class=e>"
 +eg+"</ul></div>" if eg else
 "<div class=rel><b>Relationships</b> (this node as source): none live</div>"}
{"<div class=rel><b>and as target:</b><ul class=e>"+ib+"</ul></div>" if ib else ""}
{"<div class=act><b>Actions:</b><ul>"+ac+"</ul></div>" if ac else ""}
<details><summary>evidence ({len(n["evidence"])})</summary>{ev}</details></td></tr>''')
    # A ROOT IS LIVE (R429, 2026-09-01), so it needs no
    # pulling in any more — `live_ids` already contains it directly, the
    # same way it contains every other live node. From 2026-08-05 (B23) to
    # that date, root was its own status and a root reached this view only
    # when an edge pulled it in (D26); `pulled` below is what counted that.
    # It should read 0 now and forever, for any node — the closure rule
    # (issue_gate.py) no longer admits an edge from a live node to anything
    # BUT a live node, so nothing non-live can be pulled in here either.
    # Left computed, not deleted: a future regression that let a non-live
    # neighbour back into `live_ids` would show up here as a nonzero count
    # rather than silently.
    strictly = sum(1 for i in live_ids if g.get(i, {}).get("status") == "live")
    pulled = len(live_ids) - strictly
    live_note = ("live nodes only — what the graph currently ASSERTS"
                 + (f", plus {pulled} pulled in by an issue-relationship" if pulled else ""))
    sel_html = ("" if not g_live else
                f'<div id="view"><button id="b-all" class="on" '
                f'onclick="setView(0)">all &middot; {len(g)}</button>'
                f'<button id="b-live" onclick="setView(1)">live &middot; '
                f'{strictly}{f"+{pulled}" if pulled else ""}</button>'
                f'<span class="vn" id="vnote">every node, including leads, '
                f'roots and closed</span></div>')
    return f'''<!doctype html><meta charset="utf-8">
<title>Issue graph — {len(g)} nodes</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:{P.GROUND};color:#1e1e1e}}
header{{padding:18px 26px;border-bottom:1px solid {P.RULE}}}
h1{{margin:0 0 4px;font-size:20px}} .sub{{color:#767670;font-size:13px}}
#wrap{{display:flex;align-items:flex-start;gap:0}}
#svg,#svg2{{flex:1 1 auto;position:sticky;top:0;padding:10px}}
#svg svg,#svg2 svg{{width:100%;height:auto}}
#tbl{{flex:0 0 520px;max-height:100vh;overflow:auto;border-left:1px solid {P.RULE};
background:#fff}}
table{{border-collapse:collapse;width:100%}}
td{{padding:12px 14px;border-bottom:1px solid #eee;vertical-align:top;font-size:13px}}
td.n{{width:52px;font-weight:700;color:#2c6e49;font-size:12px;font-family:ui-monospace,Menlo,Consolas,monospace}}
tr.hi{{background:{P.GOLD_WASH}}} tr:target{{background:#eef7f1}}
.m{{color:{P.MUTED};font-size:11px;margin:3px 0 7px}}
.d{{margin-bottom:6px;line-height:1.5}}
.a{{color:#4a4a44;font-size:12px;line-height:1.45;margin-bottom:6px}}
ul.e{{margin:6px 0;padding-left:18px;font-size:12px;color:#555}}
.act ul{{margin:3px 0;padding-left:18px;font-size:12px;color:#555}}
details{{font-size:12px;color:#666}} summary{{cursor:pointer;color:#2c6e49}}
.q{{margin:7px 0;padding-left:9px;border-left:2px solid #ddd;line-height:1.45}}
.q .c{{color:#9a9a94;font-size:10.5px}}
code{{background:#f2f2ee;padding:1px 4px;border-radius:3px;font-size:11px}}
.nd:hover circle{{fill-opacity:.40}}
.sr{{opacity:0}} .act .nd.on .sr{{opacity:.9}}
/* SELECTION. Presentation attributes on the SVG (fill-opacity, stroke-width,
   opacity) lose to a CSS rule, so selection is expressed purely as classes and
   nothing is set inline. Three states, not two: the chosen node, its immediate
   neighbours, and everything else pushed back far enough that the subgraph
   reads on its own.
   Scoped to plain `.act`, not `#svg.act`: issue_draw_box() puts that class on whichever
   of #svg/#svg2 is the active view, and in the live view that is #svg2. An
   id-scoped selector matched only the `all` container, so live selection ran
   (classes were added) but nothing ever dimmed or lit up. */
.nd circle,.nd text,.ed{{transition:opacity .13s,fill-opacity .13s,stroke-width .13s}}
.act .nd{{opacity:.16}}
.act .ed{{opacity:.05}}
.act .nd.nb{{opacity:.85}}
.act .nd.nb circle{{fill-opacity:.34;stroke-width:3}}
.act .nd.on{{opacity:1}}
.act .nd.on circle{{fill-opacity:.66;stroke-width:5}}
.act .nd.on text{{font-weight:800;fill:#111}}
.act .ed.on{{opacity:1;stroke-width:4}}
#view{{margin:.6rem 0 0;display:flex;align-items:center;gap:8px}}
#view button{{font:inherit;font-size:13px;padding:4px 14px;cursor:pointer;
  border:1px solid #c3c2b7;background:#fff;color:#444}}
#view button.on{{background:#2c6e49;border-color:#2c6e49;color:#fff}}
#view .vn{{font-size:12px;color:#73726c}}
tr.off{{display:none}}
tr.hi td{{background:#fff6cc!important}}
tr.hi td.n{{box-shadow:inset 4px 0 0 #2c6e49}}
</style>
<header><h1>Issue graph</h1>
<div class="sub">Derived from 34 transcripts. Every quote machine-verified verbatim.
Click a node or a row to link them. Nothing here is committed.</div>
{sel_html}</header>
<div id="wrap"><div id="svg">{svg}</div><div id="svg2" hidden>{svg_live}</div>
<div id="tbl"><table>{"".join(rows)}</table></div></div>
<script>
/* THE VIEW SWITCH. Both SVGs are in the page and one is hidden; the table
   hides rows by data-live. Selection state is cleared on every switch,
   because a node selected in `all` may not exist in `live` and a highlight
   pointing at nothing is worse than no highlight. */
let LIVE=0;
function setView(v){{
  LIVE=v;
  document.getElementById('svg').hidden = !!v;
  document.getElementById('svg2').hidden = !v;
  document.getElementById('b-all').classList.toggle('on', !v);
  document.getElementById('b-live').classList.toggle('on', !!v);
  document.getElementById('vnote').textContent = v
    ? {live_note!r}
    : 'every node, including leads, roots and closed';
  document.querySelectorAll('tr[data-id]').forEach(r=>{{
    r.classList.toggle('off', !!v && r.dataset.live!=='1');}});
  clear();
}}
const svgBox=document.getElementById('svg');
function issue_draw_box(){{ return document.getElementById(LIVE?'svg2':'svg'); }}
function clear(){{
  document.querySelectorAll('#svg,#svg2').forEach(b=>b.classList.remove('act'));
  document.querySelectorAll('tr').forEach(r=>r.classList.remove('hi'));
  document.querySelectorAll('.nd,.ed').forEach(e=>e.classList.remove('on','nb'));
}}
function sel(id){{
  clear();
  issue_draw_box().classList.add('act');
  const nb=new Set();
  document.querySelectorAll('.ed').forEach(e=>{{
    if(e.dataset.a===id||e.dataset.b===id){{
      e.classList.add('on');
      nb.add(e.dataset.a===id?e.dataset.b:e.dataset.a);
    }}}});
  document.querySelectorAll('.nd').forEach(n=>{{
    if(n.dataset.id===id) n.classList.add('on');
    else if(nb.has(n.dataset.id)) n.classList.add('nb');}});
  const r=document.getElementById('r-'+id);
  if(r){{r.classList.add('hi');r.scrollIntoView({{block:'center',behavior:'smooth'}});}}
}}
document.querySelectorAll('.nd').forEach(n=>n.onclick=e=>{{e.stopPropagation();sel(n.dataset.id);}});
document.querySelectorAll('tr').forEach(r=>r.onclick=()=>sel(r.dataset.id));
svgBox.onclick=clear;
document.onkeydown=e=>{{if(e.key==='Escape')clear();}};
</script>'''


# issue_id_normalise() and working_set_argv_parse() MOVED to working_set_manager.py, 2026-09-03
# (stage 10) — read as WS.*. --live stays retired here: the shared parser only honours
# it when handed a graph, and this tool hands none.


def issue_working_set_limit(g, chosen):
    """Trim to the named nodes, of ANY status, plus whatever they point at.

    Ruled 2026-08-03. NO DEFAULT — without `--working-set` the whole of issues/
    is drawn, every status. A picture that silently hid nodes would be the
    opposite of what the graph is for.

    Anything an included node has an edge to is pulled in and reported: a
    picture that cuts an edge in half draws a relation pointing at nothing."""
    # DIRECTED: only what a kept node points AT is pulled. The walk is
    # working_set_manager.working_set_pull() since 2026-09-03 (stage 10) —
    # this and issue_index.issue_working_set_read() were one loop written twice.
    kept, pulled, unknown = WS.working_set_pull(
        g, chosen, lambda nid: [e["to"] for e in g[nid]["edges"]])
    keep = set(kept)
    out = {k: dict(v) for k, v in g.items() if k in keep}
    for n in out.values():
        n["edges"] = [e for e in n["edges"] if e["to"] in keep]
    return out, sorted(pulled), unknown


def issue_newest_source_read(d: pathlib.Path) -> float:
    """The mtime of the most recently written node file under `d`, or 0.0
    for a directory with no nodes in it at all.

    The same glob issue_draw_read() uses, deliberately: a file this does not
    count is a file whose change cannot make the picture stale, and the two
    disagreeing is the failure nobody would see."""
    return max((f.stat().st_mtime
                for f in d.glob("*n[0-9][0-9][0-9][0-9].toml")), default=0.0)


def issue_draw_is_stale(d: pathlib.Path = ISSUES_DIR) -> bool:
    """Has the graph moved since the picture was last drawn?

    STALENESS, NOT A CHANGE COUNTER, and the difference is the point. A
    counter records the routes someone thought of; this records what the
    picture is actually made of. Every route lands here — a ruling typed at
    cmd>, a [proposed: ...] row accepted at the vetting checkpoint, a
    status change, /issue-apply, a hand edit with a text editor — and so
    does the case no counter reaches: a circle that changed the graph and
    was then ABORTED, whose rulings are already applied while the close
    that would have redrawn never ran. The next close catches it, because
    the question asked is about the files and not about that circle.

    A MISSING PICTURE IS STALE. That is a fresh install's first circle, and
    it is why the shipped work/graph/ is allowed to be empty."""
    if not OUT_HTML.is_file() or not OUT_SVG.is_file():
        return True
    return issue_newest_source_read(d) > min(OUT_HTML.stat().st_mtime,
                                  OUT_SVG.stat().st_mtime)


def issue_draw_describe(g: dict) -> str:
    """One line naming what the picture shows — issues by status, and how
    many live relations are drawn between them.

    Written for the COMMAND PANE at a close, where the reader is the person
    whose issues these are and has just finished a circle: it says what is
    in the picture, not what the renderer did. Statuses are named in the
    graph's own vocabulary (memory/issue_schema.py STATUSES), counted from
    what was actually loaded."""
    by_status = Counter(n.get("status", "?") for n in g.values())
    n_root = sum(1 for n in g.values() if n.get("root"))
    live_edges = sum(1 for n in g.values()
                     for e in n["edges"] if not e["retired"])
    parts = ", ".join(f"{by_status[s]} {s}"
                      for s in sorted(by_status, key=lambda s: (-by_status[s], s)))
    return (f"{len(g)} issue{'' if len(g) == 1 else 's'}"
            + (f" ({parts}" + (f", {n_root} root" if n_root else "") + ")"
               if parts else "")
            + f", {live_edges} live relation{'' if live_edges == 1 else 's'}")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: issue_draw.py issues/ [--working-set nNNNN,nNNNN,...]"
              " [--if-stale]")
        return 2
    arg = pathlib.Path(sys.argv[1])
    # --if-stale: THE CALLER IS A CLOSE, NOT A PERSON. Answered before
    # anything is loaded, so a circle that ruled on nothing pays one
    # directory listing rather than a whole layout. Silent, exit 0 — "the
    # picture is already right" is not news at the end of a circle, and a
    # line saying so every time would train the reader past the lines that
    # ARE news. Ignored for a graph.json snapshot: that has no picture of
    # its own for the live graph's staleness to be a claim about.
    at_close = "--if-stale" in sys.argv[1:]
    # BEFORE THE STALENESS QUESTION, NOT AFTER IT (audit-register.md #6). The whole failure
    # was that "is the picture behind?" got asked of the wrong picture, so the binding has
    # to happen before anything reads OUT_SVG/OUT_HTML — issue_draw_is_stale() reads both.
    if arg.is_dir():
        issue_draw_out_bind(arg)
    if at_close and arg.is_dir() and not issue_draw_is_stale(arg):
        return 0
    if arg.is_dir():
        g = issue_draw_read(arg)
        # never write into issues/ — that directory is the graph itself.
        # OUT_DIR is NAMED (see the constant): this was the script's own
        # directory, a derivation that silently follows the script.
        out = OUT_DIR
        out.mkdir(parents=True, exist_ok=True)
        gp = out / "graph.json"          # only sites the output files
        # THE SOURCE LINE IS FOR A PERSON AT A SHELL, who may have named a
        # directory or a snapshot and wants to be told which was read. At a
        # close there is only ever one source, and issue_draw_describe() below already
        # opens with the same node count — so under --if-stale this would be
        # the same number twice in four lines. The rest of the report is
        # identical through both doors; this one line is not.
        if not at_close:
            print(f"  source: {arg}/ — {len(g)} issues")
    else:
        g = json.loads(arg.read_text(encoding="utf-8"))
        gp = arg
        print(f"  source: {arg} (sandbox snapshot) — {len(g)} issues")
    chosen = WS.working_set_argv_parse(sys.argv[1:])
    if "--live" in sys.argv[1:]:
        print("  note: --live is retired 2026-08-13 — open issue_graph.html and use"
              " its live/all toggle instead")
    for n in g.values():
        n["edges"] = [e for e in n["edges"] if e["to"] in g]
    n_all = len(g)
    if chosen:
        # --working-set never asked to see retired edges or be pulled-into
        # by one — stripped here, before selection, so its own behavior is
        # unchanged from before retired edges were loaded at all.
        for n in g.values():
            n["edges"] = [e for e in n["edges"] if not e["retired"]]
        g, pulled, unknown = issue_working_set_limit(g, chosen)
        if unknown:
            print(f"  unknown issue id(s) ignored: {', '.join(unknown)}")
        print(f"  WORKING SET: {len(g)} of {n_all} issues"
              + (f" ({', '.join(pulled)} pulled in by an issue-relationship)" if pulled else "")
              + "  — nothing removed from issues/; omit --working-set for all")
    inbound = Counter()
    for nid, n in g.items():
        for e in n["edges"]:
            # A retired edge makes no current claim (see issue_draw_read()) —
            # it must not count toward "nothing depends on it" LEAF status,
            # even though it's now drawn in the "all" view.
            if not e["retired"]:
                inbound[e["to"]] += 1
    depth = {i: len({e["circle"] for e in g[i]["evidence"]}) for i in g}
    # Depth order is how the table READS, not what a node is CALLED.
    order = sorted(g, key=lambda x: -depth[x])
    # two_row only for the genuine, unfiltered "all" view — a --working-set
    # picture reuses this same call but is its own, smaller, focused thing,
    # not what "the all view" meant in this request.
    pos, comm = issue_draw_layout(g, two_row=not chosen)
    svg = issue_svg_build(g, pos, inbound, comm)

    # THE SECOND VIEW, built in the same run so one page can hold both.
    # Laid out independently: the live view is arranged for ten nodes and the
    # full one for thirty-five, and reusing the full layout would place the
    # live nodes wherever the other twenty-five had pushed them — a picture
    # that lies about proximity. Skipped when a working set was named, since
    # that IS already a filtered view.
    g_live = svg_live = None
    if not chosen:
        live_ids = [i for i, n in g.items() if n.get("status") == "live"]
        if live_ids and len(live_ids) < len(g):
            g_copy = json.loads(json.dumps(g))
            # Retired edges are "all"-only (the operator, 2026-08-17) — stripped
            # from this copy before limit_to_working_set runs, or a
            # retired edge from a live node would both draw in the live
            # view (which the 2026-08-04 finding ruled against) AND pull
            # its non-live target back in, the exact regression that
            # finding named.
            for n in g_copy.values():
                n["edges"] = [e for e in n["edges"] if not e["retired"]]
            gl, _pulled, _u = issue_working_set_limit(g_copy, live_ids)
            ib_l = Counter()
            for nid, n in gl.items():
                for e in n["edges"]:
                    ib_l[e["to"]] += 1
            pos_l, comm_l = issue_draw_layout(gl)
            g_live, svg_live = gl, issue_svg_build(gl, pos_l, ib_l, comm_l)
    # ONE FILE PER RUN. A standalone `graph-live.*` used to be written here
    # under a separate stem when `--live` was passed — retired 2026-08-13,
    # since it was just a second, easily-stale copy of the live view already
    # embedded (as a toggle) in issue_graph.html whenever a working set isn't
    # named. Before the stem split (2026-08-05) a full run and a `--live` run
    # wrote the same file (then named `graph.html`) and clobbered each
    # other; that risk does not return here because `--live` no longer
    # changes what gets written.
    #
    # NAMED issue_graph.* since 2026-08-13 — `graph.*` was misleadingly
    # generic (there is no other graph in work/graph/ for it to be
    # disambiguated from, but nothing about the name said which graph this
    # was). `graph-live.*` above is the old sibling that name replaced.
    # THE WRITER AND THE STALENESS TEST NOW SHARE THEIR PATHS — audit-register.md #6,
    # 2026-09-08, and this was the sharper half of that finding. These two lines rebuilt the
    # names inline while issue_draw_is_stale() read OUT_SVG/OUT_HTML, so the two ends of the
    # same question — "is the picture behind?" and "where do I put the picture?" — had
    # SEPARATE ANSWERS that only agreed by looking alike. Making the filenames group-aware
    # in the constants alone would have moved one end and not the other, which is the exact
    # shape of the bug being fixed. A snapshot render keeps writing beside its own
    # graph.json, which is why gp.parent stays in the fallback.
    svg_path = OUT_SVG if gp.parent == OUT_DIR else gp.parent / OUT_SVG.name
    html_path = OUT_HTML if gp.parent == OUT_DIR else gp.parent / OUT_HTML.name
    svg_path.write_text(svg, encoding="utf-8", newline="\n")
    html_path.write_text(
        issue_html_build(g, svg, order, inbound, g_live, svg_live or ""),
        encoding="utf-8", newline="\n")
    # THE REPORT IS THE SAME THROUGH BOTH DOORS — a person at a shell and
    # the command pane at a close read these same lines, because circle.py
    # ECHOES this stdout rather than composing a second wording of its own.
    # So it says what the picture SHOWS first and what the renderer did
    # second: at a close the reader has just finished a circle and is being
    # told about their issues, not about a file write.
    print(f"  issue graph redrawn — {issue_draw_describe(g)}")
    try:
        rel = svg_path.relative_to(ROOT).as_posix()
    except ValueError:                   # a snapshot rendered outside the tree
        rel = str(svg_path)
    print(f"  {rel} + .html   ({len(svg):,} bytes of SVG, {W}x{H})")
    # A PLAIN file:// ADDRESS, ruled R365. Windows Terminal and VS
    # Code turn one into something clickable; everywhere else it is at
    # least copyable, which a bare path is not. `as_uri()` and NOT an
    # f-string over the path: this tree's own root carries a SPACE
    # ("Inner Circling"), and an unescaped space ends the address at the
    # space in every terminal that linkifies at all.
    #
    # OSC 8 (the terminal escape that makes arbitrary text a link) was
    # considered and refused: ui/circling.py wraps a pane line by COUNTING
    # CHARACTERS, so the escape's own bytes would be counted as visible
    # width and wreck the layout. The cost accepted instead is that a
    # narrow pane may wrap this address across two lines, where most
    # terminals stop linkifying it — it stays readable and copyable.
    print(f"  {html_path.as_uri()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
