# work/manifests/

Empty delegate for packaging/exceptions.toml's work/ entry. This delegate
ships the directory with nothing in it; git does not track empty
directories, so this README is what keeps the directory present in a
clone.

**Nothing writes or reads this directory today.** It held dreaming-run
manifests, `*.json` and `*-dreaming.json`, written by the batch nightly.
That path is gone: batch processing was removed (one run is one circle,
processed synchronously at `/close`), and `coordinator/circle_audit.py`
— which this file named as `nightly.py` until 2026-08-19 — says so in
its own docstring: *"the dreaming manifests under work/manifests/ are
dead records; nothing here reads them any more."*

The directory still ships because the exceptions entry still names it,
and an empty delegate is cheaper than a special case. If that entry ever
goes, this goes with it.
