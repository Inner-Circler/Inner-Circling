#!/usr/bin/env python3
"""
paths.py — the one home for this tree's path constants and the roster
projection every writer shares. Phase 1 of the coordinator partitioning
(reviewed 2026-08-16); step 0, the module everything later extracted
reads its locations from.

WHY ONE HOME. Before this module, relocating a single register file
meant finding every module that had independently derived its path —
coordinator/best_practices.toml alone was hardcoded in BOTH
self_schema.py and check_best_practices.py. A later placement ruling
(the memory/ question, unruled) becomes one edit here instead of a
sweep.

CONSTANTS ONLY, never rebound. Consumers use
`from paths import ROOT, ...` — safe precisely because nothing here is
ever reassigned at runtime. (The attribute-access discipline that
`seam.emit`/`seam.read_line`/`circle.dev_mode` require exists because
those ARE rebound; these are not.) Note for future writers: several
functions in this tree use a LOCAL variable named `paths` — prefer
`from paths import X` over `import paths` so a local can never shadow
the module inside a function body.
"""

from __future__ import annotations

import pathlib

import roster as R

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent                      # D:\Projects\Inner Circling
SANDBOX = ROOT / "work" / "sandbox"     # moved from coordinator/sandbox, R176, 2026-08-15

# The data-directory roots — where the user-owned record lives. Defined
# here (2026-08-16, phase-1 review) so a future memory/ consolidation is
# a ruling plus one edit, not an archaeology sweep. issue_schema.py and
# roster.py still derive their own copies today; converging them on
# these is deliberate later work, not smuggled into phase 1.
SELF_DIR = ROOT / "self"
PARTS_DIR = ROOT / "parts"
ISSUES_DIR = ROOT / "issues"
CIRCLES_DIR = ROOT / "circles"
TICKING_DIR = ROOT / "ticking"          # the JOURNAL (R391/R396) — user
                                        # record; pull-main keeps the lab's

# self/best_practices.toml — RETURNED to self/ 2026-08-16 by Self's
# ruling on the memory/ decomposition ("out of coordinator and into
# self/"), reversing the 2026-08-11 circle-scoped move and putting the
# register — which physically carries the R133-merged better_options
# rows, Self's own content — back with the user-owned record. Was
# hardcoded independently by self_schema.py (BEST) and
# check_best_practices.py (BP); both read this constant, which is what
# made the move one edit here instead of a sweep.
BEST_PRACTICES = SELF_DIR / "best_practices.toml"

# parts/<dir> -> transcript tag. B29: derived from roster.py, the one
# roster every reader shares — was a hand-typed copy, kept in sync with
# circle_close.py's TAG_TO_DIR (and the other seven) only by discipline.
PART_TAGS = R.TAG_BY_DIR
