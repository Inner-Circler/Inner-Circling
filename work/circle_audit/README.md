# work/circle_audit/

Empty delegate, shipped so the directory exists. `circle_audit.py`
writes its lock and `baseline_<timestamp>/`
snapshots here (`WORK = ROOT / "work" / "circle_audit"`); its transaction
staging lives under work/nightly/, TRANSACTION_CLASS.py's own root. This
delegate ships the directory with nothing in it; git does not track empty
directories, so this README is what keeps the directory present in a clone.
