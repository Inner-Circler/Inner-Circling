# work/nightly/

Empty delegate, shipped so the directory exists. This is
TRANSACTION_CLASS.py's staging root — where each run's TRANSACTION file
and its staging/ and rollback/ live while a
swap is in flight — shared by `inter_circle.py` and
`circle_audit.py` (whose own lock and snapshots are in
work/circle_audit/). Despite the name, nothing
here is scheduled, and every write to it happens inside a `/close` or an
audit you run yourself. This delegate ships the
directory with nothing in it; git does not track empty directories, so
this README is what keeps the directory present in a clone.
