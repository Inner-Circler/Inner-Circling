# work/manifests/

Empty delegate for packaging/exceptions.toml's work/ entry. This delegate
ships the directory with nothing in it; git does not track empty
directories, so this README is what keeps the directory present in a
clone.

**No coordinator/*.py reads or writes this directory.** It was long
described here as the retired batch nightly's dead manifest output;
that attribution was wrong, corrected 2026-08-31 alongside the same
error in `coordinator/check_integrity.py` and `coordinator/circle_audit.py`.
The real project's own `work/manifests/*.json` files are written by
this repo's development tooling — `.claude/skills/workflow`, a Claude
Code skill that tracks its own multi-step engineering tasks there. That
is repo-development infrastructure, not shipped product code, so a
fresh install's own `work/manifests/` never gets populated by anything
the product itself does.

The directory still ships because the exceptions entry still names it,
and an empty delegate is cheaper than a special case. If that entry ever
goes, this goes with it.
