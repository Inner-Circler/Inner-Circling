#!/usr/bin/env python3
"""
JOURNAL_CLASS.py — the shared LEDGER/JOURNAL register base (docs/MEMORY_DESIGN.md,
"PROMPT_LEDGER / PROMPT_JOURNAL — a shared record-chain abstraction"; docs/BNF.md's LEDGER/
JOURNAL productions; B105, 2026-09-05).

Checked directly against the code before this was built: `circle_history_manager.py`,
`self_observation_manager.py` and `circle_journal_manager.py` each carried an IDENTICAL private
`_doc()` (differing only in register name and preamble) and the same three-function shape — read
the rows, read the most recent, render a new one — genuinely duplicated rather than shared.
`remember_manager.py`'s own `remember_dreamt_render()` carries the same render shape for its one
coordinator-minted row kind (MEM-), alongside real per-part/live-sandbox path resolution,
salience weighting and windowed-budget selection this base does not touch at all.

WHAT THE BASE OWNS: reading the table (`read`), reading the newest row by date (`latest` — what
each register's own `*_latest_read()` wrapper needs), finding the chain target a new row should
link to (`chain_target` — file order, never date order, see its own docstring), and rendering one
new row: id allocation against `next_id` (a high-water mark, never reused — the discipline every
register in this project follows), the date stamp, optional auto-chain or explicit-target chain,
and an optional cap refusal (`new_render`). The save (REGISTER_CLASS.register_write) is NOT here —
every existing `*_new_render()` this base replaces was already PURE, returning `(new_doc, rec)`
for the phase-2 driver to stage; this stays that way.

WHAT IT DOES NOT: text preparation (`" ".join(text.split())` vs `.strip()` vs
`remember_truncate()` — genuinely different per register), empty-text refusal (only
self_observation_manager.py does this), which optional fields a caller includes and under what
condition (`if salience:` truthiness in self_observation vs `if salience is not None:` in
remember, `if note:`, `if provenance:`), self_observation's own retire/purge (an in-place mutation
of an EXISTING row — a different shape from "append new", and the only register with a use for
it today), and remember's per-part/live-sandbox path resolution, salience constants, word-cap
truncation and chain-walking (`remember_chain_read`/`remember_chain_qualifies`) — real production
complexity NEXT.md's own B105 entry named, and none of it belongs here. `new_render()` takes an
ALREADY-PREPARED `fields` dict from its caller and adds only `id`/`date`/`chain` to it. Every
register-specific decision above stays that module's own, layered ON this base rather than forced
into it — the same relationship `practice_manager.py`'s op dispatch/routing/addressees already
has to `PROPOSE_CLASS.py`.

CHAIN TARGET IS FILE ORDER, NEVER DATE ORDER. Every existing chain rule this base replaces scans
file order — `circle_history_new_render()`/`circle_journal_new_render()` used `recs[-1]`,
`self_observation_new_render()` used `recs[-1]`, `remember_dreamt_render()` used
`next(r for r in reversed(recs) if r.get("id"))`. None of the four ever sorted by date. `latest()`
below IS date-sorted (what a `*_latest_read()` wrapper answers "what is the newest entry" with),
so `new_render(..., chain=True)` calls `chain_target()`, never `latest()` — the two diverge
whenever a register's file order is not the same as its date order, which the register gate only
WARNs on single-tree (DATE-ORDER) and which self_observation's day-scoped migrated rows plausibly
exhibit.

EVERY CONFIGURABLE IS A FUNCTION, NOT A VALUE, matching PROPOSE_CLASS.py's own discipline:
`path_fn`/`now_fn` are lambdas read at CALL time, not captured at construction — a module-level
instance (`circle_history_manager.py`'s own `_JC`, one per register, exactly like `proposal_manager.py`'s
`_PC`) still sees a test harness's rebind of its module's `PATH` global, the same late-binding
`PROPOSE_CLASS.py` documents for its own lambdas.

`path_fn`/`register`/`preamble` are OPTIONAL — only `doc()`/`read()`/`latest()` need them.
`remember_manager.py`'s own register has no single fixed path (per part, per live/sandbox root) and
no `{"register":..., "next_id":..., "doc":{...}}` envelope shape at all (its own `_load()` returns
`{TABLE: []}` when the file is absent) — it keeps its own loader entirely and uses only
`new_render()`, which needs none of the three.
"""

