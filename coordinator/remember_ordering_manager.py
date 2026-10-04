#!/usr/bin/env python3
"""
remember_ordering_manager.py — the REMEMBER_ORDERING register: Self's ordering of one entity's
memories, and the memories Self sidelined.

    python coordinator/remember_ordering_manager.py --part <part>     what is saved, most kept first

WHAT IT HOLDS. One file beside each remember.toml — parts/<part>/remember_ordering.toml and
self/remember_ordering.toml — written by the ordering tool (ui/remember_ordering.py) and by
nothing else. One row per memory Self has placed:

    key        the memory's own handle in remember.toml: its `id` when it has one, else its
               `date` (a microsecond stamp). remember_ordering_keys_read() is the one spelling.
    sidelined  when Self sidelined it, UTC ISO; absent on a memory that is carried. A sidelined
               memory stays on file in remember.toml, whole, and is carried in no prompt block —
               not the two windows, not the open-time pack, not the distillate's sources. It is
               still within reach of the part's own [recall: ...]: recall serves the record a
               part's blocks do not carry, and a sidelined memory is exactly that.

THE ROWS RUN MOST KEPT FIRST — the tool's list, top to bottom, the order a prompt reads them in
until its budget is spent. Nothing is reversed anywhere (the operator, 2026-10-02: "the list
should not be reversed upon save"). remember_ordering_read() returns `order` in the same
direction. A file still in the register's FIRST shape (rows the other way, `rejected` for
`sidelined`) is read as what it meant and flagged `legacy` — the comment above _empty() says
how and why — and the next save rewrites it.

A MEMORY THE FILE DOES NOT NAME IS UNSORTED. It was written after the last save. The projection
(remember_prompt_projection.py) places unsorted memories ahead of every ordered one, newest
first, by the rule that has always applied — so a part with no file at all is windowed exactly
as before this register existed.

TWO WRITERS, TOLD APART BY THE ID. remember_manager.py's own rule: a DREAMING-authored record
carries a Coordinator-minted `MEM-` id, a live [remember: ...] stays id-less. The tool's switch
between "written by dreaming" and "the part's own words" is that distinction and no other;
remember_ordering_origin() is its one spelling. (Self's six rows migrated from self.md in
2026-08 carry ids too, and so sit with the dreaming-written: a model wrote them between circles.)

remember.toml IS NEVER WRITTEN HERE. The tool runs in its own process, and remember.toml is
appended to by an open circle and rewritten under the register gate at every close. Keeping the
ordering in its own file leaves that register with the one writer it has always had, and a fault
in this file can cost an ordering, never a memory.

THE READER NEVER RAISES. Block assembly, the distillate's sources and the open-time pack all ask
this module which memories are sidelined; none of them may fail over this file. An unreadable
file reads as no ordering, with the reason in `error` for the tool to show. The corruption gate
(memory/record_verify.py) is what refuses an open over a file that does not parse.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import REGISTER_CLASS as SS                                       # noqa: E402
import remember_manager as RM                                     # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FILE = "remember_ordering.toml"
REGISTER = "remember_ordering"
TABLE = "ordering"
ORDER = ("key", "sidelined")
PREAMBLE = ("Self's ordering of the memories in the remember.toml beside this file, written by the "
            "ordering tool (ui/remember_ordering.py). One row per memory, named by its id there, "
            "or by its date when it has no id. The rows run most kept first: the order a prompt "
            "reads them in until its budget is spent. A row carrying `sidelined` is kept on file "
            "and carried in no prompt block; recall still reaches it. A memory with no row here "
            "is unsorted and is placed ahead of every ordered one, newest first.")

# Who wrote a memory — the two writers remember_manager.py names, by the one marker that tells
# them apart on file.
DREAMING = "dreaming"      # a Coordinator-minted, id-bearing record: the DREAMING pass wrote it
OWN = "own"                # an id-less record: the entity's own [remember: ...] in a circle


# ------------------------------------------------------------------------ keys
def remember_ordering_key(record: dict) -> str:
    """One memory's handle: its `id`, else its `date`."""
    return str(record.get("id") or record.get("date") or "")


