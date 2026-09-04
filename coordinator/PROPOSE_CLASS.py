#!/usr/bin/env python3
"""
PROPOSE_CLASS.py — the shared PROPOSE-class register base.
(propose_class.py until 2026-09-03 — B99 stage 18b, Q-5 under R435: an entity's file is ALLCAPS_CLASS.py)
docs/HELP_DESIGN.md §6's proposed collapse, built 2026-08-16 (phase 1
step 4 of the coordinator partitioning): the stage/approve/deny/
tombstone shape was duplicated near-verbatim across four register
modules when that section was written; R202 folded requests.py and
relation_proposals.py into proposal_manager.py, and this module now holds the
ONE copy of what remained duplicated between proposal_manager.py and
practice_manager.py (check_best_practices.py until 2026-09-03) — "parameterized by table name, id prefix, and
field order", exactly as §6 put it.

WHAT THE BASE OWNS: reading the table (entries/by_id/pending), id
allocation against next_id (a high-water mark, never reused), the
resolution guard ("not found" / "not pending"), the provenance
backfill, the simple accept flip, the tombstone deny (ruled 2026-08-12:
denied rows are KEPT, only `state` says which), the staging-field drop
on resolution, and the save (post-mutate hook, then REGISTER_CLASS.register_write).

WHAT IT DOES NOT: register-specific row shapes (each register's
stage()), check_best_practices' op dispatch (add/revise/delete), its
addressees, render_stage, delete and _routing_check — practice/
better_option folding was explicitly OUT of R202's scope (ruled: build
the propose mechanism now, rule on folding practice separately, later),
so those stay that module's own, layered ON this base rather than
forced into it.

EVERY CONFIGURABLE IS A FUNCTION, NOT A VALUE, deliberately:
`path_fn`/`doc_fn`/`now_fn` are lambdas that read their register's own
module globals at CALL time. The test harnesses swap `PR.PROPOSALS`,
`PM.BP` and `PM._doc` as module attributes — a value captured here at
import time would go stale the moment a test rebinds one, the same
late-binding trap seam.py documents for emit/read_line. REGISTER_CLASS is
reached as a module attribute (`SS.register_write`) for the same reason — tests
swap it — and always with the exact (path, doc, table, order) argument
shape those harnesses' replacement lambdas accept.

THE TWO REGISTERS' `_now()` DIVERGED at build time — proposal_manager.py
stamped UTC with offset, check_best_practices.py (practice_manager.py since
2026-09-03) naive local — and
phase 1 preserved both via `now_fn` rather than smuggle a unification
into a refactor. RULED 2026-08-16: UTC is the standard; both registers
now stamp identically for new rows, and the naive-local stamps in
best_practices' settled history stay as written. `now_fn` remains a
parameter — the mechanism outlived the divergence it was built for.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import REGISTER_CLASS as SS                                       # noqa: E402


class ProposeClass:
    def __init__(self, *, table: str, order: tuple[str, ...],
                 staging_only: tuple[str, ...],
                 path_fn: Callable[[], pathlib.Path],
                 doc_fn: Callable[[], dict],
                 now_fn: Callable[[], str],
                 new_id: Callable[[int], str],
                 author_field: str = "author",
                 post_mutate: Callable[[dict], None] | None = None):
        self.table = table
        self.order = order
        self.staging_only = staging_only
        self.path_fn = path_fn
        self.doc_fn = doc_fn
        self.now_fn = now_fn
        self.new_id = new_id
        self.author_field = author_field
        self.post_mutate = post_mutate

    # ------------------------------------------------------------ reads
    def entries(self) -> list[dict]:
        return self.doc_fn().get(self.table, [])

    def by_id(self, pid: str) -> dict | None:
        for r in self.entries():
            if r["id"] == pid:
                return r
        return None

    def pending(self) -> list[dict]:
        return [r for r in self.entries() if r.get("state") == "proposed"]

    # ----------------------------------------------------------- writes
    def allocate_id(self, doc: dict) -> str:
        """Bump next_id on `doc` and return the new row's id. next_id is
        a high-water mark — an id is never reused, the discipline every
        register in this project follows."""
        n = doc.get("next_id", 1)
        doc["next_id"] = n + 1
        return self.new_id(n)

    def save(self, doc: dict) -> None:
        if self.post_mutate is not None:
            self.post_mutate(doc)
        SS.register_write(self.path_fn(), doc, self.table, self.order)

    def provenance(self, row: dict) -> str:
        """The speaker IS known — `sources`/`circle` carry it; this just
        keeps it from being thrown away when the staging fields are
        dropped at resolution. Only consulted where the register's
        author field is still blank — an existing value is never
        overwritten."""
        who = ", ".join(row.get("sources", [])) or "unknown"
        circ = row.get("circle", "")
        return f"{who} in {circ}" if circ else who

    def find_pending(self, rows: list[dict],
                     pid: str) -> tuple[dict | None, str | None]:
        """(row, None) or (None, refusal) — the shared guard every
        resolution path runs first, with the exact refusal wording every
        register already used."""
        row = next((r for r in rows if r["id"] == pid), None)
        if row is None:
            return None, f"{pid} not found"
        if row.get("state") != "proposed":
            return None, f"{pid} is not pending (state={row.get('state')!r})"
        return row, None

    def drop_staging(self, row: dict) -> None:
        for k in self.staging_only:
            row.pop(k, None)

    def accept(self, pid: str) -> tuple[bool, str]:
        """The simple ruling FOR — flips state, backfills the register's
        author field from provenance if blank, drops staging fields. The
        caller must already have satisfied whatever else the row needed
        (a command row's execution, e.g.) before calling this — the base
        touches only the register's own state, never the graph."""
        doc = self.doc_fn()
        row, why = self.find_pending(doc.get(self.table, []), pid)
        if row is None:
            return False, why
        if not row.get(self.author_field, "").strip():
            row[self.author_field] = self.provenance(row)
        row["state"] = f"accepted by Self {self.now_fn()}"
        self.drop_staging(row)
        self.save(doc)
        return True, f"{pid} approved"

    def deny(self, pid: str) -> tuple[bool, str]:
        """Denied rows are TOMBSTONED, not deleted — ruled 2026-08-12: a
        denial that leaves no trace cannot be told apart from one that
        never happened. Staging fields are dropped the same as on
        acceptance, so a denied row is otherwise indistinguishable in
        shape from an accepted one — only `state` says which. The author
        field is backfilled from provenance first, exactly as accept()
        does — drop_staging() pops sources/circle, so skipping the
        backfill here (as this method did until 2026-08-19) erased who
        proposed the row, and in which circle, from the tombstone."""
        doc = self.doc_fn()
        row, why = self.find_pending(doc.get(self.table, []), pid)
        if row is None:
            return False, why
        if not row.get(self.author_field, "").strip():
            row[self.author_field] = self.provenance(row)
        row["state"] = f"denied by Self {self.now_fn()}"
        self.drop_staging(row)
        self.save(doc)
        return True, f"{pid} denied — kept as a tombstone"