from __future__ import annotations

import copy
import pathlib
import sys
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import REGISTER_CLASS as SS                                       # noqa: E402


class JournalClass:
    def __init__(self, *, table: str, id_prefix: str, cap: int | None = None,
                 cap_label: str | None = None,
                 register: str | None = None, preamble: str | None = None,
                 path_fn: Callable[[], pathlib.Path] | None = None,
                 now_fn: Callable[[], str] | None = None):
        self.table = table
        self.id_prefix = id_prefix
        self.cap = cap
        self.cap_label = cap_label or table.upper()
        self.register = register
        self.preamble = preamble
        self.path_fn = path_fn
        self.now_fn = now_fn or SS.register_now

    # ------------------------------------------------------------ reads
    def doc(self) -> dict:
        """The register's own doc, loaded from disk, or the empty shape every register in
        this project opens with. Needs `path_fn` — raises if this instance was built without
        one (a `new_render()`-only instance, e.g. remember_manager.py's own)."""
        if self.path_fn is None:
            raise ValueError(f"{self.table}: doc() needs path_fn; this instance was built for "
                              f"new_render() only")
        path = self.path_fn()
        if path.is_file():
            return SS.register_read(path)
        return {"register": self.register, "next_id": 1,
                "doc": {"preamble": self.preamble}, self.table: []}

    def read(self) -> list[dict]:
        """Every row on file, unordered — the one reader."""
        return self.doc().get(self.table, [])

    def latest(self, *, require_id: bool = False) -> dict | None:
        """The newest row BY DATE, or None. `require_id` skips id-less rows first — what
        remember_manager.remember_newest_dreamt_read() needs (the most recent DREAMING-authored
        row, never a live id-less [remember: ...])."""
        rows = self.read()
        if require_id:
            rows = [r for r in rows if r.get("id")]
        rows = sorted(rows, key=lambda r: r.get("date", ""))
        return rows[-1] if rows else None

    # ------------------------------------------------------------- chain
    def chain_target(self, recs: list[dict]) -> str | None:
        """The most recent ID-BEARING row in FILE ORDER — see the module docstring for why
        this is never date-sorted. None when no row in `recs` carries an id (a fresh register,
        or remember.toml before its first DREAMING-authored write)."""
        for r in reversed(recs):
            if r.get("id"):
                return r["id"]
        return None

    # ------------------------------------------------------------ writes
    def new_render(self, doc: dict, fields: dict, *, chain: bool | str = False,
                   cap_field: str = "text") -> tuple[dict, dict]:
        """PURE — one new row for the phase-2 driver. `fields` is already fully prepared by
        the caller (text normalized, empty-checked, optional fields already decided in or out);
        this only mints the id, stamps the date, optionally chains, optionally refuses oversize,
        appends, and bumps next_id.

        `chain=True` auto-chains to `chain_target()`'s own answer (silently omits the field when
        there is no id-bearing predecessor yet — same as every register this replaces).
        `chain="SOME-ID"` chains to exactly that id — the caller has already validated it exists
        (self_observation_continue_render()'s own rule); this never re-validates a named target.
        `chain=False` (default) never sets the field at all.

        Refuses (ValueError), never truncates, when `self.cap` is set and the named `cap_field`
        exceeds it — the discipline every capped register in this project already follows: a cut
        record is a worse record than the prior one standing alone."""
        if self.cap is not None and cap_field in fields and len(fields[cap_field]) > self.cap:
            raise ValueError(
                f"{self.cap_label} is {len(fields[cap_field]):,} chars, cap is {self.cap} — "
                f"refused, not truncated")
        doc = copy.deepcopy(doc)
        recs = doc.setdefault(self.table, [])
        n = doc.get("next_id", 1)
        rec = {"id": f"{self.id_prefix}{n:04d}", "date": self.now_fn(), **fields}
        if chain is True:
            target = self.chain_target(recs)
            if target:
                rec["chain"] = target
        elif chain:
            rec["chain"] = chain
        recs.append(rec)
        doc["next_id"] = n + 1
        return doc, rec
