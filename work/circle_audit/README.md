# work/circle_audit/

Empty delegate, shipped so the directory exists. `circle_audit.py`
(nightly.py until 2026-08-19) writes its lock and `baseline_<timestamp>/`
snapshots here (`WORK = ROOT / "work" / "circle_audit"`); its transaction
staging still lives under work/nightly/, TRANSACTION_CLASS.py's own root. This
delegate ships the directory with nothing in it; git does not track empty
directories, so this README is what keeps the directory present in a clone.
