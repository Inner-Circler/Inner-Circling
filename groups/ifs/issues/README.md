# issues/

**TOML, one file per node.** `memory/issue_schema.py` is the only
reader and writer; `memory/issue_gate.py` is the invariant gate.

An issue is something OWED — a thing the circle has recognised and not
yet resolved. Nodes carry a label, a description, evidence quoted from
circles, and edges to other nodes.

**The filename prefix shows the STATUS; the id is the identity.**

```
nNNNN.toml    live
L_nNNNN.toml  lead
R_nNNNN.toml  ROOT — a source the live
              graph descends FROM
S_nNNNN.toml  settled
D_nNNNN.toml  declined
X_nNNNN.toml  retired
```

The prefix follows the node's own `status` field — except `R_`, which
follows `root = true` (a root's status is live) — and
`memory/issue_gate.py` refuses a file whose name and fields disagree — so
renaming a file does not change its status, it breaks the node. Change a
status with `memory/issue_status.py` (`memory/docs/issue_status.md`),
or with `/issue-status nNNNN = <value>` typed at the `Self>` prompt of
`coordinator/circle.py` run on its own: either one writes the field, the rename and a
history line as one act. The `n####` inside never changes.

**No nodes ship, on purpose, and your ids will be your own.**
Node ids are allocated in your graph, counting up from the first. They
do not
correspond to anyone else's — an id in someone else's notes means
nothing here. The first node is asked for at your first live open — the
initialization dialog — and after that one is added by `/issue-add`
typed at the `Self>` prompt of `coordinator/circle.py` run on its own, or
by a part's `[proposed: /issue-add ...]` that you approve at a close.

`issue_model.md` beside this file is not a node and does not go: it is the
prologue every circle's BLOCK 2 (circle_objectives) is built on, and a circle refuses to open
without it.

`issue_graph.svg` and `issue_graph.html`, once your first circle has drawn
them, are not nodes either: they are the PICTURE of this graph. The page
inlines the drawing, lists every issue beside it, and toggles between
"everything" and "just what is live"; it opens from disk, offline. A live
close whose graph moved redraws both and prints the address; `/issue-graph`
opens the page. Nothing reads them back, and git does not track them —
deleting them costs one redraw:

    .venv/Scripts/python ui/issue_draw.py groups/<group>/issues/

Prose lives in `"""` blocks, hard-wrapped; a single newline is soft.
Run `memory/issue_gate.py` after any hand edit.
