# issues/

**TOML, one file per node.** `coordinator/issue_schema.py` is the only
reader and writer; `coordinator/issue_gate.py` is the invariant gate.

An issue is something OWED — a thing the circle has recognised and not
yet resolved. Nodes carry a label, a description, evidence quoted from
circles, and edges to other nodes.

**The filename prefix is the STATUS; the id is the identity.**

```
nNNNN.toml    live
L_nNNNN.toml  lead
R_nNNNN.toml  ROOT — a source the live
              graph descends FROM
S_nNNNN.toml  settled
D_nNNNN.toml  declined
X_nNNNN.toml  retired
```

Renaming the file changes the status. The `n####` inside never changes.

**This directory is empty on purpose, and your ids will be your own.**
Node ids are allocated in your graph, counting up from the first. They
do not
correspond to anyone else's — an id in someone else's notes means
nothing here.

Prose lives in `"""` blocks, hard-wrapped; a single newline is soft.
Run `issue_gate.py` after any hand edit.