def remember_ordering_keys_read(records: list[dict]) -> list[str]:
    """The key of every record, in the order given — FILE order is the one that makes a repeated
    key stable: the register only grows, so the second record to carry a key is always the same
    one, and it is `<key>#2`. No register on file repeats a key (measured 2026-10-02, 204
    records); the suffix is what keeps that from being an assumption."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for r in records:
        k = remember_ordering_key(r)
        n = seen.get(k, 0) + 1
        seen[k] = n
        out.append(k if n == 1 else f"{k}#{n}")
    return out


def remember_ordering_origin(record: dict) -> str:
    """DREAMING for an id-bearing record, OWN for an id-less one — see the module docstring."""
    return DREAMING if record.get("id") else OWN


# ----------------------------------------------------------------------- paths
def remember_ordering_locate(part: str) -> pathlib.Path:
    """The REAL file beside this entity's remember.toml — parts/<part>/ or self/, in the group
    this process is bound to. A dry-run circle reads the same file a live one does, exactly as
    it reads the same remember.toml (remember_manager._real_path)."""
    return RM._real_path(part).with_name(FILE)


# ------------------------------------------------------------------------ read
# THE FIRST SHAPE, read as what it meant. For the first evening of this register (2026-10-02,
# before the operator named the state) a save wrote the rows LEAST kept first and stamped a
# sidelined memory `rejected`. A file in that shape — its preamble says "reversed", or a row
# carries `rejected` — is read with its rows turned back and `rejected` as `sidelined`, and
# flagged `legacy` for the tool to say so; the next save writes the current shape. Read as the
# current shape it would have meant the opposite order and nothing sidelined, with every gate
# green — and a tool started before the change writes it until restarted.
FIRST_SHAPE_FIELD = "rejected"


def _empty(error: "str | None" = None) -> dict:
    return {"saved": None, "order": [], "sidelined": {}, "error": error, "legacy": False}


def remember_ordering_read(part: str) -> dict:
    """{saved, order, sidelined, error, legacy} for one entity. `order` is the saved keys, MOST
    KEPT FIRST — file order; `sidelined` is {key: when}; `legacy` whether the file is in the
    first shape (see above). No file is no ordering. Never raises — see the module docstring."""
    try:
        return remember_ordering_file_read(remember_ordering_locate(part))
    except Exception as e:                                       # noqa: BLE001
        return _empty(f"{type(e).__name__}: {e}")


def remember_ordering_file_read(p: pathlib.Path) -> dict:
    """remember_ordering_read() by PATH — for a reader that holds a record directory rather than
    an entity's name. Never raises."""
    try:
        if not p.is_file():
            return _empty()
        doc = SS.register_read(p)
        rows = [r for r in doc.get(TABLE, []) if isinstance(r, dict) and r.get("key")]
        preamble = doc.get("doc", {}).get("preamble", "") if isinstance(doc.get("doc"), dict) else ""
        legacy = "reversed" in str(preamble) or any(r.get(FIRST_SHAPE_FIELD) for r in rows)
        field = FIRST_SHAPE_FIELD if legacy else "sidelined"
        if legacy:
            rows = list(reversed(rows))
        order: list[str] = []
        for r in rows:
            k = str(r["key"])
            if k not in order:
                order.append(k)
        sidelined = {str(r["key"]): str(r[field]) for r in rows if r.get(field)}
        saved = doc.get("saved")
        return {"saved": str(saved) if saved else None, "order": order, "sidelined": sidelined,
                "error": None, "legacy": legacy}
    except Exception as e:                                       # noqa: BLE001
        return _empty(f"{type(e).__name__}: {e}")


