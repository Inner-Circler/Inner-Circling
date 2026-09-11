# work/manifests/

Empty delegate, shipped so the directory exists. This delegate
ships the directory with nothing in it; git does not track empty
directories, so this README is what keeps the directory present in a
clone.

**No coordinator/*.py WRITES this directory.** One reads it:
`memory/record_verify.py`'s corruption sweep parses every JSON file here
at circle open and in `circle_audit.py` phase 0, so a damaged manifest refuses
a circle rather than surfacing later. It was long
described here as the retired batch nightly's dead manifest output;
that attribution was wrong, corrected 2026-08-31 alongside the same
error in `memory/record_verify.py` and `coordinator/circle_audit.py`.
The real project's own `work/manifests/*.json` files are written by
this repo's development tooling — `.claude/skills/workflow`, a Claude
Code skill that tracks its own multi-step engineering tasks there. That
is repo-development infrastructure, not shipped product code, so a
fresh install's own `work/manifests/` never gets populated by anything
the product itself does.

So in an install the directory stays empty unless you put a JSON file
here yourself — and anything you do put here is read, and must parse,
before every circle opens.
