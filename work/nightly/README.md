# work/nightly/

Empty delegate, shipped so the directory exists. This is
TRANSACTION_CLASS.py's staging root — where each run's TRANSACTION file
(JOURNAL until 2026-09-04, R448) and its staging/ and rollback/ live while a
swap is in flight — shared by `inter_circle.py` and
`circle_audit.py` (whose own lock and snapshots moved to
work/circle_audit/ at the 2026-08-19 rename). The name is historical —
from when this ran on a nightly schedule, retired 2026-08-18 (R228; the last
scheduled run was 2026-07-28); nothing
here is scheduled, and every write to it happens inside a `/close` or an
audit you run yourself. This delegate ships the
directory with nothing in it; git does not track empty directories, so
this README is what keeps the directory present in a clone.
