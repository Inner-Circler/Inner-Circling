# work/graph/

**Where the picture of your issue graph is written.** Empty until your
first circle draws one; git does not track empty directories, so this
README is what keeps the folder here in a fresh clone.

`ui/issue_draw.py` writes two files into this folder:

    issue_graph.svg     the drawing itself
    issue_graph.html    the same drawing, wrapped in a page you can open —
                        with every issue listed beside it, and a toggle
                        between "everything" and "just what is live"

The page is self-contained. It inlines the drawing and reaches the
network for nothing, so it opens from disk and keeps working offline,
forever, with no server and no install.

**It is redrawn for you.** At the end of every live circle whose issue
graph moved — because you ruled on an issue, or accepted something a part
proposed — the close redraws this and prints its address in the command
pane, so you can open it and look at where things stand. A circle that
changed nothing redraws nothing.

To draw it yourself at any time:

    python ui/issue_draw.py issues/

**Nothing reads these files back.** They are yours to look at. Deleting
them costs one redraw; the graph itself lives in `issues/`, which is the
thing to keep.

`ui/docs/issue_draw.md` is the full manual.