def remember_ordering_kept_read(part: str) -> list[dict]:
    """This entity's remember records in FILE order, the sidelined ones left out — what every
    path that carries a memory into a prompt BLOCK reads in place of
    remember_manager.remember_read(). With no ordering on file it is that list, unchanged. (The
    recall corpus does NOT read this: a sidelined memory stays within recall's reach.)"""
    records = RM.remember_read(part)
    sidelined = remember_ordering_read(part)["sidelined"]
    if not sidelined:
        return list(records)
    keys = remember_ordering_keys_read(records)
    return [r for r, k in zip(records, keys) if k not in sidelined]


# ----------------------------------------------------------------------- write
def remember_ordering_write(part: str, order: list[str], sidelined: "list[str] | dict",
                            now: "str | None" = None) -> dict:
    """Save one entity's ordering. `order` is the tool's list top to bottom, MOST KEPT FIRST;
    `sidelined` names the memories Self sidelined. Returns {saved, order, sidelined, dropped,
    path}.

    A key the register does not hold is DROPPED and reported, never written: the file may only
    name memories that exist. A sidelined memory `order` omits takes the least-kept end. A
    memory already sidelined on file keeps its own stamp, so `sidelined` says when it was
    sidelined and not when the list was last saved."""
    known = set(remember_ordering_keys_read(RM.remember_read(part)))
    prior = remember_ordering_read(part)["sidelined"]
    stamp = now or SS.register_now()
    priority: list[str] = []
    dropped: list[str] = []
    for k in order:
        k = str(k)
        if k not in known:
            dropped.append(k)
        elif k not in priority:
            priority.append(k)
    aside: dict[str, str] = {}
    for k in sidelined:
        k = str(k)
        if k not in known:
            if k not in dropped:
                dropped.append(k)
            continue
        aside[k] = prior.get(k, stamp)
        if k not in priority:
            priority.append(k)
    rows = []
    for k in priority:                           # most kept first — the list as the tool shows it
        row = {"key": k}
        if k in aside:
            row["sidelined"] = aside[k]
        rows.append(row)
    doc = {"register": REGISTER, "saved": stamp, "doc": {"preamble": PREAMBLE}, TABLE: rows}
    p = remember_ordering_locate(part)
    p.parent.mkdir(parents=True, exist_ok=True)
    SS.register_write(p, doc, TABLE, ORDER)
    return {"saved": stamp, "order": priority, "sidelined": aside, "dropped": dropped, "path": p}


def remember_ordering_clear(part: str) -> bool:
    """Remove this entity's ordering file: every memory is unsorted again, none is sidelined, and
    the window is the newest-first one. True when a file was removed."""
    p = remember_ordering_locate(part)
    if not p.is_file():
        return False
    p.unlink()
    return True


def main() -> int:
    a = sys.argv[1:]
    part = a[a.index("--part") + 1] if "--part" in a and a.index("--part") + 1 < len(a) else None
    if not part:
        print("  --part <name> required (a part's folder name, or self)")
        return 1
    st = remember_ordering_read(part)
    if st["error"]:
        print(f"  {remember_ordering_locate(part)} does not read: {st['error']}")
        return 1
    if not st["saved"]:
        print(f"  no ordering saved for {part} — its window is newest first")
        return 0
    records = RM.remember_read(part)
    by_key = dict(zip(remember_ordering_keys_read(records), records))
    print(f"  {part}: {len(st['order'])} ordered, {len(st['sidelined'])} sidelined, "
          f"{len([k for k in by_key if k not in st['order']])} unsorted — saved {st['saved']}")
    for i, k in enumerate(st["order"], 1):
        rec = by_key.get(k, {})
        text = " ".join(str(rec.get("text", "(not in the register)")).split())
        mark = "sidelined" if k in st["sidelined"] else f"{i:>9}"
        who = "dreaming" if remember_ordering_origin(rec) == DREAMING else "own     "
        print(f"  {mark}  {who}  {k[:26]:26}  {text[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
